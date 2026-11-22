#!/usr/bin/env python3
"""
Targeted production-function runtime mutation campaign runner for GDEC verification.
Executes a documented, bounded runtime mutation campaign across 6 core production modules:
- gdec.fem.constitutive
- gdec.fem.matrix_diagnostics
- gdec.fem.adaptivity
- gdec.dse.evaluator
- gdec.dse.scaling
- gdec.eir.expressions

Reports every mutant, affected function, killer test, failure diagnostic, and kill rate.
Validates baseline test execution before mutation, aborting on baseline failures.
Distinguishes KILLED, SURVIVED, and ERROR states without false equivalence claims.
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
    status: str  # KILLED, SURVIVED, ERROR, INVALID_BASELINE
    killer_test: Optional[str] = None
    diagnostic: Optional[str] = None
    classification: str = "KILLED"  # KILLED, TEST_GAP, ERROR, INVALID_BASELINE


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

    # 4. FEM Matrix Diagnostics: Eligibility forced to True on singular system
    def mut_matrix_cg_eligibility():
        import gdec.fem.matrix_diagnostics as pmd
        import tests.test_matrix_diagnostics as tmd
        from dataclasses import replace
        orig_pmd = pmd.analyze_stiffness_matrix
        orig_tmd = tmd.analyze_stiffness_matrix
        def _mut(*args, **kwargs):
            diag = orig_pmd(*args, **kwargs)
            return replace(diag, is_cg_eligible=True, is_positive_definite=True)
        pmd.analyze_stiffness_matrix = _mut
        tmd.analyze_stiffness_matrix = _mut
        try:
            return run_target_test("tests/test_matrix_diagnostics.py::test_partially_constrained_system_remains_singular")
        finally:
            pmd.analyze_stiffness_matrix = orig_pmd
            tmd.analyze_stiffness_matrix = orig_tmd
    mutants.append((
        "MUT-SOLV-02",
        "gdec.fem.matrix_diagnostics",
        "analyze_stiffness_matrix",
        "logical",
        "Force is_cg_eligible and is_positive_definite to True unconditionally",
        "tests/test_matrix_diagnostics.py::test_partially_constrained_system_remains_singular",
        mut_matrix_cg_eligibility,
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

    # 11. DSE Evaluator: Force release recommendation when risk exceeds limit
    def mut_evaluator_force_release():
        from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            res = orig(self, *args, **kwargs)
            from dataclasses import replace
            if res.is_conclusive():
                return replace(res, recommendation=DecisionRecommendation.RELEASE)
            return res
        SingleQoIEvaluator.evaluate = _mut
        try:
            return run_target_test("tests/test_dse.py::test_evaluator_selects_reject_when_risk_exceeds")
        finally:
            SingleQoIEvaluator.evaluate = orig
    mutants.append((
        "MUT-DSE-05",
        "gdec.dse.evaluator",
        "SingleQoIEvaluator.evaluate",
        "boundary",
        "Force conclusive recommendation to RELEASE regardless of expected loss",
        "tests/test_dse.py::test_evaluator_selects_reject_when_risk_exceeds",
        mut_evaluator_force_release,
    ))

    # 12. EIR Expressions: Bypass dimensional equality in addition
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

    # 13. EIR Expressions: Invert AST depth limit check
    def mut_eir_depth_check():
        import gdec.eir.expressions as ee
        orig_ee = ee.infer_expression_type
        def _mut(expression, environment, **kwargs):
            kwargs["max_depth"] = 999999
            kwargs["max_nodes"] = 999999
            return orig_ee(expression, environment, **kwargs)
        ee.infer_expression_type = _mut
        patched_mods = []
        for m in list(sys.modules.values()):
            if m and getattr(m, "__name__", "") == "test_adversarial_hardening" and hasattr(m, "infer_expression_type"):
                setattr(m, "infer_expression_type", _mut)
                patched_mods.append(m)
        try:
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_deeply_nested_expression_rejected_with_typed_error")
        finally:
            ee.infer_expression_type = orig_ee
            for m in patched_mods:
                setattr(m, "infer_expression_type", orig_ee)
    mutants.append((
        "MUT-EIR-02",
        "gdec.eir.expressions",
        "infer_expression_type",
        "boundary",
        "Disable AST recursion depth and node count upper bounds check",
        "tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_deeply_nested_expression_rejected_with_typed_error",
        mut_eir_depth_check,
    ))

    # 14. EIR Expressions: Bypass identifier confusable character rejection
    def mut_eir_confusable_check():
        import gdec.eir.models as em
        orig_em = em._identifier
        em._identifier = lambda val: str(val)
        patched_mods = []
        for m in list(sys.modules.values()):
            if m and getattr(m, "__name__", "") == "test_adversarial_hardening" and hasattr(m, "_identifier"):
                setattr(m, "_identifier", lambda val: str(val))
                patched_mods.append(m)
        try:
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_identifier_rejects_control_and_confusable_characters")
        finally:
            em._identifier = orig_em
            for m in patched_mods:
                setattr(m, "_identifier", orig_em)
    mutants.append((
        "MUT-EIR-03",
        "gdec.eir.models",
        "_identifier",
        "boundary",
        "Disable unicode confusable and bidirectional control character check",
        "tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_identifier_rejects_control_and_confusable_characters",
        mut_eir_confusable_check,
    ))

    return mutants


def main():
    parser = argparse.ArgumentParser(description="Run GDEC targeted runtime mutation campaign.")
    parser.add_argument("--output", default="results/mutation_campaign_report.json", help="Output JSON path")
    args = parser.parse_args()

    print("=================================================================")
    print("  GDEC Targeted Production Runtime Mutation Campaign (WP2-R3)    ")
    print("=================================================================")

    mutants_def = build_mutants()
    records: List[MutantRecord] = []

    # 1. Enforce a passing baseline across all target tests before applying mutations
    print("\n--- Validating Unmutated Test Baselines ---")
    unique_target_tests = sorted(list(set(test_target for _, _, _, _, _, test_target, _ in mutants_def)))
    baseline_failures = []
    for tt in unique_target_tests:
        passed, fail_id, fail_msg = run_target_test(tt)
        if not passed:
            baseline_failures.append((tt, fail_id, fail_msg))
            print(f"  [FAIL] Baseline test failed: {tt}")
        else:
            print(f"  [PASS] Baseline test: {tt}")

    if baseline_failures:
        print(f"\n[FATAL] Baseline test validation failed for {len(baseline_failures)} tests.")
        print("Cannot continue mutation campaign with an invalid baseline.")
        sys.exit(1)

    print("\n--- Executing Targeted Runtime Mutations ---")
    for mid, mod, func, mtype, desc, test_target, runner in mutants_def:
        print(f"\n[{mid}] {desc}")
        print(f"  Target: {mod}.{func}")
        print(f"  Target Test: {test_target}")

        start_time = time.time()
        try:
            mut_pass, killer, diag = runner()
            killed = not mut_pass
            status = "KILLED" if killed else "SURVIVED"
            killer_test = killer or (test_target if killed else None)
            classification = "KILLED" if killed else "TEST_GAP"
            diag_str = diag[:200] if diag else ("Test failed under mutation as expected" if killed else "Test unexpectedly passed")
        except Exception as e:
            # Runner or environment execution error: must NOT be counted as KILLED!
            status = "ERROR"
            killer_test = None
            diag_str = f"Execution error in mutation runner: {e}"
            classification = "ERROR"

        elapsed = time.time() - start_time
        print(f"  Result: {status} in {elapsed:.2f}s (Killer: {killer_test})")

        rec = MutantRecord(
            mutant_id=mid,
            target_module=mod,
            target_function=func,
            mutation_type=mtype,
            description=desc,
            target_test=test_target,
            unmutated_passed=True,
            status=status,
            killer_test=killer_test,
            diagnostic=diag_str,
            classification=classification,
        )
        records.append(rec)

    total = len(records)
    killed = sum(1 for r in records if r.status == "KILLED")
    survived = sum(1 for r in records if r.status == "SURVIVED")
    errors = sum(1 for r in records if r.status == "ERROR")
    kill_rate = (killed / total) if total > 0 else 0.0

    print("\n=================================================================")
    print(f"Campaign Complete: {killed}/{total} mutants killed ({kill_rate:.1%})")
    print(f"Surviving mutants: {survived}")
    print(f"Execution errors: {errors}")
    print("=================================================================")

    report_data = {
        "campaign_type": "targeted_production_runtime_mutation",
        "scope": "6 core production modules (14 targeted mutants)",
        "excluded_areas": "Whole-repository AST source mutation (mutmut restricted on Windows per issue #397)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_validated": True,
        "total_mutants": total,
        "killed_mutants": killed,
        "survived_mutants": survived,
        "error_mutants": errors,
        "kill_rate": kill_rate,
        "mutants": [asdict(r) for r in records],
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"Report written to {args.output}")

    if errors > 0 or survived > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
