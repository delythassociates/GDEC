"""
Intelligent Runtime for GDEC.
Coordinates execution planning, finite-element assembly, adaptive refinement,
resource monitoring, and stopping decisions with true discrete stage profiling.
"""

from __future__ import annotations
import time
from typing import Callable, Generator, List, Optional, Tuple
import numpy as np

from gdec.language.ir import ProblemIR
from gdec.core.planner import ExecutionPlan, ExecutionPlanner
from gdec.core.controller import RuntimeController, ControllerDecision
from gdec.core.cost_model import CostModel
from gdec.core.telemetry import IterationRecord, ExecutionTrace, TelemetryTracker
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver, FEMSolution
from gdec.fem.estimators import RefinementEstimator, IndicatorResult
from gdec.fem.adaptivity import MeshAdaptor
from gdec.fem.postprocess import PostProcessor, PostprocessResult
from gdec.fem.boundary_conditions import parse_boundary_conditions, parse_loads


class GDECRuntime:
    def __init__(self, plan: ExecutionPlan, ir: ProblemIR):
        self.plan = plan
        self.ir = ir
        self.telemetry = TelemetryTracker()
        self.cost_model = CostModel()
        self.controller = RuntimeController(
            target_accuracy_pct=plan.accuracy_target_pct,
            max_dofs_budget=plan.max_dofs_budget,
            max_iterations=plan.max_iterations,
        )

        mat = ir.material
        geo = ir.geometry
        self.constitutive = ConstitutiveTensor.from_properties(
            E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
        )
        self.solver = LinearElasticitySolver(self.constitutive)
        self.estimator = RefinementEstimator(self.constitutive)
        self.postprocessor = PostProcessor(self.constitutive)

        self.fixed_bcs = parse_boundary_conditions(ir.boundary_conditions)
        self.loads = parse_loads(ir.loads)

    def execute(
        self, callback: Optional[Callable[[IterationRecord, GDECMesh, PostprocessResult], None]] = None
    ) -> ExecutionTrace:
        """Execute simulation to completion and return the full ExecutionTrace."""
        trace = ExecutionTrace(
            problem_name=self.plan.problem_name,
            strategy=self.plan.refinement_strategy,
            target_accuracy_pct=self.plan.accuracy_target_pct,
            budget_max_dofs=self.plan.max_dofs_budget,
            converged=False,
            stop_reason="In progress",
            total_wall_time_sec=0.0,
        )

        start_wall_time = self.telemetry.now()

        # Step 1: Initial mesh
        nx, ny = self.plan.initial_mesh_shape
        current_mesh = GDECMesh.create_cantilever_mesh(
            width=self.ir.geometry.width, height=self.ir.geometry.height, nx=nx, ny=ny
        )

        initial_dofs = current_mesh.nnodes * 2
        if initial_dofs > self.plan.max_dofs_budget:
            trace.converged = False
            trace.stop_reason = (
                f"Initial problem infeasible: initial mesh ({initial_dofs} DOFs) "
                f"exceeds maximum DOFs budget ({self.plan.max_dofs_budget} DOFs). Execution aborted."
            )
            trace.total_wall_time_sec = self.telemetry.now() - start_wall_time
            self._attach_evidence_and_refusal(trace, current_mesh, None, None, budget_exhausted=True)
            return trace

        iteration = 1
        previous_qoi: Optional[float] = None
        current_dofs = 0
        last_refinement_time = 0.0
        last_sol: Optional[FEMSolution] = None
        last_ind: Optional[IndicatorResult] = None

        while True:
            iter_start_time = self.telemetry.now()
            mem_start = self.telemetry.get_current_memory_mb()

            # Step 2: Solve FEM system (exact stage timings measured inside solver)
            need_adjoint = self.plan.refinement_strategy in ["goal_aware", "dwr", "goal_oriented_dwr"]

            sol = self.solver.solve(
                gdec_mesh=current_mesh,
                loads=self.loads,
                fixed_boundaries=self.fixed_bcs,
                qoi_boundary=self.ir.objective.boundary,
                qoi_component=self.ir.objective.component,
                solve_adjoint=need_adjoint,
                reuse_factorization=True,
            )

            current_dofs = sol.basis.N
            current_qoi = sol.qoi
            last_sol = sol

            # Step 3: Post-processing with discrete timer
            t_post0 = self.telemetry.now()
            post = self.postprocessor.process(current_mesh, sol)
            postprocess_time = self.telemetry.now() - t_post0

            # Step 4: Convergence calculation
            successive_change = self.controller.calculate_successive_change(
                current_qoi, previous_qoi
            )

            # Step 5: Refinement indicator computation
            t_ind0 = self.telemetry.now()
            if self.plan.refinement_strategy == "uniform":
                ind_res = self.estimator.compute_uniform_indicator(current_mesh)
            elif self.plan.refinement_strategy == "recovery":
                ind_res = self.estimator.compute_zz_recovery_indicator(current_mesh, sol)
            elif self.plan.refinement_strategy == "goal_aware":
                ind_res = self.estimator.compute_goal_aware_indicator(
                    current_mesh, sol, cost_aware=self.ir.adaptivity.cost_aware
                )
            elif self.plan.refinement_strategy in ["dwr", "goal_oriented_dwr"]:
                ind_res = self.estimator.compute_dwr_indicator(
                    current_mesh,
                    sol,
                    loads=self.loads,
                    fixed_boundaries=self.fixed_boundaries,
                    cost_aware=self.ir.adaptivity.cost_aware,
                )
            else:
                raise ValueError(f"Unknown strategy: {self.plan.refinement_strategy}")

            indicator_time = self.telemetry.now() - t_ind0
            last_ind = ind_res

            # Step 6: Mark elements under budget
            marked = MeshAdaptor.mark_elements(
                indicator_result=ind_res,
                strategy=self.plan.refinement_strategy,
                marking_fraction=self.plan.marking_fraction,
                current_dofs=current_dofs,
                max_dofs_budget=self.plan.max_dofs_budget,
            )

            predicted_dofs_growth = self.cost_model.predict_additional_dofs(
                len(marked), total_elements=current_mesh.nelements
            )
            predicted_next_dofs = current_dofs + predicted_dofs_growth

            # Step 7: Controller evaluation
            decision: ControllerDecision = self.controller.evaluate(
                iteration=iteration,
                current_dofs=current_dofs,
                predicted_next_dofs=predicted_next_dofs,
                successive_change_pct=successive_change,
                marked_elements_count=len(marked),
            )

            iter_total_time = self.telemetry.now() - iter_start_time
            peak_mem = max(mem_start, self.telemetry.get_current_memory_mb())

            # Populate record with exact measured stage timings
            record = IterationRecord(
                iteration=iteration,
                nelements=current_mesh.nelements,
                nnodes=current_mesh.nnodes,
                dofs=current_dofs,
                qoi_meters=current_qoi,
                qoi_mm=sol.qoi_mm,
                successive_change_pct=successive_change,
                max_refinement_indicator=float(np.max(ind_res.indicators)) if len(ind_res.indicators) > 0 else 0.0,
                elements_marked=len(marked),
                assembly_time_sec=sol.assembly_time_sec,
                condensation_time_sec=sol.condensation_time_sec,
                factorization_time_sec=sol.factorization_time_sec,
                primal_solve_time_sec=sol.primal_solve_time_sec,
                adjoint_solve_time_sec=sol.adjoint_solve_time_sec,
                solver_time_sec=(sol.total_solver_time_sec - sol.assembly_time_sec),
                indicator_time_sec=indicator_time,
                refinement_time_sec=last_refinement_time,
                postprocess_time_sec=postprocess_time,
                total_iteration_time_sec=iter_total_time,
                peak_memory_mb=peak_mem,
                action_reason=decision.reason,
            )
            trace.iterations.append(record)

            if callback:
                callback(record, current_mesh, post)

            # Check termination
            if decision.should_stop:
                trace.converged = decision.converged
                trace.stop_reason = decision.reason
                break

            # Step 8: Apply mesh refinement with transactional budget safety
            t_ref0 = self.telemetry.now()
            old_dofs = current_dofs
            candidate_mesh = MeshAdaptor.refine_mesh(
                current_mesh, self.plan.refinement_strategy, marked
            )
            candidate_dofs = candidate_mesh.nnodes * 2
            last_refinement_time = self.telemetry.now() - t_ref0

            # Safe Refinement Transaction: commit candidate mesh only if within hard budget
            if candidate_dofs > self.plan.max_dofs_budget:
                trace.converged = False
                trace.stop_reason = (
                    f"Candidate refinement ({candidate_dofs} DOFs) exceeds budget "
                    f"({self.plan.max_dofs_budget} DOFs). Rollback committed to previous valid mesh."
                )
                break

            # Commit candidate mesh
            current_mesh = candidate_mesh

            # Update cost model
            observed_delta = candidate_dofs - old_dofs
            self.cost_model.update(
                iteration, len(marked), observed_delta, iter_total_time, total_elements=old_dofs // 2
            )

            previous_qoi = current_qoi
            iteration += 1

        trace.total_wall_time_sec = self.telemetry.now() - start_wall_time
        budget_exhausted = (not trace.converged) and ("budget" in trace.stop_reason.lower() or "exceeds" in trace.stop_reason.lower())
        self._attach_evidence_and_refusal(trace, current_mesh, last_sol, last_ind, budget_exhausted=budget_exhausted)
        return trace

    def _attach_evidence_and_refusal(
        self,
        trace: ExecutionTrace,
        mesh: GDECMesh,
        sol: Optional[FEMSolution],
        ind_res: Optional[IndicatorResult],
        *,
        budget_exhausted: bool = False,
    ) -> None:
        """Build canonical EngineeringEvidenceRecord and evaluate deterministic RefusalEngine."""
        import hashlib
        import scipy
        import skfem
        from gdec import __version__ as gdec_version
        from gdec.dse.evidence_graph import (
            CompactProblemFeatureVector,
            EstimatorClassification,
            OutcomeMetrics,
            ParentArtifactRef,
            build_evidence_record_with_hash,
            canonical_json_dumps,
        )
        from gdec.dse.refusal import RefusalContext, RefusalEngine

        eir_payload = {
            "name": self.ir.name,
            "geometry": {"width": self.ir.geometry.width, "height": self.ir.geometry.height, "thickness": self.ir.geometry.thickness},
            "material": {"E": self.ir.material.E, "nu": self.ir.material.nu, "assumption": self.ir.material.assumption},
            "loads": [(b, float(tx), float(ty)) for b, tx, ty in self.loads],
            "fixed_bcs": [(b, list(c)) for b, c in self.fixed_bcs],
            "objective": {"boundary": self.ir.objective.boundary, "component": self.ir.objective.component},
        }
        eir_hash = hashlib.sha256(canonical_json_dumps(eir_payload).encode("utf-8")).hexdigest()
        mesh_hasher = hashlib.sha256()
        mesh_hasher.update(
            canonical_json_dumps(
                {
                    "nnodes": int(mesh.nnodes),
                    "nelements": int(mesh.nelements),
                    "width": float(mesh.width),
                    "height": float(mesh.height),
                }
            ).encode("utf-8")
        )
        mesh_hasher.update(np.ascontiguousarray(mesh.mesh.p, dtype=np.float64).tobytes())
        mesh_hasher.update(np.ascontiguousarray(mesh.mesh.t, dtype=np.int64).tobytes())
        mesh_hash = mesh_hasher.hexdigest()

        strat = self.plan.refinement_strategy.lower()
        if strat in ("dwr", "goal_oriented_dwr"):
            est_class = EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE
            est_id = "DWREstimator"
            est_interp = "Asymptotic goal-oriented DWR error indicator; NOT a certified mathematical upper bound."
        else:
            est_class = EstimatorClassification.HEURISTIC
            est_id = ind_res.name if ind_res is not None else f"Heuristic_{strat}"
            est_interp = "Heuristic refinement indicator; NOT a certified mathematical upper bound."

        est_val: Optional[float] = None
        if ind_res is not None and len(ind_res.indicators) > 0:
            est_val = float(np.max(ind_res.indicators))

        qoi_val = float(sol.qoi * 1000.0) if sol is not None else None
        dof_count = int(sol.basis.N) if sol is not None else 0
        fixed_bnd_names = [b for b, _ in self.fixed_bcs]
        mesh_valid = bool(mesh.nelements > 0 and np.all(mesh.element_areas > 0.0))

        parent_artifacts = [
            ParentArtifactRef(artifact_id=self.ir.name, artifact_type="canonical_eir", sha256_hash=eir_hash),
            ParentArtifactRef(artifact_id=f"mesh_{mesh.nnodes}n_{mesh.nelements}e", artifact_type="fem_mesh", sha256_hash=mesh_hash),
        ]

        ctx = RefusalContext(
            budget_exhausted=budget_exhausted,
            target_tolerance_met=bool(trace.converged),
            estimator_identity=est_id,
            estimator_classification=est_class.value,
            problem_class="linear_elasticity_2d",
            reference_required=False,
            reference_adequate=None,
            qoi_boundary=self.ir.objective.boundary,
            fixed_boundaries=fixed_bnd_names,
            dof_count=dof_count,
            min_required_dofs=6,
            solver_converged=bool(sol.converged) if sol is not None else False,
            qoi_value=qoi_val,
            residual_norm=float(sol.primal_relative_residual) if sol is not None else 0.0,
            error_estimate=est_val,
            mesh_valid=mesh_valid,
            mesh_element_count=int(mesh.nelements),
            model_applicability_status="established",
            parent_artifacts=[p.model_dump() for p in parent_artifacts],
            canonical_eir_hash=eir_hash,
            mesh_hash=mesh_hash,
            mandatory_evidence_present=sol is not None,
            evidence_stale=False,
            evidence_invalidated=False,
        )
        refusal_res = RefusalEngine().evaluate(ctx)

        features = CompactProblemFeatureVector(
            domain_width=float(self.ir.geometry.width),
            domain_height=float(self.ir.geometry.height),
            aspect_ratio=float(self.ir.geometry.width / self.ir.geometry.height),
            num_loads=len(self.loads),
            num_fixed_boundaries=len(self.fixed_bcs),
            youngs_modulus=float(self.ir.material.E),
            poissons_ratio=float(self.ir.material.nu),
            constitutive_assumption=self.ir.material.assumption,
            refinement_strategy=self.plan.refinement_strategy,
            initial_dofs=int(self.plan.initial_mesh_shape[0] * self.plan.initial_mesh_shape[1] * 2),
            max_dofs_budget=int(self.plan.max_dofs_budget),
        )
        outcomes = OutcomeMetrics(
            final_dofs=dof_count,
            refinement_steps=len(trace.iterations),
            wall_time_sec=float(trace.total_wall_time_sec),
            estimator_value=est_val,
        )

        record_payload = {
            "record_id": f"EER-{self.ir.name}-{eir_hash[:12]}",
            "canonical_eir_hash": eir_hash,
            "mesh_identity": f"GDECMesh_{mesh.nnodes}n_{mesh.nelements}e",
            "mesh_hash": mesh_hash,
            "material_identity": f"Isotropic_{self.ir.material.assumption}_E{self.ir.material.E:.3e}_nu{self.ir.material.nu}",
            "boundary_conditions_identity": f"fixed:{','.join(fixed_bnd_names)};loads:{len(self.loads)}",
            "solver_identity": "LinearElasticitySolver_P1",
            "solver_version": gdec_version,
            "solver_config": {
                "problem_class": "linear_elasticity_2d",
                "qoi_boundary": self.ir.objective.boundary,
                "fixed_boundaries": fixed_bnd_names,
                "solver_converged": bool(sol.converged) if sol is not None else False,
                "residual_norm": float(sol.primal_relative_residual) if sol is not None else 0.0,
                "mandatory_evidence_present": sol is not None,
                "min_required_dofs": 6,
                "reference_required": False,
            },
            "backend": sol.solver_backend if sol is not None else "none",
            "numerical_precision": "float64",
            "dependency_versions": {
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "scikit-fem": skfem.__version__,
            },
            "dof_count": dof_count,
            "mesh_metadata": {
                "nnodes": int(mesh.nnodes),
                "nelements": int(mesh.nelements),
                "mesh_valid": mesh_valid,
            },
            "qoi_id": f"{self.ir.objective.boundary}_{self.ir.objective.component}",
            "qoi_name": f"Average {self.ir.objective.component}-displacement on {self.ir.objective.boundary}",
            "qoi_units": "mm",
            "qoi_value": qoi_val,
            "estimator_identity": est_id,
            "estimator_classification": est_class.value,
            "error_estimate": est_val,
            "error_estimate_interpretation": est_interp,
            "effectivity_evidence": "NONE",
            "model_applicability_status": "established",
            "verification_validation_status": "UNASSESSED",
            "problem_features": features.model_dump(),
            "outcome_metrics": outcomes.model_dump(),
            "refusal_evaluations": [ev.model_dump() for ev in refusal_res.evaluations],
            "refused": refusal_res.refused,
            "refusal_reasons": refusal_res.reasons,
            "resource_consumption": {
                "wall_time_sec": float(trace.total_wall_time_sec),
                "budget_max_dofs": int(self.plan.max_dofs_budget),
                "budget_exhausted": budget_exhausted,
                "target_tolerance_met": bool(trace.converged),
            },
            "parent_artifacts": [p.model_dump() for p in parent_artifacts],
            "evidence_stale": False,
            "evidence_invalidated": False,
        }
        trace.evidence_record = build_evidence_record_with_hash(record_payload)
        trace.refusal_result = refusal_res
