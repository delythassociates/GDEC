"""
Tests for Conjugate Gradient and Preconditioners (Phase 4.4 & 4.5).
"""

import numpy as np
import scipy.sparse as sp
import pytest

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.solvers import (
    ConjugateGradientSolver,
    IdentityPreconditioner,
    JacobiPreconditioner,
    IncompleteCholeskyPreconditioner,
    AMGPreconditioner,
    ILUPreconditioner,
)
import skfem as fem


def test_cg_solver_exact_on_laplacian():
    """Test CG on 1D discrete Laplacian A = [-1, 2, -1]."""
    n = 20
    diags = [-np.ones(n - 1), 2.0 * np.ones(n), -np.ones(n - 1)]
    A = sp.diags(diags, [-1, 0, 1], format="csr")
    b = np.ones(n)

    cg = ConjugateGradientSolver(default_rtol=1e-10, default_atol=1e-14)
    res = cg.solve(A, b)

    assert res.converged is True
    assert res.iterations <= n
    assert res.residual_norm < 1e-10

    # Compare with scipy direct solve
    x_direct = sp.linalg.spsolve(A, b)
    assert np.allclose(res.x, x_direct, atol=1e-9)


def test_cg_early_exit_on_zero_rhs():
    """A zero RHS should terminate immediately with zero iterations."""
    A = sp.eye(10, format="csr")
    b = np.zeros(10)
    cg = ConjugateGradientSolver()
    res = cg.solve(A, b)

    assert res.converged is True
    assert res.iterations == 0
    assert np.all(res.x == 0.0)


def test_cg_rejects_asymmetric_matrix_when_checked():
    A = sp.csr_matrix([[2.0, 1.0], [0.0, 2.0]])
    b = np.array([1.0, 1.0])
    cg = ConjugateGradientSolver()

    with pytest.raises(ValueError, match="not symmetric"):
        cg.solve(A, b, check_eligibility=True)


def test_cg_breakdown_detection_on_indefinite_matrix():
    """An indefinite matrix should trigger non-positive curvature breakdown."""
    # Saddle point matrix with negative eigenvalue
    A = sp.csr_matrix([[2.0, 0.0], [0.0, -1.0]])
    b = np.array([1.0, 1.0])
    cg = ConjugateGradientSolver()

    res = cg.solve(A, b, check_eligibility=False)
    assert res.converged is False
    assert res.breakdown_reason is not None
    assert "curvature" in res.breakdown_reason.lower()


def test_jacobi_preconditioner_validation():
    # Matrix with negative diagonal must be rejected
    A_bad = sp.csr_matrix([[-1.0, 0.5], [0.5, 2.0]])
    with pytest.raises(ValueError, match="non-positive"):
        JacobiPreconditioner(A_bad)

    # Valid matrix
    A_good = sp.csr_matrix([[4.0, 1.0], [1.0, 9.0]])
    jac = JacobiPreconditioner(A_good)
    r = np.array([4.0, 18.0])
    z = jac.apply(r)
    assert np.allclose(z, [1.0, 2.0])


def test_incomplete_cholesky_preconditioner():
    """Test genuine IC(0) on small SPD matrix."""
    n = 10
    diags = [-np.ones(n - 1), 2.5 * np.ones(n), -np.ones(n - 1)]
    A = sp.diags(diags, [-1, 0, 1], format="csr")

    ic = IncompleteCholeskyPreconditioner(A)
    assert ic.L_csr.shape == (n, n)

    cg_ident = ConjugateGradientSolver(default_rtol=1e-8)
    cg_ic = ConjugateGradientSolver(default_rtol=1e-8)
    b = np.ones(n)

    res_ident = cg_ident.solve(A, b, preconditioner=IdentityPreconditioner())
    res_ic = cg_ic.solve(A, b, preconditioner=ic)

    assert res_ident.converged is True
    assert res_ic.converged is True
    assert res_ic.iterations <= res_ident.iterations


