"""Explicit unit definitions and safe conversions, including affine temperatures."""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping

from .dimensions import (
    AMOUNT, CURRENT, DIMENSIONLESS, ENERGY, FORCE, LENGTH, LUMINOUS_INTENSITY,
    MASS, POWER, PRESSURE, TEMPERATURE, TIME, Dimension,
)
from .errors import UnitError


def _fraction(value: int | float | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise UnitError("Unit scale and offset cannot be booleans.")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnitError("Unit scale and offset must be finite.")
        return Fraction(value).limit_denominator(1_000_000)
    return Fraction(value)


@dataclass(frozen=True, slots=True)
class Unit:
    """Unit conversion to a coherent base representation.

    For linear/interval units: base = value * scale.
    For absolute temperatures: base = value * scale + offset.
    """

    symbol: str
    dimension: Dimension
    scale: Fraction = Fraction(1)
    offset: Fraction = Fraction(0)
    kind: str = "linear"

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise UnitError("Unit symbol cannot be empty.")
        if not isinstance(self.dimension, Dimension):
            raise UnitError("Unit dimension must be a Dimension instance.")
        scale = _fraction(self.scale)
        offset = _fraction(self.offset)
        if scale <= 0:
            raise UnitError("Unit scale must be strictly positive.")
        if self.kind not in {"linear", "absolute_temperature", "temperature_interval"}:
            raise UnitError(f"Unsupported unit kind: {self.kind}")
        if self.kind != "absolute_temperature" and offset != 0:
            raise UnitError("Only absolute-temperature units may have an offset.")
        if self.kind in {"absolute_temperature", "temperature_interval"} and self.dimension != TEMPERATURE:
            raise UnitError("Temperature unit kinds require the temperature dimension.")
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "offset", offset)

    def to_base(self, value: float) -> float:
        if isinstance(value, bool):
            raise UnitError("Unit conversion value cannot be boolean.")
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UnitError("Unit conversion value must be a finite real number.") from exc
        if not math.isfinite(numeric):
            raise UnitError("Unit conversion value must be finite.")
        result = numeric * float(self.scale) + float(self.offset)
        if not math.isfinite(result):
            raise UnitError("Converted base value is not finite.")
        if self.kind == "absolute_temperature" and result < 0.0:
            raise UnitError("Absolute temperature cannot be below 0 K.")
        return result

    def from_base(self, value: float) -> float:
        if isinstance(value, bool):
            raise UnitError("Base value cannot be boolean.")
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise UnitError("Base value must be a finite real number.") from exc
        if not math.isfinite(numeric):
            raise UnitError("Base value must be finite.")
        if self.kind == "absolute_temperature" and numeric < 0.0:
            raise UnitError("Absolute temperature cannot be below 0 K.")
        result = (numeric - float(self.offset)) / float(self.scale)
        if not math.isfinite(result):
            raise UnitError("Converted value is not finite.")
        return result


class UnitRegistry:
    """Mutable registry with atomic registration and read-only inspection."""

    def __init__(self, units: Mapping[str, Unit] | None = None):
        self._units: dict[str, Unit] = {}
        if units:
            for key, unit in units.items():
                if not isinstance(key, str) or not key.strip():
                    raise UnitError("Unit registry keys must be non-empty strings.")
                if not isinstance(unit, Unit):
                    raise UnitError(f"Registry entry {key!r} is not a Unit.")
                self._units[key] = unit

    def register(self, unit: Unit, *, aliases: tuple[str, ...] = ()) -> None:
        if not isinstance(unit, Unit):
            raise UnitError("Only Unit instances can be registered.")
        keys = (unit.symbol, *aliases)
        if any(not isinstance(key, str) or not key.strip() for key in keys):
            raise UnitError("Unit aliases must be non-empty strings.")
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
        source_unit, target_unit = self.get(source), self.get(target)
        if source_unit.dimension != target_unit.dimension:
            raise UnitError(
                f"Cannot convert {source} ({source_unit.dimension}) to "
                f"{target} ({target_unit.dimension})."
            )
        if source_unit.kind != target_unit.kind:
            raise UnitError(
                f"Cannot convert between {source_unit.kind} and {target_unit.kind} units."
            )
        return target_unit.from_base(source_unit.to_base(value))

    @property
    def units(self) -> Mapping[str, Unit]:
        return MappingProxyType(self._units)


def _u(
    symbol: str,
    dim: Dimension,
    scale: int | Fraction = 1,
    offset: int | Fraction = 0,
    kind: str = "linear",
) -> Unit:
    return Unit(symbol, dim, Fraction(scale), Fraction(offset), kind)


SI_UNITS = UnitRegistry()
for _unit, _aliases in [
    (_u("1", DIMENSIONLESS), ("dimensionless",)),
    (_u("kg", MASS), ()), (_u("g", MASS, Fraction(1, 1000)), ()),
    (_u("m", LENGTH), ("meter", "metre")),
    (_u("mm", LENGTH, Fraction(1, 1000)), ()),
    (_u("cm", LENGTH, Fraction(1, 100)), ()),
    (_u("km", LENGTH, 1000), ()),
    (_u("s", TIME), ("sec",)), (_u("ms", TIME, Fraction(1, 1000)), ()),
    (_u("min", TIME, 60), ()), (_u("h", TIME, 3600), ()),
    (_u("A", CURRENT), ()),
    (_u("K", TEMPERATURE, kind="absolute_temperature"), ()),
    (_u("degC", TEMPERATURE, 1, Fraction(27315, 100), "absolute_temperature"), ("°C", "Celsius")),
    (_u("degF", TEMPERATURE, Fraction(5, 9), Fraction(45967, 180), "absolute_temperature"), ("°F", "Fahrenheit")),
    (_u("delta_K", TEMPERATURE, kind="temperature_interval"), ("K_delta",)),
    (_u("delta_degC", TEMPERATURE, kind="temperature_interval"), ("delta_°C",)),
    (_u("mol", AMOUNT), ()), (_u("cd", LUMINOUS_INTENSITY), ()),
    (_u("N", FORCE), ()), (_u("kN", FORCE, 1000), ()),
    (_u("Pa", PRESSURE), ()), (_u("kPa", PRESSURE, 1000), ()),
    (_u("MPa", PRESSURE, 1_000_000), ()), (_u("GPa", PRESSURE, 1_000_000_000), ()),
    (_u("J", ENERGY), ()), (_u("kJ", ENERGY, 1000), ()),
    (_u("W", POWER), ()), (_u("kW", POWER, 1000), ()),
]:
    SI_UNITS.register(_unit, aliases=_aliases)
