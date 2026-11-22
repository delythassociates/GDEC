"""Dimension-checked scalar quantities with explicit temperature semantics."""
from __future__ import annotations
from dataclasses import dataclass
from .dimensions import Dimension, DIMENSIONLESS, TEMPERATURE
from .units import UnitRegistry, SI_UNITS
from .errors import DimensionError, QuantityKindError, UnitError

@dataclass(frozen=True, slots=True)
class Quantity:
    value: float
    dimension: Dimension
    kind: str = "linear"  # linear, absolute_temperature, temperature_interval
    unit: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"linear", "absolute_temperature", "temperature_interval"}:
            raise QuantityKindError(f"Unsupported quantity kind: {self.kind}")
        if self.kind != "linear" and self.dimension != TEMPERATURE:
            raise QuantityKindError("Temperature quantity kinds require temperature dimension.")

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
        if self.dimension != other.dimension:
            raise DimensionError(f"Incompatible dimensions: {self.dimension} and {other.dimension}.")

    def __add__(self, other: "Quantity") -> "Quantity":
        self._compatible(other)
        if self.kind == other.kind == "absolute_temperature":
            raise QuantityKindError("Adding two absolute temperatures is undefined.")
        if {self.kind, other.kind} == {"absolute_temperature", "temperature_interval"}:
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

    def __mul__(self, other: "Quantity" | float | int) -> "Quantity":
        if self.kind != "linear":
            raise QuantityKindError("Absolute temperatures and temperature intervals cannot be multiplied directly.")
        if isinstance(other, Quantity):
            if other.kind != "linear":
                raise QuantityKindError("Temperature quantities cannot be multiplied directly.")
            return Quantity(self.value * other.value, self.dimension * other.dimension)
        return Quantity(self.value * float(other), self.dimension)

    def __truediv__(self, other: "Quantity" | float | int) -> "Quantity":
        if self.kind != "linear":
            raise QuantityKindError("Absolute temperatures and temperature intervals cannot be divided directly.")
        if isinstance(other, Quantity):
            if other.kind != "linear":
                raise QuantityKindError("Temperature quantities cannot be divided directly.")
            return Quantity(self.value / other.value, self.dimension / other.dimension)
        return Quantity(self.value / float(other), self.dimension)

    def __rmul__(self, other: float | int) -> "Quantity":
        return self * other

    def __neg__(self) -> "Quantity":
        if self.kind == "absolute_temperature":
            raise QuantityKindError("An absolute temperature cannot be negated.")
        return Quantity(-self.value, self.dimension, self.kind)

    def require_dimension(self, expected: Dimension, *, context: str = "value") -> None:
        if self.dimension != expected:
            raise DimensionError(f"{context} must have dimension {expected}; received {self.dimension}.")
