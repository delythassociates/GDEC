# GDEC Phase C Amendment 2 — Continuous Integration Evidence

**Workflow Specification:** `.github/workflows/ci.yml`  
**Configuration File:** `pyproject.toml`  
**CI Matrix Targets:** Ubuntu (latest) and Windows (latest) across Python 3.10, 3.11, 3.12, 3.13 (8 execution environments).  
**Trigger Rules:** Push events on `main`, `phase-a/**`, `phase-b/**`, `phase-b1/**`, `phase-c/**`, `remediation/**` and tags `prereg-*`.

---

## 1. Local CI Verification Evidence

All pipeline verification stages were executed locally on Windows 11 (AMD64, CPython 3.13.14):

1. **Ruff Code Quality Inspection:**
   `ruff check src tests`
   *Result:* Passed with 0 errors and 0 warnings.
2. **Mypy Static Type Checking:**
   `mypy src/gdec`
   *Result:* Passed with 0 errors across 42 source files.
3. **Unit, Integration, and Regression Suite:**
   `pytest tests -v --durations=10 -m "not confirmatory"`
   *Result:* **157 passed in 49.3s** (0 failures, 0 errors).
4. **Numerical Verification Suite:**
   `pytest tests/test_dwr_consistency.py tests/test_dwr_mutations.py tests/test_phase_b1_timing.py tests/test_phase_b_geometries.py -v`
   *Result:* 27 passed.
5. **Pure Wheel Distribution Build:**
   `python -m build --wheel`
   *Result:* Built `dist/gdec-0.2.2-py3-none-any.whl`, verified presence of `gdec.lark` grammar file.
6. **Isolated Sandbox Installation & CLI Smoke Test:**
   *Result:* Successfully installed wheel in clean environment; verified `gdec hardware`, `gdec validate`, `gdec compile`.

---

## 2. Hosted GitHub Actions CI Linkage

- **Repository:** `delythassociates/GDEC`
- **Workflow Path:** `.github/workflows/ci.yml`
- **Workflow Name:** `GDEC CI & Verification Matrix`
- **Branch Target:** `phase-c/amendment-2`
- **Tag Target:** `prereg-c-amendment-2`
- **Exclusion Policy:** Confirmatory experiment suites (Tier 1 40 configs, Tier 2 10 configs, Tier 3 80 cases) are strictly excluded from default CI execution via marker `-m "not confirmatory"`.
- **Workflow Triggers:** Pushing `phase-c/amendment-2` and `prereg-c-amendment-2` triggers the 8-job GitHub Actions matrix across Ubuntu and Windows runner environments.
