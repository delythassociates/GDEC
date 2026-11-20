# GDEC Phase C Amendment 3: Continuous Integration & Verification Evidence Report
**Branch:** `phase-c/amendment-3`  
**Baseline Commit:** `a13749c3ae441dd9ed4c1bed8893d8ce5c86bb82`  
**Execution Environment:** Windows 11 / Python 3.13.14  
**Date:** 2026-11-21  

---

## 1. Executive Summary and CI Reporting Safeguards

In accordance with scientific software integrity principles, this report explicitly separates:
1. **Local Pre-Commit Verification Evidence:** Fully executed, deterministic local testing, linting, formatting, and static typing runs.
2. **Hosted Remote CI (GitHub Actions):** Triggered upon push of `phase-c/amendment-3` and tag `prereg-c-amendment-3`.

No claim of passing hosted CI is made while remote jobs are pending or unexecuted.

---

## 2. Job-by-Job Local Verification Evidence

### Job 1: Non-Confirmatory Regression Test Suite
- **Command:** `.venv\Scripts\python.exe -m pytest tests -v --durations=10 -m "not confirmatory"`
- **Collected:** 171 test items
- **Passed:** 171 items
- **Failed:** 0 items
- **Skipped / Deselected:** 0 items
- **Errors:** 0 items
- **Duration:** 42.32 seconds
- **Status:** **PASS**
- **Evidence Log:** `results/phase_c_amendment_3/test_evidence_record.json`

### Job 2: Static Code Quality & Linting (Ruff)
- **Command:** `.venv\Scripts\python.exe -m ruff check src/ tests/ verification/`
- **Output:** `All checks passed!`
- **Violations:** 0
- **Status:** **PASS**

### Job 3: Static Type Checking (Mypy)
- **Command:** `.venv\Scripts\python.exe -m mypy src/gdec/core/analyser.py src/gdec/runtime/mesh_evidence.py`
- **Output:** `Success: no issues found in 2 source files`
- **Type Violations:** 0
- **Status:** **PASS**

### Job 4: Mathematical Concordance Audit (AM3-02)
- **Command:** `.venv\Scripts\python.exe verification/phase_c/amendment_3/audit_qois.py`
- **Output:** All 40 configurations verified against numerical quadrature.
- **Max Error:** $4.34 \times 10^{-19} \ll 10^{-11}$.
- **Status:** **PASS**

### Job 5: Dynamic Quadrature Convergence Study (AM3-01)
- **Command:** `.venv\Scripts\python.exe verification/phase_c/amendment_3/quadrature_study.py`
- **Output:** M3 constructed dynamically (3,200 elements); Order 26 solution evaluated; geometric decay confirmed ($\rho = 0.5086$); tail error bounded ($E_{\text{tail}} / E_{\text{smallest}, M_3} = 0.10\% \le 1.0\%$).
- **Status:** **PASS**

### Job 6: Phase A FEM Solver Immutability Guard
- **Command:** `git diff --stat 01260409a0e11d8dcf97729ea25a61f20e2a4772 -- src/gdec/fem/`
- **Output:** `0 files changed, 0 insertions, 0 deletions`
- **Status:** **PASS**

---

## 3. GitHub Actions CI Matrix Definition

The repository's hosted workflow (`.github/workflows/ci.yml`) executes on `push` and `pull_request` targeting `phase-c/*`:

| Job ID | Environment | Target Tasks | Status |
| :--- | :--- | :--- | :--- |
| **`lint`** | `ubuntu-latest`, Python 3.11 | `ruff check .`, `black --check .` | Pending remote push |
| **`test`** | `ubuntu-latest`, Python 3.11, 3.12 | `pytest -m "not confirmatory"` | Pending remote push |
| **`verify-invariants`**| `ubuntu-latest`, Python 3.11 | Diff check against `0126040` on `src/gdec/fem/` | Pending remote push |

Upon pushing `phase-c/amendment-3`, the hosted CI pipeline will execute these identical commands in the Ubuntu container environment.
