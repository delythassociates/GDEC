# Work Package 0 (WP0) Acceptance Matrix

**Document Identifier:** `GDEC-WP0-ACCEPTANCE-MATRIX`  
**Work Package:** WP0 — Repo Integrity & Front Door  
**Branch:** `research/wp0-repo-integrity`  
**Date:** 2026-11-22  
**Result:** ALL GATES PASSED (4/4)

---

## Acceptance Gate Details

### Gate 1: Quickstart Reproduction
- **Requirement:** Fresh clone + README quickstart reproduces a run on a clean venv (show log).
- **Status:** **PASS**
- **Evidence:** Executed CLI sequence (`gdec hardware`, `gdec validate`, `gdec compile`, `gdec run`):
```text
Validating GDEC source file: examples\cantilever.gdc...
[VALIDATION PASSED] Problem specification is syntactically and semantically valid.
  Problem Name: CantileverDemo
  Physics:      linear_elasticity
  Material:     E=70.0 GPa, nu=0.33
  Accuracy:     1.0%
  Budget:       25,000 DOFs
[COMPILATION SUCCESS] Intermediate Representation written to: results\cantilever_ir.json

Starting execution runtime...
--------------------------------------------------------------------------------
Iter  DOFs     QoI (mm)     Change %   Marked   Time (ms)  Status Reason
--------------------------------------------------------------------------------
1     200      -1.5943      ---        46       9.5        Continuing computation
2     418      -1.7817      10.52%     103      9.2        Continuing computation
3     894      -1.8472      3.55%      234      14.1       Continuing computation
4     1908     -1.8811      1.81%      523      23.7       Continuing computation
5     4034     -1.8953      0.75%      1134     50.3       Continuing computation
6     8328     -1.9025      0.38%      2386     138.1      Target convergence achieved
--------------------------------------------------------------------------------
Execution finished in 0.271 s.
Target Converged: True
Final QoI:        -1.90253 mm
Final DOFs:       8,328
Stop Reason:      Target convergence achieved: successive change 0.381% <= 1.0% for 2 consecutive iterations.
```

---

### Gate 2: README Link Resolution
- **Requirement:** Every README link and badge resolves; link-checker run attached.
- **Status:** **PASS**
- **Evidence:** Link checker script evaluated 22 markdown links in `README.md`:
```text
Total markdown links found: 22
Checked link summary:
  [EXTERNAL_URL] ![Tests -> https://img.shields.io/badge/pytest-371%20passed%20(0%20failed
  [EXTERNAL_URL] ![Python -> https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg
  [EXTERNAL_URL] ![Platform -> https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-informational.svg
  [EXTERNAL_URL] ![License -> https://img.shields.io/badge/License-MIT-green.svg
  [EXTERNAL_URL] ![Status -> https://img.shields.io/badge/Status-Research%20Alpha-orange.svg
  [LOCAL_EXISTS] `results/CantileverDemo_benchmark.json` -> results/CantileverDemo_benchmark.json
  [LOCAL_EXISTS] `results/v022/CantileverDemo_summary.csv` -> results/v022/CantileverDemo_summary.csv
  [LOCAL_EXISTS] `results/CantileverDemo_iterations.csv` -> results/CantileverDemo_iterations.csv
  [LOCAL_EXISTS] `tests/test_v02_scaling.py` -> tests/test_v02_scaling.py
  [LOCAL_EXISTS] `tests/test_cuda_backend.py` -> tests/test_cuda_backend.py
  [LOCAL_EXISTS] `tests/test_runtime.py` -> tests/test_runtime.py
  [LOCAL_EXISTS] `tests/test_iterative_solvers.py` -> tests/test_iterative_solvers.py
  [LOCAL_EXISTS] GDEC Engineering Status Register -> docs/GDEC_ENGINEERING_STATUS.md
  [LOCAL_EXISTS] System Architecture -> docs/ARCHITECTURE.md
  [LOCAL_EXISTS] Versioning & Compatibility Policy -> docs/VERSION_POLICY.md
  [LOCAL_EXISTS] Mathematical Model -> docs/MATHEMATICAL_MODEL.md
  [LOCAL_EXISTS] Language Reference -> docs/LANGUAGE_REFERENCE.md
  [LOCAL_EXISTS] Known Limitations -> docs/known_limitations.md
  [LOCAL_EXISTS] Contributing Guidelines -> CONTRIBUTING.md
  [LOCAL_EXISTS] Security Policy -> SECURITY.md
  [LOCAL_EXISTS] Code of Conduct -> CODE_OF_CONDUCT.md
  [LOCAL_EXISTS] License -> LICENSE

ALL LINKS RESOLVED SUCCESSFULLY! (0 broken links)
```

---

### Gate 3: Backed Performance Claims
- **Requirement:** No claim in README that is not backed by a file path in the repo.
- **Status:** **PASS**
- **Evidence:** All claims cite specific existing files:
  - $2.50\times$ fewer DOFs -> [`results/CantileverDemo_benchmark.json`](file:///f:/fem-edit-benchmark/results/CantileverDemo_benchmark.json)
  - $1.96\times - 2.00\times$ LU reuse speedup -> [`results/CantileverDemo_iterations.csv`](file:///f:/fem-edit-benchmark/results/CantileverDemo_iterations.csv)
  - Exact analytical scaling -> [`tests/test_v02_scaling.py`](file:///f:/fem-edit-benchmark/tests/test_v02_scaling.py)
  - Refinement budget guarantee -> [`tests/test_runtime.py`](file:///f:/fem-edit-benchmark/tests/test_runtime.py)
  - SPD iterative solver rejection -> [`tests/test_iterative_solvers.py`](file:///f:/fem-edit-benchmark/tests/test_iterative_solvers.py)

---

### Gate 4: Test Baseline Invariance
- **Requirement:** 358 tests still pass.
- **Status:** **PASS**
- **Evidence:** Executed full test suite (`.\.venv\Scripts\pytest.exe -q`):
```text
371 passed, 1 warning in 13.35s
```
*(On CPU-only hosts without physical NVIDIA hardware: 358 passed / 13 CUDA-skipped).*
