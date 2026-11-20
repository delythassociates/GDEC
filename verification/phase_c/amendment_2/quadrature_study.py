"""
GDEC Phase C Amendment 2 — Multi-Order Quadrature Convergence Audit.
Remediates AM2-06:
Implements a systematic exploratory quadrature study on Case B using:
- Order 14 (algebraic degree 13, 7 1D Gauss points -> 49 2D points)
- Order 18 (algebraic degree 17, 9 1D Gauss points -> 81 2D points)
- Order 22 (algebraic degree 21, 11 1D Gauss points -> 121 2D points)
- Order 26 (algebraic degree 25, 13 1D Gauss points -> 169 2D points)
Evaluates consecutive sensitivities:
delta_14_18 = |J_14 - J_18|
delta_18_22 = |J_18 - J_22|
delta_22_26 = |J_22 - J_26|
Demonstrates geometric convergence and bounds residual quadrature error below 1.0% of E_smallest.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))

from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from verification.phase_c.pilot_benchmarks import case_b_displacement_field, case_b_body_force


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

    # Invariant patch domain [0.2, 0.6] x [0.2, 0.6]
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


def run_quadrature_convergence_study() -> Dict[str, Any]:
    alpha = 1.40
    j_exact = float((0.6 ** (alpha + 1.0) - 0.2 ** (alpha + 1.0)) / ((alpha + 1.0) * 0.4))
    e_smallest_m3 = 5.2849e-5  # Discretisation error on level M3

    # Mesh hierarchy
    m0 = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 6), np.linspace(0.0, 1.0, 6)).oriented()
    m1 = m0.refined()
    m2 = m1.refined()

    orders_spec = [
        {"name": "Order 14", "n_1d": 7, "deg": 13, "points": 49},
        {"name": "Order 18", "n_1d": 9, "deg": 17, "points": 81},
        {"name": "Order 22", "n_1d": 11, "deg": 21, "points": 121},
        {"name": "Order 26", "n_1d": 13, "deg": 25, "points": 169},
    ]

    print("=== Executing Multi-Order Quadrature Convergence Study (Case B) ===")

    study_results: Dict[str, Any] = {
        "j_exact": j_exact,
        "e_smallest_m3": e_smallest_m3,
        "mesh_evaluations": {},
    }

    for mesh_name, mesh_obj in [("M1", m1), ("M2", m2)]:
        print(f"\n--- Mesh Level {mesh_name} ({mesh_obj.nelements} elements) ---")
        j_by_order = {}
        for spec in orders_spec:
            j = solve_case_b_with_quadrature(mesh_obj, alpha=alpha, n_1d=spec["n_1d"])
            j_by_order[spec["name"]] = j
            print(f"  {spec['name']} ({spec['points']} pts): J = {j:.12f}")

        j14 = j_by_order["Order 14"]
        j18 = j_by_order["Order 18"]
        j22 = j_by_order["Order 22"]
        j26 = j_by_order["Order 26"]

        delta_14_18 = float(abs(j14 - j18))
        delta_18_22 = float(abs(j18 - j22))
        delta_22_26 = float(abs(j22 - j26))

        ratio_1 = float(delta_18_22 / delta_14_18) if delta_14_18 > 0 else 0.0
        ratio_2 = float(delta_22_26 / delta_18_22) if delta_18_22 > 0 else 0.0

        quad_error_estimate = delta_22_26
        error_ratio_against_m3 = float(quad_error_estimate / e_smallest_m3)
        target_met = bool(error_ratio_against_m3 <= 0.010)

        print(f"  delta_14_18 = {delta_14_18:.4e}")
        print(f"  delta_18_22 = {delta_18_22:.4e} (ratio: {ratio_1:.4f})")
        print(f"  delta_22_26 = {delta_22_26:.4e} (ratio: {ratio_2:.4f})")
        print(f"  E_quad / E_smallest = {error_ratio_against_m3:.4e} (<= 0.010: {target_met})")

        study_results["mesh_evaluations"][mesh_name] = {
            "elements": int(mesh_obj.nelements),
            "j_values": j_by_order,
            "delta_14_18": delta_14_18,
            "delta_18_22": delta_18_22,
            "delta_22_26": delta_22_26,
            "convergence_ratio_1": ratio_1,
            "convergence_ratio_2": ratio_2,
            "is_monotonically_converging": bool(delta_14_18 > delta_18_22 > delta_22_26),
            "quad_error_estimate": quad_error_estimate,
            "error_ratio_against_m3": error_ratio_against_m3,
            "target_met_le_1pct": target_met,
        }

    out_dir = Path("results/phase_c_amendment_2")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "quadrature_study_results.json", "w", encoding="utf-8") as f:
        json.dump(study_results, f, indent=2)

    print(f"\nSaved quadrature study results to {out_dir / 'quadrature_study_results.json'}")
    return study_results


if __name__ == "__main__":
    run_quadrature_convergence_study()
