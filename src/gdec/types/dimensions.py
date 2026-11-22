"""Exact dimensional algebra over the seven SI base dimensions."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

_EXPONENTS = 7
_BASE_NAMES = ("mass", "length", "time", "current", "temperature", "amount", "luminous_intensity")

@dataclass(frozen=True, slots=True)
class Dimension:
    """Physical dimension; exponent order is M, L, T, I, Theta, N, J."""
    exponents: tuple[Fraction, ...] = (Fraction(0),) * _EXPONENTS

    def __post_init__(self) -> None:
        if len(self.exponents) != _EXPONENTS:
            raise ValueError(f"A dimension requires {_EXPONENTS} SI exponents.")
        object.__setattr__(self, "exponents", tuple(Fraction(x) for x in self.exponents))

    @classmethod
    def from_exponents(cls, values: Iterable[int | float | Fraction]) -> "Dimension":
        vals = tuple(Fraction(v) for v in values)
        return cls(vals)

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a + b for a, b in zip(self.exponents, other.exponents)))

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a - b for a, b in zip(self.exponents, other.exponents)))

    def __pow__(self, power: int | Fraction) -> "Dimension":
        p = Fraction(power)
        return Dimension(tuple(a * p for a in self.exponents))

    @property
    def is_dimensionless(self) -> bool:
        return all(x == 0 for x in self.exponents)

    def compatible_with(self, other: "Dimension") -> bool:
        return self == other

    def __str__(self) -> str:
        symbols = ("M", "L", "T", "I", "Θ", "N", "J")
        terms = [s if p == 1 else f"{s}^{p}" for s, p in zip(symbols, self.exponents) if p]
        return "1" if not terms else "·".join(terms)

DIMENSIONLESS = Dimension()
MASS = Dimension.from_exponents((1,0,0,0,0,0,0))
LENGTH = Dimension.from_exponents((0,1,0,0,0,0,0))
TIME = Dimension.from_exponents((0,0,1,0,0,0,0))
CURRENT = Dimension.from_exponents((0,0,0,1,0,0,0))
TEMPERATURE = Dimension.from_exponents((0,0,0,0,1,0,0))
AMOUNT = Dimension.from_exponents((0,0,0,0,0,1,0))
LUMINOUS_INTENSITY = Dimension.from_exponents((0,0,0,0,0,0,1))
VELOCITY = LENGTH / TIME
ACCELERATION = LENGTH / (TIME ** 2)
FORCE = MASS * ACCELERATION
PRESSURE = FORCE / (LENGTH ** 2)
ENERGY = FORCE * LENGTH
POWER = ENERGY / TIME
