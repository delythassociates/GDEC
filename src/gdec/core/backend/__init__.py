"""
GDEC Execution Backend Package.
Provides clean protocol-governed hardware abstractions for CPU and optional CUDA computation.
"""

from __future__ import annotations
from typing import Dict, Type

from gdec.core.backend.protocol import ExecutionBackend
from gdec.core.backend.capabilities import BackendCapabilities, CapabilityStatus
from gdec.core.backend.exceptions import (
    BackendError,
    BackendNotAvailableError,
    UnsupportedCapabilityError,
    DeviceOutOfMemoryError,
    DataTransferError,
    NumericalBackendError,
    InputValidationError,
)
from gdec.core.backend.cpu import CPUBackend
from gdec.core.backend.cuda import CUDABackend, detect_cuda_capability, CUDADetectionResult, CUDADetectionStatus
from gdec.core.backend.spd_check import (
    verify_cg_eligibility,
    compute_symmetry_defect,
    SPDVerificationStatus,
    CGEligibilityResult,
)


_BACKEND_REGISTRY: Dict[str, Type[ExecutionBackend]] = {
    "cpu": CPUBackend,
    "cuda": CUDABackend,
}


def get_backend(name: str = "cpu") -> ExecutionBackend:
    """
    Factory function to retrieve an initialized execution backend.

    Parameters
    ----------
    name : str, default 'cpu'
        Backend identifier: 'cpu' or 'cuda'.

    Returns
    -------
    ExecutionBackend instance.
    """
    key = name.lower().strip()
    if key not in _BACKEND_REGISTRY:
        raise ValueError(
            f"Unknown backend '{name}'. Available backends: {list(_BACKEND_REGISTRY.keys())}"
        )
    backend_cls = _BACKEND_REGISTRY[key]
    backend = backend_cls()
    if not backend.is_available:
        if key == "cuda":
            diag = backend.get_device_info().get("diagnostic_message", "CUDA unavailable")
            raise BackendNotAvailableError(f"Backend 'cuda' is not operational: {diag}")
        raise BackendNotAvailableError(f"Backend '{name}' is not available on this host.")
    return backend


__all__ = [
    "ExecutionBackend",
    "CPUBackend",
    "CUDABackend",
    "BackendCapabilities",
    "CapabilityStatus",
    "BackendError",
    "BackendNotAvailableError",
    "UnsupportedCapabilityError",
    "DeviceOutOfMemoryError",
    "DataTransferError",
    "NumericalBackendError",
    "InputValidationError",
    "detect_cuda_capability",
    "CUDADetectionResult",
    "CUDADetectionStatus",
    "get_backend",
    "verify_cg_eligibility",
    "compute_symmetry_defect",
    "SPDVerificationStatus",
    "CGEligibilityResult",
]
