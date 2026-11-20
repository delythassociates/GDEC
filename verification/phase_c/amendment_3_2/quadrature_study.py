"""
GDEC Phase C Amendment 3.2 — Multi-Order Quadrature Study & Strict Zero-Difference Handling.
Remediates AM32-04:
1. Eliminates unjustified zero-difference convergence: a plateau to zero differences is accepted ONLY
   when earlier differences are also consistent with a documented machine precision floor (<= 1e-12).
   A large earlier jump followed by zeros returns INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.
2. Designates empirical tail estimate strictly as EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE.
3. Produces canonical machine-readable results/phase_c_amendment_3_2/quadrature_study_results.json
   serving as the single source of truth for reports.
4. Preserves the frozen 1.0% residual quadrature threshold.
"""

from enum import Enum
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementTriP1, ElementVector

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))

from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from verification.phase_c.pilot_benchmarks import case_b_body_force, case_b_displacement_field


class QuadratureConvergenceStatus(str, Enum):
    CONVERGED_GEOMETRIC = "CONVERGED_GEOMETRIC"
    PASSED_MACHINE_PRECISION = "PASSED_MACHINE_PRECISION"
    CONVERGED_PRECISION_FLOOR = "CONVERGED_PRECISION_FLOOR"
    NON_GEOMETRIC_CONVERGENCE = "NON_GEOMETRIC_CONVERGENCE"
    FAILED_NON_GEOMETRIC = "FAILED_NON_GEOMETRIC"
    INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE = "INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE"
    INCOMPLETE_ZERO_DENOMINATOR = "INCOMPLETE_ZERO_DENOMINATOR"
    FAILED_NON_FINITE = "FAILED_NON_FINITE"
    FAILED_THRESHOLD_EXCEEDED = "FAILED_THRESHOLD_EXCEEDED"
    EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE = "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE"


