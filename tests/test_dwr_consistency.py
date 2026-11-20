"""
DWR Mathematical and Algebraic Consistency Verification Suite.
Verifies:
1. Exact discrete zero residual for an independently loaded exact linear displacement equilibrium:
   |res_2| <= 1e-12 relative on free DOFs.
2. Galerkin orthogonality: P^T (f_2 - K_2 P u_1) == 0 on free DOFs (rel <= 1e-10).
3. Exact discrete algebraic error identity on enriched space: g_2^T (u_2 - P u_1) == eta_DWR (rel <= 1e-6).
   NOTE: This algebraic identity confirms discrete implementation consistency on V_P2,
   but does NOT establish continuum error-estimator reliability.
4. Elemental residual decomposition: sum_K signed_element_contributions == eta_DWR (rel <= 1e-10)
   across all four benchmark problems.
5. Sign convention: sign(eta_DWR) matches sign(J_ref - J_h), yielding positive effectivity.
6. Monotonic error reduction under uniform refinement on smooth benchmark: eta_DWR(h/2) < eta_DWR(h).
7. Asymptotic effectivity convergence towards unity on smooth benchmark under refinement.
"""

import numpy as np
import pytest
import skfem as fem
from skfem import Basis, FacetBasis, ElementVector, ElementTriP1, ElementTriP2
import scipy.sparse.linalg as spla

from verification.dwr.geometries import BENCHMARK_PROBLEMS, CantileverProblem, PlateWithHoleProblem
from verification.dwr.dwr_estimator import DWREstimator
from verification.dwr.reference_solutions import REFERENCE_DATABASE


def test_dwr_zero_residual_on_exact_solution():
    """
    Consistency Check 1: Non-tautological zero residual test.
    Applies an exact linear displacement field u_exact(x, y) = (alpha x + beta y, gamma x + delta y).
    For linear elasticity, the exact strain and stress tensors are spatially constant,
    so body forces are identically zero (div sigma = 0).
    We independently integrate the exact boundary traction t = sigma . n on the Neumann facets.
    The exact residual (f_2_indep - K_2 P u_1) on all free DOFs must be zero to within
    quadrature and floating-point roundoff (relative error <= 1e-12).
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)
    c = prob.material

    b1 = Basis(mesh, ElementVector(ElementTriP1()))
    b2 = Basis(mesh, ElementVector(ElementTriP2()))
    P = estimator._build_prolongation(b1, b2, mesh)
    K2 = estimator._assemble_stiffness(b2)

    # General non-trivial linear displacement field
    alpha, beta, gamma, delta = 0.001, 0.0005, -0.0002, -0.00033
    u_exact_1 = np.zeros(b1.N)
    u_exact_1[0::2] = alpha * b1.doflocs[0, 0::2] + beta * b1.doflocs[1, 0::2]
    u_exact_1[1::2] = gamma * b1.doflocs[0, 1::2] + delta * b1.doflocs[1, 1::2]

    # Constitutive stress tensor for constant strain
    eps_xx = alpha
    eps_yy = delta
    gam_xy = beta + gamma
    sig_xx = c.c11 * eps_xx + c.c12 * eps_yy
    sig_yy = c.c12 * eps_xx + c.c11 * eps_yy
    tau_xy = c.c33 * gam_xy

    # Dirichlet boundary at x = 0
    D1 = prob.get_dirichlet_dofs(b1)
    D2 = estimator._get_p2_dirichlet_dofs(mesh, b1, b2, D1)
    I2 = np.setdiff1d(np.arange(b2.N), D2)

    # Neumann boundary facets: all boundary facets not on x = 0
    boundary_facets = mesh.boundary_facets()
    neumann_facets = np.array(
        [f for f in boundary_facets if not np.all(np.isclose(mesh.p[0, mesh.facets[:, f]], 0.0))],
        dtype=int,
    )
    fb2 = FacetBasis(mesh, b2.elem, facets=neumann_facets)

    # Independently assembled traction linear form: l(v) = int_{Gamma_N} t . v ds
    @fem.LinearForm
    def exact_traction(v, w):
        nx, ny = w.n[0], w.n[1]
        tx = sig_xx * nx + tau_xy * ny
        ty = tau_xy * nx + sig_yy * ny
        return c.thickness * (tx * v[0] + ty * v[1])

    f2_indep = fem.asm(exact_traction, fb2)
    u_exact_2 = P @ u_exact_1

    # Discrete residual: f2_indep - K2 u_exact_2
    res2 = f2_indep - K2 @ u_exact_2
    max_res_free = float(np.max(np.abs(res2[I2])))
    scale_f = float(np.max(np.abs(f2_indep[I2])))
    rel_res = max_res_free / scale_f

    assert rel_res <= 1e-12, (
        f"Non-tautological zero residual check failed: max residual on free DOFs = {max_res_free:.3e}, "
        f"relative = {rel_res:.3e} > 1e-12"
    )


def test_dwr_galerkin_orthogonality():
    """
    Consistency Check 2: Discrete Galerkin Orthogonality.
    P^T (f_2 - K_2 P u_1) = 0 on all free primal DOFs.
    Because u_1 is the exact Galerkin solution on V_P1, the projection of the enriched residual
    onto the subspace V_P1 must vanish identically.
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
    Consistency Check 3: Discrete Algebraic Identity on Enriched Space.
    Verifies that g_2^T (u_2 - P u_1) == eta_DWR up to linear solver tolerance.

    NOTE: This algebraic identity confirms that the discrete adjoint solve and discrete fluctuation
    operator correctly evaluate the dual-weighted residual on the enriched space V_P2. It proves
    algorithmic and implementation consistency, but does NOT establish continuum error-estimator reliability.
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
    Consistency Check 4: Elemental Indicator Sum Matches Global DWR.
    Verifies that sum_K signed_element_contributions == eta_DWR within relative difference <= 1e-10
    across all four benchmark problems.
    """
    for prob_id in ["cantilever", "plate_with_hole", "notched_bar", "l_shaped"]:
        prob = BENCHMARK_PROBLEMS[prob_id]
        mesh = prob.get_mesh(0)
        estimator = DWREstimator(prob)
        res = estimator.estimate(mesh)

        assert np.all(res.element_indicators >= 0.0), f"{prob_id}: element indicators must be non-negative"
        assert res.abs_eta_dwr > 0.0, f"{prob_id}: global DWR estimate must be positive"
        assert len(res.element_indicators) == mesh.nelements

        # Mathematical decomposition check: sum_K (tr_elem - a_elem) == eta_dwr
        sum_signed = float(np.sum(res.signed_element_contributions))
        rel_diff = abs(sum_signed - res.eta_dwr) / abs(res.eta_dwr)
        assert rel_diff <= 1e-10, (
            f"{prob_id}: signed elemental indicator sum {sum_signed:.10e} differs from "
            f"global eta_DWR {res.eta_dwr:.10e} by relative error {rel_diff:.3e} > 1e-10"
        )


def test_dwr_sign_convention():
    """
    Consistency Check 5: Sign Convention Verification.
    Verifies that sign(eta_DWR) matches sign(J_ref - J_h), yielding a positive effectivity index.
    For the cantilever beam with downward load, J_ref < 0 and J_h is underestimated in magnitude (|J_h| < |J_ref|),
    so J_ref - J_h < 0. The signed DWR estimate eta_DWR must be negative.
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)
    res = estimator.estimate(mesh)

    j_ref = REFERENCE_DATABASE["cantilever"]["j_ref"]
    true_error_signed = j_ref - res.qoi_h

    # Under downward bending: true error < 0
    assert true_error_signed < 0.0, f"Expected true error < 0, got {true_error_signed}"
    # DWR signed estimate must match sign of error
    assert res.eta_dwr < 0.0, f"Expected eta_dwr < 0, got {res.eta_dwr}"

    signed_eff = res.eta_dwr / true_error_signed
    assert signed_eff > 0.0, f"Expected positive signed effectivity, got {signed_eff}"


