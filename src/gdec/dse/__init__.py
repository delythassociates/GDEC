"""
GDEC Decision Sufficiency Engine (DSE).
Connects goal-driven finite element error metrics to Bayesian expected loss minimization
and declarative engineering decision contracts.
"""

from __future__ import annotations

from gdec.dse.exceptions import (
    DSEError,
    ContractError,
    ContractValidationError,
    ContractSerializationError,
    DecisionRefusalError,
    ScalingAssumptionError,
)
from gdec.dse.contract import (
    DecisionContract,
    DecisionIdentity,
    QuantityOfInterest,
    AcceptanceCriterion,
    PredictiveDistribution,
    DecisionLoss,
    EvidenceRequirements,
    ComputationalBudget,
)
from gdec.dse.evaluator import (
    SingleQoIEvaluator,
    DecisionRecommendation,
    DecisionEvaluationResult,
)
from gdec.dse.evidence import (
    ValidationStatus,
    EvidenceRecord,
    EvidenceAssessment,
    EvidenceEligibility,
    RecordEvaluationReport,
)
from gdec.dse.evidence_graph import (
    EVIDENCE_SCHEMA_VERSION,
    EstimatorClassification,
    QualificationStatus,
    QoIEpistemicRole,
    ParentArtifactRef,
    ReferenceEffectivityEvidence,
    BoundCertificateEvidence,
    CompactProblemFeatureVector,
    OutcomeMetrics,
    RefusalRuleEvaluation,
    EngineeringEvidenceRecord,
    canonical_json_dumps,
    compute_canonical_hash,
    build_evidence_record_with_hash,
)
from gdec.dse.refusal import (
    RefusalContext,
    RefusalRule,
    RefusalResult,
    RefusalEngine,
    REFUSAL_RULES,
)
from gdec.dse.verifier import (
    VerificationDiagnostic,
    VerificationReport,
    verify_evidence_payload,
    verify_evidence_file,
)
from gdec.dse.scaling import (
    RestrictedLinearElasticScaling,
    ScalingAssumptions,
    ReferenceBaseline,
)

__all__ = [
    "DSEError",
    "ContractError",
    "ContractValidationError",
    "ContractSerializationError",
    "DecisionRefusalError",
    "ScalingAssumptionError",
    "DecisionContract",
    "DecisionIdentity",
    "QuantityOfInterest",
    "AcceptanceCriterion",
    "PredictiveDistribution",
    "DecisionLoss",
    "EvidenceRequirements",
    "ComputationalBudget",
    "SingleQoIEvaluator",
    "DecisionRecommendation",
    "DecisionEvaluationResult",
    "ValidationStatus",
    "EvidenceRecord",
    "EvidenceAssessment",
    "EvidenceEligibility",
    "RecordEvaluationReport",
    "RestrictedLinearElasticScaling",
    "ScalingAssumptions",
    "ReferenceBaseline",
]
