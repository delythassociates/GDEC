# WP2 Residual Closure — Branch Coverage Baseline & Ratcheting Gate

**Baseline Commit Measured:** `2abc1a2f0422539356ad928931fdced692088652`  
**Machine-Readable Baseline:** `research/wp2/coverage-baseline.json`  
**Gate Enforcement Script:** `scripts/check_branch_coverage.py`  
**Negative/Positive Gate Tests:** `tests/verification/test_coverage_gate.py`  

---

## 1. Measurement Methodology & Configuration

- Configured `[tool.coverage.run]` in `pyproject.toml`:
  - `branch = true`
  - `source = ["src/gdec"]`
  - `omit = ["src/gdec/core/analyser.py", "src/gdec/runtime/*"]` (untracked user-owned files not present in git or CI)
- **Locked CPU-only CI-equivalent baseline** (matching `ubuntu-latest` non-GPU CI runners using `uv sync --locked --extra test --extra amg` where `cupy-cuda12x` is not installed and 14 CUDA tests skip):
  - Command: `uv run --no-sync python -m pytest --cov=src/gdec --cov-branch --cov-report=json:coverage.json tests/`
  - Result: **452 passed, 14 skipped**, **1045 / 1678 branches covered = 62.2765%** (ratcheting floor set to **62.27%**).
- **Local NVIDIA GPU-enabled measurement** (with `cupy-cuda12x` installed and operational GPU):
  - Command: `.venv\Scripts\python.exe -m pytest --cov=src/gdec --cov-branch --cov-report=json:coverage.json tests/`
  - Result: **459 passed**, **1092 / 1678 branches covered = 65.08%** (`65.0775%`).

---

## 2. Ratcheting Policy

- `scripts/check_branch_coverage.py` reads the pytest-cov JSON report and `research/wp2/coverage-baseline.json`.
- It **fails closed** if:
  - Coverage JSON or baseline JSON is missing or malformed.
  - `num_branches <= 0` (rejects zero-branch or statement-only coverage reports).
  - `observed_pct < baseline_branch_coverage_pct` (`62.27%`).
- **How to raise the baseline:** After verified test additions increase branch coverage, a developer may manually update `baseline_branch_coverage_pct`, `covered_branches`, and `num_branches` in `research/wp2/coverage-baseline.json` via an audited commit. The floor must **never** be lowered automatically.

---

## 3. Gate Verification Tests (`tests/verification/test_coverage_gate.py`)

| Test Case | Scenario | Expected & Observed Outcome |
|---|---|---|
| `test_coverage_below_floor_fails` | `62.9% < 63.0%` | Raises `CoverageGateError`, CLI returns exit code `1` |
| `test_coverage_equal_to_floor_passes` | `63.0% == 63.0%` | Passes, CLI returns exit code `0` |
| `test_coverage_above_floor_passes` | `70.0% > 63.0%` | Passes, CLI returns exit code `0` |
| `test_missing_or_malformed_coverage_data_fails` | Missing file, bad JSON, missing `num_branches`, `num_branches == 0` | All raise `CoverageGateError` |
