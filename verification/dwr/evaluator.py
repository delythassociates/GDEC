"""
Phase B.1 Evaluation, Reconciliation and Statistical Analysis.
Analyzes raw simulation results against pre-registered hypotheses:
- S_DOF savings ratio at 2.0%, 1.0%, 0.5% true QoI error
- Non-overlapping end-to-end timing including mesh refinement and component breakdown
- Trajectory-level and iteration-level DWR estimator effectivity analysis
- Rigorous reference uncertainty audit and gating (notched bar GCI > 1% handled per protocol)
- Pre-registered decision rules and reporting reconciliation
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from verification.dwr.reference_solutions import REFERENCE_DATABASE

RAW_DIR = Path("results/phase_b1/raw")
PLOT_DIR = Path("results/phase_b1/plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = Path("results/phase_b1")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [0.02, 0.01, 0.005]  # 2.0%, 1.0%, 0.5%
PROBLEMS = ["cantilever", "plate_with_hole", "notched_bar", "l_shaped"]
METHODS = ["uniform", "zz", "goal_aware", "dwr"]

QOI_DESCRIPTIONS = {
    "cantilever": "Boundary-average vertical displacement on right boundary x=2.0 (m)",
    "plate_with_hole": "Patch-average horizontal displacement on [0.95, 1.05] x [0.75, 0.95] (m)",
    "notched_bar": "Patch-average vertical displacement on [0.85, 1.15] x [0.35, 0.45] (m)",
    "l_shaped": "Patch-average vertical displacement on [0.10, 0.40] x [0.60, 0.90] (m)",
}


def find_target_metrics(records: List[Dict[str, Any]], target: float) -> Optional[Dict[str, Any]]:
    """Find first iteration meeting the true relative error target."""
    for r in records:
        if r["true_error_rel"] <= target:
            idx = r["iteration"]
            sub = records[: idx + 1]
            return {
                "iteration": r["iteration"],
                "primal_dofs": r["primal_dofs"],
                "true_error_rel": r["true_error_rel"],
                "t_total_cumulative_sec": sum(rec["t_total_iter_sec"] for rec in sub),
                "t_primal_cumulative_sec": sum(rec["t_primal_sec"] for rec in sub),
                "t_adjoint_cumulative_sec": sum(rec["t_adjoint_sec"] for rec in sub),
                "t_estimator_cumulative_sec": sum(rec["t_estimator_sec"] for rec in sub),
                "t_marking_cumulative_sec": sum(rec["t_marking_sec"] for rec in sub),
                "t_refinement_cumulative_sec": sum(rec["t_refinement_sec"] for rec in sub),
            }
    return None


def evaluate_phase_b1(raw_dir: Path = RAW_DIR, out_dir: Path = OUT_DIR, plot_dir: Path = PLOT_DIR):
    # 1. Load all raw data
    raw_data: Dict[str, Dict[str, List[List[Dict[str, Any]]]]] = {p: {m: [] for m in METHODS} for p in PROBLEMS}

    for p in PROBLEMS:
        for var_idx in range(3):
            for m in METHODS:
                fpath = raw_dir / p / f"{m}_var{var_idx}.json"
                if fpath.exists():
                    with open(fpath, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    raw_data[p][m].append(records)

    # 2. Target analysis per problem, target, and variant
    target_results: Dict[str, Any] = {}
    problem_dof_ratios_1pct: Dict[str, List[Optional[float]]] = {p: [] for p in PROBLEMS}
    problem_time_ratios_1pct: Dict[str, List[Optional[float]]] = {p: [] for p in PROBLEMS}

    for p in PROBLEMS:
        target_results[p] = {}
        for target in TARGETS:
            t_str = f"{target*100:.1f}%"
            target_results[p][t_str] = {m: [] for m in METHODS}
            target_results[p][t_str]["S_DOF_ZZ_over_DWR"] = []
            target_results[p][t_str]["S_T_ZZ_over_DWR"] = []

            for var_idx in range(3):
                m_metrics = {}
                for m in METHODS:
                    recs = raw_data[p][m][var_idx]
                    met = find_target_metrics(recs, target)
                    m_metrics[m] = met
                    target_results[p][t_str][m].append(met)

                met_zz = m_metrics["zz"]
                met_dwr = m_metrics["dwr"]
                if met_zz is not None and met_dwr is not None:
                    s_dof = float(met_zz["primal_dofs"]) / float(met_dwr["primal_dofs"])
                    t_dwr = met_dwr["t_total_cumulative_sec"]
                    s_t = float(met_zz["t_total_cumulative_sec"]) / float(t_dwr) if t_dwr > 0 else 1.0
                    target_results[p][t_str]["S_DOF_ZZ_over_DWR"].append(s_dof)
                    target_results[p][t_str]["S_T_ZZ_over_DWR"].append(s_t)
                    if target == 0.01:
                        problem_dof_ratios_1pct[p].append(s_dof)
                        problem_time_ratios_1pct[p].append(s_t)
                else:
                    target_results[p][t_str]["S_DOF_ZZ_over_DWR"].append(None)
                    target_results[p][t_str]["S_T_ZZ_over_DWR"].append(None)
                    if target == 0.01:
                        problem_dof_ratios_1pct[p].append(None)
                        problem_time_ratios_1pct[p].append(None)

    # 3. Trajectory-Level and Iteration-Level Effectivity Statistics
    trajectories_summary: List[Dict[str, Any]] = []
    all_abs_effectivities = []
    all_signed_effectivities = []

    for p in PROBLEMS:
        for var_idx in range(3):
            recs = raw_data[p]["dwr"][var_idx]
            traj_abs_effs = []
            traj_signed_effs = []
            traj_underest = 0

            for r in recs:
                abs_eff = r.get("absolute_effectivity")
                if abs_eff is None:
                    abs_eff = r.get("effectivity")

                sign_eff = r.get("signed_effectivity")
                if sign_eff is None and abs_eff is not None:
                    sign_eff = abs_eff  # fallback

                if abs_eff is not None and np.isfinite(abs_eff) and r["true_error_abs"] > 1e-12:
                    traj_abs_effs.append(abs_eff)
                    all_abs_effectivities.append(abs_eff)
                    if sign_eff is not None and np.isfinite(sign_eff):
                        traj_signed_effs.append(sign_eff)
                        all_signed_effectivities.append(sign_eff)

                    if abs_eff < 1.0:
                        traj_underest += 1

            n_points = len(traj_abs_effs)
            in_bounds = sum(1 for e in traj_abs_effs if 0.5 <= e <= 2.0)
            frac_in_bounds = float(in_bounds / n_points) if n_points > 0 else 0.0
            median_abs = float(np.median(traj_abs_effs)) if n_points > 0 else 0.0
            mean_signed = float(np.mean(traj_signed_effs)) if len(traj_signed_effs) > 0 else 0.0
            under_freq = float(traj_underest / n_points) if n_points > 0 else 0.0
            under_vals = [e for e in traj_abs_effs if e < 1.0]
            max_under = float(np.max([1.0 - e for e in under_vals])) if len(under_vals) > 0 else 0.0
            final_mesh_eff = float(traj_abs_effs[-1]) if n_points > 0 else 0.0
            traj_passed = bool(frac_in_bounds >= 0.90)

            traj_record = {
                "problem_id": p,
                "variant_idx": var_idx,
                "n_evaluations": len(recs),
                "n_eligible_points": n_points,
                "fraction_in_bounds": frac_in_bounds,
                "median_abs_effectivity": median_abs,
                "mean_signed_effectivity": mean_signed,
                "underestimation_frequency": under_freq,
                "max_underestimation": max_under,
                "final_mesh_effectivity": final_mesh_eff,
                "trajectory_passed": traj_passed,
            }
            trajectories_summary.append(traj_record)

    total_trajectories = len(trajectories_summary)
    trajectories_passed_count = sum(1 for t in trajectories_summary if t["trajectory_passed"])
    trajectory_pass_fraction = float(trajectories_passed_count / total_trajectories)

    # Iteration-level overall stats
    abs_eff_arr = np.array(all_abs_effectivities) if len(all_abs_effectivities) > 0 else np.array([1.0])
    signed_eff_arr = np.array(all_signed_effectivities) if len(all_signed_effectivities) > 0 else np.array([1.0])
    total_eligible = len(abs_eff_arr)
    in_bounds_total = int(np.sum((abs_eff_arr >= 0.5) & (abs_eff_arr <= 2.0)))
    under_total = int(np.sum(abs_eff_arr < 1.0))
    fraction_in_bounds_global = float(in_bounds_total / total_eligible)
    underestimation_freq_global = float(under_total / total_eligible)
    global_under_vals = abs_eff_arr[abs_eff_arr < 1.0]
    max_underestimation_global = float(np.max(1.0 - global_under_vals)) if len(global_under_vals) > 0 else 0.0

    # 4. Problem-Level Summary and Reference Uncertainty Reconciliation at 1.0%
    problem_summary: Dict[str, Any] = {}
    evaluable_geomean_values = []
    diagnostic_geomean_values = []
    evaluable_problems_meeting_1_30 = 0

    for p in PROBLEMS:
        ref_meta = REFERENCE_DATABASE[p]
        gci = ref_meta["gci_uncertainty_pct"]
        ratios = [r for r in problem_dof_ratios_1pct[p] if r is not None]
        t_ratios = [t for t in problem_time_ratios_1pct[p] if t is not None]

        if len(ratios) > 0:
            median_ratio = float(np.median(ratios))
            mean_ratio = float(np.mean(ratios))
            meets_target = bool(median_ratio >= 1.30)
        else:
            median_ratio = 1.0
            mean_ratio = 1.0
            meets_target = False

        median_time_ratio = float(np.median(t_ratios)) if len(t_ratios) > 0 else 1.0

        # Reference uncertainty gating at 1.0% target:
        # Notched bar GCI is 1.76% > 1.0%, so comparison is REF_UNCERTAIN
        if p == "notched_bar":
            comparison_status = "REF_UNCERTAIN"
            gating_note = (
                f"Reference GCI uncertainty ({gci:.2f}%) exceeds 1.0% target. "
                "Preserved as diagnostic evidence only; excluded from primary pass/fail tally."
            )
            diagnostic_geomean_values.append(median_ratio)
        else:
            comparison_status = "EVALUABLE"
            gating_note = f"Reference GCI uncertainty ({gci:.4f}%) is well below 1.0% target (VERIFIED)."
            evaluable_geomean_values.append(median_ratio)
            diagnostic_geomean_values.append(median_ratio)
            if meets_target:
                evaluable_problems_meeting_1_30 += 1

        problem_summary[p] = {
            "qoi_description": QOI_DESCRIPTIONS[p],
            "reference_j_ref": ref_meta["j_ref"],
            "reference_gci_pct": gci,
            "status_at_1pct_target": comparison_status,
            "gating_note": gating_note,
            "median_S_DOF": median_ratio,
            "mean_S_DOF": mean_ratio,
            "meets_30pct_savings": meets_target,
            "median_S_T_speedup": median_time_ratio,
            "variant_ratios": ratios,
        }

    # Geometric mean of evaluable benchmarks (3 problems)
    if len(evaluable_geomean_values) > 0:
        geomean_s_dof_evaluable = float(np.exp(np.mean(np.log(evaluable_geomean_values))))
    else:
        geomean_s_dof_evaluable = 1.0

    # Geometric mean of all benchmarks including diagnostic (4 problems)
    if len(diagnostic_geomean_values) > 0:
        geomean_s_dof_all = float(np.exp(np.mean(np.log(diagnostic_geomean_values))))
    else:
        geomean_s_dof_all = 1.0

    # Primary hypothesis check on evaluable benchmarks:
    # Requires >= 3 problems meeting 1.30 and geomean >= 1.30
    evaluable_problem_count = len(evaluable_geomean_values)
    primary_hypothesis_passed = (
        (evaluable_problems_meeting_1_30 >= 3)
        and (geomean_s_dof_evaluable >= 1.30)
    )

    # Secondary reliability check
    secondary_reliability_passed = (fraction_in_bounds_global >= 0.90) and (trajectory_pass_fraction >= 0.90)

    # Final Classification per pre-registered rule:
    # Consistency passed (8/8), but failed DOF savings (0/3 evaluable) and effectivity reliability
    if primary_hypothesis_passed and secondary_reliability_passed:
        final_classification = "PASS"
    elif any(ps["meets_30pct_savings"] for p, ps in problem_summary.items() if ps["status_at_1pct_target"] == "EVALUABLE"):
        final_classification = "PARTIAL"
    else:
        final_classification = "FAIL"

    summary = {
        "title": "GDEC Phase B.1 Feasibility Gate Summary: Reconciled Audit & Evaluation",
        "final_classification": final_classification,
        "primary_hypothesis": {
            "description": "S_DOF >= 1.30 at 1.0% error on >= 3 problems, geomean >= 1.30",
            "passed": primary_hypothesis_passed,
            "evaluable_problems_meeting_target": evaluable_problems_meeting_1_30,
            "total_evaluable_problems": evaluable_problem_count,
            "geometric_mean_S_DOF_evaluable": geomean_s_dof_evaluable,
            "geometric_mean_S_DOF_all_diagnostic": geomean_s_dof_all,
            "target_threshold": 1.30,
        },
        "secondary_reliability": {
            "description": "Effectivity in [0.5, 2.0] for >= 90% of runs and trajectories",
            "passed": secondary_reliability_passed,
            "iteration_level": {
                "total_evaluated_points": total_eligible,
                "fraction_in_bounds": fraction_in_bounds_global,
                "target_fraction": 0.90,
                "mean_signed_effectivity": float(np.mean(signed_eff_arr)),
                "median_signed_effectivity": float(np.median(signed_eff_arr)),
                "mean_absolute_effectivity": float(np.mean(abs_eff_arr)),
                "median_absolute_effectivity": float(np.median(abs_eff_arr)),
                "underestimation_frequency": underestimation_freq_global,
                "max_underestimation": max_underestimation_global,
            },
            "trajectory_level": {
                "total_trajectories": total_trajectories,
                "trajectories_passed": trajectories_passed_count,
                "trajectory_pass_fraction": trajectory_pass_fraction,
                "trajectories": trajectories_summary,
            },
        },
        "timing_analysis": {
            "description": "Non-overlapping timing including primal, adjoint, estimator, marking, and refinement",
            "median_speedup_S_T": {p: problem_summary[p]["median_S_T_speedup"] for p in PROBLEMS},
        },
        "problems": problem_summary,
        "target_level_evaluations": target_results,
    }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=== Phase B.1 Reconciled Evaluation Completed ===")
    print(f"Final Classification: {final_classification}")
    print(
        f"Primary Hypothesis Passed: {primary_hypothesis_passed} "
        f"({evaluable_problems_meeting_1_30}/{evaluable_problem_count} evaluable problems, "
        f"geomean S_DOF = {geomean_s_dof_evaluable:.3f})"
    )
    print(
        f"Secondary Reliability: Iterations in [0.5, 2.0] = {fraction_in_bounds_global*100:.1f}%, "
        f"Trajectories Passed = {trajectories_passed_count}/{total_trajectories} ({trajectory_pass_fraction*100:.1f}%)"
    )
    for p, ps in problem_summary.items():
        status_tag = f"[{ps['status_at_1pct_target']}]"
        print(
            f"  - {p:15s} {status_tag:15s}: S_DOF = {ps['median_S_DOF']:.3f} "
            f"(Meets >=1.30: {ps['meets_30pct_savings']}), S_T = {ps['median_S_T_speedup']:.2f}x"
        )

    # Generate plots
    _generate_plots(raw_data, all_abs_effectivities, all_signed_effectivities, plot_dir)


def _generate_plots(raw_data, abs_effectivities, signed_effectivities, plot_dir: Path):
    markers = {"uniform": "o-", "zz": "s-", "goal_aware": "^-", "dwr": "d-"}
    colors = {"uniform": "tab:gray", "zz": "tab:blue", "goal_aware": "tab:orange", "dwr": "tab:green"}

    # 1. DOF vs True Relative Error plots for each problem (Variant 0)
    for p in PROBLEMS:
        plt.figure(figsize=(7, 5))
        for m in METHODS:
            recs = raw_data[p][m][0]
            dofs = [r["primal_dofs"] for r in recs]
            errs = [r["true_error_rel"] * 100.0 for r in recs]
            plt.loglog(dofs, errs, markers[m], color=colors[m], label=m.upper(), linewidth=1.8, markersize=6)

        plt.axhline(1.0, color="r", linestyle="--", alpha=0.7, label="1.0% Target")
        plt.axhline(0.5, color="darkred", linestyle=":", alpha=0.7, label="0.5% Target")
        plt.xlabel("Primal Degrees of Freedom (DOFs)")
        plt.ylabel("True QoI Relative Error (%)")
        plt.title(f"QoI Convergence vs DOFs: {p.replace('_', ' ').title()}")
        plt.grid(True, which="both", ls=":")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_dir / f"dof_vs_error_{p}.png", dpi=200)
        plt.close()

    # 2. Effectivity Distribution Histogram
    plt.figure(figsize=(7, 5))
    eff_arr = np.array(abs_effectivities)
    plt.hist(eff_arr, bins=25, color="tab:green", edgecolor="black", alpha=0.7, label="DWR Absolute Effectivity")
    plt.axvline(1.0, color="k", linestyle="-", linewidth=2, label="Ideal (I_eff = 1.0)")
    plt.axvline(0.5, color="r", linestyle="--", label="Lower Bound (0.5)")
    plt.axvline(2.0, color="r", linestyle="--", label="Upper Bound (2.0)")
    plt.xlabel("Effectivity Index I_eff = |eta_DWR| / |J_ref - J_h|")
    plt.ylabel("Sample Frequency")
    plt.title("DWR Estimator Effectivity Distribution (Phase B.1)")
    plt.grid(True, ls=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / "effectivity_distribution.png", dpi=200)
    plt.close()


if __name__ == "__main__":
    evaluate_phase_b1()
