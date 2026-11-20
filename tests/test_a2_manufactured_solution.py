"""
A2.4: Manufactured Solution Convergence Study (MMS).
Verifies convergence rates of 2D P1 linear elasticity formulation:
- Exact displacement field:
    ux = sin(pi*x)*sin(pi*y)
    uy = x*(1-x)*y*(1-y)*(1 + x + 2*y)
- Homogeneous Dirichlet BCs on entire boundary (ux = uy = 0 on dOmega).
- Body force b = -div(sigma) derived analytically via SymPy.
- Quadrature order: >= 6 for body force assembly, >= 8 for error integration.
- Refinement levels: n in {8, 16, 32, 64, 128}.
- Meshes: structured and perturbed (seed 12345).
- Assumptions: plane_stress and plane_strain.
- Asymptotic rates evaluated over n in {32, 64, 128}.
"""

import json
from pathlib import Path
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.fem.mesh import GDECMesh
from verification.mesh_utils import create_structured_mesh, create_perturbed_mesh

RESULTS_DIR = Path("results/phase_a_completion")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_max_element_diameter(mesh: fem.MeshTri) -> float:
    """Independent calculation of maximum element diameter: h = max_{K} diam(K)."""
    p, t = mesh.p, mesh.t
    p0 = p[:, t[0]]
    p1 = p[:, t[1]]
    p2 = p[:, t[2]]
    l01 = np.linalg.norm(p1 - p0, axis=0)
    l12 = np.linalg.norm(p2 - p1, axis=0)
    l20 = np.linalg.norm(p0 - p2, axis=0)
    return float(np.max([l01, l12, l20]))


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


def get_analytical_body_force(x: np.ndarray, y: np.ndarray, c11: float, c12: float, c33: float):
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


J1_EXACT = 5.0 / 72.0
J2_EXACT = 6.0 / (np.pi**2)
LEVELS = [8, 16, 32, 64, 128]


