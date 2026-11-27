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
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from gdec.dse.evidence import ValidationStatus


EVIDENCE_SCHEMA_VERSION = "1.1.0"
LEGACY_EVIDENCE_SCHEMA_VERSION = "1.0.0"

SUPPORTED_QOI_UNITS = frozenset({"m", "mm", "Pa", "MPa", "N", "dimensionless", "pct"})
SUPPORTED_CERT_CHECKERS: frozenset[str] = frozenset()


class EstimatorClassification(str, Enum):
    """Explicit scientific classification of an error estimator or indicator."""
    HEURISTIC = "heuristic"
    DWR_ASYMPTOTIC_ESTIMATE = "dwr_asymptotic_estimate"
    REFERENCE_BASED_ESTIMATE = "reference_based_estimate"
    MATHEMATICALLY_ESTABLISHED_BOUND = "mathematically_established_bound"


class QualificationStatus(str, Enum):
    """Explicit separation of refusal/integrity from engineering decision qualification."""
    REFUSED = "REFUSED"
    NOT_QUALIFIED_UNASSESSED_VV = "NOT_QUALIFIED_UNASSESSED_VV"
    NOT_QUALIFIED_APPLICABILITY = "NOT_QUALIFIED_APPLICABILITY"
    NOT_QUALIFIED_NOT_CONVERGED = "NOT_QUALIFIED_NOT_CONVERGED"
    QUALIFIED = "QUALIFIED"


class QoIEpistemicRole(str, Enum):
    """Explicit epistemic role of the reported QoI / error value."""
    NUMERICAL_OBSERVATION = "numerical_observation"
    HEURISTIC_ESTIMATE = "heuristic_estimate"
    ASYMPTOTIC_INDICATOR = "asymptotic_indicator"
    REFERENCE_BASED_ESTIMATE = "reference_based_estimate"
    CERTIFIED_BOUND = "certified_bound"
    UNAVAILABLE = "unavailable"


class ParentArtifactRef(BaseModel):
    """Provenance link to an upstream artifact."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    artifact_type: str = Field(..., min_length=1)
    sha256_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("artifact_id", "artifact_type")
    @classmethod
    def _non_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ParentArtifactRef identifiers must not be whitespace-only.")
        return v


class ReferenceEffectivityEvidence(BaseModel):
    """Typed effectivity evidence from a reference mesh comparison."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["reference_effectivity"] = "reference_effectivity"
    adequate: bool
    reference_dofs: StrictInt = Field(..., gt=0)
    reference_qoi: float = Field(..., allow_inf_nan=False)
    effectivity_index: Optional[float] = Field(default=None, allow_inf_nan=False)
    discretization_uncertainty_pct: Optional[float] = Field(default=None, allow_inf_nan=False)


class BoundCertificateEvidence(BaseModel):
    """Typed certificate reference required for mathematically_established_bound claims."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["bound_certificate"] = "bound_certificate"
    checker_identity: str = Field(..., min_length=1)
    checker_version: str = Field(..., min_length=1)
    estimator_identity: str = Field(..., min_length=1)
    model_identity: str = Field(..., min_length=1)
    certificate_hash: str = Field(..., min_length=64, max_length=64)
    proof_obligations_satisfied: bool
    assumptions: List[str] = Field(..., min_length=1)


class CompactProblemFeatureVector(BaseModel):
    """Compact problem-feature vector per Session 2 Owner Directive for future learning."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_width: float = Field(..., gt=0.0, allow_inf_nan=False)
    domain_height: float = Field(..., gt=0.0, allow_inf_nan=False)
    aspect_ratio: float = Field(..., gt=0.0, allow_inf_nan=False)
    num_loads: StrictInt = Field(..., ge=0)
    num_fixed_boundaries: StrictInt = Field(..., ge=0)
    youngs_modulus: float = Field(..., gt=0.0, allow_inf_nan=False)
    poissons_ratio: float = Field(..., gt=-1.0, lt=0.5, allow_inf_nan=False)
    constitutive_assumption: Literal["plane_stress", "plane_strain"]
    refinement_strategy: str = Field(..., min_length=1)
    initial_dofs: StrictInt = Field(..., ge=0)
    max_dofs_budget: StrictInt = Field(..., gt=0)


