# GDEC WP2 Final Mutation Classification and Test Coverage — Changelog

## [Unreleased] - 2026-11-23

### Fixed
- **Structured Pytest Exception Capture (`scripts/run_mutation_campaign.py`)**:
  - Replaced regex/string-based parsing of pytest console outputs with first-party structured reporting via `pytest_runtest_makereport` hook and `call.excinfo`.
  - Captures exact `exception_class` (from `call.excinfo.typename`), `exception_message`, `source_location`, and execution `phase` (`setup`, `call`, `teardown`).
  - Completely eliminated fallback to `UnknownException`.
- **Classification Engine & Baseline Fail-Fast (`scripts/run_mutation_campaign.py`)**:
  - Differentiates `KILLED` (expected assertion or explicit failure in `call` phase), `SURVIVED`, `ERROR` (`COLLECTION_ERROR`, `SETUP_ERROR`, `TEARDOWN_ERROR`, `UNEXPECTED_EXCEPTION`), `INVALID_MUTANT` (`INJECTION_ERROR`), and `INVALID_BASELINE`.
  - Baseline execution strictly asserts `BASELINE_PASS`. Baseline assertion failures, unexpected exceptions, collection errors, setup errors, teardown errors, or missing tests produce `INVALID_BASELINE` and immediately abort the campaign.
  - Implemented `validate_mutant_record` enforcing complete 12-field schema compliance.
- **CI Workflow Step Labeling (`.github/workflows/ci.yml`)**:
  - Renamed `Run bounded source mutation campaign` to `Run targeted production-function runtime mutation campaign` to accurately reflect test mechanics.

### Added
- **Teardown Error Negative Test (`tests/verification/test_mutation_resilience.py`)**:
  - Added `test_runner_teardown_error_produces_error` utilizing a generator fixture that yields successfully and raises during teardown, proving teardown failure produces `ERROR` with `phase="teardown"`, not `KILLED`.
- **Baseline Validation Negative Suite (`tests/verification/test_mutation_resilience.py`)**:
  - Added `TestBaselineValidation` with 6 dedicated tests covering baseline assertion failure, unexpected exception, collection failure, setup error, teardown error, and missing test node.
- **Runtime Error Rejection Test (`tests/verification/test_mutation_resilience.py`)**:
  - Added `test_runner_unexpected_runtime_error_produces_error_not_killed` verifying non-assertion crashes are classified as `ERROR` and never as `KILLED`.
- **Schema Validation Test (`tests/verification/test_mutation_resilience.py`)**:
  - Added `test_runner_schema_validation_rejects_incomplete_record`.
- **Isolated Fail-Closed Git Inspection Tests (`tests/verification/test_status_register_traceability.py`)**:
  - Added 3 independent tests verifying fail-closed handling and traceability rejection for failures of:
    - `git rev-parse HEAD`
    - `git rev-parse --abbrev-ref HEAD`
    - `git status --porcelain -uall`
