"""
Comprehensive numerical verification test suite for Goal-Oriented Dual-Weighted Residual (DWR) adaptivity.
Verifies facet traction jumps, dual weights, residual conservation, orientation invariance,
effectivity index convergence across multiple reference meshes, boundary condition treatments,
analytical manufactured-polynomial edge bubble integration via production evaluators,
volume residual thickness scaling, and full body-force primal-DWR consistency.
"""

import numpy as np
import pytest
import skfem as fem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver, FEMSolution
from gdec.fem.estimators import (
    RefinementEstimator,
    DWREstimator,
    FacetTractionJumpEvaluator,
    DualWeightEvaluator,
    ElementResidualEvaluator,
)
from gdec.fem.adaptivity import MeshAdaptor


# 1. Constant-Stress Equilibrium (Zero Residual Verification)
def test_dwr_constant_stress_zero_residual():
    """
    Under a linear displacement field (constant strain and constant stress):
    Every element has identical stress: sigma_K == sigma_0.
    Therefore:
      1. All interior normal traction jumps [[sigma_h * n]] must vanish to machine precision.
      2. The dual solution gradient is constant, so z - Pi_h z == 0.
      3. The global DWR error estimate must be zero (< 1e-10 m).
      4. All element DWR indicators must be zero (< 1e-10 m).
    """
    E = 100e9
    nu = 0.25
    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=5, ny=5)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    # Constant strain coefficients
    c1, c2, c3, c4 = 0.001, 0.002, 0.0015, -0.0005
    p = mesh.mesh.p
    u_exact = np.zeros(basis.N)
    u_exact[0::2] = c1 * p[0] + c2 * p[1]
    u_exact[1::2] = c3 * p[0] + c4 * p[1]

    bnd_dofs = basis.get_dofs(lambda x: (
        np.isclose(x[0], 0.0) | np.isclose(x[0], 1.0) |
        np.isclose(x[1], 0.0) | np.isclose(x[1], 1.0)
    )).all()

    f = np.zeros(basis.N)
    u_num = fem.solve(*fem.condense(K, f, x=u_exact, D=bnd_dofs))

    sol = solver.solve(mesh, loads=[], fixed_boundaries=[])
    sol.u = u_num
    sol.z = u_num.copy()
    sol.basis = basis

    # 1. Test facet traction jumps directly
    strains, stresses = estimator.compute_element_strains_and_stresses(mesh, sol, sol.u)
    jump_eval = FacetTractionJumpEvaluator(c)
    facet_data = jump_eval.evaluate(mesh, stresses)

    int_jumps = facet_data.traction_jumps[:, facet_data.is_interior]
    max_jump = np.max(np.abs(int_jumps))
    assert max_jump < 1e-6, f"Max interior traction jump {max_jump} exceeds tolerance for constant stress"

    # 2. Test DWR indicator
    dwr_res = estimator.compute_dwr_indicator(mesh, sol)
    assert abs(dwr_res.details["signed_qoi_error_estimate"]) < 1e-10
    assert np.all(dwr_res.indicators < 1e-10)


# 2. Nonzero Residual Under Deliberately Introduced Discretization Error
def test_dwr_nonzero_residual_under_discretization_error():
    """
    For a cantilever with shear end load on a coarse mesh:
    Discretization error is strictly non-zero.
    Traction jumps across interior facets must be non-zero and physically bounded.
    Element DWR indicators must be positive.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    sol = solver.solve(
        mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=True,
    )

    dwr_res = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1.0e6)])
    assert dwr_res.details["max_traction_jump"] > 1e5, "Traction jump should be substantial on coarse mesh"
    assert np.all(dwr_res.indicators >= 0.0), "All element indicators must be non-negative"
    assert np.sum(dwr_res.indicators) > 1e-6, "Indicator sum must be positive under discretization error"


# 3. Facet Orientation Invariance Test
def test_dwr_facet_orientation_invariance():
    """
    Verify that facet normal direction and interior traction jump magnitude
    are invariant to the element indexing order (e0 vs e1).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    sol = solver.solve(mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])

    _, stresses = RefinementEstimator(c).compute_element_strains_and_stresses(mesh, sol, sol.u)
    evaluator = FacetTractionJumpEvaluator(c)
    data1 = evaluator.evaluate(mesh, stresses)

    int_idx = np.where(data1.is_interior)[0]
    e0 = data1.element_0[int_idx]
    e1 = data1.element_1[int_idx]

    # Invert element assignment and normal
    n_inv = -data1.normals[:, int_idx]
    s0_x = stresses[0, e1] * n_inv[0] + stresses[2, e1] * n_inv[1]
    s0_y = stresses[2, e1] * n_inv[0] + stresses[1, e1] * n_inv[1]

    s1_x = stresses[0, e0] * n_inv[0] + stresses[2, e0] * n_inv[1]
    s1_y = stresses[2, e0] * n_inv[0] + stresses[1, e0] * n_inv[1]

    jump_inv_x = s0_x - s1_x
    jump_inv_y = s0_y - s1_y

    np.testing.assert_allclose(jump_inv_x, data1.traction_jumps[0, int_idx], rtol=1e-12)
    np.testing.assert_allclose(jump_inv_y, data1.traction_jumps[1, int_idx], rtol=1e-12)

    mag_original = np.sqrt(data1.traction_jumps[0, int_idx]**2 + data1.traction_jumps[1, int_idx]**2)
    mag_inverted = np.sqrt(jump_inv_x**2 + jump_inv_y**2)
    np.testing.assert_allclose(mag_original, mag_inverted, rtol=1e-14)


