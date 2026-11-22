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
Strictly distinguishes KILLED, SURVIVED, ERROR, INVALID_MUTANT, and INVALID_BASELINE.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import patch

# Ensure src and repo root are in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(repo_root, "src"))
sys.path.insert(0, repo_root)

import pytest


@dataclass
class ExecutionResult:
    status: str              # KILLED, SURVIVED, ERROR, INVALID_MUTANT, INVALID_BASELINE
    classification: str      # KILLED, SURVIVED, SETUP_ERROR, TEARDOWN_ERROR, COLLECTION_ERROR, NO_TESTS_COLLECTED, INVALID_INJECTION, RUNNER_EXCEPTION, USAGE_ERROR
    killer_test: Optional[str]
    failure_type: Optional[str]
    phase: Optional[str]
    exit_code: int
    diagnostic: str


@dataclass
class MutantRecord:
    mutant_id: str
    target_module: str
    target_function: str
    mutation_type: str  # arithmetic, relational, logical, boundary, return_value
    description: str
    target_test: str
    unmutated_passed: bool
    status: str  # KILLED, SURVIVED, ERROR, INVALID_MUTANT, INVALID_BASELINE
    killer_test: Optional[str] = None
    failure_type: Optional[str] = None
    phase: Optional[str] = None
    exit_code: Optional[int] = None
    diagnostic: Optional[str] = None
    classification: str = "KILLED"  # KILLED, SURVIVED, ERROR, INVALID_MUTANT, INVALID_BASELINE


class MutationExecutionCapture:
    """In-process pytest plugin capturing collection, setup, call, teardown outcomes and exact failure diagnostics."""
    __test__ = False
    def __init__(self, target_nodeid: Optional[str] = None):
        self.target_nodeid = target_nodeid.replace("\\", "/") if target_nodeid else None
        self.collection_failed: bool = False
        self.collection_error: str = ""
        self.items_collected: int = 0
        self.setup_failed_node: Optional[str] = None
        self.setup_error: str = ""
        self.teardown_failed_node: Optional[str] = None
        self.teardown_error: str = ""
        self.call_failed_node: Optional[str] = None
        self.call_error: str = ""
        self.call_exception_type: Optional[str] = None
        self.passed_nodes: List[str] = []
        self.failed_nodes: List[str] = []
        self.exit_code: Optional[int] = None

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_failed = True
            self.collection_error = self._format_error(report)

    def pytest_collection_modifyitems(self, session, config, items):
        self.items_collected = len(items)

    def pytest_runtest_logreport(self, report):
        norm_nodeid = report.nodeid.replace("\\", "/")
        if report.when == "setup":
            if report.failed:
                self.setup_failed_node = norm_nodeid
                self.setup_error = self._format_error(report)
                self.failed_nodes.append(norm_nodeid)
        elif report.when == "call":
            if report.passed:
                self.passed_nodes.append(norm_nodeid)
            elif report.failed:
                self.call_failed_node = norm_nodeid
                self.call_error = self._format_error(report)
                self.call_exception_type = self._extract_exception_type(report)
                self.failed_nodes.append(norm_nodeid)
        elif report.when == "teardown":
            if report.failed:
                self.teardown_failed_node = norm_nodeid
                self.teardown_error = self._format_error(report)

    def pytest_sessionfinish(self, session, exitstatus):
        self.exit_code = int(exitstatus)

    def _extract_exception_type(self, report) -> str:
        if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash:
            msg = report.longrepr.reprcrash.message or ""
            if ":" in msg:
                return msg.split(":", 1)[0].strip()
            if msg.startswith("Failed"):
                return "Failed"
        text = str(report.longrepr)
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line and ("Error:" in line or "Exception:" in line or line.startswith("Failed")):
                return line.split(":", 1)[0].strip()
        return "UnknownException"

    def _format_error(self, report) -> str:
        if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash:
            crash = report.longrepr.reprcrash
            return f"{crash.path}:{crash.lineno} - {crash.message}"
        lines = [l.strip() for l in str(report.longrepr).splitlines() if l.strip()]
        return " | ".join(lines[-3:]) if lines else "Unknown error"


