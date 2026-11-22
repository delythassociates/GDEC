"""Canonical engineering IR and static semantic-analysis APIs.

The 0.1.0 document schema is a deliberately restricted semantic core.
Expression typing is an additive analysis layer and does not change that
versioned document wire format.
"""
from .models import (
    EIR_KIND,
    EIR_SCHEMA_VERSION,
    EIR_UNIT_REGISTRY_ID,
    CoordinateFrameIR,
    DimensionVector,
    DomainIR,
    EngineeringProblemIR,
    FieldIR,
    PhysicalModelIR,
    ProblemIdentity,
    QuantityOfInterestIR,
    QuantityParameterIR,
)
from .expressions import (
    Binary,
    Expr,
    ExpressionEnvironment,
    ExpressionRef,
    ExpressionTypeError,
    FieldRef,
    Literal,
    Negate,
    ParameterRef,
    Power,
    ValueType,
    environment_from_eir,
    infer_expression_type,
)

__all__ = [
    "EIR_KIND",
    "EIR_SCHEMA_VERSION",
    "EIR_UNIT_REGISTRY_ID",
    "CoordinateFrameIR",
    "DimensionVector",
    "DomainIR",
    "EngineeringProblemIR",
    "FieldIR",
    "PhysicalModelIR",
    "ProblemIdentity",
    "QuantityOfInterestIR",
    "QuantityParameterIR",
    "Binary",
    "Expr",
    "ExpressionEnvironment",
    "ExpressionRef",
    "ExpressionTypeError",
    "FieldRef",
    "Literal",
    "Negate",
    "ParameterRef",
    "Power",
    "ValueType",
    "environment_from_eir",
    "infer_expression_type",
]
