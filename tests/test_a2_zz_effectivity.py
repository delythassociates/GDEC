"""
A2.7: ZZ Energy-Norm Effectivity and Goal Indicator Regression.
Verifies:
1. Exact-quadrature energy norm effectivity index of Zienkiewicz-Zhu (ZZ) recovery estimator:
     I_op = ||sigma* - sigma_h||_E / ||sigma - sigma_h||_E
   evaluated via independent 3-point midpoint triangle quadrature (exact for degree <= 2).
   Gated: 0.7 <= I_op <= 1.3 on finest structured levels n=64, 128.
   Report-only: all levels, perturbed meshes, I_impl, R_impl/op, plain-L2 diagnostic.
2. Unit test verifying exact quadratic polynomial integration over reference triangle.
3. Goal indicator algebraic regression:
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
from verification.mesh_utils import create_structured_mesh, create_perturbed_mesh
from verification.zz_quadrature import (
    verify_midpoint_quadrature_precision,
    compute_independent_exact_zz_operator,
)
from tests.test_a2_manufactured_solution import get_analytical_body_force

RESULTS_DIR = Path("results/phase_a_completion")
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


def test_a2_7_midpoint_quadrature_exactness():
    """Unit test: verify exact integration of known quadratic polynomial over reference triangle."""
    test_id = "A2.7_quadrature_unit_test"
    err = verify_midpoint_quadrature_precision()
    passed = err <= 1e-14
    res = {
        "id": test_id,
        "computed": {
            "quadratic_polynomial_integration_abs_error": err,
            "quadrature_rule": "3-point edge midpoint rule on triangle",
            "algebraic_precision_degree": 2,
        },
        "threshold": {"absolute_error_tol": 1e-14},
        "pass": passed,
        "failure_class": None if passed else "IMPL_DEFECT",
        "details": "Unit test verifying exact degree-2 triangle quadrature.",
    }
    _record_result(res, "A2_7_zz_effectivity.json")
    assert passed, f"Quadrature unit test failed with error {err}"


def _compute_exact_energy_error(mesh: fem.MeshTri, u_h: np.ndarray, c: ConstitutiveTensor) -> float:
    c11, c12, c33 = c.c11, c.c12, c.c33
    basis_err = fem.Basis(mesh, fem.ElementVector(fem.ElementTriP1()), intorder=8)
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

    return float(np.sqrt(fem.asm(en_fn, basis_err, u=u_eval)))


@pytest.mark.parametrize("mtype", ["structured", "perturbed"])
@pytest.mark.parametrize("plane_type", ["plane_stress", "plane_strain"])
@pytest.mark.parametrize("n", [8, 16, 32, 64, 128])
def test_a2_7_zz_effectivity_evaluation(mtype: str, plane_type: str, n: int):
    is_gated = (mtype == "structured" and n in [64, 128])
    test_id = f"A2.7_zz_effectivity_{mtype}_{plane_type}_n{n}"

    c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption=plane_type, thickness=1.0)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    if mtype == "structured":
        mesh, _ = create_structured_mesh(n)
    else:
        mesh, _ = create_perturbed_mesh(n, seed=12345)

    gmesh = GDECMesh(mesh, 1.0, 1.0)
    basis_sol = fem.Basis(mesh, solver.element)
    basis_force = fem.Basis(mesh, solver.element, intorder=6)

    K = solver.assemble_stiffness(basis_sol)

    @fem.LinearForm
    def bf(v, w):
        bx, by = get_analytical_body_force(w.x[0], w.x[1], c.c11, c.c12, c.c33)
        return bx * v[0] + by * v[1]

    f = fem.asm(bf, basis_force)

    dofs = np.concatenate([
        solver.find_dirichlet_dofs(basis_sol, gmesh, b, ["x", "y"])
        for b in ["left", "right", "bottom", "top"]
    ])
    dofs = np.unique(dofs)

    K_free, f_free, u_full, I = fem.condense(K, f, D=dofs)
    u_h = u_full.copy()
    u_h[I] = spla.spsolve(K_free.tocsc(), f_free)

    # 1. Exact manufactured energy error
    exact_energy_err = _compute_exact_energy_error(mesh, u_h, c)

    # 2. Production solution object and element stresses
    sol_obj = FEMSolution(
        u=u_h, z=None, K=K, f=f, g=np.zeros_like(f), dofs_fixed=dofs, basis=basis_sol, qoi=0.0, qoi_mm=0.0
    )
    _, element_stresses = estimator.compute_element_strains_and_stresses(gmesh, sol_obj, u_h)

    # 3. Independent exact-quadrature ZZ operator
    zz_op = compute_independent_exact_zz_operator(
        points=mesh.p,
        triangles=mesh.t,
        element_areas=gmesh.element_areas,
        element_stresses=element_stresses,
        compliance_3x3=c.compliance_3x3,
        thickness=c.thickness,
    )

    eta_op_total = zz_op["total_energy_error_op"]
    eta_impl_total = zz_op["total_energy_error_impl"]
    eta_l2_total = zz_op["total_l2_stress_error"]

    I_op = float(eta_op_total / exact_energy_err)
    I_impl = float(eta_impl_total / exact_energy_err)
    R_ratio = float(eta_impl_total / eta_op_total)

    passed_gate = bool(0.7 <= I_op <= 1.3) if is_gated else None
    fail_class = None if (not is_gated or passed_gate) else "NUM_FAIL"

    res = {
        "id": test_id,
        "computed": {
            "n": n,
            "mesh_type": mtype,
            "plane_type": plane_type,
            "dofs": int(basis_sol.N),
            "elements": int(mesh.t.shape[1]),
            "exact_energy_norm_error": exact_energy_err,
            "exact_quadrature_zz_error_op": eta_op_total,
            "production_zz_error_impl": eta_impl_total,
            "plain_l2_stress_error_diagnostic": eta_l2_total,
            "effectivity_index_I_op": I_op,
            "effectivity_index_I_impl": I_impl,
            "ratio_impl_to_op_R": R_ratio,
            "classification": "GATED_CRITERION" if is_gated else "DIAGNOSTIC_ONLY",
        },
        "threshold": {
            "exact_quadrature_bounds": [0.7, 1.3] if is_gated else "REPORT_ONLY",
        },
        "pass": passed_gate if is_gated else None,
        "failure_class": fail_class,
        "details": f"ZZ effectivity on {mtype} mesh ({plane_type}) n={n} (Gated: {is_gated}).",
    }
    _record_result(res, "A2_7_zz_effectivity.json")

    if is_gated:
        assert passed_gate, f"Exact-quadrature effectivity {I_op} out of bounds [0.7, 1.3] on {mtype} n={n}"


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
            "classification": "GATED_CRITERION",
        },
        "threshold": {"relative_tolerance": 1e-10},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": f"Goal indicator algebraic identity regression for {mesh_case}.",
    }
    _record_result(res, "A2_7_zz_effectivity.json")

    assert passed, f"Goal indicator regression failed {rel_diff} > 1e-10 on {mesh_case}"
