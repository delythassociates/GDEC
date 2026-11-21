"""
Unit and integration tests for GDEC ExecutionBackend protocol and CPUBackend.
"""

import pytest
import numpy as np
import scipy.sparse as sp

from gdec.core.backend import (
    ExecutionBackend,
    CPUBackend,
    CUDABackend,
    get_backend,
    BackendCapabilities,
    CapabilityStatus,
    BackendNotAvailableError,
    UnsupportedCapabilityError,
    InputValidationError,
    NumericalBackendError,
    detect_cuda_capability,
)


def test_cpu_backend_protocol_conformance():
    """Verify CPUBackend conforms to ExecutionBackend protocol."""
    backend = CPUBackend()
    assert isinstance(backend, ExecutionBackend)
    assert backend.name == "cpu"
    assert backend.is_available is True
    assert backend.capabilities.sparse_matvec is True
    assert backend.capabilities.sparse_direct_solve is True
    assert backend.capabilities.multiple_rhs is True
    assert backend.capabilities.fem_assembly is False


def test_get_backend_factory():
    """Verify get_backend factory resolution."""
    cpu = get_backend("cpu")
    assert isinstance(cpu, CPUBackend)

    with pytest.raises(ValueError, match="Unknown backend 'invalid_name'"):
        get_backend("invalid_name")


def test_cpu_device_info():
    """Verify CPUBackend device diagnostic information."""
    backend = CPUBackend()
    info = backend.get_device_info()
    assert info["backend"] == "cpu"
    assert "processor" in info
    assert "cpu_count_physical" in info
    assert info["total_ram_gb"] > 0
    assert "libraries" in info
    assert "numpy" in info["libraries"]


def test_cpu_spmv_correctness():
    """Test sparse matrix-vector multiplication against known values."""
    backend = CPUBackend()
    A = sp.csr_matrix([[2.0, -1.0, 0.0], [-1.0, 3.0, -1.0], [0.0, -1.0, 2.0]])
    x = np.array([1.0, 2.0, 3.0])

    y = backend.spmv(A, x)
    expected = A @ x
    np.testing.assert_allclose(y, expected, rtol=1e-12)


def test_cpu_spmv_validation():
    """Test spmv input validation and error handling."""
    backend = CPUBackend()
    A = sp.csr_matrix([[2.0, -1.0], [-1.0, 2.0]])

    # Dimension mismatch
    with pytest.raises(InputValidationError, match="Dimension mismatch"):
        backend.spmv(A, np.array([1.0, 2.0, 3.0]))

    # Non-1D vector
    with pytest.raises(InputValidationError, match="Expected 1D vector"):
        backend.spmv(A, np.array([[1.0], [2.0]]))

    # Non-finite vector
    with pytest.raises(NumericalBackendError, match="non-finite values"):
        backend.spmv(A, np.array([1.0, np.nan]))

    # Dense matrix passed instead of sparse
    with pytest.raises(InputValidationError, match="must be a scipy.sparse matrix"):
        backend.spmv(np.array([[1.0, 0.0], [0.0, 1.0]]), np.array([1.0, 2.0]))


def test_cpu_solve_direct_correctness():
    """Test sparse direct solve A x = b."""
    backend = CPUBackend()
    A = sp.csr_matrix([[4.0, 1.0, 0.0], [1.0, 4.0, 1.0], [0.0, 1.0, 4.0]])
    b = np.array([5.0, 6.0, 5.0])

    x = backend.solve_direct(A, b)
    res = np.linalg.norm(b - A @ x)
    assert res < 1e-12
    np.testing.assert_allclose(x, np.array([1.0, 1.0, 1.0]), rtol=1e-10)


