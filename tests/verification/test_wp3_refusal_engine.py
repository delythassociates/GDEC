"""
Positive and negative tests for all 12 deterministic refusal rules (REF-001..REF-012)
and GDECRuntime refusal integration (WP3 Stage 2 & Stage 5).
"""
from __future__ import annotations

import math
import pytest

from gdec.compiler import GDECCompiler
from gdec.core import ExecutionPlanner, GDECRuntime
from gdec.dse.evidence_graph import EstimatorClassification
from gdec.dse.refusal import RefusalContext, RefusalEngine


def _valid_context() -> RefusalContext:
    h = "a" * 64
    return RefusalContext(
        budget_exhausted=False,
        target_tolerance_met=True,
        estimator_identity="DWREstimator",
        estimator_classification=EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE.value,
        problem_class="linear_elasticity_2d",
        reference_required=True,
        reference_adequate=True,
        qoi_boundary="right",
        fixed_boundaries=["left"],
        dof_count=100,
        min_required_dofs=6,
        solver_converged=True,
        qoi_value=-1.9,
        residual_norm=1e-12,
        error_estimate=1e-4,
        mesh_valid=True,
        mesh_element_count=80,
        model_applicability_status="established",
        parent_artifacts=[{"artifact_id": "eir", "artifact_type": "canonical_eir", "sha256_hash": h}],
        canonical_eir_hash=h,
        mesh_hash=h,
        mandatory_evidence_present=True,
        missing_evidence_fields=[],
        evidence_stale=False,
        evidence_invalidated=False,
    )


def test_valid_context_triggers_zero_refusal_rules():
    res = RefusalEngine().evaluate(_valid_context())
    assert res.refused is False
    assert res.triggered_rule_ids == []
    assert res.reasons == []
    assert len(res.evaluations) == 12


@pytest.mark.parametrize(
    "rule_id,overrides",
    [
        ("REF-001", {"budget_exhausted": True, "target_tolerance_met": False}),
        ("REF-002", {"estimator_identity": "DWREstimator", "estimator_classification": EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value}),
        ("REF-003", {"reference_required": True, "reference_adequate": False}),
        ("REF-004", {"qoi_boundary": "left", "fixed_boundaries": ["left"]}),
        ("REF-005", {"dof_count": 4, "min_required_dofs": 6}),
        ("REF-006", {"solver_converged": False}),
        ("REF-007", {"qoi_value": float("nan")}),
        ("REF-008", {"mesh_valid": False, "mesh_element_count": 0}),
        ("REF-009", {"model_applicability_status": "unestablished"}),
        ("REF-010", {"canonical_eir_hash": "short"}),
        ("REF-011", {"mandatory_evidence_present": False}),
        ("REF-012", {"evidence_stale": True}),
    ],
)
def test_each_refusal_rule_positive_and_negative(rule_id: str, overrides: dict):
    engine = RefusalEngine()
    # Negative (rule does not trigger on clean context)
    clean_res = engine.evaluate(_valid_context())
    assert rule_id not in clean_res.triggered_rule_ids

    # Positive (rule triggers on violated context)
    bad_ctx = RefusalContext(**{**_valid_context().__dict__, **overrides})
    bad_res = engine.evaluate(bad_ctx)
    assert bad_res.refused is True
    assert rule_id in bad_res.triggered_rule_ids
    matching = [ev for ev in bad_res.evaluations if ev.rule_id == rule_id]
    assert len(matching) == 1
    assert matching[0].triggered is True
    assert matching[0].version == "1.0.0"
    assert len(matching[0].reason) > 0


def test_ref_007_rejects_infinity():
    bad_ctx = RefusalContext(**{**_valid_context().__dict__, "error_estimate": math.inf})
    res = RefusalEngine().evaluate(bad_ctx)
    assert res.refused is True
    assert "REF-007" in res.triggered_rule_ids


def test_runtime_budget_exhaustion_produces_refused_evidence_record():
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    res.ir.budget.value = 500
    plan = ExecutionPlanner().create_plan(res.ir, override_strategy="goal_aware")
    trace = GDECRuntime(plan, res.ir).execute()
    assert trace.evidence_record is not None
    assert trace.refusal_result is not None
    assert trace.refusal_result.refused is True
    assert "REF-001" in trace.refusal_result.triggered_rule_ids
    assert trace.evidence_record.refused is True