def duffy_triangle_quadrature(n_1d: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generates tensor Gauss-Legendre quadrature mapped to reference triangle via Duffy transform."""
    x1, w1 = np.polynomial.legendre.leggauss(n_1d)
    x1 = 0.5 * (x1 + 1.0)
    w1 = 0.5 * w1
    xi, eta = np.meshgrid(x1, x1, indexing="ij")
    w_xi, w_eta = np.meshgrid(w1, w1, indexing="ij")
    u = xi.ravel()
    v = ((1.0 - xi) * eta).ravel()
    weights = (w_xi * w_eta * (1.0 - xi)).ravel()
    return u, v, weights


def solve_case_b_with_quadrature(
    mesh: fem.MeshTri, alpha: float = 1.40, n_1d: int = 9
) -> float:
    c = ConstitutiveTensor.from_properties(E=200e9, nu=0.25, assumption="plane_stress")
    solver = LinearElasticitySolver(c)

    u_q, v_q, w_q = duffy_triangle_quadrature(n_1d)
    pts = np.vstack([u_q, v_q])
    quad = (pts, w_q)

    basis = Basis(mesh, ElementVector(ElementTriP1()), quadrature=quad)
    K = solver.assemble_stiffness(basis)

    @fem.LinearForm
    def body_f(v, w):
        fx, fy = case_b_body_force(w.x[0], w.x[1], c, alpha=alpha)
        return fx * v[0] + fy * v[1]

    f = fem.asm(body_f, basis)

    boundary_nodes = mesh.boundary_nodes()
    dirichlet_dofs = []
    u_exact_d = np.zeros(basis.N)
    for n in boundary_nodes:
        x_n = basis.doflocs[0, 2 * n]
        y_n = basis.doflocs[1, 2 * n]
        ux, uy = case_b_displacement_field(np.array([x_n]), np.array([y_n]), alpha=alpha)
        dirichlet_dofs.extend([2 * n, 2 * n + 1])
        u_exact_d[2 * n] = ux[0]
        u_exact_d[2 * n + 1] = uy[0]

    D = np.unique(np.array(dirichlet_dofs, dtype=int))
    I = np.setdiff1d(np.arange(basis.N), D)
    K_c, f_c, u_full, _ = fem.condense(K, f, x=u_exact_d, D=D)
    u = u_full.copy()
    u[I] = spla.spsolve(K_c.tocsc(), f_c)

    mid = np.mean(mesh.p[:, mesh.t], axis=1)
    mask = (
        (mid[0] > 0.2 - 1e-6)
        & (mid[0] < 0.6 + 1e-6)
        & (mid[1] > 0.2 - 1e-6)
        & (mid[1] < 0.6 + 1e-6)
    )
    p_elems = np.where(mask)[0]
    b_p = Basis(mesh, basis.elem, elements=p_elems, quadrature=quad)

    @fem.LinearForm
    def p_avg(v, w):
        return (1.0 / 0.16) * v[0]

    j_val = float(fem.asm(p_avg, b_p) @ u)
    return j_val


def assess_quadrature_convergence(
    j14: float,
    j18: float,
    j22: float,
    j26: float,
    e_smallest_spatial: float,
    threshold_ratio: float = 0.010,
    precision_floor: float = 1e-12,
) -> Dict[str, Any]:
    """
    Evaluates multi-order quadrature sensitivity convergence (AM31-03, AM32-04).
    Enforces strict zero-difference handling and fail-closed non-geometric semantics.
    """
    vals = [j14, j18, j22, j26, e_smallest_spatial]
    if any(not np.isfinite(v) for v in vals):
        return {
            "status": "FAILED_NON_FINITE",
            "is_geometric_convergence": False,
            "rho": None,
            "tail_error_estimate": None,
            "ratio_to_spatial_error": None,
            "passes_verification": False,
            "failure_reason": "One or more quadrature evaluations or spatial error values are non-finite (NaN/Inf).",
            "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
        }

    d14_18 = abs(j14 - j18)
    d18_22 = abs(j18 - j22)
    d22_26 = abs(j22 - j26)

    # 1. Zero-Difference Handling (AM32-04)
    if d22_26 == 0.0 and d18_22 == 0.0:
        # Preceding difference must also be consistent with machine precision floor
        if d14_18 <= precision_floor:
            # Entire sequence has plateaued at numerical precision floor
            tail_est = precision_floor
            ratio = tail_est / e_smallest_spatial if e_smallest_spatial > 0 else 0.0
            passes = bool(ratio <= threshold_ratio)
            return {
                "status": QuadratureConvergenceStatus.PASSED_MACHINE_PRECISION.value if passes else QuadratureConvergenceStatus.FAILED_THRESHOLD_EXCEEDED.value,
                "is_geometric_convergence": True,
                "rho": 0.0,
                "tail_error_estimate": tail_est,
                "ratio_to_spatial_error": ratio,
                "passes_verification": passes,
                "failure_reason": None if passes else f"Precision floor tail ratio {ratio:.4e} exceeds threshold {threshold_ratio:.4e}.",
                "nature_of_estimate": "precision_floor_bounded",
            }
        else:
            # Earlier difference is large; plateau to zero differences indicates stalled or unjustified convergence
            return {
                "status": QuadratureConvergenceStatus.INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.value,
                "is_geometric_convergence": False,
                "rho": None,
                "tail_error_estimate": None,
                "ratio_to_spatial_error": None,
                "passes_verification": False,
                "failure_reason": f"Preceding difference d14_18={d14_18:.4e} exceeds precision floor while subsequent differences are zero; precision floor not established.",
                "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
            }

    # 2. Strict Zero Denominator Check
    if d18_22 <= 0.0:
        return {
            "status": QuadratureConvergenceStatus.INCOMPLETE_ZERO_DENOMINATOR.value,
            "is_geometric_convergence": False,
            "rho": None,
            "tail_error_estimate": None,
            "ratio_to_spatial_error": None,
            "passes_verification": False,
            "failure_reason": f"Zero or non-positive intermediate sensitivity difference (d18_22={d18_22:.3e}); decay ratio cannot be evaluated.",
            "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
        }

    # 3. Strict Geometric Monotonic Decay: d14_18 > d18_22 > d22_26 > 0
    if not (d14_18 > d18_22 > d22_26 > 0.0):
        return {
            "status": QuadratureConvergenceStatus.NON_GEOMETRIC_CONVERGENCE.value,
            "is_geometric_convergence": False,
            "rho": None,
            "tail_error_estimate": None,
            "ratio_to_spatial_error": None,
            "passes_verification": False,
            "failure_reason": f"Quadrature sensitivities do not decrease monotonically (d14_18={d14_18:.3e}, d18_22={d18_22:.3e}, d22_26={d22_26:.3e}).",
            "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
        }

    rho = d22_26 / d18_22
    if rho >= 1.0 or rho <= 0.0:
        return {
            "status": QuadratureConvergenceStatus.NON_GEOMETRIC_CONVERGENCE.value,
            "is_geometric_convergence": False,
            "rho": rho,
            "tail_error_estimate": None,
            "ratio_to_spatial_error": None,
            "passes_verification": False,
            "failure_reason": f"Observed decay ratio rho={rho:.4f} is outside the geometric decay regime (0, 1).",
            "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
        }

    e_tail = d22_26 / (1.0 - rho)
    ratio = e_tail / e_smallest_spatial if e_smallest_spatial > 0 else float("inf")
    passes = bool(ratio <= threshold_ratio)

    return {
        "status": QuadratureConvergenceStatus.CONVERGED_GEOMETRIC.value if passes else QuadratureConvergenceStatus.FAILED_THRESHOLD_EXCEEDED.value,
        "is_geometric_convergence": True,
        "rho": rho,
        "tail_error_estimate": e_tail,
        "ratio_to_spatial_error": ratio,
        "passes_verification": passes,
        "failure_reason": None if passes else f"Residual quadrature tail ratio ({ratio:.4e}) exceeds frozen threshold ({threshold_ratio:.4e}).",
        "nature_of_estimate": "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE",
    }


def run_case_b_study() -> Dict[str, Any]:
    """Executes dynamic multi-order quadrature study on Case B across M0-M3."""
    alpha = 1.40
    # Exact analytical QoI on [0.2, 0.6]^2:
    # J_exact = int_{0.2}^{0.6} int_{0.2}^{0.6} x^alpha dx dy / 0.16 = (0.6^2.4 - 0.2^2.4) / (2.4 * 0.4)
    j_exact = float((0.6 ** 2.4 - 0.2 ** 2.4) / (2.4 * 0.4))

    m0 = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 6), np.linspace(0.0, 1.0, 6)).oriented()
    m1 = m0.refined()
    m2 = m1.refined()
    m3 = m2.refined()

    orders = [
        ("Order 14", 7),
        ("Order 18", 9),
        ("Order 22", 11),
        ("Order 26", 13),
    ]

    # Compute M3 order 26 baseline
    j_m3_26 = solve_case_b_with_quadrature(m3, alpha=alpha, n_1d=13)
    e_smallest_m3 = abs(j_m3_26 - j_exact)

    mesh_dict = {"M1": m1, "M2": m2, "M3": m3}
    levels_results = {}
    all_levels_pass = True

    for lvl_name, mesh in mesh_dict.items():
        qois = {}
        for ord_name, n_1d in orders:
            val = solve_case_b_with_quadrature(mesh, alpha=alpha, n_1d=n_1d)
            qois[ord_name] = val

        d14_18 = abs(qois["Order 14"] - qois["Order 18"])
        d18_22 = abs(qois["Order 18"] - qois["Order 22"])
        d22_26 = abs(qois["Order 22"] - qois["Order 26"])

        assess = assess_quadrature_convergence(
            qois["Order 14"],
            qois["Order 18"],
            qois["Order 22"],
            qois["Order 26"],
            e_smallest_spatial=e_smallest_m3,
        )

        if not assess["passes_verification"]:
            all_levels_pass = False

        levels_results[lvl_name] = {
            "element_count": mesh.t.shape[1],
            "node_count": mesh.p.shape[1],
            "qoi_by_order": qois,
            "sensitivities": {
                "delta_14_18": d14_18,
                "delta_18_22": d18_22,
                "delta_22_26": d22_26,
            },
            "convergence_assessment": assess,
        }

    results = {
        "benchmark": "Case B — Singular Elasticity MMS",
        "exact_qoi": j_exact,
        "m3_reference": {
            "element_count": m3.t.shape[1],
            "node_count": m3.p.shape[1],
            "qoi_order_26": j_m3_26,
            "e_smallest_m3": e_smallest_m3,
            "provenance": "dynamically_computed_order26",
        },
        "mesh_levels": levels_results,
        "acceptance_criteria": {
            "residual_quadrature_ratio_threshold": 0.010,
            "geometric_convergence_required": True,
            "fail_closed_on_non_geometric": True,
        },
        "all_levels_verified": all_levels_pass,
    }
    return results


def main():
    res = run_case_b_study()
    out_dir = Path("results/phase_c_amendment_3_2")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "quadrature_study_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"Case B Quadrature Study completed. Written to {out_file}.")
    print(f"Exact QoI: {res['exact_qoi']:.16f}")
    print(f"M3 Error: {res['m3_reference']['e_smallest_m3']:.6e}")
    m3_assess = res["mesh_levels"]["M3"]["convergence_assessment"]
    print(f"M3 Tail Ratio: {m3_assess['ratio_to_spatial_error']:.6e} ({m3_assess['status']})")
    print(f"All Levels Verified: {res['all_levels_verified']}")


if __name__ == "__main__":
    main()
