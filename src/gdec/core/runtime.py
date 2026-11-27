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
        budget_exhausted_flag = False

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
                    fixed_boundaries=self.fixed_bcs,
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
                budget_exhausted_flag = decision.budget_exhausted
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
                budget_exhausted_flag = True
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
        self._attach_evidence_and_refusal(trace, current_mesh, last_sol, last_ind, budget_exhausted=budget_exhausted_flag)
        return trace

    @staticmethod
    def _get_source_revision() -> str:
        import subprocess
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and len(res.stdout.strip()) == 40:
                return res.stdout.strip()
        except Exception:
            pass
        return "unavailable"

    @staticmethod
    def _assess_model_applicability(
        ir: ProblemIR, mesh: GDECMesh, sol: Optional[FEMSolution], mesh_valid: bool
    ) -> Tuple[str, List[str]]:
        reasons: List[str] = []
        if ir.physics != "linear_elasticity":
            reasons.append(f"Unsupported physics '{ir.physics}'.")
            return "unestablished", reasons
        if ir.geometry.kind != "rectangle" or ir.material.kind != "isotropic":
            reasons.append("Geometry/material outside supported 2D isotropic rectangle scope.")
            return "unestablished", reasons
        if not mesh_valid:
            reasons.append("Mesh failed positivity/validity check.")
            return "invalidated", reasons
        if sol is not None:
            grad_u = sol.basis.interpolate(sol.u).grad[:, :, :, 0]
            max_grad = float(np.max(np.abs(grad_u)))
            if not np.isfinite(max_grad) or max_grad >= 0.05:
                reasons.append(f"Small-strain linear regime exceeded or non-finite (max|grad u|={max_grad}).")
                return "invalidated", reasons
        reasons.append("2D small-strain isotropic linear elasticity geometric/kinematic preconditions satisfied; physical constitutive validity requires external validation.")
        return "established", reasons

    def _attach_evidence_and_refusal(
        self,
        trace: ExecutionTrace,
        mesh: GDECMesh,
        sol: Optional[FEMSolution],
        ind_res: Optional[IndicatorResult],
        *,
        budget_exhausted: bool = False,
    ) -> None:
        """Build canonical EngineeringEvidenceRecord (v1.1.0) and evaluate deterministic RefusalEngine."""
        import hashlib
        import math
        import scipy
        import skfem
        from gdec import __version__ as gdec_version
        from gdec.dse.evidence import ValidationStatus
        from gdec.dse.evidence_graph import (
            CompactProblemFeatureVector,
            EstimatorClassification,
            OutcomeMetrics,
            ParentArtifactRef,
            QoIEpistemicRole,
            QualificationStatus,
            build_evidence_record_with_hash,
            canonical_json_dumps,
        )
        from gdec.dse.refusal import RefusalContext, RefusalEngine, structural_min_dofs_for_estimator

        # Complete canonical ProblemIR payload (sorted BCs & loads for order-independent identity)
        ir_dict = self.ir.model_dump(mode="json")
        ir_dict["boundary_conditions"] = sorted(ir_dict["boundary_conditions"], key=lambda x: x["boundary"])
        ir_dict["loads"] = sorted(ir_dict["loads"], key=lambda x: x["boundary"])
        problem_ir_hash = hashlib.sha256(canonical_json_dumps(ir_dict).encode("utf-8")).hexdigest()

        plan_payload = {
            "problem_name": self.plan.problem_name,
            "initial_mesh_shape": list(self.plan.initial_mesh_shape),
            "refinement_strategy": self.plan.refinement_strategy,
            "marking_fraction": float(self.plan.marking_fraction),
            "accuracy_target_pct": float(self.plan.accuracy_target_pct),
            "max_dofs_budget": int(self.plan.max_dofs_budget),
            "max_iterations": int(self.plan.max_iterations),
            "backend_device": self.plan.backend_device,
            "cost_aware": bool(self.ir.adaptivity.cost_aware),
        }
        execution_plan_hash = hashlib.sha256(canonical_json_dumps(plan_payload).encode("utf-8")).hexdigest()

        p_arr = np.ascontiguousarray(mesh.mesh.p, dtype=np.float64)
        t_arr = np.ascontiguousarray(mesh.mesh.t, dtype=np.int64)
        mesh_hasher = hashlib.sha256()
        mesh_hasher.update(
            canonical_json_dumps(
                {
                    "nnodes": int(mesh.nnodes),
                    "nelements": int(mesh.nelements),
                    "width": float(mesh.width),
                    "height": float(mesh.height),
                    "shape_p": list(p_arr.shape),
                    "dtype_p": str(p_arr.dtype),
                    "shape_t": list(t_arr.shape),
                    "dtype_t": str(t_arr.dtype),
                    "coordinate_units": "m",
                }
            ).encode("utf-8")
        )
        mesh_hasher.update(p_arr.tobytes())
        mesh_hasher.update(t_arr.tobytes())
        mesh_hash = mesh_hasher.hexdigest()

        strat = self.plan.refinement_strategy.lower()
        if strat in ("dwr", "goal_oriented_dwr"):
            est_class = EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE
            est_id = "DWREstimator"
            est_interp = "Asymptotic goal-oriented DWR error indicator; NOT a certified mathematical upper bound."
            qoi_role = QoIEpistemicRole.ASYMPTOTIC_INDICATOR
            est_units = "mm"
            est_qty = "signed_qoi_error_estimate"
        elif strat == "uniform":
            est_class = EstimatorClassification.HEURISTIC
            est_id = ind_res.name if ind_res is not None else "Uniform"
            est_interp = "Uniform refinement marker; NOT a quantitative error bound."
            qoi_role = QoIEpistemicRole.NUMERICAL_OBSERVATION
            est_units = "dimensionless"
            est_qty = "uniform_marker"
        else:
            est_class = EstimatorClassification.HEURISTIC
            est_id = ind_res.name if ind_res is not None else f"Heuristic_{strat}"
            est_interp = "Heuristic refinement indicator; NOT a certified mathematical upper bound."
            qoi_role = QoIEpistemicRole.HEURISTIC_ESTIMATE
            est_units = "dimensionless"
            est_qty = "max_element_indicator"

        raw_est: Optional[float] = None
        if ind_res is not None:
            if est_class == EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE and "signed_qoi_error_estimate_mm" in ind_res.details:
                raw_est = float(ind_res.details["signed_qoi_error_estimate_mm"])
            elif len(ind_res.indicators) > 0:
                raw_est = float(np.max(ind_res.indicators))

        raw_qoi = float(sol.qoi * 1000.0) if sol is not None else None
        raw_res = float(sol.primal_relative_residual) if sol is not None else 0.0
        raw_adj_res = float(sol.adjoint_relative_residual) if sol is not None else 0.0

        nonfinite_detected = (
            (raw_qoi is not None and not math.isfinite(raw_qoi))
            or (raw_est is not None and not math.isfinite(raw_est))
            or (not math.isfinite(raw_res))
            or (not math.isfinite(raw_adj_res))
        )
        qoi_val = raw_qoi if (raw_qoi is not None and math.isfinite(raw_qoi)) else None
        est_val = raw_est if (raw_est is not None and math.isfinite(raw_est)) else None
        res_val = raw_res if math.isfinite(raw_res) else 0.0
        adj_res_val = raw_adj_res if math.isfinite(raw_adj_res) else 0.0

        if qoi_val is None:
            qoi_role = QoIEpistemicRole.UNAVAILABLE

        dof_count = int(sol.basis.N) if sol is not None else int(mesh.nnodes * 2)
        fixed_dofs_count = int(len(sol.dofs_fixed)) if sol is not None else 0
        free_dofs = max(0, dof_count - fixed_dofs_count)
        interior_facets = int(np.sum(mesh.mesh.f2t[1] >= 0))
        bnd_nodes = set(mesh.mesh.boundary_nodes().tolist()) if hasattr(mesh.mesh, "boundary_nodes") else set()
        interior_nodes = max(0, int(mesh.nnodes) - len(bnd_nodes))

        fixed_bnd_names = sorted(b for b, _ in self.fixed_bcs)
        mesh_valid = bool(mesh.nelements > 0 and np.all(mesh.element_areas > 0.0))
        app_status, app_reasons = self._assess_model_applicability(self.ir, mesh, sol, mesh_valid)

        parent_artifacts = [
            ParentArtifactRef(artifact_id=f"problem_ir:{self.ir.name}", artifact_type="canonical_problem_ir", sha256_hash=problem_ir_hash),
            ParentArtifactRef(artifact_id=f"execution_plan:{self.plan.problem_name}", artifact_type="execution_plan", sha256_hash=execution_plan_hash),
            ParentArtifactRef(artifact_id=f"mesh_{mesh.nnodes}n_{mesh.nelements}e", artifact_type="fem_mesh", sha256_hash=mesh_hash),
        ]

        canon_reqs = structural_min_dofs_for_estimator(est_id, est_class.value)
        ctx = RefusalContext(
            budget_exhausted=budget_exhausted,
            target_tolerance_met=bool(trace.converged),
            estimator_identity=est_id,
            estimator_classification=est_class.value,
            problem_class="linear_elasticity_2d",
            reference_required=False,
            reference_adequate=None,
            effectivity_evidence_present=False,
            bound_certificate_verified=False,
            bound_checker_identity="",
            qoi_boundary=self.ir.objective.boundary,
            fixed_boundaries=fixed_bnd_names,
            dof_count=dof_count,
            free_dof_count=free_dofs,
            interior_node_count=interior_nodes,
            interior_facet_count=interior_facets,
            min_required_dofs=canon_reqs["min_total_dofs"],
            solver_converged=bool(sol.primal_converged) if sol is not None else False,
            adjoint_converged=bool(sol.adjoint_converged) if sol is not None else False,
            qoi_value=qoi_val,
            residual_norm=res_val,
            adjoint_residual_norm=adj_res_val,
            error_estimate=est_val,
            nonfinite_detected=nonfinite_detected,
            mesh_valid=mesh_valid,
            mesh_element_count=int(mesh.nelements),
            model_applicability_status=app_status,
            parent_artifacts=[p.model_dump() for p in parent_artifacts],
            problem_ir_hash=problem_ir_hash,
            canonical_eir_hash=problem_ir_hash,
            execution_plan_hash=execution_plan_hash,
            mesh_hash=mesh_hash,
            mandatory_evidence_present=sol is not None,
            evidence_stale=False,
            evidence_invalidated=False,
        )
        refusal_res = RefusalEngine().evaluate(ctx)

        if sol is None:
            conv_status = "aborted_pre_solve"
        elif not sol.converged:
            conv_status = "solver_failed"
        elif trace.converged:
            conv_status = "converged"
        else:
            conv_status = "not_converged"

        if refusal_res.refused:
            qual_status = QualificationStatus.REFUSED
        elif app_status != "established":
            qual_status = QualificationStatus.NOT_QUALIFIED_APPLICABILITY
        elif conv_status != "converged":
            qual_status = QualificationStatus.NOT_QUALIFIED_NOT_CONVERGED
        else:
            qual_status = QualificationStatus.NOT_QUALIFIED_UNASSESSED_VV

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
            "record_id": f"EER-{self.ir.name}-{problem_ir_hash[:10]}-{execution_plan_hash[:10]}",
            "problem_ir_hash": problem_ir_hash,
            "canonical_eir_hash": problem_ir_hash,
            "execution_plan_hash": execution_plan_hash,
            "source_revision": self._get_source_revision(),
            "mesh_identity": f"GDECMesh_{mesh.nnodes}n_{mesh.nelements}e",
            "mesh_hash": mesh_hash,
            "material_identity": f"Isotropic_{self.ir.material.assumption}_E{self.ir.material.E:.3e}_nu{self.ir.material.nu}",
            "boundary_conditions_identity": f"fixed:{','.join(fixed_bnd_names)};loads:{len(self.loads)}",
            "solver_identity": "LinearElasticitySolver_P1",
            "solver_version": gdec_version,
            "linear_solver_type": sol.solver_backend if sol is not None else "none",
            "compute_device": self.ir.backend.device,
            "solver_config": {
                "problem_class": "linear_elasticity_2d",
                "qoi_boundary": self.ir.objective.boundary,
                "fixed_boundaries": fixed_bnd_names,
                "solver_converged": bool(sol.primal_converged) if sol is not None else False,
                "adjoint_converged": bool(sol.adjoint_converged) if sol is not None else False,
                "residual_norm": res_val,
                "adjoint_residual_norm": adj_res_val,
                "mandatory_evidence_present": sol is not None,
                "min_required_dofs": canon_reqs["min_total_dofs"],
                "reference_required": False,
                "marking_fraction": float(self.plan.marking_fraction),
                "accuracy_target_pct": float(self.plan.accuracy_target_pct),
                "max_iterations": int(self.plan.max_iterations),
                "cost_aware": bool(self.ir.adaptivity.cost_aware),
                "initial_mesh_shape": list(self.plan.initial_mesh_shape),
            },
            "backend": self.ir.backend.device,
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
                "free_dofs": free_dofs,
                "interior_nodes": interior_nodes,
                "interior_facets": interior_facets,
                "shape_p": list(p_arr.shape),
                "dtype_p": str(p_arr.dtype),
                "shape_t": list(t_arr.shape),
                "dtype_t": str(t_arr.dtype),
                "coordinate_units": "m",
                "mesh_valid": mesh_valid,
            },
            "qoi_id": f"{self.ir.objective.boundary}_{self.ir.objective.component}",
            "qoi_name": f"Average {self.ir.objective.component}-displacement on {self.ir.objective.boundary}",
            "qoi_units": "mm",
            "qoi_value": qoi_val,
            "qoi_epistemic_role": qoi_role.value,
            "estimator_identity": est_id,
            "estimator_classification": est_class.value,
            "error_estimate": est_val,
            "error_estimate_units": est_units,
            "error_estimate_quantity": est_qty,
            "error_estimate_interpretation": est_interp,
            "effectivity_evidence": "NONE",
            "model_applicability_status": app_status,
            "model_applicability_reasons": app_reasons,
            "numerical_convergence_status": conv_status,
            "verification_status": ValidationStatus.UNASSESSED.value,
            "validation_status": ValidationStatus.UNASSESSED.value,
            "verification_validation_status": ValidationStatus.UNASSESSED.value,
            "qualification_status": qual_status.value,
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
