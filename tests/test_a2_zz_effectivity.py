"""
A2.7: ZZ Energy-Norm Effectivity and Goal Indicator Regression.
Verifies:
1. Exact-quadrature energy norm effectivity index of Zienkiewicz-Zhu (ZZ) recovery estimator:
     I_eff = ||sigma* - sigma_h||_E / ||sigma - sigma_h||_E
   on manufactured solution meshes n=64 and n=128.
   Gate: 0.7 <= I_eff <= 1.3 on n=64, 128.
2. Goal indicator algebraic regression:
     eta_e / (h_e^2 * A_e) = |sigma(u) : eps(u)| / |k|
   where k = -10000.0 on both uniform and adapted cantilever meshes.
   Tolerance: relative error <= 1e-10.
"""

import json
from pathlib import Path
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor, FEMSolution
from gdec.fem.mesh import GDECMesh
from gdec.fem.estimators import RefinementEstimator
from verification.mesh_utils import create_structured_mesh

RESULTS_DIR = Path("results/verification")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _record_result(entry: dict, filename: str):
    path = RESULTS_DIR / filename
    results = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            results = []
    results = [r for r in results if r.get("id") != entry.get("id")]
    results.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def get_body_force(x: np.ndarray, y: np.ndarray, c11: float, c12: float, c33: float):
    pi = np.pi
    sin_x, cos_x = np.sin(pi * x), np.cos(pi * x)
    sin_y, cos_y = np.sin(pi * y), np.cos(pi * y)
    ux_val = sin_x * sin_y

    d2ux_dx2 = -pi**2 * ux_val
    d2ux_dy2 = -pi**2 * ux_val
    d2ux_dxdy = pi**2 * cos_x * cos_y

    d2uy_dx2 = 2.0 * y * (1.0 - y) * (-3.0 * x - 2.0 * y)
    d2uy_dy2 = x * (1.0 - x) * (2.0 - 2.0 * x - 12.0 * y)
    d2uy_dxdy = (1.0 - 2.0 * x) * ((1.0 - 2.0 * y) * (1.0 + x + 2.0 * y) + 2.0 * y * (1.0 - y)) + x * (1.0 - x) * (1.0 - 2.0 * y)

    bx = -(c11 * d2ux_dx2 + c12 * d2uy_dxdy + c33 * (d2ux_dy2 + d2uy_dxdy))
    by = -(c33 * (d2ux_dxdy + d2uy_dx2) + c12 * d2ux_dxdy + c11 * d2uy_dy2)
    return bx, by


