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
        min_required_dofs=18,
        free_dof_count=90,
        interior_facet_count=40,
        interior_node_count=15,
        solver_converged=True,
        adjoint_converged=True,
        qoi_value=-1.9,
        residual_norm=1e-12,
        adjoint_residual_norm=1e-12,
        error_estimate=1e-4,
        mesh_valid=True,
        mesh_element_count=80,
        model_applicability_status="established",
        parent_artifacts=[
            {"artifact_id": "eir", "artifact_type": "canonical_eir", "sha256_hash": h},
            {"artifact_id": "ir", "artifact_type": "problem_ir", "sha256_hash": h},
            {"artifact_id": "plan", "artifact_type": "execution_plan", "sha256_hash": h},
        ],
        canonical_eir_hash=h,
        problem_ir_hash=h,
        execution_plan_hash=h,
        mesh_hash=h,
        mandatory_evidence_present=True,
        missing_evidence_fields=[],
        evidence_stale=False,
        evidence_invalidated=False,
    )


_EXPECTED_RULE_VERSIONS = {
    "REF-001": "1.0.0",
    "REF-002": "1.1.0",
    "REF-003": "1.1.0",
    "REF-004": "1.0.0",
    "REF-005": "1.1.0",
    "REF-006": "1.1.0",
    "REF-007": "1.1.0",
    "REF-008": "1.0.0",
    "REF-009": "1.0.0",
    "REF-010": "1.1.0",
    "REF-011": "1.0.0",
    "REF-012": "1.0.0",
}


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
        ("REF-005", {"dof_count": 4, "min_required_dofs": 18}),
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
    assert matching[0].version == _EXPECTED_RULE_VERSIONS[rule_id]
    assert len(matching[0].reason) > 0


def test_ref_007_rejects_infinity():
    bad_ctx = RefusalContext(**{**_valid_context().__dict__, "error_estimate": math.inf})
    res = RefusalEngine().evaluate(bad_ctx)
    assert res.refused is True
    assert "REF-007" in res.triggered_rule_ids


def test_ref_005_structural_floor_boundaries():
    engine = RefusalEngine()
    # Below DWR structural floor (17 < 18) -> refused
    low_dofs = RefusalContext(**{**_valid_context().__dict__, "dof_count": 17, "min_required_dofs": 18})
    assert "REF-005" in engine.evaluate(low_dofs).triggered_rule_ids

    # Zero free DOFs -> refused
    no_free = RefusalContext(**{**_valid_context().__dict__, "free_dof_count": 0})
    assert "REF-005" in engine.evaluate(no_free).triggered_rule_ids

    # Insufficient interior facets (3 < 4) or interior nodes (0 < 1) -> refused
    low_facets = RefusalContext(**{**_valid_context().__dict__, "interior_facet_count": 3})
    assert "REF-005" in engine.evaluate(low_facets).triggered_rule_ids
    no_int_nodes = RefusalContext(**{**_valid_context().__dict__, "interior_node_count": 0})
    assert "REF-005" in engine.evaluate(no_int_nodes).triggered_rule_ids

    # At exact DWR structural floor (18 >= 18, free=12, facets=4, int_nodes=1) -> allowed
    at_floor = RefusalContext(
        **{
            **_valid_context().__dict__,
            "dof_count": 18,
            "min_required_dofs": 18,
            "free_dof_count": 12,
            "interior_facet_count": 4,
            "interior_node_count": 1,
        }
    )
    assert "REF-005" not in engine.evaluate(at_floor).triggered_rule_ids


def test_ref_002_rejects_unverified_bound_for_non_dwr_and_ref_006_adjoint():
    engine = RefusalEngine()
    non_dwr_bound = RefusalContext(
        **{
            **_valid_context().__dict__,
            "estimator_identity": "CustomEstimator",
            "estimator_classification": EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value,
            "bound_certificate_verified": False,
        }
    )
    assert "REF-002" in engine.evaluate(non_dwr_bound).triggered_rule_ids

    bad_adjoint = RefusalContext(**{**_valid_context().__dict__, "adjoint_converged": False})
    assert "REF-006" in engine.evaluate(bad_adjoint).triggered_rule_ids


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
