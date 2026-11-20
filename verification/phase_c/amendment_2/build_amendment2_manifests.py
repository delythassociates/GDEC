"""
GDEC Phase C Amendment 2 — Manifest Builder.
Remediates:
- AM2-01: Correct manufactured body forces and exact QoIs for all 40 Tier 1 BVPs.
- AM2-02: 80 unique, executable Tier 3 refusal cases across 10 priority categories.
- AM2-07: Tier 2 singular benchmarks and reference-gate consistency.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

AMEND2_DIR = Path("verification/phase_c/amendment_2")
AMEND2_DIR.mkdir(parents=True, exist_ok=True)


def get_c_components(E: float, nu: float, assumption: str) -> Dict[str, float]:
    """Calculates isotropic elasticity tensor components c11, c12, c33."""
    if assumption == "plane_stress":
        c11 = E / (1.0 - nu**2)
        c12 = (E * nu) / (1.0 - nu**2)
    else:  # plane_strain
        c11 = (E * (1.0 - nu)) / ((1.0 + nu) * (1.0 - 2.0 * nu))
        c12 = (E * nu) / ((1.0 + nu) * (1.0 - 2.0 * nu))
    c33 = (c11 - c12) / 2.0
    return {"c11": c11, "c12": c12, "c33": c33}


def build_tier1_amended2_manifest() -> List[Dict[str, Any]]:
    families = [
        "family_1_polynomial",
        "family_2_trigonometric",
        "family_3_localized_gaussian",
        "family_4_mixed_shear",
        "family_5_multiscale_oscillatory",
    ]
    qoi_types = ["boundary_average_displacement", "patch_average_displacement"]
    assumptions = ["plane_stress", "plane_strain"]

    # Tolerances: exactly 14 @ 0.01, 13 @ 0.005, 13 @ 0.0025 (40 total)
    tolerances_list = [0.01] * 14 + [0.005] * 13 + [0.0025] * 13

    # Balanced M3 selection: 2 per family = 10 items total
    # 5 boundary, 5 patch; 5 structured, 5 perturbed; 5 plane stress, 5 plane strain
    m3_selected_pairs = {
        0: (0, 5),  # Fam 1: item 0 (bnd, str, stress), item 5 (patch, pert, strain)
        1: (1, 4),  # Fam 2: item 1 (patch, pert, stress), item 4 (bnd, str, strain)
        2: (2, 7),  # Fam 3: item 2 (bnd, str, strain), item 7 (patch, pert, stress)
        3: (3, 6),  # Fam 4: item 3 (patch, pert, strain), item 6 (bnd, str, stress)
        4: (1, 6),  # Fam 5: item 1 (patch, pert, stress), item 6 (bnd, str, strain)
    }

    configs = []
    cfg_id = 1

    for fam_idx, fam in enumerate(families):
        for item_idx in range(8):
            flat_idx = fam_idx * 8 + item_idx
            tol = tolerances_list[flat_idx]

            q_type = qoi_types[item_idx % len(qoi_types)]
            assump = assumptions[(item_idx // 2) % len(assumptions)]
            is_m3 = item_idx in m3_selected_pairs[fam_idx]
            mesh_type = "perturbed" if (item_idx % 2 == 1) else "structured"
            seed = 2000 * (fam_idx + 1) + 100 * item_idx + 42

            E_val = 100e9 + 15e9 * (item_idx % 5)
            nu_val = 0.22 + 0.02 * (item_idx % 6)
            c_dict = get_c_components(E_val, nu_val, assump)
            c11, c12, c33 = c_dict["c11"], c_dict["c12"], c_dict["c33"]

            # Family 1: Polynomial
            if fam == "family_1_polynomial":
                a = 0.001 * (item_idx + 1)
                b = -0.0004 * (item_idx + 1)
                expr_ux = f"{a} * x^2 + {b} * y^2"
                expr_uy = f"{a} * x * y"
                # Correct body force: -a*(2*c11 + c12) - c33*(a + 2*b)
                fx_val = -a * (2.0 * c11 + c12) - c33 * (a + 2.0 * b)
                fy_val = 0.0
                fx_expr = f"-{a} * (2 * c11 + c12) - c33 * ({a} + 2 * {b})"
                fy_expr = "0.0"
                params = {"a": a, "b": b, "p_order": 2}
                scale = 1e-4

                if q_type == "boundary_average_displacement":
                    # int_0^1 a*x*(1) dx = 0.5 * a
                    j_exact = 0.5 * a
                else:
                    # int_[0.25, 0.75]^2 (a*x^2 + b*y^2) dx dy / 0.25 = (13/48) * (a + b)
                    j_exact = (13.0 / 48.0) * (a + b)

            # Family 2: Trigonometric
            elif fam == "family_2_trigonometric":
                freqs = [0.5, 1.25, 1.5, 2.25, 2.5, 3.25, 3.5, 4.25]
                freq = freqs[item_idx]
                amp = 1e-4 * (0.8 + 0.1 * item_idx)
                expr_ux = f"{amp} * sin({freq} * pi * x) * cos({freq} * pi * y)"
                expr_uy = f"{amp} * cos({freq} * pi * x) * sin({freq} * pi * y)"
                k_w = freq * math.pi
                fx_expr = f"2 * c11 * ({freq} * pi)^2 * {amp} * sin({freq} * pi * x) * cos({freq} * pi * y)"
                fy_expr = f"2 * c11 * ({freq} * pi)^2 * {amp} * cos({freq} * pi * x) * sin({freq} * pi * y)"
                fx_val = None  # spatially varying
                fy_val = None
                params = {"freq": freq, "amp": amp}
                scale = 1e-4

                if q_type == "boundary_average_displacement":
                    # int_0^1 amp * cos(freq*pi*x) * sin(freq*pi) dx = amp * sin(freq*pi)^2 / (freq*pi)
                    j_exact = amp * (math.sin(k_w) ** 2) / k_w
                else:
                    # int_[0.25, 0.75]^2 amp * sin(k*x)*cos(k*y) dx dy / 0.25
                    ix = (math.cos(0.25 * k_w) - math.cos(0.75 * k_w)) / k_w
                    iy = (math.sin(0.75 * k_w) - math.sin(0.25 * k_w)) / k_w
                    j_exact = (amp / 0.25) * ix * iy

            # Family 3: Localized Gaussian
            elif fam == "family_3_localized_gaussian":
                x0 = 0.35 + 0.04 * (item_idx % 4)
                y0 = 0.45 + 0.03 * (item_idx % 4)
                sigma = 0.12 + 0.02 * (item_idx % 4)
                amp = 2e-4
                expr_ux = f"{amp} * exp(-((x - {x0})^2 + (y - {y0})^2) / {sigma**2})"
                expr_uy = f"0.5 * {amp} * exp(-((x - {x0})^2 + (y - {y0})^2) / {sigma**2})"
                fx_expr = f"-(c11 * phi_xx + c33 * phi_yy + 0.5 * (c12 + c33) * phi_xy)"
                fy_expr = f"-(0.5 * c11 * phi_yy + 0.5 * c33 * phi_xx + (c12 + c33) * phi_xy)"
                fx_val = None
                fy_val = None
                params = {"x0": x0, "y0": y0, "sigma": sigma, "amp": amp}
                scale = 1e-4

                # Analytical exact QoI using erf
                if q_type == "boundary_average_displacement":
                    # uy(x, 1) = 0.5 * amp * exp(-(1-y0)^2 / sigma^2) * exp(-(x-x0)^2 / sigma^2)
                    y_factor = math.exp(-((1.0 - y0) ** 2) / (sigma**2))
                    x_integral = (math.sqrt(math.pi) * sigma / 2.0) * (
                        math.erf((1.0 - x0) / sigma) - math.erf((0.0 - x0) / sigma)
                    )
                    j_exact = 0.5 * amp * y_factor * x_integral
                else:
                    ix = (math.sqrt(math.pi) * sigma / 2.0) * (
                        math.erf((0.75 - x0) / sigma) - math.erf((0.25 - x0) / sigma)
                    )
                    iy = (math.sqrt(math.pi) * sigma / 2.0) * (
                        math.erf((0.75 - y0) / sigma) - math.erf((0.25 - y0) / sigma)
                    )
                    j_exact = (amp / 0.25) * ix * iy

            # Family 4: Mixed Shear (Isotropic)
            elif fam == "family_4_mixed_shear":
                kx = 0.0015 * (item_idx + 1)
                ky = 0.0006 * (item_idx + 1)
                expr_ux = f"{kx} * x * y + {ky} * y^2"
                expr_uy = f"-{ky} * x^2 + {kx} * x * y"
                fx_val = -(2.0 * c33 * ky + (c12 + c33) * kx)
                fy_val = 2.0 * c33 * ky - (c12 + c33) * kx
                fx_expr = f"-2 * c33 * {ky} - (c12 + c33) * {kx}"
                fy_expr = f"2 * c33 * {ky} - (c12 + c33) * {kx}"
                params = {"kx": kx, "ky": ky}
                scale = 1e-4

                if q_type == "boundary_average_displacement":
                    # uy(x, 1) = -ky * x^2 + kx * x -> int_0^1 = -ky/3 + kx/2
                    j_exact = -ky / 3.0 + kx / 2.0
                else:
                    # int_[0.25, 0.75]^2 (kx*x*y + ky*y^2) dx dy / 0.25 = 0.25*kx + (13/48)*ky
                    j_exact = 0.25 * kx + (13.0 / 48.0) * ky

            # Family 5: Multiscale Oscillatory
            elif fam == "family_5_multiscale_oscillatory":
                k_pairs = [(2, 6), (3, 8), (4, 10), (5, 12), (3, 7), (4, 9), (2, 8), (5, 15)]
                k1, k2 = k_pairs[item_idx]
                beta = 0.25
                amp = 5e-5
                expr_ux = f"{amp} * (sin({k1} * pi * x) + {beta} * sin({k2} * pi * x))"
                expr_uy = f"{amp} * (cos({k1} * pi * y) + {beta} * cos({k2} * pi * y))"
                fx_expr = f"c11 * (pi^2) * {amp} * ({k1}^2 * sin({k1}*pi*x) + {beta} * {k2}^2 * sin({k2}*pi*x))"
                fy_expr = f"c11 * (pi^2) * {amp} * ({k1}^2 * cos({k1}*pi*y) + {beta} * {k2}^2 * cos({k2}*pi*y))"
                fx_val = None
                fy_val = None
                params = {"k1": k1, "k2": k2, "beta": beta, "amp": amp}
                scale = 5e-5

                if q_type == "boundary_average_displacement":
                    # uy(x, 1) = amp * (cos(k1*pi) + beta*cos(k2*pi)) (constant in x)
                    j_exact = amp * (math.cos(k1 * math.pi) + beta * math.cos(k2 * math.pi))
                else:
                    # int_[0.25, 0.75] ux(x) dx / 0.5
                    ix1 = (math.cos(0.25 * k1 * math.pi) - math.cos(0.75 * k1 * math.pi)) / (k1 * math.pi)
                    ix2 = (math.cos(0.25 * k2 * math.pi) - math.cos(0.75 * k2 * math.pi)) / (k2 * math.pi)
                    j_exact = (amp / 0.5) * (ix1 + beta * ix2)

            cfg = {
                "config_id": f"T1_{cfg_id:02d}",
                "family": fam,
                "family_index": fam_idx + 1,
                "item_index": item_idx,
                "domain": {"x_bounds": [0.0, 1.0], "y_bounds": [0.0, 1.0], "dimension": 2},
                "bvp_specification": {
                    "displacement_field": {"ux": expr_ux, "uy": expr_uy},
                    "body_force": {
                        "fx": fx_expr,
                        "fy": fy_expr,
                        "fx_constant_value": fx_val,
                        "fy_constant_value": fy_val,
                    },
                    "boundary_conditions": {
                        "dirichlet_boundaries": ["bottom (y=0)", "top (y=1)", "left (x=0)", "right (x=1)"],
                        "prescription": "exact_displacement_trace",
                    },
                },
                "parameters": params,
                "constitutive_assumption": assump,
                "material": {"E": E_val, "nu": nu_val},
                "elasticity_tensor": c_dict,
                "qoi": {
                    "type": q_type,
                    "component": "y" if q_type == "boundary_average_displacement" else "x",
                    "scale": scale,
                    "target_region": (
                        "top edge y=1.0, x in [0, 1]"
                        if q_type == "boundary_average_displacement"
                        else "interior patch [0.25, 0.75] x [0.25, 0.75]"
                    ),
                    "exact_analytical_value": float(j_exact),
                    "reference_evaluation_tolerance": 1e-12,
                },
                "initial_mesh": {
                    "type": mesh_type,
                    "seed": seed,
                    "coarse_elements": 32 + 8 * (item_idx % 4),
                },
                "refinement_levels": ["M0", "M1", "M2"] + (["M3"] if is_m3 else []),
                "m3_validation_level": is_m3,
                "verification_mode": "four_grid" if is_m3 else "three_grid",
                "requested_tolerance": tol,
                "tolerance_type": "relative",
                "reference_type": "exact_analytical",
                "applicable_hypotheses": [
                    "H5a_coverage",
                    "H5b_claim_integrity",
                    "H6a_availability",
                    "H6b_sharpness",
                ],
            }
            configs.append(cfg)
            cfg_id += 1

    return configs


def build_tier2_amended2_manifest() -> List[Dict[str, Any]]:
    # 10 configurations with exact Williams characteristic equation roots
    # and closed-form eigenfunction equations
    williams_cases = [
        {
            "config_id": "T2_01",
            "name": "Williams L-Shape Mode-I Corner Notch (Plane Strain)",
            "corner_angle_deg": 270.0,
            "corner_angle_rad": "1.5 * pi",
            "singular_exponent_lambda": 0.544483736782464,
            "stress_singularity_exponent": -0.455516263217536,
            "constitutive_assumption": "plane_strain",
            "material": {"E": 100e9, "nu": 0.30},
            "domain": "L-shaped [-1, 1]^2 \\ ([0, 1] x [-1, 0])",
            "boundary_conditions": {
                "notch_facets": "theta = 0 and theta = 1.5*pi traction-free (Neumann)",
                "exterior_facets": "exact Williams displacement trace (Dirichlet)",
            },
            "qoi": {
                "type": "patch_average_displacement",
                "patch": [-0.75, -0.25, 0.25, 0.75],
                "scale": 1e-11,
            },
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Duffy tensor Gauss-Legendre quadrature (order >= 18) with error <= 0.01 * finest error",
        },
        {
            "config_id": "T2_02",
            "name": "Williams L-Shape Mode-I Corner Notch (Plane Stress)",
            "corner_angle_deg": 270.0,
            "corner_angle_rad": "1.5 * pi",
            "singular_exponent_lambda": 0.544483736782464,
            "stress_singularity_exponent": -0.455516263217536,
            "constitutive_assumption": "plane_stress",
            "material": {"E": 100e9, "nu": 0.30},
            "domain": "L-shaped [-1, 1]^2 \\ ([0, 1] x [-1, 0])",
            "boundary_conditions": {
                "notch_facets": "traction-free notch surfaces",
                "exterior_facets": "exact displacement trace",
            },
            "qoi": {
                "type": "patch_average_displacement",
                "patch": [-0.75, -0.25, 0.25, 0.75],
                "scale": 1e-11,
            },
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_03",
            "name": "Williams Re-entrant Wedge Mode-I 300 deg",
            "corner_angle_deg": 300.0,
            "corner_angle_rad": "5 * pi / 3",
            "singular_exponent_lambda": 0.512221405106197,
            "stress_singularity_exponent": -0.487778594893803,
            "constitutive_assumption": "plane_strain",
            "material": {"E": 120e9, "nu": 0.28},
            "domain": "Wedge domain with 60 deg opening notch",
            "boundary_conditions": {"notch_facets": "traction-free", "exterior": "exact trace"},
            "qoi": {"type": "patch_average_displacement", "patch": [-0.8, -0.3, 0.3, 0.8], "scale": 1e-11},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_04",
            "name": "Williams Re-entrant Wedge Mode-I 315 deg",
            "corner_angle_deg": 315.0,
            "corner_angle_rad": "7 * pi / 4",
            "singular_exponent_lambda": 0.504990924760086,
            "stress_singularity_exponent": -0.495009075239914,
            "constitutive_assumption": "plane_strain",
            "material": {"E": 120e9, "nu": 0.28},
            "domain": "Wedge domain with 45 deg opening notch",
            "boundary_conditions": {"notch_facets": "traction-free", "exterior": "exact trace"},
            "qoi": {"type": "patch_average_displacement", "patch": [-0.8, -0.3, 0.3, 0.8], "scale": 1e-11},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_05",
            "name": "Williams Slit Crack Mode-I 360 deg (Plane Strain)",
            "corner_angle_deg": 360.0,
            "corner_angle_rad": "2 * pi",
            "singular_exponent_lambda": 0.500000000000000,
            "stress_singularity_exponent": -0.500000000000000,
            "constitutive_assumption": "plane_strain",
            "material": {"E": 150e9, "nu": 0.25},
            "domain": "Edge-cracked plate [-1, 1] x [-1, 1] with crack on y=0, x in [-1, 0]",
            "boundary_conditions": {"crack_lips": "traction-free", "exterior": "exact trace"},
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.7, 0.2, 0.7], "scale": 1e-11},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_06",
            "name": "Williams Slit Crack Mode-I 360 deg (Plane Stress)",
            "corner_angle_deg": 360.0,
            "corner_angle_rad": "2 * pi",
            "singular_exponent_lambda": 0.500000000000000,
            "stress_singularity_exponent": -0.500000000000000,
            "constitutive_assumption": "plane_stress",
            "material": {"E": 150e9, "nu": 0.25},
            "domain": "Edge-cracked plate [-1, 1] x [-1, 1] with crack on y=0, x in [-1, 0]",
            "boundary_conditions": {"crack_lips": "traction-free", "exterior": "exact trace"},
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.7, 0.2, 0.7], "scale": 1e-11},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_07",
            "name": "Manufactured Weakly-Singular Field alpha=1.20",
            "alpha": 1.20,
            "stress_singularity_exponent": -0.80,
            "constitutive_assumption": "plane_stress",
            "material": {"E": 200e9, "nu": 0.25},
            "domain": "Unit square [0, 1]^2",
            "bvp_specification": {
                "displacement": "ux = x^1.20, uy = y^1.20",
                "body_force": "fx = -c11 * 1.2 * 0.2 * x^(-0.8), fy = -c11 * 1.2 * 0.2 * y^(-0.8)",
            },
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.6, 0.2, 0.6], "scale": 0.25},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_08",
            "name": "Manufactured Weakly-Singular Field alpha=1.30",
            "alpha": 1.30,
            "stress_singularity_exponent": -0.70,
            "constitutive_assumption": "plane_stress",
            "material": {"E": 200e9, "nu": 0.25},
            "domain": "Unit square [0, 1]^2",
            "bvp_specification": {
                "displacement": "ux = x^1.30, uy = y^1.30",
                "body_force": "fx = -c11 * 1.3 * 0.3 * x^(-0.7), fy = -c11 * 1.3 * 0.3 * y^(-0.7)",
            },
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.6, 0.2, 0.6], "scale": 0.27},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_09",
            "name": "Manufactured Weakly-Singular Field alpha=1.40",
            "alpha": 1.40,
            "stress_singularity_exponent": -0.60,
            "constitutive_assumption": "plane_stress",
            "material": {"E": 200e9, "nu": 0.25},
            "domain": "Unit square [0, 1]^2",
            "bvp_specification": {
                "displacement": "ux = x^1.40, uy = y^1.40",
                "body_force": "fx = -c11 * 1.4 * 0.4 * x^(-0.6), fy = -c11 * 1.4 * 0.4 * y^(-0.6)",
            },
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.6, 0.2, 0.6], "scale": 0.28},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
        {
            "config_id": "T2_10",
            "name": "Manufactured Weakly-Singular Field alpha=1.60",
            "alpha": 1.60,
            "stress_singularity_exponent": -0.40,
            "constitutive_assumption": "plane_strain",
            "material": {"E": 200e9, "nu": 0.30},
            "domain": "Unit square [0, 1]^2",
            "bvp_specification": {
                "displacement": "ux = x^1.60, uy = y^1.60",
                "body_force": "fx = -c11 * 1.6 * 0.6 * x^(-0.4), fy = -c11 * 1.6 * 0.6 * y^(-0.4)",
            },
            "qoi": {"type": "patch_average_displacement", "patch": [0.2, 0.6, 0.2, 0.6], "scale": 0.31},
            "reference_uncertainty_bound": 0.0005,
            "quadrature_requirement": "Order 18 quadrature",
        },
    ]
    return williams_cases


def build_tier3_amended2_manifest() -> List[Dict[str, Any]]:
    # AM2-02: 80 distinct executable test cases (8 per category across all 10 priority categories)
    # Every case has unique meaningful input and maps directly to ProblemAnalyser.evaluate_contract
    categories = [
        ("ill_posed_qoi", 1),
        ("unsupported_qoi", 2),
        ("invalid_geometry", 3),
        ("mesh_quality_failure", 4),
        ("solver_not_converged", 5),
        ("unverified_insufficient_levels", 6),
        ("unverified_difference_below_numerical_floor", 7),
        ("unverified_order", 8),
        ("unverified_non_asymptotic", 9),
        ("reference_uncertain", 10),
    ]

    cases = []
    case_idx = 1

    # Base valid numbers for higher priority bypass
    base_j0, base_j1, base_j2 = 1.04, 1.01, 1.0025  # p_obs = 2.0, d01=0.03, d12=0.0075

    for cat_code, priority in categories:
        for sub_idx in range(8):
            case_id = f"T3_{case_idx:02d}"

            # Default valid arguments
            j0_val, j1_val, j2_val = base_j0, base_j1, base_j2
            j3_val = None
            qoi_spec = {"type": "boundary_average_displacement"}
            geometry_input = True
            min_angle_val = 35.0
            solver_resid_val = 1e-12
            mesh_levels_val = 3
            refinement_ratio_val = 2.0
            ref_uncertainty_val = 0.0001
            v_mode = "three_grid"

            # 1. ill_posed_qoi (singular point stress)
            if cat_code == "ill_posed_qoi":
                coords = [
                    [0.0, 0.0], [0.0, 0.0], [0.5, 0.0], [0.0, 0.5],
                    [0.0, 0.0], [0.25, 0.0], [0.0, 0.0], [0.0, 0.0]
                ][sub_idx]
                qoi_spec = {
                    "type": "point_stress",
                    "location": coords,
                    "is_singular_point": True,
                    "notch_angle_deg": 270.0 - 15.0 * sub_idx,
                }
                desc = f"Singular point stress at re-entrant corner vertex {coords} (notch angle {270.0 - 15.0 * sub_idx} deg)"

            # 2. unsupported_qoi (unsupported functional types)
            elif cat_code == "unsupported_qoi":
                unsupported_types = [
                    "point_displacement",
                    "patch_average_stress",
                    "maximum_boundary_stress",
                    "sif_k1",
                    "j_integral_unregularized",
                    "point_strain",
                    "patch_stress",
                    "unsupported_custom_energy_norm",
                ]
                utype = unsupported_types[sub_idx]
                qoi_spec = {"type": utype, "location": [0.5, 0.5]}
                desc = f"Unsupported functional request of type '{utype}'"

            # 3. invalid_geometry (distinct geometric anomalies)
            elif cat_code == "invalid_geometry":
                geom_types = [
                    {"has_nan": True, "description": "NaN vertex coordinates"},
                    {"has_inf": True, "description": "Inf vertex coordinates"},
                    {"zero_area": True, "description": "Zero-area degenerate element"},
                    {"invalid_topology": True, "description": "Invalid out-of-bounds topology indexing"},
                    {"inverted": True, "description": "Inverted element orientation (det J < 0)"},
                    {"self_intersecting": True, "description": "Self-intersecting boundary polygon"},
                    {"disconnected_nodes": True, "description": "Disconnected floating nodes"},
                    {"degenerate_1d": True, "description": "Zero-thickness 1D degenerate element"},
                ]
                g_anomaly = geom_types[sub_idx]
                geometry_input = g_anomaly
                desc = f"Invalid geometry: {g_anomaly['description']}"

            # 4. mesh_quality_failure (distinct actual minimum angles < 10 deg)
            elif cat_code == "mesh_quality_failure":
                bad_angles = [4.2, 5.5, 6.8, 7.8, 8.5, 9.1, 9.5, 9.8]
                min_angle_val = bad_angles[sub_idx]
                desc = f"Mesh quality violation: minimum interior angle {min_angle_val} deg (< 10.0 deg)"

            # 5. solver_not_converged (distinct residuals > 1e-10)
            elif cat_code == "solver_not_converged":
                bad_resids = [1.5e-6, 3.2e-7, 1.0e-5, 4.8e-8, 2.1e-9, 8.5e-4, 5.0e-2, 1.2e-6]
                solver_resid_val = bad_resids[sub_idx]
                desc = f"Linear solver convergence failure: relative residual {solver_resid_val:.2e} (> 1e-10)"

            # 6. unverified_insufficient_levels (insufficient levels, non-doubling r)
            elif cat_code == "unverified_insufficient_levels":
                level_configs = [
                    {"levels": 1, "r": 2.0, "mode": "three_grid", "desc": "Single coarse grid M0 provided"},
                    {"levels": 2, "r": 2.0, "mode": "three_grid", "desc": "Two mesh levels (M0, M1) provided"},
                    {"levels": 3, "r": 1.5, "mode": "three_grid", "desc": "Refinement ratio r=1.50 != 2.0"},
                    {"levels": 3, "r": 4.0, "mode": "three_grid", "desc": "Missing intermediate level (r=4.0 != 2.0)"},
                    {"levels": 3, "r": 1.75, "mode": "three_grid", "desc": "Non-uniform adaptive refinement r=1.75"},
                    {"levels": 3, "r": 2.0, "mode": "four_grid", "desc": "Four-grid mode requested but J3 omitted"},
                    {"levels": 2, "r": 1.5, "mode": "three_grid", "desc": "Two levels with non-standard ratio r=1.5"},
                    {"levels": 3, "r": 2.5, "mode": "three_grid", "desc": "Non-standard refinement ratio r=2.50"},
                ]
                cfg_item = level_configs[sub_idx]
                mesh_levels_val = cfg_item["levels"]
                refinement_ratio_val = cfg_item["r"]
                v_mode = cfg_item["mode"]
                desc = f"Insufficient grid sequence: {cfg_item['desc']}"

            # 7. unverified_difference_below_numerical_floor (actual sub-floor values)
            elif cat_code == "unverified_difference_below_numerical_floor":
                floor_pairs = [
                    (1.0 + 2.4e-14, 1.0 + 6.0e-15, 1.0),
                    (1.0 + 1.0e-14, 1.0 + 2.5e-15, 1.0),
                    (1.0, 1.0, 1.0),  # machine zero
                    (1.0 + 5.0e-15, 1.0 + 1.2e-15, 1.0),
                    (1.0 + 8.0e-14, 1.0 + 2.0e-14, 1.0),
                    (1.0 + 3.5e-15, 1.0 + 9.0e-16, 1.0),
                    (1.0 + 7.2e-14, 1.0 + 1.8e-14, 1.0),
                    (1.0 + 1.1e-14, 1.0 + 2.8e-15, 1.0),
                ]
                j0_val, j1_val, j2_val = floor_pairs[sub_idx]
                d01_val = j0_val - j1_val
                d12_val = j1_val - j2_val
                desc = f"Sub-floor differences: |d01|={abs(d01_val):.2e}, |d12|={abs(d12_val):.2e} (< 1e-13 m)"

            # 8. unverified_order (actual sequences producing p_obs < 0.5 or > 3.5)
            elif cat_code == "unverified_order":
                # p_obs = log2(q) -> q = 2^p
                orders = [0.25, 0.35, 0.45, 3.80, 4.20, 4.80, 0.15, 5.50]
                p_target = orders[sub_idx]
                q_target = 2.0**p_target
                d12_v = 0.01
                d01_v = q_target * d12_v
                j2_val = 1.0
                j1_val = j2_val + d12_v
                j0_val = j1_val + d01_v
                desc = f"Observed order failure: p_obs = {p_target:.2f} (outside window [0.5, 3.5])"

            # 9. unverified_non_asymptotic (oscillating, diverging, four-grid stability failure)
            elif cat_code == "unverified_non_asymptotic":
                non_asymp_cases = [
                    (1.02, 1.00, 1.01, None, "three_grid", "Oscillating sequence (d01 > 0, d12 < 0)"),
                    (1.01, 1.00, 0.98, None, "three_grid", "Diverging sequence (q = 0.50 < 1.0)"),
                    (1.02, 1.01, 1.00, None, "three_grid", "Stagnant sequence (q = 1.0)"),
                    (0.98, 1.00, 0.99, None, "three_grid", "Oscillating sequence (d01 < 0, d12 > 0)"),
                    (1.005, 1.00, 0.985, None, "three_grid", "Diverging sequence (q = 0.33 < 1.0)"),
                    (1.04, 1.01, 1.0025, 1.0025 + 0.002, "four_grid", "Four-grid mode with non-monotonic M3"),
                    (1.04, 1.01, 1.0025, 1.0025 - 0.00375, "four_grid", "Four-grid mode with delta_p = 1.0 > 0.50"),
                    (1.04, 1.01, 1.0025, 1.0025 - 0.005, "four_grid", "Four-grid mode with delta_p = 1.42 > 0.50"),
                ]
                j0_val, j1_val, j2_val, j3_val, v_mode, na_desc = non_asymp_cases[sub_idx]
                desc = f"Non-asymptotic convergence: {na_desc}"

            # 10. reference_uncertain (reference uncertainty > 0.05% gate)
            elif cat_code == "reference_uncertain":
                ref_uncertainties = [0.0012, 0.0008, 0.0025, 0.0050, 0.0007, 0.0015, 0.0030, 0.0100]
                ref_uncertainty_val = ref_uncertainties[sub_idx]
                desc = f"Reference solution uncertainty {ref_uncertainty_val*100:.2f}% exceeds frozen gate 0.05%"

            case = {
                "case_id": case_id,
                "category": cat_code,
                "priority": priority,
                "sub_index": sub_idx + 1,
                "description": desc,
                "expected_refusal_code": cat_code,
                "expected_contract_issued": False,
                "verification_stage": "ProblemAnalyser.evaluate_contract",
                "test_inputs": {
                    "J0": float(j0_val),
                    "J1": float(j1_val),
                    "J2": float(j2_val),
                    "J3": float(j3_val) if j3_val is not None else None,
                    "qoi_spec": qoi_spec,
                    "geometry": geometry_input,
                    "mesh_min_angle_deg": float(min_angle_val),
                    "solver_relative_residual": float(solver_resid_val),
                    "mesh_levels": mesh_levels_val,
                    "refinement_ratio": refinement_ratio_val,
                    "reference_uncertainty": float(ref_uncertainty_val),
                    "verification_mode": v_mode,
                },
            }
            cases.append(case)
            case_idx += 1

    return cases


def generate_all_amended2_manifests() -> None:
    t1 = build_tier1_amended2_manifest()
    t2 = build_tier2_amended2_manifest()
    t3 = build_tier3_amended2_manifest()

    print(f"Generated Tier 1: {len(t1)} configurations")
    print(f"Generated Tier 2: {len(t2)} configurations")
    print(f"Generated Tier 3: {len(t3)} refusal cases")

    with open(AMEND2_DIR / "tier1_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t1, f, indent=2)
    with open(AMEND2_DIR / "tier2_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t2, f, indent=2)
    with open(AMEND2_DIR / "tier3_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t3, f, indent=2)

    print(f"Successfully saved amended manifests to {AMEND2_DIR}")


if __name__ == "__main__":
    generate_all_amended2_manifests()