@pytest.mark.parametrize("n", [64, 128])
def test_a2_7_zz_effectivity_index(n: int):
    test_id = f"A2.7_zz_effectivity_n{n}"

    c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption="plane_stress", thickness=1.0)
    c11, c12, c33 = c.c11, c.c12, c.c33
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    mesh, _ = create_structured_mesh(n)
    gmesh = GDECMesh(mesh, 1.0, 1.0)
    basis_sol = fem.Basis(mesh, solver.element)
    basis_f = fem.Basis(mesh, solver.element, intorder=6)
    basis_err = fem.Basis(mesh, solver.element, intorder=8)

    K = solver.assemble_stiffness(basis_sol)

    @fem.LinearForm
    def bf(v, w):
        bx, by = get_body_force(w.x[0], w.x[1], c11, c12, c33)
        return bx * v[0] + by * v[1]

    f = fem.asm(bf, basis_f)

    dofs = np.concatenate([
        solver.find_dirichlet_dofs(basis_sol, gmesh, b, ["x", "y"])
        for b in ["left", "right", "bottom", "top"]
    ])
    dofs = np.unique(dofs)

    K_free, f_free, u_full, I = fem.condense(K, f, D=dofs)
    u_h = u_full.copy()
    u_h[I] = spla.spsolve(K_free.tocsc(), f_free)

    # Exact energy error
    u_eval = basis_err.interpolate(u_h)

    @fem.Functional
    def en_fn(w):
        x, y = w.x[0], w.x[1]
        pi = np.pi
        eps11_ex = pi * np.cos(pi * x) * np.sin(pi * y)
        eps22_ex = x * (1.0 - x) * ((1.0 - 2.0 * y) * (1.0 + x + 2.0 * y) + 2.0 * y * (1.0 - y))
        gamma12_ex = pi * np.sin(pi * x) * np.cos(pi * y) + y * (1.0 - y) * ((1.0 - 2.0 * x) * (1.0 + x + 2.0 * y) + x * (1.0 - x))

        grad = w["u"].grad
        e11 = eps11_ex - grad[0, 0]
        e22 = eps22_ex - grad[1, 1]
        e12 = 0.5 * gamma12_ex - 0.5 * (grad[0, 1] + grad[1, 0])

        sig11 = c11 * e11 + c12 * e22
        sig22 = c12 * e11 + c11 * e22
        sig12 = 2.0 * c33 * e12
        return sig11 * e11 + sig22 * e22 + 2.0 * sig12 * e12

    exact_energy_err = float(np.sqrt(fem.asm(en_fn, basis_err, u=u_eval)))

    # Production ZZ indicator
    sol_obj = FEMSolution(
        u=u_h, z=None, K=K, f=f, g=np.zeros_like(f), dofs_fixed=dofs, basis=basis_sol, qoi=0.0, qoi_mm=0.0
    )
    ind_res = estimator.compute_zz_recovery_indicator(gmesh, sol_obj)
    eta_zz = float(ind_res.details["total_energy_error"])

    I_eff = float(eta_zz / exact_energy_err)
    passed = bool(0.7 <= I_eff <= 1.3)

    res = {
        "id": test_id,
        "computed": {
            "n": n,
            "dofs": int(basis_sol.N),
            "elements": int(mesh.t.shape[1]),
            "exact_energy_norm_error": exact_energy_err,
            "zz_recovered_energy_error": eta_zz,
            "effectivity_index_I_eff": I_eff,
        },
        "threshold": {
            "min_effectivity": 0.7,
            "max_effectivity": 1.3,
        },
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": f"ZZ energy norm effectivity index on n={n} structured mesh.",
    }
    _record_result(res, "A2_7_zz_effectivity.json")

    assert passed, f"ZZ effectivity {I_eff} out of bounds [0.7, 1.3] for n={n}"


@pytest.mark.parametrize("mesh_case", ["uniform_cantilever", "adapted_cantilever"])
def test_a2_7_goal_indicator_regression(mesh_case: str):
    test_id = f"A2.7_goal_regression_{mesh_case}"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    gmesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, 9, 5)
    if mesh_case == "adapted_cantilever":
        gmesh = gmesh.refine_elements(np.array([0, 1, 2, 3, 4]))

    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]
    sol = solver.solve(gmesh, loads, bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)

    ind_res = estimator.compute_goal_aware_indicator(gmesh, sol, cost_aware=False)
    eta = ind_res.indicators

    # LHS: eta_e / (h_e^2 * A_e)
    he = gmesh.element_diameters
    Ae = gmesh.element_areas
    ratio_lhs = eta / (he**2 * Ae)

    # RHS: |sigma(u) : eps(u)| / |k|
    eps_u, sig_u = estimator.compute_element_strains_and_stresses(gmesh, sol, sol.u)
    inner_prod = sig_u[0] * eps_u[0] + sig_u[1] * eps_u[1] + sig_u[2] * eps_u[2]
    k_factor = -10000.0
    ratio_rhs = np.abs(inner_prod) / abs(k_factor)

    max_rhs = float(np.max(np.abs(ratio_rhs)))
    abs_diff = float(np.max(np.abs(ratio_lhs - ratio_rhs)))
    rel_diff = float(abs_diff / max_rhs)

    passed = bool(rel_diff <= 1e-10)
    res = {
        "id": test_id,
        "computed": {
            "mesh_case": mesh_case,
            "elements": int(gmesh.nelements),
            "max_abs_difference": abs_diff,
            "relative_difference": rel_diff,
            "k_factor": k_factor,
        },
        "threshold": {"relative_tolerance": 1e-10},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": f"Goal indicator algebraic identity regression for {mesh_case}.",
    }
    _record_result(res, "A2_7_zz_effectivity.json")

    assert passed, f"Goal indicator regression failed {rel_diff} > 1e-10 on {mesh_case}"
