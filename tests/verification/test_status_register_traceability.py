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
    GitInspectionError,
    SYSTEM_CAPABILITIES,
    CapabilityEntry,
    get_git_info,
    get_environment_info,
    get_provenance_info,
)


class TestStatusRegisterTraceability:
    """Verifies schema validity, evidence derivation, and CI traceability enforcement for GDEC capabilities."""

    def test_status_register_schema_and_generation(self, tmp_path):
        """Verify status register generates valid JSON matching schema specification with executed tests."""
        out_file = str(tmp_path / "status_register.json")
        data = generate_status_register(output_path=out_file, run_tests=True)

        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["schema_version"] == "1.1.0"
        assert "generated_at" in loaded
        assert "git" in loaded
        assert "commit_sha" in loaded["git"]
        assert "branch" in loaded["git"]
        assert "dirty" in loaded["git"]

        assert "provenance" in loaded
        assert "is_ci" in loaded["provenance"]
        assert "local_execution" in loaded["provenance"]

        assert "environment" in loaded
        assert "platform" in loaded["environment"]
        assert "python_version" in loaded["environment"]
        assert "numpy_version" in loaded["environment"]
        assert "scipy_version" in loaded["environment"]
        assert "scikit_fem_version" in loaded["environment"]

        assert "collection_errors" in loaded
        assert loaded["collection_errors"] == []
        assert "pytest_exit_code" in loaded
        assert loaded["pytest_exit_code"] == 0

        assert loaded["total_capabilities"] == len(SYSTEM_CAPABILITIES)
        assert len(loaded["capabilities"]) == len(SYSTEM_CAPABILITIES)

        # Check that executed test IDs and required test nodes are captured
        for cap in loaded["capabilities"]:
            assert "required_test_node_ids" in cap
            assert len(cap["required_test_node_ids"]) > 0
            assert "verification_criteria" in cap
            assert len(cap["verification_criteria"]) > 0
            assert "executed_test_ids" in cap
            assert "required_nodes_passed" in cap
            assert cap["test_execution_state"] == "PASS"
            assert cap["demonstrated_status"] == cap["claimed_status"]
            assert len(cap["required_nodes_missing"]) == 0
            assert len(cap["required_nodes_failed"]) == 0
            assert len(cap["required_nodes_skipped"]) == 0

        # Check summary counts
        summary = loaded["status_summary"]
        assert summary["NUMERICALLY VERIFIED"] == 16
        assert summary["TESTED"] == 8
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
            assert len(cap.required_test_node_ids) > 0
            assert len(cap.verification_criteria) > 0
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
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [
                {
                    "capability_id": "fake_broken_capability",
                    "name": "Broken Mechanical Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "FAILED",
                    "test_files_exist": True,
                    "required_test_node_ids": ["tests/fake_test.py::test_broken"],
                    "executed_test_ids": ["tests/fake_test.py::test_broken"],
                    "passed_test_ids": [],
                    "failed_test_ids": ["tests/fake_test.py::test_broken"],
                    "skipped_test_ids": [],
                    "required_nodes_passed": [],
                    "required_nodes_failed": ["tests/fake_test.py::test_broken"],
                    "required_nodes_skipped": [],
                    "required_nodes_missing": [],
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
            "collection_errors": [],
            "pytest_exit_code": 0,
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
            "collection_errors": [],
            "pytest_exit_code": 0,
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
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [
                {
                    "capability_id": "untested_capability",
                    "name": "Untested Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "PLANNED",
                    "test_files_exist": True,
                    "required_test_node_ids": ["tests/test_existing.py::test_a"],
                    "executed_test_ids": [],
                    "passed_test_ids": [],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "required_nodes_passed": [],
                    "required_nodes_failed": [],
                    "required_nodes_skipped": [],
                    "required_nodes_missing": ["tests/test_existing.py::test_a"],
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
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [
                {
                    "capability_id": "fake_missing_files",
                    "name": "Missing Test Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "TESTED",
                    "test_files_exist": False,
                    "required_test_node_ids": ["tests/non_existent_file_99999.py::test_foo"],
                    "executed_test_ids": ["tests/non_existent_file_99999.py::test_foo"],
                    "passed_test_ids": ["tests/non_existent_file_99999.py::test_foo"],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "required_nodes_passed": ["tests/non_existent_file_99999.py::test_foo"],
                    "required_nodes_failed": [],
                    "required_nodes_skipped": [],
                    "required_nodes_missing": [],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/non_existent_file_99999.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(bad_register, allow_dirty=True)
        assert "missing" in str(exc_info.value)

    def test_traceability_enforcement_fails_on_collection_error(self):
        """WP2-R4: Test suite reporting collection error must fail traceability."""
        current_sha = get_git_info()["commit_sha"]
        coll_error_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "collection_errors": ["Collection failure in tests/test_bad.py: SyntaxError"],
            "pytest_exit_code": 2,
            "capabilities": []
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(coll_error_register, allow_dirty=True)
        assert "collection errors" in str(exc_info.value).lower()

    def test_traceability_enforcement_fails_on_nonzero_exit_code(self):
        """WP2-R4: Test suite reporting non-zero exit code must fail traceability."""
        current_sha = get_git_info()["commit_sha"]
        exit_code_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "collection_errors": [],
            "pytest_exit_code": 1,
            "capabilities": []
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(exit_code_register, allow_dirty=True)
        assert "non-zero exit code" in str(exc_info.value).lower()

    def test_traceability_fails_when_claimed_status_exceeds_demonstrated_status(self):
        """WP2-R4: Fails if claimed status exceeds demonstrated status."""
        current_sha = get_git_info()["commit_sha"]
        exceeded_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [
                {
                    "capability_id": "overclaimed_capability",
                    "name": "Overclaimed Component",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "demonstrated_status": "TESTED",
                    "test_files_exist": True,
                    "required_test_node_ids": ["tests/test_something.py::test_basic"],
                    "executed_test_ids": ["tests/test_something.py::test_basic"],
                    "passed_test_ids": ["tests/test_something.py::test_basic"],
                    "failed_test_ids": [],
                    "skipped_test_ids": [],
                    "required_nodes_passed": ["tests/test_something.py::test_basic"],
                    "required_nodes_failed": [],
                    "required_nodes_skipped": [],
                    "required_nodes_missing": [],
                    "test_execution_state": "PASS",
                    "test_files": ["tests/test_something.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(exceeded_register, allow_dirty=True)
        assert "exceeds demonstrated status" in str(exc_info.value)

    def test_traceability_fails_on_skipped_required_tests(self):
        """WP2-R4: Any skipped required test on claimed capability must fail."""
        current_sha = get_git_info()["commit_sha"]
        skipped_register = {
            "git": {"commit_sha": current_sha, "dirty": False},
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [
                {
                    "capability_id": "skipped_capability",
                    "name": "Skipped Component",
                    "claimed_status": "TESTED",
                    "demonstrated_status": "PARTIAL_SKIP",
                    "test_files_exist": True,
                    "required_test_node_ids": ["tests/test_something.py::test_skipped"],
                    "executed_test_ids": ["tests/test_something.py::test_skipped"],
                    "passed_test_ids": [],
                    "failed_test_ids": [],
                    "skipped_test_ids": ["tests/test_something.py::test_skipped"],
                    "required_nodes_passed": [],
                    "required_nodes_failed": [],
                    "required_nodes_skipped": ["tests/test_something.py::test_skipped"],
                    "required_nodes_missing": [],
                    "test_execution_state": "PARTIAL",
                    "test_files": ["tests/test_something.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(skipped_register, allow_dirty=True)
        assert "skipped" in str(exc_info.value).lower()

    def test_isolated_git_repo_cleanliness_and_preservation(self, tmp_path):
        """
        WP2-R4: Test Git cleanliness detection in an isolated temporary Git repo.
        Verifies:
        1. Clean working tree is detected as clean.
        2. Tracked file modification is detected as dirty.
        3. Newly created untracked file is detected as dirty.
        4. Preserved user paths (analyser.py, runtime/) are strictly ignored and remain clean.
        """
        git_dir = tmp_path / "test_repo"
        git_dir.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@gdec.org", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@gdec.org"}

        # 1. Initialize repo
        subprocess.check_call(["git", "init"], cwd=str(git_dir), env=env)
        tracked_file = git_dir / "README.md"
        tracked_file.write_text("# Test Repo\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "README.md"], cwd=str(git_dir), env=env)
        subprocess.check_call(["git", "commit", "-m", "Initial commit"], cwd=str(git_dir), env=env)

        # Baseline: clean
        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is False
        assert len(info["dirty_entries"]) == 0

        # 2. Tracked file modification -> dirty
        tracked_file.write_text("# Test Repo Modified\n", encoding="utf-8")
        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is True
        assert any("README.md" in e for e in info["dirty_entries"])

        # Revert modification -> clean again
        subprocess.check_call(["git", "checkout", "--", "README.md"], cwd=str(git_dir), env=env)
        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is False

        # 3. Newly created untracked file -> dirty
        untracked = git_dir / "random_new_file.txt"
        untracked.write_text("Hello", encoding="utf-8")
        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is True
        assert any("random_new_file.txt" in e for e in info["dirty_entries"])
        untracked.unlink()

        # Clean again
        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is False

        # 4. Preserved user paths must NOT trigger dirty state!
        user_analyser = git_dir / "src" / "gdec" / "core"
        user_analyser.mkdir(parents=True)
        (user_analyser / "analyser.py").write_text("# User analyser code\n", encoding="utf-8")

        user_runtime = git_dir / "src" / "gdec" / "runtime"
        user_runtime.mkdir(parents=True)
        (user_runtime / "engine.py").write_text("# User runtime code\n", encoding="utf-8")

        info = get_git_info(repo_dir=str(git_dir))
        assert info["dirty"] is False, f"Preserved user files should not be dirty: {info['dirty_entries']}"
        assert len(info["dirty_entries"]) == 0

    def test_cli_script_generates_and_checks(self, tmp_path):
        """Verify scripts/generate_status_register.py runs cleanly via CLI using isolated tmp_path."""
        out_path = str(tmp_path / "cli_status_register.json")
        # Generate fresh status register to tmp_path (never write to tracked repo files)
        gen_cmd = [sys.executable, "scripts/generate_status_register.py", "--output", out_path]
        gen_proc = subprocess.run(gen_cmd, capture_output=True, text=True)
        assert gen_proc.returncode == 0, f"Generation failed: {gen_proc.stderr}\n{gen_proc.stdout}"

        # Verify check succeeds
        chk_cmd = [sys.executable, "scripts/generate_status_register.py", "--check", "--input", out_path, "--allow-dirty", "--allow-stale"]
        chk_proc = subprocess.run(chk_cmd, capture_output=True, text=True)
        assert chk_proc.returncode == 0, f"CLI check failed: {chk_proc.stderr}\n{chk_proc.stdout}"
        assert "[PASS]" in chk_proc.stdout

    def test_git_inspection_fail_closed_on_subprocess_error(self, monkeypatch):
        """WP2-R4: Git inspection must fail closed with git_valid=False and dirty=True on command failure."""
        def mock_check_output(cmd, *args, **kwargs):
            if "status" in cmd:
                raise subprocess.CalledProcessError(1, cmd, output="mock git status error")
            return "mock_output\n"

        monkeypatch.setattr(subprocess, "check_output", mock_check_output)
        
        # When fail_fast is False, should not crash but report git_valid=False and dirty=True
        info = get_git_info(fail_fast=False)
        assert info["git_valid"] is False
        assert info["dirty"] is True
        assert any("status" in err for err in info["git_errors"])

        # When fail_fast is True, must raise GitInspectionError
        with pytest.raises(GitInspectionError) as exc_info:
            get_git_info(fail_fast=True)
        assert "Git inspection failed closed" in str(exc_info.value)

    def test_traceability_fails_closed_on_invalid_live_git(self, monkeypatch):
        """Traceability verification must reject if live git inspection failed."""
        current_sha = "abc1234567890abcdef1234567890abcdef12345"
        mock_register = {
            "git": {"commit_sha": current_sha, "dirty": False, "git_valid": True},
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [],
        }

        def mock_get_git_info(*args, **kwargs):
            return {
                "commit_sha": "unknown",
                "branch": "unknown",
                "dirty": True,
                "dirty_entries": [],
                "git_valid": False,
                "git_errors": ["git command not found or broken repository"],
            }

        monkeypatch.setattr("gdec.verification.status_register.get_git_info", mock_get_git_info)
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(mock_register, allow_dirty=True, allow_stale=True)
        assert "Live repository Git inspection failed closed" in str(exc_info.value)

    def test_traceability_fails_closed_on_invalid_recorded_git(self):
        """Traceability verification must reject if status register recorded git_valid=False."""
        live_sha = get_git_info()["commit_sha"]
        mock_register = {
            "git": {"commit_sha": live_sha, "dirty": False, "git_valid": False, "git_errors": ["recorded git error"]},
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [],
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(mock_register, allow_dirty=True, allow_stale=True)
        assert "Status register indicates invalid git inspection state" in str(exc_info.value)

    def test_traceability_fails_closed_on_unknown_sha(self):
        """Traceability verification must fail closed when commit SHA is unknown unless allow_stale=True."""
        mock_register = {
            "git": {"commit_sha": "unknown", "dirty": False, "git_valid": True},
            "collection_errors": [],
            "pytest_exit_code": 0,
            "capabilities": [],
        }
        # Disallow stale -> must raise
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(mock_register, allow_dirty=True, allow_stale=False)
        assert "Cannot verify status register freshness: commit SHA is unknown" in str(exc_info.value)

    def test_unit_tests_cannot_grant_independently_validated(self, monkeypatch):
        """
        Policy (WP2-EIP): Automated unit/verification tests alone cannot grant INDEPENDENTLY VALIDATED.
        Even if all tests pass 100%, demonstrated status is capped at NUMERICALLY VERIFIED.
        Consequently, claimed_status='INDEPENDENTLY VALIDATED' fails traceability verification.
        """
        dummy_cap = CapabilityEntry(
            capability_id="test_cap_validation",
            name="Physical Validation Test Capability",
            subsystem="fem",
            claimed_status="INDEPENDENTLY VALIDATED",
            evidence_path="tests/test_dse.py",
            test_files=["tests/test_dse.py"],
            required_test_node_ids=["tests/test_dse.py::test_ok"],
            verification_criteria="Passes physical test criteria.",
            notes="Requires external experimental data.",
        )
        monkeypatch.setattr("gdec.verification.status_register.SYSTEM_CAPABILITIES", [dummy_cap])

        results = {"tests/test_dse.py::test_ok": "PASS"}
        reg = generate_status_register(run_tests=False, test_results=results, output_path="")
        
        cap_result = reg["capabilities"][0]
        assert cap_result["claimed_status"] == "INDEPENDENTLY VALIDATED"
        assert cap_result["demonstrated_status"] == "NUMERICALLY VERIFIED"
        assert cap_result["test_execution_state"] == "PASS"

        # Traceability must fail because claimed exceeds demonstrated
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(reg, allow_dirty=True, allow_stale=True)
        assert "claimed status 'INDEPENDENTLY VALIDATED' exceeds demonstrated status 'NUMERICALLY VERIFIED'" in str(exc_info.value)
