"""
A2.5: Adjoint Verification.
Verifies adjoint sensitivity, exact discrete algebraic identity on nested meshes,
reference convergence comparison, and cantilever symmetry/proportionality:
- A2.5a: Finite-difference sensitivities:
    dJ/df_k = z_k (10 randomly sampled DOFs, seed 42, rel tol 1e-6)
    dJ/dE = -z^T (dK/dE) u = -(1/E) z^T K u (rel tol 1e-6)
- A2.5b: Exact discrete algebraic identity:
    J(u_h) - J(w) = z_h^T (f_h - K_h w) (rel tol 1e-9)
    Tested on:
      1) manufactured_J1 with w1 = P u_H and w2 = random admissible (seed 9999)
      2) boundary_average_displacement with w1 = P u_H and w2 = random admissible (seed 9999)
- A2.5c: Multi-level reference comparison (report-only, DIAGNOSTIC_ONLY, pass: None)
- A2.5d: Cantilever proportionality:
    u = k * z where k = -10000.0, ||u - k*z||_inf / ||u||_inf <= 1e-10
"""

import json
from pathlib import Path
from typing import Tuple
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.fem.mesh import GDECMesh

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


def _build_prolongation_matrix(coarse_mesh: fem.MeshTri, fine_mesh: fem.MeshTri) -> sp.csr_matrix:
    """
    Construct prolongation matrix P: 2*Nf x 2*Nc mapping coarse P1 displacement to fine P1 displacement.
    MeshTri.refined() appends edge midpoints corresponding to coarse_mesh.facets in order.
    """
    Nc = coarse_mesh.p.shape[1]
    Nf = fine_mesh.p.shape[1]

    rows, cols, vals = [], [], []
    for i in range(Nc):
        for comp in (0, 1):
            rows.append(2 * i + comp)
            cols.append(2 * i + comp)
            vals.append(1.0)

    for k in range(coarse_mesh.facets.shape[1]):
        n1, n2 = coarse_mesh.facets[0, k], coarse_mesh.facets[1, k]
        fine_node = Nc + k
        for comp in (0, 1):
            rows.extend([2 * fine_node + comp, 2 * fine_node + comp])
            cols.extend([2 * n1 + comp, 2 * n2 + comp])
            vals.extend([0.5, 0.5])

    return sp.csr_matrix((vals, (rows, cols)), shape=(2 * Nf, 2 * Nc))


