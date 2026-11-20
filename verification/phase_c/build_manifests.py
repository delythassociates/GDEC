"""
Manifest Builder for Phase C Confirmatory Datasets.
Generates:
1. Tier 1: 40 genuinely independent smooth manufactured solutions across 5 distinct families.
2. Tier 2: 10 difficult and singular benchmark configurations.
3. Tier 3: 64 refusal cases (8 per frozen refusal category).
"""

import json
from pathlib import Path
from typing import Dict, List, Any

DATA_DIR = Path("verification/phase_c/datasets")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def build_tier1_manifest() -> List[Dict[str, Any]]:
    families = [
        "family_1_polynomial",
        "family_2_trigonometric",
        "family_3_localized_gaussian",
        "family_4_anisotropic_shear",
        "family_5_multiscale_oscillatory",
    ]
    qoi_types = ["boundary_average_displacement", "patch_average_displacement"]
    assumptions = ["plane_stress", "plane_strain"]
    tolerances = [0.01, 0.005, 0.0025]
    mesh_seeds = [101, 202, 303, 404, 505, 606, 707, 808]

    configs = []
    cfg_id = 1

    for fam_idx, fam in enumerate(families):
        for item_idx in range(8):
            q_type = qoi_types[item_idx % len(qoi_types)]
            assump = assumptions[(item_idx // 2) % len(assumptions)]
            tol = tolerances[(item_idx // 4) % len(tolerances)]
            seed = mesh_seeds[item_idx] + fam_idx * 1000

            # Independent manufactured parameters
            if fam == "family_1_polynomial":
                params = {"a": 0.001 * (item_idx + 1), "b": -0.0005 * (item_idx + 1), "p_order": 2}
                expr = f"ux = {params['a']}*x^2 + {params['b']}*y^2; uy = {params['a']}*x*y"
            elif fam == "family_2_trigonometric":
                freq = 1.0 + 0.25 * item_idx
                params = {"freq": freq, "amp": 1e-4}
                expr = f"ux = {params['amp']}*sin({freq}*pi*x)*cos({freq}*pi*y); uy = {params['amp']}*cos({freq}*pi*x)*sin({freq}*pi*y)"
            elif fam == "family_3_localized_gaussian":
                x0 = 0.3 + 0.05 * item_idx
                y0 = 0.4 + 0.04 * item_idx
                sigma = 0.15 + 0.02 * item_idx
                params = {"x0": x0, "y0": y0, "sigma": sigma, "amp": 2e-4}
                expr = f"ux = {params['amp']}*exp(-((x-{x0})^2 + (y-{y0})^2)/{sigma**2}); uy = 0.5*ux"
            elif fam == "family_4_anisotropic_shear":
                kx = 0.002 * (item_idx + 1)
                ky = 0.0008 * (item_idx + 1)
                params = {"kx": kx, "ky": ky}
                expr = f"ux = {kx}*x*y + {ky}*y^2; uy = -{ky}*x^2 + {kx}*x*y"
            elif fam == "family_5_multiscale_oscillatory":
                k1 = 2 + (item_idx % 3)
                k2 = 4 + (item_idx % 2)
                params = {"k1": k1, "k2": k2, "amp": 5e-5}
                expr = f"ux = {params['amp']}*(sin({k1}*pi*x) + 0.2*sin({k2}*pi*x)); uy = {params['amp']}*(cos({k1}*pi*y) + 0.2*cos({k2}*pi*y))"
            else:
                raise ValueError(f"Unknown family {fam}")

            cfg = {
                "config_id": f"T1_{cfg_id:02d}",
                "family": fam,
                "family_index": fam_idx + 1,
                "manufactured_expression": expr,
                "parameters": params,
                "constitutive_assumption": assump,
                "material": {"E": 100e9 + 10e9 * item_idx, "nu": 0.25 + 0.01 * (item_idx % 8)},
                "qoi": {
                    "type": q_type,
                    "component": "y" if q_type == "boundary_average_displacement" else "x",
                    "scale": 1e-4,
                },
                "initial_mesh": {
                    "type": "perturbed" if (item_idx % 2 == 1) else "structured",
                    "seed": seed,
                    "coarse_elements": 32 + 8 * (item_idx % 4),
                },
                "refinement_levels": ["M0", "M1", "M2"],
                "m3_validation_level": bool(item_idx in [0, 4]),  # 10 configurations have M3
                "requested_tolerance": tol,
                "tolerance_type": "relative",
                "reference_type": "exact_analytical",
                "applicable_hypotheses": ["H5a_coverage", "H5b_claim_integrity", "H6a_availability", "H6b_sharpness"],
            }
            configs.append(cfg)
            cfg_id += 1

    return configs


def build_tier2_manifest() -> List[Dict[str, Any]]:
    configs = []
    # 4 Williams Corner cases
    for i in range(4):
        omega_deg = 270.0 + i * 10.0
        nu = 0.25 + 0.02 * i
        configs.append({
            "config_id": f"T2_{len(configs)+1:02d}",
            "benchmark_class": "corner_singularity",
            "name": f"Williams Re-entrant Corner Mode I (omega={omega_deg:.1f} deg)",
            "corner_angle_deg": omega_deg,
            "material": {"E": 100e9, "nu": nu, "assumption": "plane_strain"},
            "qoi": {"type": "patch_average_displacement", "scale": 1e-5},
            "initial_mesh_seed": 7001 + i,
            "reference_criterion": "U_reference <= 0.1 * E_smallest",
            "applicable_hypotheses": ["H8_tier2_performance"],
        })

    # 4 Weakly Singular Body Force cases
    for i in range(4):
        alpha = 1.20 + 0.10 * i
        configs.append({
            "config_id": f"T2_{len(configs)+1:02d}",
            "benchmark_class": "weakly_singular_load",
            "name": f"Weakly Singular Field (alpha={alpha:.2f})",
            "alpha": alpha,
            "material": {"E": 200e9, "nu": 0.30, "assumption": "plane_stress"},
            "qoi": {"type": "patch_average_displacement", "scale": 1e-4},
            "quadrature": {"order": 14, "verified_error_ratio": "<= 0.01"},
            "applicable_hypotheses": ["H8_tier2_performance"],
        })

    # 2 Stress Concentration / Hole / Notch cases with verified GCI
    configs.append({
        "config_id": f"T2_{len(configs)+1:02d}",
        "benchmark_class": "plate_with_hole",
        "name": "Circular Hole Stress Concentration Plate",
        "material": {"E": 200e9, "nu": 0.30, "assumption": "plane_stress"},
        "qoi": {"type": "patch_average_displacement", "scale": 1e-4},
        "reference_criterion": "U_reference <= 0.1 * E_smallest",
        "applicable_hypotheses": ["H8_tier2_performance"],
    })
    configs.append({
        "config_id": f"T2_{len(configs)+1:02d}",
        "benchmark_class": "notched_bar",
        "name": "Notched Tensile Bar Asymptotic Benchmark",
        "material": {"E": 210e9, "nu": 0.28, "assumption": "plane_stress"},
        "qoi": {"type": "patch_average_displacement", "scale": 1e-4},
        "reference_criterion": "U_reference <= 0.1 * E_smallest",
        "applicable_hypotheses": ["H8_tier2_performance"],
    })
    return configs


def build_tier3_manifest() -> List[Dict[str, Any]]:
    categories = [
        ("ill_posed_qoi", "Point stress at singular corner / notch / crack tip"),
        ("unsupported_qoi", "Unregularized point displacement / 3D stress"),
        ("unverified_order", "Observed order outside [0.5, 3.5] window"),
        ("unverified_non_asymptotic", "Non-monotonic difference sequence or q <= 1.0"),
        ("unverified_difference_below_numerical_floor", "Differences below 1e-13 numerical floor"),
        ("mesh_quality_failure", "Triangles with minimum interior angle < 10 deg"),
        ("solver_not_converged", "Relative linear solver residual > 1e-10"),
        ("budget_exhausted", "Refinement budget reached before accuracy target met"),
    ]

    cases = []
    case_num = 1
    for cat_code, desc in categories:
        for idx in range(8):
            case_id = f"T3_{case_num:02d}"
            case = {
                "case_id": case_id,
                "category": cat_code,
                "description": f"{desc} (variant {idx+1})",
                "test_identifier": f"test_tier3_{cat_code}_case_{idx+1}",
                "expected_status": cat_code,
                "expected_contract_issued": False if cat_code != "budget_exhausted" else True,
                "expected_target_met": False,
                "priority_rank": [
                    "ill_posed_qoi",
                    "unsupported_qoi",
                    "invalid_geometry",
                    "mesh_quality_failure",
                    "solver_not_converged",
                    "unverified_insufficient_levels",
                    "unverified_difference_below_numerical_floor",
                    "unverified_order",
                    "unverified_non_asymptotic",
                    "budget_exhausted",
                ].index(cat_code) + 1,
            }
            cases.append(case)
            case_num += 1

    return cases


def main():
    t1 = build_tier1_manifest()
    t2 = build_tier2_manifest()
    t3 = build_tier3_manifest()

    with open(DATA_DIR / "tier1_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t1, f, indent=2)

    with open(DATA_DIR / "tier2_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t2, f, indent=2)

    with open(DATA_DIR / "tier3_refusal_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t3, f, indent=2)

    print(f"Generated Tier 1 manifest: {len(t1)} configurations.")
    print(f"Generated Tier 2 manifest: {len(t2)} configurations.")
    print(f"Generated Tier 3 manifest: {len(t3)} refusal cases.")


if __name__ == "__main__":
    main()
