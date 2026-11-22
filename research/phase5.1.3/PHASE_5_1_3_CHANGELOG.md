# GDEC Phase 5.1.3 — Detailed Changelog

**Repository:** `delythassociates/GDEC`  
**Base Commit:** `33aed0202aa5f4c359c9df3cb8d28e3a7753f475`  
**Target Branch:** `research/phase-5.1.3-validation-and-ci-closure`

---

## 1. Decision Sufficiency Engine (`src/gdec/dse/`)

### `evaluator.py`
- **Bound DWR Metric Selection to Eligible Records**:
  - Filtered candidate discretization error records to those satisfying `is_acceptable == True` from Gate 2.
  - Excluded ineligible, unassessed, expired, rejected, or non-DWR records.
  - Implemented deterministic conflict resolution: if multiple eligible records provide conflicting numerical metrics, evaluation fails closed with `INSUFFICIENT_EVIDENCE`.
- **Enforced Metric Semantics and Dimensional Consistency**:
  - Validated that `effective_dwr` is finite and non-negative.
  - Verified physical units: record `units` must match `contract.qoi.unit` (case-insensitive).
  - Enforced reference scale requirement: `evidence_assessment.reference_scale` must be non-null, finite, and $> 10^{-12}$. Silent fallback to threshold limit eliminated.
- **Enhanced Diagnostics & Data Models**:
  - Added `selected_dwr_record_id: Optional[str] = None` to `DecisionEvaluationResult` dataclass and dictionary serialization.
  - Attached `selected_dwr_record_id` to diagnostics dictionary in both conclusive and insufficient results.

### `evidence.py`
- Added duplicate record ID auditing: detects identical record IDs with conflicting provenance, validation status, or numerical metrics, and emits auditable refusal reasons.

---

## 2. Independent Reference FEM Validation (`benchmarks/` & `tests/`)

### `benchmarks/phase5_1_2/scaling/validate_scaling_independent.py`
- **Reconciled Authoritative Configuration**: Established $L = 5.0\text{ mm}, H = 1.0\text{ mm}, E_0 = 210,000\text{ MPa}, P_0 = 1,000\text{ N}, nx=41, ny=17$ as the single authoritative benchmark.
- **Corrected Residual Formulation**:
  - Partitioned degrees of freedom into free ($1,360$ DOFs) and clamped ($34$ DOFs).
  - Evaluated free-DOF relative equilibrium residual: $\|\mathbf{f}_c - K_c \mathbf{u}_{\text{free}}\|_2 / \|\mathbf{f}_c\|_2 = 2.38 \times 10^{-11} \ll 10^{-10}$.
  - Evaluated clamped wall reaction forces separately: total vertical reaction $R_y = 1,000.0\text{ N}$ (exact static equilibrium balance with load $P_0$).
- **Regenerated Raw Observations**: Emitted complete data rows with free/clamped DOF partitions to `research/phase5.1.2/scaling/INDEPENDENT_SKFEM_RAW_RESULTS.csv` and `research/phase5.1.3/scaling/INDEPENDENT_SKFEM_RAW_RESULTS.csv`.

### `tests/test_independent_fem_validation.py`
- Synchronized test fixture to authoritative benchmark geometry ($5.0 \times 1.0\text{ mm}$, $1,280$ elements, $1,394$ DOFs).
- Reassembles stiffness matrix and load vector independently for each parameter variation.
- Added assertions for free-DOF residual ($< 10^{-10}$) and vertical reaction force equilibrium balance ($< 10^{-7}$).

---

## 3. Adversarial & Regression Testing (`tests/`)

### `tests/test_phase5_1_3_dse_adversarial.py`
- Added 15 new adversarial test cases covering:
  - Accepted record followed by rejected record in same category (category poisoning).
  - Accepted record followed by incompatible-model or incompatible-domain record.
  - Accepted record followed by unassessed record.
  - Conflicting DWR values across eligible records.
  - Incompatible metric units (MPa vs mm).
  - Missing or near-zero reference scale.
  - Wrong category used as DWR evidence.
  - DWR metric supplied by expired record.
  - Duplicate records with conflicting provenance.
  - Caller-supplied `dwr_indicator` attempting to bypass missing eligible evidence.
  - Negative DWR metric.
  - Diagnostics verification of `selected_dwr_record_id`.

---

## 4. Continuous Integration & Repository (`.github/workflows/`)

### `.github/workflows/ci.yml`
- Added `"research/**"` to `push.branches` so pushes to research branches trigger GitHub Actions.
- Added `benchmarks` to `python -m compileall -q src tests benchmarks`.
- Preserved Python test matrix `["3.10", "3.11", "3.12"]` and PR triggers on `main`.
