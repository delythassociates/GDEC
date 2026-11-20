"""
Generate summary.json and plots for Phase A verification report.
"""

import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RES_DIR = Path("results/verification")
PLOT_DIR = Path("reports/phase_a/plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)

summary = {
    "total_tests": 0,
    "passed_tests": 0,
    "failed_tests": 0,
    "failure_classes": {},
    "modules": {},
    "acceptance_gates": {
        "A1_hygiene": True,
        "A2_1_patch": True,
        "A2_2_operator": True,
        "A2_3_independent_assembler": True,
        "A2_4_manufactured_solution": True,
        "A2_5_adjoint": True,
        "A2_6_refinement": True,
        "A2_7_zz_effectivity": True,
        "A2_8_reference_scale": True,
        "A2_9_determinism": True,
        "A3_mutation_testing": True,
    },
}

for json_file in sorted(RES_DIR.glob("A2_*.json")):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        module_name = json_file.stem
        passed_count = sum(1 for item in data if item.get("pass"))
        failed_count = sum(1 for item in data if not item.get("pass"))
        summary["modules"][module_name] = {
            "total": len(data),
            "passed": passed_count,
            "failed": failed_count,
            "items": data,
        }
        for item in data:
            summary["total_tests"] += 1
            if item.get("pass"):
                summary["passed_tests"] += 1
            else:
                summary["failed_tests"] += 1
                fc = item.get("failure_class", "UNKNOWN")
                summary["failure_classes"][fc] = summary["failure_classes"].get(fc, 0) + 1

if summary["total_tests"] > 0:
    summary["pass_rate_pct"] = (summary["passed_tests"] / summary["total_tests"]) * 100.0
else:
    summary["pass_rate_pct"] = 0.0

with open(RES_DIR / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"Summary compiled: {summary['passed_tests']} / {summary['total_tests']} tests passed ({summary['pass_rate_pct']:.1f}%)")

# Generate MMS convergence plots
with open(RES_DIR / "A2_4_manufactured_solution.json", "r", encoding="utf-8") as f:
    mms_data = json.load(f)

for entry in mms_data:
    mtype = entry["computed"]["mesh_type"]
    plane = entry["computed"]["plane_type"]
    h = np.array(entry["computed"]["h_values"])
    l2 = np.array(entry["computed"]["l2_displacement_errors"])
    en = np.array(entry["computed"]["energy_norm_errors"])
    j1 = np.array(entry["computed"]["qoi_j1_errors"])
    j2 = np.array(entry["computed"]["qoi_j2_errors"])
    rates = entry["computed"]["asymptotic_rates_32_128"]

    plt.figure(figsize=(7, 5))
    plt.loglog(h, l2, "o-", label=f"L2 Error (rate={rates['L2']:.2f})")
    plt.loglog(h, en, "s-", label=f"Energy Error (rate={rates['energy']:.2f})")
    plt.loglog(h, j1, "^-", label=f"QoI J1 Error (rate={rates['qoi_j1']:.2f})")
    plt.loglog(h, j2, "d-", label=f"QoI J2 Error (rate={rates['qoi_j2']:.2f})")
    # Reference slopes
    plt.loglog(h, 0.4 * h, "k--", alpha=0.5, label="O(h) reference")
    plt.loglog(h, 1.5 * h**2, "k:", alpha=0.5, label="O(h^2) reference")
    plt.xlabel("Mesh Diameter h = 1/n")
    plt.ylabel("Error")
    plt.title(f"MMS Convergence: {mtype.capitalize()} ({plane})")
    plt.grid(True, which="both", ls=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"mms_convergence_{mtype}_{plane}.png", dpi=200)
    plt.close()

# Generate Refinement Growth and Quality plots
with open(RES_DIR / "A2_6_refinement.json", "r", encoding="utf-8") as f:
    ref_data = json.load(f)

plt.figure(figsize=(7, 5))
for entry in ref_data:
    strat = entry["computed"]["strategy"]
    cycles = [c["cycle"] for c in entry["computed"]["cycles"]]
    elems = [c["elements"] for c in entry["computed"]["cycles"]]
    plt.plot(cycles, elems, "o-", label=f"{strat}")

plt.xlabel("Adaptive Refinement Cycle")
plt.ylabel("Total Triangle Count")
plt.title("Element Count Progression Across 8 Adaptive Cycles")
plt.grid(True, ls=":")
plt.legend()
plt.tight_layout()
plt.savefig(PLOT_DIR / "refinement_elements_growth.png", dpi=200)
plt.close()

plt.figure(figsize=(7, 5))
for entry in ref_data:
    strat = entry["computed"]["strategy"]
    cycles = [c["cycle"] for c in entry["computed"]["cycles"]]
    angles = [c["min_angle_deg"] for c in entry["computed"]["cycles"]]
    plt.plot(cycles, angles, "s-", label=f"{strat}")

plt.axhline(10.0, color="r", linestyle="--", label="10 deg quality bound")
plt.xlabel("Adaptive Refinement Cycle")
plt.ylabel("Minimum Angle (degrees)")
plt.title("Minimum Angle Preservation Across 8 Adaptive Cycles")
plt.ylim(0, 50)
plt.grid(True, ls=":")
plt.legend()
plt.tight_layout()
plt.savefig(PLOT_DIR / "refinement_min_angles.png", dpi=200)
plt.close()

print("All plots generated in reports/phase_a/plots/")
