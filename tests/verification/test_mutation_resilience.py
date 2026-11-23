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
from scripts.run_mutation_campaign import (
    run_target_test,
    MutationExecutionCapture,
    ExecutionResult,
    validate_mutant_record,
)


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

        res = run_target_test(str(test_file), expected_failure_type="AssertionError")
        assert res.status == "KILLED"
        assert res.classification == "KILLED"
        assert "test_math_assertion" in (res.killer_test or "")
        assert res.exception_class == "AssertionError"
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

    def test_runner_unexpected_runtime_error_produces_error_not_killed(self, tmp_path):
        """An unexpected RuntimeError during test execution must be classified as ERROR (UNEXPECTED_EXCEPTION), never KILLED."""
        test_file = tmp_path / "test_runtime_crash.py"
        test_file.write_text(
            "def test_unexpected_crash():\n"
            "    raise RuntimeError('Unexpected matrix singularity during solve')\n",
            encoding="utf-8",
        )

        res = run_target_test(str(test_file), expected_failure_type="AssertionError")
        assert res.status == "ERROR"
        assert res.classification == "UNEXPECTED_EXCEPTION"
        assert res.status != "KILLED"
        assert res.failure_type == "RuntimeError"
        assert res.exception_class == "RuntimeError"
        assert "Unexpected exception during test execution (RuntimeError)" in res.diagnostic

    def test_runner_collection_error_produces_error(self, tmp_path):
        """A syntax error preventing pytest collection must be classified as ERROR."""
        test_file = tmp_path / "test_syntax_broken.py"
        test_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

        res = run_target_test(str(test_file))
        assert res.status == "ERROR"
        assert res.classification == "COLLECTION_ERROR"
        assert res.failure_type == "CollectionError"
        assert res.phase == "collection"

    def test_runner_setup_error_produces_error(self, tmp_path):
        """A fixture setup failure must be classified as ERROR (SETUP_ERROR), not KILLED."""
        test_file = tmp_path / "test_fixture_setup_broken.py"
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
        assert res.status != "KILLED"
        assert "Database connection failed during setup" in res.diagnostic

    def test_runner_teardown_error_produces_error(self, tmp_path):
        """A fixture teardown failure where call succeeded must be classified as ERROR (TEARDOWN_ERROR), not KILLED."""
        test_file = tmp_path / "test_fixture_teardown_broken.py"
        test_file.write_text(
            "import pytest\n"
            "@pytest.fixture\n"
            "def broken_teardown():\n"
            "    yield 'resource_ready'\n"
            "    raise RuntimeError('Controlled fixture teardown exception')\n"
            "def test_call_passes_teardown_fails(broken_teardown):\n"
            "    assert broken_teardown == 'resource_ready'\n",
            encoding="utf-8",
        )

        res = run_target_test(str(test_file))
        assert res.status == "ERROR"
        assert res.classification == "TEARDOWN_ERROR"
        assert res.phase == "teardown"
        assert res.exception_class == "RuntimeError"
        assert res.status != "KILLED"
        assert "Controlled fixture teardown exception" in res.diagnostic

    def test_runner_surviving_mutation_produces_survived(self, tmp_path):
        """A test that executes and passes despite mutation must be classified as SURVIVED."""
        test_file = tmp_path / "test_passes_clean.py"
        test_file.write_text("def test_clean_pass():\n    assert 2 + 2 == 4\n", encoding="utf-8")

        res = run_target_test(str(test_file))
        assert res.status == "SURVIVED"
        assert res.classification == "SURVIVED"
        assert res.exit_code == 0
        assert res.killer_test is None

    def test_runner_schema_validation_rejects_incomplete_record(self):
        """MutantRecord validation must reject records missing required fields or invalid classifications."""
        valid_rec = {
            "mutation_id": "MUT-TEST-01",
            "target_production_function": "module.func",
            "mutation_description": "Test description",
            "target_test_node_id": "tests/test.py::test_fn",
            "unmutated_baseline_result": "BASELINE_PASS",
            "mutation_injection_result": "SUCCESS",
            "pytest_execution_result": "FAILED",
            "captured_failure_phase": "call",
            "exception_class": "AssertionError",
            "exception_message": "assert 1 == 2",
            "final_classification": "KILLED",
            "classification_rationale": "Designated behavioral assertion failed",
        }
        # Must pass validation cleanly
        validate_mutant_record(valid_rec)

        # Reject missing required field
        bad_rec = dict(valid_rec)
        del bad_rec["target_production_function"]
        with pytest.raises(ValueError, match="Missing required mutant record field"):
            validate_mutant_record(bad_rec)

        # Reject invalid classification
        bad_rec2 = dict(valid_rec, final_classification="INVALID_STATUS")
        with pytest.raises(ValueError, match="Invalid classification"):
            validate_mutant_record(bad_rec2)

        # Reject KILLED without exception_class
        bad_rec3 = dict(valid_rec, exception_class="")
        with pytest.raises(ValueError, match="KILLED mutant must have non-empty exception_class"):
            validate_mutant_record(bad_rec3)


