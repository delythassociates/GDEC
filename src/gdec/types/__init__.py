"""Foundational, solver-independent engineering type primitives for GDEC."""
from .dimensions import (Dimension, DIMENSIONLESS, MASS, LENGTH, TIME, CURRENT, TEMPERATURE, AMOUNT, LUMINOUS_INTENSITY, VELOCITY, ACCELERATION, FORCE, PRESSURE, ENERGY, POWER)
from .units import Unit, UnitRegistry, SI_UNITS
from .quantities import Quantity
from .shapes import TensorShape, CoordinateFrame, ValueShape, FieldType
from .errors import TypeSystemError, DimensionError, UnitError, QuantityKindError, ShapeError

__all__ = ["Dimension", "DIMENSIONLESS", "MASS", "LENGTH", "TIME", "CURRENT", "TEMPERATURE", "AMOUNT", "LUMINOUS_INTENSITY", "VELOCITY", "ACCELERATION", "FORCE", "PRESSURE", "ENERGY", "POWER", "Unit", "UnitRegistry", "SI_UNITS", "Quantity", "TensorShape", "CoordinateFrame", "ValueShape", "FieldType", "TypeSystemError", "DimensionError", "UnitError", "QuantityKindError", "ShapeError"]
