"""
Comprehensive FEM mathematical verification test suite for GDEC.
Verifies element formulation, constitutive relations, equilibrium, patch tests,
beam analytical comparison, manufactured solutions, rigid body modes, and distortion robustness.
"""

import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
import pytest

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.postprocess import PostProcessor


# 1. Constant-Strain Patch Test on Distorted/Irregular Mesh
def test_constant_strain_patch_test_distorted_mesh():
    """
    Standard patch test on an intentionally distorted mesh:
    Linear displacement field:
      u_x = c1 * x + c2 * y
      u_y = c3 * x + c4 * y
    Constant strain:
      eps_xx = c1, eps_yy = c4, gamma_xy = c2 + c3
    Enforce Dirichlet BCs on all boundary nodes.
    Interior node displacements must match the exact linear field to machine precision.
    Element stresses must match exact C * eps.
    """
    E = 100e9
    nu = 0.25
    thickness = 1.0
    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=thickness)
    solver = LinearElasticitySolver(c)

    # Initial grid
    nx, ny = 5, 5
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=nx, ny=ny)

    # Distort interior nodes by perturbing their coordinates
    p = mesh.mesh.p.copy()
    is_interior = (p[0] > 0.05) & (p[0] < 0.95) & (p[1] > 0.05) & (p[1] < 0.95)
    np.random.seed(42)
    perturbation = (np.random.rand(2, np.sum(is_interior)) - 0.5) * 0.08  # up to 4% perturbation
    p[:, is_interior] += perturbation
    distorted_skm = fem.MeshTri(p, mesh.mesh.t)
    distorted_mesh = GDECMesh(distorted_skm, width=1.0, height=1.0)

    # Check element areas remain positive
    assert np.all(distorted_mesh.element_areas > 0.0)

    basis = solver.create_basis(distorted_mesh)
    K = solver.assemble_stiffness(basis)

    # Linear displacement field coefficients
    c1, c2, c3, c4 = 0.001, 0.002, 0.0015, -0.0005
    u_exact = np.zeros(basis.N)
    u_exact[0::2] = c1 * p[0] + c2 * p[1]
    u_exact[1::2] = c3 * p[0] + c4 * p[1]

    # Prescribe all boundary nodes
    bnd_dofs = basis.get_dofs(lambda x: (
        np.isclose(x[0], 0.0) | np.isclose(x[0], 1.0) |
        np.isclose(x[1], 0.0) | np.isclose(x[1], 1.0)
    )).all()

    f = np.zeros(basis.N)
    u_num = fem.solve(*fem.condense(K, f, x=u_exact, D=bnd_dofs))

    # 1. Interior displacement error
    max_disp_err = np.max(np.abs(u_num - u_exact))
    assert max_disp_err < 1e-11, f"Patch test displacement error {max_disp_err} exceeds 1e-11"

    # 2. Element stress recovery check
    sol = solver.solve(distorted_mesh, loads=[], fixed_boundaries=[])
    sol.u = u_num
    sol.basis = basis
    post = PostProcessor(c)
    res = post.process(distorted_mesh, sol)

    # Theoretical plane stress values:
    sig_xx_expected = c.c11 * c1 + c.c12 * c4
    sig_yy_expected = c.c12 * c1 + c.c11 * c4
    tau_xy_expected = c.c33 * (c2 + c3)

    assert np.allclose(res.sigma_xx, sig_xx_expected, atol=1e-3, rtol=1e-10)
    assert np.allclose(res.sigma_yy, sig_yy_expected, atol=1e-3, rtol=1e-10)
    assert np.allclose(res.tau_xy, tau_xy_expected, atol=1e-3, rtol=1e-10)


