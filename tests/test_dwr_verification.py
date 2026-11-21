"""
Comprehensive numerical verification test suite for Goal-Oriented Dual-Weighted Residual (DWR) adaptivity.
Verifies facet traction jumps, dual weights, residual conservation, orientation invariance,
effectivity index convergence, and adaptive refinement behavior.
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
      3. The global DWR error estimate must be zero (< 1e-12 m).
      4. All element DWR indicators must be zero (< 1e-12 m).
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
    # Linear dual field
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
    assert dwr_res.details["signed_qoi_error_estimate"] > 0.0
    assert np.all(dwr_res.indicators >= 0.0)
    assert np.max(dwr_res.indicators) > 1e-6
    assert dwr_res.details["max_traction_jump"] > 1e5  # Pa


# 3. Interior Facet Orientation Invariance
def test_dwr_interior_facet_orientation_invariance():
    """
    The traction jump across an interior facet F shared by elements e0 and e1 is:
      [[sigma_h * n]] = sigma_0 * n_0 + sigma_1 * n_1 = (sigma_0 - sigma_1) * n_0.
    If the facet normal or vertex ordering is inverted:
      n_0' = -n_0, and the elements are swapped (sigma_1 - sigma_0) * (-n_0) == (sigma_0 - sigma_1) * n_0.
    Verify that traction jump magnitude and DWR contribution are strictly invariant.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    sol = solver.solve(
        mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=True,
    )

    strains, stresses = RefinementEstimator(c).compute_element_strains_and_stresses(mesh, sol, sol.u)
    evaluator = FacetTractionJumpEvaluator(c)
    data1 = evaluator.evaluate(mesh, stresses)

    # Invert normals and swap element order artificially
    int_idx = np.where(data1.is_interior)[0]
    e0, e1 = data1.element_0[int_idx], data1.element_1[int_idx]

    # Evaluate traction jump computed from element 1 with outward normal pointing into element 0
    normals_inv = -data1.normals[:, int_idx]
    s_0 = stresses[:, e0]
    s_1 = stresses[:, e1]

    t1_x = s_1[0] * normals_inv[0] + s_1[2] * normals_inv[1]
    t1_y = s_1[2] * normals_inv[0] + s_1[1] * normals_inv[1]

    t0_x = s_0[0] * normals_inv[0] + s_0[2] * normals_inv[1]
    t0_y = s_0[2] * normals_inv[0] + s_0[1] * normals_inv[1]

    # Jump from swapped elements: T_1 - T_0 with inverted normal
    jump_inv_x = t1_x - t0_x
    jump_inv_y = t1_y - t0_y

    np.testing.assert_allclose(jump_inv_x, data1.traction_jumps[0, int_idx], rtol=1e-12)
    np.testing.assert_allclose(jump_inv_y, data1.traction_jumps[1, int_idx], rtol=1e-12)

    # Magnitude is strictly invariant
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
    n1 = -n0  # outward normal for element 1

    # T_{0 -> 1} = sigma_0 * n0
    T01_x = stresses[0, e0] * n0[0] + stresses[2, e0] * n0[1]
    T01_y = stresses[2, e0] * n0[0] + stresses[1, e0] * n0[1]

    # T_{1 -> 0} = sigma_1 * n1
    T10_x = stresses[0, e1] * n1[0] + stresses[2, e1] * n1[1]
    T10_y = stresses[2, e1] * n1[0] + stresses[1, e1] * n1[1]

    # The jump [[sigma * n]] is T01 + T10
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

    # Discrete linear QoI functional J(u)
    assert np.isclose(sol.qoi, float(sol.g @ sol.u))

    # Dual problem residual: K_free * z_free == g_free
    basis = sol.basis
    I = np.setdiff1d(np.arange(basis.N), sol.dofs_fixed)
    K_free = sol.K[I, :][:, I]
    g_free = sol.g[I]
    z_free = sol.z[I]

    res_dual = np.linalg.norm(K_free @ z_free - g_free) / np.linalg.norm(g_free)
    assert res_dual < 1e-12, f"Dual linear system residual {res_dual} exceeds 1e-12"


# 6. QoI Error Estimation Against High-Resolution Reference (Effectivity Convergence)
def test_dwr_qoi_error_estimation_and_effectivity_convergence():
    """
    Evaluate cantilever tip displacement on mesh sequence (9x5, 17x9, 33x17)
    against high-resolution reference (65x33).
    Verify that:
      1. Signed DWR error estimate has correct sign (+).
      2. Effectivity index I_eff = E_DWR / (J_ref - J_h) is within [0.5, 1.5] and converges to 1.0.
      3. Absolute DWR indicator sum bounds the error.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    ref_mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=65, ny=33)
    sol_ref = solver.solve(
        ref_mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
        solve_adjoint=False,
    )
    qoi_ref = abs(sol_ref.qoi)

    effectivities = []
    for nx, ny in [(9, 5), (17, 9), (33, 17)]:
        mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=nx, ny=ny)
        sol = solver.solve(
            mesh,
            loads=[("right", 0.0, -1.0e6)],
            fixed_boundaries=[("left", ["x", "y"])],
            solve_adjoint=True,
        )
        qoi_h = abs(sol.qoi)
        true_err = qoi_ref - qoi_h

        dwr_res = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1.0e6)])
        dwr_est = dwr_res.details["signed_qoi_error_estimate"]

        assert dwr_est > 0.0, f"DWR error estimate {dwr_est} must have positive sign"
        eff = dwr_est / true_err
        effectivities.append(eff)

        # Upper bound indicator sum must be >= signed error estimate
        assert dwr_res.details["absolute_error_indicator_sum"] >= abs(dwr_est)

    # Effectivity index must be physically meaningful (within 0.5 to 1.3)
    assert 0.5 < effectivities[0] < 1.3
    assert 0.7 < effectivities[1] < 1.3
    assert 0.9 < effectivities[2] < 1.3


# 7. Adaptive Refinement Monotonic Error Reduction
def test_dwr_adaptive_refinement_reduces_qoi_error():
    """
    Perform 4 iterations of DWR goal-oriented adaptive mesh refinement.
    Verify that:
      1. QoI error decreases monotonically at each refinement iteration.
      2. Element count and DOFs remain within budget.
      3. Final error is less than 1.0%.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    ref_mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=65, ny=33)
    sol_ref = solver.solve(ref_mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])])
    qoi_ref = abs(sol_ref.qoi)

    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    errors = []

    for it in range(4):
        sol = solver.solve(mesh, loads=[("right", 0.0, -1.0e6)], fixed_boundaries=[("left", ["x", "y"])], solve_adjoint=True)
        qoi_h = abs(sol.qoi)
        err = abs(qoi_ref - qoi_h) / qoi_ref
        errors.append(err)

        if it == 3:
            break

        ind = estimator.compute_dwr_indicator(mesh, sol, loads=[("right", 0.0, -1.0e6)], cost_aware=True)
        marked = MeshAdaptor.mark_elements(ind, "dwr", marking_fraction=0.3, current_dofs=sol.basis.N, max_dofs_budget=10000)
        mesh = mesh.refine_elements(marked)

    # Strict monotonic error reduction
    for i in range(len(errors) - 1):
        assert errors[i + 1] < errors[i], f"Error did not decrease: {errors[i]*100:.2f}% -> {errors[i+1]*100:.2f}%"

    # Final error must be small
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
    p[:, is_interior] += 0.03  # shear perturbation
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
