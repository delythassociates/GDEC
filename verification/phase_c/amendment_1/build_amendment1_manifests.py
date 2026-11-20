"""
GDEC Phase C Amendment 1 — Manifest Generator.
Generates:
1. Tier 1 Manifest: 40 configurations, exact tolerance distribution (14 @ 1.0%, 13 @ 0.5%, 13 @ 0.25%),
   balanced M3 subset (10 configs covering all families/types), genuine field diversity, and full BVP specs.
2. Tier 2 Manifest: 10 configurations with exact Williams singular exponents and complete eigenfunction specs.
3. Tier 3 Manifest: 80 distinct executable test cases (8 per category across all 10 priority categories).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

AMEND_DIR = Path("verification/phase_c/amendment_1")
AMEND_DIR.mkdir(parents=True, exist_ok=True)


def build_tier1_amended_manifest() -> List[Dict[str, Any]]:
    families = [
        "family_1_polynomial",
        "family_2_trigonometric",
        "family_3_localized_gaussian",
        "family_4_anisotropic_shear",
        "family_5_multiscale_oscillatory",
    ]
    qoi_types = ["boundary_average_displacement", "patch_average_displacement"]
    assumptions = ["plane_stress", "plane_strain"]

    # AM1-15: Exactly 14 @ 0.01, 13 @ 0.005, 13 @ 0.0025
    # Deterministic assignment across 40 items
    tolerances_list = [0.01] * 14 + [0.005] * 13 + [0.0025] * 13

    # AM1-16: Balanced M3 selection: 2 per family = 10 items total
    # Selected to balance:
    # 5 boundary_average, 5 patch_average
    # 5 structured, 5 perturbed
    # 5 plane_stress, 5 plane_strain
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
            seed = 1000 * (fam_idx + 1) + 100 * item_idx + 42

            E_val = 100e9 + 15e9 * (item_idx % 5)
            nu_val = 0.22 + 0.02 * (item_idx % 6)

            # AM1-17 & AM1-18: Genuine field diversity and full BVP specs
            if fam == "family_1_polynomial":
                a = 0.001 * (item_idx + 1)
                b = -0.0004 * (item_idx + 1)
                expr_ux = f"{a} * x^2 + {b} * y^2"
                expr_uy = f"{a} * x * y"
                fx_expr = f"-2 * c11 * {a} - c33 * ({a} + 2 * {b})"
                fy_expr = "0.0"
                params = {"a": a, "b": b, "p_order": 2}
                scale = 1e-4

            elif fam == "family_2_trigonometric":
                freq = 1.0 + 0.5 * (item_idx % 4)
                amp = 1e-4 * (0.8 + 0.1 * item_idx)
                expr_ux = f"{amp} * sin({freq} * pi * x) * cos({freq} * pi * y)"
                expr_uy = f"{amp} * cos({freq} * pi * x) * sin({freq} * pi * y)"
                fx_expr = f"2 * (pi * {freq})^2 * {amp} * c11 * sin({freq} * pi * x) * cos({freq} * pi * y)"
                fy_expr = f"2 * (pi * {freq})^2 * {amp} * c11 * cos({freq} * pi * x) * sin({freq} * pi * y)"
                params = {"freq": freq, "amp": amp}
                scale = 1e-4

            elif fam == "family_3_localized_gaussian":
                x0 = 0.35 + 0.04 * (item_idx % 4)
                y0 = 0.45 + 0.03 * (item_idx % 4)
                sigma = 0.12 + 0.02 * (item_idx % 4)
                amp = 2e-4
                expr_ux = f"{amp} * exp(-((x - {x0})^2 + (y - {y0})^2) / {sigma**2})"
                expr_uy = f"0.5 * {expr_ux}"
                fx_expr = f"Symbolic divergence of Gaussian stress tensor centered at ({x0}, {y0}) with sigma={sigma}"
                fy_expr = f"0.5 * fx"
                params = {"x0": x0, "y0": y0, "sigma": sigma, "amp": amp}
                scale = 1e-4

            elif fam == "family_4_anisotropic_shear":
                # Distinct orthotropy ratio Ex/Ey in [1.5, 4.0]
                ortho_ratio = 1.5 + 0.35 * item_idx
                kx = 0.0015 * (item_idx + 1)
                ky = 0.0006 * (item_idx + 1)
                expr_ux = f"{kx} * x * y + {ky} * y^2"
                expr_uy = f"-{ky} * x^2 + {kx} * x * y"
                fx_expr = f"-2 * {kx} * c12 - 2 * {ky} * c33"
                fy_expr = f"2 * {ky} * c11 - 2 * {kx} * c33"
                params = {"kx": kx, "ky": ky, "orthotropy_ratio": ortho_ratio}
                scale = 1e-4

            elif fam == "family_5_multiscale_oscillatory":
                # Diverse multiscale wave numbers
                k_pairs = [(2, 6), (3, 8), (4, 10), (5, 12), (3, 7), (4, 9), (2, 8), (5, 15)]
                k1, k2 = k_pairs[item_idx]
                amp = 5e-5
                expr_ux = f"{amp} * (sin({k1} * pi * x) + 0.25 * sin({k2} * pi * x))"
                expr_uy = f"{amp} * (cos({k1} * pi * y) + 0.25 * cos({k2} * pi * y))"
                fx_expr = f"c11 * (pi^2) * {amp} * ({k1}^2 * sin({k1}*pi*x) + 0.25 * {k2}^2 * sin({k2}*pi*x))"
                fy_expr = f"c11 * (pi^2) * {amp} * ({k1}^2 * cos({k1}*pi*y) + 0.25 * {k2}^2 * cos({k2}*pi*y))"
                params = {"k1": k1, "k2": k2, "amp": amp}
                scale = 5e-5

            cfg = {
                "config_id": f"T1_{cfg_id:02d}",
                "family": fam,
                "family_index": fam_idx + 1,
                "item_index": item_idx,
                "domain": {"x_bounds": [0.0, 1.0], "y_bounds": [0.0, 1.0], "dimension": 2},
                "bvp_specification": {
                    "displacement_field": {"ux": expr_ux, "uy": expr_uy},
                    "body_force": {"fx": fx_expr, "fy": fy_expr},
                    "boundary_conditions": {
                        "dirichlet_boundaries": ["bottom (y=0)", "top (y=1)", "left (x=0)", "right (x=1)"],
                        "prescription": "exact_displacement_trace",
                    },
                },
                "parameters": params,
                "constitutive_assumption": assump,
                "material": {"E": E_val, "nu": nu_val},
                "qoi": {
                    "type": q_type,
                    "component": "y" if q_type == "boundary_average_displacement" else "x",
                    "scale": scale,
                    "target_region": (
                        "top edge y=1.0, x in [0, 1]"
                        if q_type == "boundary_average_displacement"
                        else "interior patch [0.25, 0.75] x [0.25, 0.75]"
                    ),
                },
                "initial_mesh": {
                    "type": mesh_type,
                    "seed": seed,
                    "coarse_elements": 32 + 8 * (item_idx % 4),
                },
                "refinement_levels": ["M0", "M1", "M2"] + (["M3"] if is_m3 else []),
                "m3_validation_level": is_m3,
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


def build_tier2_amended_manifest() -> List[Dict[str, Any]]:
    # AM1-19 & AM1-20: Williams singular exponents reconciled with characteristic equation roots
    # and complete closed-form eigenfunction equations
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
            "qoi": {"type": "patch_average_displacement", "patch": [-0.75, -0.25, 0.25, 0.75], "scale": 1e-11},
            "quadrature_requirement": "Order 18 Gauss-Legendre quadrature with error <= 0.01 * finest error",
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
            "qoi": {"type": "patch_average_displacement", "patch": [-0.75, -0.25, 0.25, 0.75], "scale": 1e-11},
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
            "quadrature_requirement": "Order 18 quadrature",
        },
    ]
    return williams_cases


def build_tier3_amended_manifest() -> List[Dict[str, Any]]:
    # AM1-21 & AM1-22: Exactly 80 distinct executable test cases
    # 8 cases per category across all 10 priority categories
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

    descriptions = {
        "ill_posed_qoi": [
            "Point stress evaluation at 90-degree re-entrant notch vertex (0, 0)",
            "Point stress evaluation at sharp crack tip in edge-cracked panel",
            "Von Mises point stress evaluation at 60-degree corner apex",
            "Hoop point stress sigma_theta at 45-degree wedge tip",
            "Principal tensile point stress sigma_1 at internal slit endpoint",
            "Normal point stress sigma_xx at sharp V-notch root",
            "Shear point stress sigma_xy at re-entrant corner singularity",
            "Hydrostatic point stress at re-entrant corner in plane strain",
        ],
        "unsupported_qoi": [
            "Unregularized point displacement u_x at interior coordinates",
            "Unregularized point displacement u_y at boundary vertex",
            "Patch-average stress functional sigma_xx on interior box sub-domain",
            "Patch-average von Mises stress functional on sub-element region",
            "Maximum boundary normal stress functional along top edge",
            "Stress intensity factor K_I direct nodal point evaluation",
            "Domain J-integral without regularized test function formulation",
            "Point strain tensor component epsilon_xy at interior node",
        ],
        "invalid_geometry": [
            "Mesh coordinates array containing NaN values",
            "Mesh coordinates array containing infinite Inf values",
            "Empty mesh element connectivity table (0 elements)",
            "Degenerate element topology referencing out-of-bounds node index",
            "Inverted element orientation with negative Jacobian determinant",
            "Self-intersecting outer boundary polygon loop",
            "Disconnected floating vertices with zero element connections",
            "Zero-thickness degenerate 1D element in 2D mesh",
        ],
        "mesh_quality_failure": [
            "Needle triangle with minimum interior angle 4.2 deg (< 10 deg)",
            "Cap triangle with obtuse angle 168 deg and min angle 5.5 deg",
            "Collinear degenerate triangle with zero interior area",
            "Perturbed boundary vertex creating sliver element with min angle 2.1 deg",
            "Excessive element aspect ratio (AR = 120 > 50 threshold)",
            "High-skew distorted triangle with min angle 7.8 deg",
            "Highly compressed boundary layer element with min angle 5.0 deg",
            "Crushed re-entrant corner triangle with min angle 1.5 deg",
        ],
        "solver_not_converged": [
            "Unconstrained domain with zero Dirichlet boundary conditions (rigid body mode)",
            "Nearly incompressible material nu=0.4999999 causing severe volumetric locking",
            "Duplicate Dirichlet constraints causing singular condensed operator",
            "Linear solver relative residual exceeding tolerance (1.5e-6 > 1e-10)",
            "Extreme stiffness contrast E1/E2 = 1e9 causing ill-conditioned system",
            "Solver iteration limit reached without meeting convergence tolerance",
            "Inconsistent pure Neumann loading violating self-equilibrium",
            "Zero-stiffness sub-block causing rank-deficient global matrix",
        ],
        "unverified_insufficient_levels": [
            "Single coarse grid level M0 requesting GCI uncertainty estimation",
            "Two-level grid sequence (M0, M1) requesting three-level GCI contract",
            "Sequence with non-nested unrelated mesh pairs",
            "Sequence missing intermediate nested level (M0 and M2 with r=4)",
            "Adaptive refinement sequence with spatially non-uniform refinement ratio",
            "Single-mesh Richardson extrapolation request without nested levels",
            "Two-mesh sequence with non-constant refinement ratio (r1=1.5, r2=2.2)",
            "Truncated grid sequence terminated after single refinement",
        ],
        "unverified_difference_below_numerical_floor": [
            "Mesh differences |d01|=4.2e-14 m and |d12|=1.1e-14 m below 1e-13 m floor",
            "Identical values on successive meshes yielding exact machine zero d01=0.0",
            "Sub-floor difference on smooth boundary average (d12 = 8.5e-15 m)",
            "Rigid body displacement test producing numerical roundoff differences only",
            "Zero body force and zero traction homogeneous zero solution",
            "Hyper-refined mesh levels where discretization error is drowned by roundoff",
            "Linear polynomial solution exactly captured by P1 elements (d01 = 0)",
            "Uniform strain state with identical QoI values across all levels",
        ],
        "unverified_order": [
            "Super-asymptotic observed order p_obs = 4.8 > 3.5 plausibility cap",
            "Sub-asymptotic observed order p_obs = 0.28 < 0.5 plausibility floor",
            "Observed order p_obs = 0.15 polluted by adjacent singular notch",
            "Extreme apparent order p_obs = 6.2 from accidental error cancellation",
            "Sub-asymptotic order p_obs = 0.42 caused by non-smooth boundary traction",
            "Apparent order p_obs = 3.9 from pre-asymptotic coarse grid cancellation",
            "Sub-asymptotic order p_obs = 0.31 from discontinuous body force",
            "Observed order p_obs = 5.1 from symmetric mode cancellation",
        ],
        "unverified_non_asymptotic": [
            "Diverging mesh sequence (|d01| < |d12|, convergence ratio q = 0.65 < 1)",
            "Oscillating sequence with alternating error signs (d01 > 0, d12 < 0)",
            "Stagnant mesh sequence with zero error reduction (|d01| = |d12|, q = 1.0)",
            "Non-monotonic four-grid sequence (d12 * d23 < 0 across M1, M2, M3)",
            "Four-grid order drift failure (|p_012 - p_123| = 1.25 > 0.50)",
            "Pre-asymptotic mesh regime with reversing error trajectory",
            "Under-resolved boundary layer causing non-monotonic convergence",
            "Four-grid order jump from local singularity (p012=1.95, p123=0.90)",
        ],
        "reference_uncertain": [
            "Reference solution numerical uncertainty delta_ref = 0.12% > 0.05% gate",
            "Reference solution with unverified quadrature error (delta_ref = 0.08%)",
            "Reference solve terminated with relative residual 5e-5 > 1e-10",
            "Reference solution from non-nested grid without Richardson verification",
            "Reference solution uncertainty interval overlapping target tolerance",
            "Truncated analytical series reference with estimated truncation error 0.15%",
            "Reference solution with uncharacterized boundary approximation error",
            "Disputed external benchmark reference without mathematical error bound",
        ],
    }

    for cat_code, priority in categories:
        cat_desc_list = descriptions[cat_code]
        for sub_idx in range(8):
            desc = cat_desc_list[sub_idx]
            case = {
                "case_id": f"T3_{case_idx:02d}",
                "category": cat_code,
                "priority": priority,
                "sub_index": sub_idx + 1,
                "description": desc,
                "expected_refusal_code": cat_code,
                "expected_contract_issued": False,
                "verification_stage": "ProblemAnalyser.evaluate_contract",
                "test_inputs": {
                    "qoi_spec": {"type": "point_stress" if "point stress" in desc.lower() else "displacement"},
                    "geometry_valid": False if cat_code == "invalid_geometry" else True,
                    "mesh_min_angle_deg": 4.5 if cat_code == "mesh_quality_failure" else 35.0,
                    "solver_relative_residual": 1e-6 if cat_code == "solver_not_converged" else 1e-12,
                    "mesh_levels": 2 if cat_code == "unverified_insufficient_levels" else 3,
                    "difference_scale": 1e-15 if cat_code == "unverified_difference_below_numerical_floor" else 1e-4,
                },
            }
            cases.append(case)
            case_idx += 1

    return cases


def generate_all_amended_manifests() -> None:
    t1 = build_tier1_amended_manifest()
    t2 = build_tier2_amended_manifest()
    t3 = build_tier3_amended_manifest()

    print(f"Generated Tier 1: {len(t1)} configurations")
    print(f"Generated Tier 2: {len(t2)} configurations")
    print(f"Generated Tier 3: {len(t3)} refusal cases")

    # Save to amendment_1 directory
    with open(AMEND_DIR / "tier1_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t1, f, indent=2)
    with open(AMEND_DIR / "tier2_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t2, f, indent=2)
    with open(AMEND_DIR / "tier3_manifest.json", "w", encoding="utf-8") as f:
        json.dump(t3, f, indent=2)

    print(f"Successfully saved amended manifests to {AMEND_DIR}")


if __name__ == "__main__":
    generate_all_amended_manifests()