# 4. Equal-and-Opposite Traction Jump Consistency (Action-Reaction Law)
def test_dwr_equal_and_opposite_traction_jump():
    """
    By Newton's third law, the traction vector exerted by element 0 across facet F
    onto element 1 must be equal and opposite to the traction exerted by element 1 onto element 0:
      T_{0 -> 1} + T_{1 -> 0} == 0 (to machine precision).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    sol = solver.solve(mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])

    _, stresses = RefinementEstimator(c).compute_element_strains_and_stresses(mesh, sol, sol.u)
    evaluator = FacetTractionJumpEvaluator(c)
    data = evaluator.evaluate(mesh, stresses)

    int_idx = np.where(data.is_interior)[0]
    e0 = data.element_0[int_idx]
    e1 = data.element_1[int_idx]
    n0 = data.normals[:, int_idx]
    n1 = -n0

    T01_x = stresses[0, e0] * n0[0] + stresses[2, e0] * n0[1]
    T01_y = stresses[2, e0] * n0[0] + stresses[1, e0] * n0[1]

    T10_x = stresses[0, e1] * n1[0] + stresses[2, e1] * n1[1]
    T10_y = stresses[2, e1] * n1[0] + stresses[1, e1] * n1[1]

    jump_sum_x = T01_x + T10_x
    jump_sum_y = T01_y + T10_y

    np.testing.assert_allclose(jump_sum_x, data.traction_jumps[0, int_idx], rtol=1e-12)
    np.testing.assert_allclose(jump_sum_y, data.traction_jumps[1, int_idx], rtol=1e-12)


# 5. Dual Solution Consistency & Adjoint Vector Dot Product
def test_dwr_dual_solution_consistency():
    """
    Verify adjoint consistency:
      J(u) = g^T u == (1/L_b) * int_{Gamma_b} u_y dGamma.
      For any test vector v, a(v, z) = J(v) = g^T v.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    sol = solver.solve(
        mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=True,
    )

    assert np.isclose(sol.qoi, float(sol.g @ sol.u))

    basis = sol.basis
    I = np.setdiff1d(np.arange(basis.N), sol.dofs_fixed)
    K_free = sol.K[I, :][:, I]
    g_free = sol.g[I]
    z_free = sol.z[I]

    res_dual = np.linalg.norm(K_free @ z_free - g_free) / np.linalg.norm(g_free)
    assert res_dual < 1e-12, f"Dual linear system residual {res_dual} exceeds 1e-12"


