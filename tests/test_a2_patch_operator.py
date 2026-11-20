"""
tests/test_a2_patch_operator.py
Phase A Numerical Verification:
- A2.1a: Linear displacement patch test on perturbed mesh (plane stress & plane strain)
- A2.1b: Production uniform tension solve against analytical continuum fields
- A2.2: Operator checks: stiffness matrix symmetry, rigid body mode eigenvalue spectrum,
        null-space projection residuals, cantilever residual and reaction equilibrium.

Writes machine-readable JSON results to results/verification/A2_1_patch.json and A2_2_operator.json.
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from verification.mesh_utils import create_perturbed_mesh, compute_mesh_metrics


RESULTS_DIR = Path("results/verification")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _record_result(res_dict: dict, file_name: str) -> None:
    """Append machine-readable JSON result to target file and print it."""
    out_file = RESULTS_DIR / file_name
    existing = []
    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text())
            if not isinstance(existing, list):
                existing = [existing]
        except Exception:
            existing = []
    # Replace if same id exists, else append
    existing = [r for r in existing if r.get("id") != res_dict["id"]]
    existing.append(res_dict)
    out_file.write_text(json.dumps(existing, indent=2))
    print(f"\n[VERIFICATION RESULT {res_dict['id']}] pass={res_dict['pass']} failure_class={res_dict['failure_class']}")
    print(json.dumps(res_dict, indent=2))


def test_a2_1a_linear_displacement_patch_test():
    """
    A2.1a: Linear displacement field reproduction on perturbed mesh.
    Field: ux = a0 + a1*x + a2*y, uy = b0 + b1*x + b2*y
    Tested for both plane_stress and plane_strain.
    Threshold:
      - Interior nodal displacement error: ||u_h - u_exact||_inf / max|u_exact| <= 1e-10
      - Element stress agrees with D * eps to relative tolerance 1e-10
    """
    # 5x5 perturbed mesh
    skfem_mesh, mesh_metrics = create_perturbed_mesh(n=5, seed=12345)
    p = skfem_mesh.p
    t = skfem_mesh.t
    nnodes = p.shape[1]

    # Linear displacement coefficients
    a0, a1, a2 = 0.001, 0.002, -0.0015
    b0, b1, b2 = -0.0005, 0.0012, 0.0025

    ux_exact = a0 + a1 * p[0] + a2 * p[1]
    uy_exact = b0 + b1 * p[0] + b2 * p[1]

    u_exact_nodal = np.zeros(2 * nnodes)
    u_exact_nodal[0::2] = ux_exact
    u_exact_nodal[1::2] = uy_exact
    max_u_exact = float(np.max(np.abs(u_exact_nodal)))

    # Constant engineering strain
    eps_11 = a1
    eps_22 = b2
    gamma_12 = a2 + b1
    eps_vec = np.array([eps_11, eps_22, gamma_12])

    # Identify boundary nodes
    tol = 1e-12
    is_bnd = (p[0] < tol) | (p[0] > 1.0 - tol) | (p[1] < tol) | (p[1] > 1.0 - tol)
    interior_nodes = np.where(~is_bnd)[0]
    bnd_nodes = np.where(is_bnd)[0]
    bnd_dofs = np.concatenate([2 * bnd_nodes, 2 * bnd_nodes + 1])
    interior_dofs = np.concatenate([2 * interior_nodes, 2 * interior_nodes + 1])

    for assumption in ["plane_stress", "plane_strain"]:
        test_id = f"A2.1a_{assumption}"
        c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption=assumption, thickness=1.0)
        solver = LinearElasticitySolver(c)
        gmesh = GDECMesh(skfem_mesh, 1.0, 1.0)
        basis = solver.create_basis(gmesh)

        # Assemble stiffness matrix
        K = solver.assemble_stiffness(basis)
        f = np.zeros(basis.N)

        # Condense Dirichlet boundary conditions u_D = u_exact
        u_prescribed = np.zeros(basis.N)
        u_prescribed[bnd_dofs] = u_exact_nodal[bnd_dofs]

        K_free, f_free, u_full, I = skfem.condense(K, f, x=u_prescribed, D=bnd_dofs)
        u_free = spla.spsolve(K_free.tocsc(), f_free)
        u_h = u_full.copy()
        u_h[I] = u_free

        # Displacement error on interior nodes
        interior_err = np.max(np.abs(u_h[interior_dofs] - u_exact_nodal[interior_dofs]))
        rel_disp_err = float(interior_err / max_u_exact)

        # Stress evaluation: D * eps
        sigma_exact = c.matrix_3x3 @ eps_vec
        # Evaluate numerical stress via basis interpolation
        # In P1 triangle, gradient is uniform across each element
        grad = basis.interpolate(u_h).grad[:, :, :, 0]
        exx_h = grad[0, 0, :]
        eyy_h = grad[1, 1, :]
        exy2_h = grad[0, 1, :] + grad[1, 0, :]
        eps_h = np.vstack([exx_h, eyy_h, exy2_h])
        sigma_h = c.matrix_3x3 @ eps_h

        stress_err = np.max(np.abs(sigma_h - sigma_exact[:, None]))
        rel_stress_err = float(stress_err / np.max(np.abs(sigma_exact)))

        passed = bool(rel_disp_err <= 1e-10 and rel_stress_err <= 1e-10)
        fail_class = None if passed else "NUM_FAIL"

        res = {
            "id": test_id,
            "computed": {
                "relative_interior_displacement_error": rel_disp_err,
                "relative_element_stress_error": rel_stress_err,
                "max_interior_displacement_abs_error_m": float(interior_err),
                "max_stress_abs_error_Pa": float(stress_err),
                "assumption": assumption,
                "mesh_metrics": mesh_metrics,
            },
            "threshold": {
                "interior_nodal_displacement_rel_tol": 1e-10,
                "stress_constitutive_rel_tol": 1e-10,
            },
            "pass": passed,
            "failure_class": fail_class,
            "details": f"Linear displacement patch test ({assumption}) on 5x5 perturbed mesh with h_loc perturbation."
        }
        _record_result(res, "A2_1_patch.json")
        assert passed, f"{test_id} failed: rel_disp_err={rel_disp_err}, rel_stress_err={rel_stress_err}"


def test_a2_1b_production_uniform_tension():
    """
    A2.1b: Production uniform tension solve.
    Boundary conditions:
      - Left: ux = 0
      - Bottom: uy = 0
      - Right: traction (s, 0)
    Analytical solutions:
      - Plane stress: ux = s*x/E, uy = -nu*s*y/E
      - Plane strain: ux = s*(1-nu^2)*x/E, uy = -s*nu*(1+nu)*y/E
    Threshold: relative error <= 1e-10
    """
    E = 70e9
    nu = 0.33
    t = 0.02
    s = 1000.0  # Applied right-hand traction (Pa)

    for assumption in ["plane_stress", "plane_strain"]:
        test_id = f"A2.1b_{assumption}"
        c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption=assumption, thickness=t)
        solver = LinearElasticitySolver(c)
        gmesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=6, ny=6)

        # Boundary conditions: left ux=0, bottom uy=0
        fixed_bcs = [("left", ["x"]), ("bottom", ["y"])]
        loads = [("right", s, 0.0)]

        # Production solve
        sol = solver.solve(gmesh, loads=loads, fixed_boundaries=fixed_bcs, solve_adjoint=False)

        # Analytical nodal solution
        p = gmesh.mesh.p
        x = p[0]
        y = p[1]
        if assumption == "plane_stress":
            ux_exact = s * x / E
            uy_exact = -nu * s * y / E
        else:
            ux_exact = s * (1.0 - nu**2) * x / E
            uy_exact = -s * nu * (1.0 + nu) * y / E

        u_exact_nodal = np.zeros(2 * len(x))
        u_exact_nodal[0::2] = ux_exact
        u_exact_nodal[1::2] = uy_exact

        max_exact = float(np.max(np.abs(u_exact_nodal)))
        linf_err = float(np.max(np.abs(sol.u - u_exact_nodal)))
        rel_err = float(linf_err / max_exact)

        passed = bool(rel_err <= 1e-10)
        fail_class = None if passed else "NUM_FAIL"

        res = {
            "id": test_id,
            "computed": {
                "relative_displacement_error_Linf": rel_err,
                "max_absolute_error_m": linf_err,
                "assumption": assumption,
                "applied_traction_Pa": s,
            },
            "threshold": {
                "relative_error_tol": 1e-10,
            },
            "pass": passed,
            "failure_class": fail_class,
            "details": f"Production solve uniform tension test ({assumption}) on unit square."
        }
        _record_result(res, "A2_1_patch.json")
        assert passed, f"{test_id} failed: rel_err={rel_err} > 1e-10"


def test_a2_2_operator_checks():
    """
    A2.2: Operator checks on exact A0-4 mesh:
    - Domain: unit square, 4 elements x, 3 elements y (5 nodes x, 4 nodes y), default diagonal.
    - Thickness = 1, E = 1, nu = 0.3.
    - Plane stress and plane strain.
    Acceptance:
    - Matrix asymmetry: ||K - K^T||_F / ||K||_F <= 1e-12
    - Rigid body modes: exactly 3 eigenvalues <= 1e-10 * lambda_max
    - 4th eigenvalue: lambda_4 / lambda_max >= 1e-4
    - Null-space projection: ||(I - P_null) r|| / ||r|| <= 10^-8 for rigid fields
    - Cantilever equilibrium: ||Ku - f|| / ||f|| <= 1e-10
    - Cantilever reactions: ||applied load + reaction|| / ||applied load|| <= 1e-8
    """
    for assumption in ["plane_stress", "plane_strain"]:
        test_id_sym = f"A2.2_symmetry_{assumption}"
        test_id_eig = f"A2.2_rigid_modes_{assumption}"
        test_id_proj = f"A2.2_null_projection_{assumption}"

        # Exact A0-4 mesh: 4 elements x, 3 elements y (5 nodes x, 4 nodes y)
        skfem_mesh = skfem.MeshTri.init_tensor(
            np.linspace(0.0, 1.0, 5),
            np.linspace(0.0, 1.0, 4)
        )
        c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption=assumption, thickness=1.0)
        solver = LinearElasticitySolver(c)
        gmesh = GDECMesh(skfem_mesh, 1.0, 1.0)
        basis = solver.create_basis(gmesh)

        K_sp = solver.assemble_stiffness(basis)
        K = K_sp.toarray()

        # 1. Symmetry check
        K_diff = K - K.T
        norm_diff = float(np.linalg.norm(K_diff, "fro"))
        norm_K = float(np.linalg.norm(K, "fro"))
        asym_ratio = float(norm_diff / norm_K)

        sym_pass = bool(asym_ratio <= 1e-12)
        _record_result({
            "id": test_id_sym,
            "computed": {
                "frobenius_asymmetry_ratio": asym_ratio,
                "frobenius_diff": norm_diff,
                "frobenius_K": norm_K,
                "assumption": assumption,
            },
            "threshold": {
                "stiffness_symmetry_frobenius_rel_tol": 1e-12,
            },
            "pass": sym_pass,
            "failure_class": None if sym_pass else "NUM_FAIL",
            "details": f"Stiffness matrix symmetry check ({assumption}) on A0-4 mesh."
        }, "A2_2_operator.json")
        assert sym_pass, f"{test_id_sym} failed: asym_ratio={asym_ratio}"

        # 2. Eigenvalue spectrum of unconstrained stiffness matrix
        K_sym = 0.5 * (K + K.T)
        evals, evecs = np.linalg.eigh(K_sym)
        # eigh returns eigenvalues in ascending order
        lambda_max = float(evals[-1])
        lambda_0 = float(evals[0])
        lambda_1 = float(evals[1])
        lambda_2 = float(evals[2])
        lambda_3 = float(evals[3])

        null_tol = 1e-10 * lambda_max
        null_count = int(np.sum(evals <= null_tol))
        ratio_4 = float(lambda_3 / lambda_max)

        eig_pass = bool(null_count == 3 and ratio_4 >= 1e-4)
        _record_result({
            "id": test_id_eig,
            "computed": {
                "smallest_four_eigenvalues": [lambda_0, lambda_1, lambda_2, lambda_3],
                "largest_eigenvalue": lambda_max,
                "null_eigenvalues_count": null_count,
                "fourth_to_largest_ratio": ratio_4,
                "expected_ratio_order": "~2e-2",
                "assumption": assumption,
            },
            "threshold": {
                "null_space_dimension": 3,
                "null_space_eigenvalue_max_rel_tol": 1e-10,
                "fourth_eigenvalue_ratio_min": 1e-4,
            },
            "pass": eig_pass,
            "failure_class": None if eig_pass else "NUM_FAIL",
            "details": f"Rigid body eigenvalue spectrum check ({assumption}) on unconstrained stiffness."
        }, "A2_2_operator.json")
        assert eig_pass, f"{test_id_eig} failed: null_count={null_count}, ratio_4={ratio_4}"

        # 3. Rigid body mode span verification: translation x, translation y, rotation about centroid
        # Null space projection operator P_null = V_3 @ V_3^T
        V3 = evecs[:, :3]
        P_null = V3 @ V3.T

        p = skfem_mesh.p
        xc, yc = float(np.mean(p[0])), float(np.mean(p[1]))

        # Analytical rigid fields:
        # r_x: ux=1, uy=0
        rx = np.zeros(basis.N)
        rx[0::2] = 1.0
        # r_y: ux=0, uy=1
        ry = np.zeros(basis.N)
        ry[1::2] = 1.0
        # r_rot: ux = -(y - yc), uy = (x - xc)
        rrot = np.zeros(basis.N)
        rrot[0::2] = -(p[1] - yc)
        rrot[1::2] = (p[0] - xc)

        res_x = float(np.linalg.norm((np.eye(basis.N) - P_null) @ rx) / np.linalg.norm(rx))
        res_y = float(np.linalg.norm((np.eye(basis.N) - P_null) @ ry) / np.linalg.norm(ry))
        res_rot = float(np.linalg.norm((np.eye(basis.N) - P_null) @ rrot) / np.linalg.norm(rrot))
        max_proj_res = max(res_x, res_y, res_rot)

        proj_pass = bool(max_proj_res <= 1e-8)
        _record_result({
            "id": test_id_proj,
            "computed": {
                "translation_x_projection_residual": res_x,
                "translation_y_projection_residual": res_y,
                "rotation_projection_residual": res_rot,
                "max_projection_residual": max_proj_res,
                "assumption": assumption,
            },
            "threshold": {
                "rigid_body_null_projection_residual_rel_tol": 1e-8,
            },
            "pass": proj_pass,
            "failure_class": None if proj_pass else "NUM_FAIL",
            "details": f"Null space projection residual of analytical rigid body modes ({assumption})."
        }, "A2_2_operator.json")
        assert proj_pass, f"{test_id_proj} failed: max_proj_res={max_proj_res}"

    # 4. Cantilever equilibrium and reactions
    c_cant = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver_cant = LinearElasticitySolver(c_cant)
    mesh_cant = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    loads_cant = [("right", 0.0, -1e6)]
    bcs_cant = [("left", ["x", "y"])]

    sol_cant = solver_cant.solve(mesh_cant, loads=loads_cant, fixed_boundaries=bcs_cant)

    # Cantilever residual ||K_free * u_free - f_free|| / ||f_free||
    # In scikit-fem, on free DOFs: K_free @ u_free - f_free
    K_free, f_free, _, I = skfem.condense(sol_cant.K, sol_cant.f, D=sol_cant.dofs_fixed)
    res_vec = K_free @ sol_cant.u[I] - f_free
    norm_res = float(np.linalg.norm(res_vec))
    norm_f_free = float(np.linalg.norm(f_free))
    rel_res = float(norm_res / norm_f_free)

    res_pass = bool(rel_res <= 1e-10)
    _record_result({
        "id": "A2.2_cantilever_residual",
        "computed": {
            "relative_free_dof_residual": rel_res,
            "residual_norm_N": norm_res,
            "load_norm_N": norm_f_free,
        },
        "threshold": {
            "cantilever_residual_rel_tol": 1e-10,
        },
        "pass": res_pass,
        "failure_class": None if res_pass else "NUM_FAIL",
        "details": "Cantilever free-DOF equation equilibrium residual ||Ku - f|| / ||f||."
    }, "A2_2_operator.json")
    assert res_pass, f"A2.2_cantilever_residual failed: rel_res={rel_res}"

    # Reaction equilibrium: ||applied load + reaction|| / ||applied load||
    R, bal_x, bal_y = solver_cant.check_reactions_equilibrium(sol_cant)
    total_reaction = np.array([bal_x, bal_y])
    # Applied tip load: ty = -1e6 Pa * area (height 0.5 * thickness 0.02 = 0.01 m^2) = -10,000 N
    total_applied = np.array([0.0, -10000.0])
    diff_reactions = float(np.linalg.norm(total_reaction))
    rel_react = float(diff_reactions / np.linalg.norm(total_applied))

    react_pass = bool(rel_react <= 1e-8)
    _record_result({
        "id": "A2.2_reaction_equilibrium",
        "computed": {
            "total_reaction_force_x_N": float(R[0]),
            "total_reaction_force_y_N": float(R[1]),
            "net_force_balance_x_N": float(bal_x),
            "net_force_balance_y_N": float(bal_y),
            "relative_reaction_equilibrium_error": rel_react,
        },
        "threshold": {
            "cantilever_reaction_equilibrium_rel_tol": 1e-8,
        },
        "pass": react_pass,
        "failure_class": None if react_pass else "NUM_FAIL",
        "details": "Static force equilibrium between applied surface traction and boundary reaction forces."
    }, "A2_2_operator.json")
    assert react_pass, f"A2.2_reaction_equilibrium failed: rel_react={rel_react}"
