"""
Abstract base class for computational backends in GDEC.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any


class ComputationalBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Backend unique identifier (e.g. 'cpu', 'cuda')."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can be used on the current host machine."""
        pass

    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Hardware and library information."""
        pass