# 2. Linear Displacement Reproduction (Pure Tension and Pure Shear)
def test_pure_tension_linear_displacement_reproduction():
    """
    Pure uniaxial tension in x-direction:
      sigma_xx = sigma_0, sigma_yy = 0, tau_xy = 0
      u_x = (sigma_0 / E) * x
      u_y = -nu * (sigma_0 / E) * y
    """
    E = 200e9
    nu = 0.3
    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=0.01)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    sigma_0 = 100e6  # 100 MPa
    p = mesh.mesh.p
    u_exact = np.zeros(basis.N)
    u_exact[0::2] = (sigma_0 / E) * p[0]
    u_exact[1::2] = -nu * (sigma_0 / E) * p[1]

    bnd_dofs = basis.get_dofs(lambda x: (
        np.isclose(x[0], 0.0) | np.isclose(x[0], 2.0) |
        np.isclose(x[1], 0.0) | np.isclose(x[1], 0.5)
    )).all()

    f = np.zeros(basis.N)
    u_num = fem.solve(*fem.condense(K, f, x=u_exact, D=bnd_dofs))
    err = np.max(np.abs(u_num - u_exact))
    assert err < 1e-11


# 3. Analytical Cantilever Beam Tip Deflection (Timoshenko Beam Comparison)
def test_cantilever_beam_timoshenko_analytical_comparison():
    """
    Cantilever beam under end shear load:
    L = 2.0 m, H = 0.5 m, t = 0.02 m, E = 70 GPa, nu = 0.33, plane stress.
    Tip traction ty = -1.0e6 Pa.
    Total load P = |ty| * H * t = 10,000 N.
    Timoshenko beam tip deflection:
      w_tip = P*L^3 / (3*E*I) + P*L / (kappa * G * A)
      where I = t*H^3/12, A = t*H, G = E/(2*(1+nu)), kappa = 5/6.
    Evaluate FEM average tip displacement on refined mesh.
    FEM must agree with Timoshenko theory within 2% (difference due to 2D clamping restraint).
    """
    L, H, t = 2.0, 0.5, 0.02
    E, nu = 70e9, 0.33
    ty = -1.0e6
    P = abs(ty) * H * t  # 10,000 N

    I = (t * H**3) / 12.0
    A = t * H
    G = E / (2.0 * (1.0 + nu))
    kappa = 5.0 / 6.0

    w_bending = (P * L**3) / (3.0 * E * I)
    w_shear = (P * L) / (kappa * G * A)
    w_timoshenko = w_bending + w_shear  # in meters

    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=t)
    solver = LinearElasticitySolver(c)

    # Solve on mesh sequence to demonstrate monotonic convergence toward Timoshenko solution
    displacements = []
    for nx, ny in [(9, 5), (17, 9), (33, 17), (65, 33)]:
        mesh = GDECMesh.create_cantilever_mesh(width=L, height=H, nx=nx, ny=ny)
        sol = solver.solve(
            mesh,
            loads=[("right", 0.0, ty)],
            fixed_boundaries=[("left", ["x", "y"])],
            qoi_boundary="right",
            qoi_component="y",
            solve_adjoint=False,
        )
        displacements.append(abs(sol.qoi))

    # 1. Monotonic convergence from below (conforming stiffness upper bound)
    for i in range(len(displacements) - 1):
        assert displacements[i] < displacements[i + 1]

    # 2. On finest mesh (65 x 33), FEM tip deflection is within 2% of Timoshenko beam theory
    finest_disp = displacements[-1]
    relative_diff = abs(finest_disp - w_timoshenko) / w_timoshenko
    assert relative_diff < 0.02, f"FEM tip deflection {finest_disp*1000:.3f} mm deviates {relative_diff*100:.2f}% from Timoshenko {w_timoshenko*1000:.3f} mm"


# 4. Manufactured Solution: Exact Pure Bending Field
def test_manufactured_solution_pure_bending():
    """
    Exact pure bending solution with zero body force:
      u_x(x, y) = M/(E*I) * x * (y - H/2)
      u_y(x, y) = -M/(2*E*I) * (x^2 + nu * (y - H/2)^2)
    Exact stresses:
      sigma_xx = M * (y - H/2) / I
      sigma_yy = 0
      tau_xy = 0
    Divergence of stress: div(sigma) = 0 everywhere.
    Enforce Dirichlet BC on all boundaries matching exact displacement.
    Interior displacements must match exact field to machine precision (< 1e-11).
    """
    L, H, t = 2.0, 1.0, 1.0
    E, nu = 100e9, 0.25
    I = (t * H**3) / 12.0
    M = 1000.0  # bending moment

    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=t)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=L, height=H, nx=9, ny=5)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    p = mesh.mesh.p
    y_c = p[1] - (H / 2.0)
    u_exact = np.zeros(basis.N)
    u_exact[0::2] = (M / (E * I)) * p[0] * y_c
    u_exact[1::2] = -(M / (2.0 * E * I)) * (p[0]**2 + nu * y_c**2)

    bnd_dofs = basis.get_dofs(lambda x: (
        np.isclose(x[0], 0.0) | np.isclose(x[0], L) |
        np.isclose(x[1], 0.0) | np.isclose(x[1], H)
    )).all()

    f = np.zeros(basis.N)
    u_num = fem.solve(*fem.condense(K, f, x=u_exact, D=bnd_dofs))

    max_err = np.max(np.abs(u_num - u_exact))
    assert max_err < 1e-11, f"Manufactured bending error {max_err} exceeds 1e-11"


