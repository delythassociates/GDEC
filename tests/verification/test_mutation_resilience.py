"""
Targeted mutation testing and resilience verification for GDEC.
Verifies that 100% of injected production mutants are detected and killed by the test suite,
and verifies strict classification of test execution states in the mutation runner.
"""
from __future__ import annotations

import os
import sys
import pytest

from gdec.verification.mutation_harness import (
    execute_mutation_suite,
    run_mutation_trial_1_stiffness_constitutive,
    run_mutation_trial_2_symmetry_defect,
    run_mutation_trial_3_analytical_scaling,
    run_mutation_trial_4_amr_marking,
    run_mutation_trial_5_eir_type_dimension,
    run_mutation_trial_6_dse_decision_logic,
)

# Import runner components from scripts/run_mutation_campaign.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from scripts.run_mutation_campaign import run_target_test, MutationExecutionCapture, ExecutionResult


class TestMutationResilience:
    """Verifies that automated test assertions kill mathematical mutants in FEM logic."""

    def test_full_mutation_suite_100_percent_kill_rate(self):
        """Gate 3: All 6 injected production mutants must be detected and killed."""
        results = execute_mutation_suite()
        assert len(results) == 6

        killed_count = sum(1 for r in results if r.killed)
        kill_rate = killed_count / len(results)

        for r in results:
            status = "KILLED" if r.killed else "SURVIVED"
            print(f"[{status}] {r.mutant_id}: {r.target_function} -> killed by {r.killer_test}")
            assert r.unmutated_passed, f"{r.mutant_id}: unmutated test failed!"

        assert kill_rate == 1.0, f"Mutation kill rate {kill_rate:.1%} < 100.0%. Surviving mutants: {[r.mutant_id for r in results if not r.killed]}"

    def test_mutant_1_stiffness_constitutive(self):
        """Mutant 1: Doubling E breaks analytical Timoshenko tip deflection match."""
        res = run_mutation_trial_1_stiffness_constitutive()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_cantilever_beam_timoshenko_analytical_comparison" in res.killer_test

    def test_mutant_2_symmetry_defect(self):
        """Mutant 2: Bypassing symmetry check fails perturbed matrix test."""
        res = run_mutation_trial_2_symmetry_defect()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_symmetry_defect_exact_and_perturbed" in res.killer_test

    def test_mutant_3_analytical_scaling(self):
        """Mutant 3: Mutating scaling law fails independent FEM Monte Carlo comparison."""
        res = run_mutation_trial_3_analytical_scaling()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_independent_fem_scaling_agreement" in res.killer_test

    def test_mutant_4_amr_marking(self):
        """Mutant 4: Zeroing marked elements halts AMR error reduction."""
        res = run_mutation_trial_4_amr_marking()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_dwr_adaptive_refinement_reduces_qoi_error" in res.killer_test

    def test_mutant_5_eir_type_dimension(self):
        """Mutant 5: Bypassing dimension check fails DimensionError assertion."""
        res = run_mutation_trial_5_eir_type_dimension()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_addition_requires_equal_dimensions" in res.killer_test

    def test_mutant_6_dse_decision_logic(self):
        """Mutant 6: Inverting decision recommendation fails exact loss evaluation."""
        res = run_mutation_trial_6_dse_decision_logic()
        assert res.unmutated_passed is True
        assert res.killed is True
        assert "test_evaluator_known_gaussian_calculation" in res.killer_test


class TestMutationRunnerClassification:
    """Verifies strict classification of execution states in scripts/run_mutation_campaign.py."""

    def test_runner_genuine_assertion_failure_produces_killed(self, tmp_path):
        """A genuine intended assertion failure must be classified as KILLED."""
        test_file = tmp_path / "test_assertion_fail.py"
        test_file.write_text("def test_math_assertion():\n    assert 1.0 == 2.0\n", encoding="utf-8")

        res = run_target_test(str(test_file))
        assert res.status == "KILLED"
        assert res.classification == "KILLED"
        assert "test_math_assertion" in (res.killer_test or "")
        assert "assert 1.0 == 2.0" in res.diagnostic

    def test_runner_injection_attribute_error_produces_invalid_mutant(self, tmp_path):
        """An invalid mutation injection raising AttributeError must be classified as INVALID_MUTANT, never KILLED."""
        test_file = tmp_path / "test_attr_error.py"
        test_file.write_text(
            "def test_attribute_injection():\n"
            "    # Simulates: 'RestrictedLinearElasticScaling' object has no attribute 'reference'\n"
            "    raise AttributeError(\"'RestrictedLinearElasticScaling' object has no attribute 'reference'\")\n",
            encoding="utf-8",
        )

        res = run_target_test(str(test_file))
        assert res.status == "INVALID_MUTANT"
        assert res.classification == "INVALID_INJECTION"
        assert res.failure_type == "AttributeError"
        assert "Invalid mutant injection (AttributeError)" in res.diagnostic
        assert res.status != "KILLED"

    def test_runner_collection_error_produces_error(self, tmp_path):
        """A syntax error preventing pytest collection must be classified as ERROR."""
        test_file = tmp_path / "test_syntax_broken.py"
        test_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

        res = run_target_test(str(test_file))
        assert res.status == "ERROR"
        assert res.classification == "COLLECTION_ERROR"
        assert res.failure_type == "CollectionError"
        assert res.phase == "collection"

    def test_runner_setup_teardown_error_produces_error(self, tmp_path):
        """A fixture setup failure must be classified as ERROR, not KILLED."""
        test_file = tmp_path / "test_fixture_broken.py"
        test_file.write_text(
            "import pytest\n"
            "@pytest.fixture\n"
            "def broken_setup():\n"
            "    raise RuntimeError('Database connection failed during setup')\n"
            "def test_with_fixture(broken_setup):\n"
            "    pass\n",
            encoding="utf-8",
        )

        res = run_target_test(str(test_file))
        assert res.status == "ERROR"
        assert res.classification == "SETUP_ERROR"
        assert res.failure_type == "SetupError"
        assert res.phase == "setup"
        assert "Database connection failed during setup" in res.diagnostic

    def test_runner_surviving_mutation_produces_survived(self, tmp_path):
        """A test that executes and passes despite mutation must be classified as SURVIVED."""
        test_file = tmp_path / "test_passes_clean.py"
        test_file.write_text("def test_clean_pass():\n    assert 2 + 2 == 4\n", encoding="utf-8")

        res = run_target_test(str(test_file))
        assert res.status == "SURVIVED"
        assert res.classification == "SURVIVED"
        assert res.exit_code == 0
        assert res.killer_test is None

    def test_failed_unmutated_baseline_aborts_campaign(self, tmp_path):
        """A failing unmutated baseline must be detected and fail validation."""
        test_file = tmp_path / "test_baseline_broken.py"
        test_file.write_text("def test_broken_baseline():\n    assert False, 'Pre-existing failure'\n", encoding="utf-8")

        res = run_target_test(str(test_file), is_baseline=True)
        # In baseline mode, any non-zero exit code indicates broken baseline
        assert res.status != "SURVIVED"
        assert res.exit_code != 0