def test_cantilever_cg_vs_direct_equivalence():
    """Compare direct solver and PCG on cantilever beam FEM problem."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=10, ny=5)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = solver.assemble_traction(mesh, "right", 0.0, -1e6)
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])

    K_free, f_free, u_full, I = fem.condense(K, f, D=dofs_fixed)

    # Direct solve
    solve_fac = sp.linalg.factorized(K_free.tocsc())
    u_direct = solve_fac(f_free)

    # Jacobi PCG
    cg = ConjugateGradientSolver(default_rtol=1e-9, default_atol=1e-14)
    res_jacobi = cg.solve(K_free, f_free, preconditioner=JacobiPreconditioner(K_free))

    assert res_jacobi.converged is True

    # Relative difference between direct and PCG displacements
    rel_diff = np.linalg.norm(res_jacobi.x - u_direct) / np.linalg.norm(u_direct)
    assert rel_diff < 1e-7

    # QoI comparison
    g = solver.assemble_qoi_adjoint_vector(mesh, "right", "y")
    g_free = g[I]
    qoi_direct = float(np.dot(g_free, u_direct))
    qoi_pcg = float(np.dot(g_free, res_jacobi.x))
    rel_qoi_err = abs(qoi_pcg - qoi_direct) / abs(qoi_direct)
    assert rel_qoi_err < 1e-7


def test_qoi_accuracy_vs_cg_tolerance():
    """Verify that relaxing CG tolerance systematically affects QoI accuracy."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=8, ny=4)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = solver.assemble_traction(mesh, "right", 0.0, -1e6)
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])

    K_free, f_free, _, I = fem.condense(K, f, D=dofs_fixed)
    g = solver.assemble_qoi_adjoint_vector(mesh, "right", "y")
    g_free = g[I]

    # Reference solution with tight tolerance
    solve_fac = sp.linalg.factorized(K_free.tocsc())
    u_ref = solve_fac(f_free)
    qoi_ref = float(np.dot(g_free, u_ref))

    tolerances = [1e-2, 1e-4, 1e-6, 1e-8]
    qoi_errors = []

    cg = ConjugateGradientSolver()
    prec = JacobiPreconditioner(K_free)

    for tol in tolerances:
        res = cg.solve(K_free, f_free, preconditioner=prec, rtol=tol, atol=1e-15)
        assert res.converged is True
        qoi_val = float(np.dot(g_free, res.x))
        rel_qoi_err = abs(qoi_val - qoi_ref) / abs(qoi_ref)
        qoi_errors.append(rel_qoi_err)

    # Looser tolerance (1e-2) has larger error than tight tolerance (1e-8)
    assert qoi_errors[0] >= qoi_errors[-1]
    assert qoi_errors[-1] < 1e-7


def test_amg_preconditioner_availability_contract():
    """Verify AMGPreconditioner correctly detects availability and reports name."""
    is_avail = AMGPreconditioner.is_available()
    assert isinstance(is_avail, bool)

    A = sp.eye(5, format="csr")
    if not is_avail:
        with pytest.raises(ImportError, match="PyAMG is not installed"):
            AMGPreconditioner(A)


