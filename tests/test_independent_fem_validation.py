"""
Automated Independent FEM Reference Validation Test using scikit-fem.
Verifies that GDEC analytical scaling agrees with independently assembled
and solved finite element elasticity solutions to within machine precision.
"""

import pytest
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
from skfem.models.elasticity import linear_elasticity, plane_stress

from gdec.dse.scaling import (
    RestrictedLinearElasticScaling,
    ReferenceBaseline,
    ScalingAssumptions,
    ScalingAssumptionError,
)


@pytest.fixture(scope="module")
def independent_reference_fem():
    """Construct and solve authoritative baseline cantilever elasticity problem in scikit-fem."""
    L, H = 5.0, 1.0
    nx, ny = 41, 17
    nu = 0.3
    E_0 = 210e3  # 210,000 MPa (210 GPa)
    P_0 = 1000.0 # 1,000 N shear load

    mesh = fem.MeshTri.init_tensor(np.linspace(0, L, nx), np.linspace(0, H, ny))
    element = fem.ElementVector(fem.ElementTriP1())
    ib = fem.Basis(mesh, element)

    dofs_clamped = ib.get_dofs(lambda x: np.isclose(x[0], 0.0)).all()
    facets_right = mesh.facets_satisfying(lambda x: np.isclose(x[0], L))
    fb = fem.FacetBasis(mesh, element, facets=facets_right)

    nodes_tip = np.where(np.isclose(mesh.p[0], L) & np.isclose(mesh.p[1], H / 2.0))[0]
    dof_tip_uy = ib.nodal_dofs[1, nodes_tip[0]]

    def solve_fn(E_val, P_val):
        """Fresh independent assembly and solve from scratch."""
        @fem.LinearForm
        def traction(v, w):
            return - (P_val / H) * v[1]

        f = fem.asm(traction, fb)
        mu, lmbda = plane_stress(E_val, nu)
        K = fem.asm(linear_elasticity(mu, lmbda), ib)

        K_c, f_c, u_init, I_dofs = fem.condense(K, f, D=dofs_clamped)
        u_free = spla.spsolve(K_c, f_c)
        u_full = u_init.copy()
        u_full[I_dofs] = u_free

        # Free-DOF equilibrium residual
        r_free = f_c - K_c @ u_free
        r_free_norm = float(np.linalg.norm(r_free))
        res_free_rel = float(r_free_norm / max(np.linalg.norm(f_c), 1e-14))

        # Constrained-DOF reaction forces
        reactions = K @ u_full - f
        dofs_clamped_y = ib.get_dofs(lambda x: np.isclose(x[0], 0.0)).nodal['u^2']
        total_Ry = float(np.sum(reactions[dofs_clamped_y]))
        vert_equil_err = abs(total_Ry - P_val) / max(P_val, 1e-14)

        tip_u = abs(float(u_full[dof_tip_uy]))
        compliance = abs(float(f @ u_full))
        return {
            "tip_u": tip_u,
            "compliance": compliance,
            "res_free_rel": res_free_rel,
            "vert_equil_err": vert_equil_err,
        }

    base_res = solve_fn(E_0, P_0)
    J_0 = base_res["tip_u"]
    C_0 = base_res["compliance"]

    baseline = ReferenceBaseline(
        E_0=E_0,
        P_0=P_0,
        J_0=J_0,
        poisson_ratio=nu,
        dof_count=ib.N,
        qoi_name="tip_deflection",
    )
    assumptions = ScalingAssumptions(
        uniform_material_scaling=True,
        fixed_geometry=True,
        fixed_poisson_ratio=True,
        linear_elastic_regime=True,
        proportional_loading=True,
        compatible_displacement_qoi=True,
        qoi_type="fixed_displacement",
        attested_by="skfem_independent_validator",
    )
    scaler = RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

    return {
        "solve_fn": solve_fn,
        "scaler": scaler,
        "E_0": E_0,
        "P_0": P_0,
        "J_0": J_0,
        "C_0": C_0,
        "baseline": baseline,
        "n_elements": mesh.nelements,
        "n_nodes": mesh.p.shape[1],
        "n_dofs": ib.N,
    }


def test_independent_fem_scaling_agreement(independent_reference_fem):
    """Verify that analytical scaling matches independent scikit-fem solutions across parameter variations."""
    ctx = independent_reference_fem
    solve_fn = ctx["solve_fn"]
    scaler = ctx["scaler"]
    E_0, P_0 = ctx["E_0"], ctx["P_0"]

    variations = [
        (2.0 * E_0, P_0),
        (0.5 * E_0, P_0),
        (E_0, 2.0 * P_0),
        (E_0, 0.5 * P_0),
        (1.5 * E_0, 3.0 * P_0),
    ]

    for E_var, P_var in variations:
        res = solve_fn(E_var, P_var)
        J_fem = res["tip_u"]
        J_pred = scaler.evaluate_scalar(E_var, P_var)
        rel_diff = abs(J_fem - J_pred) / J_fem
        assert rel_diff < 1e-10
        # Assert free-DOF equilibrium residual and vertical reaction balance
        assert res["res_free_rel"] < 1e-10
        assert res["vert_equil_err"] < 1e-7


def test_independent_fem_compliance_quadratic_law(independent_reference_fem):
    """
    Verify why GDEC scaling refuses compliance:
    Compliance scales quadratically with load (P^2/E), NOT linearly (P/E).
    """
    ctx = independent_reference_fem
    solve_fn = ctx["solve_fn"]
    E_0, P_0, C_0 = ctx["E_0"], ctx["P_0"], ctx["C_0"]

    # When load doubles (P = 2 P_0), compliance quadruples (4x)
    res_2P = solve_fn(E_0, 2.0 * P_0)
    C_2P = res_2P["compliance"]
    quad_ratio = C_2P / C_0
    assert pytest.approx(quad_ratio, abs=1e-8) == 4.0

    # If linear scaling (P/E) was erroneously applied, it would predict 2x instead of 4x (100% error!)
    linear_prediction = (2.0) * C_0
    err_linear = abs(C_2P - linear_prediction) / C_2P
    assert err_linear == pytest.approx(0.5, abs=1e-8)


def test_scaling_api_rejects_compliance_and_stress(independent_reference_fem):
    """Verify that GDEC scaling strictly rejects compliance and stress QoI types."""
    ctx = independent_reference_fem
    baseline = ctx["baseline"]

    # Rejection of compliance
    asm_comp = ScalingAssumptions(
        uniform_material_scaling=True,
        fixed_geometry=True,
        fixed_poisson_ratio=True,
        linear_elastic_regime=True,
        proportional_loading=True,
        compatible_displacement_qoi=True,
        qoi_type="compliance",
        attested_by="analyst",
    )
    with pytest.raises(ScalingAssumptionError, match="scales quadratically"):
        RestrictedLinearElasticScaling(baseline, assumptions=asm_comp)

    # Rejection of stress
    asm_stress = ScalingAssumptions(
        uniform_material_scaling=True,
        fixed_geometry=True,
        fixed_poisson_ratio=True,
        linear_elastic_regime=True,
        proportional_loading=True,
        compatible_displacement_qoi=False,
        qoi_type="stress",
        attested_by="analyst",
    )
    with pytest.raises(ScalingAssumptionError, match="Stress QoIs"):
        RestrictedLinearElasticScaling(baseline, assumptions=asm_stress)
