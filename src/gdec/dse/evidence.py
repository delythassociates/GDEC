"""
Evidence assessment and provenance models for GDEC Decision Sufficiency Engine.
Provides strongly typed evidence records, verification/validation status tracking,
record-level eligibility auditing, and domain applicability verification.
"""

from __future__ import annotations
import math
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class ValidationStatus(str, Enum):
    """
    Formal maturity and credibility status of an engineering simulation or model.
    Enforces precise scientific distinctions:
    - UNASSESSED: No formal verification or validation has been conducted.
    - UNVALIDATED: Attempted validation was incomplete or uncertified.
    - VERIFIED: Code and solution verification confirmed (equations solved correctly).
    - VALIDATED: Model validated against physical experimental test data.
    - INDEPENDENTLY_VALIDATED: Validated by an independent third party or regulatory audit.
    - CALIBRATED: Material/constitutive parameters tuned against measured data.
    - REJECTED: Evidence was reviewed and explicitly discredited or disqualified.
    - EXPIRED: Evidence was valid previously but is no longer valid for this design revision.
    """
    UNASSESSED = "UNASSESSED"
    UNVALIDATED = "UNVALIDATED"
    VERIFIED = "VERIFIED"
    VALIDATED = "VALIDATED"
    INDEPENDENTLY_VALIDATED = "INDEPENDENTLY_VALIDATED"
    CALIBRATED = "CALIBRATED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class EvidenceEligibility(str, Enum):
    """
    Evaluated eligibility of an individual evidence record with respect to a Decision Contract.
    """
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNASSESSED = "UNASSESSED"
    INCOMPATIBLE_MODEL = "INCOMPATIBLE_MODEL"
    INCOMPATIBLE_DOMAIN = "INCOMPATIBLE_DOMAIN"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    INSUFFICIENT_METRIC = "INSUFFICIENT_METRIC"
    MISSING = "MISSING"


@dataclass(frozen=True)
class RecordEvaluationReport:
    """Detailed eligibility assessment for a single evidence record."""
    record_id: str
    category: str
    eligibility: EvidenceEligibility
    is_acceptable: bool
    reason: str
    validation_status: ValidationStatus
    model_reference: str
    applicable_domain: str


