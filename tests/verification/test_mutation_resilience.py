"""
Targeted mutation testing and resilience verification for GDEC.
Verifies that 100% of injected production mutants are detected and killed by the test suite.
"""
from __future__ import annotations

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
