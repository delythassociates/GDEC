"""
Unit and parity tests for GDEC CUDABackend prototype.
Tests numerical agreement with CPU reference, device synchronization,
and graceful degradation when CUDA is unavailable.
"""

import pytest
import numpy as np
import scipy.sparse as sp

from gdec.core.backend import (
    CUDABackend,
    CPUBackend,
    get_backend,
    ExecutionBackend,
    detect_cuda_capability,
    CUDADetectionStatus,
    UnsupportedCapabilityError,
    InputValidationError,
    NumericalBackendError,
)

cuda_detection = detect_cuda_capability()
CUDA_AVAILABLE = cuda_detection.is_operational


@pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA GPU hardware not operational on this host")
class TestCUDABackendOperational:
    """Tests executing directly on physical NVIDIA GPU hardware."""

    def test_cuda_protocol_conformance(self):
        backend = CUDABackend()
        assert isinstance(backend, ExecutionBackend)
        assert backend.name == "cuda"
        assert backend.is_available is True
        assert backend.capabilities.sparse_matvec is True
        assert backend.capabilities.device_resident_memory is True
        assert backend.capabilities.fem_assembly is False
        assert backend.capabilities.sparse_direct_solve is False

    def test_cuda_device_info(self):
        backend = CUDABackend()
        info = backend.get_device_info()
        assert info["backend"] == "cuda"
        assert info["is_available"] is True
        assert "NVIDIA" in info["device_name"]
        assert info["total_vram_mb"] > 1000.0

    def test_cuda_spmv_parity_with_cpu(self):
        """Test numerical parity of GPU SpMV vs CPU SciPy SpMV."""
        cpu = CPUBackend()
        cuda = CUDABackend()

        # Create structured tridiagonal SPD matrix
        n = 1000
        diags = [np.full(n, 2.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)]
        A = sp.diags(diags, [0, -1, 1], format="csr", dtype=np.float64)
        x = np.sin(np.linspace(0.0, 10.0, n))

        y_cpu = cpu.spmv(A, x)
        y_cuda = cuda.spmv(A, x)

        rel_diff = np.linalg.norm(y_cuda - y_cpu) / np.linalg.norm(y_cpu)
        assert rel_diff < 1e-10
        np.testing.assert_allclose(y_cuda, y_cpu, rtol=1e-10, atol=1e-14)

    def test_cuda_resident_execution(self):
        """Test execution when data is already resident on GPU device."""
        import cupy as cp
        import cupyx.scipy.sparse as cp_sp

        cuda = CUDABackend()
        A_sp = sp.csr_matrix([[3.0, 1.0], [1.0, 2.0]], dtype=np.float64)
        x_np = np.array([2.0, 4.0], dtype=np.float64)

        # Pre-load onto GPU
        A_gpu = cp_sp.csr_matrix(A_sp)
        x_gpu = cp.asarray(x_np)

        # Execute with host_output=False -> remains on GPU
        y_gpu = cuda.spmv(A_gpu, x_gpu, host_output=False)
        assert isinstance(y_gpu, cp.ndarray)

        y_host = cuda.to_host(y_gpu)
        np.testing.assert_allclose(y_host, A_sp @ x_np, rtol=1e-12)

    def test_cuda_unsupported_direct_solve_raises(self):
        """Verify that sparse direct solve on GPU raises UnsupportedCapabilityError."""
        cuda = CUDABackend()
        A = sp.csr_matrix([[1.0, 0.0], [0.0, 1.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(UnsupportedCapabilityError, match="does not support sparse direct solves"):
            cuda.solve_direct(A, b)

    def test_cuda_cg_parity_with_cpu(self):
        """Test GPU CG solver agreement with CPU on an SPD system."""
        cpu = CPUBackend()
        cuda = CUDABackend()

        n = 100
        A = sp.diags([np.full(n, 4.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)], [0, -1, 1], format="csr")
        b = np.ones(n, dtype=np.float64)

        x_cpu, info_cpu = cpu.solve_cg(A, b, rtol=1e-8)
        x_cuda, info_cuda = cuda.solve_cg(A, b, rtol=1e-8)

        assert info_cpu["converged"] is True
        assert info_cuda["converged"] is True

        rel_diff = np.linalg.norm(x_cuda - x_cpu) / np.linalg.norm(x_cpu)
        assert rel_diff < 1e-6
        np.testing.assert_allclose(x_cuda, x_cpu, rtol=1e-6)

    def test_cuda_batched_analytical_scaling(self):
        """Test GPU batched analytical parameter scaling matches CPU results."""
        cpu = CPUBackend()
        cuda = CUDABackend()

        np.random.seed(42)
        n_samples = 5000
        E_vals = np.random.uniform(150e3, 250e3, size=n_samples)
        P_vals = np.random.uniform(500.0, 1500.0, size=n_samples)
        J_0 = 4.25
        E_0 = 200e3
        P_0 = 1000.0

        res_cpu = cpu.evaluate_parameter_scaling_batch(E_vals, P_vals, J_0, E_0, P_0)
        res_cuda = cuda.evaluate_parameter_scaling_batch(E_vals, P_vals, J_0, E_0, P_0)

        np.testing.assert_allclose(res_cuda, res_cpu, rtol=1e-12)

    def test_cuda_solve_cg_indefinite_rejection(self):
        """Verify CUDA CG rejects symmetric indefinite matrix unless certified."""
        cuda = CUDABackend()
        # A = [[1, 2], [2, 1]] has diag > 0, but is indefinite (lambda = -1, 3)
        A_indef = sp.csr_matrix([[1.0, 2.0], [2.0, 1.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(NumericalBackendError, match="Matrix A is indefinite"):
            cuda.solve_cg(A_indef, b, caller_certified_spd=False)

        # Allowed with explicit caller certification
        x_cert, info_cert = cuda.solve_cg(A_indef, np.array([3.0, 3.0]), caller_certified_spd=True)
        assert np.all(np.isfinite(x_cert))

    def test_cuda_solve_cg_preconditioner_validation(self):
        """Verify CUDA CG rejects CPU LinearOperator and accepts 'jacobi'."""
        import scipy.sparse.linalg as spla
        cuda = CUDABackend()
        n = 20
        A = sp.diags([np.full(n, 4.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)], [0, -1, 1], format="csr")
        b = np.ones(n)

        # Rejects CPU LinearOperator
        cpu_M = spla.LinearOperator(A.shape, matvec=lambda v: v)
        with pytest.raises(UnsupportedCapabilityError, match="CPU operator"):
            cuda.solve_cg(A, b, M=cpu_M, caller_certified_spd=True)

        # Accepts 'jacobi' preconditioner string
        x_jacobi, info_jacobi = cuda.solve_cg(A, b, M="jacobi", caller_certified_spd=True)
        assert info_jacobi["converged"] is True
        res_norm = np.linalg.norm(b - A @ x_jacobi) / np.linalg.norm(b)
        assert res_norm < 1e-6

    def test_cuda_gpu_custom_linear_operator_contract(self):
        """Verify GPU LinearOperator must declare is_spd=True."""
        import cupy as cp
        import cupyx.scipy.sparse.linalg as cp_spla
        cuda = CUDABackend()
        n = 25
        A = sp.diags([np.full(n, 4.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)], [0, -1, 1], format="csr")
        b = np.ones(n)

        # GPU LinearOperator without is_spd -> MUST BE REJECTED
        gpu_M_untrusted = cp_spla.LinearOperator((n, n), matvec=lambda v: v, dtype=cp.float64)
        with pytest.raises(NumericalBackendError, match="does not declare is_spd=True"):
            cuda.solve_cg(A, b, M=gpu_M_untrusted, caller_certified_spd=True)

        # GPU LinearOperator with is_spd=True -> ACCEPTED
        gpu_M_trusted = cp_spla.LinearOperator((n, n), matvec=lambda v: v, dtype=cp.float64)
        gpu_M_trusted.is_spd = True
        x_sol, info = cuda.solve_cg(A, b, M=gpu_M_trusted, caller_certified_spd=True)
        assert info["converged"] is True
        assert info["preconditioner_status"] == "CALLER_ASSUMED_SPD_GPU_OPERATOR"

    def test_cuda_solve_cg_edge_cases_and_telemetry(self):
        """Test zero RHS, empty system, dimension mismatch, and data residency telemetry on GPU."""
        import cupy as cp
        import cupyx.scipy.sparse as cp_sp
        cuda = CUDABackend()
        n = 15
        A_sp = sp.diags([np.full(n, 4.0), np.full(n - 1, -1.0), np.full(n - 1, -1.0)], [0, -1, 1], format="csr")

        # Zero RHS
        x_z, info_z = cuda.solve_cg(A_sp, np.zeros(n), caller_certified_spd=True)
        assert info_z["converged"] is True
        assert info_z["iterations"] == 0
        assert info_z["residual_norm"] == 0.0
        np.testing.assert_allclose(x_z, 0.0)

        # Empty 0x0 system
        with pytest.raises(InputValidationError, match="empty 0x0 system"):
            cuda.solve_cg(sp.csr_matrix((0, 0)), np.array([]))

        # Device-resident validation without host transfer
        A_device = cp_sp.csr_matrix(A_sp)
        b_device = cp.ones(n, dtype=cp.float64)
        _, info_res = cuda.solve_cg(A_device, b_device, caller_certified_spd=True)
        assert info_res["device_resident_validation"] is True
        assert info_res["host_matrix_transfers"] == 0
        assert info_res["spd_status"] == "CALLER_ASSUMED_SPD"

        # When caller_certified_spd=False, host transfer is recorded for ARPACK eigensolve
        _, info_eigensolve = cuda.solve_cg(A_device, b_device, caller_certified_spd=False)
        assert info_eigensolve["device_resident_validation"] is False
        assert info_eigensolve["host_matrix_transfers"] == 1
        assert info_eigensolve["spd_status"] == "VERIFIED_SPD"


class TestCUDADetectionAndFallback:
    """Tests ensuring graceful handling when CUDA is absent or uninstalled."""

    def test_detection_structure(self):
        result = detect_cuda_capability()
        assert result.status in CUDADetectionStatus
        assert isinstance(result.is_operational, bool)
        assert isinstance(result.diagnostic_message, str)

    def test_cpu_never_requires_cuda(self):
        """Verify CPU backend remains fully operational regardless of CUDA state."""
        cpu = CPUBackend()
        assert cpu.is_available is True
        res = cpu.spmv(sp.eye(5, format="csr"), np.ones(5))
        np.testing.assert_allclose(res, np.ones(5))
