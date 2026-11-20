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
            return trace

        iteration = 1
        previous_qoi: Optional[float] = None
        current_dofs = 0
        last_refinement_time = 0.0

        while True:
            iter_start_time = self.telemetry.now()
            mem_start = self.telemetry.get_current_memory_mb()

            # Step 2: Solve FEM system (exact stage timings measured inside solver)
            need_adjoint = self.plan.refinement_strategy == "goal_aware"

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
            else:
                raise ValueError(f"Unknown strategy: {self.plan.refinement_strategy}")

            indicator_time = self.telemetry.now() - t_ind0

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
        return trace
