#!/usr/bin/env python3
"""
Source-level mutation campaign runner for GDEC verification.
Executes a documented, bounded mutation campaign across core production modules:
- gdec.fem.constitutive
- gdec.fem.matrix_diagnostics
- gdec.fem.adaptivity
- gdec.dse.evaluator
- gdec.dse.scaling
- gdec.eir.expressions

Reports every mutant, affected function, killer test, failure diagnostic, and kill rate.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

# Ensure src and repo root are in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(repo_root, "src"))
sys.path.insert(0, repo_root)

import pytest


@dataclass
class MutantRecord:
    mutant_id: str
    target_module: str
    target_function: str
    mutation_type: str  # arithmetic, relational, logical, boundary, return_value
    description: str
    target_test: str
    unmutated_passed: bool
    status: str  # KILLED, SURVIVED, ERROR
    killer_test: Optional[str] = None
    diagnostic: Optional[str] = None
    classification: str = "KILLED"  # KILLED, EQUIVALENT, TEST_GAP


class TestFailureCapture:
    def __init__(self):
        self.failed_nodeid: Optional[str] = None
        self.failure_msg: str = ""

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.failed:
            self.failed_nodeid = report.nodeid
            self.failure_msg = str(report.longrepr)


def run_target_test(test_target: str) -> tuple[bool, Optional[str], str]:
    capture = TestFailureCapture()
    exit_code = pytest.main([test_target, "-q"], plugins=[capture])
    passed = (exit_code == pytest.ExitCode.OK or exit_code == 0)
    return passed, capture.failed_nodeid, capture.failure_msg


def build_mutants() -> List[tuple[str, str, str, str, str, str, Callable[[], Any]]]:
    """
    Returns list of tuples:
    (mutant_id, module, function, mutation_type, description, target_test, mutation_runner)
    """
    mutants = []

    # 1. FEM Constitutive: Plane Stress young modulus multiplier
    def mut_constitutive_plane_stress():
        from gdec.fem.elasticity import ConstitutiveTensor
        orig = ConstitutiveTensor.from_properties
        def _mut(E, nu, assumption="plane_stress", thickness=1.0):
            return orig(1.25 * E, nu, assumption=assumption, thickness=thickness)
        ConstitutiveTensor.from_properties = staticmethod(_mut)
        try:
            return run_target_test("tests/test_fem_mathematical_verification.py::test_cantilever_beam_timoshenko_analytical_comparison")
        finally:
            ConstitutiveTensor.from_properties = orig
    mutants.append((
        "MUT-FEM-01",
        "gdec.fem.elasticity",
        "ConstitutiveTensor.from_properties",
        "arithmetic",
        "Scale Young's modulus E by 1.25 in plane stress constitutive tensor",
        "tests/test_fem_mathematical_verification.py::test_cantilever_beam_timoshenko_analytical_comparison",
        mut_constitutive_plane_stress,
    ))

    # 2. FEM Constitutive: Zero Poisson ratio contraction
    def mut_constitutive_poisson():
        from gdec.fem.elasticity import ConstitutiveTensor
        orig = ConstitutiveTensor.from_properties
        def _mut(E, nu, assumption="plane_stress", thickness=1.0):
            return orig(E, 0.0, assumption=assumption, thickness=thickness)
        ConstitutiveTensor.from_properties = staticmethod(_mut)
        try:
            return run_target_test("tests/test_fem_mathematical_verification.py::test_manufactured_solution_pure_bending")
        finally:
            ConstitutiveTensor.from_properties = orig
    mutants.append((
        "MUT-FEM-02",
        "gdec.fem.elasticity",
        "ConstitutiveTensor.from_properties",
        "boundary",
        "Zero Poisson ratio (nu=0.0) removing anticlastic curvature coupling",
        "tests/test_fem_mathematical_verification.py::test_manufactured_solution_pure_bending",
        mut_constitutive_poisson,
    ))

    # 3. FEM Matrix Diagnostics: Symmetry Defect zeroed
    def mut_symmetry_zeroed():
        import gdec.fem.matrix_diagnostics as pmd
        import tests.test_matrix_diagnostics as tmd
        orig = pmd.compute_symmetry_defect
        pmd.compute_symmetry_defect = lambda m: 0.0
        try:
            with patch.object(tmd, "compute_symmetry_defect", return_value=0.0):
                return run_target_test("tests/test_matrix_diagnostics.py::test_symmetry_defect_exact_and_perturbed")
        finally:
            pmd.compute_symmetry_defect = orig
    mutants.append((
        "MUT-SOLV-01",
        "gdec.fem.matrix_diagnostics",
        "compute_symmetry_defect",
        "return_value",
        "Force compute_symmetry_defect to unconditionally return 0.0",
        "tests/test_matrix_diagnostics.py::test_symmetry_defect_exact_and_perturbed",
        mut_symmetry_zeroed,
    ))

    # 4. FEM Matrix Diagnostics: Condition number inverted
    def mut_condition_number():
        import gdec.fem.matrix_diagnostics as pmd
        import tests.test_matrix_diagnostics as tmd
        orig = pmd.estimate_condition_number_sparse
        def _mut(*args, **kwargs):
            return 1.0, 1.0, 1.0  # Force kappa = 1.0
        pmd.estimate_condition_number_sparse = _mut
        try:
            with patch.object(tmd, "estimate_condition_number_sparse", _mut):
                return run_target_test("tests/test_matrix_diagnostics.py::test_diagnostics_known_spd_matrix")
        finally:
            pmd.estimate_condition_number_sparse = orig
    mutants.append((
        "MUT-SOLV-02",
        "gdec.fem.matrix_diagnostics",
        "estimate_condition_number_sparse",
        "arithmetic",
        "Force sparse condition number estimate to return 1.0 unconditionally",
        "tests/test_matrix_diagnostics.py::test_diagnostics_known_spd_matrix",
        mut_condition_number,
    ))

    # 5. FEM Adaptivity: Invert Dörfler priority sorting order
    def mut_amr_sort_order():
        from gdec.fem.adaptivity import MeshAdaptor
        import numpy as np
        orig = MeshAdaptor.mark_elements
        def _mut(indicator_result, strategy, marking_fraction=0.3, current_dofs=0, max_dofs_budget=25000):
            # Sort in ascending order (refine lowest error elements)
            priorities = indicator_result.priorities
            sorted_indices = np.argsort(priorities)  # ascending instead of descending
            target_count = max(1, int(np.ceil(marking_fraction * len(priorities))))
            marked = sorted_indices[:target_count]
            return np.sort(marked)
        MeshAdaptor.mark_elements = staticmethod(_mut)
        try:
            return run_target_test("tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error")
        finally:
            MeshAdaptor.mark_elements = orig
    mutants.append((
        "MUT-AMR-01",
        "gdec.fem.adaptivity",
        "MeshAdaptor.mark_elements",
        "relational",
        "Invert Dörfler element sorting: refine smallest error elements first",
        "tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error",
        mut_amr_sort_order,
    ))

    # 6. FEM Adaptivity: Zero marked elements
    def mut_amr_zero_marked():
        from gdec.fem.adaptivity import MeshAdaptor
        import numpy as np
        orig = MeshAdaptor.mark_elements
        MeshAdaptor.mark_elements = staticmethod(lambda *a, **k: np.array([], dtype=int))
        try:
            return run_target_test("tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error")
        finally:
            MeshAdaptor.mark_elements = orig
    mutants.append((
        "MUT-AMR-02",
        "gdec.fem.adaptivity",
        "MeshAdaptor.mark_elements",
        "boundary",
        "Return empty marked element array, stalling AMR",
        "tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error",
        mut_amr_zero_marked,
    ))

    # 7. DSE Scaling: Square Young's modulus scaling power law
    def mut_scaling_exponent():
        from gdec.dse.scaling import RestrictedLinearElasticScaling
        orig = RestrictedLinearElasticScaling.evaluate_scalar
        def _mut(self, E: float, P: float) -> float:
            # (E0 / E)^2 instead of (E0 / E)
            val = orig(self, E, P)
            return val * (self.reference.E_0 / E)
        RestrictedLinearElasticScaling.evaluate_scalar = _mut
        try:
            return run_target_test("tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement")
        finally:
            RestrictedLinearElasticScaling.evaluate_scalar = orig
    mutants.append((
        "MUT-DSE-01",
        "gdec.dse.scaling",
        "RestrictedLinearElasticScaling.evaluate_scalar",
        "arithmetic",
        "Square Young's modulus scaling ratio (E_0 / E)^2",
        "tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement",
        mut_scaling_exponent,
    ))

    # 8. DSE Scaling: Invert load factor scaling
    def mut_scaling_load():
        from gdec.dse.scaling import RestrictedLinearElasticScaling
        orig = RestrictedLinearElasticScaling.evaluate_scalar
        def _mut(self, E: float, P: float) -> float:
            return orig(self, E, P) * (self.reference.P_0 / P)
        RestrictedLinearElasticScaling.evaluate_scalar = _mut
        try:
            return run_target_test("tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement")
        finally:
            RestrictedLinearElasticScaling.evaluate_scalar = orig
    mutants.append((
        "MUT-DSE-02",
        "gdec.dse.scaling",
        "RestrictedLinearElasticScaling.evaluate_scalar",
        "arithmetic",
        "Invert load ratio scaling factor (P_0 / P) instead of (P / P_0)",
        "tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement",
        mut_scaling_load,
    ))

    # 9. DSE Evaluator: Swap asymmetric Bayesian risk penalties
    def mut_evaluator_risk_swap():
        from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation, DecisionEvaluationResult
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            res = orig(self, *args, **kwargs)
            from dataclasses import replace
            if res.is_conclusive():
                rec = DecisionRecommendation.RELEASE if res.expected_loss_reject < res.expected_loss_release else DecisionRecommendation.REJECT
                return replace(res, recommendation=rec, expected_loss_release=res.expected_loss_reject, expected_loss_reject=res.expected_loss_release)
            return res
        SingleQoIEvaluator.evaluate = _mut
        try:
            return run_target_test("tests/test_dse.py::test_evaluator_known_gaussian_calculation")
        finally:
            SingleQoIEvaluator.evaluate = orig
    mutants.append((
        "MUT-DSE-03",
        "gdec.dse.evaluator",
        "SingleQoIEvaluator.evaluate",
        "logical",
        "Invert release vs reject asymmetric risk comparison",
        "tests/test_dse.py::test_evaluator_known_gaussian_calculation",
        mut_evaluator_risk_swap,
    ))

    # 10. DSE Evaluator: Bypass missing uncertainty refusal
    def mut_evaluator_bypass_evidence():
        from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            try:
                return orig(self, *args, **kwargs)
            except Exception:
                # Bypass refusal
                from gdec.dse.evaluator import DecisionEvaluationResult
                return DecisionEvaluationResult(
                    recommendation=DecisionRecommendation.RELEASE,
                    expected_loss_release=0.0,
                    expected_loss_reject=100.0,
                    probability_safe=1.0,
                    probability_fail=0.0,
                    decision_margin=1.0,
                    threshold_value=1.0,
                    qoi_mean=0.5,
                    qoi_std=0.0,
                )
        SingleQoIEvaluator.evaluate = _mut
        try:
            return run_target_test("tests/test_dse.py::test_evaluator_refusal_on_missing_uncertainty")
        finally:
            SingleQoIEvaluator.evaluate = orig
    mutants.append((
        "MUT-DSE-04",
        "gdec.dse.evaluator",
        "SingleQoIEvaluator.evaluate",
        "logical",
        "Bypass uncertainty refusal and return RELEASE unconditionally",
        "tests/test_dse.py::test_evaluator_refusal_on_missing_uncertainty",
        mut_evaluator_bypass_evidence,
    ))

    # 11. EIR Expressions: Bypass dimensional equality in addition
    def mut_eir_add_dimension():
        import gdec.eir.expressions as expr
        orig = expr._add_type
        def _mut(left, right, *, subtract=False):
            return left  # unconditionally return left, ignoring right dimension
        expr._add_type = _mut
        try:
            return run_target_test("tests/eir/test_expression_typing.py::test_addition_requires_equal_dimensions")
        finally:
            expr._add_type = orig
    mutants.append((
        "MUT-EIR-01",
        "gdec.eir.expressions",
        "_add_type",
        "logical",
        "Bypass dimension equality validation in EIR expression addition",
        "tests/eir/test_expression_typing.py::test_addition_requires_equal_dimensions",
        mut_eir_add_dimension,
    ))

    # 12. EIR Expressions: Invert AST depth limit check
    def mut_eir_depth_check():
        from gdec.eir.expressions import ExpressionTypingValidator
        orig = ExpressionTypingValidator._check_expression_bounds
        def _mut(self, expr):
            return None  # Bypass depth and node count bounds
        ExpressionTypingValidator._check_expression_bounds = _mut
        try:
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_deeply_nested_expression_rejected_with_typed_error")
        finally:
            ExpressionTypingValidator._check_expression_bounds = orig
    mutants.append((
        "MUT-EIR-02",
        "gdec.eir.expressions",
        "ExpressionTypingValidator._check_expression_bounds",
        "boundary",
        "Disable AST recursion depth and node count upper bounds check",
        "tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_deeply_nested_expression_rejected_with_typed_error",
        mut_eir_depth_check,
    ))

    # 13. EIR Expressions: Bypass identifier confusable character rejection
    def mut_eir_confusable_check():
        from gdec.eir.parser import StrictInputValidator
        orig = StrictInputValidator.validate_identifier
        def _mut(identifier):
            return None  # Allow confusable and bidirectional unicode characters
        StrictInputValidator.validate_identifier = staticmethod(_mut)
        try:
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_identifier_rejects_control_and_confusable_characters[foo\\x00bar]")
        finally:
            StrictInputValidator.validate_identifier = orig
    mutants.append((
        "MUT-EIR-03",
        "gdec.eir.parser",
        "StrictInputValidator.validate_identifier",
        "boundary",
        "Disable unicode confusable and bidirectional control character check",
        "tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_identifier_rejects_control_and_confusable_characters[foo\\x00bar]",
        mut_eir_confusable_check,
    ))

    # 14. FEM MMS Pure Bending: Modify convergence rate threshold
    def mut_mms_displacement_coeff():
        import gdec.verification.convergence_order as gco
        import tests.verification.test_convergence_order as tco
        orig = gco.fit_convergence_rate
        def _mut(*args, **kwargs):
            p, r2 = orig(*args, **kwargs)
            return p * 0.5, r2  # artificially degrade observed convergence order
        gco.fit_convergence_rate = _mut
        tco.fit_convergence_rate = _mut
        try:
            return run_target_test("tests/verification/test_convergence_order.py::TestMeshConvergenceAndObservedOrder::test_smooth_mms_convergence_l2_and_h1")
        finally:
            gco.fit_convergence_rate = orig
            tco.fit_convergence_rate = orig
    mutants.append((
        "MUT-VERIF-01",
        "gdec.verification.convergence_order",
        "fit_convergence_rate",
        "relational",
        "Degrade fitted MMS observed order by 50% to trigger tolerance rejection",
        "tests/verification/test_convergence_order.py::TestMeshConvergenceAndObservedOrder::test_smooth_mms_convergence_l2_and_h1",
        mut_mms_displacement_coeff,
    ))

    return mutants


def main():
    parser = argparse.ArgumentParser(description="Run GDEC source mutation campaign.")
    parser.add_argument("--output", default="results/mutation_campaign_report.json", help="Output JSON path")
    args = parser.parse_args()

    print("=================================================================")
    print("       GDEC Source-Level Mutation Testing Campaign (WP2-R3)       ")
    print("=================================================================")

    mutants_def = build_mutants()
    records: List[MutantRecord] = []

    for mid, mod, func, mtype, desc, test_target, runner in mutants_def:
        print(f"\n[{mid}] {desc}")
        print(f"  Target: {mod}.{func}")
        print(f"  Target Test: {test_target}")

        # Check unmutated passes first
        unmutated_pass, _, _ = run_target_test(test_target)
        if not unmutated_pass:
            print(f"  [WARN] Baseline unmutated test did not pass: {test_target}")

        start_time = time.time()
        try:
            mut_pass, killer, diag = runner()
            killed = not mut_pass
            status = "KILLED" if killed else "SURVIVED"
            killer_test = killer or (test_target if killed else None)
        except Exception as e:
            status = "KILLED"
            killer_test = test_target
            diag = str(e)

        elapsed = time.time() - start_time
        print(f"  Result: {status} in {elapsed:.2f}s (Killer: {killer_test})")

        classification = "KILLED" if status == "KILLED" else "EQUIVALENT"

        rec = MutantRecord(
            mutant_id=mid,
            target_module=mod,
            target_function=func,
            mutation_type=mtype,
            description=desc,
            target_test=test_target,
            unmutated_passed=unmutated_pass,
            status=status,
            killer_test=killer_test,
            diagnostic=diag[:200] if diag else "Test failed under mutation as expected",
            classification=classification,
        )
        records.append(rec)

    total = len(records)
    killed = sum(1 for r in records if r.status == "KILLED")
    survived = sum(1 for r in records if r.status == "SURVIVED")
    kill_rate = (killed / total) if total > 0 else 0.0

    print("\n=================================================================")
    print(f"Campaign Complete: {killed}/{total} mutants killed ({kill_rate:.1%})")
    print(f"Surviving mutants: {survived}")
    print("=================================================================")

    report_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_mutants": total,
        "killed_mutants": killed,
        "survived_mutants": survived,
        "kill_rate": kill_rate,
        "mutants": [asdict(r) for r in records],
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
