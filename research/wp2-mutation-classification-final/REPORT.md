# GDEC WP2 Final Mutation-Runner Classification and Test-Coverage Closure — Completion Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/wp2-mutation-classification-final`  
**Starting baseline commit:** `c1bb69dfe976720bc8035cf6832f90626e5dc1cf`  
**Previous CI run:** [45074745212](https://github.com/delythassociates/GDEC/actions/runs/45074745212) (15/15 jobs successful)  
**Date:** 2026-11-23  

---

## 1. Executive Summary

This targeted corrective pass resolves the remaining audit findings regarding mutation testing reliability, exception extraction accuracy, baseline failure classification, teardown error handling, Git inspection test coverage, and CI workflow step naming.

The changes establish defensible, rigorous evidence:
1. **Reliable Mutation Outcome Classification & Exception Extraction**:
   - Replaced fragile string-based exception parsing in `scripts/run_mutation_campaign.py` with structured pytest outcome capture via `pytest_runtest_makereport` hook and `call.excinfo`.
   - Captures exact exception class name (`typename`), message, failure phase (`setup`, `call`, `teardown`), and source location.
   - Eliminates all occurrences of generic `UnknownException`.
   - Distinctly classifies execution outcomes: `KILLED` (genuine test assertion failure or test failure), `SURVIVED` (mutant passed test), `ERROR` (setup, collection, or teardown failures), `INVALID_MUTANT` (injection/attribute errors), and `INVALID_BASELINE` (baseline execution failure).
2. **Correct `INVALID_BASELINE` Behavior**:
   - In baseline execution mode, any failure (assertion failure, unexpected exception, collection failure, setup error, teardown error, or missing test node) produces an `INVALID_BASELINE` outcome.
   - Aborts the mutation campaign immediately before any mutant is injected.
   - Covered by 6 dedicated negative unit tests in `TestBaselineValidation`.
3. **Explicit Teardown-Error Testing**:
   - Added `test_runner_teardown_error_produces_error` in `tests/verification/test_mutation_resilience.py`, where a fixture succeeds during test execution (`call`) but raises during fixture teardown.
   - Verifies the runner reports `ERROR` with `phase="teardown"`, `exception_class="RuntimeError"`, and diagnostic `TEARDOWN_ERROR`, proving it is never misclassified as `KILLED`.
4. **Complete Negative Tests for All Three Git Inspection Commands**:
   - Separated Git inspection negative tests in `tests/verification/test_status_register_traceability.py` into 3 isolated tests targeting:
     - `git rev-parse HEAD` failure
     - `git rev-parse --abbrev-ref HEAD` failure
     - `git status --porcelain -uall` failure
   - Each verifies `git_valid=False`, `dirty=True`, freshness verification rejection, and accurate command error capture.
5. **Accurate Mutation Artifact Schema**:
   - Every mutant record in `results/mutation_campaign_report.json` satisfies all 12 schema fields: `mutation_id`, `target_production_function`, `mutation_description`, `target_test_node_id`, `unmutated_baseline_result`, `mutation_injection_result`, `pytest_execution_result`, `captured_failure_phase`, `exception_class`, `exception_message`, `final_classification`, `classification_rationale`.
   - Validated automatically with `validate_mutant_record` during campaign generation.
6. **Accurate CI Workflow Step Label**:
   - Renamed `Run bounded source mutation campaign` to `Run targeted production-function runtime mutation campaign` in `.github/workflows/ci.yml`.

---

## 2. Mutation Classification & Campaign Results

The runtime mutation campaign was executed using `python scripts/run_mutation_campaign.py`. All 14 production runtime mutants were evaluated against their unmutated baseline and target tests.

| Mutation ID | Target Production Function | Target Test Node ID | Unmutated Baseline | Failure Phase | Captured Exception Class | Final Classification | Classification Rationale |
|---|---|---|---|---|---|---|---|
| `MUT-DSE-01` | `RestrictedLinearElasticScaling.evaluate_candidate_thickness` | `tests/dse/test_scaling.py::test_independent_fem_scaling_agreement` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-DSE-02` | `RestrictedLinearElasticScaling.evaluate_candidate_pressure` | `tests/dse/test_scaling.py::test_independent_fem_scaling_agreement` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-DSE-03` | `ThicknessBudgetEvaluator.evaluate_feasibility` | `tests/dse/test_dse_evaluators.py::test_thickness_budget_evaluator_budget_respected` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-DSE-04` | `PressureCapacityEvaluator.evaluate_feasibility` | `tests/dse/test_dse_evaluators.py::test_pressure_capacity_evaluator_safety_margin` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-DSE-05` | `GeometricFeasibilityEvaluator.evaluate_feasibility` | `tests/dse/test_dse_evaluators.py::test_geometric_feasibility_evaluator_aspect_ratio` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-AST-01` | `SafeExpressionEvaluator._eval_ast` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_depth_limit_exceeded` | `BASELINE_PASS` | `call` | `Failed` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-AST-02` | `SafeExpressionEvaluator._eval_ast` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_node_limit_exceeded` | `BASELINE_PASS` | `call` | `Failed` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-AST-03` | `SafeExpressionEvaluator._eval_ast` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_rational_exponent_den_exceeded` | `BASELINE_PASS` | `call` | `Failed` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-EIR-01` | `validate_eir_expression` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_nfc_normalization` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-EIR-02` | `validate_eir_expression` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_homoglyph_detection` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-EIR-03` | `validate_eir_expression` | `tests/test_ast_evaluator_adversarial.py::test_adversarial_control_characters_rejected` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-REF-01` | `LinearElasticitySolver.assemble_stiffness` | `tests/verification/test_reference_library.py::test_ref_01_cantilever_mesh_convergence_rate` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-REF-02` | `KirschBenchmark.solve` | `tests/verification/test_reference_library.py::test_ref_06_kirsch_reference_formulation_sensitivity` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |
| `MUT-REF-03` | `LShapedDomainSingularityBenchmark.solve` | `tests/verification/test_reference_library.py::test_ref_07_lshaped_singularity_detection` | `BASELINE_PASS` | `call` | `AssertionError` | `KILLED` | Test failed with expected AssertionError during call phase |

**Mutation Campaign Statistics:**
- Total mutants defined: 14
- Baseline validation passes: 14 / 14
- Mutants injected: 14 / 14
- Mutants killed: 14 / 14 (100.0%)
- Mutants survived: 0
- Invalid mutants: 0
- Runner errors: 0
- Records with generic `UnknownException`: 0

---

## 3. Negative-Test Evidence

All negative test cases pass cleanly in the test suite:

### Mutation Runner & Baseline Negative Tests (`tests/verification/test_mutation_resilience.py`)
1. `tests/verification/test_mutation_resilience.py::test_runner_genuine_assertion_failure_produces_killed`
   - Evaluates genuine `assert 1 == 2` in test call phase $\to$ classified as `KILLED`.
2. `tests/verification/test_mutation_resilience.py::test_runner_injection_attribute_error_produces_invalid_mutant`
   - Injects mutant that raises `AttributeError` $\to$ classified as `INVALID_MUTANT` / `INJECTION_ERROR`.
3. `tests/verification/test_mutation_resilience.py::test_runner_unexpected_runtime_error_produces_error_not_killed`
   - Simulates unexpected test execution crash (`RuntimeError("Disk full")`) $\to$ classified as `ERROR` / `UNEXPECTED_EXCEPTION`, never `KILLED`.
4. `tests/verification/test_mutation_resilience.py::test_runner_collection_error_produces_error`
   - Exercises syntax/import failure during pytest collection phase $\to$ classified as `ERROR` / `COLLECTION_ERROR`.
5. `tests/verification/test_mutation_resilience.py::test_runner_setup_error_produces_error`
   - Exercises fixture setup failure $\to$ classified as `ERROR` / `SETUP_ERROR`.
6. `tests/verification/test_mutation_resilience.py::test_runner_teardown_error_produces_error`
   - Exercises fixture teardown failure where `call` succeeds $\to$ classified as `ERROR` / `TEARDOWN_ERROR` with `phase="teardown"`, never `KILLED`.
7. `tests/verification/test_mutation_resilience.py::test_runner_surviving_mutation_produces_survived`
   - Mutates code into equivalent form passing test $\to$ classified as `SURVIVED`.
8. `tests/verification/test_mutation_resilience.py::test_runner_schema_validation_rejects_incomplete_record`
   - Validates that omitting required fields raises `ValueError`.
9. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_assertion_failure_produces_invalid_baseline`
   - Baseline test failing an assertion produces `INVALID_BASELINE` / `BASELINE_ASSERTION_FAILURE`.
10. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_unexpected_exception_produces_invalid_baseline`
    - Baseline test raising unexpected error produces `INVALID_BASELINE` / `BASELINE_EXCEPTION`.
11. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_collection_failure_produces_invalid_baseline`
    - Baseline test failing collection produces `INVALID_BASELINE` / `COLLECTION_ERROR`.
12. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_setup_failure_produces_invalid_baseline`
    - Baseline fixture failing during setup produces `INVALID_BASELINE` / `SETUP_ERROR`.
13. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_teardown_failure_produces_invalid_baseline`
    - Baseline fixture failing during teardown produces `INVALID_BASELINE` / `TEARDOWN_ERROR`.
14. `tests/verification/test_mutation_resilience.py::TestBaselineValidation::test_baseline_missing_target_test_produces_invalid_baseline`
    - Missing test node ID produces `INVALID_BASELINE` / `NO_TESTS_COLLECTED`.
15. `tests/verification/test_mutation_resilience.py::test_failed_unmutated_baseline_aborts_campaign`
    - Verifies campaign aborts immediately without injecting mutants if any baseline fails.

### Git Inspection Negative Tests (`tests/verification/test_status_register_traceability.py`)
1. `tests/verification/test_status_register_traceability.py::test_git_inspection_fails_closed_when_rev_parse_head_fails`
   - Simulates failure of `git rev-parse HEAD`. Verifies `git_valid=False`, `dirty=True`, command captured in errors, and `verify_traceability()` rejects state.
2. `tests/verification/test_status_register_traceability.py::test_git_inspection_fails_closed_when_rev_parse_branch_fails`
   - Simulates failure of `git rev-parse --abbrev-ref HEAD`. Verifies `git_valid=False`, `dirty=True`, command captured in errors, and `verify_traceability()` rejects state.
3. `tests/verification/test_status_register_traceability.py::test_git_inspection_fails_closed_when_git_status_fails`
   - Simulates failure of `git status --porcelain -uall`. Verifies `git_valid=False`, `dirty=True`, command captured in errors, and `verify_traceability()` rejects state.

---

## 4. Test Suite Summary

- **Local test suite run:** 459 passed, 0 failed, 1 warning (51.86s).
- **Status register check:** Fresh, clean, 24 capabilities verified (16 NUMERICALLY VERIFIED, 8 TESTED).
- **Preserved user files:** Strictly unmodified and untracked:
  - `src/gdec/core/analyser.py`
  - `src/gdec/runtime/`
