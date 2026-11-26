"""
Versioned Engineering Evidence Record and canonical deterministic hashing for GDEC WP3.

IMPORTANT NON-CLAIM:
A canonical SHA-256 hash verifies byte-level / structural integrity of the serialized
record only. It does NOT prove scientific correctness, physical validity, authorship,
or cryptographic authenticity.
"""
from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


EVIDENCE_SCHEMA_VERSION = "1.0.0"

SUPPORTED_QOI_UNITS = frozenset({"m", "mm", "Pa", "MPa", "N", "dimensionless", "pct"})


class EstimatorClassification(str, Enum):
    """Explicit scientific classification of an error estimator or indicator."""
    HEURISTIC = "heuristic"
    DWR_ASYMPTOTIC_ESTIMATE = "dwr_asymptotic_estimate"
    REFERENCE_BASED_ESTIMATE = "reference_based_estimate"
    MATHEMATICALLY_ESTABLISHED_BOUND = "mathematically_established_bound"


class ParentArtifactRef(BaseModel):
    """Provenance link to an upstream artifact."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    artifact_type: str = Field(..., min_length=1)
    sha256_hash: str = Field(..., min_length=64, max_length=64)


class CompactProblemFeatureVector(BaseModel):
    """Compact problem-feature vector per Session 2 Owner Directive for future learning."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_width: float = Field(..., gt=0.0)
    domain_height: float = Field(..., gt=0.0)
    aspect_ratio: float = Field(..., gt=0.0)
    num_loads: int = Field(..., ge=0)
    num_fixed_boundaries: int = Field(..., ge=0)
    youngs_modulus: float = Field(..., gt=0.0)
    poissons_ratio: float = Field(..., gt=-1.0, lt=0.5)
    constitutive_assumption: Literal["plane_stress", "plane_strain"]
    refinement_strategy: str = Field(..., min_length=1)
    initial_dofs: int = Field(..., ge=0)
    max_dofs_budget: int = Field(..., gt=0)


class OutcomeMetrics(BaseModel):
    """Compact outcome metrics per Session 2 Owner Directive."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    final_dofs: int = Field(..., ge=0)
    refinement_steps: int = Field(..., ge=0)
    wall_time_sec: float = Field(..., ge=0.0)
    estimator_value: Optional[float] = Field(default=None)

    @field_validator("wall_time_sec", "estimator_value")
    @classmethod
    def _check_finite_outcome(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Non-finite numeric value in OutcomeMetrics: {v}")
        return v


class RefusalRuleEvaluation(BaseModel):
    """Structured result of evaluating a single deterministic refusal rule."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    triggered: bool
    reason: str = Field(default="")
    diagnostic_context: Dict[str, Any] = Field(default_factory=dict)


class EngineeringEvidenceRecord(BaseModel):
    """
    Versioned, machine-checkable Engineering Evidence Record (schema v1.0.0).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=EVIDENCE_SCHEMA_VERSION)
    record_id: str = Field(..., min_length=1)
    canonical_eir_hash: str = Field(..., min_length=64, max_length=64)
    mesh_identity: str = Field(..., min_length=1)
    mesh_hash: str = Field(..., min_length=64, max_length=64)
    material_identity: str = Field(..., min_length=1)
    boundary_conditions_identity: str = Field(..., min_length=1)
    solver_identity: str = Field(..., min_length=1)
    solver_version: str = Field(..., min_length=1)
    solver_config: Dict[str, Any] = Field(default_factory=dict)
    backend: str = Field(..., min_length=1)
    numerical_precision: str = Field(..., min_length=1)
    dependency_versions: Dict[str, str] = Field(default_factory=dict)
    dof_count: int = Field(..., ge=0)
    mesh_metadata: Dict[str, Any] = Field(default_factory=dict)
    qoi_id: str = Field(..., min_length=1)
    qoi_name: str = Field(..., min_length=1)
    qoi_units: str = Field(..., min_length=1)
    qoi_value: Optional[float] = Field(default=None)
    estimator_identity: str = Field(..., min_length=1)
    estimator_classification: EstimatorClassification
    error_estimate: Optional[float] = Field(default=None)
    error_estimate_interpretation: str = Field(..., min_length=1)
    effectivity_evidence: Any = Field(default="NONE")
    model_applicability_status: Literal["established", "unestablished", "invalidated"]
    verification_validation_status: str = Field(..., min_length=1)
    problem_features: CompactProblemFeatureVector
    outcome_metrics: OutcomeMetrics
    refusal_evaluations: List[RefusalRuleEvaluation] = Field(default_factory=list)
    refused: bool
    refusal_reasons: List[str] = Field(default_factory=list)
    resource_consumption: Dict[str, Any] = Field(default_factory=dict)
    parent_artifacts: List[ParentArtifactRef] = Field(default_factory=list)
    evidence_stale: bool = Field(default=False)
    evidence_invalidated: bool = Field(default=False)
    canonical_result_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("schema_version")
    @classmethod
    def _check_schema_version(cls, v: str) -> str:
        if v != EVIDENCE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported evidence schema_version: '{v}'")
        return v

    @field_validator("qoi_value", "error_estimate")
    @classmethod
    def _check_finite_if_present(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Non-finite numeric value is not permitted in evidence record: {v}")
        return v

    def to_canonical_json(self) -> str:
        return canonical_json_dumps(self.model_dump(mode="json"))

    @classmethod
    def export_json_schema(cls) -> Dict[str, Any]:
        return cls.model_json_schema()


def canonical_json_dumps(data: Any) -> str:
    """Deterministic canonical JSON serialization (sorted keys, compact separators, allow_nan=False)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def compute_canonical_hash(payload: Dict[str, Any]) -> str:
    """
    Compute SHA-256 over canonical JSON representation of payload,
    excluding 'canonical_result_hash' if present.
    """
    filtered = {k: v for k, v in payload.items() if k != "canonical_result_hash"}
    encoded = canonical_json_dumps(filtered).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_evidence_record_with_hash(payload: Dict[str, Any]) -> EngineeringEvidenceRecord:
    """Populate canonical_result_hash deterministically over the normalized schema dump."""
    data = dict(payload)
    data["canonical_result_hash"] = "0" * 64
    prelim = EngineeringEvidenceRecord.model_validate(data)
    actual_hash = compute_canonical_hash(prelim.model_dump(mode="json"))
    return prelim.model_copy(update={"canonical_result_hash": actual_hash})