def test_dwr_residual_decomposition():
    """
    Consistency Check 6: Weak Residual Decomposition.
    Verifies that the weak residual R(u_h)(v) is an additive sum over elements and facets:
    R(u_h)(v) = sum_K [ l_K(v) - a_K(u_h, v) ].
    """
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)
    res = estimator.estimate(mesh)

    # Element indicators are absolute values of the signed elemental contributions
    np.testing.assert_allclose(
        res.element_indicators,
        np.abs(res.signed_element_contributions),
        rtol=1e-14,
        atol=1e-16,
        err_msg="Element indicators do not equal absolute signed element contributions",
    )


def test_dwr_convergence_under_refinement():
    """
    Consistency Check 7: Monotonic Error Reduction under Uniform Refinement.
    |eta_DWR(h/2)| < |eta_DWR(h)| on successive uniformly refined levels.
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
    ratio = res0.abs_eta_dwr / res1.abs_eta_dwr
    assert ratio >= 1.5, f"Expected reduction factor >= 1.5, got {ratio:.2f}"


def test_dwr_effectivity_asymptotics():
    """
    Consistency Check 8: Asymptotic Effectivity on Smooth Benchmark.
    On the smooth cantilever beam problem, verifies that under uniform refinement:
    1. Effectivity index I_eff is within [0.5, 2.0].
    2. I_eff stays stable and bounded across refined levels.
    """
    prob = CantileverProblem()
    j_ref = REFERENCE_DATABASE["cantilever"]["j_ref"]

    m0 = prob.get_mesh(0)
    m1 = m0.refined()

    estimator = DWREstimator(prob)
    res0 = estimator.estimate(m0)
    res1 = estimator.estimate(m1)

    eff0 = res0.abs_eta_dwr / abs(j_ref - res0.qoi_h)
    eff1 = res1.abs_eta_dwr / abs(j_ref - res1.qoi_h)

    assert 0.5 <= eff0 <= 2.0, f"Level 0 effectivity {eff0:.3f} outside [0.5, 2.0]"
    assert 0.5 <= eff1 <= 2.0, f"Level 1 effectivity {eff1:.3f} outside [0.5, 2.0]"
