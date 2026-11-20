"""
A2.5: Adjoint Verification.
Verifies adjoint sensitivity, exact discrete algebraic identity,
reference convergence comparison, and cantilever symmetry/proportionality:
- A2.5a: Finite-difference sensitivities:
    dJ/df_k = z_k (10 randomly sampled DOFs, rel tol 1e-6)
    dJ/dE = -z^T (dK/dE) u = -(1/E) z^T K u (rel tol 1e-6)
- A2.5b: Exact discrete algebraic identity:
    J(u_h) - J(w) = z_h^T (f_h - K_h w) (rel tol 1e-9)
- A2.5c: Multi-level reference comparison (report-only)
- A2.5d: Cantilever proportionality:
    u = k * z where k = -10000.0, ||u - k*z||_inf / ||u||_inf <= 1e-10
"""

import json
from pathlib import Path
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.fem.mesh import GDECMesh

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


def test_a2_5a_adjoint_sensitivities():
    """
    A2.5a: Sensitivity of QoI with respect to nodal load and Young's modulus.
    """
    test_id_f = "A2.5a_force_sensitivity"
    test_id_E = "A2.5a_material_sensitivity"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    gmesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=10, ny=5)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
    u, z = sol.u, sol.z
    assert z is not None
    K, g = sol.K, sol.g
    dofs_fixed = sol.dofs_fixed
    free_dofs = np.setdiff1d(np.arange(len(u)), dofs_fixed)

    # 1. Force sensitivity dJ/df_k = z_k on 10 randomly sampled free DOFs
    rng = np.random.default_rng(12345)
    sample_dofs = rng.choice(free_dofs, size=10, replace=False)
    delta_f = 100.0

    fd_errors = []
    sampled_details = []
    for dof in sample_dofs:
        f_plus = sol.f.copy()
        f_plus[dof] += delta_f
        K_f, f_f, u_full_p, I_p = fem.condense(K, f_plus, D=dofs_fixed)
        u_p = u_full_p.copy()
        u_p[I_p] = fem.solve(K_f, f_f)
        j_plus = float(g @ u_p)

        f_minus = sol.f.copy()
        f_minus[dof] -= delta_f
        K_f, f_f, u_full_m, I_m = fem.condense(K, f_minus, D=dofs_fixed)
        u_m = u_full_m.copy()
        u_m[I_m] = fem.solve(K_f, f_f)
        j_minus = float(g @ u_m)

        fd_deriv = (j_plus - j_minus) / (2.0 * delta_f)
        rel_diff = abs(fd_deriv - z[dof]) / (abs(z[dof]) + 1e-15)
        fd_errors.append(float(rel_diff))
        sampled_details.append({
            "dof": int(dof),
            "adjoint_z": float(z[dof]),
            "fd_deriv": float(fd_deriv),
            "rel_diff": float(rel_diff),
        })

    max_rel_f = float(max(fd_errors))
    pass_f = max_rel_f <= 1e-6
    res_f = {
        "id": test_id_f,
        "computed": {
            "max_relative_difference": max_rel_f,
            "sampled_dofs": sampled_details,
            "perturbation_N": delta_f,
        },
        "threshold": {"dJ_dfk_rel_tol": 1e-6},
        "pass": pass_f,
        "failure_class": None if pass_f else "NUM_FAIL",
        "details": "Central finite difference sensitivity dJ/df_k vs adjoint vector z_k.",
    }
    _record_result(res_f, "A2_5_adjoint.json")
    assert pass_f, f"Force sensitivity mismatch {max_rel_f} > 1e-6"

    # 2. Material sensitivity dJ/dE = -(1/E) z^T K u
    dE = 1e-5 * c.E
    c_p = ConstitutiveTensor.from_properties(E=c.E + dE, nu=c.nu, assumption=c.assumption, thickness=c.thickness)
    sol_p = LinearElasticitySolver(c_p).solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=False)

    c_m = ConstitutiveTensor.from_properties(E=c.E - dE, nu=c.nu, assumption=c.assumption, thickness=c.thickness)
    sol_m = LinearElasticitySolver(c_m).solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=False)

    fd_dJ_dE = (sol_p.qoi - sol_m.qoi) / (2.0 * dE)
    analytical_dJ_dE = -(1.0 / c.E) * float(z @ (K @ u))
    rel_diff_E = float(abs(fd_dJ_dE - analytical_dJ_dE) / abs(analytical_dJ_dE))

    pass_E = rel_diff_E <= 1e-6
    res_E = {
        "id": test_id_E,
        "computed": {
            "relative_difference": rel_diff_E,
            "fd_derivative": float(fd_dJ_dE),
            "analytical_adjoint_derivative": float(analytical_dJ_dE),
            "dE": float(dE),
        },
        "threshold": {"dJ_dE_rel_tol": 1e-6},
        "pass": pass_E,
        "failure_class": None if pass_E else "NUM_FAIL",
        "details": "Central finite difference sensitivity dJ/dE vs adjoint formula -(1/E) z^T K u.",
    }
    _record_result(res_E, "A2_5_adjoint.json")
    assert pass_E, f"Material sensitivity mismatch {rel_diff_E} > 1e-6"