@pytest.mark.parametrize("mtype", ["structured", "perturbed"])
@pytest.mark.parametrize("plane_type", ["plane_stress", "plane_strain"])
def test_a2_4_manufactured_solution_convergence(mtype: str, plane_type: str):
    test_id = f"A2.4_{mtype}_{plane_type}"

    c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption=plane_type, thickness=1.0)
    c11, c12, c33 = c.c11, c.c12, c.c33
    solver = LinearElasticitySolver(c)

    h_vals = []
    l2_errors = []
    energy_errors = []
    j1_errors = []
    j2_errors = []
    dof_counts = []
    element_counts = []

    for n in LEVELS:
        if mtype == "structured":
            mesh, _ = create_structured_mesh(n)
        else:
            mesh, _ = create_perturbed_mesh(n, seed=12345)

        h = compute_max_element_diameter(mesh)
        h_vals.append(h)
        element_counts.append(int(mesh.t.shape[1]))

        gmesh = GDECMesh(mesh, 1.0, 1.0)
        basis_sol = fem.Basis(mesh, solver.element)
        basis_force = fem.Basis(mesh, solver.element, intorder=6)
        basis_eval = fem.Basis(mesh, solver.element, intorder=8)
        dof_counts.append(int(basis_sol.N))

        K = solver.assemble_stiffness(basis_sol)

        @fem.LinearForm
        def bf(v, w):
            bx, by = get_analytical_body_force(w.x[0], w.x[1], c11, c12, c33)
            return bx * v[0] + by * v[1]

        f = fem.asm(bf, basis_force)

        # All Dirichlet DOFs (u = 0 on boundary)
        dirichlet_dofs = np.concatenate([
            solver.find_dirichlet_dofs(basis_sol, gmesh, b, ["x", "y"])
            for b in ["left", "right", "bottom", "top"]
        ])
        dirichlet_dofs = np.unique(dirichlet_dofs)

        K_free, f_free, u_full, I = fem.condense(K, f, D=dirichlet_dofs)
        u_h = u_full.copy()
        u_h[I] = spla.spsolve(K_free.tocsc(), f_free)

        u_eval = basis_eval.interpolate(u_h)

        # L2 error functional
        @fem.Functional
        def l2_fn(w):
            x, y = w.x[0], w.x[1]
            ux_ex = np.sin(np.pi * x) * np.sin(np.pi * y)
            uy_ex = x * (1.0 - x) * y * (1.0 - y) * (1.0 + x + 2.0 * y)
            u = w["u"]
            return (u[0] - ux_ex)**2 + (u[1] - uy_ex)**2

        err_l2 = float(np.sqrt(fem.asm(l2_fn, basis_eval, u=u_eval)))
        l2_errors.append(err_l2)

        # Energy norm error functional
        @fem.Functional
        def energy_fn(w):
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

        err_en = float(np.sqrt(fem.asm(energy_fn, basis_eval, u=u_eval)))
        energy_errors.append(err_en)

        # QoI functionals
        @fem.Functional
        def q1_fn(w):
            return w["u"][1]

        @fem.Functional
        def q2_fn(w):
            return (1.0 + w.x[0]) * w["u"][0]

        j1_val = float(fem.asm(q1_fn, basis_eval, u=u_eval))
        j2_val = float(fem.asm(q2_fn, basis_eval, u=u_eval))

        j1_errors.append(float(abs(j1_val - J1_EXACT)))
        j2_errors.append(float(abs(j2_val - J2_EXACT)))

    # Compute asymptotic rates via linear regression over n in {32, 64, 128}
    log_h_fine = np.log(h_vals[-3:])
    rate_l2 = float(np.polyfit(log_h_fine, np.log(l2_errors[-3:]), 1)[0])
    rate_energy = float(np.polyfit(log_h_fine, np.log(energy_errors[-3:]), 1)[0])
    rate_j1 = float(np.polyfit(log_h_fine, np.log(j1_errors[-3:]), 1)[0])
    rate_j2 = float(np.polyfit(log_h_fine, np.log(j2_errors[-3:]), 1)[0])

    # Compute pairwise slopes
    def _pairwise_slopes(errs):
        slopes = []
        for i in range(len(errs) - 1):
            s = np.log(errs[i] / errs[i + 1]) / np.log(h_vals[i] / h_vals[i + 1])
            slopes.append(float(s))
        return slopes

    pw_l2 = _pairwise_slopes(l2_errors)
    pw_energy = _pairwise_slopes(energy_errors)
    pw_j1 = _pairwise_slopes(j1_errors)
    pw_j2 = _pairwise_slopes(j2_errors)

    # Acceptance gates from thresholds.json
    min_l2 = 1.9 if mtype == "structured" else 1.8
    pass_l2 = rate_l2 >= min_l2
    pass_energy = 0.9 <= rate_energy <= 1.1
    pass_j1 = rate_j1 >= 1.8
    pass_j2 = rate_j2 >= 1.8

    # Pairwise relaxed bounds
    min_pw_l2 = min_l2 - 0.1
    min_pw_qoi = 1.8 - 0.1
    pass_pw_l2 = all(s >= min_pw_l2 for s in pw_l2)
    pass_pw_en = all(0.8 <= s <= 1.2 for s in pw_energy)
    pass_pw_j1 = all(s >= min_pw_qoi for s in pw_j1)
    pass_pw_j2 = all(s >= min_pw_qoi for s in pw_j2)

    all_passed = bool(
        pass_l2 and pass_energy and pass_j1 and pass_j2 and
        pass_pw_l2 and pass_pw_en and pass_pw_j1 and pass_pw_j2
    )
    fail_class = None if all_passed else "NUM_FAIL"

    res = {
        "id": test_id,
        "computed": {
            "mesh_type": mtype,
            "plane_type": plane_type,
            "refinement_levels_n": LEVELS,
            "h_values": h_vals,
            "dof_counts": dof_counts,
            "element_counts": element_counts,
            "l2_displacement_errors": l2_errors,
            "energy_norm_errors": energy_errors,
            "qoi_j1_errors": j1_errors,
            "qoi_j2_errors": j2_errors,
            "asymptotic_rates_32_128": {
                "L2": rate_l2,
                "energy": rate_energy,
                "qoi_j1": rate_j1,
                "qoi_j2": rate_j2,
            },
            "pairwise_slopes": {
                "L2": pw_l2,
                "energy": pw_energy,
                "qoi_j1": pw_j1,
                "qoi_j2": pw_j2,
            },
        },
        "threshold": {
            "asymptotic_rates": {
                "L2_min": min_l2,
                "energy_range": [0.9, 1.1],
                "qoi_min": 1.8,
            },
            "pairwise_slopes": {
                "L2_min": min_pw_l2,
                "energy_range": [0.8, 1.2],
                "qoi_min": min_pw_qoi,
            },
        },
        "pass": all_passed,
        "failure_class": fail_class,
        "details": f"MMS convergence study on {mtype} meshes ({plane_type}) over n in {LEVELS}.",
    }
    _record_result(res, "A2_4_manufactured_solution.json")

    assert pass_l2, f"L2 rate {rate_l2} < {min_l2}"
    assert pass_energy, f"Energy rate {rate_energy} not in [0.9, 1.1]"
    assert pass_j1, f"QoI J1 rate {rate_j1} < 1.8"
    assert pass_j2, f"QoI J2 rate {rate_j2} < 1.8"
    assert pass_pw_l2, f"L2 pairwise slopes {pw_l2} failed relaxed bound {min_pw_l2}"
    assert pass_pw_en, f"Energy pairwise slopes {pw_energy} failed relaxed bound [0.8, 1.2]"
    assert pass_pw_j1, f"J1 pairwise slopes {pw_j1} failed relaxed bound {min_pw_qoi}"
    assert pass_pw_j2, f"J2 pairwise slopes {pw_j2} failed relaxed bound {min_pw_qoi}"
