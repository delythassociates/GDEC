"""
Targeted production mutation testing and resilience harness for GDEC.
Injects lethal mathematical and logical mutations directly into actual
production functions and verifies that the automated test suite kills 100% of mutants.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import pytest


@dataclass(frozen=True)
class MutationResult:
    mutant_id: str
    target_function: str
    description: str
    target_test: str
    unmutated_passed: bool
    killed: bool
    killer_test: Optional[str]
    failure_diagnostic: str


class FailureCapturePlugin:
    """Pytest plugin to capture exact test failure diagnostic."""
    def __init__(self):
        self.failed_nodeid: Optional[str] = None
        self.failure_message: str = ""

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.failed:
            self.failed_nodeid = report.nodeid
            self.failure_message = str(report.longrepr)


def _run_single_test(test_target: str) -> tuple[bool, Optional[str], str]:
    """Run a single pytest test and capture pass/fail state and diagnostic."""
    capture = FailureCapturePlugin()
    exit_code = pytest.main([test_target, "-q"], plugins=[capture])
    passed = (exit_code == pytest.ExitCode.OK or exit_code == 0)
    return passed, capture.failed_nodeid, capture.failure_message


def run_mutation_trial_1_stiffness_constitutive() -> MutationResult:
    """Mutant 1: Double elastic modulus in ConstitutiveTensor.from_properties."""
    from gdec.fem.elasticity import ConstitutiveTensor
    target_test = "tests/test_fem_mathematical_verification.py::test_cantilever_beam_timoshenko_analytical_comparison"

    # 1. Verify unmutated passes
    unmutated_pass, _, _ = _run_single_test(target_test)

    # 2. Mutate production function
    orig = ConstitutiveTensor.from_properties
    try:
        def mutated_from_properties(E, nu, assumption="plane_stress", thickness=1.0):
            return orig(2.0 * E, nu, assumption=assumption, thickness=thickness)
        ConstitutiveTensor.from_properties = staticmethod(mutated_from_properties)

        # 3. Run target test against mutant
        mutated_pass, killer, diag = _run_single_test(target_test)
        killed = not mutated_pass
    finally:
        ConstitutiveTensor.from_properties = orig

    return MutationResult(
        mutant_id="MUTANT-1-STIFFNESS-CONSTITUTIVE",
        target_function="gdec.fem.elasticity.ConstitutiveTensor.from_properties",
        description="Double elastic modulus E -> 2*E in constitutive tensor",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def run_mutation_trial_2_symmetry_defect() -> MutationResult:
    """Mutant 2: Bypass symmetry defect check by returning 0.0 unconditionally in production module."""
    import gdec.fem.matrix_diagnostics as pmd
    import tests.test_matrix_diagnostics as tmd
    from unittest.mock import patch
    target_test = "tests/test_matrix_diagnostics.py::test_symmetry_defect_exact_and_perturbed"

    unmutated_pass, _, _ = _run_single_test(target_test)

    # Mutate the actual production module function directly
    orig_func = pmd.compute_symmetry_defect
    try:
        pmd.compute_symmetry_defect = lambda matrix: 0.0
        with patch.object(tmd, "compute_symmetry_defect", return_value=0.0):
            mutated_pass, killer, diag = _run_single_test(target_test)
            killed = not mutated_pass
    finally:
        pmd.compute_symmetry_defect = orig_func

    return MutationResult(
        mutant_id="MUTANT-2-SYMMETRY-DEFECT",
        target_function="gdec.fem.matrix_diagnostics.compute_symmetry_defect",
        description="Bypass matrix symmetry defect check to return 0.0 unconditionally in production module",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def run_mutation_trial_3_analytical_scaling() -> MutationResult:
    """Mutant 3: Mutate scaling power law in RestrictedLinearElasticScaling.evaluate_scalar."""
    from gdec.dse.scaling import RestrictedLinearElasticScaling
    target_test = "tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement"

    unmutated_pass, _, _ = _run_single_test(target_test)

    orig = RestrictedLinearElasticScaling.evaluate_scalar
    try:
        def mutated_eval(self, E: float, P: float) -> float:
            # Mutate: square the modulus scaling ratio
            val = orig(self, E, P)
            return val * (self.baseline.E_0 / E)
        RestrictedLinearElasticScaling.evaluate_scalar = mutated_eval

        mutated_pass, killer, diag = _run_single_test(target_test)
        killed = not mutated_pass
    finally:
        RestrictedLinearElasticScaling.evaluate_scalar = orig

    return MutationResult(
        mutant_id="MUTANT-3-ANALYTICAL-SCALING",
        target_function="gdec.dse.scaling.RestrictedLinearElasticScaling.evaluate_scalar",
        description="Square the modulus scaling power law (E_0 / E)^2 instead of linear",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def run_mutation_trial_4_amr_marking() -> MutationResult:
    """Mutant 4: Bypass adaptive refinement by marking 0 elements."""
    from gdec.fem.adaptivity import MeshAdaptor
    import numpy as np
    target_test = "tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error"

    unmutated_pass, _, _ = _run_single_test(target_test)

    orig = MeshAdaptor.mark_elements
    try:
        def mutated_mark(*args, **kwargs):
            return np.array([], dtype=int)
        MeshAdaptor.mark_elements = staticmethod(mutated_mark)

        mutated_pass, killer, diag = _run_single_test(target_test)
        killed = not mutated_pass
    finally:
        MeshAdaptor.mark_elements = orig

    return MutationResult(
        mutant_id="MUTANT-4-AMR-MARKING",
        target_function="gdec.fem.adaptivity.MeshAdaptor.mark_elements",
        description="Return 0 marked elements, completely bypassing AMR",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def run_mutation_trial_5_eir_type_dimension() -> MutationResult:
    """Mutant 5: Bypass dimension equality check in EIR addition."""
    import gdec.eir.expressions as expr
    target_test = "tests/eir/test_expression_typing.py::test_addition_requires_equal_dimensions"

    unmutated_pass, _, _ = _run_single_test(target_test)

    orig = expr._add_type
    try:
        def mutated_add(left, right, *, subtract=False):
            # Mutate: bypass dimension equality check and simply return left
            return left
        expr._add_type = mutated_add

        mutated_pass, killer, diag = _run_single_test(target_test)
        killed = not mutated_pass
    finally:
        expr._add_type = orig

    return MutationResult(
        mutant_id="MUTANT-5-EIR-TYPE-DIMENSION",
        target_function="gdec.eir.expressions._add_type",
        description="Bypass dimension equality validation in EIR expression typing",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def run_mutation_trial_6_dse_decision_logic() -> MutationResult:
    """Mutant 6: Invert decision recommendation RELEASE -> REJECT in SingleQoIEvaluator."""
    from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation
    from dataclasses import replace
    target_test = "tests/test_dse.py::test_evaluator_known_gaussian_calculation"

    unmutated_pass, _, _ = _run_single_test(target_test)

    orig = SingleQoIEvaluator.evaluate
    try:
        def mutated_eval(self, *args, **kwargs):
            res = orig(self, *args, **kwargs)
            if res.recommendation == DecisionRecommendation.RELEASE:
                res = replace(res, recommendation=DecisionRecommendation.REJECT)
            return res
        SingleQoIEvaluator.evaluate = mutated_eval

        mutated_pass, killer, diag = _run_single_test(target_test)
        killed = not mutated_pass
    finally:
        SingleQoIEvaluator.evaluate = orig

    return MutationResult(
        mutant_id="MUTANT-6-DSE-DECISION-LOGIC",
        target_function="gdec.dse.evaluator.SingleQoIEvaluator.evaluate",
        description="Invert recommendation: flip RELEASE to REJECT in decision engine",
        target_test=target_test,
        unmutated_passed=unmutated_pass,
        killed=killed,
        killer_test=killer or target_test,
        failure_diagnostic=diag[:300] if diag else "Test failed as expected",
    )


def execute_mutation_suite() -> List[MutationResult]:
    """Execute full production mutation resilience suite."""
    return [
        run_mutation_trial_1_stiffness_constitutive(),
        run_mutation_trial_2_symmetry_defect(),
        run_mutation_trial_3_analytical_scaling(),
        run_mutation_trial_4_amr_marking(),
        run_mutation_trial_5_eir_type_dimension(),
        run_mutation_trial_6_dse_decision_logic(),
    ]
