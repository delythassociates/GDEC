"""
Comprehensive tests for machine-readable status_register.json generation
and CI traceability enforcement.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import pytest

from gdec.verification.status_register import (
    generate_status_register,
    verify_traceability,
    TraceabilityVerificationError,
    SYSTEM_CAPABILITIES,
    get_git_info,
    get_environment_info,
)


class TestStatusRegisterTraceability:
    """Verifies schema validity and CI traceability enforcement for GDEC capabilities."""

    def test_status_register_schema_and_generation(self, tmp_path):
        """Verify status register generates valid JSON matching schema specification with executed tests."""
        out_file = str(tmp_path / "status_register.json")
        data = generate_status_register(output_path=out_file, run_tests=True)

        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["schema_version"] == "1.0.0"
        assert "generated_at" in loaded
        assert "git" in loaded
        assert "commit_sha" in loaded["git"]
        assert "branch" in loaded["git"]
        assert "dirty" in loaded["git"]

        assert "environment" in loaded
        assert "platform" in loaded["environment"]
        assert "python_version" in loaded["environment"]
        assert "numpy_version" in loaded["environment"]
        assert "scipy_version" in loaded["environment"]
        assert "scikit_fem_version" in loaded["environment"]

        assert loaded["total_capabilities"] == len(SYSTEM_CAPABILITIES)
        assert len(loaded["capabilities"]) == len(SYSTEM_CAPABILITIES)

        # Check that executed test IDs are captured
        for cap in loaded["capabilities"]:
            assert "executed_test_ids" in cap
            if cap["claimed_status"] == "NUMERICALLY VERIFIED":
                assert cap["test_execution_state"] == "PASS"
                assert len(cap["executed_test_ids"]) > 0

        # Check summary counts
        summary = loaded["status_summary"]
        assert summary["NUMERICALLY VERIFIED"] > 0
        assert summary["TESTED"] > 0
        assert sum(summary.values()) == loaded["total_capabilities"]

    def test_every_capability_has_traceable_fields(self):
        """Verify each capability has required audit fields populated."""
        for cap in SYSTEM_CAPABILITIES:
            assert len(cap.capability_id) > 0
            assert len(cap.name) > 0
            assert cap.subsystem in ["compiler", "eir", "fem", "estimator", "solver", "dse"]
            assert cap.claimed_status in ["PLANNED", "IMPLEMENTED", "EXECUTED", "TESTED", "NUMERICALLY VERIFIED", "INDEPENDENTLY VALIDATED"]
            assert len(cap.evidence_path) > 0
            assert len(cap.test_files) > 0
            assert len(cap.notes) > 0

    def test_traceability_enforcement_passes_healthy_register(self, tmp_path):
        """Gate 2: Traceability verification must pass when all tests pass."""
        out_file = str(tmp_path / "status_register.json")
        data = generate_status_register(output_path=out_file, run_tests=True)
        # Should not raise (allow_dirty and allow_stale permit unit test execution on unstaged working tree)
        verify_traceability(data, on_disk_path=out_file, allow_dirty=True, allow_stale=True)

    def test_traceability_enforcement_fails_on_unverified_capability(self):
        """Gate 2: Any NUMERICALLY VERIFIED capability with FAIL or missing tests must fail."""
        current_sha = get_git_info()["commit_sha"]
        bad_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "capabilities": [
                {
                    "capability_id": "fake_broken_capability",
                    "name": "Broken Mechanical Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "FAILED",
                    "test_files_exist": True,
                    "executed_test_ids": ["tests/fake_test.py::test_broken"],
                    "passed_test_ids": [],
                    "failed_test_ids": ["tests/fake_test.py::test_broken"],
                    "skipped_test_ids": [],
                    "test_execution_state": "FAIL",
                    "test_files": ["tests/fake_test.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(bad_register, allow_dirty=True)
        assert "Broken Mechanical Solver" in str(exc_info.value)
        assert "expected 'PASS'" in str(exc_info.value)

    def test_traceability_enforcement_fails_on_stale_commit_sha(self):
        """WP2-R4: Status register with a stale commit SHA must fail --check."""
        stale_register = {
            "git": {"commit_sha": "deadbeef00000000000000000000000000000000", "dirty": False},
            "capabilities": []
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(stale_register, allow_dirty=True)
        assert "Stale status register detected" in str(exc_info.value)

    def test_traceability_enforcement_fails_on_dirty_working_tree(self):
        """WP2-R4: Status register indicating dirty tree must fail."""
        current_sha = get_git_info()["commit_sha"]
        dirty_register = {
            "git": {"commit_sha": current_sha, "dirty": True},
            "capabilities": []
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(dirty_register)
        assert "dirty" in str(exc_info.value).lower()

    def test_traceability_enforcement_fails_on_zero_executed_tests(self):
        """WP2-R4: NUMERICALLY VERIFIED capability with 0 executed tests must fail."""
        current_sha = get_git_info()["commit_sha"]
        empty_tests_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "capabilities": [
                {
                    "capability_id": "untested_capability",
                    "name": "Untested Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "PLANNED",
                    "test_files_exist": True,
                    "executed_test_ids": [],
                    "passed_test_ids": [],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/test_existing.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(empty_tests_register, allow_dirty=True)
        assert "0 tests were executed" in str(exc_info.value)

    def test_traceability_enforcement_fails_on_missing_test_files(self):
        """Gate 2: Any NUMERICALLY VERIFIED capability with missing test files must fail."""
        current_sha = get_git_info()["commit_sha"]
        bad_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "capabilities": [
                {
                    "capability_id": "fake_missing_files",
                    "name": "Missing Test Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "TESTED",
                    "test_files_exist": False,
                    "executed_test_ids": ["tests/non_existent_file_99999.py::test_foo"],
                    "passed_test_ids": ["tests/non_existent_file_99999.py::test_foo"],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/non_existent_file_99999.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(bad_register, allow_dirty=True)
        assert "missing" in str(exc_info.value)

    def test_cli_script_generates_and_checks(self, tmp_path):
        """Verify scripts/generate_status_register.py runs cleanly via CLI using isolated tmp_path."""
        out_path = str(tmp_path / "cli_status_register.json")
        # Generate fresh status register to tmp_path (never write to tracked repo files)
        gen_cmd = [sys.executable, "scripts/generate_status_register.py", "--output", out_path]
        gen_proc = subprocess.run(gen_cmd, capture_output=True, text=True)
        assert gen_proc.returncode == 0, f"Generation failed: {gen_proc.stderr}\n{gen_proc.stdout}"

        # Verify check succeeds
        chk_cmd = [sys.executable, "scripts/generate_status_register.py", "--check", "--input", out_path, "--allow-dirty"]
        chk_proc = subprocess.run(chk_cmd, capture_output=True, text=True)
        assert chk_proc.returncode == 0, f"CLI check failed: {chk_proc.stderr}\n{chk_proc.stdout}"
        assert "[PASS]" in chk_proc.stdout

    def test_traceability_fails_when_claimed_status_exceeds_demonstrated_status(self):
        """WP2-R4: Fails if claimed status exceeds demonstrated status."""
        current_sha = get_git_info()["commit_sha"]
        exceeded_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "capabilities": [
                {
                    "capability_id": "overclaimed_capability",
                    "name": "Overclaimed Component",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "TESTED",
                    "test_files_exist": True,
                    "executed_test_ids": ["tests/test_something.py::test_basic"],
                    "passed_test_ids": ["tests/test_something.py::test_basic"],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/test_something.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(exceeded_register, allow_dirty=True)
        assert "exceeds demonstrated status" in str(exc_info.value)

    def test_traceability_fails_on_skipped_tests(self):
        """WP2-R4: Any skipped tests on claimed capability must fail."""
        current_sha = get_git_info()["commit_sha"]
        skipped_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "capabilities": [
                {
                    "capability_id": "skipped_capability",
                    "name": "Skipped Component",
                    "claimed_status": "TESTED",
                    "demonstrated_status": "TESTED",
                    "test_files_exist": True,
                    "executed_test_ids": ["tests/test_something.py::test_1"],
                    "passed_test_ids": ["tests/test_something.py::test_1"],
                    "failed_test_ids": [],
                    "skipped_test_ids": ["tests/test_something.py::test_skipped"],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/test_something.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(skipped_register, allow_dirty=True)
        assert "skipped" in str(exc_info.value).lower()

    def test_working_tree_cleanliness_detects_untracked_and_modified(self, tmp_path):
        """WP2-R4: Working tree cleanliness detects unexpected untracked files while preserving user files."""
        git_info = get_git_info()
        assert isinstance(git_info["dirty"], bool)
        assert isinstance(git_info["dirty_entries"], list)
        # Verify that preserved user prefixes are not counted as dirty
        for entry in git_info["dirty_entries"]:
            assert "analyser.py" not in entry
            assert "src/gdec/runtime" not in entry
