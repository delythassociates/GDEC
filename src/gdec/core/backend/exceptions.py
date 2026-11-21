"""
Exception hierarchy for GDEC execution backends.
"""

from __future__ import annotations


class BackendError(Exception):
    """Base exception for all execution backend operations."""
    pass


class BackendNotAvailableError(BackendError):
    """Raised when a requested backend cannot be loaded or hardware is unavailable."""
    pass


class UnsupportedCapabilityError(BackendError):
    """Raised when an operation is requested that the backend does not support."""
    pass


class DeviceOutOfMemoryError(BackendError):
    """Raised when memory allocation fails on the host or accelerator device."""
    pass


class DataTransferError(BackendError):
    """Raised when data transfer between host and accelerator device fails."""
    pass


class NumericalBackendError(BackendError):
    """Raised when an algebraic or numerical breakdown occurs (singular matrix, NaN/Inf)."""
    pass


class InputValidationError(BackendError):
    """Raised when matrix dimensions, sparsity formats, or vector shapes are invalid."""
    pass