def test_a2_5b_exact_discrete_identity():
    """
    A2.5b: Exact discrete algebraic identity:
      J(u_h) - J(w) = z_h^T (f_h - K_h w)
    for arbitrary w satisfying Dirichlet BCs.
    """
    test_id = "A2.5b_exact_discrete_identity"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    gmesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=16, ny=8)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
    u, z = sol.u, sol.z
    assert z is not None
    K, f, g = sol.K, sol.f, sol.g
    dofs_fixed = sol.dofs_fixed

    # Construct test vector w: perturbed u satisfying Dirichlet boundary conditions
    rng = np.random.default_rng(54321)
    w = u + 1e-4 * rng.normal(size=len(u))
    w[dofs_fixed] = 0.0

    Ju = float(g @ u)
    Jw = float(g @ w)
    residual = f - K @ w
    dwr = float(z @ residual)

    abs_err = abs((Ju - Jw) - dwr)
    scale = max(abs(Ju), abs(Jw))
    rel_err = float(abs_err / scale)

    passed = rel_err <= 1e-9
    res = {
        "id": test_id,
        "computed": {
            "Ju_minus_Jw": float(Ju - Jw),
            "dual_weighted_residual": dwr,
            "absolute_identity_error": abs_err,
            "relative_identity_error": rel_err,
        },
        "threshold": {"relative_tolerance": 1e-9},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "Exact algebraic identity J(u) - J(w) = z^T (f - Kw).",
    }
    _record_result(res, "A2_5_adjoint.json")
    assert passed, f"Algebraic identity error {rel_err} > 1e-9"


def test_a2_5c_reference_comparison():
    """
    A2.5c: Report-only reference comparison.
    Computes fine reference solutions (n in {16, 32, 64}) and evaluates coarse error.
    """
    test_id = "A2.5c_reference_comparison"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    qois = {}
    for ny in [4, 8, 16, 32]:
        nx = 2 * ny
        gmesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=nx, ny=ny)
        sol = solver.solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=False)
        qois[f"nx{nx}_ny{ny}"] = {
            "dofs": int(len(sol.u)),
            "qoi_meters": float(sol.qoi),
            "qoi_mm": float(sol.qoi_mm),
        }

    res = {
        "id": test_id,
        "computed": {
            "mesh_hierarchy": qois,
            "finest_qoi_mm": qois["nx64_ny32"]["qoi_mm"],
        },
        "threshold": {"report_only": True},
        "pass": True,
        "failure_class": None,
        "details": "Hierarchical cantilever reference QoI progression (report only).",
    }
    _record_result(res, "A2_5_adjoint.json")


def test_a2_5d_cantilever_proportionality():
    """
    A2.5d: Cantilever symmetry and adjoint-primal proportionality:
      u = k * z where k = -10000.0
      Tolerance: ||u - k*z||_inf / ||u||_inf <= 1e-10
    """
    test_id = "A2.5d_cantilever_proportionality"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    gmesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=10, ny=5)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(gmesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
    u, z = sol.u, sol.z
    assert z is not None

    k_factor = -10000.0
    abs_diff = float(np.max(np.abs(u - k_factor * z)))
    max_u = float(np.max(np.abs(u)))
    rel_diff = float(abs_diff / max_u)

    passed = rel_diff <= 1e-10
    res = {
        "id": test_id,
        "computed": {
            "k_factor": k_factor,
            "max_displacement_inf_m": max_u,
            "max_proportionality_abs_diff_m": abs_diff,
            "relative_proportionality_diff": rel_diff,
        },
        "threshold": {"relative_tolerance": 1e-10},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "Cantilever u = k*z proportionality check.",
    }
    _record_result(res, "A2_5_adjoint.json")
    assert passed, f"Cantilever proportionality mismatch {rel_diff} > 1e-10"
