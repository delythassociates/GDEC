"""
Declarative Decision Contract specification and validation schema for GDEC.
Enforces strongly typed, machine-validatable engineering requirements.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from gdec.dse.exceptions import ContractValidationError, ContractSerializationError


class DecisionIdentity(BaseModel):
    """Identification and governance metadata for an engineering decision."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique contract identifier, e.g. 'DEC-BRACKET-001'")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    title: str = Field(..., min_length=1, description="Short human-readable title of the decision")
    question: str = Field(..., min_length=1, description="Explicit engineering question being answered")
    description: Optional[str] = Field(default=None, description="Detailed context or engineering background")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != "1.0.0":
            raise ValueError(f"Unsupported schema version: '{v}'. Only '1.0.0' is supported in Phase 5.1.")
        return v


class QuantityOfInterest(BaseModel):
    """Definition of the physical Quantity of Interest (QoI) under evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    qoi_id: str = Field(..., min_length=1, description="Identifier for the QoI, e.g. 'tip_deflection'")
    name: str = Field(..., min_length=1, description="Physical name, e.g. 'Max Vertical Tip Displacement'")
    unit: str = Field(..., min_length=1, description="Physical unit, e.g. 'mm', 'MPa'")
    expected_sign: Literal["positive", "negative", "any"] = Field(
        default="any", description="Expected physical sign of the QoI"
    )
    model_reference: Optional[str] = Field(default=None, description="Governing boundary-value problem")


class AcceptanceCriterion(BaseModel):
    """Formal mathematical threshold and comparison operator for decision acceptance."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: Literal["<=", "<", ">=", ">"] = Field(
        ..., description="Comparison operator relating the QoI to the limit (e.g. QoI <= limit)"
    )
    limit: float = Field(..., description="Engineering performance threshold value")
    unit: str = Field(..., min_length=1, description="Physical unit of the threshold")
    safety_margin: float = Field(default=0.0, ge=0.0, description="Mandatory safety buffer")


class PredictiveDistribution(BaseModel):
    """Predictive uncertainty distribution for the Quantity of Interest."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: Literal["normal"] = Field(
        default="normal", description="Distribution family (only 'normal' supported in Phase 5.1)"
    )
    mean: float = Field(..., description="Expected value / mean prediction")
    std: float = Field(..., ge=0.0, description="Standard deviation of the prediction (must be non-negative)")
    unit: str = Field(..., min_length=1, description="Physical unit of distribution parameters")
    provenance: str = Field(..., min_length=1, description="Source of the predictive distribution")


class DecisionLoss(BaseModel):
    """Asymmetric economic or safety consequences associated with incorrect decisions."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_false_acceptance: float = Field(
        ..., gt=0.0, description="Cost of falsely releasing an unsafe design (C_FA > 0)"
    )
    cost_false_rejection: float = Field(
        ..., gt=0.0, description="Cost of falsely rejecting a safe design (C_FR > 0)"
    )
    cost_unit: str = Field(default="USD", min_length=1, description="Currency or dimensionless cost unit")


class EvidenceRequirements(BaseModel):
    """Documented evidence and validity preconditions required to certify a decision."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    required_categories: List[str] = Field(
        default_factory=lambda: ["discretization_error", "boundary_conditions"],
        description="Mandatory evidence categories"
    )
    model_assumptions: List[str] = Field(
        ..., min_length=1, description="Physical and numerical assumptions that must hold"
    )
    applicable_domain: str = Field(..., min_length=1, description="Stated operating envelope")
    numerical_quality_threshold: float = Field(
        default=0.05, gt=0.0, description="Maximum allowable relative discretization error indicator"
    )
    validation_status: str = Field(default="unvalidated", description="Physical test validation status")
    known_limitations: List[str] = Field(default_factory=list, description="Explicit known edge cases")


class ComputationalBudget(BaseModel):
    """Budgetary constraints on mesh refinement, runtime, and evaluations."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_evaluations: Optional[int] = Field(default=None, gt=0, description="Maximum solver/AMR evaluations")
    max_wall_clock_seconds: Optional[float] = Field(default=None, gt=0.0, description="Wall-clock timeout")
    enforced: bool = Field(default=False, description="Whether limits are strictly enforced or descriptive")


class DecisionContract(BaseModel):
    """
    Root Decision Contract model for GDEC.
    Unifies decision identity, QoI definitions, acceptance criteria,
    predictive distributions, asymmetric loss, and evidence requirements.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: DecisionIdentity
    qoi: QuantityOfInterest
    criterion: AcceptanceCriterion
    predictive_distribution: Optional[PredictiveDistribution] = None
    loss: DecisionLoss
    evidence: EvidenceRequirements
    budget: ComputationalBudget = Field(default_factory=lambda: ComputationalBudget())

    @model_validator(mode="after")
    def validate_unit_consistency(self) -> DecisionContract:
        """Enforce strict unit consistency across QoI, criterion, and distribution."""
        qoi_unit = self.qoi.unit.strip().lower()
        crit_unit = self.criterion.unit.strip().lower()

        if qoi_unit != crit_unit:
            raise ValueError(
                f"Unit mismatch: QoI unit is '{self.qoi.unit}', but criterion unit is '{self.criterion.unit}'"
            )

        if self.predictive_distribution is not None:
            dist_unit = self.predictive_distribution.unit.strip().lower()
            if dist_unit != qoi_unit:
                raise ValueError(
                    f"Unit mismatch: Predictive distribution unit '{self.predictive_distribution.unit}' "
                    f"does not match QoI unit '{self.qoi.unit}'"
                )

        return self

    def to_json(self, indent: int = 2) -> str:
        """Serialize contract to deterministic JSON string."""
        try:
            return json.dumps(self.model_dump(mode="json"), indent=indent, sort_keys=True)
        except Exception as e:
            raise ContractSerializationError(f"Failed to serialize DecisionContract: {str(e)}") from e

    @classmethod
    def from_json(cls, json_str: str) -> DecisionContract:
        """Parse and validate DecisionContract from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.model_validate(data)
        except json.JSONDecodeError as e:
            raise ContractValidationError(f"Invalid JSON format: {str(e)}") from e
        except Exception as e:
            raise ContractValidationError(f"Contract validation failed: {str(e)}") from e

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Export standardized JSON Schema."""
        return cls.model_json_schema()