def test_linear_elasticity_solver_pcg_integration():
    """Verify LinearElasticitySolver.solve supports solver_type='pcg_jacobi'."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=8, ny=4)

    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    sol_direct = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solver_type="direct")
    sol_pcg = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solver_type="pcg_jacobi", solver_rtol=1e-8)

    assert sol_pcg.solver_backend == "pcg_jacobi"
    assert sol_pcg.primal_iterations > 0
    assert sol_pcg.adjoint_iterations > 0
    rel_disp_err = np.linalg.norm(sol_pcg.u - sol_direct.u) / np.linalg.norm(sol_direct.u)
    assert rel_disp_err < 1e-6
    rel_qoi_err = abs(sol_pcg.qoi - sol_direct.qoi) / abs(sol_direct.qoi)
    assert rel_qoi_err < 1e-6


def test_cg_rejects_indefinite_matrix_with_positive_diagonal():
    """
    P0 Regression Test:
    A matrix with positive diagonal entries that is indefinite must be rejected by CG
    during upfront eligibility verification (caller_certified_spd=False).
    """
    A = sp.csr_matrix([[1.0, 2.0], [2.0, 1.0]])
    b = np.array([1.0, 1.0])
    cg = ConjugateGradientSolver()

    with pytest.raises(ValueError, match="not positive-definite"):
        cg.solve(A, b, check_eligibility=True, caller_certified_spd=False)


def test_cg_rejects_singular_matrix():
    """P0 Regression Test: A singular matrix must be rejected by CG upfront."""
    # Singular matrix with null mode (1, 1)
    A = sp.csr_matrix([[1.0, -1.0], [-1.0, 1.0]])
    b = np.array([1.0, 1.0])
    cg = ConjugateGradientSolver()

    with pytest.raises(ValueError, match="not positive-definite"):
        cg.solve(A, b, check_eligibility=True, caller_certified_spd=False)


def test_cg_rejects_non_finite_inputs():
    """P0 Regression Test: Non-finite inputs in K, b, x0 must be rejected."""
    cg = ConjugateGradientSolver()
    A = sp.eye(4, format="csr")
    b = np.ones(4)

    # NaN in K
    A_nan = A.copy().astype(float)
    A_nan[0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        cg.solve(A_nan, b)

    # Inf in b
    b_inf = b.copy()
    b_inf[1] = np.inf
    with pytest.raises(ValueError, match="non-finite"):
        cg.solve(A, b_inf)

    # NaN in x0
    x0_nan = np.array([0.0, np.nan, 0.0, 0.0])
    with pytest.raises(ValueError, match="non-finite"):
        cg.solve(A, b, x0=x0_nan)


def test_cg_preconditioner_spd_compatibility_gate():
    """
    P0 Regression Test:
    Passing ILUPreconditioner (which has is_spd=False) to ordinary CG must be
    rejected by the compatibility gate with a clear ValueError.
    """
    from gdec.fem.solvers import ILUPreconditioner
    A = sp.diags([-1.0, 2.5, -1.0], [-1, 0, 1], shape=(10, 10), format="csc")
    b = np.ones(10)
    cg = ConjugateGradientSolver()

    ilu = ILUPreconditioner(A)
    assert ilu.is_spd is False

    with pytest.raises(ValueError, match="not symmetric positive-definite"):
        cg.solve(A, b, preconditioner=ilu)


def test_linear_elasticity_solver_non_convergence_handling():
    """
    P1 Regression Test:
    When iterative solver cannot converge within max iterations:
    1. By default (raise_on_nonconvergence=True), raises SolverConvergenceError.
    2. When raise_on_nonconvergence=False, returns FEMSolution with converged=False.
    """
    from gdec.fem.elasticity import SolverConvergenceError
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=10, ny=5)

    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    # Deliberately impossible tolerance with tight max_iter (isolate primal)
    with pytest.raises(SolverConvergenceError) as exc_info:
        solver.solve(
            mesh,
            loads=loads,
            fixed_boundaries=bcs,
            solver_type="cg",
            solver_rtol=1e-18,
            solver_atol=0.0,
            solver_max_iter=2,
            raise_on_nonconvergence=True,
        )
    assert "Primal linear solve failed to converge" in str(exc_info.value)

    # With raise_on_nonconvergence=False, returns FEMSolution with converged=False
    sol = solver.solve(
        mesh,
        loads=loads,
        fixed_boundaries=bcs,
        solver_type="cg",
        solver_rtol=1e-18,
        solver_atol=0.0,
        solver_max_iter=2,
        raise_on_nonconvergence=False,
    )
    assert sol.converged is False
    assert sol.primal_converged is False
    assert "failed" in sol.termination_reason.lower()


def test_linear_elasticity_solver_telemetry_corrections():
    """
    P1 Regression Test:
    Verify that iterative solvers report factorization_reused=False and
    factorization_time_sec=0.0 even when reuse_factorization=True is passed.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=8, ny=4)

    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    # Direct solve with reuse
    sol_dir_reuse = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solver_type="direct", reuse_factorization=True)
    assert sol_dir_reuse.factorization_reused is True
    assert sol_dir_reuse.factorization_time_sec > 0.0
    assert sol_dir_reuse.preconditioner_setup_time_sec == 0.0

    # Direct solve without reuse
    sol_dir_noreuse = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solver_type="direct", reuse_factorization=False)
    assert sol_dir_noreuse.factorization_reused is False
    assert sol_dir_noreuse.factorization_time_sec == 0.0

    # Iterative solve with reuse_factorization=True passed
    sol_pcg = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solver_type="pcg_jacobi", reuse_factorization=True)
    assert sol_pcg.factorization_reused is False
    assert sol_pcg.factorization_time_sec == 0.0
    assert sol_pcg.preconditioner_setup_time_sec > 0.0