class OutcomeMetrics(BaseModel):
    """Compact outcome metrics per Session 2 Owner Directive."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    final_dofs: StrictInt = Field(..., ge=0)
    refinement_steps: StrictInt = Field(..., ge=0)
    wall_time_sec: float = Field(..., ge=0.0, allow_inf_nan=False)
    estimator_value: Optional[float] = Field(default=None, allow_inf_nan=False)


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
    Versioned, machine-checkable Engineering Evidence Record (schema v1.1.0).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=EVIDENCE_SCHEMA_VERSION)
    record_id: str = Field(..., min_length=1)
    problem_ir_hash: str = Field(..., min_length=64, max_length=64)
    canonical_eir_hash: str = Field(..., min_length=64, max_length=64)
    execution_plan_hash: str = Field(..., min_length=64, max_length=64)
    source_revision: str = Field(..., min_length=1)
    mesh_identity: str = Field(..., min_length=1)
    mesh_hash: str = Field(..., min_length=64, max_length=64)
    material_identity: str = Field(..., min_length=1)
    boundary_conditions_identity: str = Field(..., min_length=1)
    solver_identity: str = Field(..., min_length=1)
    solver_version: str = Field(..., min_length=1)
    linear_solver_type: str = Field(..., min_length=1)
    compute_device: str = Field(..., min_length=1)
    solver_config: Dict[str, Any] = Field(default_factory=dict)
    backend: str = Field(..., min_length=1)
    numerical_precision: str = Field(..., min_length=1)
    dependency_versions: Dict[str, str] = Field(default_factory=dict)
    dof_count: StrictInt = Field(..., ge=0)
    mesh_metadata: Dict[str, Any] = Field(default_factory=dict)
    qoi_id: str = Field(..., min_length=1)
    qoi_name: str = Field(..., min_length=1)
    qoi_units: str = Field(..., min_length=1)
    qoi_value: Optional[float] = Field(default=None, allow_inf_nan=False)
    qoi_epistemic_role: QoIEpistemicRole
    estimator_identity: str = Field(..., min_length=1)
    estimator_classification: EstimatorClassification
    error_estimate: Optional[float] = Field(default=None, allow_inf_nan=False)
    error_estimate_units: str = Field(..., min_length=1)
    error_estimate_quantity: str = Field(..., min_length=1)
    error_estimate_interpretation: str = Field(..., min_length=1)
    effectivity_evidence: Union[Literal["NONE"], ReferenceEffectivityEvidence, BoundCertificateEvidence] = Field(default="NONE")
    model_applicability_status: Literal["established", "unestablished", "invalidated"]
    model_applicability_reasons: List[str] = Field(default_factory=list)
    numerical_convergence_status: Literal["converged", "not_converged", "aborted_pre_solve", "solver_failed"]
    verification_status: ValidationStatus
    validation_status: ValidationStatus
    verification_validation_status: ValidationStatus
    qualification_status: QualificationStatus
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
            raise ValueError(f"Unsupported evidence schema_version: '{v}'. Expected '{EVIDENCE_SCHEMA_VERSION}'.")
        return v

    @model_validator(mode="after")
    def _validate_epistemic_invariants(self) -> "EngineeringEvidenceRecord":
        if self.qualification_status == QualificationStatus.QUALIFIED:
            if self.refused:
                raise ValueError("Refused record cannot have qualification_status='QUALIFIED'.")
            if self.numerical_convergence_status != "converged":
                raise ValueError("Non-converged record cannot have qualification_status='QUALIFIED'.")
            if self.model_applicability_status != "established":
                raise ValueError("Record without established model applicability cannot be 'QUALIFIED'.")
            if self.verification_status not in (
                ValidationStatus.VERIFIED,
                ValidationStatus.VALIDATED,
                ValidationStatus.INDEPENDENTLY_VALIDATED,
            ):
                raise ValueError(f"Record with verification_status={self.verification_status.value} cannot be 'QUALIFIED'.")
            if self.validation_status not in (
                ValidationStatus.VALIDATED,
                ValidationStatus.INDEPENDENTLY_VALIDATED,
            ):
                raise ValueError(f"Record with validation_status={self.validation_status.value} cannot be 'QUALIFIED'.")
            if self.evidence_stale or self.evidence_invalidated:
                raise ValueError("Stale or invalidated record cannot be 'QUALIFIED'.")
            if self.qoi_value is None:
                raise ValueError("Record without QoI value cannot be 'QUALIFIED'.")
            if not bool(self.resource_consumption.get("target_tolerance_met", False)):
                raise ValueError("Record without target_tolerance_met=True cannot be 'QUALIFIED'.")
            if self.verification_validation_status not in (
                ValidationStatus.VALIDATED,
                ValidationStatus.INDEPENDENTLY_VALIDATED,
            ):
                raise ValueError(
                    f"Record with verification_validation_status={self.verification_validation_status.value} cannot be 'QUALIFIED'."
                )
        if self.estimator_classification == EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND:
            if not isinstance(self.effectivity_evidence, BoundCertificateEvidence):
                raise ValueError("mathematically_established_bound requires a BoundCertificateEvidence object.")
        if self.estimator_classification == EstimatorClassification.REFERENCE_BASED_ESTIMATE:
            if not isinstance(self.effectivity_evidence, ReferenceEffectivityEvidence):
                raise ValueError("reference_based_estimate requires a ReferenceEffectivityEvidence object.")
        return self

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