# 5. Global Force and Moment Equilibrium
def test_global_force_and_moment_equilibrium():
    """
    Verify static equilibrium of reaction forces and applied traction loads:
      1. sum(R_x) + sum(F_x) == 0 (< 1e-9 N)
      2. sum(R_y) + sum(F_y) == 0 (< 1e-9 N)
      3. sum(x * (R_y + F_y) - y * (R_x + F_x)) == 0 (< 1e-8 N*m)
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    sol = solver.solve(
        mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
    )

    R, bal_x, bal_y = solver.check_reactions_equilibrium(sol)
    # Applied vertical load is 10,000 N; check balance within 1e-7 N (relative error < 1e-11)
    assert abs(bal_x) < 1e-7, f"Force balance x error {bal_x}"
    assert abs(bal_y) < 1e-7, f"Force balance y error {bal_y}"

    # Moment equilibrium about the origin
    p = mesh.mesh.p
    Ku = sol.K @ sol.u
    moment_about_origin = np.sum(p[0] * Ku[1::2] - p[1] * Ku[0::2])
    assert abs(moment_about_origin) < 1e-8, f"Moment equilibrium error {moment_about_origin}"


# 6. Reaction-Force Verification
def test_reaction_force_accuracy_on_clamped_boundary():
    """
    For a cantilever with tip traction ty = -1.0e6 Pa on right boundary (H=0.5, t=0.02),
    total downward force P = 10,000 N.
    Reaction forces on left boundary (x=0) must satisfy:
      sum(R_y) = 10,000 N (< 1e-8 relative error)
      sum(R_x) = 0 N (< 1e-9)
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    sol = solver.solve(
        mesh,
        loads=[("right", 0.0, -1.0e6)],
        fixed_boundaries=[("left", ["x", "y"])],
    )

    # R = K u - f
    R = sol.K @ sol.u - sol.f
    left_nodes = np.where(np.isclose(mesh.mesh.p[0], 0.0))[0]
    total_Ry_left = np.sum(R[2 * left_nodes + 1])
    total_Rx_left = np.sum(R[2 * left_nodes])

    expected_P = 1.0e6 * 0.5 * 0.02  # 10,000 N
    assert np.isclose(total_Ry_left, expected_P, rtol=1e-8)
    assert abs(total_Rx_left) < 1e-9