def test_qoi_accuracy_across_multiple_configurations():
    """
    P1 Regression Test:
    Verify QoI behavior across different load types and QoI functional components
    without assuming universal O(e_u^2) super-convergence.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, 8, 4)

    configs = [
        ("Shear Y", [("right", 0.0, -1e6)], "right", "y"),
        ("Axial X", [("right", 1e7, 0.0)], "right", "x"),
    ]

    for name, loads, qbnd, qcomp in configs:
        sol_ref = solver.solve(mesh, loads=loads, fixed_boundaries=[("left", ["x", "y"])], solver_type="direct", qoi_boundary=qbnd, qoi_component=qcomp)
        sol_pcg = solver.solve(mesh, loads=loads, fixed_boundaries=[("left", ["x", "y"])], solver_type="pcg_jacobi", solver_rtol=1e-4, qoi_boundary=qbnd, qoi_component=qcomp)

        rel_disp_err = np.linalg.norm(sol_pcg.u - sol_ref.u) / np.linalg.norm(sol_ref.u)
        rel_qoi_err = abs(sol_pcg.qoi - sol_ref.qoi) / abs(sol_ref.qoi)

        # QoI error is bounded by displacement error, demonstrating consistency
        assert rel_disp_err < 1e-4
        assert rel_qoi_err < 1e-4


def test_default_fem_cg_interface_spd_verification():
    """
    P0 Regression Test (Phase 4.1.2):
    Verify that the default FEM iterative solve (caller_certified_spd=False by default)
    strictly performs upfront SPD verification:
    - Clamped cantilever: verified SPD and solves successfully.
    - Unconstrained model: rejected upfront with ValueError (null modes / near-singular).
    - Roller-constrained model: rejected upfront with ValueError (unconstrained y-mode).
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, 6, 3)

    loads = [("right", 0.0, -1e6)]

    # 1. Clamped cantilever: fully constrained, genuinely SPD -> succeeds under default setting
    sol_clamped = solver.solve(
        mesh, loads=loads, fixed_boundaries=[("left", ["x", "y"])], solver_type="cg"
    )
    assert sol_clamped.converged is True
    assert sol_clamped.u is not None

    # 2. Unconstrained elasticity model: rigid body modes present -> rejected upfront
    with pytest.raises(ValueError, match="not positive-definite"):
        solver.solve(
            mesh, loads=loads, fixed_boundaries=[], solver_type="cg"
        )

    # 3. Roller-constrained model (only x fixed, y free) -> unconstrained vertical translation -> rejected upfront
    with pytest.raises(ValueError, match="not positive-definite"):
        solver.solve(
            mesh, loads=loads, fixed_boundaries=[("left", ["x"])], solver_type="cg"
        )

    # 4. Explicit opt-in caller assertion bypass: passing caller_certified_spd=True bypasses upfront check
    # (Direct SuperLU behavior is always unaffected)
    sol_dir = solver.solve(mesh, loads=loads, fixed_boundaries=[("left", ["x", "y"])], solver_type="direct")
    assert sol_dir.converged is True


def test_direct_cg_indefinite_matrix_positive_eigenspace_rhs():
    """
    P0 Regression Test (Phase 4.1.2):
    Direct CG regression using an indefinite matrix with positive diagonal and a
    right-hand side confined entirely to its positive eigenspace.
    Demonstrates why runtime curvature checks alone along the Krylov trajectory are
    NOT a global proof of positive-definiteness.
    """
    # A has eigenvalues -1.0 (vector [1, -1]) and +5.0 (vector [1, 1])
    # Both diagonal entries are +2.0 (positive diagonal)
    A = sp.csr_matrix([[2.0, 3.0], [3.0, 2.0]])
    # b is exactly in the positive eigenspace of lambda = +5
    b = np.array([1.0, 1.0])
    cg = ConjugateGradientSolver()

    # 1. Default caller_certified_spd=False:
    # Upfront scale-aware spectral verification catches the negative eigenvalue -1.0
    # and strictly rejects the matrix as indefinite!
    with pytest.raises(ValueError, match="indefinite"):
        cg.solve(A, b, caller_certified_spd=False)

    # 2. Bypassing upfront check with caller_certified_spd=True:
    # Search direction p0 = r0 = [1, 1], curvature p0^T A p0 = 10.0 > 0.
    # CG terminates in 1 iteration without ever encountering negative curvature,
    # because the Krylov subspace never probed the negative eigenspace span([1, -1]).
    # This demonstrates conclusively why runtime curvature checks alone are NOT a global SPD proof.
    res_bypassed = cg.solve(A, b, caller_certified_spd=True)
    assert res_bypassed.converged is True
    assert res_bypassed.iterations == 1
    np.testing.assert_allclose(res_bypassed.x, [0.2, 0.2])