def run_target_test(test_target: str, is_baseline: bool = False) -> ExecutionResult:
    capture = MutationExecutionCapture(test_target)
    exit_code = pytest.main([test_target, "-q"], plugins=[capture])

    # 1. Collection errors
    if capture.collection_failed:
        return ExecutionResult(
            status="ERROR",
            classification="COLLECTION_ERROR",
            killer_test=None,
            failure_type="CollectionError",
            phase="collection",
            exit_code=exit_code,
            diagnostic=f"Collection error: {capture.collection_error}",
        )

    # 2. No tests collected or usage error
    if capture.items_collected == 0 or exit_code in (pytest.ExitCode.NO_TESTS_COLLECTED, pytest.ExitCode.USAGE_ERROR):
        return ExecutionResult(
            status="ERROR",
            classification="NO_TESTS_COLLECTED",
            killer_test=None,
            failure_type="UsageError" if exit_code == pytest.ExitCode.USAGE_ERROR else "NoTestsCollected",
            phase="collection",
            exit_code=exit_code,
            diagnostic=f"No tests collected for target: {test_target} (exit code: {exit_code})",
        )

    # 3. Setup errors
    if capture.setup_failed_node:
        return ExecutionResult(
            status="ERROR",
            classification="SETUP_ERROR",
            killer_test=capture.setup_failed_node,
            failure_type="SetupError",
            phase="setup",
            exit_code=exit_code,
            diagnostic=f"Setup failure in {capture.setup_failed_node}: {capture.setup_error}",
        )

    # 4. Teardown errors
    if capture.teardown_failed_node:
        return ExecutionResult(
            status="ERROR",
            classification="TEARDOWN_ERROR",
            killer_test=capture.teardown_failed_node,
            failure_type="TeardownError",
            phase="teardown",
            exit_code=exit_code,
            diagnostic=f"Teardown failure in {capture.teardown_failed_node}: {capture.teardown_error}",
        )

    # 5. Call phase failures
    if capture.call_failed_node:
        exc_type = capture.call_exception_type or "Unknown"
        # Injection error types originating from invalid mutant code (not test assertions)
        INJECTION_ERROR_TYPES = {"AttributeError", "NameError", "TypeError", "UnboundLocalError", "ImportError"}
        if exc_type in INJECTION_ERROR_TYPES and not is_baseline:
            return ExecutionResult(
                status="INVALID_MUTANT",
                classification="INVALID_INJECTION",
                killer_test=capture.call_failed_node,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=f"Invalid mutant injection ({exc_type}): {capture.call_error}",
            )
        else:
            return ExecutionResult(
                status="KILLED",
                classification="KILLED",
                killer_test=capture.call_failed_node,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=capture.call_error,
            )

    # 6. Test passed
    if exit_code == 0 and len(capture.passed_nodes) > 0:
        return ExecutionResult(
            status="SURVIVED",
            classification="SURVIVED",
            killer_test=None,
            failure_type=None,
            phase="call",
            exit_code=exit_code,
            diagnostic="Test passed despite mutation (mutant survived)",
        )

    # 7. Fallback unexpected exit
    return ExecutionResult(
        status="ERROR",
        classification="UNEXPECTED_EXIT",
        killer_test=None,
        failure_type="UnexpectedExit",
        phase="unknown",
        exit_code=exit_code,
        diagnostic=f"Pytest exited with code {exit_code} without test report",
    )


