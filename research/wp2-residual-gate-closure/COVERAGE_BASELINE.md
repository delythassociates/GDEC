# WP2 Residual Closure — Branch Coverage Baseline & Ratcheting Gate

**Baseline commit measured:** `2abc1a2f0422539356ad928931fdced692088652`  
**Machine-readable baseline:** `research/wp2/coverage-baseline.json`  
**Gate enforcement script:** `scripts/check_branch_coverage.py`  
**Negative/positive gate tests:** `tests/verification/test_coverage_gate.py`

---

## 1. Measurement Methodology & Configuration

- Configured `[tool.coverage.run]` in `pyproject.toml`:
  - `branch = true`
  - `source = ["src/gdec"]`
  - `omit = ["src/gdec/core/analyser.py", "src/gdec/runtime/*"]` (untracked user-owned files not present in the tracked source tree or CI checkout).

### 1.1 Calibration reference and ratcheting floor

The committed calibration reference was recorded for the locked CPU/non-GPU-equivalent test profile:

- Test command: `uv run --no-sync python -m pytest --cov=src/gdec --cov-branch --cov-report=json:coverage.json tests/`
- Recorded calibration result: **1043 / 1678 branches = 62.16%**.
- Ratcheting floor committed in `research/wp2/coverage-baseline.json`: **62.15%**.
- The calibration measurement is the basis for the floor; it should not be described as an exact measurement from the later GitHub Actions run.

### 1.2 Official GitHub Actions run on the WP2 closure branch

GitHub Actions run [45876161338](https://github.com/delythassociates/GDEC/actions/runs/45876161338) tested implementation commit `20baa84cbb4ec305450e715a6a2b000a35ca0d3e` and completed **15/15 jobs successfully**.

The Windows/Python 3.13 mutation-and-coverage job logged:

- Test suite: **452 passed, 14 skipped**.
- Observed branch coverage: **1044 / 1678 = 62.22%**.
- Ratcheting floor: **62.15%** — passed.
- Targeted mutation campaign: **20/20 killed**, 0 invalid.

This is the observed result of that hosted CI job. The log does not explicitly establish whether `nvidia-smi` was present on that runner; the result is therefore not relabelled as the original calibration environment.

### 1.3 Separate local environment measurements

- Local CPU environment with `nvidia-smi` present: **1045 / 1678 = 62.28%**.
- Local NVIDIA GPU-enabled run with `cupy-cuda12x` operational: **459 passed**, **1092 / 1678 = 65.08%** (65.0775%).

These are environment-specific observations, not alternative CI calibration baselines.

---

## 2. Ratcheting Policy

- `scripts/check_branch_coverage.py` reads the pytest-cov JSON report and `research/wp2/coverage-baseline.json`.
- It fails closed if:
  - Coverage JSON or baseline JSON is missing or malformed.
  - `num_branches <= 0` (rejecting zero-branch or statement-only coverage reports).
  - `observed_pct < baseline_branch_coverage_pct` (62.15%).
- **How to raise the baseline:** After verified test additions increase branch coverage, a developer may manually update `baseline_branch_coverage_pct`, `covered_branches`, and `num_branches` in `research/wp2/coverage-baseline.json` via an audited commit. The floor must never be lowered automatically.

---

## 3. Gate Verification Tests

The recorded gate suite includes four negative/positive tests in `tests/verification/test_coverage_gate.py`, covering below-floor rejection, equal-floor acceptance, above-floor acceptance, and missing/malformed/zero-branch input rejection.
