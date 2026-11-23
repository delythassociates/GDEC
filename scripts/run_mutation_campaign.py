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
class CapturedFailure:
    nodeid: str
    phase: str                  # "collection", "setup", "call", "teardown"
    exception_class: str        # e.g. "AssertionError", "Failed", "AttributeError", "RuntimeError"
    exception_message: str
    source_location: str
    diagnostic: str


@dataclass
class ExecutionResult:
    status: str              # KILLED, SURVIVED, ERROR, INVALID_MUTANT, INVALID_BASELINE, BASELINE_PASS
    classification: str      # KILLED, SURVIVED, SETUP_ERROR, TEARDOWN_ERROR, COLLECTION_ERROR, NO_TESTS_COLLECTED, INVALID_INJECTION, RUNNER_EXCEPTION, UNEXPECTED_EXCEPTION, UNEXPECTED_ASSERTION, BASELINE_PASS, BASELINE_ASSERTION_FAILURE, BASELINE_EXCEPTION
    killer_test: Optional[str]
    failure_type: Optional[str]
    phase: Optional[str]
    exit_code: int
    diagnostic: str
    exception_class: Optional[str] = None
    exception_message: Optional[str] = None
    source_location: Optional[str] = None
    rationale: str = ""


@dataclass
class MutantRecord:
    mutation_id: str
    target_production_function: str
    mutation_description: str
    target_test_node_id: str
    unmutated_baseline_result: str
    mutation_injection_result: str
    pytest_execution_result: str
    captured_failure_phase: Optional[str]
    exception_class: Optional[str]
    exception_message: Optional[str]
    final_classification: str
    classification_rationale: str
    source_location: Optional[str] = None
    killer_test: Optional[str] = None
    exit_code: Optional[int] = None
    diagnostic: Optional[str] = None
    # Backwards compatibility fields
    mutant_id: str = ""
    target_module: str = ""
    target_function: str = ""
    mutation_type: str = ""
    description: str = ""
    target_test: str = ""
    unmutated_passed: bool = True
    status: str = ""
    failure_type: Optional[str] = None
    phase: Optional[str] = None
    classification: str = ""

    def __post_init__(self):
        if not self.mutant_id:
            self.mutant_id = self.mutation_id
        if not self.description:
            self.description = self.mutation_description
        if not self.target_test:
            self.target_test = self.target_test_node_id
        if not self.status:
            self.status = self.final_classification
        if not self.classification:
            self.classification = self.final_classification
        if not self.failure_type:
            self.failure_type = self.exception_class
        if not self.phase:
            self.phase = self.captured_failure_phase


REQUIRED_RECORD_FIELDS = [
    "mutation_id",
    "target_production_function",
    "mutation_description",
    "target_test_node_id",
    "unmutated_baseline_result",
    "mutation_injection_result",
    "pytest_execution_result",
    "captured_failure_phase",
    "exception_class",
    "exception_message",
    "final_classification",
    "classification_rationale",
]

VALID_CLASSIFICATIONS = {"KILLED", "SURVIVED", "ERROR", "INVALID_MUTANT", "INVALID_BASELINE"}


def validate_mutant_record(record: Dict[str, Any]) -> None:
    """Validates that a mutant record conforms to the required audit schema."""
    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise ValueError(f"Missing required mutant record field: '{field}'")
    if record["final_classification"] not in VALID_CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification: '{record['final_classification']}'. Must be one of {VALID_CLASSIFICATIONS}"
        )
    if not record["mutation_id"] or not str(record["mutation_id"]).strip():
        raise ValueError("mutation_id cannot be empty")
    if not record["target_production_function"] or not str(record["target_production_function"]).strip():
        raise ValueError("target_production_function cannot be empty")
    if record["final_classification"] == "KILLED":
        if not record["exception_class"]:
            raise ValueError("KILLED mutant must have non-empty exception_class")
        if not record["captured_failure_phase"]:
            raise ValueError("KILLED mutant must have non-empty captured_failure_phase")
        if not record["classification_rationale"]:
            raise ValueError("KILLED mutant must have non-empty classification_rationale")


