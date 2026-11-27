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
    assert any(
        c in report.diagnostic_codes
        for c in ("VER-SCHEMA-INVALID", "VER-ESTIMATOR-CLASS-INVALID")
    )


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
    assert "VER-REFUSAL-MISMATCH" in report.diagnostic_codes


def test_nan_and_inf_rejected(tmp_path: Path, monkeypatch):
    tampered = _produce_valid_record_dict(tmp_path, monkeypatch)
    tampered["qoi_value"] = float("nan")
    report = verify_evidence_payload(tampered)
    assert report.valid is False
    assert "VER-NONFINITE" in report.diagnostic_codes


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
    h = "a" * 64
    ctx = RefusalContext(
        budget_exhausted=True,
        target_tolerance_met=False,
        dof_count=100,
        free_dof_count=90,
        interior_facet_count=40,
        interior_node_count=15,
        mesh_element_count=80,
        canonical_eir_hash=h,
        problem_ir_hash=h,
        execution_plan_hash=h,
        mesh_hash=h,
        parent_artifacts=[
            {"artifact_id": "x", "artifact_type": "canonical_eir", "sha256_hash": h},
            {"artifact_id": "y", "artifact_type": "problem_ir", "sha256_hash": h},
            {"artifact_id": "z", "artifact_type": "execution_plan", "sha256_hash": h},
        ],
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
    assert "VER-NONFINITE" in nan_rep.diagnostic_codes


def test_hostile_verifier_attack_vectors(tmp_path: Path, monkeypatch):
    base = _produce_valid_record_dict(tmp_path, monkeypatch)

    # 1. Oversized file (> MAX_EVIDENCE_BYTES)
    big_file = tmp_path / "huge.json"
    big_file.write_bytes(b"{" + b" " * 5_000_010 + b"}")
    rep = verify_evidence_file(big_file)
    assert rep.valid is False
    assert "VER-MALFORMED-INPUT" in rep.diagnostic_codes

    # 2. Duplicate JSON keys in raw text
    dup_file = tmp_path / "dup.json"
    dup_file.write_text('{"qoi_value": 1.0, "qoi_value": 2.0}', encoding="utf-8")
    rep_dup = verify_evidence_file(dup_file)
    assert rep_dup.valid is False
    assert "VER-MALFORMED-INPUT" in rep_dup.diagnostic_codes

    # 3. Raw NaN / Infinity in JSON text
    nan_file = tmp_path / "raw_nan.json"
    nan_file.write_text('{"qoi_value": NaN}', encoding="utf-8")
    rep_nan = verify_evidence_file(nan_file)
    assert rep_nan.valid is False
    assert any(c in rep_nan.diagnostic_codes for c in ("VER-NONFINITE", "VER-MALFORMED-INPUT"))

    # 4. Deeply nested JSON (> 32)
    nested: dict = {"a": 1}
    for _ in range(40):
        nested = {"nested": nested}
    assert "VER-MALFORMED-INPUT" in verify_evidence_payload(nested).diagnostic_codes

    # 5. Oversized string (> 100,000)
    big_str = copy.deepcopy(base)
    big_str["problem_name"] = "x" * 100_005
    assert "VER-MALFORMED-INPUT" in verify_evidence_payload(big_str).diagnostic_codes

    # 6. Oversized integer (> 10**100)
    big_int = copy.deepcopy(base)
    big_int["dof_count"] = 10**105
    assert "VER-MALFORMED-INPUT" in verify_evidence_payload(big_int).diagnostic_codes

    # 7. Type confusion (bool passed for int field)
    bool_int = copy.deepcopy(base)
    bool_int["dof_count"] = True
    assert verify_evidence_payload(bool_int).valid is False

    # 8. Tampered refusal evaluation version / diagnostic_context with recomputed hash
    tampered_ref = copy.deepcopy(base)
    tampered_ref["refusal_evaluations"][0]["version"] = "9.9.9"
    tampered_ref["canonical_result_hash"] = compute_canonical_hash(tampered_ref)
    assert "VER-REFUSAL-MISMATCH" in verify_evidence_payload(tampered_ref).diagnostic_codes

    # 9. Tampered problem_ir_hash mismatching parent_artifacts with recomputed hash
    tampered_ir = copy.deepcopy(base)
    tampered_ir["problem_ir_hash"] = "0" * 64
    tampered_ir["canonical_result_hash"] = compute_canonical_hash(tampered_ir)
    assert "VER-PROVENANCE-INVALID" in verify_evidence_payload(tampered_ir).diagnostic_codes

    # 10. Unsupported BoundCertificateEvidence
    bad_cert = copy.deepcopy(base)
    bad_cert["estimator_classification"] = EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND.value
    bad_cert["bound_certificate"] = {
        "bound_checker_identity": "FakeChecker",
        "bound_checker_version": "0.1",
        "certificate_hash": "a" * 64,
        "certified_upper_bound": 1.0,
        "verified": True,
    }
    bad_cert["canonical_result_hash"] = compute_canonical_hash(bad_cert)
    assert verify_evidence_payload(bad_cert).valid is False

    # 11. QUALIFIED status with UNASSESSED V&V
    bad_qual = copy.deepcopy(base)
    bad_qual["qualification_status"] = "QUALIFIED"
    bad_qual["canonical_result_hash"] = compute_canonical_hash(bad_qual)
    assert "VER-SCHEMA-INVALID" in verify_evidence_payload(bad_qual).diagnostic_codes

    # 12. error_estimate_units mismatch
    bad_units = copy.deepcopy(base)
    bad_units["error_estimate_units"] = "inches"
    bad_units["canonical_result_hash"] = compute_canonical_hash(bad_units)
    assert verify_evidence_payload(bad_units).valid is False

    # 13. Structural floor violation (dof_count=4) with refused=False
    low_dof = copy.deepcopy(base)
    low_dof["dof_count"] = 4
    low_dof["outcome_metrics"]["final_dofs"] = 4
    low_dof["canonical_result_hash"] = compute_canonical_hash(low_dof)
    assert "VER-REFUSAL-MISMATCH" in verify_evidence_payload(low_dof).diagnostic_codes

    # 14. Malformed JSON file & missing file
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert verify_evidence_file(bad_json).valid is False
    assert verify_evidence_file(tmp_path / "does_not_exist.json").valid is False


def test_finding_a_qualification_and_cli_require_qualified(tmp_path: Path, monkeypatch):
    from gdec.compiler import GDECCompiler
    from gdec.core import ExecutionPlanner, GDECRuntime

    # Non-refused runtime record is NOT_QUALIFIED_UNASSESSED_VV and fails --require-qualified with exit 2
    out_file = tmp_path / "unassessed.json"
    monkeypatch.setattr(
        sys, "argv", ["gdec", "run", "examples/cantilever.gdc", "--strategy", "goal_aware", "-o", str(out_file)]
    )
    assert cli_main() == 0
    monkeypatch.setattr(sys, "argv", ["gdec", "verify", str(out_file), "--require-qualified"])
    assert cli_main() == 2

    # Valid refused record (budget exhausted) passes integrity verification (exit 0) but fails --require-qualified (exit 2)
    res = GDECCompiler().compile_file("examples/cantilever.gdc")
    res.ir.budget.value = 500
    plan = ExecutionPlanner().create_plan(res.ir, override_strategy="goal_aware")
    trace = GDECRuntime(plan, res.ir).execute()
    assert trace.evidence_record is not None
    assert trace.evidence_record.refused is True
    assert trace.evidence_record.qualification_status == "REFUSED"

    refused_file = tmp_path / "refused.json"
    refused_file.write_text(trace.evidence_record.to_canonical_json(), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["gdec", "verify", str(refused_file)])
    assert cli_main() == 0
    monkeypatch.setattr(sys, "argv", ["gdec", "verify", str(refused_file), "--require-qualified"])
    assert cli_main() == 2


def test_finding_b_provenance_collision_resistance():
    from gdec.compiler import GDECCompiler
    from gdec.core import ExecutionPlanner, GDECRuntime

    compiler = GDECCompiler()
    base_ir = compiler.compile_file("examples/cantilever.gdc").ir
    base_plan = ExecutionPlanner().create_plan(base_ir, override_strategy="goal_aware")
    base_rec = GDECRuntime(base_plan, base_ir).execute().evidence_record
    assert base_rec is not None

    # Differing budget produces distinct problem_ir_hash and canonical_result_hash
    ir_budget = copy.deepcopy(base_ir)
    ir_budget.budget.value = 5000
    plan_budget = ExecutionPlanner().create_plan(ir_budget, override_strategy="goal_aware")
    rec_budget = GDECRuntime(plan_budget, ir_budget).execute().evidence_record
    assert rec_budget is not None
    assert rec_budget.problem_ir_hash != base_rec.problem_ir_hash
    assert rec_budget.canonical_result_hash != base_rec.canonical_result_hash

    # Differing strategy produces distinct execution_plan_hash and canonical_result_hash
    plan_unif = ExecutionPlanner().create_plan(base_ir, override_strategy="uniform")
    rec_unif = GDECRuntime(plan_unif, base_ir).execute().evidence_record
    assert rec_unif is not None
    assert rec_unif.execution_plan_hash != base_rec.execution_plan_hash
    assert rec_unif.canonical_result_hash != base_rec.canonical_result_hash


def test_finding_de_cli_default_persistence_dwr_and_benchmark(tmp_path: Path, monkeypatch, capsys):
    from gdec.benchmark import BenchmarkMetrics, BenchmarkReporter, BenchmarkRunner
    from gdec.compiler import GDECCompiler

    # 1. Default persistence without -o (isolated in tmp_path)
    src_gdc = Path("examples/cantilever.gdc").resolve()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gdec", "run", str(src_gdc), "--strategy", "goal_aware"])
    assert cli_main() == 0
    persisted = list((tmp_path / "results" / "evidence").glob("cantilever_*.json"))
    assert len(persisted) == 1
    assert verify_evidence_file(persisted[0]).valid is True

    # 2. DWR strategy executes cleanly without fixed_boundaries crash
    dwr_out = tmp_path / "dwr.json"
    monkeypatch.setattr(sys, "argv", ["gdec", "run", str(src_gdc), "--strategy", "dwr", "-o", str(dwr_out)])
    assert cli_main() == 0
    dwr_data = json.loads(dwr_out.read_text(encoding="utf-8"))
    assert dwr_data["estimator_classification"] == EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE.value
    assert dwr_data["error_estimate_units"] == "mm"

    # 3. Invalid output path returns exit 1
    bad_dir = tmp_path / "existing_file"
    bad_dir.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["gdec", "run", str(src_gdc), "--strategy", "goal_aware", "-o", str(bad_dir / "out.json")]
    )
    assert cli_main() == 1

    # 4. verify --json outputs valid JSON
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["gdec", "verify", str(dwr_out), "--json"])
    assert cli_main() == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["valid"] is True
    assert parsed["qualification_status"] == "NOT_QUALIFIED_UNASSESSED_VV"

    # 5. Benchmark propagates refusal/qualification & marks research-only
    ir = GDECCompiler().compile_file(src_gdc).ir
    ir.budget.value = 1500
    suite = BenchmarkRunner(ir, ref_target_dofs=2000).run_all()
    df = BenchmarkMetrics.summary_table(suite)
    assert "Qualification" in df.columns
    assert "Refused" in df.columns
    md = BenchmarkReporter.generate_markdown_report(suite, ir)
    assert "RESEARCH BENCHMARK" in md
    bm_dir = tmp_path / "bm_out"
    exported = BenchmarkReporter.export_all(suite, ir, bm_dir)
    json_path = next(bm_dir.glob("*.json"))
    bm_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert bm_json["classification"] == "RESEARCH_BENCHMARK_ONLY"
    assert len(exported) >= 4


