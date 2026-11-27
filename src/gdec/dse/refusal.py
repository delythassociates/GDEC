"""
Deterministic, versioned Refusal Engine for GDEC WP3.

Evaluates 12 explicit, versioned refusal rules against an engineering
execution/evidence context and returns a first-class structured RefusalResult.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from gdec.dse.evidence_graph import (
    SUPPORTED_CERT_CHECKERS,
    EstimatorClassification,
    RefusalRuleEvaluation,
)


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
    effectivity_evidence_present: bool = False
    bound_certificate_verified: bool = False
    bound_checker_identity: str = ""
    qoi_boundary: str = "right"
    fixed_boundaries: List[str] = field(default_factory=list)
    supported_boundaries: List[str] = field(default_factory=lambda: ["left", "right", "top", "bottom"])
    dof_count: int = 0
    free_dof_count: int = 0
    interior_node_count: int = 0
    interior_facet_count: int = 0
    min_required_dofs: int = 8
    solver_converged: bool = True
    adjoint_converged: bool = True
    qoi_value: Optional[float] = 0.0
    residual_norm: Optional[float] = 0.0
    adjoint_residual_norm: Optional[float] = 0.0
    residual_tol: float = 1e-8
    error_estimate: Optional[float] = 0.0
    nonfinite_detected: bool = False
    mesh_valid: bool = True
    mesh_element_count: int = 1
    model_applicability_status: str = "established"
    parent_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    problem_ir_hash: str = ""
    canonical_eir_hash: str = ""
    execution_plan_hash: str = ""
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


def _is_hex64(val: Any) -> bool:
    if not isinstance(val, str):
        return False
    return len(val) == 64 and all(c in "0123456789abcdef" for c in val.lower()) and val != ("0" * 64)


def _safe_finite(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(float(val))
    except (OverflowError, TypeError, ValueError):
        return False


def structural_min_dofs_for_estimator(estimator_identity: str, estimator_classification: str) -> Dict[str, int]:
    """
    Documented structural mesh preconditions (NOT a proof of asymptotic convergence).
    - 6 total DOFs = 1 P1 triangle (degenerate: 0 interior facets, 0 interior nodes).
    - Minimum structured 2x2 tensor mesh = 4 nodes = 8 total DOFs, >=2 elements.
    - Patch recovery / residual energy require >=1 interior facet and >=4 free DOFs.
    - DWR asymptotic indicator requires >=1 interior node, >=4 interior facets, >=18 free DOFs (3x3 nodal patch).
    """
    est_lower = str(estimator_identity).lower()
    cls_val = str(estimator_classification)
    if cls_val == EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE.value or "dwr" in est_lower:
        return {"min_total_dofs": 18, "min_free_dofs": 12, "min_elements": 8, "min_interior_facets": 4, "min_interior_nodes": 1}
    if "zz" in est_lower or "recovery" in est_lower or "residual" in est_lower:
        return {"min_total_dofs": 8, "min_free_dofs": 4, "min_elements": 2, "min_interior_facets": 1, "min_interior_nodes": 0}
    return {"min_total_dofs": 8, "min_free_dofs": 2, "min_elements": 2, "min_interior_facets": 0, "min_interior_nodes": 0}


def _eval_ref_001(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = bool(ctx.budget_exhausted and not ctx.target_tolerance_met)
    return RefusalRuleEvaluation(
        rule_id="REF-001",
        version="1.0.0",
        triggered=triggered,
        reason="Computation budget exhausted before required QoI tolerance was met." if triggered else "",
        diagnostic_context={"budget_exhausted": bool(ctx.budget_exhausted), "target_tolerance_met": bool(ctx.target_tolerance_met)},
    )


def _eval_ref_002(ctx: RefusalContext) -> RefusalRuleEvaluation:
    valid_classes = {"linear_elasticity_2d"}
    est_id = str(ctx.estimator_identity)
    est_id_lower = est_id.lower()
    cls_val = str(ctx.estimator_classification)
    invalid_class = ctx.problem_class not in valid_classes
    unverified_bound = (
        cls_val == EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value
        and (
            "dwr" in est_id_lower
            or not ctx.bound_certificate_verified
            or ctx.bound_checker_identity not in SUPPORTED_CERT_CHECKERS
        )
    )
    missing_ref_evidence = (
        cls_val == EstimatorClassification.REFERENCE_BASED_ESTIMATE.value
        and not ctx.effectivity_evidence_present
    )
    triggered = invalid_class or unverified_bound or missing_ref_evidence
    reason = ""
    if unverified_bound:
        reason = (
            f"Estimator '{est_id}' cannot claim 'mathematically_established_bound' without a "
            "verified certificate from a registered independent checker."
        )
    elif missing_ref_evidence:
        reason = f"Estimator '{est_id}' claims 'reference_based_estimate' without reference effectivity evidence."
    elif invalid_class:
        reason = f"Estimator '{est_id}' is not valid for problem class '{ctx.problem_class}'."
    return RefusalRuleEvaluation(
        rule_id="REF-002",
        version="1.1.0",
        triggered=triggered,
        reason=reason,
        diagnostic_context={
            "estimator_identity": est_id,
            "estimator_classification": cls_val,
            "problem_class": str(ctx.problem_class),
            "bound_certificate_verified": bool(ctx.bound_certificate_verified),
        },
    )


def _eval_ref_003(ctx: RefusalContext) -> RefusalRuleEvaluation:
    ref_needed = bool(ctx.reference_required or ctx.estimator_classification == EstimatorClassification.REFERENCE_BASED_ESTIMATE.value)
    triggered = bool(ref_needed and ctx.reference_adequate is not True)
    return RefusalRuleEvaluation(
        rule_id="REF-003",
        version="1.1.0",
        triggered=triggered,
        reason="Reference adequacy is unknown or inadequate when required." if triggered else "",
        diagnostic_context={"reference_required": ref_needed, "reference_adequate": ctx.reference_adequate},
    )


def _eval_ref_004(ctx: RefusalContext) -> RefusalRuleEvaluation:
    qoi_bnd = str(ctx.qoi_boundary).lower().strip() if isinstance(ctx.qoi_boundary, str) else ""
    supported = {str(b).lower().strip() for b in (ctx.supported_boundaries or []) if isinstance(b, str)}
    fixed_list = [str(b).lower().strip() for b in (ctx.fixed_boundaries or []) if isinstance(b, str)]
    fixed = set(fixed_list)
    unsupported = (not qoi_bnd) or (qoi_bnd not in supported)
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
        diagnostic_context={"qoi_boundary": str(ctx.qoi_boundary), "fixed_boundaries": fixed_list},
    )


def _eval_ref_005(ctx: RefusalContext) -> RefusalRuleEvaluation:
    reqs = structural_min_dofs_for_estimator(ctx.estimator_identity, ctx.estimator_classification)
    eff_min_total = max(reqs["min_total_dofs"], int(ctx.min_required_dofs) if isinstance(ctx.min_required_dofs, int) else reqs["min_total_dofs"])
    failures: List[str] = []
    if not isinstance(ctx.dof_count, int) or ctx.dof_count < eff_min_total:
        failures.append(f"total DOFs {ctx.dof_count} < {eff_min_total}")
    if not isinstance(ctx.free_dof_count, int) or ctx.free_dof_count < reqs["min_free_dofs"]:
        failures.append(f"free DOFs {ctx.free_dof_count} < {reqs['min_free_dofs']}")
    if not isinstance(ctx.mesh_element_count, int) or ctx.mesh_element_count < reqs["min_elements"]:
        failures.append(f"elements {ctx.mesh_element_count} < {reqs['min_elements']}")
    if not isinstance(ctx.interior_facet_count, int) or ctx.interior_facet_count < reqs["min_interior_facets"]:
        failures.append(f"interior facets {ctx.interior_facet_count} < {reqs['min_interior_facets']}")
    if not isinstance(ctx.interior_node_count, int) or ctx.interior_node_count < reqs["min_interior_nodes"]:
        failures.append(f"interior nodes {ctx.interior_node_count} < {reqs['min_interior_nodes']}")
    triggered = len(failures) > 0
    return RefusalRuleEvaluation(
        rule_id="REF-005",
        version="1.1.0",
        triggered=triggered,
        reason=f"Structural mesh preconditions not met ({'; '.join(failures)})." if triggered else "",
        diagnostic_context={
            "dof_count": ctx.dof_count,
            "free_dof_count": ctx.free_dof_count,
            "interior_facet_count": ctx.interior_facet_count,
            "interior_node_count": ctx.interior_node_count,
            "required": reqs,
        },
    )


def _eval_ref_006(ctx: RefusalContext) -> RefusalRuleEvaluation:
    primal_bad = not bool(ctx.solver_converged)
    adjoint_bad = not bool(ctx.adjoint_converged)
    primal_res_bad = (
        isinstance(ctx.residual_norm, (int, float))
        and not isinstance(ctx.residual_norm, bool)
        and _safe_finite(ctx.residual_norm)
        and float(ctx.residual_norm) > float(ctx.residual_tol)
    )
    adjoint_res_bad = (
        isinstance(ctx.adjoint_residual_norm, (int, float))
        and not isinstance(ctx.adjoint_residual_norm, bool)
        and _safe_finite(ctx.adjoint_residual_norm)
        and float(ctx.adjoint_residual_norm) > float(ctx.residual_tol)
    )
    triggered = primal_bad or adjoint_bad or primal_res_bad or adjoint_res_bad
    return RefusalRuleEvaluation(
        rule_id="REF-006",
        version="1.1.0",
        triggered=triggered,
        reason="Solver failed to converge or residual exceeds tolerance." if triggered else "",
        diagnostic_context={
            "solver_converged": bool(ctx.solver_converged),
            "adjoint_converged": bool(ctx.adjoint_converged),
            "residual_norm": ctx.residual_norm if _safe_finite(ctx.residual_norm) else "NONFINITE",
            "adjoint_residual_norm": ctx.adjoint_residual_norm if _safe_finite(ctx.adjoint_residual_norm) else "NONFINITE",
        },
    )


def _eval_ref_007(ctx: RefusalContext) -> RefusalRuleEvaluation:
    nonfinite: List[str] = []
    if ctx.nonfinite_detected:
        nonfinite.append("runtime_solver_output")
    for name, val in [
        ("qoi_value", ctx.qoi_value),
        ("residual_norm", ctx.residual_norm),
        ("adjoint_residual_norm", ctx.adjoint_residual_norm),
        ("error_estimate", ctx.error_estimate),
    ]:
        if not _safe_finite(val):
            nonfinite.append(name)
    triggered = len(nonfinite) > 0
    return RefusalRuleEvaluation(
        rule_id="REF-007",
        version="1.1.0",
        triggered=triggered,
        reason=f"Non-finite values detected in: {', '.join(nonfinite)}." if triggered else "",
        diagnostic_context={"nonfinite_fields": nonfinite},
    )


def _eval_ref_008(ctx: RefusalContext) -> RefusalRuleEvaluation:
    elem_bad = not isinstance(ctx.mesh_element_count, int) or ctx.mesh_element_count <= 0
    triggered = (not bool(ctx.mesh_valid)) or elem_bad
    return RefusalRuleEvaluation(
        rule_id="REF-008",
        version="1.0.0",
        triggered=triggered,
        reason="Invalid or unsupported mesh conditions (degenerate or zero elements)." if triggered else "",
        diagnostic_context={"mesh_valid": bool(ctx.mesh_valid), "mesh_element_count": ctx.mesh_element_count},
    )


def _eval_ref_009(ctx: RefusalContext) -> RefusalRuleEvaluation:
    triggered = ctx.model_applicability_status != "established"
    return RefusalRuleEvaluation(
        rule_id="REF-009",
        version="1.0.0",
        triggered=triggered,
        reason=f"Model applicability is '{ctx.model_applicability_status}' (must be 'established')." if triggered else "",
        diagnostic_context={"model_applicability_status": str(ctx.model_applicability_status)},
    )


def _eval_ref_010(ctx: RefusalContext) -> RefusalRuleEvaluation:
    hashes_ok = (
        _is_hex64(ctx.problem_ir_hash)
        and _is_hex64(ctx.canonical_eir_hash)
        and _is_hex64(ctx.execution_plan_hash)
        and _is_hex64(ctx.mesh_hash)
    )
    parents = ctx.parent_artifacts if isinstance(ctx.parent_artifacts, list) else []
    empty_parents = len(parents) == 0
    bad_parent = any(
        not isinstance(p, dict)
        or not isinstance(p.get("artifact_id"), str)
        or not p.get("artifact_id", "").strip()
        or not _is_hex64(p.get("sha256_hash"))
        for p in parents
    )
    parent_hashes = {str(p.get("sha256_hash", "")).lower() for p in parents if isinstance(p, dict)}
    missing_links = (
        ctx.problem_ir_hash.lower() not in parent_hashes
        or ctx.mesh_hash.lower() not in parent_hashes
    ) if hashes_ok else True
    triggered = (not hashes_ok) or empty_parents or bad_parent or missing_links
    return RefusalRuleEvaluation(
        rule_id="REF-010",
        version="1.1.0",
        triggered=triggered,
        reason="Missing or inconsistent canonical provenance or parent artifact hashes." if triggered else "",
        diagnostic_context={
            "hashes_valid_hex64": hashes_ok,
            "parent_count": len(parents),
            "missing_parent_links": missing_links,
        },
    )


def _eval_ref_011(ctx: RefusalContext) -> RefusalRuleEvaluation:
    missing_list = ctx.missing_evidence_fields if isinstance(ctx.missing_evidence_fields, list) else ["invalid_missing_list"]
    triggered = (not bool(ctx.mandatory_evidence_present)) or (len(missing_list) > 0) or (ctx.qoi_value is None)
    return RefusalRuleEvaluation(
        rule_id="REF-011",
        version="1.0.0",
        triggered=triggered,
        reason="Mandatory evidence or QoI output is missing." if triggered else "",
        diagnostic_context={
            "mandatory_evidence_present": bool(ctx.mandatory_evidence_present),
            "missing_evidence_fields": missing_list,
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
        diagnostic_context={"evidence_stale": bool(ctx.evidence_stale), "evidence_invalidated": bool(ctx.evidence_invalidated)},
    )


REFUSAL_RULES: List[RefusalRule] = [
    RefusalRule("REF-001", "1.0.0", "Budget exhausted before QoI tolerance met", "budget_exhausted and not target_tolerance_met", _eval_ref_001),
    RefusalRule("REF-002", "1.1.0", "Estimator invalid or uncertified bound claimed", "invalid problem_class, unverified bound certificate, or missing reference evidence", _eval_ref_002),
    RefusalRule("REF-003", "1.1.0", "Reference adequacy unknown when required", "(reference_required or reference_based_estimate) and reference_adequate is not True", _eval_ref_003),
    RefusalRule("REF-004", "1.0.0", "QoI evaluated on unsupported or constrained boundary", "qoi_boundary unsupported or Dirichlet-constrained", _eval_ref_004),
    RefusalRule("REF-005", "1.1.0", "Structural mesh preconditions not met for estimator", "mesh below structural minimum DOFs/free-DOFs/elements/facets/interior nodes", _eval_ref_005),
    RefusalRule("REF-006", "1.1.0", "Solver non-convergence or residual exceeds tolerance", "primal or adjoint non-convergence or residual > tol", _eval_ref_006),
    RefusalRule("REF-007", "1.1.0", "Non-finite QoI, residual, or error estimate", "NaN or inf in qoi_value, residual_norm, adjoint_residual_norm, or error_estimate", _eval_ref_007),
    RefusalRule("REF-008", "1.0.0", "Invalid or unsupported mesh conditions", "not mesh_valid or mesh_element_count <= 0", _eval_ref_008),
    RefusalRule("REF-009", "1.0.0", "Model applicability not established", "model_applicability_status != 'established'", _eval_ref_009),
    RefusalRule("REF-010", "1.1.0", "Missing or inconsistent provenance", "invalid 64-hex hashes or missing parent links for ProblemIR and mesh", _eval_ref_010),
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
