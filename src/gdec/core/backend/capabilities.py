"""
Capability definitions and enumeration for GDEC execution backends.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, List


class CapabilityStatus(Enum):
    """Maturity and support level of a backend capability."""
    SUPPORTED = auto()       # Fully implemented, tested, and certified
    OPTIONAL = auto()        # Supported if optional hardware/dependencies are present
    EXPERIMENTAL = auto()    # Functional prototype; subject to verification restrictions
    UNSUPPORTED = auto()     # Explicitly not supported by this backend


@dataclass(frozen=True)
class BackendCapabilities:
    """
    Explicit capability matrix for an execution backend.
    Enforces honest discovery without speculative claims.
    """
    # Core linear algebra
    sparse_matvec: bool = True
    sparse_direct_solve: bool = False
    sparse_cg_solve: bool = False
    multiple_rhs: bool = False
    factorization_reuse: bool = False

    # Device execution characteristics
    device_resident_memory: bool = False
    device_synchronization: bool = False
    asynchronous_streams: bool = False

    # High-level analytical operations
    batched_analytical_scaling: bool = False

    # Assembly and mechanics (explicitly marked False in Phase 5.1)
    fem_assembly: bool = False
    mesh_refinement: bool = False
    dwr_evaluation: bool = False

    # Detailed status map
    capability_status: Dict[str, CapabilityStatus] = field(default_factory=dict)

    def is_supported(self, feature: str) -> bool:
        """Check whether a named feature is supported."""
        return getattr(self, feature, False)

    def describe(self) -> Dict[str, Any]:
        """Return a structured summary of capabilities and their maturity."""
        return {
            "sparse_matvec": self.sparse_matvec,
            "sparse_direct_solve": self.sparse_direct_solve,
            "sparse_cg_solve": self.sparse_cg_solve,
            "multiple_rhs": self.multiple_rhs,
            "factorization_reuse": self.factorization_reuse,
            "device_resident_memory": self.device_resident_memory,
            "device_synchronization": self.device_synchronization,
            "asynchronous_streams": self.asynchronous_streams,
            "batched_analytical_scaling": self.batched_analytical_scaling,
            "fem_assembly": self.fem_assembly,
            "mesh_refinement": self.mesh_refinement,
            "dwr_evaluation": self.dwr_evaluation,
            "maturity_levels": {k: v.name for k, v in self.capability_status.items()},
        }