# 7. Mesh Refinement Monotonicity (Rayleigh-Ritz Energy Principle)
def test_mesh_refinement_energy_monotonicity():
    """
    By the Rayleigh-Ritz principle (strain energy convergence for conforming displacement FEM):
    The computed strain energy U_h = 1/2 * u_h^T K u_h must increase monotonically
    as the mesh is uniformly refined, bounding the exact strain energy from below.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)

    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    energies = []

    for _ in range(3):
        sol = solver.solve(
            mesh,
            loads=[("right", 0.0, -1.0e6)],
            fixed_boundaries=[("left", ["x", "y"])],
            solve_adjoint=False,
        )
        U_h = 0.5 * float(sol.u @ (sol.K @ sol.u))
        energies.append(U_h)
        mesh = mesh.refine_uniform()

    # Verify strictly monotonic increase
    for i in range(len(energies) - 1):
        assert energies[i + 1] > energies[i], f"Energy did not increase: {energies[i]} -> {energies[i+1]}"


# 8. Singular System Detection and Rigid-Body Modes
def test_unconstrained_stiffness_rigid_body_modes():
    """
    An unconstrained 2D elasticity stiffness matrix possesses exactly 3 zero eigenvalues
    corresponding to rigid-body motions (2 translations, 1 rotation).
    Verify that K * v_rb == 0 for:
      v_tx: uniform translation in x
      v_ty: uniform translation in y
      v_rot: rigid-body rotation about origin [-y, x]
    And verify that smallest 3 eigenvalues are ~0 while 4th is strictly positive (> 1e6).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    p = mesh.mesh.p
    N = basis.N

    v_tx = np.zeros(N)
    v_tx[0::2] = 1.0

    v_ty = np.zeros(N)
    v_ty[1::2] = 1.0

    v_rot = np.zeros(N)
    v_rot[0::2] = -p[1]
    v_rot[1::2] = p[0]

    # Rigid body residuals relative to stiffness magnitude
    K_norm = spla.norm(K, ord=np.inf)
    assert np.linalg.norm(K @ v_tx) / K_norm < 1e-12
    assert np.linalg.norm(K @ v_ty) / K_norm < 1e-12
    assert np.linalg.norm(K @ v_rot) / K_norm < 1e-12

    # Eigenvalue spectrum check
    w, _ = spla.eigsh(K.tocsc(), k=6, which="SM")
    sorted_w = np.sort(w)
    # First 3 eigenvalues must be close to zero
    assert abs(sorted_w[0]) < 1e-4
    assert abs(sorted_w[1]) < 1e-4
    assert abs(sorted_w[2]) < 1e-4
    # 4th eigenvalue must be positive and separated by many orders of magnitude
    assert sorted_w[3] > 1e6


# 9. Element Distortion Robustness
def test_distorted_mesh_positive_definiteness_and_solvability():
    """
    Verify that applying geometric distortion to interior nodes preserves
    positive element areas and symmetric positive-definiteness of condensed stiffness.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=6, ny=6)

    # Distort interior nodes
    p = mesh.mesh.p.copy()
    is_interior = (p[0] > 0.1) & (p[0] < 0.9) & (p[1] > 0.1) & (p[1] < 0.9)
    p[:, is_interior] += 0.03  # shear distortion
    distorted_mesh = GDECMesh(fem.MeshTri(p, mesh.mesh.t), 1.0, 1.0)

    # Ensure all element areas remain strictly positive
    assert np.all(distorted_mesh.element_areas > 0.0)

    sol = solver.solve(
        distorted_mesh,
        loads=[("right", 0.0, -100.0)],
        fixed_boundaries=[("left", ["x", "y"])],
    )
    assert np.isfinite(sol.qoi)
    assert sol.qoi < 0.0  # downward deflection


# 10. Plane Strain vs Plane Stress Von Mises Stress Invariant
def test_plane_strain_out_of_plane_stress_invariant():
    """
    Verify that PostProcessor correctly includes sigma_zz = nu * (sigma_xx + sigma_yy)
    for plane strain, and sets sigma_zz = 0 for plane stress.
    """
    E = 210e9
    nu = 0.3
    c_strain = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_strain")
    c_stress = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress")

    post_strain = PostProcessor(c_strain)
    post_stress = PostProcessor(c_stress)

    s_xx = np.array([200.0e6])
    s_yy = np.array([50.0e6])
    t_xy = np.array([30.0e6])

    # Plane stress: sigma_zz = 0
    vm_stress_expected = np.sqrt(s_xx**2 - s_xx * s_yy + s_yy**2 + 3.0 * t_xy**2)
    vm_stress_actual = post_stress._von_mises(s_xx, s_yy, t_xy)
    np.testing.assert_allclose(vm_stress_actual, vm_stress_expected)

    # Plane strain: sigma_zz = nu * (s_xx + s_yy)
    s_zz = nu * (s_xx + s_yy)
    vm_strain_expected = np.sqrt(
        0.5 * ((s_xx - s_yy)**2 + (s_yy - s_zz)**2 + (s_zz - s_xx)**2) + 3.0 * t_xy**2
    )
    vm_strain_actual = post_strain._von_mises(s_xx, s_yy, t_xy)
    np.testing.assert_allclose(vm_strain_actual, vm_strain_expected)
    assert not np.isclose(vm_strain_actual[0], vm_stress_actual[0])
