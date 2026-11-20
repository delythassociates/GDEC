"""
Numerical tests for 2D Linear Elasticity FEM formulation.
Includes matrix symmetry, equilibrium check, and linear elastic patch test.
"""

import numpy as np
import scipy.sparse as sp
import skfem as fem
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver


def test_stiffness_matrix_symmetry():
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    diff = (K - K.T).tocsr()
    assert sp.linalg.norm(diff) < 1e-10


def test_cantilever_solve_and_displacement_direction():
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    loads = [("right", 0.0, -1.0e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, qoi_boundary="right", qoi_component="y")

    assert np.all(np.isfinite(sol.u))
    # Downward load should cause downward deflection
    assert sol.qoi < 0.0
    # Expected order of magnitude for cantilever (~ -1.0 to -2.5 mm)
    assert -5.0 < sol.qoi_mm < -0.1


def test_static_reactions_equilibrium():
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    loads = [("right", 0.0, -1.0e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(mesh, loads=loads, fixed_boundaries=bcs)
    R, bal_x, bal_y = solver.check_reactions_equilibrium(sol)

    # Reaction forces must balance external load to numerical tolerance
    assert abs(bal_x) < 1e-5
    assert abs(bal_y) < 1e-5


def test_linear_elastic_patch_test():
    """
    Standard finite element patch test:
    Under prescribed linear displacement field u_x = c1*x + c2*y, u_y = c3*x + c4*y,
    the strain is constant throughout the domain.
    When Dirichlet BCs are enforced on all outer boundary nodes, the interior node
    displacements must match the exact linear field to machine precision.
    """
    E = 100e9
    nu = 0.25
    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)

    # Distorted/irregular internal mesh
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=1.0, nx=4, ny=4)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    # Linear displacement field coefficients
    c1, c2, c3, c4 = 0.001, 0.002, 0.0015, -0.0005
    p = mesh.mesh.p  # (2, nnodes)
    u_exact = np.zeros(basis.N)
    u_exact[0::2] = c1 * p[0] + c2 * p[1]
    u_exact[1::2] = c3 * p[0] + c4 * p[1]

    # Find all boundary DOFs
    boundary_dofs = basis.get_dofs(lambda x: (
        np.isclose(x[0], 0.0) | np.isclose(x[0], 1.0) |
        np.isclose(x[1], 0.0) | np.isclose(x[1], 1.0)
    )).all()

    f = np.zeros(basis.N)
    u_num = fem.solve(*fem.condense(K, f, x=u_exact, D=boundary_dofs))

    # Error between numerical and exact linear field across all nodes (including interior)
    max_err = np.max(np.abs(u_num - u_exact))
    assert max_err < 1e-12, f"Patch test failed: max error {max_err} exceeds tolerance"