def test_a2_5a_adjoint_sensitivities():
    """
    A2.5a: Sensitivity of QoI with respect to nodal load and Young's modulus.
    Uses seed 42 as preregistered in environment manifest.
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

    # 1. Force sensitivity dJ/df_k = z_k on 10 randomly sampled free DOFs (seed 42)
    rng = np.random.default_rng(42)
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
        "details": "Central finite difference sensitivity dJ/df_k vs adjoint vector z_k (seed 42).",
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


@pytest.mark.parametrize("qoi_type", ["manufactured_J1", "boundary_average_displacement"])
def test_a2_5b_exact_discrete_identity(qoi_type: str):
    """
    A2.5b: Exact discrete algebraic identity:
      J(u_h) - J(w) = z_h^T (f_h - K_h w)
    Evaluated with nested coarse-to-fine refinement (n=8 -> 16), testing:
      1) w_1 = P u_H (prolonged coarse solution)
      2) w_2 = random admissible displacement (seed 9999)
    for both manufactured J1 and boundary-average displacement QoIs.
    """
    test_id = f"A2.5b_exact_discrete_identity_{qoi_type}"

    if qoi_type == "manufactured_J1":
        c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption="plane_stress", thickness=1.0)
        c11, c12, c33 = c.c11, c.c12, c.c33
        solver = LinearElasticitySolver(c)

        mesh_c = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 9), np.linspace(0.0, 1.0, 9))
        mesh_f = mesh_c.refined()
        gmesh_c = GDECMesh(mesh_c, width=1.0, height=1.0)
        gmesh_f = GDECMesh(mesh_f, width=1.0, height=1.0)

        basis_c = Basis(mesh_c, ElementVector(ElementTriP1()))
        basis_f = Basis(mesh_f, ElementVector(ElementTriP1()))

        P = _build_prolongation_matrix(mesh_c, mesh_f)

        def get_bf(basis):
            @fem.LinearForm
            def bf(v, w):
                x, y = w.x[0], w.x[1]
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
                return bx * v[0] + by * v[1]
            return fem.asm(bf, basis)

        # Coarse solve
        K_c = solver.assemble_stiffness(basis_c)
        f_c = get_bf(basis_c)
        D_c = np.concatenate([solver.find_dirichlet_dofs(basis_c, gmesh_c, b, ["x", "y"]) for b in ["left", "right", "bottom", "top"]])
        D_c = np.unique(D_c)
        K_c_free, f_c_free, u_c_full, I_c = fem.condense(K_c, f_c, D=D_c)
        u_H = u_c_full.copy()
        u_H[I_c] = spla.spsolve(K_c_free.tocsc(), f_c_free)

        # Fine solve
        K_f = solver.assemble_stiffness(basis_f)
        f_f = get_bf(basis_f)
        D_f = np.concatenate([solver.find_dirichlet_dofs(basis_f, gmesh_f, b, ["x", "y"]) for b in ["left", "right", "bottom", "top"]])
        D_f = np.unique(D_f)
        K_f_free, f_f_free, u_f_full, I_f = fem.condense(K_f, f_f, D=D_f)
        u_h = u_f_full.copy()
        u_h[I_f] = spla.spsolve(K_f_free.tocsc(), f_f_free)

        # Manufactured J1 QoI
        @fem.LinearForm
        def j1_form(v, w):
            return v[1]
        g_f = fem.asm(j1_form, basis_f)

        K_f_adj, g_free, z_full, _ = fem.condense(K_f, g_f, D=D_f)
        z_h = z_full.copy()
        z_h[I_f] = spla.spsolve(K_f_adj.tocsc(), g_free)

    elif qoi_type == "boundary_average_displacement":
        c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
        solver = LinearElasticitySolver(c)

        gmesh_c = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=16, ny=8)
        mesh_c = gmesh_c.mesh
        mesh_f = mesh_c.refined()
        gmesh_f = GDECMesh(mesh_f, width=2.0, height=0.5)

        basis_c = Basis(mesh_c, ElementVector(ElementTriP1()))
        basis_f = Basis(mesh_f, ElementVector(ElementTriP1()))

        P = _build_prolongation_matrix(mesh_c, mesh_f)
        loads = [("right", 0.0, -1e6)]
        bcs = [("left", ["x", "y"])]

        sol_c = solver.solve(gmesh_c, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
        u_H = sol_c.u

        sol_f = solver.solve(gmesh_f, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
        u_h = sol_f.u
        z_h = sol_f.z
        K_f = sol_f.K
        f_f = sol_f.f
        g_f = sol_f.g
        D_f = sol_f.dofs_fixed
    else:
        raise ValueError(f"Unknown qoi_type: {qoi_type}")

    # Field 1: w1 = P @ u_H
    w1 = P @ u_H
    Ju = float(g_f @ u_h)
    Jw1 = float(g_f @ w1)
    dwr1 = float(z_h @ (f_f - K_f @ w1))
    abs_err1 = abs((Ju - Jw1) - dwr1)
    scale1 = max(abs(Ju), abs(Jw1))
    if scale1 == 0.0:
        rel_err1 = float("inf")
    else:
        rel_err1 = float(abs_err1 / scale1)

    # Field 2: w2 = random admissible displacement (seed 9999)
    rng = np.random.default_rng(9999)
    w2 = u_h + 1e-4 * rng.normal(size=len(u_h))
    w2[D_f] = u_h[D_f]  # enforce Dirichlet BCs exactly
    Jw2 = float(g_f @ w2)
    dwr2 = float(z_h @ (f_f - K_f @ w2))
    abs_err2 = abs((Ju - Jw2) - dwr2)
    scale2 = max(abs(Ju), abs(Jw2))
    if scale2 == 0.0:
        rel_err2 = float("inf")
    else:
        rel_err2 = float(abs_err2 / scale2)

    max_rel_err = max(rel_err1, rel_err2)
    passed = max_rel_err <= 1e-9

    failure_class = None
    if not passed:
        failure_class = "SPEC_AMBIG" if (scale1 == 0.0 or scale2 == 0.0) else "NUM_FAIL"

    res = {
        "id": test_id,
        "computed": {
            "qoi_type": qoi_type,
            "w1_prolonged_coarse": {
                "Ju_minus_Jw": float(Ju - Jw1),
                "dual_weighted_residual": dwr1,
                "absolute_identity_error": abs_err1,
                "relative_identity_error": rel_err1,
            },
            "w2_random_admissible": {
                "Ju_minus_Jw": float(Ju - Jw2),
                "dual_weighted_residual": dwr2,
                "absolute_identity_error": abs_err2,
                "relative_identity_error": rel_err2,
            },
            "max_relative_identity_error": max_rel_err,
        },
        "threshold": {"relative_tolerance": 1e-9},
        "pass": passed,
        "failure_class": failure_class,
        "details": f"Nested-mesh exact discrete algebraic identity J(u) - J(w) = z^T (f - Kw) for {qoi_type}.",
    }
    _record_result(res, "A2_5_adjoint.json")
    assert passed, f"Adjoint discrete identity error {max_rel_err} > 1e-9 for {qoi_type}"


def test_a2_5c_reference_comparison():
    """
    A2.5c: Report-only reference comparison (classification: DIAGNOSTIC_ONLY, pass: None).
    Computes fine reference solutions (ny in {4, 8, 16, 32}) and evaluates coarse error.
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
            "classification": "DIAGNOSTIC_ONLY",
        },
        "threshold": {"report_only": True},
        "pass": None,
        "failure_class": None,
        "details": "Hierarchical cantilever reference QoI progression (report only, diagnostic).",
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