class MutationExecutionCapture:
    """In-process pytest plugin capturing collection, setup, call, teardown outcomes and exact failure diagnostics."""
    __test__ = False

    def __init__(self, target_nodeid: Optional[str] = None):
        self.target_nodeid = target_nodeid.replace("\\", "/") if target_nodeid else None
        self.collection_failed: bool = False
        self.collection_error: Optional[CapturedFailure] = None
        self.items_collected: int = 0
        self.collected_nodeids: List[str] = []
        self.setup_failures: List[CapturedFailure] = []
        self.call_failures: List[CapturedFailure] = []
        self.teardown_failures: List[CapturedFailure] = []
        self.passed_nodes: List[str] = []
        self.exit_code: Optional[int] = None

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_failed = True
            loc = ""
            msg = str(report.longrepr)
            if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash:
                loc = f"{report.longrepr.reprcrash.path}:{report.longrepr.reprcrash.lineno}"
                msg = str(report.longrepr.reprcrash.message)
            self.collection_error = CapturedFailure(
                nodeid=report.nodeid.replace("\\", "/"),
                phase="collection",
                exception_class="CollectionError",
                exception_message=msg,
                source_location=loc,
                diagnostic=f"{loc} - {msg}" if loc else msg,
            )

    def pytest_collection_modifyitems(self, session, config, items):
        self.items_collected = len(items)
        self.collected_nodeids = [item.nodeid.replace("\\", "/") for item in items]

    def pytest_runtest_makereport(self, item, call):
        norm_nodeid = item.nodeid.replace("\\", "/")
        if call.excinfo is not None:
            exc_class = call.excinfo.typename
            exc_msg = str(call.excinfo.value)
            loc = ""
            try:
                tb_entry = call.excinfo.traceback[-1]
                loc = f"{tb_entry.path}:{tb_entry.lineno}"
            except Exception:
                loc = ""
            diag = f"{loc} - {exc_class}: {exc_msg}" if loc else f"{exc_class}: {exc_msg}"

            failure = CapturedFailure(
                nodeid=norm_nodeid,
                phase=call.when,
                exception_class=exc_class,
                exception_message=exc_msg,
                source_location=loc,
                diagnostic=diag,
            )

            if call.when == "setup":
                self.setup_failures.append(failure)
            elif call.when == "call":
                self.call_failures.append(failure)
            elif call.when == "teardown":
                self.teardown_failures.append(failure)

    def pytest_runtest_logreport(self, report):
        norm_nodeid = report.nodeid.replace("\\", "/")
        if report.when == "call" and report.passed:
            self.passed_nodes.append(norm_nodeid)
        elif report.failed:
            # Fallback if makereport didn't capture
            target_list = None
            if report.when == "setup" and not self.setup_failures:
                target_list = self.setup_failures
            elif report.when == "call" and not self.call_failures:
                target_list = self.call_failures
            elif report.when == "teardown" and not self.teardown_failures:
                target_list = self.teardown_failures
            if target_list is not None:
                loc = ""
                msg = str(report.longrepr)
                if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash:
                    loc = f"{report.longrepr.reprcrash.path}:{report.longrepr.reprcrash.lineno}"
                    msg = str(report.longrepr.reprcrash.message)
                exc_class = "AssertionError" if "assert" in msg.lower() else "Failed"
                target_list.append(CapturedFailure(
                    nodeid=norm_nodeid,
                    phase=report.when,
                    exception_class=exc_class,
                    exception_message=msg,
                    source_location=loc,
                    diagnostic=f"{loc} - {exc_class}: {msg}" if loc else msg,
                ))

    def pytest_sessionfinish(self, session, exitstatus):
        self.exit_code = int(exitstatus)