def test_cpu_solve_direct_validation():
    """Test solve_direct validation."""
    backend = CPUBackend()
    A = sp.csr_matrix([[1.0, 2.0], [3.0, 4.0]])

    # Non-square matrix
    A_rect = sp.csr_matrix([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    with pytest.raises(InputValidationError, match="must be square"):
        backend.solve_direct(A_rect, np.array([1.0, 2.0]))

    # Dimension mismatch
    with pytest.raises(InputValidationError, match="Dimension mismatch"):
        backend.solve_direct(A, np.array([1.0, 2.0, 3.0]))

    # Non-finite RHS
    with pytest.raises(NumericalBackendError, match="contains NaN or Inf"):
        backend.solve_direct(A, np.array([1.0, np.inf]))


def test_cpu_solve_multiple_rhs():
    """Test multiple right-hand side solve via single LU factorization."""
    backend = CPUBackend()
    A = sp.csr_matrix([[5.0, 1.0, 0.0], [1.0, 5.0, 1.0], [0.0, 1.0, 5.0]])
    B = np.array([
        [5.0, 1.0, 0.0],
        [6.0, 5.0, 1.0],
        [5.0, 1.0, 5.0]
    ])

    X = backend.solve_multiple_rhs(A, B)
    assert X.shape == (3, 3)

    # Compare each column with separate solve_direct
    for j in range(3):
        x_single = backend.solve_direct(A, B[:, j])
        np.testing.assert_allclose(X[:, j], x_single, rtol=1e-12)


def test_cpu_solve_cg():
    """Test Conjugate Gradient solver with strict SPD verification."""
    backend = CPUBackend()
    # SPD Matrix
    A = sp.csr_matrix([[4.0, 1.0], [1.0, 3.0]])
    b = np.array([5.0, 4.0])

    x, info = backend.solve_cg(A, b, rtol=1e-9)
    assert info["converged"] is True
    assert info["residual_norm"] < 1e-8
    np.testing.assert_allclose(x, np.array([1.0, 1.0]), rtol=1e-7)


def test_cpu_solve_cg_rejects_non_spd():
    """Test that CG rejects non-symmetric and indefinite matrices."""
    backend = CPUBackend()

    # Non-symmetric matrix
    A_non_sym = sp.csr_matrix([[4.0, 2.0], [1.0, 3.0]])
    with pytest.raises(NumericalBackendError, match="not symmetric"):
        backend.solve_cg(A_non_sym, np.array([1.0, 1.0]))

    # Non-positive diagonal
    A_zero_diag = sp.csr_matrix([[0.0, 1.0], [1.0, 3.0]])
    with pytest.raises(NumericalBackendError, match="non-positive"):
        backend.solve_cg(A_zero_diag, np.array([1.0, 1.0]))

    # Symmetric indefinite matrix with positive diagonal (Counterexample: A = [[1, 2], [2, 1]])
    # diag = [1, 1] > 0, but eigenvalues are -1 and 3
    A_indef = sp.csr_matrix([[1.0, 2.0], [2.0, 1.0]])
    with pytest.raises(NumericalBackendError, match="Matrix A is indefinite"):
        backend.solve_cg(A_indef, np.array([1.0, 1.0]), caller_certified_spd=False)

    # Allowed when caller explicitly certifies SPD
    x_cert, info_cert = backend.solve_cg(A_indef, np.array([3.0, 3.0]), caller_certified_spd=True)
    assert np.all(np.isfinite(x_cert))


def test_cpu_evaluate_parameter_scaling_batch():
    """Test vectorized analytical scaling on CPU."""
    backend = CPUBackend()
    E_vals = np.array([200e3, 100e3, 50e3])
    P_vals = np.array([1.0, 2.0, 0.5])
    J_0 = 10.0
    E_0 = 200e3
    P_0 = 1.0

    # J(E, P) = (P / P_0) * (E_0 / E) * J_0
    # Sample 0: (1.0 / 1.0) * (200 / 200) * 10 = 10.0
    # Sample 1: (2.0 / 1.0) * (200 / 100) * 10 = 40.0
    # Sample 2: (0.5 / 1.0) * (200 / 50) * 10 = 20.0
    expected = np.array([10.0, 40.0, 20.0])

    results = backend.evaluate_parameter_scaling_batch(E_vals, P_vals, J_0, E_0, P_0)
    np.testing.assert_allclose(results, expected, rtol=1e-12)


def test_cpu_evaluate_parameter_scaling_validation():
    """Test validation on parameter scaling inputs."""
    backend = CPUBackend()
    with pytest.raises(InputValidationError, match="strictly positive"):
        backend.evaluate_parameter_scaling_batch([1.0], [1.0], J_0=1.0, E_0=-10.0, P_0=1.0)

    with pytest.raises(InputValidationError, match="cannot be zero"):
        backend.evaluate_parameter_scaling_batch([1.0], [1.0], J_0=1.0, E_0=10.0, P_0=0.0)

    with pytest.raises(NumericalBackendError, match="strictly positive"):
        backend.evaluate_parameter_scaling_batch([-1.0], [1.0], J_0=1.0, E_0=10.0, P_0=1.0)


def test_cpu_solve_cg_edge_cases():
    """Test solver edge cases: zero RHS, empty system, dimension mismatch, and SPD status telemetry."""
    import scipy.sparse.linalg as spla
    backend = CPUBackend()
    n = 10
    A = sp.diags([np.full(n, 4.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)], [0, -1, 1], format="csr")

    # Zero RHS edge case
    b_zero = np.zeros(n)
    x_zero, info_zero = backend.solve_cg(A, b_zero)
    assert info_zero["converged"] is True
    assert info_zero["iterations"] == 0
    assert info_zero["residual_norm"] == 0.0
    np.testing.assert_allclose(x_zero, 0.0)

    # Preconditioner dimension mismatch
    M_bad = spla.LinearOperator((n + 2, n + 2), matvec=lambda v: v)
    M_bad.is_spd = True
    with pytest.raises(InputValidationError, match="Preconditioner shape"):
        backend.solve_cg(A, np.ones(n), M=M_bad)

    # Empty 0x0 system
    A_empty = sp.csr_matrix((0, 0))
    with pytest.raises(InputValidationError, match="empty 0x0 system"):
        backend.solve_cg(A_empty, np.array([]))

    # Invalid max_iter
    with pytest.raises(InputValidationError, match="positive integer"):
        backend.solve_cg(A, np.ones(n), max_iter=-5)

    # Verified SPD vs Caller Assumed SPD telemetry
    _, info_verified = backend.solve_cg(A, np.ones(n), caller_certified_spd=False)
    assert info_verified["spd_status"] == "VERIFIED_SPD"

    _, info_assumed = backend.solve_cg(A, np.ones(n), caller_certified_spd=True)
    assert info_assumed["spd_status"] == "CALLER_ASSUMED_SPD"