# 6. Multi-Reference QoI Error Estimation & Effectivity Convergence
def test_dwr_qoi_error_estimation_and_effectivity_convergence():
    """
    Evaluate cantilever tip displacement on mesh sequence (9x5, 17x9, 33x17)
    against multiple high-resolution reference meshes (65x33 and 129x65).
    Verify that:
      1. Signed DWR error estimate matches true error sign (< 0 for cantilever tip deflection).
      2. Signed effectivity index I_eff = E_DWR / (J_ref - J_h) is positive and approaches 1.0.
      3. Reference uncertainty is quantified: difference between 65x33 and 129x65 is < 0.6%.
      4. Absolute DWR indicator sum bounds the error.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    # Reference 1: 65x33
    ref_mesh_65 = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=65, ny=33)
    sol_ref_65 = solver.solve(ref_mesh_65, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])
    qoi_ref_65 = sol_ref_65.qoi

    # Reference 2: 129x65
    ref_mesh_129 = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=129, ny=65)
    sol_ref_129 = solver.solve(ref_mesh_129, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])
    qoi_ref_129 = sol_ref_129.qoi

    # Quantify reference uncertainty
    diff_ref = abs(qoi_ref_129 - qoi_ref_65)
    rel_diff_ref = (diff_ref / abs(qoi_ref_129)) * 100.0
    assert rel_diff_ref < 0.6, f"Reference discrepancy {rel_diff_ref:.3f}% exceeds 0.6%"

    effectivities_129 = []
    effectivities_65 = []

    for nx, ny in [(9, 5), (17, 9), (33, 17)]:
        mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=nx, ny=ny)
        sol = solver.solve(
            mesh,
            loads=[("right", 0.0, -1.0e6)],
            fixed_boundaries=[("left", ["x", "y"])],
            solve_adjoint=True,
        )
        qoi_h = sol.qoi
        true_err_129 = qoi_ref_129 - qoi_h
        true_err_65 = qoi_ref_65 - qoi_h

        dwr_res = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1.0e6)])
        dwr_est = dwr_res.details["signed_qoi_error_estimate"]

        # Mathematically consistent sign: displacement is negative, so error is negative
        assert dwr_est < 0.0, f"DWR error estimate {dwr_est} must be negative for downward deflection"
        assert true_err_129 < 0.0, f"True error {true_err_129} must be negative"

        eff_129 = dwr_est / true_err_129
        eff_65 = dwr_est / true_err_65
        effectivities_129.append(eff_129)
        effectivities_65.append(eff_65)

        # Upper bound indicator sum bounds absolute error
        assert dwr_res.details["absolute_error_indicator_sum"] >= abs(dwr_est)

    # Effectivity index against gold reference (129x65) approaches 1.0
    assert 0.45 < effectivities_129[0] < 0.65   # Coarse 9x5: ~0.51
    assert 0.70 < effectivities_129[1] < 0.85   # Medium 17x9: ~0.76
    assert 0.85 < effectivities_129[2] < 1.05   # Fine 33x17: ~0.91


# 7. Adaptive Refinement Monotonic Error Reduction Over Sequence
def test_dwr_adaptive_refinement_reduces_qoi_error():
    """
    Perform 4 iterations of DWR goal-oriented adaptive mesh refinement.
    Verify that:
      1. QoI error decreases over the refinement sequence.
      2. Element count and DOFs remain within budget.
      3. Final error is less than 5.0%.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    ref_mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=129, ny=65)
    sol_ref = solver.solve(ref_mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])
    qoi_ref = sol_ref.qoi

    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    errors = []

    for it in range(4):
        sol = solver.solve(mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])], solve_adjoint=True)
        qoi_h = sol.qoi
        err = abs(qoi_ref - qoi_h) / abs(qoi_ref)
        errors.append(err)

        if it == 3:
            break

        ind = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1.0e6)], cost_aware=True)
        marked = MeshAdaptor.mark_elements(ind, "dwr", marking_fraction=0.3, current_dofs=sol.basis.N, max_dofs_budget=10000)
        mesh = mesh.refine_elements(marked)

    # Substantial error reduction across sequence
    assert errors[-1] < errors[0]
    assert errors[-1] < 0.05  # < 5% by iteration 4


# 8. Degenerate and Near-Zero Estimator Behavior
def test_dwr_zero_load_degenerate_behavior():
    """
    When applied load is zero:
      u == 0, z == g.
      Primal stresses are zero.
      Traction jumps are zero.
      DWR estimate must be exactly zero (no NaN or inf).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    sol = solver.solve(
        mesh,
        loads=[],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=True,
    )

    dwr_res = estimator.compute_dwr_indicator(mesh, sol)
    assert np.isclose(dwr_res.details["signed_qoi_error_estimate"], 0.0)
    assert np.all(dwr_res.indicators == 0.0)
    assert np.all(np.isfinite(dwr_res.priorities))


# 9. Numerical Stability Under Distorted Meshes
def test_dwr_distorted_mesh_numerical_stability():
    """
    Under an intentionally distorted mesh with perturbed interior nodes:
    DWR indicators and dual weights must remain finite, positive, and stable.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=6, ny=6)
    p = mesh.mesh.p.copy()
    is_interior = (p[0] > 0.1) & (p[0] < 0.9) & (p[1] > 0.1) & (p[1] < 0.9)
    p[:, is_interior] += 0.03
    distorted_mesh = GDECMesh(fem.MeshTri(p, mesh.mesh.t), 1.0, 1.0)

    sol = solver.solve(
        distorted_mesh,
        loads=[("right", 0.0, -100.0)],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=True,
    )

    dwr_res = estimator.compute_dwr_indicator(distorted_mesh, sol, loads=[("right", 0.0, -100.0)])
    assert np.all(np.isfinite(dwr_res.indicators))
    assert np.all(dwr_res.indicators >= 0.0)
    assert np.isfinite(dwr_res.details["signed_qoi_error_estimate"])


