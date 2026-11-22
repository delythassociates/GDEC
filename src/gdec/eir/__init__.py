"""Canonical engineering IR APIs.

The 0.1.0 module intentionally implements a small semantic core only.
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
]
