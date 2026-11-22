"""Static engineering-expression type inference for canonical EIR.

This layer computes types only; it never evaluates numerical values or executes
solver code. Tensor broadcasting and implicit frame transforms are deliberately
unsupported so ambiguous engineering semantics fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Mapping

from gdec.types.dimensions import DIMENSIONLESS, Dimension
from gdec.types.errors import DimensionError, QuantityKindError, ShapeError
from gdec.types.units import SI_UNITS

QuantityKind = str
_VALID_KINDS = {"linear", "absolute_temperature", "temperature_interval"}


class ExpressionTypeError(ValueError):
    """Raised when an engineering expression is not well-typed."""


@dataclass(frozen=True, slots=True)
class ValueType:
    dimension: Dimension
    kind: QuantityKind = "linear"
    shape: tuple[int, ...] = ()
    frame_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, Dimension):
            raise TypeError("ValueType.dimension must be a Dimension.")
        if self.kind not in _VALID_KINDS:
            raise QuantityKindError(f"Unsupported quantity kind: {self.kind!r}.")
        if self.kind != "linear" and self.dimension != SI_UNITS.get("K").dimension:
            raise QuantityKindError("Temperature quantity kinds require temperature dimension.")
        if not isinstance(self.shape, tuple):
            object.__setattr__(self, "shape", tuple(self.shape))
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in self.shape):
            raise ShapeError("Expression shape extents must be positive integers.")
        if self.frame_id is not None and (not isinstance(self.frame_id, str) or not self.frame_id.strip()):
            raise ShapeError("Frame IDs must be non-empty strings when supplied.")
        if self.frame_id is not None and not self.shape:
            raise ShapeError("A scalar expression cannot carry a coordinate frame.")


class Expr:
    """Marker base class for immutable typed-expression nodes."""


@dataclass(frozen=True, slots=True)
class Literal(Expr):
    value: float
    value_type: ValueType


@dataclass(frozen=True, slots=True)
class ParameterRef(Expr):
    parameter_id: str


@dataclass(frozen=True, slots=True)
class FieldRef(Expr):
    field_id: str


@dataclass(frozen=True, slots=True)
class ExpressionRef(Expr):
    expression_id: str


@dataclass(frozen=True, slots=True)
class Negate(Expr):
    operand: Expr


@dataclass(frozen=True, slots=True)
class Binary(Expr):
    operator: str
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Power(Expr):
    operand: Expr
    exponent: Fraction


@dataclass(frozen=True, slots=True)
class ExpressionEnvironment:
    parameters: Mapping[str, ValueType] = field(default_factory=dict)
    fields: Mapping[str, ValueType] = field(default_factory=dict)
    expressions: Mapping[str, Expr] = field(default_factory=dict)


def environment_from_eir(problem) -> ExpressionEnvironment:
    """Build a type environment from a validated EngineeringProblemIR."""
    parameters = {}
    for item in problem.physical_model.parameters:
        unit = SI_UNITS.get(item.unit)
        parameters[item.id] = ValueType(unit.dimension, item.quantity_kind)
    fields = {}
    for item in problem.physical_model.fields:
        dimension = item.dimension.to_dimension()
        frame = item.coordinate_frame_id
        fields[item.id] = ValueType(dimension, item.quantity_kind, item.shape, frame)
    return ExpressionEnvironment(parameters=parameters, fields=fields)


def _same_value_shape(left: ValueType, right: ValueType) -> None:
    if left.shape != right.shape:
        raise ShapeError(
            f"Expression shape mismatch: {left.shape!r} != {right.shape!r}; "
            "implicit broadcasting is not supported."
        )
    if left.frame_id != right.frame_id:
        raise ShapeError(
            "Expression coordinate-frame mismatch; an explicit transform is required."
        )


def _add_type(left: ValueType, right: ValueType, *, subtract: bool) -> ValueType:
    if left.dimension != right.dimension:
        raise DimensionError(
            f"Cannot {'subtract' if subtract else 'add'} dimensions "
            f"{left.dimension} and {right.dimension}."
        )
    _same_value_shape(left, right)
    a, b = left.kind, right.kind
    if subtract:
        if a == b == "absolute_temperature":
            result_kind = "temperature_interval"
        elif a == "absolute_temperature" and b == "temperature_interval":
            result_kind = "absolute_temperature"
        elif a == b == "linear":
            result_kind = "linear"
        elif a == b == "temperature_interval":
            result_kind = "temperature_interval"
        else:
            raise QuantityKindError("Invalid quantity-kind combination for subtraction.")
    else:
        if a == b == "absolute_temperature":
            raise QuantityKindError("Adding two absolute temperatures is undefined.")
        if {a, b} == {"absolute_temperature", "temperature_interval"}:
            result_kind = "absolute_temperature"
        elif a == b == "linear":
            result_kind = "linear"
        elif a == b == "temperature_interval":
            result_kind = "temperature_interval"
        else:
            raise QuantityKindError("Invalid quantity-kind combination for addition.")
    return ValueType(left.dimension, result_kind, left.shape, left.frame_id)


def _multiply_type(left: ValueType, right: ValueType, *, divide: bool) -> ValueType:
    if left.kind == "absolute_temperature" or right.kind == "absolute_temperature":
        raise QuantityKindError("Absolute temperatures cannot be multiplied or divided.")
    if left.shape or right.shape:
        raise ShapeError(
            "Tensor multiplication/division requires an explicit contraction operator; "
            "implicit tensor algebra is not supported."
        )
    dimension = left.dimension / right.dimension if divide else left.dimension * right.dimension
    if left.kind == "temperature_interval" and right.dimension.is_dimensionless:
        kind = "temperature_interval"
    elif not divide and right.kind == "temperature_interval" and left.dimension.is_dimensionless:
        kind = "temperature_interval"
    else:
        kind = "linear"
    return ValueType(dimension, kind)


def infer_expression_type(
    expression: Expr,
    environment: ExpressionEnvironment,
) -> ValueType:
    """Infer an expression's physical type, rejecting ambiguous operations."""
    active: set[str] = set()
    cache: dict[str, ValueType] = {}

    def visit(node: Expr) -> ValueType:
        if isinstance(node, Literal):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ExpressionTypeError("Expression literals must be real numeric scalars.")
            import math
            if not math.isfinite(float(node.value)):
                raise ExpressionTypeError("Expression literals must be finite.")
            if not isinstance(node.value_type, ValueType):
                raise ExpressionTypeError("Literal requires a ValueType.")
            if node.value_type.kind == "absolute_temperature" and node.value < 0:
                raise QuantityKindError("Absolute-temperature literal cannot be below 0 K.")
            return node.value_type
        if isinstance(node, ParameterRef):
            try:
                return environment.parameters[node.parameter_id]
            except KeyError as exc:
                raise ExpressionTypeError(f"Unknown parameter reference: {node.parameter_id!r}.") from exc
        if isinstance(node, FieldRef):
            try:
                return environment.fields[node.field_id]
            except KeyError as exc:
                raise ExpressionTypeError(f"Unknown field reference: {node.field_id!r}.") from exc
        if isinstance(node, ExpressionRef):
            key = node.expression_id
            if key in cache:
                return cache[key]
            if key in active:
                raise ExpressionTypeError(f"Expression reference cycle detected at {key!r}.")
            try:
                target = environment.expressions[key]
            except KeyError as exc:
                raise ExpressionTypeError(f"Unknown expression reference: {key!r}.") from exc
            active.add(key)
            try:
                result = visit(target)
                cache[key] = result
                return result
            finally:
                active.remove(key)
        if isinstance(node, Negate):
            operand = visit(node.operand)
            if operand.kind == "absolute_temperature":
                raise QuantityKindError("An absolute temperature cannot be negated.")
            return operand
        if isinstance(node, Binary):
            left, right = visit(node.left), visit(node.right)
            if node.operator == "add":
                return _add_type(left, right, subtract=False)
            if node.operator == "subtract":
                return _add_type(left, right, subtract=True)
            if node.operator == "multiply":
                return _multiply_type(left, right, divide=False)
            if node.operator == "divide":
                return _multiply_type(left, right, divide=True)
            raise ExpressionTypeError(f"Unsupported binary operator: {node.operator!r}.")
        if isinstance(node, Power):
            operand = visit(node.operand)
            if operand.kind != "linear":
                raise QuantityKindError("Only linear quantities may be raised to a power.")
            if operand.shape:
                raise ShapeError("Tensor powers require an explicit tensor operator.")
            exponent = Fraction(node.exponent)
            return ValueType(operand.dimension ** exponent)
        raise ExpressionTypeError(f"Unsupported expression node: {type(node).__name__}.")

    return visit(expression)


__all__ = [
    "Binary", "Expr", "ExpressionEnvironment", "ExpressionRef",
    "ExpressionTypeError", "FieldRef", "Literal", "Negate",
    "ParameterRef", "Power", "ValueType", "environment_from_eir",
    "infer_expression_type",
]