def test_review_fixes_epistemic_and_ref007(tmp_path: Path, monkeypatch):
    from gdec.core.telemetry import ExecutionTrace
    from gdec.dse.evidence_graph import EngineeringEvidenceRecord, ValidationStatus

    # 1. ExecutionTrace.qualified_qoi_mm fails closed when evidence_record is None
    trace = ExecutionTrace(
        problem_name="CantileverDemo",
        strategy="goal_aware",
        target_accuracy_pct=1.0,
        budget_max_dofs=1000,
        converged=False,
        stop_reason="test",
        total_wall_time_sec=0.1,
    )
    assert trace.qualified_qoi_mm is None

    # 2. QUALIFIED requires target_tolerance_met=True and verification_validation_status validated
    base = _produce_valid_record_dict(tmp_path, monkeypatch)
    bad_qual = copy.deepcopy(base)
    bad_qual["verification_status"] = ValidationStatus.VERIFIED.value
    bad_qual["validation_status"] = ValidationStatus.VALIDATED.value
    bad_qual["verification_validation_status"] = ValidationStatus.VALIDATED.value
    bad_qual["qualification_status"] = "QUALIFIED"
    bad_qual["resource_consumption"]["target_tolerance_met"] = False
    with pytest.raises(Exception):
        EngineeringEvidenceRecord(**bad_qual)


