"""
Negative and positive tests for the ratcheting branch coverage gate.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.check_branch_coverage import CoverageGateError, evaluate_branch_coverage, main


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_coverage_below_floor_fails(tmp_path: Path):
    baseline = _write_json(tmp_path / "baseline.json", {"baseline_branch_coverage_pct": 63.0})
    cov = _write_json(tmp_path / "cov.json", {"totals": {"num_branches": 1000, "covered_branches": 629}})
    with pytest.raises(CoverageGateError, match="regression"):
        evaluate_branch_coverage(cov, baseline)
    assert main(["--coverage-json", str(cov), "--baseline", str(baseline)]) == 1


def test_coverage_equal_to_floor_passes(tmp_path: Path):
    baseline = _write_json(tmp_path / "baseline.json", {"baseline_branch_coverage_pct": 63.0})
    cov = _write_json(tmp_path / "cov.json", {"totals": {"num_branches": 1000, "covered_branches": 630}})
    obs, floor, covered, total = evaluate_branch_coverage(cov, baseline)
    assert obs == pytest.approx(63.0)
    assert floor == pytest.approx(63.0)
    assert (covered, total) == (630, 1000)
    assert main(["--coverage-json", str(cov), "--baseline", str(baseline)]) == 0


def test_coverage_above_floor_passes(tmp_path: Path):
    baseline = _write_json(tmp_path / "baseline.json", {"baseline_branch_coverage_pct": 63.0})
    cov = _write_json(tmp_path / "cov.json", {"totals": {"num_branches": 1000, "covered_branches": 700}})
    obs, floor, _, _ = evaluate_branch_coverage(cov, baseline)
    assert obs == pytest.approx(70.0)
    assert floor == pytest.approx(63.0)
    assert main(["--coverage-json", str(cov), "--baseline", str(baseline)]) == 0


def test_missing_or_malformed_coverage_data_fails(tmp_path: Path):
    baseline = _write_json(tmp_path / "baseline.json", {"baseline_branch_coverage_pct": 63.0})

    # Missing coverage file
    with pytest.raises(CoverageGateError, match="not found"):
        evaluate_branch_coverage(tmp_path / "nonexistent.json", baseline)

    # Malformed JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CoverageGateError, match="Malformed coverage JSON"):
        evaluate_branch_coverage(bad_json, baseline)

    # Missing totals / branch fields
    no_branches = _write_json(tmp_path / "no_branches.json", {"totals": {"num_statements": 100}})
    with pytest.raises(CoverageGateError, match="num_branches"):
        evaluate_branch_coverage(no_branches, baseline)

    # Zero branches rejected
    zero_branches = _write_json(tmp_path / "zero.json", {"totals": {"num_branches": 0, "covered_branches": 0}})
    with pytest.raises(CoverageGateError, match="Zero-branch"):
        evaluate_branch_coverage(zero_branches, baseline)
