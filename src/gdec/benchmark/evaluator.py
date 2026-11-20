"""
Equal-Accuracy Benchmark Evaluation Module for GDEC (v0.2.3).
Compares Uniform, Recovery (ZZ), and Goal-Aware strategies at identical reference-relative
error thresholds (2.0%, 1.0%, 0.5%, 0.25%) without conflating stopping criteria or metrics.
Separates DOF efficiency from runtime efficiency and overall computational-cost superiority.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from gdec.benchmark.runner import BenchmarkSuiteResult, StrategyBenchmarkResult, BenchmarkIterationData


@dataclass
class ThresholdEvaluationResult:
    threshold_pct: float
    strategy: str
    achieved: bool
    iteration_reached: Optional[int]
    dofs_at_target: Optional[int]
    elements_at_target: Optional[int]
    time_to_target_sec: Optional[float]
    peak_memory_mb: Optional[float]
    qoi_at_target_mm: Optional[float]
    actual_ref_error_pct: Optional[float]
    runtime_convergence_pct: Optional[float]
    status_note: str


@dataclass
class EqualAccuracyComparison:
    threshold_pct: float
    results: Dict[str, ThresholdEvaluationResult]
    dof_ratio_unif_over_goal: Optional[float] = None
    time_ratio_unif_over_goal: Optional[float] = None
    dof_ratio_rec_over_goal: Optional[float] = None
    time_ratio_rec_over_goal: Optional[float] = None


@dataclass
class HypothesisEvaluationResult:
    dof_efficiency_vs_uniform: str
    dof_efficiency_vs_recovery: str
    runtime_efficiency_vs_uniform: str
    runtime_efficiency_vs_recovery: str
    combined_computational_cost_superiority: str
    accuracy_target_attainment: str
    overall_verdict: str
    dof_ratios_vs_uniform: Dict[str, float]
    dof_ratios_vs_recovery: Dict[str, float]
    runtime_ratios_vs_uniform: Dict[str, float]
    runtime_ratios_vs_recovery: Dict[str, float]
    detailed_reasons: List[str]

    def to_dict(self) -> Dict[str, any]:
        return {
            "dof_efficiency_vs_uniform": self.dof_efficiency_vs_uniform,
            "dof_efficiency_vs_recovery": self.dof_efficiency_vs_recovery,
            "runtime_efficiency_vs_uniform": self.runtime_efficiency_vs_uniform,
            "runtime_efficiency_vs_recovery": self.runtime_efficiency_vs_recovery,
            "combined_computational_cost_superiority": self.combined_computational_cost_superiority,
            "accuracy_target_attainment": self.accuracy_target_attainment,
            "overall_verdict": self.overall_verdict,
            "dof_ratios_vs_uniform": self.dof_ratios_vs_uniform,
            "dof_ratios_vs_recovery": self.dof_ratios_vs_recovery,
            "runtime_ratios_vs_uniform": self.runtime_ratios_vs_uniform,
            "runtime_ratios_vs_recovery": self.runtime_ratios_vs_recovery,
            "reasons": self.detailed_reasons,
            "hypothesis_supported": self.overall_verdict in ["SUPPORTED", "PARTIALLY_SUPPORTED"],
        }


class EqualAccuracyEvaluator:
    STANDARD_THRESHOLDS = [2.0, 1.0, 0.5, 0.25]

    @classmethod
    def evaluate_strategy_at_threshold(
        cls, strat_res: StrategyBenchmarkResult, threshold_pct: float
    ) -> ThresholdEvaluationResult:
        """Find the earliest iteration where reference error <= threshold_pct."""
        for it in strat_res.iterations:
            if it.reference_error_pct <= threshold_pct:
                return ThresholdEvaluationResult(
                    threshold_pct=threshold_pct,
                    strategy=strat_res.strategy,
                    achieved=True,
                    iteration_reached=it.iteration,
                    dofs_at_target=it.dofs,
                    elements_at_target=it.nelements,
                    time_to_target_sec=it.cumulative_time_sec,
                    peak_memory_mb=it.peak_memory_mb,
                    qoi_at_target_mm=it.qoi_mm,
                    actual_ref_error_pct=it.reference_error_pct,
                    runtime_convergence_pct=it.successive_change_pct,
                    status_note=f"Target reached at iteration {it.iteration} with {it.dofs:,} DOFs.",
                )

        best_it = min(strat_res.iterations, key=lambda x: x.reference_error_pct) if strat_res.iterations else None
        best_err = best_it.reference_error_pct if best_it else 100.0
        return ThresholdEvaluationResult(
            threshold_pct=threshold_pct,
            strategy=strat_res.strategy,
            achieved=False,
            iteration_reached=None,
            dofs_at_target=None,
            elements_at_target=None,
            time_to_target_sec=None,
            peak_memory_mb=None,
            qoi_at_target_mm=None,
            actual_ref_error_pct=best_err,
            runtime_convergence_pct=None,
            status_note=f"Threshold not achieved within budget (best error achieved: {best_err:.3f}%).",
        )

    @classmethod
    def evaluate_suite(
        cls,
        suite_res: BenchmarkSuiteResult,
        thresholds: Optional[List[float]] = None,
    ) -> List[EqualAccuracyComparison]:
        """Evaluate all strategies across all target accuracy thresholds."""
        if thresholds is None:
            thresholds = cls.STANDARD_THRESHOLDS

        comparisons: List[EqualAccuracyComparison] = []

        for thresh in thresholds:
            strat_evals: Dict[str, ThresholdEvaluationResult] = {}
            for strat_name, strat_res in suite_res.strategies.items():
                strat_evals[strat_name] = cls.evaluate_strategy_at_threshold(strat_res, thresh)

            goal = strat_evals.get("goal_aware")
            unif = strat_evals.get("uniform")
            rec = strat_evals.get("recovery")

            dof_ratio_unif_goal = None
            time_ratio_unif_goal = None
            dof_ratio_rec_goal = None
            time_ratio_rec_goal = None

            if goal and unif and goal.achieved and unif.achieved:
                if goal.dofs_at_target and unif.dofs_at_target and goal.dofs_at_target > 0:
                    dof_ratio_unif_goal = float(unif.dofs_at_target) / float(goal.dofs_at_target)
                if goal.time_to_target_sec and unif.time_to_target_sec and goal.time_to_target_sec > 0:
                    time_ratio_unif_goal = float(unif.time_to_target_sec) / float(goal.time_to_target_sec)

            if goal and rec and goal.achieved and rec.achieved:
                if goal.dofs_at_target and rec.dofs_at_target and goal.dofs_at_target > 0:
                    dof_ratio_rec_goal = float(rec.dofs_at_target) / float(goal.dofs_at_target)
                if goal.time_to_target_sec and rec.time_to_target_sec and goal.time_to_target_sec > 0:
                    time_ratio_rec_goal = float(rec.time_to_target_sec) / float(goal.time_to_target_sec)

            comparisons.append(
                EqualAccuracyComparison(
                    threshold_pct=thresh,
                    results=strat_evals,
                    dof_ratio_unif_over_goal=dof_ratio_unif_goal,
                    time_ratio_unif_over_goal=time_ratio_unif_goal,
                    dof_ratio_rec_over_goal=dof_ratio_rec_goal,
                    time_ratio_rec_over_goal=time_ratio_rec_goal,
                )
            )

        return comparisons

    @classmethod
    def evaluate_hypothesis_rigorous(
        cls, comparisons: List[EqualAccuracyComparison]
    ) -> HypothesisEvaluationResult:
        """
        Evaluate research hypothesis on equal-accuracy criteria with separated dimensions:
        1. DOF efficiency vs Uniform
        2. DOF efficiency vs Recovery
        3. Runtime efficiency vs Uniform
        4. Runtime efficiency vs Recovery
        5. Combined computational-cost superiority
        6. Accuracy-target attainment
        """
        dof_ratios_unif: Dict[str, float] = {}
        dof_ratios_rec: Dict[str, float] = {}
        time_ratios_unif: Dict[str, float] = {}
        time_ratios_rec: Dict[str, float] = {}
        reasons: List[str] = []

        attained_count = 0
        total_targets = len(comparisons)

        for comp in comparisons:
            th_str = f"{comp.threshold_pct}%"
            goal = comp.results.get("goal_aware")
            unif = comp.results.get("uniform")
            rec = comp.results.get("recovery")

            if goal and goal.achieved:
                attained_count += 1

            if goal and unif and goal.achieved and unif.achieved:
                if comp.dof_ratio_unif_over_goal is not None:
                    dof_ratios_unif[th_str] = comp.dof_ratio_unif_over_goal
                if comp.time_ratio_unif_over_goal is not None:
                    time_ratios_unif[th_str] = comp.time_ratio_unif_over_goal

            if goal and rec and goal.achieved and rec.achieved:
                if comp.dof_ratio_rec_over_goal is not None:
                    dof_ratios_rec[th_str] = comp.dof_ratio_rec_over_goal
                if comp.time_ratio_rec_over_goal is not None:
                    time_ratios_rec[th_str] = comp.time_ratio_rec_over_goal

        # 1. DOF efficiency vs Uniform
        if not dof_ratios_unif:
            dof_eff_unif = "INCONCLUSIVE"
        elif all(r > 1.05 for r in dof_ratios_unif.values()):
            dof_eff_unif = "SUPPORTED"
            avg_adv = np.mean(list(dof_ratios_unif.values()))
            reasons.append(f"DOF efficiency vs Uniform is SUPPORTED (average {avg_adv:.2f}x reduction across matched thresholds).")
        elif any(r > 1.05 for r in dof_ratios_unif.values()):
            dof_eff_unif = "PARTIALLY_SUPPORTED"
            reasons.append("DOF efficiency vs Uniform is PARTIALLY_SUPPORTED (advantage demonstrated at subset of thresholds).")
        else:
            dof_eff_unif = "NOT_SUPPORTED"
            reasons.append("DOF efficiency vs Uniform is NOT_SUPPORTED.")

        # 2. DOF efficiency vs Recovery
        if not dof_ratios_rec:
            dof_eff_rec = "INCONCLUSIVE"
        elif all(r > 1.05 for r in dof_ratios_rec.values()):
            dof_eff_rec = "SUPPORTED"
            reasons.append("DOF efficiency vs Recovery is SUPPORTED across matched thresholds.")
        elif any(r > 1.05 for r in dof_ratios_rec.values()):
            dof_eff_rec = "PARTIALLY_SUPPORTED"
            reasons.append("DOF efficiency vs Recovery is PARTIALLY_SUPPORTED.")
        else:
            dof_eff_rec = "NOT_SUPPORTED"
            reasons.append("DOF efficiency vs Recovery is NOT_SUPPORTED.")

        # 3. Runtime efficiency vs Uniform
        if not time_ratios_unif:
            time_eff_unif = "INCONCLUSIVE"
        elif all(r > 1.05 for r in time_ratios_unif.values()):
            time_eff_unif = "SUPPORTED"
            reasons.append("Runtime efficiency vs Uniform is SUPPORTED across matched thresholds.")
        elif any(r > 1.05 for r in time_ratios_unif.values()):
            time_eff_unif = "PARTIALLY_SUPPORTED"
            reasons.append("Runtime efficiency vs Uniform is PARTIALLY_SUPPORTED (faster only on fine thresholds; small-mesh overhead limits speedup).")
        else:
            time_eff_unif = "NOT_SUPPORTED"
            reasons.append("Runtime efficiency vs Uniform is NOT_SUPPORTED (net wall-clock time not consistently faster).")

        # 4. Runtime efficiency vs Recovery
        if not time_ratios_rec:
            time_eff_rec = "INCONCLUSIVE"
        elif all(r > 1.05 for r in time_ratios_rec.values()):
            time_eff_rec = "SUPPORTED"
        elif any(r > 1.05 for r in time_ratios_rec.values()):
            time_eff_rec = "PARTIALLY_SUPPORTED"
        else:
            time_eff_rec = "NOT_SUPPORTED"

        # 5. Combined computational-cost superiority
        if dof_eff_unif == "SUPPORTED" and time_eff_unif == "SUPPORTED":
            combined_cost = "SUPPORTED"
        elif dof_eff_unif == "SUPPORTED":
            combined_cost = "PARTIALLY_SUPPORTED"
            reasons.append("Combined computational-cost superiority is PARTIALLY_SUPPORTED: spatial DOF efficiency is demonstrated against Uniform, but wall-clock time superiority is not universally established.")
        else:
            combined_cost = "NOT_SUPPORTED"

        # 6. Accuracy-target attainment
        if attained_count == total_targets:
            attainment = "SUPPORTED"
            reasons.append(f"Accuracy-target attainment is SUPPORTED ({attained_count}/{total_targets} thresholds achieved within budget).")
        elif attained_count > 0:
            attainment = "PARTIALLY_SUPPORTED"
            reasons.append(f"Accuracy-target attainment is PARTIALLY_SUPPORTED ({attained_count}/{total_targets} thresholds achieved within budget).")
        else:
            attainment = "NOT_SUPPORTED"

        # Overall verdict
        if combined_cost == "SUPPORTED":
            overall_verdict = "SUPPORTED"
        elif dof_eff_unif == "SUPPORTED":
            overall_verdict = "PARTIALLY_SUPPORTED"
        else:
            overall_verdict = "NOT_SUPPORTED"

        return HypothesisEvaluationResult(
            dof_efficiency_vs_uniform=dof_eff_unif,
            dof_efficiency_vs_recovery=dof_eff_rec,
            runtime_efficiency_vs_uniform=time_eff_unif,
            runtime_efficiency_vs_recovery=time_eff_rec,
            combined_computational_cost_superiority=combined_cost,
            accuracy_target_attainment=attainment,
            overall_verdict=overall_verdict,
            dof_ratios_vs_uniform=dof_ratios_unif,
            dof_ratios_vs_recovery=dof_ratios_rec,
            runtime_ratios_vs_uniform=time_ratios_unif,
            runtime_ratios_vs_recovery=time_ratios_rec,
            detailed_reasons=reasons,
        )

    @classmethod
    def comparisons_to_dataframe(
        cls, comparisons: List[EqualAccuracyComparison]
    ) -> pd.DataFrame:
        """Create a clean tabular presentation of equal-accuracy comparisons."""
        rows = []
        for comp in comparisons:
            for strat_name, res in comp.results.items():
                rows.append({
                    "Target Error": f"<= {comp.threshold_pct}%",
                    "Strategy": strat_name.replace("_", " ").title(),
                    "Target Achieved": "YES" if res.achieved else "NO",
                    "Iteration": res.iteration_reached if res.achieved else "N/A",
                    "DOFs Required": f"{res.dofs_at_target:,}" if res.achieved and res.dofs_at_target is not None else "N/A",
                    "Time to Target (s)": f"{res.time_to_target_sec:.3f}" if res.achieved and res.time_to_target_sec is not None else "N/A",
                    "Actual Ref Error (%)": f"{res.actual_ref_error_pct:.3f}%" if res.actual_ref_error_pct is not None else "N/A",
                    "Runtime Change (%)": f"{res.runtime_convergence_pct:.3f}%" if res.runtime_convergence_pct is not None else "N/A",
                    "Peak RAM (MB)": f"{res.peak_memory_mb:.1f}" if res.peak_memory_mb is not None else "N/A",
                    "Status Note": res.status_note,
                })
        return pd.DataFrame(rows)
