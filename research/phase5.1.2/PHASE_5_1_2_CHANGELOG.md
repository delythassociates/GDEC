# GDEC Phase 5.1.2 — Detailed Changelog

**Repository:** `delythassociates/GDEC`  
**Base Commit:** `17d997874370b90b2b2e4ae441711bf945ce2bec`  
**Target Branch:** `research/phase-5.1.2-evidence-integrity-closure`

---

## Summary of Changes

Phase 5.1.2 delivers comprehensive contract closure and verification hardening across the numerical backends, DSE evidence validation engine, and mechanical scaling models, supported by independent external FEM benchmark verification.

---

## 1. Core Numerical Backend (`src/gdec/core/backend/`)

### `spd_check.py`
- **Added `SPDVerificationStatus(str, Enum)`**:
  - `VERIFIED_SPD`: Structurally and spectrally verified to be positive definite.
  - `CALLER_ASSUMED_SPD`: Declared SPD by caller under `caller_certified_spd=True`.
  - `DEMONSTRABLY_NON_SPD`: Disproved via asymmetry, non-positive diagonal, or $\lambda_{\min} \le 0$.
  - `INCONCLUSIVE`: Spectral checks failed to converge or undetermined.
- **Added `CGEligibilityResult(tuple)`**:
  - Inherits from `tuple` to maintain exact backwards compatibility with tuple unpacking `n, lmin, lmax = verify_cg_eligibility(...)`.
  - Exposes `.status`, `.dimension`, and `.reasons` properties for rich error diagnostics and telemetry.
- **Dimension & Parameter Validation**:
  - Explicitly rejects matrices with dimension $N \le 0$ with `NumericalBackendError`.
  - Enforces `max_iter` type checking (must be integer $\ge 1$).

### `cpu.py`
- **Zero RHS Handling**: Added exact zero-vector short-circuit when $\|b\|_2 == 0$. Returns $x = 0$, $0$ iterations, $0.0$ residual immediately without executing iterative solvers.
- **Preconditioner Dimension Check**: Enforces `tuple(M.shape) == tuple(A.shape)`, raising `NumericalBackendError` on mismatch.
- **Diagnostics Return**: Emits `"spd_status": spd_status.value` in the result dictionary.

### `cuda.py`
- **Preconditioner Hardening**:
  - Explicitly rejects host CPU `LinearOperator` instances with `UnsupportedCapabilityError`.
  - Rejects GPU preconditioners lacking `is_spd=True` with `NumericalBackendError`.
  - Checks preconditioner shape matching against matrix dimension.
- **Device-Resident Validation**:
  - Implemented `_validate_device_resident_matrix` for matrices already in CuPy VRAM when `caller_certified_spd=True`.
  - Performs non-empty check, square shape check, positive diagonal check, and finite value check using CuPy array operations entirely on device.
  - Avoids host memory transfers and PCIe overheads during matrix audit.
- **Telemetry Enhancements**:
  - Emits `"spd_status"`, `"device_resident_validation"`, `"host_matrix_transfers"`, and `"preconditioner_status"` in return dictionary.
- **Zero RHS Handling**: Added device-resident zero-RHS short-circuit on GPU.

---

## 2. Decision Sufficiency Engine (`src/gdec/dse/`)

### `evidence.py`
- **Extended `ValidationStatus`**: Added `REJECTED`, `EXPIRED`, and `UNVALIDATED` statuses.
- **Added `EvidenceEligibility(str, Enum)`**:
  - `ACCEPTED`, `REJECTED`, `UNASSESSED`, `INCOMPATIBLE_MODEL`, `INCOMPATIBLE_DOMAIN`, `INSUFFICIENT_PROVENANCE`, `INSUFFICIENT_METRIC`, `MISSING`.
- **Added `RecordEvaluationReport`**: Dataclass capturing record ID, category, eligibility status, and diagnostic messages.
- **Implemented `EvidenceAssessment.evaluate_record_eligibility(...)`**:
  - Executes rigorous record-level audit evaluating expiration dates, whitespace provenance, domain compatibility, model consistency, and discredited flags.
  - Implements the strict category satisfaction policy: **A category is satisfied if and only if it has $\ge 1$ ACCEPTED record and 0 REJECTED records.** Any rejected record poisons the category and forces failure closed.

### `evaluator.py`
- **Hardened Gate 2 (Evidence Eligibility)**:
  - Replaces coarse category-presence check with detailed record-level audit.
  - Embeds `record_reports` in `DecisionResult` diagnostics.
  - Fails closed with `INSUFFICIENT_EVIDENCE` if any required category is unsatisfied or tainted by rejected records.
- **Hardened Gate 3 (Non-Omittable DWR Quality Gate)**:
  - If numerical quality or mesh discretisation error is declared in required evidence categories, missing DWR metrics unconditionally fails closed with `INSUFFICIENT_EVIDENCE`.
  - Exceeding DWR tolerance unconditionally forces `DecisionRecommendation.REFINE`.

---

## 3. Independent Numerical Validation & Tests

### `benchmarks/phase5_1_2/scaling/validate_scaling_independent.py`
- Standalone plane-stress cantilever plate elasticity benchmark using `scikit-fem` v12.0.2 on an unstructured triangular mesh ($1,280$ elements, $1,394$ DOFs).
- Solved directly via SciPy `spsolve` without using any GDEC code.
- Validates linear scaling law $J(E, P) = (P/P_0)(E_0/E)J_0$ across 5 parameter variations with max error $< 10^{-10}$.
- Proves quadratic scaling of compliance energy $C = f^T u \propto P^2/E$.

### `tests/`
- Added `test_phase5_1_2_dse_adversarial.py` (20 new adversarial tests).
- Added `test_independent_fem_validation.py` (3 new numerical validation tests).
- Extended `test_backend.py` and `test_cuda_backend.py` with 3 new contract verification tests.
- Total test count increased from 234 to 260 passed (100% passing).
