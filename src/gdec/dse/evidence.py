"""
Evidence assessment and provenance models for GDEC Decision Sufficiency Engine.
Provides strongly typed evidence records, verification/validation status tracking,
and domain applicability auditing.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ValidationStatus(str, Enum):
    """
    Formal maturity and credibility status of an engineering simulation or model.
    Enforces precise scientific distinctions:
    - UNASSESSED: No formal verification or validation has been conducted.
    - VERIFIED: Code and solution verification confirmed (equations solved correctly).
    - VALIDATED: Model validated against physical experimental test data.
    - INDEPENDENTLY_VALIDATED: Validated by an independent third party or regulatory audit.
    - CALIBRATED: Material/constitutive parameters tuned against measured data.
    """
    UNASSESSED = "UNASSESSED"
    VERIFIED = "VERIFIED"
    VALIDATED = "VALIDATED"
    INDEPENDENTLY_VALIDATED = "INDEPENDENTLY_VALIDATED"
    CALIBRATED = "CALIBRATED"


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
    description: Optional[str] = Field(default=None, description="Detailed evidence notes")


class EvidenceAssessment(BaseModel):
    """
    Comprehensive evidence package submitted to evaluate a Decision Contract.
    Enforces that required evidence categories, model assumptions, and domain
    applicability are explicitly satisfied before any decision recommendation is rendered.
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
