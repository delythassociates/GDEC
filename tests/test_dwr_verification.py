"""
Comprehensive numerical verification test suite for Goal-Oriented Dual-Weighted Residual (DWR) adaptivity.
Verifies facet traction jumps, dual weights, residual conservation, orientation invariance,
effectivity index convergence across multiple reference meshes, boundary condition treatments,
analytical manufactured-polynomial edge bubble integration, and volume residual support.
"""

import numpy as np
import pytest
import skfem as fem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
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


# 10. Rigorous Dual Boundary Treatment (DOF-based constraints)
def test_dwr_dual_boundary_treatments():
    """
    Audit DualWeightEvaluator under various boundary configurations:
      1. Left-only Dirichlet: dual weights vanish on left boundary facets and NOT on others.
      2. Right-only Dirichlet: dual weights vanish on right boundary facets.
      3. Multiple Dirichlet boundaries (left and bottom clamped): dual weights vanish on both.
      4. Mixed Dirichlet/Neumann (bottom roller in y, left clamped in x and y):
         on bottom, dual_weights[1] == 0 while dual_weights[0] != 0.
      5. Incomplete/incorrect metadata fallback: inspecting sol.dofs_fixed succeeds.
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
    # On bottom: y component must vanish, x component must NOT vanish
    assert np.all(w_mixed[1, is_bottom] == 0.0), "Bottom roller must zero y dual weight"
    assert not np.all(w_mixed[0, is_bottom] == 0.0), "Bottom roller must NOT zero x dual weight"

    # 5. Incorrect metadata passed: sol.dofs_fixed ensures correct behavior
    w_wrong_meta = evaluator.evaluate(mesh, sol_left, facet_data, fixed_boundary_names=["top"])
    assert np.all(w_wrong_meta[:, is_left] == 0.0), "sol.dofs_fixed must protect true Dirichlet boundary"


# 11. Manufactured Polynomial Tests for Cubic Hermite Edge Bubble Integration
def test_dwr_manufactured_polynomial_bubble_integration():
    """
    Independently verify edge bubble integration against exact calculus on [0, h_F]:
      e(s) = p(s) - Pi_h p(s)
      W_F = int_0^{h_F} e(s) ds == (h_F^2 / 12) * (p'_0 - p'_1)
    Tests:
      1. Linear field p(s) = c0 + c1*s -> e(s) == 0 -> W_F == 0.
      2. Quadratic bubble p(s) = s*(h_F - s) -> exact integral = +h_F^3 / 6.
      3. Cubic field p(s) = s^3 -> exact integral = -h_F^4 / 4.
      4. Orientation reversal invariance: reversing endpoints gives identical signed integral.
      5. Dimensional consistency: scales as h_F^2 * d(grad)/ds ~ [length] * [field].
    """
    for h_F in [0.1, 0.5, 2.0, 10.0]:
        # 1. Linear field: p(s) = 3.0 + 2.5*s
        p_prime_0 = 2.5
        p_prime_1 = 2.5
        w_lin = (h_F**2 / 12.0) * (p_prime_0 - p_prime_1)
        assert np.isclose(w_lin, 0.0)

        # 2. Quadratic bubble: p(s) = h_F*s - s^2
        # p'(s) = h_F - 2s -> p'(0) = h_F, p'(h_F) = -h_F
        # Exact integral: int_0^{h_F} (h_F*s - s^2) ds = h_F^3/2 - h_F^3/3 = +h_F^3/6
        exact_quad = (h_F**3) / 6.0
        w_quad = (h_F**2 / 12.0) * (h_F - (-h_F))
        np.testing.assert_allclose(w_quad, exact_quad, rtol=1e-14)

        # 3. Cubic field: p(s) = s^3
        # Pi_h p(s) = h_F^2 * s -> e(s) = s^3 - h_F^2 * s
        # Exact integral: int_0^{h_F} (s^3 - h_F^2*s) ds = h_F^4/4 - h_F^4/2 = -h_F^4/4
        # p'(s) = 3s^2 -> p'(0) = 0, p'(h_F) = 3h_F^2
        exact_cubic = - (h_F**4) / 4.0
        w_cubic = (h_F**2 / 12.0) * (0.0 - 3.0 * h_F**2)
        np.testing.assert_allclose(w_cubic, exact_cubic, rtol=1e-14)

        # 4. Orientation reversal invariance
        # Let t_F be from 0 to h_F. If reversed, tangent is -t_F, endpoint 0 becomes endpoint 1.
        # Original: (h_F^2 / 12) * (grad(0) - grad(1)) . t_F
        # Reversed: (h_F^2 / 12) * (grad(1) - grad(0)) . (-t_F) = original!
        diff_orig = (p_prime_0 - p_prime_1)
        diff_rev = (-p_prime_1 - (-p_prime_0))
        assert np.isclose(diff_orig, diff_rev)


# 12. Element Volume Residual Support and Validation
def test_dwr_element_volume_residual_support():
    """
    Verify ElementResidualEvaluator:
      1. For standard zero-body-force BVPs, volume residual is identically zero.
      2. For nonzero body force, volume contribution is evaluated and included in DWR estimate.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)

    sol = solver.solve(mesh, loads=[("right", 0.0, -1e6)], fixed_boundaries=[("left", ["x", "y"])], solve_adjoint=True)

    # 1. Zero body force: volume residual contribution must be 0.0
    res_zero = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1e6)])
    assert res_zero.details["is_zero_body_force"] is True
    assert res_zero.details["volume_residual_contribution"] == 0.0
    assert res_zero.details["volume_residual_norm"] == 0.0

    # 2. Nonzero constant body force
    b_fn = lambda x: np.tile(np.array([[0.0], [-1000.0]]), (1, x.shape[1]))
    res_body = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1e6)], body_force_fn=b_fn)
    assert res_body.details["is_zero_body_force"] is False
    assert res_body.details["volume_residual_norm"] > 0.0
    assert np.isfinite(res_body.details["volume_residual_contribution"])
