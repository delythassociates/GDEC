"""
Automated benchmark runner for GDEC v0.2.
Executes Uniform, Recovery-based, and Goal-Aware strategies under identical conditions,
evaluates equal-accuracy comparisons across standardized error thresholds (2%, 1%, 0.5%, 0.25%),
and rigorously tests the central research hypothesis.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from gdec.language.ir import ProblemIR
from gdec.core.planner import ExecutionPlan, ExecutionPlanner
from gdec.core.runtime import GDECRuntime
from gdec.core.telemetry import ExecutionTrace, IterationRecord
from gdec.benchmark.reference import ReferenceSolution, ReferenceSolver
from gdec.benchmark.evaluator import EqualAccuracyEvaluator, EqualAccuracyComparison


@dataclass
class BenchmarkIterationData:
    iteration: int
    strategy: str
    nelements: int
    nnodes: int
    dofs: int
    qoi_meters: float
    qoi_mm: float
    reference_error_pct: float
    successive_change_pct: Optional[float]
    max_indicator: float
    elements_marked: int
    assembly_time_sec: float
    solver_time_sec: float
    total_time_sec: float
    cumulative_time_sec: float
    peak_memory_mb: float
    action_reason: str


@dataclass
class StrategyBenchmarkResult:
    strategy: str
    trace: ExecutionTrace
    iterations: List[BenchmarkIterationData]
    final_reference_error_pct: float
    target_achieved: bool
    total_execution_time_sec: float
    final_dofs: int
    refused: Optional[bool] = None
    refusal_reasons: List[str] = field(default_factory=list)
    qualification_status: Optional[str] = None
    estimator_classification: Optional[str] = None
    canonical_result_hash: Optional[str] = None


@dataclass
class BenchmarkSuiteResult:
    problem_name: str
    timestamp: str
    reference: ReferenceSolution
    strategies: Dict[str, StrategyBenchmarkResult]
    hypothesis_evaluation: Dict[str, any] = field(default_factory=dict)
    equal_accuracy_comparisons: List[EqualAccuracyComparison] = field(default_factory=list)


class BenchmarkRunner:
    def __init__(self, ir: ProblemIR, ref_target_dofs: int = 35000):
        self.ir = ir
        self.ref_target_dofs = ref_target_dofs
        self.planner = ExecutionPlanner()

    def run_all(
        self, progress_callback: Optional[callable] = None
    ) -> BenchmarkSuiteResult:
        """Run high-res reference solve followed by Uniform, Recovery, and Goal-Aware simulations."""
        if progress_callback:
            progress_callback("Computing high-resolution reference solution and multi-mesh verification...", 0.1)

        ref = ReferenceSolver.compute_reference(self.ir, target_dofs=self.ref_target_dofs, verify_convergence=True)

        strategies = ["uniform", "recovery", "goal_aware"]
        results: Dict[str, StrategyBenchmarkResult] = {}

        total_strats = len(strategies)
        for idx, strat in enumerate(strategies):
            if progress_callback:
                progress_callback(
                    f"Executing strategy {strat.upper()} ({idx+1}/{total_strats})...",
                    0.2 + 0.65 * (idx / total_strats),
                )

            # Create plan with strategy override
            plan = self.planner.create_plan(self.ir, override_strategy=strat)
            runtime = GDECRuntime(plan, self.ir)
            trace = runtime.execute()

            # Process iterations and annotate with reference error
            annotated_iters: List[BenchmarkIterationData] = []
            cum_time = 0.0

            for it in trace.iterations:
                # Refinement is performed between QoI observations and is measured
                # separately from the next iteration's solve/postprocess interval.
                cum_time += it.total_iteration_time_sec + it.refinement_time_sec
                ref_err = (
                    abs(it.qoi_meters - ref.qoi_meters) / max(abs(ref.qoi_meters), 1e-12)
                ) * 100.0

                annotated_iters.append(
                    BenchmarkIterationData(
                        iteration=it.iteration,
                        strategy=strat,
                        nelements=it.nelements,
                        nnodes=it.nnodes,
                        dofs=it.dofs,
                        qoi_meters=it.qoi_meters,
                        qoi_mm=it.qoi_mm,
                        reference_error_pct=float(ref_err),
                        successive_change_pct=it.successive_change_pct,
                        max_indicator=it.max_refinement_indicator,
                        elements_marked=it.elements_marked,
                        assembly_time_sec=it.assembly_time_sec,
                        solver_time_sec=it.solver_time_sec,
                        total_time_sec=it.total_iteration_time_sec,
                        cumulative_time_sec=cum_time,
                        peak_memory_mb=it.peak_memory_mb,
                        action_reason=it.action_reason,
                    )
                )

            final_err = annotated_iters[-1].reference_error_pct if annotated_iters else 100.0
            target_achieved = trace.converged

            rec = getattr(trace, "evidence_record", None)
            results[strat] = StrategyBenchmarkResult(
                strategy=strat,
                trace=trace,
                iterations=annotated_iters,
                final_reference_error_pct=final_err,
                target_achieved=target_achieved,
                total_execution_time_sec=trace.total_wall_time_sec,
                final_dofs=trace.final_dofs,
                refused=rec.refused if rec is not None else None,
                refusal_reasons=list(rec.refusal_reasons) if rec is not None else [],
                qualification_status=rec.qualification_status.value if rec is not None else None,
                estimator_classification=rec.estimator_classification.value if rec is not None else None,
                canonical_result_hash=rec.canonical_result_hash if rec is not None else None,
            )

        # Build intermediate suite result for equal accuracy evaluation
        import datetime
        temp_suite = BenchmarkSuiteResult(
            problem_name=self.ir.name,
            timestamp=datetime.datetime.now().isoformat(),
            reference=ref,
            strategies=results,
        )

        # Equal-accuracy evaluations at 2%, 1%, 0.5%, 0.25%
        equal_acc = EqualAccuracyEvaluator.evaluate_suite(temp_suite)

        # Evaluate hypothesis on equal-accuracy criteria
        hyp = self._evaluate_hypothesis(results, ref, equal_acc)

        if progress_callback:
            progress_callback("Benchmark complete!", 1.0)

        temp_suite.hypothesis_evaluation = hyp
        temp_suite.equal_accuracy_comparisons = equal_acc
        return temp_suite

    def _evaluate_hypothesis(
        self,
        results: Dict[str, StrategyBenchmarkResult],
        ref: ReferenceSolution,
        equal_acc: List[EqualAccuracyComparison],
    ) -> Dict[str, any]:
        """
        Evaluate research hypothesis on equal-accuracy criteria:
        Does Goal-Aware reach target reference error with lower computational cost (DOFs & time)
        than Uniform and Conventional Recovery baselines?
        """
        eval_data = {}
        for name, res in results.items():
            eval_data[name] = {
                "converged": res.target_achieved,
                "final_dofs": res.final_dofs,
                "total_time_sec": res.total_execution_time_sec,
                "final_ref_error_pct": res.final_reference_error_pct,
            }

        reasons = []
        dof_advantages = []
        time_advantages = []
        dof_advantages_recovery = []
        time_advantages_recovery = []

        for comp in equal_acc:
            th = comp.threshold_pct
            goal = comp.results.get("goal_aware")
            unif = comp.results.get("uniform")
            rec = comp.results.get("recovery")

            if goal and unif and goal.achieved and unif.achieved:
                d_ratio = comp.dof_ratio_unif_over_goal
                t_ratio = comp.time_ratio_unif_over_goal
                if d_ratio is not None:
                    dof_advantages.append(d_ratio)
                    reasons.append(
                        f"At error <= {th}%: Goal-Aware used {goal.dofs_at_target:,} DOFs vs Uniform {unif.dofs_at_target:,} DOFs ({d_ratio:.2f}x DOF advantage)."
                    )
                if t_ratio is not None:
                    time_advantages.append(t_ratio)

            if goal and rec and goal.achieved and rec.achieved:
                d_ratio_rec = comp.dof_ratio_rec_over_goal
                t_ratio_rec = comp.time_ratio_rec_over_goal
                if d_ratio_rec is not None:
                    dof_advantages_recovery.append(d_ratio_rec)
                if t_ratio_rec is not None:
                    time_advantages_recovery.append(t_ratio_rec)

        # Evaluate DOF and wall-clock efficiency as separate hypotheses.
        # A DOF-only win must not be reported as an end-to-end computational-cost win.
        mean_dof_adv = float(np.mean(dof_advantages)) if dof_advantages else None
        mean_time_adv = float(np.mean(time_advantages)) if time_advantages else None
        mean_dof_adv_rec = float(np.mean(dof_advantages_recovery)) if dof_advantages_recovery else None
        mean_time_adv_rec = float(np.mean(time_advantages_recovery)) if time_advantages_recovery else None
        dof_supported = (
            mean_dof_adv is not None and mean_dof_adv > 1.05
            and mean_dof_adv_rec is not None and mean_dof_adv_rec > 1.05
        )
        time_supported = (
            mean_time_adv is not None and mean_time_adv > 1.05
            and mean_time_adv_rec is not None and mean_time_adv_rec > 1.05
        )
        supported = dof_supported and time_supported

        reasons.insert(
            0,
            "Combined efficiency hypothesis SUPPORTED: goal-aware refinement demonstrated both DOF and wall-clock advantages at matched reference-relative accuracy."
            if supported
            else "Combined efficiency hypothesis NOT SUPPORTED: both DOF and wall-clock advantages at matched reference-relative accuracy were not demonstrated."
        )

        eval_data["hypothesis_supported"] = supported
        eval_data["dof_efficiency_supported"] = dof_supported
        eval_data["wall_clock_efficiency_supported"] = time_supported
        eval_data["reasons"] = reasons
        eval_data["mean_dof_advantage_vs_uniform"] = mean_dof_adv
        eval_data["mean_time_advantage_vs_uniform"] = mean_time_adv
        eval_data["mean_dof_advantage_vs_recovery"] = mean_dof_adv_rec
        eval_data["mean_time_advantage_vs_recovery"] = mean_time_adv_rec

        return eval_data
