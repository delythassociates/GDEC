"""Structured exceptions for GDEC's standalone engineering type system."""

class TypeSystemError(ValueError):
    """Base class for invalid engineering type operations."""

class DimensionError(TypeSystemError):
    """Raised when physical dimensions are incompatible."""

class UnitError(TypeSystemError):
    """Raised for unknown or incompatible units and conversions."""

class QuantityKindError(TypeSystemError):
    """Raised when absolute and differential quantities are mixed illegally."""

class ShapeError(TypeSystemError):
    """Raised for incompatible tensor shapes or coordinate frames."""