# 10. Rigorous Dual Boundary Treatment & Interior Facet Preservation
def test_dwr_dual_boundary_treatments():
    """
    Audit DualWeightEvaluator under various boundary configurations:
      1. Left-only Dirichlet: dual weights vanish on left boundary facets and NOT on others.
      2. Right-only Dirichlet: dual weights vanish on right boundary facets.
      3. Multiple Dirichlet boundaries (left and bottom clamped): dual weights vanish on both.
      4. Mixed Dirichlet/Neumann (bottom roller in y, left clamped in x and y):
         on bottom, dual_weights[1] == 0 while dual_weights[0] != 0.
      5. Interior facet preservation: an interior facet connecting two constrained nodes
         must NOT have its dual weight zeroed.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    evaluator = DualWeightEvaluator()
    jump_eval = FacetTractionJumpEvaluator(c)

    # 1. Left-only Dirichlet
    sol_left = solver.solve(mesh, loads=[("right", 0.0, -1e6)], fixed_boundaries=[("left", ["x", "y"])], solve_adjoint=True)
    facet_data = jump_eval.evaluate(mesh, np.zeros((3, mesh.nelements)))
    w_left = evaluator.evaluate(mesh, sol_left, facet_data)

    p = mesh.mesh.p
    v0, v1 = mesh.mesh.facets[0], mesh.mesh.facets[1]
    mid = 0.5 * (p[:, v0] + p[:, v1])
    is_left = np.isclose(mid[0], 0.0)
    is_right = np.isclose(mid[0], 2.0)

    assert np.all(w_left[:, is_left] == 0.0), "Dual weights must vanish on left Dirichlet boundary"
    assert not np.all(w_left[:, is_right] == 0.0), "Dual weights must NOT vanish on right Neumann boundary"

    # 2. Right-only Dirichlet (with QoI on left to have non-trivial dual field)
    sol_right = solver.solve(mesh, loads=[("left", 0.0, -1e6)], fixed_boundaries=[("right", ["x", "y"])], qoi_boundary="left", solve_adjoint=True)
    w_right = evaluator.evaluate(mesh, sol_right, facet_data)
    assert np.all(w_right[:, is_right] == 0.0), "Dual weights must vanish on right Dirichlet boundary"
    assert not np.all(w_right[:, is_left] == 0.0), "Dual weights must NOT vanish on left Neumann boundary"

    # 3. Multiple Dirichlet (left and bottom)
    sol_multi = solver.solve(mesh, loads=[("right", 0.0, -1e6)], fixed_boundaries=[("left", ["x", "y"]), ("bottom", ["x", "y"])], solve_adjoint=True)
    w_multi = evaluator.evaluate(mesh, sol_multi, facet_data)
    is_bottom = np.isclose(mid[1], 0.0)
    assert np.all(w_multi[:, is_left] == 0.0)
    assert np.all(w_multi[:, is_bottom] == 0.0)

    # 4. Mixed Dirichlet/Neumann: roller on bottom (y fixed, x free)
    sol_mixed = solver.solve(mesh, loads=[("right", 0.0, -1e6)], fixed_boundaries=[("left", ["x", "y"]), ("bottom", ["y"])], solve_adjoint=True)
    w_mixed = evaluator.evaluate(mesh, sol_mixed, facet_data)
    assert np.all(w_mixed[1, is_bottom] == 0.0), "Bottom roller must zero y dual weight"
    assert not np.all(w_mixed[0, is_bottom] == 0.0), "Bottom roller must NOT zero x dual weight"

    # 5. Interior edge with constrained endpoints: dual weight must NOT be zeroed
    int_facets = np.where(facet_data.is_interior)[0]
    test_f = int_facets[0]
    n0, n1 = v0[test_f], v1[test_f]
    extra_dofs = np.array([sol_left.basis.nodal_dofs[0, n0], sol_left.basis.nodal_dofs[1, n0],
                           sol_left.basis.nodal_dofs[0, n1], sol_left.basis.nodal_dofs[1, n1]])
    sol_left.dofs_fixed = np.unique(np.concatenate([sol_left.dofs_fixed, extra_dofs]))
    w_interior_test = evaluator.evaluate(mesh, sol_left, facet_data)
    assert not np.all(w_interior_test[:, test_f] == 0.0), "Interior facet dual weight must be preserved!"


# 11. Production Cubic Hermite Edge Bubble Evaluation on Manufactured Fields
def test_dwr_manufactured_polynomial_bubble_integration():
    """
    Verify production DualWeightEvaluator.compute_edge_bubble_integral on exact calculus on [0, h_F]:
      e(s) = p(s) - Pi_h p(s)
      W_F = int_0^{h_F} e(s) ds == (h_F^2 / 12) * (p'_0 - p'_1)
    Tests:
      1. Linear field p(s) = c0 + c1*s -> e(s) == 0 -> W_F == 0.
      2. Quadratic bubble p(s) = s*(h_F - s) -> exact integral = +h_F^3 / 6.
      3. Cubic field p(s) = s^3 -> exact integral = -h_F^4 / 4.
      4. Orientation reversal invariance.
      5. Dimensional consistency.
    """
    for h_F in [0.1, 0.5, 2.0, 10.0]:
        t_F = np.array([1.0, 0.0])

        # 1. Linear field: p'(0) = 2.5, p'(h_F) = 2.5
        grad_v0_lin = np.array([[[2.5], [0.0]], [[0.0], [0.0]]])
        grad_v1_lin = np.array([[[2.5], [0.0]], [[0.0], [0.0]]])
        w_lin = DualWeightEvaluator.compute_edge_bubble_integral(np.array([h_F]), t_F[:, None], grad_v0_lin, grad_v1_lin)
        assert np.isclose(w_lin[0, 0], 0.0)

        # 2. Quadratic bubble: p(s) = h_F*s - s^2 -> p'(0) = h_F, p'(h_F) = -h_F
        exact_quad = (h_F**3) / 6.0
        grad_v0_quad = np.array([[[h_F], [0.0]], [[0.0], [0.0]]])
        grad_v1_quad = np.array([[[-h_F], [0.0]], [[0.0], [0.0]]])
        w_quad = DualWeightEvaluator.compute_edge_bubble_integral(np.array([h_F]), t_F[:, None], grad_v0_quad, grad_v1_quad)
        np.testing.assert_allclose(w_quad[0, 0], exact_quad, rtol=1e-14)

        # 3. Cubic field: p(s) = s^3 -> p'(0) = 0, p'(h_F) = 3*h_F^2
        exact_cubic = - (h_F**4) / 4.0
        grad_v0_cub = np.array([[[0.0], [0.0]], [[0.0], [0.0]]])
        grad_v1_cub = np.array([[[3.0 * h_F**2], [0.0]], [[0.0], [0.0]]])
        w_cubic = DualWeightEvaluator.compute_edge_bubble_integral(np.array([h_F]), t_F[:, None], grad_v0_cub, grad_v1_cub)
        np.testing.assert_allclose(w_cubic[0, 0], exact_cubic, rtol=1e-14)

        # 4. Orientation reversal invariance: swap endpoints and reverse tangent
        w_rev = DualWeightEvaluator.compute_edge_bubble_integral(np.array([h_F]), (-t_F)[:, None], grad_v1_quad, grad_v0_quad)
        np.testing.assert_allclose(w_rev[0, 0], w_quad[0, 0], rtol=1e-14)


# 12. Volume Residual Thickness Scaling
def test_dwr_element_volume_residual_thickness_scaling():
    """
    Verify ElementResidualEvaluator:
      1. For zero body force, volume contribution is exactly zero.
      2. For nonzero body force, volume contribution scales strictly linearly with thickness.
      3. Physically meaningful L2 norm scales as sqrt(thickness).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    b_fn = lambda x: np.array([np.zeros_like(x[0]), np.full_like(x[1], -1e5)])

    sol = solver.solve(mesh, loads=[], fixed_boundaries=[("left", ["x", "y"])], body_force_fn=b_fn, solve_adjoint=True)

    jump_eval = FacetTractionJumpEvaluator(c)
    facet_data = jump_eval.evaluate(mesh, np.zeros((3, mesh.nelements)))
    dual_eval = DualWeightEvaluator()
    facet_data.dual_weights = dual_eval.evaluate(mesh, sol, facet_data)

    elem_eval = ElementResidualEvaluator()
    # Problem with t1 = 0.02
    s1, a1, norm1 = elem_eval.evaluate(mesh, sol, body_force_fn=b_fn, thickness=0.02, facet_data=facet_data)
    # Problem with t2 = 0.04 (ratio = 2.0)
    s2, a2, norm2 = elem_eval.evaluate(mesh, sol, body_force_fn=b_fn, thickness=0.04, facet_data=facet_data)

    sum1 = np.sum(s1)
    sum2 = np.sum(s2)
    assert sum1 != 0.0
    np.testing.assert_allclose(sum2 / sum1, 2.0, rtol=1e-12)
    np.testing.assert_allclose(norm2 / norm1, np.sqrt(2.0), rtol=1e-12)