def test_aud_02_direct_verifier_finite_qoi_nonfinite_estimator(tmp_path: Path, monkeypatch):
    from gdec.dse.evidence_graph import build_evidence_record_with_hash

    base = _produce_valid_record_dict(tmp_path, monkeypatch)
    assert base["qoi_value"] is not None

    # 1. Inject non-finite estimator values while keeping qoi_value finite -> must fail closed
    for bad_val in (float("nan"), float("inf")):
        tampered = copy.deepcopy(base)
        tampered["error_estimate"] = bad_val
        tampered["outcome_metrics"]["estimator_value"] = bad_val
        report = verify_evidence_payload(tampered)
        assert report.valid is False
        assert report.qualification_status != "QUALIFIED"
        assert "VER-NONFINITE" in report.diagnostic_codes

    # 2. Valid refused REF-007 record (finite QoI, nonfinite_detected=True, error_estimate=None)
    ref_rec_dict = copy.deepcopy(base)
    ref_rec_dict["error_estimate"] = None
    ref_rec_dict["outcome_metrics"]["estimator_value"] = None
    ref_rec_dict["refused"] = True
    ref_rec_dict["qualification_status"] = "REFUSED"
    ref_rec_dict["qoi_epistemic_role"] = "unavailable"
    sc = ref_rec_dict["solver_config"]
    mm = ref_rec_dict["mesh_metadata"]
    rc = ref_rec_dict["resource_consumption"]
    ctx = RefusalContext(
        budget_exhausted=rc["budget_exhausted"],
        target_tolerance_met=rc["target_tolerance_met"],
        estimator_identity=ref_rec_dict["estimator_identity"],
        estimator_classification=ref_rec_dict["estimator_classification"],
        problem_class=sc["problem_class"],
        reference_required=sc["reference_required"],
        qoi_boundary=sc["qoi_boundary"],
        fixed_boundaries=sc["fixed_boundaries"],
        dof_count=ref_rec_dict["dof_count"],
        free_dof_count=mm["free_dofs"],
        interior_node_count=mm["interior_nodes"],
        interior_facet_count=mm["interior_facets"],
        min_required_dofs=sc["min_required_dofs"],
        solver_converged=sc["solver_converged"],
        adjoint_converged=sc["adjoint_converged"],
        qoi_value=ref_rec_dict["qoi_value"],
        residual_norm=sc["residual_norm"],
        adjoint_residual_norm=sc["adjoint_residual_norm"],
        error_estimate=None,
        nonfinite_detected=True,
        mesh_valid=mm["mesh_valid"],
        mesh_element_count=mm["nelements"],
        model_applicability_status=ref_rec_dict["model_applicability_status"],
        parent_artifacts=ref_rec_dict["parent_artifacts"],
        problem_ir_hash=ref_rec_dict["problem_ir_hash"],
        canonical_eir_hash=ref_rec_dict["canonical_eir_hash"],
        execution_plan_hash=ref_rec_dict["execution_plan_hash"],
        mesh_hash=ref_rec_dict["mesh_hash"],
        mandatory_evidence_present=sc["mandatory_evidence_present"],
        evidence_stale=ref_rec_dict["evidence_stale"],
        evidence_invalidated=ref_rec_dict["evidence_invalidated"],
    )
    ref_res = RefusalEngine().evaluate(ctx)
    assert "REF-007" in ref_res.triggered_rule_ids
    ref_rec_dict["refusal_evaluations"] = [ev.model_dump(mode="json") for ev in ref_res.evaluations]
    ref_rec_dict["refusal_reasons"] = list(ref_res.reasons)
    rebuilt = build_evidence_record_with_hash(ref_rec_dict).model_dump(mode="json")
    ok_rep = verify_evidence_payload(rebuilt)
    assert ok_rep.valid is True
    assert ok_rep.refused is True
    assert ok_rep.qualification_status == "REFUSED"


def test_aud_01_v1_0_0_schema_rejected(tmp_path: Path, monkeypatch):
    base = _produce_valid_record_dict(tmp_path, monkeypatch)
    legacy = copy.deepcopy(base)
    legacy["schema_version"] = "1.0.0"
    legacy["canonical_result_hash"] = compute_canonical_hash(legacy)
    report = verify_evidence_payload(legacy)
    assert report.valid is False
    assert "VER-SCHEMA-INVALID" in report.diagnostic_codes
