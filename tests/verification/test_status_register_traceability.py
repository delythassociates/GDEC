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
        """Verify status register generates valid JSON matching schema specification."""
        out_file = str(tmp_path / "status_register.json")
        data = generate_status_register(output_path=out_file)

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
        data = generate_status_register(output_path=out_file)
        # Should not raise
        verify_traceability(data)

    def test_traceability_enforcement_fails_on_unverified_capability(self):
        """Gate 2: Any NUMERICALLY VERIFIED capability with FAIL or missing tests must fail."""
        # Simulated register with a failed test for a numerically verified capability
        bad_register = {
            "capabilities": [
                {
                    "capability_id": "fake_broken_capability",
                    "name": "Broken Mechanical Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "test_files_exist": True,
                    "test_execution_state": "FAIL",
                    "test_files": ["tests/fake_test.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(bad_register)
        assert "Broken Mechanical Solver" in str(exc_info.value)
        assert "expected 'PASS'" in str(exc_info.value)

    def test_traceability_enforcement_fails_on_missing_test_files(self):
        """Gate 2: Any NUMERICALLY VERIFIED capability with missing test files must fail."""
        bad_register = {
            "capabilities": [
                {
                    "capability_id": "fake_missing_files",
                    "name": "Missing Test Solver",
                    "claimed_status": "NUMERICALLY VERIFIED",
                    "test_files_exist": False,
                    "test_execution_state": "PASS",
                    "test_files": ["tests/non_existent_file_99999.py"],
                }
            ]
        }
        with pytest.raises(TraceabilityVerificationError) as exc_info:
            verify_traceability(bad_register)
        assert "missing" in str(exc_info.value)

    def test_cli_script_generates_and_checks(self):
        """Verify scripts/generate_status_register.py runs cleanly via CLI."""
        cmd = [sys.executable, "scripts/generate_status_register.py", "--check"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, f"CLI check failed: {proc.stderr}\n{proc.stdout}"
        assert "[PASS]" in proc.stdout
