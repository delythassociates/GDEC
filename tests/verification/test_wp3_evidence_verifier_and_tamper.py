"""
Adversarial tampering, round-trip CLI verification, and verifier/refusal
mutation tests for GDEC WP3 (Stage 5).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
import pytest

from gdec.cli import main as cli_main
from gdec.dse.evidence_graph import EstimatorClassification, compute_canonical_hash
from gdec.dse.refusal import REFUSAL_RULES, RefusalContext, RefusalEngine
from gdec.dse.verifier import verify_evidence_file, verify_evidence_payload


def _produce_valid_record_dict(tmp_path: Path, monkeypatch) -> dict:
    out_file = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys, "argv", ["gdec", "run", "examples/cantilever.gdc", "--strategy", "goal_aware", "-o", str(out_file)]
    )
    assert cli_main() == 0
    assert out_file.is_file()
    return json.loads(out_file.read_text(encoding="utf-8"))


def test_complete_round_trip_run_save_verify(tmp_path: Path, monkeypatch):
    out_file = tmp_path / "roundtrip.json"
    monkeypatch.setattr(
        sys, "argv", ["gdec", "run", "examples/cantilever.gdc", "--strategy", "goal_aware", "-o", str(out_file)]
    )
    assert cli_main() == 0

    monkeypatch.setattr(sys, "argv", ["gdec", "verify", str(out_file)])
    assert cli_main() == 0

    report = verify_evidence_file(out_file)
    assert report.valid is True
    assert report.diagnostic_codes == ["VER-OK"]
    assert report.refused is False


def test_tampering_individual_fields_triggers_hash_mismatch(tmp_path: Path, monkeypatch):
    base = _produce_valid_record_dict(tmp_path, monkeypatch)
    for field, new_val in [
        ("qoi_value", -999.0),
        ("dof_count", base["dof_count"] + 2),
        ("material_identity", "TamperedMaterial"),
        ("solver_identity", "TamperedSolver"),
        ("backend", "tampered_gpu"),
        ("numerical_precision", "float16"),
    ]:
        tampered = copy.deepcopy(base)
        tampered[field] = new_val
        report = verify_evidence_payload(tampered)
        assert report.valid is False
        assert "VER-HASH-MISMATCH" in report.diagnostic_codes


def test_recomputed_hash_over_inconsistent_metadata_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["outcome_metrics"]["final_dofs"] = tampered["dof_count"] + 10
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-METADATA-INCONSISTENT" in report.diagnostic_codes


def test_incorrect_dwr_estimator_classification_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["estimator_identity"] = "DWREstimator"
    tampered["estimator_classification"] = EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-ESTIMATOR-CLASS-INVALID" in report.diagnostic_codes


def test_wrong_units_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["qoi_units"] = "furlongs"
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-UNITS-INCONSISTENT" in report.diagnostic_codes


def test_missing_dependency_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    del tampered["dependency_versions"]["numpy"]
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-MISSING-DEPENDENCY" in report.diagnostic_codes


def test_stale_and_invalidated_evidence_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["evidence_stale"] = True
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-STALE-OR-INVALIDATED" in report.diagnostic_codes
    assert "VER-REFUSAL-MISMATCH" in report.diagnostic_codes


def test_forged_provenance_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["parent_artifacts"] = []
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-PROVENANCE-INVALID" in report.diagnostic_codes


def test_refusal_bypass_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["resource_consumption"]["budget_exhausted"] = True
    tampered["resource_consumption"]["target_tolerance_met"] = False
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-REFUSAL-MISMATCH" in report.diagnostic_codes


def test_unsupported_model_applicability_fails(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["model_applicability_status"] = "unestablished"
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-APPLICABILITY-UNESTABLISHED" in report.diagnostic_codes


def test_nan_and_inf_rejected(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["qoi_value"] = float("nan")
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-SCHEMA-INVALID" in report.diagnostic_codes


def test_optional_rerun_mode(tmp_path: Path, monkeypatch):
    base = _produce_valid_record_dict(tmp_path, monkeypatch)
    ok_rep = verify_evidence_payload(base, rerun=True, reexec_fn=lambda r: r.qoi_value)
    assert ok_rep.valid is True
    bad_rep = verify_evidence_payload(base, rerun=True, reexec_fn=lambda r: r.qoi_value + 1.0)
    assert bad_rep.valid is False
    assert "VER-RERUN-MISMATCH" in bad_rep.diagnostic_codes


def test_mutation_weakening_verifier_hash_or_bypassing_refusal_detected(tmp_path: Path, monkeypatch):
    # Mutant 1: Bypassing REF-001 allows budget_exhausted without refusal
    bypassed_rules = [r for r in REFUSAL_RULES if r.rule_id != "REF-001"]
    ctx = RefusalContext(
        budget_exhausted=True,
        target_tolerance_met=False,
        dof_count=100,
        canonical_eir_hash="a" * 64,
        mesh_hash="a" * 64,
        parent_artifacts=[{"artifact_id": "x", "artifact_type": "eir", "sha256_hash": "a" * 64}],
    )
    assert RefusalEngine().evaluate(ctx).refused is True
    assert RefusalEngine(rules=bypassed_rules).evaluate(ctx).refused is False

    # Mutant 2: Tampered QoI must fail real verifier even if someone ignores hash
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["qoi_value"] = -42.0
    assert "VER-HASH-MISMATCH" in verify_evidence_payload(tampered).diagnostic_codes


def test_empty_config_metadata_bypass_and_outcome_nan_rejected(tmp_path: Path, monkeypatch):
    # Empty solver_config / mesh_metadata with recomputed hash must fail closed
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["solver_config"] = {}
    tampered["mesh_metadata"] = {}
    tampered["canonical_result_hash"] = compute_canonical_hash(tampered)
    rep = verify_evidence_payload(tampered)
    assert rep.valid is False
    assert "VER-METADATA-INCONSISTENT" in rep.diagnostic_codes
    assert "VER-REFUSAL-MISMATCH" in rep.diagnostic_codes

    # NaN in outcome_metrics.estimator_value must return VerificationReport(valid=False), not raise ValueError
    nan_rec = _produce_valid_record_dict(tmp_path, monkeypatch)
    nan_rec["outcome_metrics"]["estimator_value"] = float("nan")
    nan_rep = verify_evidence_payload(nan_rec)
    assert nan_rep.valid is False
    assert "VER-SCHEMA-INVALID" in nan_rep.diagnostic_codes
