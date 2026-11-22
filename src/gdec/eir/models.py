"""Versioned canonical engineering-problem IR core.

This module implements only the reviewed semantic core: problem identity,
coordinate frames, domains, scalar parameters, fields, and direct field-value
quantities of interest. It is not a complete physics or variational IR.
"""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gdec.types.dimensions import Dimension
from gdec.types.units import SI_UNITS


EIR_KIND = "gdec.engineering_problem"
EIR_SCHEMA_VERSION = "0.1.0"
EIR_UNIT_REGISTRY_ID = "gdec-si-engineering-0.1"

# Freeze the unit definitions used by this schema version. A user extending
# the general-purpose SI_UNITS registry cannot silently change EIR semantics.
_EIR_UNITS = dict(SI_UNITS.units)
_EIR_KINDS = {"linear", "absolute_temperature", "temperature_interval"}
_BASE_UNIT_SYMBOLS = ("1", "kg", "m", "s", "A", "K", "delta_K", "mol", "cd", "N", "Pa", "J", "W")
_BASE_UNITS = {
    (candidate.dimension, candidate.kind): candidate
    for symbol in _BASE_UNIT_SYMBOLS
    for candidate in (_EIR_UNITS[symbol],)
}


def _canonical_unit(unit):
    try:
        return _BASE_UNITS[(unit.dimension, unit.kind)]
    except KeyError as exc:
        raise ValueError(
            f"No coherent base unit is defined for dimension {unit.dimension} and kind {unit.kind!r}."
        ) from exc


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _unit(symbol: str):
    try:
        return _EIR_UNITS[symbol]
    except KeyError as exc:
        raise ValueError(
            f"Unit {symbol!r} is not in the pinned {EIR_UNIT_REGISTRY_ID} registry."
        ) from exc


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("Identifiers must be non-empty strings without surrounding whitespace.")
    return value


def _finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Numeric values must be finite real numbers; booleans are not accepted.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Numeric values must be finite.")
    return 0.0 if result == 0.0 else result


class EIRModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DimensionVector(EIRModel):
    """Seven SI exponents in M, L, T, I, Theta, N, J order.

    Each exponent is stored as a canonical rational string, e.g. "0", "-2",
    or "1/2", making the wire representation exact and JSON-stable.
    """

    exponents: tuple[str, ...]

    @field_validator("exponents", mode="before")
    @classmethod
    def canonicalise_exponents(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (tuple, list)) or len(value) != 7:
            raise ValueError("Dimension vectors require exactly seven SI exponents.")
        result: list[str] = []
        for exponent in value:
            if isinstance(exponent, bool):
                raise ValueError("Dimension exponents cannot be booleans.")
            try:
                rational = Fraction(str(exponent))
            except (ValueError, ZeroDivisionError) as exc:
                raise ValueError(f"Invalid rational dimension exponent: {exponent!r}") from exc
            result.append(_fraction_text(rational))
        return tuple(result)

    @classmethod
    def from_dimension(cls, dimension: Dimension) -> "DimensionVector":
        return cls(exponents=tuple(_fraction_text(v) for v in dimension.exponents))

    def to_dimension(self) -> Dimension:
        return Dimension.from_exponents(Fraction(v) for v in self.exponents)


class ProblemIdentity(EIRModel):
    id: str
    name: str = Field(min_length=1)
    description: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Problem name cannot be blank.")
        return value


class CoordinateFrameIR(EIRModel):
    id: str
    dimension: int = Field(ge=1, le=3)
    parent_id: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier(value)

    @field_validator("dimension", mode="before")
    @classmethod
    def reject_boolean_dimension(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Coordinate-frame dimension cannot be boolean.")
        return value

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, value: str | None) -> str | None:
        return None if value is None else _identifier(value)


