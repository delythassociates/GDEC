"""
Tests for Stiffness Matrix Diagnostics and Conditioning Analysis (Phase 4.1).
"""

import numpy as np
import scipy.sparse as sp
import pytest

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.matrix_diagnostics import (
    compute_symmetry_defect,
    analyze_stiffness_matrix,
    MatrixDiagnostics,
)
import skfem as fem


def test_symmetry_defect_exact_and_perturbed():
    # Symmetric matrix
    A_sym = np.array([[2.0, -1.0], [-1.0, 3.0]])
    assert compute_symmetry_defect(A_sym) < 1e-15

    # Perturbed matrix
    A_asym = A_sym.copy()
    A_asym[0, 1] += 0.1
    defect = compute_symmetry_defect(A_asym)
    assert 0.01 < defect < 0.1


def test_sparse_and_dense_symmetry_defect_consistency():
    np.random.seed(42)
    dense_M = np.random.randn(20, 20)
    dense_sym = 0.5 * (dense_M + dense_M.T)
    sparse_sym = sp.csr_matrix(dense_sym)

    d_dense = compute_symmetry_defect(dense_sym)
    d_sparse = compute_symmetry_defect(sparse_sym)
    assert abs(d_dense - d_sparse) < 1e-14
    assert d_dense < 1e-14


def test_unconstrained_stiffness_rigid_body_modes():
    """Unconstrained 2D elasticity has 3 rigid-body zero modes."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=0.5, nx=4, ny=3)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    diag = analyze_stiffness_matrix(K, compute_spectrum=True, dense_threshold=500)
    assert diag.is_square is True
    assert diag.is_symmetric is True
    assert diag.null_modes_count == 3
    assert diag.is_positive_definite is False
    assert diag.is_cg_eligible is False
    assert any("rigid-body" in w.lower() for w in diag.warnings)


def test_clamped_cantilever_is_spd_and_cg_eligible():
    """Properly clamped cantilever removes all rigid body modes and is SPD."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=0.5, nx=4, ny=3)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = np.zeros(basis.N)
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])

    K_free, _, _, _ = fem.condense(K, f, D=dofs_fixed)
    diag = analyze_stiffness_matrix(K_free, compute_spectrum=True, dense_threshold=500)

    assert diag.is_square is True
    assert diag.is_symmetric is True
    assert diag.null_modes_count == 0
    assert diag.is_positive_definite is True
    assert diag.is_cg_eligible is True
    assert diag.lambda_min > 0.0
    assert diag.lambda_max > diag.lambda_min
    assert diag.condition_number > 1.0


def test_partially_constrained_system_remains_singular():
    """Fixing only x-displacement leaves vertical translation unconstrained."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=0.5, nx=4, ny=3)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = np.zeros(basis.N)
    # Constrain only x component on left boundary (roller boundary)
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x"])

    K_free, _, _, _ = fem.condense(K, f, D=dofs_fixed)
    diag = analyze_stiffness_matrix(K_free, compute_spectrum=True, dense_threshold=500)

    assert diag.null_modes_count >= 1
    assert diag.is_positive_definite is False
    assert diag.is_cg_eligible is False
    assert any("rigid-body" in w.lower() or "non-positive" in w.lower() for w in diag.warnings)


def test_dense_vs_sparse_eigenvalue_agreement():
    """Verify that sparse ARPACK eigsh agrees with dense exact eigensolver."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=1.0, height=0.5, nx=6, ny=4)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = np.zeros(basis.N)
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])
    K_free, _, _, _ = fem.condense(K, f, D=dofs_fixed)

    diag_dense = analyze_stiffness_matrix(K_free, compute_spectrum=True, dense_threshold=1000)
    diag_sparse = analyze_stiffness_matrix(K_free, compute_spectrum=True, dense_threshold=10)

    assert np.isclose(diag_dense.lambda_min, diag_sparse.lambda_min, rtol=1e-4)
    assert np.isclose(diag_dense.lambda_max, diag_sparse.lambda_max, rtol=1e-4)
    assert np.isclose(diag_dense.condition_number, diag_sparse.condition_number, rtol=1e-3)


