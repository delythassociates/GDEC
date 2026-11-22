"""Dimension-checked scalar quantities with explicit temperature semantics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from .dimensions import Dimension, TEMPERATURE
from .errors import DimensionError, QuantityKindError, UnitError
from .units import SI_UNITS, UnitRegistry

_KINDS = {"linear", "absolute_temperature", "temperature_interval"}


@dataclass(frozen=True, slots=True)
class Quantity:
    """Scalar quantity stored internally in coherent SI base units.

    unit is optional source/display metadata. It does not change the
    canonical value stored in value.
    """

    value: float
    dimension: Dimension
    kind: str = "linear"
    unit: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, Dimension):
            raise TypeError("dimension must be a Dimension instance.")
        if self.kind not in _KINDS:
            raise QuantityKindError(f"Unsupported quantity kind: {self.kind}")
        if self.kind != "linear" and self.dimension != TEMPERATURE:
            raise QuantityKindError(
                "Absolute-temperature and temperature-interval kinds require pure temperature dimension."
            )
        if isinstance(self.value, bool) or not isinstance(self.value, Real):
            raise TypeError("Quantity value must be a real scalar, not bool.")
        numeric_value = float(self.value)
        if not math.isfinite(numeric_value):
            raise ValueError("Quantity values must be finite.")
        if self.kind == "absolute_temperature" and numeric_value < 0.0:
            raise QuantityKindError("Absolute temperature cannot be below 0 K.")
        if self.unit is not None and (not isinstance(self.unit, str) or not self.unit.strip()):
            raise ValueError("Source unit metadata must be a non-empty string when supplied.")
        object.__setattr__(self, "value", numeric_value)

    @classmethod
    def from_unit(cls, value: float, symbol: str, registry: UnitRegistry = SI_UNITS) -> "Quantity":
        unit = registry.get(symbol)
        return cls(unit.to_base(value), unit.dimension, unit.kind, symbol)

    def to(self, symbol: str, registry: UnitRegistry = SI_UNITS) -> float:
        unit = registry.get(symbol)
        if unit.dimension != self.dimension or unit.kind != self.kind:
            raise UnitError(f"Quantity ({self.dimension}, {self.kind}) is incompatible with unit {symbol}.")
        return unit.from_base(self.value)

    def _compatible(self, other: "Quantity") -> None:
        if not isinstance(other, Quantity):
            raise TypeError("Quantity arithmetic requires another Quantity.")
        if self.dimension != other.dimension:
            raise DimensionError(f"Incompatible dimensions: {self.dimension} and {other.dimension}.")

    @staticmethod
    def _scalar(value: Real) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("Scalar multiplier/divisor must be a real number, not bool.")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Scalar multiplier/divisor must be finite.")
        return result

    def __add__(self, other: "Quantity") -> "Quantity":
        self._compatible(other)
        kinds = {self.kind, other.kind}
        if kinds == {"absolute_temperature"}:
            raise QuantityKindError("Adding two absolute temperatures is undefined.")
        if kinds == {"absolute_temperature", "temperature_interval"}:
            return Quantity(self.value + other.value, TEMPERATURE, "absolute_temperature")
        if self.kind != other.kind:
            raise QuantityKindError("Cannot add absolute temperature and linear quantity.")
        return Quantity(self.value + other.value, self.dimension, self.kind)

    def __sub__(self, other: "Quantity") -> "Quantity":
        self._compatible(other)
        if self.kind == other.kind == "absolute_temperature":
            return Quantity(self.value - other.value, TEMPERATURE, "temperature_interval")
        if self.kind == "absolute_temperature" and other.kind == "temperature_interval":
            return Quantity(self.value - other.value, TEMPERATURE, "absolute_temperature")
        if self.kind != other.kind:
            raise QuantityKindError("Incompatible quantity kinds in subtraction.")
        return Quantity(self.value - other.value, self.dimension, self.kind)

    def __mul__(self, other: "Quantity" | Real) -> "Quantity":
        if self.kind == "absolute_temperature":
            raise QuantityKindError("An absolute temperature cannot be multiplied directly.")
        if isinstance(other, Quantity):
            if other.kind == "absolute_temperature":
                raise QuantityKindError("An absolute temperature cannot be multiplied directly.")
            result_dimension = self.dimension * other.dimension
            preserve_interval = (
                self.kind == "temperature_interval" and other.dimension.is_dimensionless
            ) or (
                other.kind == "temperature_interval" and self.dimension.is_dimensionless
            )
            result_kind = "temperature_interval" if preserve_interval else "linear"
            return Quantity(self.value * other.value, result_dimension, result_kind)
        scalar = self._scalar(other)
        return Quantity(self.value * scalar, self.dimension, self.kind)

    def __truediv__(self, other: "Quantity" | Real) -> "Quantity":
        if self.kind == "absolute_temperature":
            raise QuantityKindError("An absolute temperature cannot be divided directly.")
        if isinstance(other, Quantity):
            if other.kind == "absolute_temperature":
                raise QuantityKindError("An absolute temperature cannot be used as a divisor.")
            if other.value == 0.0:
                raise ZeroDivisionError("Cannot divide a Quantity by zero.")
            result_dimension = self.dimension / other.dimension
            preserve_interval = self.kind == "temperature_interval" and other.dimension.is_dimensionless
            result_kind = "temperature_interval" if preserve_interval else "linear"
            return Quantity(self.value / other.value, result_dimension, result_kind)
        scalar = self._scalar(other)
        if scalar == 0.0:
            raise ZeroDivisionError("Cannot divide a Quantity by zero.")
        return Quantity(self.value / scalar, self.dimension, self.kind)

    def __rmul__(self, other: Real) -> "Quantity":
        return self * other

    def __neg__(self) -> "Quantity":
        if self.kind == "absolute_temperature":
            raise QuantityKindError("An absolute temperature cannot be negated.")
        return Quantity(-self.value, self.dimension, self.kind)

    def require_dimension(self, expected: Dimension, *, context: str = "value") -> None:
        if self.dimension != expected:
            raise DimensionError(f"{context} must have dimension {expected}; received {self.dimension}.")
