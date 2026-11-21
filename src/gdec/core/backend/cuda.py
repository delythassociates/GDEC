"""
CUDA execution backend prototype for GDEC using CuPy and cuSPARSE.
Provides isolated GPU sparse matrix-vector multiplication, batched analytical scaling,
and robust hardware discovery without mandatory CUDA dependencies.
"""

from __future__ import annotations
import platform
import shutil
import subprocess
from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional, Union
import numpy as np
import scipy.sparse as sp

from gdec.core.backend.capabilities import BackendCapabilities, CapabilityStatus
from gdec.core.backend.spd_check import verify_cg_eligibility
from gdec.core.backend.exceptions import (
    BackendNotAvailableError,
    UnsupportedCapabilityError,
    InputValidationError,
    NumericalBackendError,
    DataTransferError,
    DeviceOutOfMemoryError,
)

# Optional CuPy import
_CUPY_AVAILABLE = False
_CUPY_IMPORT_ERROR: Optional[str] = None
try:
    import cupy as cp
    import cupyx.scipy.sparse as cp_sp
    import cupyx.scipy.sparse.linalg as cp_spla
    _CUPY_AVAILABLE = True
except ImportError as e:
    cp = None
    cp_sp = None
    cp_spla = None
    _CUPY_IMPORT_ERROR = str(e)
except Exception as e:
    cp = None
    cp_sp = None
    cp_spla = None
    _CUPY_IMPORT_ERROR = f"Unexpected error importing cupy: {str(e)}"


class CUDADetectionStatus(Enum):
    """Detailed discovery status for CUDA acceleration."""
    CUPY_NOT_INSTALLED = auto()
    CUDA_DRIVER_UNAVAILABLE = auto()
    NO_COMPATIBLE_DEVICE = auto()
    RUNTIME_INIT_FAILURE = auto()
    SUPPORTED_GPU_AVAILABLE = auto()


@dataclass(frozen=True)
class CUDADetectionResult:
    """Diagnostic outcome of CUDA hardware and software discovery."""
    status: CUDADetectionStatus
    is_operational: bool
    device_name: Optional[str] = None
    device_memory_mb: Optional[float] = None
    cuda_driver_version: Optional[str] = None
    cupy_version: Optional[str] = None
    diagnostic_message: str = ""


def detect_cuda_capability() -> CUDADetectionResult:
    """
    Perform a strict, non-destructive probe of CUDA hardware and libraries.
    Distinguishes missing packages, missing drivers, missing GPUs, and initialization failures.
    """
    if not _CUPY_AVAILABLE:
        return CUDADetectionResult(
            status=CUDADetectionStatus.CUPY_NOT_INSTALLED,
            is_operational=False,
            diagnostic_message=(
                f"CuPy package is not installed ({_CUPY_IMPORT_ERROR}). "
                "GDEC defaults safely to CPU execution. Install via 'pip install gdec[gpu]' or 'pip install cupy-cuda12x'."
            ),
        )

    # Check for nvidia-smi / driver presence
    has_nvidia_smi = shutil.which("nvidia-smi") is not None
    driver_version = None
    if has_nvidia_smi:
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout.strip():
                driver_version = res.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass

    # Probe CuPy device count and runtime
    try:
        dev_count = cp.cuda.runtime.getDeviceCount()
        if dev_count == 0:
            return CUDADetectionResult(
                status=CUDADetectionStatus.NO_COMPATIBLE_DEVICE,
                is_operational=False,
                diagnostic_message="CUDA runtime initialized but reported 0 compatible NVIDIA GPU devices.",
            )

        # Attempt to access device 0 and query properties
        dev = cp.cuda.Device(0)
        props = cp.cuda.runtime.getDeviceProperties(0)
        dev_name = props["name"].decode("utf-8") if isinstance(props["name"], bytes) else str(props["name"])
        total_mem_mb = round(dev.mem_info[1] / (1024**2), 1)

        # Non-destructive memory allocation sanity check
        test_arr = cp.zeros(10, dtype=cp.float32)
        cp.cuda.Stream.null.synchronize()
        del test_arr

        return CUDADetectionResult(
            status=CUDADetectionStatus.SUPPORTED_GPU_AVAILABLE,
            is_operational=True,
            device_name=dev_name,
            device_memory_mb=total_mem_mb,
            cuda_driver_version=driver_version,
            cupy_version=cp.__version__,
            diagnostic_message=f"Operational CUDA GPU detected: {dev_name} ({total_mem_mb} MB VRAM).",
        )
    except cp.cuda.runtime.CUDARuntimeError as e:
        return CUDADetectionResult(
            status=CUDADetectionStatus.RUNTIME_INIT_FAILURE,
            is_operational=False,
            cuda_driver_version=driver_version,
            diagnostic_message=f"CUDA runtime initialization error: {str(e)}",
        )
    except Exception as e:
        return CUDADetectionResult(
            status=CUDADetectionStatus.RUNTIME_INIT_FAILURE,
            is_operational=False,
            cuda_driver_version=driver_version,
            diagnostic_message=f"Failed to initialize GPU device: {str(e)}",
        )