def test_diagnostics_on_non_square_and_invalid_matrices():
    rect_mat = sp.csr_matrix(np.zeros((5, 8)))
    diag_rect = analyze_stiffness_matrix(rect_mat)
    assert diag_rect.is_square is False
    assert diag_rect.is_cg_eligible is False

    # Negative diagonal matrix
    neg_mat = sp.diags([-2.0, 3.0, 4.0], format="csr")
    diag_neg = analyze_stiffness_matrix(neg_mat, compute_spectrum=True)
    assert any("non-positive" in w for w in diag_neg.warnings)
    assert diag_neg.is_positive_definite is False


def test_sparse_indefinite_matrix_detection():
    """
    P0 Regression Test:
    500x500 sparse symmetric matrix with positive diagonal entries, but
    indefinite due to eigenvalues -1 and 3 in the first 2x2 block.
    Must be identified as indefinite and NOT CG-eligible by the sparse branch.
    """
    A = sp.eye(500, format="lil")
    A[0, 0] = 1.0
    A[0, 1] = 2.0
    A[1, 0] = 2.0
    A[1, 1] = 1.0
    A = A.tocsr()

    # dense_threshold=400 forces execution through the sparse eigensolver branch
    diag = analyze_stiffness_matrix(A, compute_spectrum=True, dense_threshold=400)

    assert diag.is_square is True
    assert diag.is_symmetric is True
    assert diag.lambda_min is not None
    assert diag.lambda_min < 0.0
    assert np.isclose(diag.lambda_min, -1.0, atol=1e-5)
    assert diag.is_positive_definite is False
    assert diag.is_cg_eligible is False
    assert any("indefinite" in w.lower() for w in diag.warnings)


def test_scale_invariance_across_orders_of_magnitude():
    """
    P1 Regression Test:
    Verify that relative spectral condition number, definiteness, and null mode
    classifications are strictly scale-invariant across 18 orders of magnitude.
    """
    K1 = np.diag([1e-11, 1e-3])
    scales = [1e-12, 1e-6, 1.0, 1e6, 1e12, 1e18]

    for s in scales:
        Ks = s * K1
        diag = analyze_stiffness_matrix(Ks, compute_spectrum=True)
        assert diag.is_positive_definite is True, f"Failed at scale {s}"
        assert diag.is_cg_eligible is True, f"Failed at scale {s}"
        assert diag.has_null_modes is False, f"Failed at scale {s}"
        assert np.isclose(diag.condition_number, 1e8, rtol=1e-4), f"Failed at scale {s}"


def test_sparse_null_mode_multiplicity_and_detection():
    """
    P0 Regression Test:
    Verify that the sparse branch correctly detects all 3 rigid-body modes of an
    unconstrained elasticity system with N > 400 DOFs, and reports null_modes_detected == 3.
    """
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=24, ny=12)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)

    # 576 DOFs: sparse branch evaluated with dense_threshold=400
    diag = analyze_stiffness_matrix(K, compute_spectrum=True, dense_threshold=400)

    assert diag.n_rows == 576
    assert diag.is_symmetric is True
    assert diag.null_modes_detected == 3
    assert diag.has_null_modes is True
    assert diag.exact_nullity is None  # Incomplete spectrum in sparse mode
    assert diag.is_positive_definite is False
    assert diag.is_cg_eligible is False