def run_target_test(
    test_target: str,
    is_baseline: bool = False,
    expected_failure_type: str = "AssertionError",
    expected_failure_pattern: Optional[str] = None,
) -> ExecutionResult:
    capture = MutationExecutionCapture(test_target)
    exit_code = pytest.main([test_target, "-q"], plugins=[capture])

    # 1. Collection errors
    if capture.collection_failed or capture.collection_error is not None:
        err = capture.collection_error
        diag = err.diagnostic if err else "Collection failed"
        loc = err.source_location if err else None
        msg = err.exception_message if err else "Collection error"
        return ExecutionResult(
            status="INVALID_BASELINE" if is_baseline else "ERROR",
            classification="COLLECTION_ERROR",
            killer_test=None,
            failure_type="CollectionError",
            phase="collection",
            exit_code=exit_code,
            diagnostic=f"Collection error: {diag}",
            exception_class="CollectionError",
            exception_message=msg,
            source_location=loc,
            rationale="Test collection failed before execution",
        )

    # 2. No tests collected or usage error
    if capture.items_collected == 0 or exit_code in (pytest.ExitCode.NO_TESTS_COLLECTED, pytest.ExitCode.USAGE_ERROR):
        return ExecutionResult(
            status="INVALID_BASELINE" if is_baseline else "ERROR",
            classification="NO_TESTS_COLLECTED",
            killer_test=None,
            failure_type="NoTestsCollected",
            phase="collection",
            exit_code=exit_code,
            diagnostic=f"No tests collected for target: {test_target} (exit code: {exit_code})",
            exception_class="NoTestsCollected",
            exception_message=f"No tests collected for target: {test_target}",
            source_location=None,
            rationale="Pytest collected zero matching tests for target",
        )

    # 3. Setup errors
    if capture.setup_failures:
        err = capture.setup_failures[0]
        return ExecutionResult(
            status="INVALID_BASELINE" if is_baseline else "ERROR",
            classification="SETUP_ERROR",
            killer_test=err.nodeid,
            failure_type="SetupError",
            phase="setup",
            exit_code=exit_code,
            diagnostic=f"Setup failure in {err.nodeid}: {err.diagnostic}",
            exception_class=err.exception_class,
            exception_message=err.exception_message,
            source_location=err.source_location,
            rationale=f"Fixture or harness setup failure: {err.exception_class}",
        )

    # 4. Teardown errors
    if capture.teardown_failures:
        err = capture.teardown_failures[0]
        return ExecutionResult(
            status="INVALID_BASELINE" if is_baseline else "ERROR",
            classification="TEARDOWN_ERROR",
            killer_test=err.nodeid,
            failure_type="TeardownError",
            phase="teardown",
            exit_code=exit_code,
            diagnostic=f"Teardown failure in {err.nodeid}: {err.diagnostic}",
            exception_class=err.exception_class,
            exception_message=err.exception_message,
            source_location=err.source_location,
            rationale=f"Fixture or harness teardown failure: {err.exception_class}",
        )

    # 5. Call phase failures
    if capture.call_failures:
        err = capture.call_failures[0]
        exc_type = err.exception_class

        if is_baseline:
            cls = "BASELINE_ASSERTION_FAILURE" if exc_type == "AssertionError" else "BASELINE_EXCEPTION"
            return ExecutionResult(
                status="INVALID_BASELINE",
                classification=cls,
                killer_test=err.nodeid,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=err.diagnostic,
                exception_class=exc_type,
                exception_message=err.exception_message,
                source_location=err.source_location,
                rationale=f"Unmutated baseline test failed in call phase with {exc_type}",
            )

        # In mutation mode:
        INJECTION_ERROR_TYPES = {"AttributeError", "NameError", "TypeError", "UnboundLocalError", "ImportError"}
        if exc_type in INJECTION_ERROR_TYPES:
            return ExecutionResult(
                status="INVALID_MUTANT",
                classification="INVALID_INJECTION",
                killer_test=err.nodeid,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=f"Invalid mutant injection ({exc_type}): {err.diagnostic}",
                exception_class=exc_type,
                exception_message=err.exception_message,
                source_location=err.source_location,
                rationale=f"Mutant injection caused {exc_type} rather than behavioral failure",
            )

        # Check if failure matches expected behavioral assertion / failure
        is_expected_type = (exc_type == expected_failure_type)
        pattern_matches = True
        if expected_failure_pattern:
            pattern_matches = (
                expected_failure_pattern.lower() in err.diagnostic.lower()
                or expected_failure_pattern.lower() in err.exception_message.lower()
            )

        if is_expected_type and pattern_matches:
            return ExecutionResult(
                status="KILLED",
                classification="KILLED",
                killer_test=err.nodeid,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=err.diagnostic,
                exception_class=exc_type,
                exception_message=err.exception_message,
                source_location=err.source_location,
                rationale=f"Designated behavioral assertion ({exc_type}) triggered in call phase as expected",
            )
        elif is_expected_type and not pattern_matches:
            return ExecutionResult(
                status="ERROR",
                classification="UNEXPECTED_ASSERTION",
                killer_test=err.nodeid,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=f"Assertion failed but pattern '{expected_failure_pattern}' was not matched: {err.diagnostic}",
                exception_class=exc_type,
                exception_message=err.exception_message,
                source_location=err.source_location,
                rationale="Assertion failure occurred but did not match expected behavioral failure pattern",
            )
        else:
            return ExecutionResult(
                status="ERROR",
                classification="UNEXPECTED_EXCEPTION",
                killer_test=err.nodeid,
                failure_type=exc_type,
                phase="call",
                exit_code=exit_code,
                diagnostic=f"Unexpected exception during test execution ({exc_type}): {err.diagnostic}",
                exception_class=exc_type,
                exception_message=err.exception_message,
                source_location=err.source_location,
                rationale=f"Test crashed with unexpected {exc_type} (expected {expected_failure_type})",
            )

    # 6. Test passed
    if exit_code == 0 and len(capture.passed_nodes) > 0:
        if is_baseline:
            return ExecutionResult(
                status="BASELINE_PASS",
                classification="BASELINE_PASS",
                killer_test=None,
                failure_type=None,
                phase="call",
                exit_code=exit_code,
                diagnostic="Unmutated baseline test passed successfully",
                exception_class=None,
                exception_message=None,
                source_location=None,
                rationale="Baseline test passed cleanly without mutations",
            )
        return ExecutionResult(
            status="SURVIVED",
            classification="SURVIVED",
            killer_test=None,
            failure_type=None,
            phase="call",
            exit_code=exit_code,
            diagnostic="Test passed despite mutation (mutant survived)",
            exception_class=None,
            exception_message=None,
            source_location=None,
            rationale="Mutant produced no detectable behavioral failure; test passed",
        )

    # 7. Fallback unexpected exit
    return ExecutionResult(
        status="INVALID_BASELINE" if is_baseline else "ERROR",
        classification="UNEXPECTED_EXIT",
        killer_test=None,
        failure_type="UnexpectedExit",
        phase="unknown",
        exit_code=exit_code,
        diagnostic=f"Pytest exited with code {exit_code} without test report",
        exception_class="UnexpectedExit",
        exception_message=f"Pytest exited with code {exit_code}",
        source_location=None,
        rationale=f"Pytest exited with unexpected code {exit_code}",
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
            return run_target_test("tests/eir/test_expression_typing.py::test_addition_requires_equal_dimensions", expected_failure_type="Failed", expected_failure_pattern="DID NOT RAISE")
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
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_deeply_nested_expression_rejected_with_typed_error", expected_failure_type="Failed", expected_failure_pattern="DID NOT RAISE")
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
            return run_target_test("tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing::test_identifier_rejects_control_and_confusable_characters", expected_failure_type="Failed", expected_failure_pattern="DID NOT RAISE")
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
        # In baseline, the test MUST pass cleanly (status == BASELINE_PASS or SURVIVED)
        if res.status not in ("BASELINE_PASS", "SURVIVED"):
            baseline_failures.append((tt, res))
            print(f"  [FAIL] Baseline test failed: {tt} -> {res.status} ({res.classification}): {res.diagnostic}")
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
        injection_result = "SUCCESS"
        try:
            exec_res = runner()
        except Exception as e:
            injection_result = "INVALID_INJECTION"
            exec_res = ExecutionResult(
                status="INVALID_MUTANT",
                classification="RUNNER_EXCEPTION",
                killer_test=None,
                failure_type=type(e).__name__,
                phase="runner",
                exit_code=1,
                diagnostic=f"Mutation runner exception: {type(e).__name__}: {e}",
                exception_class=type(e).__name__,
                exception_message=str(e),
                source_location=None,
                rationale="Exception occurred in mutation runner callable",
            )

        elapsed = time.time() - start_time
        print(f"  Result: {exec_res.status} in {elapsed:.2f}s (Killer: {exec_res.killer_test})")
        print(f"  Diagnostic: {exec_res.diagnostic[:150]}")

        py_res = (
            "FAILED"
            if exec_res.status in ("KILLED", "INVALID_MUTANT")
            else ("PASSED" if exec_res.status in ("SURVIVED", "BASELINE_PASS") else "ERROR")
        )

        rec = MutantRecord(
            mutation_id=mid,
            target_production_function=f"{mod}.{func}",
            mutation_description=desc,
            target_test_node_id=test_target,
            unmutated_baseline_result="BASELINE_PASS",
            mutation_injection_result=injection_result,
            pytest_execution_result=py_res,
            captured_failure_phase=exec_res.phase,
            exception_class=exec_res.exception_class,
            exception_message=exec_res.exception_message,
            final_classification=exec_res.status,
            classification_rationale=exec_res.rationale,
            source_location=exec_res.source_location,
            killer_test=exec_res.killer_test,
            exit_code=exec_res.exit_code,
            diagnostic=exec_res.diagnostic,
            mutant_id=mid,
            target_module=mod,
            target_function=func,
            mutation_type=mtype,
            description=desc,
            target_test=test_target,
            unmutated_passed=True,
            status=exec_res.status,
            failure_type=exec_res.failure_type,
            phase=exec_res.phase,
            classification=exec_res.classification,
        )
        validate_mutant_record(asdict(rec))
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