class DomainIR(EIRModel):
    id: str
    spatial_dimension: int = Field(ge=1, le=3)
    coordinate_frame_id: str

    @field_validator("id", "coordinate_frame_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _identifier(value)

    @field_validator("spatial_dimension", mode="before")
    @classmethod
    def reject_boolean_dimension(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Domain spatial dimension cannot be boolean.")
        return value


class QuantityParameterIR(EIRModel):
    id: str
    value: float
    unit: str
    quantity_kind: Literal["linear", "absolute_temperature", "temperature_interval"] = "linear"
    description: str | None = None

    @field_validator("id", "unit")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return _identifier(value)

    @field_validator("value", mode="before")
    @classmethod
    def validate_numeric_value(cls, value: Any) -> float:
        return _finite_number(value)

    @model_validator(mode="after")
    def validate_unit_semantics(self) -> "QuantityParameterIR":
        unit = _unit(self.unit)
        if unit.kind != self.quantity_kind:
            raise ValueError(
                f"Unit {self.unit!r} has kind {unit.kind!r}, not {self.quantity_kind!r}."
            )
        unit.to_base(self.value)
        return self


class FieldIR(EIRModel):
    id: str
    domain_id: str
    dimension: DimensionVector
    unit: str
    quantity_kind: Literal["linear", "absolute_temperature", "temperature_interval"] = "linear"
    shape: tuple[int, ...] = ()
    coordinate_frame_id: str | None = None
    function_space: str = Field(min_length=1)

    @field_validator("id", "domain_id", "unit")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return _identifier(value)

    @field_validator("coordinate_frame_id")
    @classmethod
    def validate_optional_frame_id(cls, value: str | None) -> str | None:
        return None if value is None else _identifier(value)

    @field_validator("function_space")
    @classmethod
    def validate_function_space(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Function-space name cannot be blank.")
        return value

    @field_validator("shape", mode="before")
    @classmethod
    def validate_shape(cls, value: Any) -> tuple[int, ...]:
        if not isinstance(value, (tuple, list)):
            raise ValueError("Field shape must be a list or tuple of positive integers.")
        extents = tuple(value)
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in extents):
            raise ValueError("Field shape extents must be positive integers.")
        return extents

    @model_validator(mode="after")
    def validate_unit_dimension(self) -> "FieldIR":
        unit = _unit(self.unit)
        if unit.dimension != self.dimension.to_dimension():
            raise ValueError(
                f"Field unit {self.unit!r} has dimension {unit.dimension}; "
                f"declared dimension is {self.dimension.to_dimension()}."
            )
        if unit.kind != self.quantity_kind:
            raise ValueError(
                f"Field unit {self.unit!r} has kind {unit.kind!r}, "
                f"not {self.quantity_kind!r}."
            )
        return self


class QuantityOfInterestIR(EIRModel):
    id: str
    field_id: str
    operation: Literal["field_value"] = "field_value"
    unit: str

    @field_validator("id", "field_id", "unit")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return _identifier(value)


class PhysicalModelIR(EIRModel):
    coordinate_frames: tuple[CoordinateFrameIR, ...] = ()
    domains: tuple[DomainIR, ...] = ()
    parameters: tuple[QuantityParameterIR, ...] = ()
    fields: tuple[FieldIR, ...] = ()


class EngineeringProblemIR(EIRModel):
    """Validated, solver-independent core of the canonical GDEC EIR."""

    kind: Literal["gdec.engineering_problem"] = EIR_KIND
    schema_version: Literal["0.1.0"] = EIR_SCHEMA_VERSION
    unit_registry_id: Literal["gdec-si-engineering-0.1"] = EIR_UNIT_REGISTRY_ID
    problem: ProblemIdentity
    physical_model: PhysicalModelIR = Field(default_factory=PhysicalModelIR)
    quantities_of_interest: tuple[QuantityOfInterestIR, ...] = ()

    @model_validator(mode="after")
    def validate_document_invariants(self) -> "EngineeringProblemIR":
        # All semantic entity IDs are unique within the document.
        ids = [self.problem.id]
        ids.extend(item.id for item in self.physical_model.coordinate_frames)
        ids.extend(item.id for item in self.physical_model.domains)
        ids.extend(item.id for item in self.physical_model.parameters)
        ids.extend(item.id for item in self.physical_model.fields)
        ids.extend(item.id for item in self.quantities_of_interest)
        if len(ids) != len(set(ids)):
            raise ValueError("Entity identifiers must be globally unique within an EIR document.")

        frames = {item.id: item for item in self.physical_model.coordinate_frames}
        domains = {item.id: item for item in self.physical_model.domains}
        fields = {item.id: item for item in self.physical_model.fields}

        # Every parent reference resolves and frame dimensions agree.
        for frame in frames.values():
            if frame.parent_id is not None:
                parent = frames.get(frame.parent_id)
                if parent is None:
                    raise ValueError(
                        f"Coordinate frame {frame.id!r} references missing parent {frame.parent_id!r}."
                    )
                if parent.dimension != frame.dimension:
                    raise ValueError("Parent and child coordinate frames must have equal dimensions.")

        # Reject parent cycles with a linear-time colour/visited traversal.
        completed: set[str] = set()
        for frame_id in frames:
            path: set[str] = set()
            current: str | None = frame_id
            while current is not None and current not in completed:
                if current in path:
                    raise ValueError(f"Coordinate-frame parent cycle detected at {current!r}.")
                path.add(current)
                current = frames[current].parent_id
            completed.update(path)

        for domain in domains.values():
            frame = frames.get(domain.coordinate_frame_id)
            if frame is None:
                raise ValueError(
                    f"Domain {domain.id!r} references missing frame {domain.coordinate_frame_id!r}."
                )
            if frame.dimension != domain.spatial_dimension:
                raise ValueError(
                    f"Domain {domain.id!r} spatial dimension does not match its coordinate frame."
                )

        for field in self.physical_model.fields:
            domain = domains.get(field.domain_id)
            if domain is None:
                raise ValueError(
                    f"Field {field.id!r} references missing domain {field.domain_id!r}."
                )
            if field.coordinate_frame_id is not None:
                frame = frames.get(field.coordinate_frame_id)
                if frame is None:
                    raise ValueError(
                        f"Field {field.id!r} references missing frame {field.coordinate_frame_id!r}."
                    )
                if field.coordinate_frame_id != domain.coordinate_frame_id:
                    raise ValueError(
                        f"Field {field.id!r} frame must match its domain frame; "
                        "explicit transform entities are not part of EIR 0.1."
                    )
                if not field.shape or field.shape[0] != frame.dimension:
                    raise ValueError(
                        f"Field {field.id!r} leading shape extent must equal its frame dimension."
                    )

        for qoi in self.quantities_of_interest:
            field = fields.get(qoi.field_id)
            if field is None:
                raise ValueError(
                    f"QoI {qoi.id!r} references missing field {qoi.field_id!r}."
                )
            output_unit = _unit(qoi.unit)
            field_unit = _unit(field.unit)
            if output_unit.dimension != field_unit.dimension or output_unit.kind != field_unit.kind:
                raise ValueError(
                    f"QoI {qoi.id!r} output unit is incompatible with field {field.id!r}."
                )
        return self

    def canonical_json(self) -> str:
        """Return deterministic JSON with semantically unordered entities sorted by ID."""
        payload = self.model_dump(mode="json", exclude_none=True)
        physical = payload["physical_model"]
        for collection in ("coordinate_frames", "domains", "parameters", "fields"):
            physical[collection] = sorted(physical[collection], key=lambda item: item["id"])
        payload["quantities_of_interest"] = sorted(
            payload["quantities_of_interest"], key=lambda item: item["id"]
        )

        # Normalize value-bearing parameters to coherent SI base values and
        # normalize all declared/output units to the corresponding base unit.
        for parameter in physical["parameters"]:
            source_unit = _unit(parameter["unit"])
            base_unit = _canonical_unit(source_unit)
            parameter["value"] = source_unit.to_base(parameter["value"])
            parameter["unit"] = base_unit.symbol
        for field in physical["fields"]:
            field["unit"] = _canonical_unit(_unit(field["unit"])).symbol
        for qoi in payload["quantities_of_interest"]:
            qoi["unit"] = _canonical_unit(_unit(qoi["unit"])).symbol

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def canonical_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, source: str) -> "EngineeringProblemIR":
        return cls.model_validate_json(source)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent, exclude_none=True)
