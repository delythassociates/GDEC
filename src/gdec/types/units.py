"""Explicit unit definitions and safe conversions, including affine temperatures."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping
from .dimensions import (Dimension, DIMENSIONLESS, MASS, LENGTH, TIME, CURRENT, TEMPERATURE, AMOUNT, LUMINOUS_INTENSITY, FORCE, PRESSURE, ENERGY, POWER)
from .errors import UnitError

@dataclass(frozen=True, slots=True)
class Unit:
    symbol: str
    dimension: Dimension
    scale: Fraction = Fraction(1)
    offset: Fraction = Fraction(0)  # base_value = value * scale + offset
    kind: str = "linear"  # linear, absolute_temperature, temperature_interval

    def __post_init__(self) -> None:
        if not self.symbol:
            raise UnitError("Unit symbol cannot be empty.")
        if self.scale <= 0:
            raise UnitError("Unit scale must be strictly positive.")
        if self.kind not in {"linear", "absolute_temperature", "temperature_interval"}:
            raise UnitError(f"Unsupported unit kind: {self.kind}")
        if self.kind != "absolute_temperature" and self.offset != 0:
            raise UnitError("Only absolute-temperature units may have an offset.")
        if self.kind in {"absolute_temperature", "temperature_interval"} and self.dimension != TEMPERATURE:
            raise UnitError("Temperature unit kinds require the temperature dimension.")

    def to_base(self, value: float) -> float:
        return float(value) * float(self.scale) + float(self.offset)

    def from_base(self, value: float) -> float:
        return (float(value) - float(self.offset)) / float(self.scale)

class UnitRegistry:
    def __init__(self, units: Mapping[str, Unit] | None = None):
        self._units: dict[str, Unit] = dict(units or {})

    def register(self, unit: Unit, *, aliases: tuple[str, ...] = ()) -> None:
        keys = (unit.symbol, *aliases)
        if len(set(keys)) != len(keys):
            raise UnitError("A unit symbol and its aliases must be unique.")
        duplicate = next((key for key in keys if key in self._units), None)
        if duplicate is not None:
            raise UnitError(f"Unit symbol or alias already registered: {duplicate}")
        for key in keys:
            self._units[key] = unit

    def get(self, symbol: str) -> Unit:
        try:
            return self._units[symbol]
        except KeyError as exc:
            raise UnitError(f"Unknown unit: {symbol}") from exc

    def convert(self, value: float, source: str, target: str) -> float:
        a, b = self.get(source), self.get(target)
        if a.dimension != b.dimension:
            raise UnitError(f"Cannot convert {source} ({a.dimension}) to {target} ({b.dimension}).")
        if a.kind != b.kind:
            raise UnitError(f"Cannot convert between {a.kind} and {b.kind} units.")
        return b.from_base(a.to_base(value))

    @property
    def units(self) -> Mapping[str, Unit]:
        return MappingProxyType(self._units)


def _u(symbol: str, dim: Dimension, scale: int | Fraction = 1, offset: int | Fraction = 0, kind: str = "linear") -> Unit:
    return Unit(symbol, dim, Fraction(scale), Fraction(offset), kind)

SI_UNITS = UnitRegistry()
for unit, aliases in [
    (_u("1", DIMENSIONLESS), ("dimensionless",)),
    (_u("kg", MASS), ()), (_u("g", MASS, Fraction(1,1000)), ()),
    (_u("m", LENGTH), ("meter", "metre")), (_u("mm", LENGTH, Fraction(1,1000)), ()), (_u("cm", LENGTH, Fraction(1,100)), ()), (_u("km", LENGTH, 1000), ()),
    (_u("s", TIME), ("sec",)), (_u("ms", TIME, Fraction(1,1000)), ()), (_u("min", TIME, 60), ()), (_u("h", TIME, 3600), ()),
    (_u("A", CURRENT), ()), (_u("K", TEMPERATURE, kind="absolute_temperature"), ()),
    (_u("degC", TEMPERATURE, 1, Fraction(27315,100), "absolute_temperature"), ("°C", "Celsius")),
    (_u("degF", TEMPERATURE, Fraction(5,9), Fraction(45967,180), "absolute_temperature"), ("°F", "Fahrenheit")),
    (_u("delta_K", TEMPERATURE, kind="temperature_interval"), ("K_delta",)),
    (_u("delta_degC", TEMPERATURE, kind="temperature_interval"), ("delta_°C",)),
    (_u("mol", AMOUNT), ()), (_u("cd", LUMINOUS_INTENSITY), ()),
    (_u("N", FORCE), ()), (_u("kN", FORCE, 1000), ()),
    (_u("Pa", PRESSURE), ()), (_u("kPa", PRESSURE, 1000), ()), (_u("MPa", PRESSURE, 1_000_000), ()), (_u("GPa", PRESSURE, 1_000_000_000), ()),
    (_u("J", ENERGY), ()), (_u("kJ", ENERGY, 1000), ()), (_u("W", POWER), ()), (_u("kW", POWER, 1000), ()),
]:
    SI_UNITS.register(unit, aliases=aliases)
