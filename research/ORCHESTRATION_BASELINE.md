# GDEC Orchestration Baseline & Repository Health Audit

**Date:** 2026-11-22  
**Baseline Git Ref:** `research/phase-5.2.1b-expression-input-integrity` @ `7cd97381b5dee3d5c6a432a80b845fc2a369a661`  
**Parent / Remote Baseline:** `origin/research/phase-5.2.1b-expression-input-integrity` (in sync)  
**Author:** Lead Engineering Research Orchestrator (Phase 0 Audit)

---

## 1. Test Suite & Execution Verification

- **Total Test Items Collected:** 371 items.
- **Reference Baseline Specification:** 358 passed / 13 CUDA skips (on CPU-only nodes lacking physical NVIDIA hardware).
- **Host Execution Verification (Local Host with Operational NVIDIA GPU):**
  - **Result:** `371 passed, 1 warning in 12.58s` (exit code 0).
  - **CUDA Skips:** 0 (all 13 hardware GPU tests in `tests/test_cuda_backend.py` executed and passed on local NVIDIA device).
  - **Deprecation / Environment Warnings:** 1 warning (`cupy/_environment.py:286: UserWarning: CUDA path could not be detected. Set CUDA_PATH environment variable if CuPy fails to load.`).
  - **Execution Command:** `.\.venv\Scripts\pytest.exe -rs`
- **Coverage Status:**
  - `pytest-cov` is not bundled inside the offline `.venv` environment; coverage measurement is deferred to CI container environments (or when offline wheel is installed in WP2).
- **CI State (`.github/workflows/ci.yml`):**
  - Runs on `ubuntu-latest` across Python matrix: `["3.10", "3.11", "3.12"]`.
  - Python 3.13 is missing from CI matrix.
  - Windows and macOS test runners are currently absent from CI matrix (despite repository docs claiming Windows 10/11 platform focus).

---

## 2. Environment & Dependency Freshness

- **Python Runtime:** Python 3.13.14 (`win32`)
- **Key Installed Scientific Packages:**
  - `numpy`: 2.5.5
  - `scipy`: 1.18.1
  - `scikit-fem`: 12.0.2
  - `cupy-cuda12x`: 14.2.0
  - `pyamg`: 5.4.1
  - `pydantic`: 2.14.4 (core: 2.50.5)
  - `pytest`: 9.2.0
  - `sympy`: 1.14.0
  - `lark`: 1.3.1
- **Upstream Drift / Known Vulnerabilities:**
  - Sandboxed execution environment operates in offline / network-isolated mode (Rule R8 compliance). Network-dependent `pip list --outdated` was not executed. Version verification relies on local wheel freeze.

---

## 3. Repository Hygiene Audit

- **Binary Zips Tracked in Version Control:**
  - `GDEC_v0.2.2_PRIVATE_REVIEW.zip` (294,127 bytes, committed in initial commit `789f1f1`).
  - `materials-simulation-skills-main.zip` (committed in initial commit `789f1f1`).
  - *Recommendation:* Address in WP0 via formal justification table and removal from working tree without rewriting git history.
- **Legacy Scratch Directory Tracked in Version Control:**
  - 6 files under `scratch/` committed in `789f1f1`:
    - `scratch/regenerate_v022_benchmarks.py`
    - `scratch/test_stage1_reference_reconciliation.py`
    - `scratch/test_stage2_equal_accuracy_reconciliation.py`
    - `scratch/test_stage4_heuristic_correlation_deep.py`
    - `scratch/test_stage6_budget_and_cost_model_deep.py`
    - `scratch/test_stage8_performance_deep.py`
  - *Recommendation:* Move to `docs/archive/` or remove from working tree in WP0.
- **Stale `README.md` Front Door on `main` and `HEAD`:**
  - Test badge reads `42 passed` (actual suite has 371 tests).
  - Platform badge claims `Windows 10/11` only (CI actually runs Ubuntu Linux).
  - Compute description states `backend = cpu` with no mention of Phase 5.x CUDA backend or Decision Sufficiency Engine.
  - Quickstart references non-standard directory paths (`cd fem-edit-benchmark`).
  - Contains absolute local file links (`file:///f:/fem-edit-benchmark/...`).
- **Strictly Preserved Untracked User Assets:**
  - `src/gdec/core/analyser.py` (preserved untracked).
  - `src/gdec/runtime/` (preserved untracked).

---

## 4. Documentation Sprawl Audit

- **Docs File Count:** 58 Markdown files in `docs/` root and subdirectories.
- **Structure Defect:** ~45 historical audit reports, phase-specific remediation memos, and temporary notes sit alongside primary living specifications (`language_specification.md`, `ARCHITECTURE.md`).
- **Reports Directory:** Multiple overlapping directories (`reports/v021/`, `reports/v022/`, `research/phase5.1.x/`).
- *Remediation Plan (WP0 & WP7):* Consolidate historical audit artifacts into `docs/archive/` with a machine-readable index; maintain single authoritative living specs for architecture, language, IR, and verification.

---

## 5. Git Branch Stack & Ahead-of-Main Commit Audit

`main` is anchored at initial release commit `789f1f1`. The research branch stack represents 94 commits of verified mathematical and architectural development:

| Branch / Ref | Ahead of `main` | Behind `main` | Note |
|---|---|---|---|
| `main` | 0 | 0 | v0.2.2 baseline release |
| `remediation/v0.2.3-review` | 1 | 0 | Post-v0.2.2 review checkpoint |
| `audit/v0.2.2-deep-review` | 37 | 0 | Phase 4.1.4 closure baseline (PR #1) |
| `phase-c/amendment-3.2` | 37 | 0 | Phase C branch tip |
| `research/phase-5-parallel-engineering` | 38 | 0 | Phase 5.0 orchestrator baseline |
| `research/phase-5.1-prototypes` | 39 | 0 | Phase 5.1 initial prototypes |
| `research/phase-5.1.1-correctness-remediation` | 40 | 0 | Phase 5.1.1 numerical corrections |
| `research/phase-5.1.2-evidence-integrity-closure` | 41 | 0 | Phase 5.1.2 independent verification |
| `research/phase-5.1.3-validation-and-ci-closure` | 43 | 0 | Phase 5.1.3 audited release baseline |
| `research/phase-5.2-foundational-types` | 84 | 0 | Phase 5.2 foundational type system |
| `research/phase-5.2.1-eir-semantic-validation` | 88 | 0 | EIR semantic validation |
| `research/phase-5.2.1-expression-hardening` | 91 | 0 | EIR expression hardening |
| `research/phase-5.2.1b-expression-input-integrity` | 94 | 0 | Current tip (`7cd9738`) |

---

## 6. Phase 5.2 Governance Status

- **Status in Decision Register:** Added `ADR-013: Phase 5.2 Execution Authorization (OWNER MUST CONFIRM)` to `research/phase5/PHASE_5_DECISION_REGISTER.md`.
- **Verdict:** Provisional progression authorized to proceed with Phase 0 baseline triage and independent work packages without blocking; formal ratification queued for project owner review.
