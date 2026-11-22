# GDEC WP2 Targeted Final Corrections — Changelog

## [Unreleased] - 2026-11-23

### Fixed
- **DSE Mutation Definitions (`scripts/run_mutation_campaign.py`, `src/gdec/verification/mutation_harness.py`)**:
  - Corrected `MUT-DSE-01` and `MUT-DSE-02` to use `self.baseline.E_0` and `self.baseline.P_0` instead of non-existent `self.reference`.
  - Mathematically formulated scaling mutations: modulus scaling multiplied by $(E_0/E)^2$ and inverted load scaling multiplied by $(P_0/P)^2$, producing valid perturbed evaluations and genuine mathematical `AssertionError` failures.
  - Corrected wrapper signatures for `MUT-DSE-03`, `MUT-DSE-04`, and `MUT-DSE-05` to accept `*args, **kwargs` and mutate `res.recommendation` and `res.expected_loss_release` rather than non-existent `res.expected_loss`.
- **Mutation Runner Classification Hardening (`scripts/run_mutation_campaign.py`, `tests/verification/test_mutation_resilience.py`)**:
  - Implemented `MutationExecutionCapture` and `ExecutionResult` distinguishing `KILLED` (genuine test failure), `SURVIVED` (passing mutant), `ERROR` (collection/setup/teardown error), `INVALID_MUTANT` (injection/attribute error), and `INVALID_BASELINE` (baseline failure).
  - Added 6 isolated negative tests in `test_mutation_resilience.py` to ensure injection crashes or runner bugs are never misreported as kills.
- **Fail-Closed Git Inspection (`src/gdec/verification/status_register.py`, `tests/verification/test_status_register_traceability.py`)**:
  - Updated `get_git_info()` to capture errors across `git rev-parse HEAD`, `git rev-parse --abbrev-ref HEAD`, and `git status --porcelain -uall`. Returns `git_valid: bool`, `git_errors: List[str]`, and sets `dirty = True` when invalid. Added `GitInspectionError`.
  - Updated `verify_traceability()` to fail closed when `git_valid` is False or when recorded/live commit SHA is "unknown".
  - Added 4 isolated negative tests in `test_status_register_traceability.py`.
- **Status-Register Evidence Level Policy (`src/gdec/verification/status_register.py`)**:
  - Enforced policy: automated unit test suite execution alone cannot grant `INDEPENDENTLY VALIDATED` (capped at `NUMERICALLY VERIFIED`).
  - Added policy verification test `test_unit_tests_cannot_grant_independently_validated`.
- **Kirsch Benchmark Scope Qualification (`tests/verification/test_reference_library.py`, `src/gdec/verification/reference_problems.py`)**:
  - Adopted Option B: Renamed `test_ref_06_kirsch_production_defect_sensitivity` to `test_ref_06_kirsch_reference_formulation_sensitivity`.
  - Documented that Kirsch evaluates reference model constitutive formulation sensitivity; production solver defect sensitivity remains open/deferred because `LinearElasticitySolver` is currently coupled to rectangular `GDECMesh`.
  - Documented stress recovery at $(0, a)$ as area-weighted one-ring patch centroid average.
- **Lamé Discrete Error Norm Qualification (`tests/verification/test_reference_library.py`, `src/gdec/verification/reference_problems.py`)**:
  - Qualified error norm in REF-05 as an "area-weighted centroid-sampled discrete error norm" without claiming continuously integrated finite-element $L_2$ norm.
