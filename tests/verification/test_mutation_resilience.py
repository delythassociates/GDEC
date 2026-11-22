"""
Targeted mutation testing and resilience verification for GDEC.
Verifies that 100% of injected mathematical mutants are detected and killed.
"""
from __future__ import annotations

import pytest
from gdec.verification.mutation_harness import (
    execute_mutation_suite,
    run_mutation_trial_shear_sign_flip,
    run_mutation_trial_poisson_zero,
    run_mutation_trial_omit_facet_jumps,
    run_mutation_trial_zero_dorfler_fraction,
    run_mutation_trial_stiffness_asymmetry,
    run_mutation_trial_invert_adjoint_load,
    plane_stress_matrix,
)


class TestMutationResilience:
    """Verifies that automated test assertions kill mathematical mutants in FEM logic."""

    def test_full_mutation_suite_100_percent_kill_rate(self):
        """Gate 3: All 6 injected mathematical mutants must be detected and killed."""
        results = execute_mutation_suite()
        assert len(results) == 6

        detected_count = sum(1 for r in results if r.detected)
        kill_rate = detected_count / len(results)

        # Print detection log for CI traceability
        for r in results:
            status = "KILLED" if r.detected else "SURVIVED"
            print(f"[{status}] {r.mutant_id}: {r.description} -> {r.detection_reason}")

        assert kill_rate == 1.0, f"Mutation kill rate {kill_rate:.1%} < 100.0%. Surviving mutants: {[r.mutant_id for r in results if not r.detected]}"

    def test_mutant_1_shear_modulus_sign_flip(self):
        """Mutant 1: G -> -G violates positive definiteness."""
        result = run_mutation_trial_shear_sign_flip()
        assert result.detected is True
        assert "MUTANT-1" in result.mutant_id
        assert len(result.detection_reason) > 0

    def test_mutant_2_poisson_ratio_zeroing(self):
        """Mutant 2: nu = 0 eliminates transverse Poisson contraction."""
        result = run_mutation_trial_poisson_zero()
        assert result.detected is True
        assert "MUTANT-2" in result.mutant_id

    def test_mutant_3_omit_interior_facet_jumps(self):
        """Mutant 3: Omitting facet jumps collapses DWR error indicator."""
        result = run_mutation_trial_omit_facet_jumps()
        assert result.detected is True
        assert "MUTANT-3" in result.mutant_id

    def test_mutant_4_zero_dorfler_fraction(self):
        """Mutant 4: theta = 0 marks no elements, halting AMR."""
        result = run_mutation_trial_zero_dorfler_fraction()
        assert result.detected is True
        assert "MUTANT-4" in result.mutant_id

    def test_mutant_5_stiffness_matrix_asymmetry(self):
        """Mutant 5: Asymmetric perturbation is detected by matrix symmetry check."""
        result = run_mutation_trial_stiffness_asymmetry()
        assert result.detected is True
        assert "MUTANT-5" in result.mutant_id

    def test_mutant_6_invert_adjoint_load_sign(self):
        """Mutant 6: Inverting adjoint load flips sensitivity sign."""
        result = run_mutation_trial_invert_adjoint_load()
        assert result.detected is True
        assert "MUTANT-6" in result.mutant_id
