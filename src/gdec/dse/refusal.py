"""
Deterministic, versioned Refusal Engine for GDEC WP3.

Evaluates 12 explicit, versioned refusal rules against an engineering
execution/evidence context and returns a first-class structured RefusalResult.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from gdec.dse.evidence_graph import EstimatorClassification, RefusalRuleEvaluation


@dataclass(frozen=True)
class RefusalContext:
    """Normalized deterministic inputs for refusal-rule evaluation."""
    budget_exhausted: bool = False
    target_tolerance_met: bool = True
    estimator_identity: str = "Unknown"
    estimator_classification: str = EstimatorClassification.HEURISTIC.value
    problem_class: str = "linear_elasticity_2d"
    reference_required: bool = False
    reference_adequate: Optional[bool] = None
    qoi_boundary: str = "right"
    fixed_boundaries: List[str] = field(default_factory=list)
    supported_boundaries: List[str] = field(default_factory=lambda: ["left", "right", "top", "bottom"])
    dof_count: int = 0
    min_required_dofs: int = 6
    solver_converged: bool = True
    qoi_value: Optional[float] = 0.0
    residual_norm: Optional[float] = 0.0
    error_estimate: Optional[float] = 0.0
    mesh_valid: bool = True
    mesh_element_count: int = 1
    model_applicability_status: str = "established"
    parent_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    canonical_eir_hash: str = ""
    mesh_hash: str = ""
    mandatory_evidence_present: bool = True
    missing_evidence_fields: List[str] = field(default_factory=list)
    evidence_stale: bool = False
    evidence_invalidated: bool = False


@dataclass(frozen=True)
class RefusalRule:
    """Definition of a single deterministic versioned refusal rule."""
    rule_id: str
    version: str
    description: str
    preconditions: str
    evaluator: Callable[[RefusalContext], RefusalRuleEvaluation]


@dataclass(frozen=True)
class RefusalResult:
    """First-class structured refusal output."""
    refused: bool
    evaluations: List[RefusalRuleEvaluation]
    triggered_rule_ids: List[str]
    reasons: List[str]


def _eval_ref_001(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = bool(ctx.budget_exhausted and not ctx.target_tolerance_met)
    return RefusalRuleEvaluation(
        rule_id="REF-001",
        version="1.0.0",
        triggered=triggered,
        reason="Computation budget exhausted before required QoI tolerance was met." if triggered else "",
        diagnostic_context={"budget_exhausted": ctx.budget_exhausted, "target_tolerance_met": ctx.target_tolerance_met},
    )


def _eval_ref_002(ctx: RefusalContext) -> RefusalRuleEvaluation:
    valid_classes = {"linear_elasticity_2d"}
    est_id_lower = ctx.estimator_identity.lower()
    is_dwr_mislabelled = (
        "dwr" in est_id_lower
        and ctx.estimator_classification == EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value
    )
    invalid_class = ctx.problem_class not in valid_classes
    triggered = is_dwr_mislabelled or invalid_class
    reason = ""
    if is_dwr_mislabelled:
        reason = "DWR indicator must not be classified as a mathematically_established_bound."
    elif invalid_class:
        reason = f"Estimator '{ctx.estimator_identity}' is not valid for problem class '{ctx.problem_class}'."
    return RefusalRuleEvaluation(
        rule_id="REF-002",
        version="1.0.0",
        triggered=triggered,
        reason=reason,
        diagnostic_context={
            "estimator_identity": ctx.estimator_identity,
            "estimator_classification": ctx.estimator_classification,
            "problem_class": ctx.problem_class,
        },
    )


def _eval_ref_003(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = bool(ctx.reference_required and ctx.reference_adequate is not True)
    return RefusalRuleEvaluation(
        rule_id="REF-003",
        version="1.0.0",
        triggered=triggered,
        reason="Reference adequacy is unknown or inadequate when required by contract." if triggered else "",
        diagnostic_context={"reference_required": ctx.reference_required, "reference_adequate": ctx.reference_adequate},
    )


def _eval_ref_004(ctx: RefusalContext) -> RefusalRuleEvaluation:
    qoi_bnd = ctx.qoi_boundary.lower().strip()
    supported = {b.lower().strip() for b in ctx.supported_boundaries}
    fixed = {b.lower().strip() for b in ctx.fixed_boundaries}
    unsupported = qoi_bnd not in supported
    constrained = qoi_bnd in fixed
    triggered = unsupported or constrained
    reason = ""
    if unsupported:
        reason = f"QoI evaluated on unsupported boundary '{ctx.qoi_boundary}'."
    elif constrained:
        reason = f"QoI evaluated on Dirichlet-constrained boundary '{ctx.qoi_boundary}'."
    return RefusalRuleEvaluation(
        rule_id="REF-004",
        version="1.0.0",
        triggered=triggered,
        reason=reason,
        diagnostic_context={"qoi_boundary": ctx.qoi_boundary, "fixed_boundaries": ctx.fixed_boundaries},
    )


def _eval_ref_005(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = ctx.dof_count < ctx.min_required_dofs
    return RefusalRuleEvaluation(
        rule_id="REF-005",
        version="1.0.0",
        triggered=triggered,
        reason=f"Insufficient DOFs ({ctx.dof_count} < {ctx.min_required_dofs}) for estimator validity regime." if triggered else "",
        diagnostic_context={"dof_count": ctx.dof_count, "min_required_dofs": ctx.min_required_dofs},
    )


def _eval_ref_006(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = not ctx.solver_converged
    return RefusalRuleEvaluation(
        rule_id="REF-006",
        version="1.0.0",
        triggered=triggered,
        reason="Solver failed to converge or experienced numerical breakdown." if triggered else "",
        diagnostic_context={"solver_converged": ctx.solver_converged},
    )


def _eval_ref_007(ctx: RefusalContext) -> RefusalRuleEvaluation:
    nonfinite = []
    for name, val in [("qoi_value", ctx.qoi_value), ("residual_norm", ctx.residual_norm), ("error_estimate", ctx.error_estimate)]:
        if val is not None and not math.isfinite(val):
            nonfinite.append(name)
    triggered = len(nonfinite) > 0
    return RefusalRuleEvaluation(
        rule_id="REF-007",
        version="1.0.0",
        triggered=triggered,
        reason=f"Non-finite values detected in: {', '.join(nonfinite)}." if triggered else "",
        diagnostic_context={"nonfinite_fields": nonfinite},
    )


def _eval_ref_008(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = (not ctx.mesh_valid) or (ctx.mesh_element_count <= 0)
    return RefusalRuleEvaluation(
        rule_id="REF-008",
        version="1.0.0",
        triggered=triggered,
        reason="Invalid or unsupported mesh conditions (degenerate or zero elements)." if triggered else "",
        diagnostic_context={"mesh_valid": ctx.mesh_valid, "mesh_element_count": ctx.mesh_element_count},
    )


def _eval_ref_009(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = ctx.model_applicability_status != "established"
    return RefusalRuleEvaluation(
        rule_id="REF-009",
        version="1.0.0",
        triggered=triggered,
        reason=f"Model applicability is '{ctx.model_applicability_status}' (must be 'established')." if triggered else "",
        diagnostic_context={"model_applicability_status": ctx.model_applicability_status},
    )


def _is_hex64(val: Any) -> bool:
    s = str(val)
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def _eval_ref_010(ctx: RefusalContext) -> RefusalRuleEvaluation:
    missing_hashes = not (_is_hex64(ctx.canonical_eir_hash) and _is_hex64(ctx.mesh_hash))
    empty_parents = len(ctx.parent_artifacts) == 0
    bad_parent = any(
        not p.get("artifact_id") or not _is_hex64(p.get("sha256_hash", ""))
        for p in ctx.parent_artifacts
    )
    triggered = missing_hashes or empty_parents or bad_parent
    return RefusalRuleEvaluation(
        rule_id="REF-010",
        version="1.0.0",
        triggered=triggered,
        reason="Missing or inconsistent canonical provenance or parent artifact hashes." if triggered else "",
        diagnostic_context={
            "eir_hash_len": len(ctx.canonical_eir_hash),
            "mesh_hash_len": len(ctx.mesh_hash),
            "parent_count": len(ctx.parent_artifacts),
        },
    )


def _eval_ref_011(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = (not ctx.mandatory_evidence_present) or (len(ctx.missing_evidence_fields) > 0) or (ctx.qoi_value is None)
    return RefusalRuleEvaluation(
        rule_id="REF-011",
        version="1.0.0",
        triggered=triggered,
        reason="Mandatory evidence or QoI output is missing." if triggered else "",
        diagnostic_context={
            "mandatory_evidence_present": ctx.mandatory_evidence_present,
            "missing_evidence_fields": ctx.missing_evidence_fields,
            "qoi_present": ctx.qoi_value is not None,
        },
    )


def _eval_ref_012(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = bool(ctx.evidence_stale or ctx.evidence_invalidated)
    return RefusalRuleEvaluation(
        rule_id="REF-012",
        version="1.0.0",
        triggered=triggered,
        reason="Evidence is stale or has been invalidated." if triggered else "",
        diagnostic_context={"evidence_stale": ctx.evidence_stale, "evidence_invalidated": ctx.evidence_invalidated},
    )


REFUSAL_RULES: List[RefusalRule] = [
    RefusalRule("REF-001", "1.0.0", "Budget exhausted before QoI tolerance met", "budget_exhausted and not target_tolerance_met", _eval_ref_001),
    RefusalRule("REF-002", "1.0.0", "Estimator invalid or misclassified for problem class", "invalid problem_class or DWR labelled as certified bound", _eval_ref_002),
    RefusalRule("REF-003", "1.0.0", "Reference adequacy unknown when required", "reference_required and reference_adequate is not True", _eval_ref_003),
    RefusalRule("REF-004", "1.0.0", "QoI evaluated on unsupported or constrained boundary", "qoi_boundary unsupported or Dirichlet-constrained", _eval_ref_004),
    RefusalRule("REF-005", "1.0.0", "Insufficient DOFs for estimator validity regime", "dof_count < min_required_dofs", _eval_ref_005),
    RefusalRule("REF-006", "1.0.0", "Solver non-convergence or numerical breakdown", "not solver_converged", _eval_ref_006),
    RefusalRule("REF-007", "1.0.0", "Non-finite QoI, residual, or error estimate", "NaN or inf in qoi_value, residual_norm, or error_estimate", _eval_ref_007),
    RefusalRule("REF-008", "1.0.0", "Invalid or unsupported mesh conditions", "not mesh_valid or mesh_element_count <= 0", _eval_ref_008),
    RefusalRule("REF-009", "1.0.0", "Model applicability not established", "model_applicability_status != 'established'", _eval_ref_009),
    RefusalRule("REF-010", "1.0.0", "Missing or inconsistent provenance", "invalid EIR/mesh/parent artifact SHA-256 provenance", _eval_ref_010),
    RefusalRule("REF-011", "1.0.0", "Missing mandatory evidence", "mandatory_evidence_present is False or qoi_value is None", _eval_ref_011),
    RefusalRule("REF-012", "1.0.0", "Stale or invalidated evidence", "evidence_stale or evidence_invalidated", _eval_ref_012),
]


class RefusalEngine:
    """Deterministic refusal-rule evaluator."""

    def __init__(self, rules: Optional[List[RefusalRule]] = None) -> None:
        self.rules = rules if rules is not None else list(REFUSAL_RULES)

    def evaluate(self, context: RefusalContext) -> RefusalResult:
        evaluations = [rule.evaluator(context) for rule in self.rules]
        triggered = [ev for ev in evaluations if ev.triggered]
        return RefusalResult(
            refused=len(triggered) > 0,
            evaluations=evaluations,
            triggered_rule_ids=[ev.rule_id for ev in triggered],
            reasons=[ev.reason for ev in triggered if ev.reason],
        )
