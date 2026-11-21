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
    "RestrictedLinearElasticScaling",
    "ScalingAssumptions",
    "ReferenceBaseline",
]