def test_symmetry_defect_scale_invariance_across_24_orders():
    """
    P1 Regression Test (Phase 4.1.2):
    Verify that relative symmetry defect calculation is strictly scale-invariant
    across at least 24 orders of magnitude (1e-12 to 1e12 and beyond),
    without arbitrary denominator floor distortions.
    """
    from gdec.fem.matrix_diagnostics import compute_symmetry_defect, analyze_stiffness_matrix

    # Asymmetric test matrix from specification
    # K = [[1.0, 1e-8], [0.0, 1.0]]
    K_base = np.array([[1.0, 1e-8], [0.0, 1.0]])
    expected_defect = float(np.linalg.norm(K_base - K_base.T, "fro") / np.linalg.norm(K_base, "fro"))

    # Test scaling factors spanning 28 orders of magnitude
    scale_factors = [1e-14, 1e-12, 1e-8, 1e-4, 1.0, 1e4, 1e8, 1e12, 1e14]

    for c in scale_factors:
        K_scaled = c * K_base
        defect = compute_symmetry_defect(K_scaled)
        np.testing.assert_allclose(
            defect, expected_defect, rtol=1e-12,
            err_msg=f"Symmetry defect changed under scale {c}!"
        )

        # Full analysis must consistently classify as asymmetric
        diag = analyze_stiffness_matrix(K_scaled, sym_tol=1e-10)
        assert diag.is_symmetric is False, f"Scaled matrix at scale {c} was falsely marked symmetric!"
        assert diag.is_cg_eligible is False

    # Symmetric test matrix
    K_sym = np.array([[2.0, 1.0], [1.0, 2.0]])
    for c in scale_factors:
        defect_sym = compute_symmetry_defect(c * K_sym)
        assert defect_sym <= 1e-15
        diag_sym = analyze_stiffness_matrix(c * K_sym, sym_tol=1e-10)
        assert diag_sym.is_symmetric is True
        assert diag_sym.is_positive_definite is True

    # Exact zero matrix
    assert compute_symmetry_defect(np.zeros((3, 3))) == 0.0
    assert compute_symmetry_defect(sp.csr_matrix((4, 4))) == 0.0


def test_nonsymmetric_matrix_no_symmetric_eigensolvers():
    """
    P1 Regression Test (Phase 4.1.2):
    Ensure that nonsymmetric matrices:
    1. Are not analyzed using symmetric eigensolvers (eigvalsh or eigsh).
    2. Do not have imaginary eigenvalue parts discarded to claim positive-definiteness.
    3. Are strictly classified as is_positive_definite=False and is_cg_eligible=False.
    4. Emit clear diagnostic warnings in both dense and sparse paths.
    """
    from gdec.fem.matrix_diagnostics import analyze_stiffness_matrix

    # 1. Dense nonsymmetric matrix with positive real eigenvalue parts
    # K = [[2.0, 5.0], [0.0, 2.0]] -> eigenvalues are 2.0, 2.0 (real positive), but matrix is asymmetric
    K_dense_asym = np.array([[2.0, 5.0], [0.0, 2.0]])
    diag_dense = analyze_stiffness_matrix(K_dense_asym, compute_spectrum=True, dense_threshold=400)
    assert diag_dense.is_symmetric is False
    assert diag_dense.is_positive_definite is False
    assert diag_dense.is_cg_eligible is False
    assert diag_dense.eigenvalue_method == "dense_general"
    assert any("nonsymmetric" in w.lower() for w in diag_dense.warnings)
    assert any("symmetric eigensolvers" in w.lower() for w in diag_dense.warnings)

    # Dense nonsymmetric matrix with complex eigenvalues
    # K = [[1.0, -2.0], [2.0, 1.0]] -> eigenvalues are 1 +/- 2i
    K_complex = np.array([[1.0, -2.0], [2.0, 1.0]])
    diag_comp = analyze_stiffness_matrix(K_complex, compute_spectrum=True, dense_threshold=400)
    assert diag_comp.is_symmetric is False
    assert diag_comp.is_positive_definite is False
    assert any("complex eigenvalues" in w.lower() for w in diag_comp.warnings)

    # 2. Sparse nonsymmetric matrix (N = 500 > dense_threshold = 400)
    # Must NOT call ARPACK eigsh!
    A_sparse_asym = sp.diags([1.0], [1], shape=(500, 500), format="csr") + sp.eye(500, format="csr") * 2.0
    diag_sparse = analyze_stiffness_matrix(A_sparse_asym, compute_spectrum=True, dense_threshold=400)
    assert diag_sparse.is_symmetric is False
    assert diag_sparse.is_positive_definite is False
    assert diag_sparse.is_cg_eligible is False
    assert diag_sparse.eigenvalue_method == "skipped_nonsymmetric"
    assert any("sparse spectrum computation skipped" in w.lower() for w in diag_sparse.warnings)

