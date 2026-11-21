"""
Exceptions for GDEC Decision Sufficiency Engine (DSE).
"""

from __future__ import annotations


class DSEError(Exception):
    """Base exception for all Decision Sufficiency Engine operations."""
    pass


class ContractError(DSEError):
    """Base exception for Decision Contract definition, validation, or parsing."""
    pass


class ContractValidationError(ContractError):
    """Raised when a Decision Contract violates syntactic or physical schema rules."""
    pass


class ContractSerializationError(ContractError):
    """Raised when serializing or deserializing a Decision Contract fails."""
    pass


class DecisionRefusalError(DSEError):
    """
    Raised when an engineering decision cannot be evaluated or certified
    due to numerical invalidity, physical boundary breaches, or missing evidence.
    """
    def __init__(self, reason: str, diagnostics: dict | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostics = diagnostics or {}


class ScalingAssumptionError(DSEError):
    """Raised when analytical parameter scaling assumptions are violated."""
    pass
