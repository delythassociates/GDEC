# WP2 Residual Acceptance-Gate Closure — Acceptance Matrix

| Gate | Acceptance Requirement | Observed Evidence | Status |
|---|---|---|---|
| **A1** | Branch coverage measured and baseline committed | `research/wp2/coverage-baseline.json` (`62.15%` CI non-GPU floor; `1043 / 1678 = 62.16%` without `nvidia-smi`, `1045 / 1678 = 62.28%` with `nvidia-smi`, `65.08%` with GPU) | **PASS** |
| **A2** | CI enforces the branch coverage floor | `.github/workflows/ci.yml` runs `scripts/check_branch_coverage.py` | **PASS** |
| **A3** | Negative coverage-gate tests pass | `tests/verification/test_coverage_gate.py` (4/4 passed) | **PASS** |
| **B1** | FEM and estimator mutation targets audited | `MUTATION_RESULTS_BY_MODULE.md` documents all 8 modules & 20 targets | **PASS** |
| **B2** | Estimator mutation campaign executed | `scripts/run_mutation_campaign.py` executed 20/20 mutants (`MUT-EST-01..05`, `MUT-FEM-03` + 14 existing) | **PASS** |
| **B3** | Per-module mutation scores and all survivors classified | `per_module_summary` in `mutation_campaign_report.json`; 20/20 killed, 0 survivors | **PASS** |
| **C1** | GDEC P1 elasticity MMS convergence-order test executed | `tests/verification/test_elasticity_mms_convergence.py` (2/2 passed: $p_{L^2} \approx 1.97$, $p_{H^1} \approx 0.99$) | **PASS** |
| **D1** | Adaptive QoI-versus-DOFs dataset generated and locked | `research/wp2/adaptive_qoi_dof_baseline.json` (6 steps, 90 to 4716 DOFs) | **PASS** |
| **D2** | Adaptive regression test passes | `tests/verification/test_adaptive_qoi_regression.py` (1/1 passed) | **PASS** |
| **E1** | Dependency lockfile committed | Universal `uv.lock` (88 packages) committed | **PASS** |
| **E2** | Primary CI matrix uses locked dependencies | `.github/workflows/ci.yml` uses `uv sync --locked --extra test --extra amg` | **PASS** |
| **E3** | Separate latest-dependency drift job remains operational | `upstream-dependency-drift` job retained unpinned with `pip install --upgrade` | **PASS** |
| **F1** | ADR-013 wording reconciled without fabricated authorization | `research/phase5/PHASE_5_DECISION_REGISTER.md` heading/consequence reconciled | **PASS** |
| **G1** | Existing test suite remains green | Local: 452 passed, 14 skipped (`uv sync --locked --extra test --extra amg`) | **PASS** |
| **G2** | All 15 CI jobs pass | Pending CI run on pushed branch `research/wp2-residual-gate-closure` | **IN PROGRESS** |
| **G3** | Preserved user files remain untouched | `src/gdec/core/analyser.py` and `src/gdec/runtime/` untracked and unmodified | **PASS** |
| **G4** | Working tree clean and evidence traceable | Pending final commit & push | **IN PROGRESS** |