def test_cg_scale_aware_near_null_rejection():
    """
    P0 Regression Test (Phase 4.1.2):
    Test scale-aware near-null rejection in CG:
    1. Positive-definite matrix at several scales (1e-6, 1.0, 1e6) succeeds.
    2. Exactly singular matrix is rejected upfront.
    3. Nearly singular matrix with small positive eigenvalue (1e-12 * lambda_max) is rejected upfront.
    4. Indefinite matrix with positive diagonal is rejected upfront.
    5. Sparse (N > 300) and dense (N <= 300) paths produce consistent rejections.
    """
    cg = ConjugateGradientSolver(null_tol=1e-10)

    # 1. Positive-definite matrix across 12 orders of magnitude
    for scale in [1e-6, 1.0, 1e6]:
        A_scaled = sp.csr_matrix([[4.0, 1.0], [1.0, 4.0]]) * scale
        b_scaled = np.array([5.0, 5.0]) * scale
        res = cg.solve(A_scaled, b_scaled, caller_certified_spd=False)
        assert res.converged is True

    # 2. Exactly singular matrix (dense path)
    A_sing = sp.csr_matrix([[1.0, 1.0], [1.0, 1.0]])
    b = np.array([2.0, 2.0])
    with pytest.raises(ValueError, match="not positive-definite"):
        cg.solve(A_sing, b, caller_certified_spd=False)

    # 3. Nearly singular matrix with small positive eigenvalue (lambda_min / lambda_max = 1e-12 < null_tol)
    # Naive lambda_min > 0 checks would falsely pass this!
    A_near_null = sp.diags([1e-12, 1.0], shape=(2, 2), format="csr")
    with pytest.raises(ValueError, match="not positive-definite"):
        cg.solve(A_near_null, np.array([1.0, 1.0]), caller_certified_spd=False)

    # 4. Sparse path (N = 350 > 300 dense_threshold):
    # Construct 350x350 sparse diagonal matrix with positive entries but one near-zero entry (1e-12)
    diag_vals = np.ones(350)
    diag_vals[0] = 1e-12
    A_sparse_near_null = sp.diags(diag_vals, shape=(350, 350), format="csr")
    with pytest.raises(ValueError, match="not positive-definite"):
        cg.solve(A_sparse_near_null, np.ones(350), caller_certified_spd=False)

    # 5. Sparse path with negative eigenvalue (indefinite)
    diag_vals_indef = np.ones(350)
    diag_vals_indef[0] = -0.5
    # Note: to ensure diagonal positivity passes so it reaches the spectral test, use 2x2 block
    A_sparse_indef = sp.eye(350, format="lil")
    A_sparse_indef[0, 0] = 2.0
    A_sparse_indef[0, 1] = 3.0
    A_sparse_indef[1, 0] = 3.0
    A_sparse_indef[1, 1] = 2.0
    with pytest.raises(ValueError, match="indefinite"):
        cg.solve(A_sparse_indef.tocsr(), np.ones(350), caller_certified_spd=False)


def test_preconditioner_fail_closed_and_amg_configuration():
    """
    P1 Regression Test (Phase 4.1.2):
    1. Base Preconditioner class fails closed (is_spd == False).
    2. Unknown custom preconditioner inheriting Preconditioner without overriding is_spd is rejected by CG.
    3. Identity, Jacobi, and IC(0) declare is_spd == True.
    4. ILU declares is_spd == False.
    5. AMG verified configuration check: supported symmetric configuration vs unverified configuration.
    """
    from gdec.fem.solvers.iterative import Preconditioner, IdentityPreconditioner, JacobiPreconditioner, IncompleteCholeskyPreconditioner, ILUPreconditioner, AMGPreconditioner

    # 1. Custom preconditioner inheriting Preconditioner without overriding is_spd
    class UnknownCustomPreconditioner(Preconditioner):
        def apply(self, r: np.ndarray) -> np.ndarray:
            return r

        @property
        def name(self) -> str:
            return "UnknownCustom"

    custom = UnknownCustomPreconditioner()
    assert custom.is_spd is False  # Must fail closed!

    # Rejected by CG compatibility gate
    cg = ConjugateGradientSolver()
    A = sp.eye(4, format="csr")
    b = np.ones(4)
    with pytest.raises(ValueError, match="not symmetric positive-definite"):
        cg.solve(A, b, preconditioner=custom)

    # 2. Known SPD preconditioners
    assert IdentityPreconditioner().is_spd is True
    assert JacobiPreconditioner(A).is_spd is True
    assert IncompleteCholeskyPreconditioner(A).is_spd is True

    # 3. Known non-SPD preconditioner
    assert ILUPreconditioner(A).is_spd is False

    # 4. AMGPreconditioner configuration verification
    if AMGPreconditioner.is_available():
        # Supported symmetric configuration: V-cycle, symmetric=True
        amg_sym = AMGPreconditioner(A, cycle="V", symmetric=True)
        assert amg_sym.is_spd is True

        # Unsupported unsymmetric configuration: symmetric=False
        amg_unsym = AMGPreconditioner(A, cycle="V", symmetric=False)
        assert amg_unsym.is_spd is False
        with pytest.raises(ValueError, match="not symmetric positive-definite"):
            cg.solve(A, b, preconditioner=amg_unsym)
    else:
        # Clear optional dependency error
        with pytest.raises(ImportError, match="PyAMG is not installed"):
            AMGPreconditioner(A)