class TestBaselineValidation:
    """Verifies exact INVALID_BASELINE semantics across all failure modes."""

    def test_baseline_assertion_failure_produces_invalid_baseline(self, tmp_path):
        """Baseline with assertion failure must produce INVALID_BASELINE / BASELINE_ASSERTION_FAILURE."""
        test_file = tmp_path / "test_baseline_assert.py"
        test_file.write_text("def test_broken():\n    assert 1 == 2, 'Unmutated math error'\n", encoding="utf-8")
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "BASELINE_ASSERTION_FAILURE"
        assert res.phase == "call"
        assert res.exception_class == "AssertionError"
        assert "Unmutated math error" in res.diagnostic

    def test_baseline_unexpected_exception_produces_invalid_baseline(self, tmp_path):
        """Baseline with unexpected exception must produce INVALID_BASELINE / BASELINE_EXCEPTION."""
        test_file = tmp_path / "test_baseline_error.py"
        test_file.write_text("def test_broken():\n    raise RuntimeError('Baseline runtime crash')\n", encoding="utf-8")
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "BASELINE_EXCEPTION"
        assert res.phase == "call"
        assert res.exception_class == "RuntimeError"
        assert "Baseline runtime crash" in res.diagnostic

    def test_baseline_collection_failure_produces_invalid_baseline(self, tmp_path):
        """Baseline with syntax error must produce INVALID_BASELINE / COLLECTION_ERROR."""
        test_file = tmp_path / "test_baseline_syntax.py"
        test_file.write_text("def broken(:\n    pass\n", encoding="utf-8")
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "COLLECTION_ERROR"
        assert res.phase == "collection"

    def test_baseline_setup_failure_produces_invalid_baseline(self, tmp_path):
        """Baseline with setup fixture failure must produce INVALID_BASELINE / SETUP_ERROR."""
        test_file = tmp_path / "test_baseline_setup.py"
        test_file.write_text(
            "import pytest\n"
            "@pytest.fixture\n"
            "def bad_setup():\n"
            "    raise ValueError('Fixture setup failed')\n"
            "def test_foo(bad_setup):\n"
            "    pass\n",
            encoding="utf-8",
        )
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "SETUP_ERROR"
        assert res.phase == "setup"

    def test_baseline_teardown_failure_produces_invalid_baseline(self, tmp_path):
        """Baseline with teardown failure must produce INVALID_BASELINE / TEARDOWN_ERROR."""
        test_file = tmp_path / "test_baseline_teardown.py"
        test_file.write_text(
            "import pytest\n"
            "@pytest.fixture\n"
            "def bad_teardown():\n"
            "    yield 'ok'\n"
            "    raise RuntimeError('Fixture teardown cleanup failed')\n"
            "def test_foo(bad_teardown):\n"
            "    assert bad_teardown == 'ok'\n",
            encoding="utf-8",
        )
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "TEARDOWN_ERROR"
        assert res.phase == "teardown"

    def test_baseline_missing_target_test_produces_invalid_baseline(self):
        """Baseline targeting non-existent node must produce INVALID_BASELINE / NO_TESTS_COLLECTED."""
        res = run_target_test("tests/non_existent_file.py::test_missing", is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.classification == "NO_TESTS_COLLECTED"
        assert res.phase == "collection"

    def test_failed_unmutated_baseline_aborts_campaign(self, tmp_path):
        """A failing unmutated baseline must be detected and fail validation."""
        test_file = tmp_path / "test_baseline_broken.py"
        test_file.write_text("def test_broken_baseline():\n    assert False, 'Pre-existing failure'\n", encoding="utf-8")
        res = run_target_test(str(test_file), is_baseline=True)
        assert res.status == "INVALID_BASELINE"
        assert res.exit_code != 0