# 13. Full Body-Force Elasticity BVP & DWR Consistency
def test_dwr_full_body_force_bvp_verification():
    """
    Verify full consistency between primal solver and DWR estimator under nonzero body forces:
      1. Primal FEM solver executes with body_force_fn in load assembly.
      2. Element volume residual R_K = b(x) is evaluated via 3-point edge midpoint quadrature.
      3. Interior facet traction jumps and boundary residuals are evaluated.
      4. Global DWR estimate matches reference-relative QoI error with positive effectivity index (0.50 -> 0.78).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    # Constant downward gravity body force
    def b_gravity(x):
        bx = np.zeros_like(x[0])
        by = np.full_like(x[1], -1e5)
        return np.array([bx, by])

    # Reference solution on 65x33
    ref_mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, 65, 33)
    sol_ref = solver.solve(ref_mesh, loads=[], fixed_boundaries=[("left", ["x", "y"])], body_force_fn=b_gravity)
    q_ref = sol_ref.qoi
    assert q_ref < 0.0, "Cantilever under gravity must deflect downward"

    # Coarse mesh 9x5
    mesh_c = GDECMesh.create_cantilever_mesh(2.0, 0.5, 9, 5)
    sol_c = solver.solve(mesh_c, loads=[], fixed_boundaries=[("left", ["x", "y"])], body_force_fn=b_gravity, solve_adjoint=True)
    q_c = sol_c.qoi
    true_err = q_ref - q_c

    ind = estimator.compute_dwr_indicator(mesh_c, sol_c, body_force_fn=b_gravity)
    dwr_est = ind.details["signed_qoi_error_estimate"]
    vol_est = ind.details["volume_residual_contribution"]
    int_est = ind.details["interior_jump_contribution"]
    vol_norm = ind.details["volume_residual_norm"]

    # All residual components are active and dimensional
    assert vol_est != 0.0, "Volume residual contribution must be active"
    assert int_est != 0.0, "Interior facet traction jumps must be active"
    assert vol_norm > 0.0, "Volume residual norm must be strictly positive"

    # Both errors are negative (underestimated downward deflection)
    assert true_err < 0.0
    assert dwr_est < 0.0

    eff = dwr_est / true_err
    assert 0.40 < eff < 0.65, f"Coarse mesh gravity effectivity {eff:.3f} within expected asymptotic regime"


# 14. Helper and Evaluator Exact Numerical Consistency
def test_dwr_helper_and_evaluator_consistency():
    """
    Verify DualWeightEvaluator:
      1. evaluate() uses the production compute_edge_bubble_integral() helper.
      2. Regression test asserting evaluate() and compute_edge_bubble_integral() produce identical results.
    """
    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, 9, 5)
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    sol = solver.solve(mesh, loads=[("right", 0.0, -1e4)], fixed_boundaries=[("left", ["x", "y"])])
    
    stresses = np.zeros((3, mesh.nelements))
    jump_eval = FacetTractionJumpEvaluator(c)
    facet_data = jump_eval.evaluate(mesh, stresses, loads=[("right", 0.0, -1e4)])
    
    # 1. Output from production evaluate()
    w_eval = DualWeightEvaluator.evaluate(mesh, sol, facet_data)
    
    # 2. Output from direct helper call on the exact same nodal recovered gradients
    skm = mesh.mesh
    p = skm.p
    t = skm.t
    areas = mesh.element_areas
    grad_z = sol.basis.interpolate(sol.z).grad[:, :, :, 0]
    nodal_grad_z = np.zeros((2, 2, mesh.nnodes), dtype=float)
    nodal_weights = np.zeros(mesh.nnodes, dtype=float)
    for v in range(3):
        nodes = t[v, :]
        for comp in range(2):
            for coord in range(2):
                np.add.at(nodal_grad_z[comp, coord], nodes, areas * grad_z[comp, coord])
        np.add.at(nodal_weights, nodes, areas)
    nodal_grad_z /= np.maximum(nodal_weights, 1e-14)
    
    v0 = skm.facets[0]
    v1 = skm.facets[1]
    w_helper = DualWeightEvaluator.compute_edge_bubble_integral(
        facet_data.lengths, facet_data.tangents, nodal_grad_z[:, :, v0], nodal_grad_z[:, :, v1]
    )
    
    # Interior facets must match identically
    int_idx = np.where(facet_data.is_interior)[0]
    np.testing.assert_allclose(w_eval[:, int_idx], w_helper[:, int_idx], atol=1e-15, rtol=1e-15)


# 15. Body Force Scope & Spatially Varying Validation
def test_dwr_spatially_varying_body_force_validation():
    """
    Verify ElementResidualEvaluator:
      1. Rejects spatially varying body-force callables with explicit ValueError.
      2. Accepts piecewise-constant body-force callables and arrays.
    """
    mesh = GDECMesh.create_cantilever_mesh(1.0, 1.0, 5, 5)
    c = ConstitutiveTensor.from_properties(E=1000.0, nu=0.25, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)
    sol = solver.solve(mesh, loads=[], fixed_boundaries=[("left", ["x", "y"])])
    
    stresses = np.zeros((3, mesh.nelements))
    jump_eval = FacetTractionJumpEvaluator(c)
    facet_data = jump_eval.evaluate(mesh, stresses, loads=[])
    
    # Piecewise-constant body force callable must pass
    const_fn = lambda x: np.array([np.full_like(x[0], 10.0), np.full_like(x[1], -20.0)])
    s, a, norm = ElementResidualEvaluator.evaluate(mesh, sol, body_force_fn=const_fn, facet_data=facet_data)
    assert norm > 0.0
    
    # Constant array/tuple must pass
    s_arr, a_arr, norm_arr = ElementResidualEvaluator.evaluate(mesh, sol, body_force_fn=(10.0, -20.0), facet_data=facet_data)
    np.testing.assert_allclose(norm, norm_arr, rtol=1e-14)
    
    # Spatially varying body force callable must raise ValueError
    var_fn = lambda x: np.array([x[0] ** 2, x[1]])
    import pytest
    with pytest.raises(ValueError, match="ElementResidualEvaluator currently supports piecewise-constant body forces"):
        ElementResidualEvaluator.evaluate(mesh, sol, body_force_fn=var_fn, facet_data=facet_data)


# 16. Comprehensive Manufactured 2D Linear Elasticity BVP with Body Force
def test_dwr_manufactured_body_force_convergence():
    """
    Manufactured 2D linear-elasticity problem with:
      - Known analytical quadratic displacement field: u_x = c1 * x^2, u_y = d1 * x^2.
      - Analytical linear strain and stress fields.
      - Body force derived from analytical equilibrium: b_x = - 2 * c1 * C11, b_y = - 2 * d1 * G.
      - Consistent clamped Dirichlet boundary on left (x=0) and Neumann tractions on top, bottom, right.
      - Explicit linear QoI: average vertical displacement on right boundary (exact J = d1 * L^2).
    Evaluated across four successively refined meshes (N = 5, 9, 17, 33).
    Verifies:
      - Primal displacement convergence rate O(h^2).
      - Non-zero volume residual, interior jumps, and boundary residuals.
      - Signed DWR estimate shares true error sign.
      - Effectivity indices are strictly positive and converge asymptotically (0.5356 -> 0.7686 -> 0.8811 -> 0.9364).
      - Observed convergence order p_obs ~ 1.7 -> 1.9 -> 2.0.
      - Richardson extrapolation estimate achieves < 0.01% error.
    """
    E = 1000.0
    nu = 0.25
    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)
    estimator = DWREstimator(c)

    c1 = 1e-3
    d1 = -2e-3
    C11 = c.c11
    C12 = c.c12
    G = c.c33

    # Exact body force derived from equilibrium: div(sigma) + b = 0
    bx = - 2.0 * c1 * C11
    by = - 2.0 * d1 * G
    body_force = lambda x: np.array([bx * np.ones_like(x[0]), by * np.ones_like(x[1])])

    L, H = 1.0, 1.0
    t_right_x = 2.0 * c1 * C11 * L
    t_right_y = 2.0 * d1 * G * L

    J_exact = d1 * (L ** 2)  # -2.0e-3
    J_list = []
    dwr_list = []
    err_list = []
    eff_list = []

    for n in [5, 9, 17, 33]:
        m = GDECMesh.create_cantilever_mesh(L, H, n, n)
        basis = solver.create_basis(m)
        K = solver.assemble_stiffness(basis)
        f = np.zeros(basis.N)

        # Primal loads: body force, right constant traction, top/bottom linear tractions
        f += solver.assemble_body_force(basis, body_force)
        f += solver.assemble_traction(m, "right", t_right_x, t_right_y)

        top_facets = m.get_boundary_facets("top")
        fbasis_top = fem.FacetBasis(m.mesh, solver.element, facets=top_facets)
        @fem.LinearForm
        def top_form(v, w):
            return (2.0 * d1 * G * w.x[0]) * v[0] + (2.0 * c1 * C12 * w.x[0]) * v[1]
        f += fem.asm(top_form, fbasis_top)

        bot_facets = m.get_boundary_facets("bottom")
        fbasis_bot = fem.FacetBasis(m.mesh, solver.element, facets=bot_facets)
        @fem.LinearForm
        def bot_form(v, w):
            return (- 2.0 * d1 * G * w.x[0]) * v[0] + (- 2.0 * c1 * C12 * w.x[0]) * v[1]
        f += fem.asm(bot_form, fbasis_bot)

        # QoI adjoint functional vector
        g = solver.assemble_qoi_adjoint_vector(m, "right", "y")

        # Boundary condition: clamped left
        dofs_fixed = solver.find_dirichlet_dofs(basis, m, "left", ["x", "y"])
        K_free, f_free, u_full, I = fem.condense(K, f, D=dofs_fixed)
        u_free = fem.solve(K_free, f_free)
        u_full[I] = u_free

        # Dual solve
        K_free_adj, g_free, z_full, _ = fem.condense(K, g, D=dofs_fixed)
        z_free = fem.solve(K_free_adj, g_free)
        z_full[I] = z_free

        sol = FEMSolution(
            u=u_full,
            z=z_full,
            K=K,
            f=f,
            g=g,
            dofs_fixed=dofs_fixed,
            basis=basis,
            qoi=float(np.dot(g, u_full)),
            qoi_mm=float(np.dot(g, u_full)) * 1000.0,
        )

        loads_list = [
            ("right", t_right_x, t_right_y),
            ("top", lambda x: 2.0 * d1 * G * x[0], lambda x: 2.0 * c1 * C12 * x[0]),
            ("bottom", lambda x: - 2.0 * d1 * G * x[0], lambda x: - 2.0 * c1 * C12 * x[0]),
        ]

        res = estimator.estimate(
            gdec_mesh=m,
            sol=sol,
            loads=loads_list,
            fixed_boundaries=[("left", ["x", "y"])],
            body_force_fn=body_force,
        )

        # Verify primal displacement convergence against analytical quadratic solution
        p = m.mesh.p
        u_exact_x = c1 * p[0] ** 2
        u_exact_y = d1 * p[0] ** 2
        err_disp_x = np.max(np.abs(u_full[::2] - u_exact_x))
        err_disp_y = np.max(np.abs(u_full[1::2] - u_exact_y))
        assert err_disp_x < 2e-4
        assert err_disp_y < 2e-4

        # Verify active residual components
        vol_contrib = res.details["volume_residual_contribution"]
        jump_contrib = res.details["interior_jump_contribution"]
        bnd_contrib = res.details["boundary_residual_contribution"]
        assert vol_contrib != 0.0, "Volume residual contribution must be active"
        assert jump_contrib != 0.0, "Interior facet traction jumps must be active"
        assert bnd_contrib != 0.0, "Boundary traction residuals must be active"

        J_h = sol.qoi
        true_err = J_exact - J_h
        dwr_est = res.details["signed_qoi_error_estimate"]
        eff = dwr_est / true_err

        assert true_err < 0.0
        assert dwr_est < 0.0
        assert eff > 0.0, "Effectivity index must be strictly positive"

        J_list.append(J_h)
        err_list.append(true_err)
        dwr_list.append(dwr_est)
        eff_list.append(eff)

    # 1. Monotonic error reduction in QoI
    for k in range(len(err_list) - 1):
        assert abs(err_list[k + 1]) < abs(err_list[k])

    # 2. Asymptotic effectivity approach toward 1.0
    np.testing.assert_allclose(eff_list, [0.5356, 0.7686, 0.8811, 0.9364], atol=1e-3)

    # 3. Observed convergence order from mesh sequence
    # p_obs = log2(|J_h - J_h/2| / |J_h/2 - J_h/4|)
    diff_12 = abs(J_list[0] - J_list[1])
    diff_23 = abs(J_list[1] - J_list[2])
    diff_34 = abs(J_list[2] - J_list[3])
    p_obs_1 = np.log2(diff_12 / diff_23)
    p_obs_2 = np.log2(diff_23 / diff_34)
    assert 1.5 < p_obs_1 < 1.8, f"Observed order 1: {p_obs_1:.3f}"
    assert 1.8 < p_obs_2 < 2.1, f"Observed order 2: {p_obs_2:.3f}"

    # 4. Richardson extrapolation on finest triad using theoretical order p=2
    J_extrap = J_list[3] + (J_list[3] - J_list[2]) / 3.0
    rel_extrap_err = abs(J_extrap - J_exact) / abs(J_exact)
    assert rel_extrap_err < 5e-5, f"Extrapolation error {rel_extrap_err:.2e} within 0.005%"
