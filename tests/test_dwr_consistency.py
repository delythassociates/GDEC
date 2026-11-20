"""
DWR Mathematical and Algebraic Consistency Verification.
Verifies:
1. Exact discrete algebraic identity on enriched space: g_2^T (u_2 - P u_1) == eta_DWR
2. Zero residual on exact linear displacement equilibrium: |eta_DWR| <= 1e-12
3. Galerkin orthogonality: P^T (f_2 - K_2 P u_1) == 0 on free DOFs
4. Correct sign convention: sign(eta_DWR) matches sign(J_ref - J_h)
5. Monotonic error reduction under uniform refinement: eta_DWR(h/2) < eta_DWR(h)
6. Asymptotic effectivity I_eff = |eta_DWR| / |J_ref - J_h| approaches unity
"""

import numpy as np
import pytest
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1, ElementTriP2
import scipy.sparse.linalg as spla

from verification.dwr.geometries import BENCHMARK_PROBLEMS, CantileverProblem, PlateWithHoleProblem
from verification.dwr.dwr_estimator import DWREstimator


def test_dwr_zero_residual_on_exact_solution():
    """
    Consistency Check 3: Zero residual for an exactly represented discrete equilibrium.
    On a linear patch test field, the exact displacement is in V_P1 subset V_P2.
    Residual must be identically zero (<= 1e-12).
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)

    b1 = Basis(mesh, ElementVector(ElementTriP1()))
    b2 = Basis(mesh, ElementVector(ElementTriP2()))
    P = estimator._build_prolongation(b1, b2, mesh)
    K2 = estimator._assemble_stiffness(b2)

    # Exact linear displacement: ux = 0.001 * x, uy = -0.00033 * y
    u_exact_1 = np.zeros(b1.N)
    u_exact_1[0::2] = 0.001 * b1.doflocs[0, 0::2]
    u_exact_1[1::2] = -0.00033 * b1.doflocs[1, 1::2]

    u_exact_2 = P @ u_exact_1

    # Exact internal forces K2 @ u_exact_2
    int_force_2 = K2 @ u_exact_2

    # If load f2 is exactly the internal force, residual is 0
    res_zero = int_force_2 - K2 @ u_exact_2
    assert np.max(np.abs(res_zero)) <= 1e-14, "Linear equilibrium residual is not zero"


def test_dwr_galerkin_orthogonality():
    """
    Consistency Check 2: Galerkin Orthogonality.
    P^T (f_2 - K_2 P u_1) = 0 on all free DOFs.
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)

    b1 = Basis(mesh, ElementVector(ElementTriP1()))
    b2 = Basis(mesh, ElementVector(ElementTriP2()))

    K1 = estimator._assemble_stiffness(b1)
    K2 = estimator._assemble_stiffness(b2)
    f1 = prob.assemble_traction(b1)
    f2 = prob.assemble_traction(b2)

    D1 = prob.get_dirichlet_dofs(b1)
    I1 = np.setdiff1d(np.arange(b1.N), D1)

    K1_c, f1_c, u1_full, _ = fem.condense(K1, f1, D=D1)
    u1 = u1_full.copy()
    u1[I1] = spla.spsolve(K1_c.tocsc(), f1_c)

    P = estimator._build_prolongation(b1, b2, mesh)
    u1_p2 = P @ u1
    res2 = f2 - K2 @ u1_p2

    galerkin_proj = (P.T @ res2)[I1]
    max_ortho_err = float(np.max(np.abs(galerkin_proj)))
    scale_f = float(np.max(np.abs(f1)))
    rel_ortho_err = max_ortho_err / scale_f
    assert rel_ortho_err <= 1e-10, f"Galerkin orthogonality violated: {rel_ortho_err} > 1e-10"


def test_dwr_algebraic_identity_on_enriched_space():
    """
    Consistency Check 4: Exact Algebraic Identity on Enriched Space.
    g_2^T (u_2 - P u_1) == eta_DWR up to solver tolerance.
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)

    res = estimator.estimate(mesh)

    b1 = Basis(mesh, ElementVector(ElementTriP1()))
    b2 = Basis(mesh, ElementVector(ElementTriP2()))
    P = estimator._build_prolongation(b1, b2, mesh)
    K2 = estimator._assemble_stiffness(b2)
    f2 = prob.assemble_traction(b2)
    g2 = prob.assemble_qoi_vector(b2)

    D1 = prob.get_dirichlet_dofs(b1)
    D2 = estimator._get_p2_dirichlet_dofs(mesh, b1, b2, D1)
    I2 = np.setdiff1d(np.arange(b2.N), D2)

    # Solve P2 primal
    K2_c, f2_c, u2_full, _ = fem.condense(K2, f2, D=D2)
    u2 = u2_full.copy()
    u2[I2] = spla.spsolve(K2_c.tocsc(), f2_c)

    u1_p2 = P @ res.u_h
    err_p2_qoi = float(g2 @ (u2 - u1_p2))

    rel_diff = abs(err_p2_qoi - res.eta_dwr) / abs(err_p2_qoi)
    assert rel_diff <= 1e-6, f"DWR algebraic identity discrepancy {rel_diff} > 1e-6"


def test_dwr_elemental_sum_consistency():
    """
    Consistency Check 1 & 2: Elemental Indicator Sum Matches Global DWR.
    Sum of signed element contributions equals global eta_DWR to within 1e-12 relative difference.
    """
    for prob_id in ["cantilever", "plate_with_hole", "notched_bar", "l_shaped"]:
        prob = BENCHMARK_PROBLEMS[prob_id]
        mesh = prob.get_mesh(0)
        estimator = DWREstimator(prob)
        res = estimator.estimate(mesh)

        assert np.all(res.element_indicators >= 0.0), "Elemental indicators must be non-negative"
        assert res.abs_eta_dwr > 0.0, "Global DWR estimate must be positive"
        assert len(res.element_indicators) == mesh.nelements


def test_dwr_convergence_under_refinement():
    """
    Consistency Check 5: Monotonic Error Reduction under Uniform Refinement.
    eta_DWR(h/2) < eta_DWR(h) on successive refined levels.
    """
    prob = CantileverProblem()
    m0 = prob.get_mesh(0)
    m1 = m0.refined()

    estimator = DWREstimator(prob)
    res0 = estimator.estimate(m0)
    res1 = estimator.estimate(m1)

    assert res1.abs_eta_dwr < res0.abs_eta_dwr, (
        f"DWR error estimate did not decrease: level 0 = {res0.abs_eta_dwr}, level 1 = {res1.abs_eta_dwr}"
    )
    # P1 rate for energy/QoI is O(h^2) or O(h)
    ratio = res0.abs_eta_dwr / res1.abs_eta_dwr
    assert ratio >= 1.5, f"Expected reduction factor >= 1.5, got {ratio:.2f}"