def build_mutants() -> List[tuple[str, str, str, str, str, str, Callable[[], ExecutionResult]]]:
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
            # Intended modulus-scaling mutation:
            # J_mutated = (P / P0) * (E0 / E)^2 * J0 = orig(self, E, P) * (self.baseline.E_0 / E)
            return orig(self, E, P) * (self.baseline.E_0 / E)
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
            # Intended inverted load-scaling mutation:
            # J_mutated = (P0 / P) * (E0 / E) * J0 = orig(self, E, P) * (self.baseline.P_0 / P)^2
            return orig(self, E, P) * (self.baseline.P_0 / P) ** 2
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
        from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            res = orig(self, *args, **kwargs)
            if res.is_conclusive():
                new_rec = DecisionRecommendation.RELEASE if res.recommendation == DecisionRecommendation.REJECT else DecisionRecommendation.REJECT
                from dataclasses import replace
                return replace(res, recommendation=new_rec)
            return res
        SingleQoIEvaluator.evaluate = _mut
        try:
            return run_target_test("tests/test_dse.py::test_evaluator_selects_reject_when_risk_exceeds")
        finally:
            SingleQoIEvaluator.evaluate = orig
    mutants.append((
        "MUT-DSE-03",
        "gdec.dse.evaluator",
        "SingleQoIEvaluator.evaluate",
        "relational",
        "Invert risk recommendation in Bayesian loss decision evaluator (RELEASE instead of REJECT)",
        "tests/test_dse.py::test_evaluator_selects_reject_when_risk_exceeds",
        mut_evaluator_risk_swap,
    ))

    # 10. DSE Evaluator: Bypass epistemic uncertainty check
    def mut_evaluator_bypass_evidence():
        from gdec.dse.evaluator import SingleQoIEvaluator, DecisionRecommendation, DecisionEvaluationResult
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            return DecisionEvaluationResult(
                recommendation=DecisionRecommendation.RELEASE,
                expected_loss_release=0.0,
                expected_loss_reject=100.0,
                probability_safe=1.0,
                probability_fail=0.0,
                decision_margin=5.0,
                threshold_value=5.0,
                qoi_mean=2.0,
                qoi_std=0.1,
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
        from gdec.dse.evaluator import SingleQoIEvaluator
        orig = SingleQoIEvaluator.evaluate
        def _mut(self, *args, **kwargs):
            res = orig(self, *args, **kwargs)
            from dataclasses import replace
            return replace(res, expected_loss_release=res.expected_loss_release + 2.0)
        SingleQoIEvaluator.evaluate = _mut
        try:
            return run_target_test("tests/test_dse.py::test_evaluator_known_gaussian_calculation")
        finally:
            SingleQoIEvaluator.evaluate = orig
    mutants.append((
        "MUT-DSE-05",
        "gdec.dse.evaluator",
        "SingleQoIEvaluator.evaluate",
        "boundary",
        "Perturb expected loss release by +2.0 in Gaussian loss calculation",
        "tests/test_dse.py::test_evaluator_known_gaussian_calculation",
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
        res = run_target_test(tt, is_baseline=True)
        # In baseline, the test MUST pass cleanly (status == SURVIVED means exit_code == 0)
        if res.status != "SURVIVED":
            baseline_failures.append((tt, res))
            print(f"  [FAIL] Baseline test failed: {tt} -> {res.diagnostic}")
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
            exec_res = runner()
        except Exception as e:
            exec_res = ExecutionResult(
                status="INVALID_MUTANT",
                classification="RUNNER_EXCEPTION",
                killer_test=None,
                failure_type=type(e).__name__,
                phase="runner",
                exit_code=1,
                diagnostic=f"Mutation runner exception: {type(e).__name__}: {e}",
            )

        elapsed = time.time() - start_time
        print(f"  Result: {exec_res.status} in {elapsed:.2f}s (Killer: {exec_res.killer_test})")
        print(f"  Diagnostic: {exec_res.diagnostic[:150]}")

        rec = MutantRecord(
            mutant_id=mid,
            target_module=mod,
            target_function=func,
            mutation_type=mtype,
            description=desc,
            target_test=test_target,
            unmutated_passed=True,
            status=exec_res.status,
            killer_test=exec_res.killer_test,
            failure_type=exec_res.failure_type,
            phase=exec_res.phase,
            exit_code=exec_res.exit_code,
            diagnostic=exec_res.diagnostic,
            classification=exec_res.classification,
        )
        records.append(rec)

    total = len(records)
    killed = sum(1 for r in records if r.status == "KILLED")
    survived = sum(1 for r in records if r.status == "SURVIVED")
    errors = sum(1 for r in records if r.status == "ERROR")
    invalid_mutants = sum(1 for r in records if r.status == "INVALID_MUTANT")
    kill_rate = (killed / total) if total > 0 else 0.0

    print("\n=================================================================")
    print(f"Campaign Complete: {killed}/{total} mutants killed ({kill_rate:.1%})")
    print(f"Surviving mutants: {survived}")
    print(f"Invalid mutants: {invalid_mutants}")
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
        "invalid_mutants": invalid_mutants,
        "error_mutants": errors,
        "kill_rate": kill_rate,
        "mutants": [asdict(r) for r in records],
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"Report written to {args.output}")

    if errors > 0 or survived > 0 or invalid_mutants > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
