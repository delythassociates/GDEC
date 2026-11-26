"""
P1 2D Linear Elasticity Manufactured-Solution (MMS) Convergence-Order Verification.

Exercises GDEC's actual production LinearElasticitySolver.solve() on a smooth
2D vector manufactured solution u(x, y) = (A sin(pi x) sin(pi y), B sin(pi x) sin(pi y))
with homogeneous Dirichlet BCs on [0, 1]^2 and exact analytical body force f = -div(sigma(u)).
Verifies theoretical P1 convergence orders:
  - Displacement L2 norm: O(h^2), observed slope in [1.85, 2.15], R^2 >= 0.99
  - Displacement H1 seminorm: O(h^1), observed slope in [0.85, 1.15], R^2 >= 0.99
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pytest
import skfem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from tests.verification.test_convergence_order import fit_convergence_rate


def run_elasticity_mms_sequence(
    assumption: str = "plane_stress",
    mesh_sizes: Tuple[int, ...] = (4, 8, 16, 32),
) -> Dict[str, object]:
    """Run GDEC's production P1 elasticity solver on a smooth MMS refinement hierarchy."""
    E = 100e9
    nu = 0.3
    thickness = 0.02
    A = 1.0e-3
    B = 0.7e-3

    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption=assumption, thickness=thickness)
    solver = LinearElasticitySolver(c)

    def body_force_fn(x):
        xx, yy = x[0], x[1]
        sxsy = np.sin(np.pi * xx) * np.sin(np.pi * yy)
        cxcy = np.cos(np.pi * xx) * np.cos(np.pi * yy)
        bx = (np.pi ** 2) * ((c.c11 + c.c33) * A * sxsy - (c.c12 + c.c33) * B * cxcy)
        by = (np.pi ** 2) * ((c.c11 + c.c33) * B * sxsy - (c.c12 + c.c33) * A * cxcy)
        return np.array([bx, by])

    fixed_bcs = [
        ("left", ["x", "y"]),
        ("right", ["x", "y"]),
        ("bottom", ["x", "y"]),
        ("top", ["x", "y"]),
    ]

    h_vals: List[float] = []
    dofs_list: List[int] = []
    l2_errors: List[float] = []
    h1_errors: List[float] = []

    for N in mesh_sizes:
        gdec_mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=N + 1, ny=N + 1)
        sol = solver.solve(
            gdec_mesh=gdec_mesh,
            loads=[],
            fixed_boundaries=fixed_bcs,
            body_force_fn=body_force_fn,
            solve_adjoint=False,
        )
        assert sol.converged

        @skfem.Functional
        def l2_err_form(w):
            xx, yy = w.x[0], w.x[1]
            ux_ex = A * np.sin(np.pi * xx) * np.sin(np.pi * yy)
            uy_ex = B * np.sin(np.pi * xx) * np.sin(np.pi * yy)
            u_h = w["u"]
            return (u_h[0] - ux_ex) ** 2 + (u_h[1] - uy_ex) ** 2

        @skfem.Functional
        def h1_semi_err_form(w):
            xx, yy = w.x[0], w.x[1]
            dux_dx = A * np.pi * np.cos(np.pi * xx) * np.sin(np.pi * yy)
            dux_dy = A * np.pi * np.sin(np.pi * xx) * np.cos(np.pi * yy)
            duy_dx = B * np.pi * np.cos(np.pi * xx) * np.sin(np.pi * yy)
            duy_dy = B * np.pi * np.sin(np.pi * xx) * np.cos(np.pi * yy)
            g = w["u"].grad
            return (
                (g[0, 0] - dux_dx) ** 2
                + (g[0, 1] - dux_dy) ** 2
                + (g[1, 0] - duy_dx) ** 2
                + (g[1, 1] - duy_dy) ** 2
            )

        l2_err = float(np.sqrt(skfem.asm(l2_err_form, sol.basis, u=sol.basis.interpolate(sol.u))))
        h1_err = float(np.sqrt(skfem.asm(h1_semi_err_form, sol.basis, u=sol.basis.interpolate(sol.u))))

        h_vals.append(1.0 / N)
        dofs_list.append(int(sol.basis.N))
        l2_errors.append(l2_err)
        h1_errors.append(h1_err)

    p_l2, c_l2, r2_l2 = fit_convergence_rate(h_vals, l2_errors)
    p_h1, c_h1, r2_h1 = fit_convergence_rate(h_vals, h1_errors)

    return {
        "assumption": assumption,
        "mesh_sizes": list(mesh_sizes),
        "h": h_vals,
        "dofs": dofs_list,
        "l2_errors": l2_errors,
        "h1_seminorm_errors": h1_errors,
        "p_l2": p_l2,
        "c_l2": c_l2,
        "r2_l2": r2_l2,
        "p_h1": p_h1,
        "c_h1": c_h1,
        "r2_h1": r2_h1,
    }


@pytest.mark.parametrize("assumption", ["plane_stress", "plane_strain"])
def test_gdec_p1_elasticity_mms_convergence_order(assumption: str):
    """
    Verify GDEC's production P1 LinearElasticitySolver achieves optimal
    theoretical convergence rates in L2 (order ~ 2.0) and H1 seminorm (order ~ 1.0).
    """
    res = run_elasticity_mms_sequence(assumption=assumption)
    assert 1.85 <= res["p_l2"] <= 2.15, f"{assumption} L2 slope {res['p_l2']:.4f} outside [1.85, 2.15]"
    assert 0.85 <= res["p_h1"] <= 1.15, f"{assumption} H1 slope {res['p_h1']:.4f} outside [0.85, 1.15]"
    assert res["r2_l2"] >= 0.99, f"{assumption} L2 R^2 {res['r2_l2']:.4f} < 0.99"
    assert res["r2_h1"] >= 0.99, f"{assumption} H1 R^2 {res['r2_h1']:.4f} < 0.99"