class CUDABackend:
    """
    Isolated CUDA execution backend prototype for GDEC.
    Provides GPU-accelerated sparse matrix-vector multiplication (SpMV)
    and batched analytical parameter scaling using CuPy.
    """

    def __init__(self, device_id: int = 0) -> None:
        self._device_id = device_id
        self._detection = detect_cuda_capability()
        self._name = "cuda"

        if not self._detection.is_operational:
            self._capabilities = BackendCapabilities(
                sparse_matvec=False,
                sparse_direct_solve=False,
                sparse_cg_solve=False,
                multiple_rhs=False,
                factorization_reuse=False,
                device_resident_memory=False,
                device_synchronization=False,
                asynchronous_streams=False,
                batched_analytical_scaling=False,
                fem_assembly=False,
                mesh_refinement=False,
                dwr_evaluation=False,
                capability_status={
                    "sparse_matvec": CapabilityStatus.UNSUPPORTED,
                    "batched_analytical_scaling": CapabilityStatus.UNSUPPORTED,
                },
            )
        else:
            self._capabilities = BackendCapabilities(
                sparse_matvec=True,
                sparse_direct_solve=False,  # Sparse direct SuperLU on GPU is out-of-scope for 5.1 POC
                sparse_cg_solve=True,       # Minimal prototype CG available on GPU
                multiple_rhs=False,         # Multi-RHS direct solve out of scope on GPU for 5.1
                factorization_reuse=False,
                device_resident_memory=True,
                device_synchronization=True,
                asynchronous_streams=True,
                batched_analytical_scaling=True,
                fem_assembly=False,         # Not claimed
                mesh_refinement=False,      # Not claimed
                dwr_evaluation=False,       # Not claimed
                capability_status={
                    "sparse_matvec": CapabilityStatus.SUPPORTED,
                    "device_resident_memory": CapabilityStatus.SUPPORTED,
                    "device_synchronization": CapabilityStatus.SUPPORTED,
                    "batched_analytical_scaling": CapabilityStatus.SUPPORTED,
                    "sparse_cg_solve": CapabilityStatus.EXPERIMENTAL,
                    "sparse_direct_solve": CapabilityStatus.UNSUPPORTED,
                    "fem_assembly": CapabilityStatus.UNSUPPORTED,
                },
            )

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return self._detection.is_operational

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def _ensure_operational(self) -> None:
        if not self._detection.is_operational:
            raise BackendNotAvailableError(
                f"CUDA backend is not operational on this host: {self._detection.diagnostic_message}"
            )

    def get_device_info(self) -> Dict[str, Any]:
        """Return detailed hardware, memory, and runtime diagnostics."""
        base_info: Dict[str, Any] = {
            "backend": "cuda",
            "is_available": self._detection.is_operational,
            "status": self._detection.status.name,
            "diagnostic_message": self._detection.diagnostic_message,
        }
        if self._detection.is_operational and cp is not None:
            dev = cp.cuda.Device(self._device_id)
            free_mem, total_mem = dev.mem_info
            base_info.update({
                "device_id": self._device_id,
                "device_name": self._detection.device_name,
                "total_vram_mb": round(total_mem / (1024**2), 1),
                "free_vram_mb": round(free_mem / (1024**2), 1),
                "cupy_version": self._detection.cupy_version,
                "driver_version": self._detection.cuda_driver_version,
            })
        return base_info

    def to_device(self, data: Any) -> Any:
        """Explicit host-to-device transfer."""
        self._ensure_operational()
        try:
            if sp.issparse(data):
                return cp_sp.csr_matrix(data)
            return cp.asarray(data)
        except cp.cuda.memory.OutOfMemoryError as e:
            raise DeviceOutOfMemoryError(f"CUDA Out of Memory during to_device transfer: {str(e)}") from e
        except Exception as e:
            raise DataTransferError(f"Host-to-device transfer failed: {str(e)}") from e

    def to_host(self, data: Any) -> Any:
        """Explicit device-to-host transfer."""
        self._ensure_operational()
        try:
            if hasattr(data, "get"):
                return data.get()
            return np.asarray(data)
        except Exception as e:
            raise DataTransferError(f"Device-to-host transfer failed: {str(e)}") from e

    def spmv(self, A: Any, x: Any, host_output: bool = True) -> Any:
        """
        Sparse matrix-vector multiplication: y = A @ x on GPU.
        Supports both host (SciPy/NumPy) and GPU-resident (CuPy) inputs.
        """
        self._ensure_operational()

        # Check if already GPU-resident
        is_gpu_A = cp_sp.issparse(A)
        is_gpu_x = isinstance(x, cp.ndarray)

        # Transfer if host data
        A_gpu = A if is_gpu_A else self.to_device(A.tocsr() if sp.issparse(A) else A)
        x_gpu = x if is_gpu_x else self.to_device(x)

        if not cp_sp.issparse(A_gpu):
            raise InputValidationError("Matrix A must be a sparse CSR matrix.")
        if x_gpu.ndim != 1:
            raise InputValidationError(f"Expected 1D vector x, got ndim={x_gpu.ndim}")
        if A_gpu.shape[1] != x_gpu.shape[0]:
            raise InputValidationError(
                f"Dimension mismatch: A is {A_gpu.shape}, but x has length {x_gpu.shape[0]}"
            )

        try:
            y_gpu = A_gpu.dot(x_gpu)
            self.synchronize()
        except cp.cuda.memory.OutOfMemoryError as e:
            raise DeviceOutOfMemoryError(f"CUDA Out of Memory during SpMV: {str(e)}") from e
        except Exception as e:
            raise NumericalBackendError(f"GPU SpMV kernel execution failed: {str(e)}") from e

        if host_output:
            return self.to_host(y_gpu)
        return y_gpu

    def solve_direct(self, A: Any, b: Any) -> Any:
        """GPU sparse direct solve is unsupported in Phase 5.1 POC."""
        raise UnsupportedCapabilityError(
            "CUDABackend does not support sparse direct solves in Phase 5.1. "
            "Use CPUBackend.solve_direct() (SuperLU default)."
        )

    def solve_multiple_rhs(self, A: Any, B: Any) -> Any:
        """GPU multi-RHS direct solve is unsupported in Phase 5.1 POC."""
        raise UnsupportedCapabilityError(
            "CUDABackend does not support direct multi-RHS solves in Phase 5.1. "
            "Use CPUBackend.solve_multiple_rhs()."
        )

    def solve_cg(
        self,
        A: Any,
        b: Any,
        rtol: float = 1e-8,
        atol: float = 1e-12,
        max_iter: Optional[int] = None,
        M: Optional[Any] = None,
        caller_certified_spd: bool = False,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Minimal experimental GPU Conjugate Gradient solver for SPD systems.
        Enforces identical structural and SPD verification checks as CPUBackend.
        """
        self._ensure_operational()

        # Extract host arrays for structural and SPD verification
        A_host = self.to_host(A) if (cp_sp is not None and cp_sp.issparse(A)) else (
            A.tocsr() if sp.issparse(A) else np.asarray(A)
        )
        b_host = self.to_host(b) if (cp is not None and isinstance(b, cp.ndarray)) else np.asarray(b)

        # Enforce unified eligibility policy
        n, _, _ = verify_cg_eligibility(
            A=A_host,
            b=b_host,
            rtol=rtol,
            atol=atol,
            max_iter=max_iter,
            caller_certified_spd=caller_certified_spd,
        )

        if max_iter is None:
            max_iter = n * 2

        # Transfer verified inputs to device
        A_gpu = A if (cp_sp is not None and cp_sp.issparse(A)) else self.to_device(sp.csr_matrix(A_host))
        b_gpu = b if (cp is not None and isinstance(b, cp.ndarray)) else self.to_device(b_host)

        # Preconditioner handling: support GPU Jacobi or reject unsupported CPU preconditioners
        M_gpu = None
        if M is not None:
            if isinstance(M, str) and M.lower() == "jacobi":
                diag_gpu = A_gpu.diagonal()
                M_gpu = cp_spla.LinearOperator(A_gpu.shape, matvec=lambda v: v / diag_gpu, dtype=A_gpu.dtype)
            elif hasattr(M, "is_spd"):
                if not M.is_spd:
                    p_name = getattr(M, "name", type(M).__name__)
                    raise NumericalBackendError(
                        f"Preconditioner '{p_name}' is not SPD (is_spd=False). "
                        "Conjugate Gradient strictly requires an SPD preconditioner."
                    )
                p_name = getattr(M, "name", "").lower()
                if "jacobi" in p_name:
                    diag_gpu = A_gpu.diagonal()
                    M_gpu = cp_spla.LinearOperator(A_gpu.shape, matvec=lambda v: v / diag_gpu, dtype=A_gpu.dtype)
                elif "identity" in p_name:
                    M_gpu = None
                else:
                    raise UnsupportedCapabilityError(
                        f"Preconditioner '{getattr(M, 'name', type(M).__name__)}' is a CPU operator. "
                        "CUDABackend requires a GPU-resident preconditioner (e.g. 'jacobi' or cupyx LinearOperator)."
                    )
            elif cp_spla is not None and isinstance(M, cp_spla.LinearOperator):
                M_gpu = M
            else:
                raise UnsupportedCapabilityError(
                    f"Unsupported preconditioner type '{type(M).__name__}' passed to CUDABackend. "
                    "Only GPU-resident preconditioners or 'jacobi' are supported on CUDA."
                )

        try:
            x_gpu, info = cp_spla.cg(A_gpu, b_gpu, rtol=rtol, atol=atol, maxiter=max_iter, M=M_gpu)
            self.synchronize()

            # Residual evaluated directly on GPU without transferring matrix A
            r_gpu = b_gpu - A_gpu.dot(x_gpu)
            res_norm = float(cp.linalg.norm(r_gpu).get())
            x = self.to_host(x_gpu)

            converged = (info == 0)
            return x, {
                "converged": converged,
                "iterations": None, # CuPy CG does not return iteration telemetry; documented limitation
                "residual_norm": res_norm,
                "exit_code": info,
                "breakdown_reason": None if converged else f"CuPy CG did not converge (exit code {info})",
            }
        except Exception as e:
            if isinstance(e, (UnsupportedCapabilityError, NumericalBackendError, InputValidationError)):
                raise
            raise NumericalBackendError(f"GPU CG solve failed: {str(e)}") from e

    def synchronize(self) -> None:
        """Synchronize default CUDA stream."""
        if self._detection.is_operational and cp is not None:
            cp.cuda.Stream.null.synchronize()

    def evaluate_parameter_scaling_batch(
        self,
        E_vals: Any,
        P_vals: Any,
        J_0: float,
        E_0: float,
        P_0: float,
        host_output: bool = True,
    ) -> Any:
        """
        Batched GPU evaluation: J(E, P) = (P / P_0) * (E_0 / E) * J_0 using CuPy arrays.
        """
        self._ensure_operational()
        if E_0 <= 0.0:
            raise InputValidationError(f"Reference Young's modulus E_0 must be strictly positive, got {E_0}")
        if P_0 == 0.0:
            raise InputValidationError("Reference load factor P_0 cannot be zero.")

        # Transfer samples to GPU
        E_gpu = E_vals if isinstance(E_vals, cp.ndarray) else self.to_device(E_vals)
        P_gpu = P_vals if isinstance(P_vals, cp.ndarray) else self.to_device(P_vals)

        if E_gpu.shape != P_gpu.shape:
            raise InputValidationError(f"Shape mismatch: {E_gpu.shape} != {P_gpu.shape}")

        if bool(cp.any(E_gpu <= 0.0)):
            raise NumericalBackendError("Sampled Young's modulus E must be strictly positive.")

        try:
            scaled_gpu = (P_gpu / P_0) * (E_0 / E_gpu) * J_0
            self.synchronize()
        except cp.cuda.memory.OutOfMemoryError as e:
            raise DeviceOutOfMemoryError(f"CUDA Out of Memory during batched scaling: {str(e)}") from e

        if host_output:
            return self.to_host(scaled_gpu)
        return scaled_gpu