class EvidenceRecord(BaseModel):
    """Individual auditable evidence record supporting an engineering decision."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique evidence record identifier, e.g. 'EV-DISC-001'")
    category: str = Field(..., min_length=1, description="Evidence category, e.g. 'discretization_error'")
    provenance: str = Field(..., min_length=1, description="Origin or tool that generated this evidence")
    model_reference: str = Field(..., min_length=1, description="Target governing model or BVP identifier")
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.VERIFIED, description="Verification or validation credibility level"
    )
    applicable_domain: str = Field(..., min_length=1, description="Operational/geometric envelope where valid")
    numerical_metric: Optional[float] = Field(default=None, description="Quantitative error or convergence metric")
    assumptions_attested: List[str] = Field(default_factory=list, description="Assumptions attested by this record")
    validation_method: Optional[str] = Field(default=None, description="Method used to verify/validate this record")
    units: Optional[str] = Field(default=None, description="Units for numerical_metric")
    description: Optional[str] = Field(default=None, description="Detailed evidence notes")


class EvidenceAssessment(BaseModel):
    """
    Comprehensive evidence package submitted to evaluate a Decision Contract.
    Enforces that required evidence categories, model assumptions, and domain
    applicability are explicitly satisfied at record-level before any decision recommendation is rendered.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: str = Field(..., min_length=1, description="Unique assessment batch identifier")
    evidence_records: List[EvidenceRecord] = Field(
        ..., min_length=1, description="List of individual verified evidence records"
    )
    validated_assumptions: List[str] = Field(
        ..., min_length=1, description="List of physical and numerical assumptions attested as validated"
    )
    model_reference: str = Field(..., min_length=1, description="Target model identifier matching contract")
    applicable_domain: str = Field(..., min_length=1, description="Operating envelope matching contract")
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.VERIFIED, description="Overall validation status of the submitted model"
    )
    reference_scale: Optional[float] = Field(
        default=None, gt=0.0, description="Explicit positive reference scale (J_ref) in matching physical units"
    )
    provenance: str = Field(..., min_length=1, description="Audit chain provenance or author of this assessment")

    @property
    def supplied_categories(self) -> List[str]:
        """Return list of all evidence categories present in this assessment."""
        return list({rec.category for rec in self.evidence_records})

    def has_category(self, category: str) -> bool:
        """Check whether a specific evidence category is present."""
        return any(rec.category.strip().lower() == category.strip().lower() for rec in self.evidence_records)

    def evaluate_record_eligibility(
        self,
        required_categories: List[str],
        target_model: str,
        target_domain: str,
        required_status: str = "verified",
    ) -> Tuple[bool, Dict[str, List[RecordEvaluationReport]], List[str]]:
        """
        Evaluate every evidence record individually against the contract requirements.

        Policy:
        A required category is satisfied IF AND ONLY IF:
        1. It has at least one ACCEPTED EvidenceRecord; AND
        2. It contains ZERO REJECTED EvidenceRecords (rejected evidence in a required category taints it).

        Returns
        -------
        (all_categories_satisfied, reports_by_category, refusal_reasons)
        """
        reports_by_category: Dict[str, List[RecordEvaluationReport]] = {}
        refusal_reasons: List[str] = []

        # 0. Check for duplicate records with conflicting provenance or data
        seen_records: Dict[str, EvidenceRecord] = {}
        for rec in self.evidence_records:
            if rec.id in seen_records:
                prev = seen_records[rec.id]
                if prev.provenance.strip() != rec.provenance.strip():
                    refusal_reasons.append(
                        f"Duplicate record ID '{rec.id}' with conflicting provenance: "
                        f"'{prev.provenance}' vs '{rec.provenance}'."
                    )
                elif prev.validation_status != rec.validation_status or prev.numerical_metric != rec.numerical_metric:
                    refusal_reasons.append(
                        f"Duplicate record ID '{rec.id}' with conflicting status or numerical metric."
                    )
            seen_records[rec.id] = rec

        # 1. Audit every individual record
        for rec in self.evidence_records:
            cat_key = rec.category.strip().lower()
            if cat_key not in reports_by_category:
                reports_by_category[cat_key] = []

            # Check status
            if rec.validation_status in (ValidationStatus.REJECTED, ValidationStatus.EXPIRED):
                eligibility = EvidenceEligibility.REJECTED
                reason = f"Record '{rec.id}' is discredited with status '{rec.validation_status.value}'."
                is_acceptable = False
            elif rec.validation_status in (ValidationStatus.UNASSESSED, ValidationStatus.UNVALIDATED):
                eligibility = EvidenceEligibility.UNASSESSED
                reason = f"Record '{rec.id}' has unassessed status '{rec.validation_status.value}'."
                is_acceptable = False
            elif target_model and rec.model_reference.strip().lower() != target_model.strip().lower():
                eligibility = EvidenceEligibility.INCOMPATIBLE_MODEL
                reason = f"Record model '{rec.model_reference}' does not match contract target model '{target_model}'."
                is_acceptable = False
            elif target_domain and rec.applicable_domain.strip().lower() != target_domain.strip().lower():
                eligibility = EvidenceEligibility.INCOMPATIBLE_DOMAIN
                reason = f"Record domain '{rec.applicable_domain}' does not match contract envelope '{target_domain}'."
                is_acceptable = False
            elif not rec.provenance or not rec.provenance.strip():
                eligibility = EvidenceEligibility.INSUFFICIENT_PROVENANCE
                reason = f"Record '{rec.id}' lacks explicit provenance or authorship."
                is_acceptable = False
            elif rec.numerical_metric is not None and (not math.isfinite(rec.numerical_metric) or rec.numerical_metric < 0.0):
                eligibility = EvidenceEligibility.INSUFFICIENT_METRIC
                reason = f"Record '{rec.id}' contains invalid non-finite or negative numerical metric: {rec.numerical_metric}."
                is_acceptable = False
            elif required_status.lower() in ("validated", "independently_validated") and rec.validation_status.value.lower() not in ("validated", "independently_validated"):
                eligibility = EvidenceEligibility.UNASSESSED
                reason = f"Record status '{rec.validation_status.value}' does not satisfy contract requirement '{required_status}'."
                is_acceptable = False
            else:
                eligibility = EvidenceEligibility.ACCEPTED
                reason = "Record satisfies all integrity, model, domain, and validation preconditions."
                is_acceptable = True

            reports_by_category[cat_key].append(
                RecordEvaluationReport(
                    record_id=rec.id,
                    category=rec.category,
                    eligibility=eligibility,
                    is_acceptable=is_acceptable,
                    reason=reason,
                    validation_status=rec.validation_status,
                    model_reference=rec.model_reference,
                    applicable_domain=rec.applicable_domain,
                )
            )

        # 2. Check each required category
        for req_cat in required_categories:
            key = req_cat.strip().lower()
            cat_reports = reports_by_category.get(key, [])

            if not cat_reports:
                refusal_reasons.append(f"Missing required evidence categories: '{req_cat}' (no records provided).")
                continue

            # Check if any record in this category was rejected
            rejected_records = [r for r in cat_reports if r.eligibility == EvidenceEligibility.REJECTED]
            if rejected_records:
                rej_ids = [r.record_id for r in rejected_records]
                refusal_reasons.append(
                    f"Required category '{req_cat}' contains explicitly rejected/discredited evidence: {rej_ids}."
                )
                continue

            # Check if at least one record was accepted
            accepted_records = [r for r in cat_reports if r.is_acceptable]
            if not accepted_records:
                detailed_reasons = [f"{r.record_id}: {r.reason}" for r in cat_reports]
                refusal_reasons.append(
                    f"Required category '{req_cat}' has no acceptable evidence records: {'; '.join(detailed_reasons)}."
                )

        all_satisfied = len(refusal_reasons) == 0
        return all_satisfied, reports_by_category, refusal_reasons
