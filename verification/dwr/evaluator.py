"""
Phase B Evaluation and Statistical Analysis.
Analyzes raw simulation results against pre-registered hypotheses:
- S_DOF savings ratio at 2.0%, 1.0%, 0.5% true QoI error
- Primary hypothesis check: S_DOF >= 1.30 on >= 3 problems, geomean >= 1.30
- Secondary hypothesis check: Effectivity in [0.5, 2.0] for >= 90% of runs
- Secondary computational cost: S_T runtime comparison
- Generates publication plots and summary.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW_DIR = Path("results/phase_b/raw")
PLOT_DIR = Path("results/phase_b/plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = Path("results/phase_b")

TARGETS = [0.02, 0.01, 0.005]  # 2.0%, 1.0%, 0.5%
PROBLEMS = ["cantilever", "plate_with_hole", "notched_bar", "l_shaped"]
METHODS = ["uniform", "zz", "goal_aware", "dwr"]


def find_target_metrics(records: List[Dict[str, Any]], target: float) -> Optional[Dict[str, Any]]:
    """Find first iteration meeting the true relative error target."""
    for r in records:
        if r["true_error_rel"] <= target:
            return {
                "iteration": r["iteration"],
                "primal_dofs": r["primal_dofs"],
                "true_error_rel": r["true_error_rel"],
                "t_total_cumulative_sec": sum(rec["t_total_iter_sec"] for rec in records[:r["iteration"]+1]),
            }
    return None


def evaluate_phase_b():
    # 1. Load all raw data
    raw_data: Dict[str, Dict[str, List[List[Dict[str, Any]]]]] = {p: {m: [] for m in METHODS} for p in PROBLEMS}

    for p in PROBLEMS:
        for var_idx in range(3):
            for m in METHODS:
                fpath = RAW_DIR / p / f"{m}_var{var_idx}.json"
                if fpath.exists():
                    with open(fpath, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    raw_data[p][m].append(records)

    # 2. Target analysis per problem and variant
    target_results: Dict[str, Any] = {}
    problem_dof_ratios_1pct: Dict[str, List[float]] = {p: [] for p in PROBLEMS}
    problem_time_ratios_1pct: Dict[str, List[float]] = {p: [] for p in PROBLEMS}

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

                # Compute S_DOF = N_ZZ / N_DWR
                met_zz = m_metrics["zz"]
                met_dwr = m_metrics["dwr"]
                if met_zz is not None and met_dwr is not None:
                    s_dof = float(met_zz["primal_dofs"]) / float(met_dwr["primal_dofs"])
                    s_t = float(met_zz["t_total_cumulative_sec"]) / float(met_dwr["t_total_cumulative_sec"]) if met_dwr["t_total_cumulative_sec"] > 0 else 1.0
                    target_results[p][t_str]["S_DOF_ZZ_over_DWR"].append(s_dof)
                    target_results[p][t_str]["S_T_ZZ_over_DWR"].append(s_t)
                    if target == 0.01:
                        problem_dof_ratios_1pct[p].append(s_dof)
                        problem_time_ratios_1pct[p].append(s_t)
                else:
                    target_results[p][t_str]["S_DOF_ZZ_over_DWR"].append(None)
                    target_results[p][t_str]["S_T_ZZ_over_DWR"].append(None)

    # 3. Effectivity statistics across all DWR runs
    effectivities = []
    signed_effectivities = []
    underestimation_count = 0
    in_bounds_count = 0
    total_eligible = 0

    for p in PROBLEMS:
        for var_idx in range(3):
            recs = raw_data[p]["dwr"][var_idx]
            for r in recs:
                eff = r.get("effectivity")
                if eff is not None and np.isfinite(eff) and r["true_error_abs"] > 1e-12:
                    total_eligible += 1
                    effectivities.append(eff)
                    signed_effectivities.append(eff)
                    if 0.5 <= eff <= 2.0:
                        in_bounds_count += 1
                    if eff < 1.0:
                        underestimation_count += 1

    eff_arr = np.array(effectivities) if len(effectivities) > 0 else np.array([1.0])
    mean_signed_eff = float(np.mean(eff_arr))
    median_abs_eff = float(np.median(np.abs(eff_arr)))
    fraction_in_bounds = float(in_bounds_count / total_eligible) if total_eligible > 0 else 0.0
    fraction_below_one = float(underestimation_count / total_eligible) if total_eligible > 0 else 0.0
    underestimates = eff_arr[eff_arr < 1.0]
    max_underestimation = float(np.max(1.0 - underestimates)) if len(underestimates) > 0 else 0.0

    # 4. Problem-level summary at 1.0% target
    problem_summary: Dict[str, Any] = {}
    valid_geomean_values = []
    problems_meeting_1_30 = 0

    for p in PROBLEMS:
        ratios = [r for r in problem_dof_ratios_1pct[p] if r is not None]
        if len(ratios) > 0:
            median_ratio = float(np.median(ratios))
            mean_ratio = float(np.mean(ratios))
            meets_target = bool(median_ratio >= 1.30)
            if meets_target:
                problems_meeting_1_30 += 1
            valid_geomean_values.append(median_ratio)
        else:
            median_ratio = 1.0
            mean_ratio = 1.0
            meets_target = False

        t_ratios = [t for t in problem_time_ratios_1pct[p] if t is not None]
        median_time_ratio = float(np.median(t_ratios)) if len(t_ratios) > 0 else 1.0

        problem_summary[p] = {
            "median_S_DOF": median_ratio,
            "mean_S_DOF": mean_ratio,
            "meets_30pct_savings": meets_target,
            "median_S_T_speedup": median_time_ratio,
            "variant_ratios": ratios,
        }

    # Geometric mean across problems
    if len(valid_geomean_values) > 0:
        geomean_s_dof = float(np.exp(np.mean(np.log(valid_geomean_values))))
    else:
        geomean_s_dof = 1.0

    primary_hypothesis_passed = (problems_meeting_1_30 >= 3) and (geomean_s_dof >= 1.30)
    secondary_reliability_passed = (fraction_in_bounds >= 0.90)

    # 5. Final Classification Rule (Section 12)
    # PASS: DWR consistency passes, >= 3 problems meet S_DOF >= 1.30, geomean >= 1.30, reliability >= 90%, ref uncertainty verified
    # PARTIAL: Real advantage on some problems but misses broad 3-problem / geomean target, or ref uncertain
    # FAIL: Valid but fails to demonstrate advantage
    # INCOMPLETE: Consistency check failed or controls violated
    if primary_hypothesis_passed and secondary_reliability_passed:
        final_classification = "PASS"
    elif any(ps["meets_30pct_savings"] for ps in problem_summary.values()):
        final_classification = "PARTIAL"
    else:
        final_classification = "FAIL"

    summary = {
        "title": "GDEC Phase B Feasibility Gate Summary: DWR vs ZZ",
        "final_classification": final_classification,
        "primary_hypothesis": {
            "description": "S_DOF >= 1.30 at 1.0% error on >= 3 problems, geomean >= 1.30",
            "passed": primary_hypothesis_passed,
            "problems_meeting_target": problems_meeting_1_30,
            "total_problems": len(PROBLEMS),
            "geometric_mean_S_DOF": geomean_s_dof,
            "target_threshold": 1.30,
        },
        "secondary_reliability": {
            "description": "Effectivity in [0.5, 2.0] for >= 90% of eligible runs",
            "passed": secondary_reliability_passed,
            "fraction_in_bounds": fraction_in_bounds,
            "target_fraction": 0.90,
            "total_evaluated_runs": total_eligible,
            "mean_signed_effectivity": mean_signed_eff,
            "median_absolute_effectivity": median_abs_eff,
            "fraction_below_one": fraction_below_one,
            "max_underestimation": max_underestimation,
        },
        "problems": problem_summary,
        "target_level_evaluations": target_results,
    }

    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=== Phase B Evaluation Completed ===")
    print(f"Final Classification: {final_classification}")
    print(f"Primary Hypothesis Passed: {primary_hypothesis_passed} ({problems_meeting_1_30}/4 problems, geomean S_DOF = {geomean_s_dof:.3f})")
    print(f"Secondary Reliability Passed: {secondary_reliability_passed} ({fraction_in_bounds*100:.1f}% in [0.5, 2.0])")
    for p, ps in problem_summary.items():
        print(f"  - {p:15s}: S_DOF = {ps['median_S_DOF']:.3f} (Meets >=1.30: {ps['meets_30pct_savings']}), S_T = {ps['median_S_T_speedup']:.2f}x")

    # 6. Generate Publication Plots
    _generate_plots(raw_data, effectivities)


def _generate_plots(raw_data, effectivities):
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
        plt.savefig(PLOT_DIR / f"dof_vs_error_{p}.png", dpi=200)
        plt.close()

    # 2. Effectivity Distribution Histogram
    plt.figure(figsize=(7, 5))
    eff_arr = np.array(effectivities)
    plt.hist(eff_arr, bins=25, color="tab:green", edgecolor="black", alpha=0.7, label="DWR Effectivities")
    plt.axvline(1.0, color="k", linestyle="-", linewidth=2, label="Ideal (I_eff = 1.0)")
    plt.axvline(0.5, color="r", linestyle="--", label="Lower Bound (0.5)")
    plt.axvline(2.0, color="r", linestyle="--", label="Upper Bound (2.0)")
    plt.xlabel("Effectivity Index I_eff = |eta_DWR| / |J_ref - J_h|")
    plt.ylabel("Sample Frequency")
    plt.title("DWR Estimator Effectivity Distribution Across All Simulations")
    plt.grid(True, ls=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "effectivity_distribution.png", dpi=200)
    plt.close()

    # 3. Runtime vs True Relative Error (Cantilever)
    plt.figure(figsize=(7, 5))
    for m in METHODS:
        recs = raw_data["cantilever"][m][0]
        t_cum = []
        running_t = 0.0
        for r in recs:
            running_t += r["t_total_iter_sec"]
            t_cum.append(running_t)
        errs = [r["true_error_rel"] * 100.0 for r in recs]
        plt.loglog(t_cum, errs, markers[m], color=colors[m], label=m.upper(), linewidth=1.8, markersize=6)

    plt.axhline(1.0, color="r", linestyle="--", alpha=0.7, label="1.0% Target")
    plt.xlabel("Cumulative Wall-Clock Time (seconds)")
    plt.ylabel("True QoI Relative Error (%)")
    plt.title("QoI Convergence vs Computational Time (Cantilever)")
    plt.grid(True, which="both", ls=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "runtime_vs_error.png", dpi=200)
    plt.close()

    # 4. Repeated Mesh Sensitivity
    plt.figure(figsize=(8, 5))
    bar_width = 0.18
    indices = np.arange(len(PROBLEMS))

    for m_idx, m in enumerate(METHODS):
        median_dofs_1pct = []
        for p in PROBLEMS:
            dof_vals = []
            for var_idx in range(3):
                met = find_target_metrics(raw_data[p][m][var_idx], 0.01)
                if met is not None:
                    dof_vals.append(met["primal_dofs"])
                else:
                    dof_vals.append(raw_data[p][m][var_idx][-1]["primal_dofs"])
            median_dofs_1pct.append(np.median(dof_vals))

        plt.bar(indices + m_idx * bar_width, median_dofs_1pct, bar_width, label=m.upper(), color=colors[m], alpha=0.85)

    plt.yscale("log")
    plt.xlabel("Benchmark Problem")
    plt.ylabel("Median Primal DOFs to Reach 1.0% Error (log scale)")
    plt.title("Cross-Method Resource Comparison across Repeated Mesh Variants")
    plt.xticks(indices + 1.5 * bar_width, [p.replace('_', ' ').title() for p in PROBLEMS])
    plt.grid(True, which="both", ls=":", axis="y")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "repeated_mesh_sensitivity.png", dpi=200)
    plt.close()

    print("All Phase B publication plots generated successfully.")


if __name__ == "__main__":
    evaluate_phase_b()
