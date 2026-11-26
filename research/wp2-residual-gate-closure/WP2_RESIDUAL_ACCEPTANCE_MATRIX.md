# WP2 Residual Acceptance-Gate Closure — Acceptance Matrix

**Implementation/evidence commit:** `20baa84cbb4ec305450e715a6a2b000a35ca0d3e`  
**CI run:** [45876161338 — 15/15 jobs successful](https://github.com/delythassociates/GDEC/actions/runs/45876161338)  
**Review status:** Technical gates passed; formal owner acceptance pending.

| Gate | Acceptance Requirement | Observed Evidence | Status |
|---|---|---|---|
| **A1** | Branch coverage calibration and ratcheting floor committed | `research/wp2/coverage-baseline.json`: calibration reference 1043/1678 = 62.16%; floor 62.15%. Latest official CI gate job reported 1044/1678 = 62.22%. | **PASS** |
| **A2** | CI enforces the branch coverage floor | `.github/workflows/ci.yml` invokes `scripts/check_branch_coverage.py`; official gate job passed. | **PASS** |
| **A3** | Negative/positive coverage-gate tests pass | `tests/verification/test_coverage_gate.py` (4 tests passed in recorded gate run). | **PASS** |
| **B1** | FEM and estimator mutation targets audited | `MUTATION_RESULTS_BY_MODULE.md` documents 20 targeted mutants across 8 modules. | **PASS** |
| **B2** | Targeted FEM/estimator mutation campaign executed | `scripts/run_mutation_campaign.py`; recorded result 20/20 mutants killed. | **PASS** |
| **B3** | Per-module mutation scores and survivors classified | `results/mutation_campaign_report.json` and CI gate logs; 20 killed, 0 survived, 0 invalid in the targeted campaign. | **PASS** |
| **C1** | P1 elasticity MMS convergence-order verification executed | `tests/verification/test_elasticity_mms_convergence.py`; plane stress/strain fits approximately (p_{L^2}=1.97), (p_{H^1}=0.99). | **PASS** |
| **D1** | Adaptive QoI-versus-DOFs dataset generated and locked | `research/wp2/adaptive_qoi_dof_baseline.json`; six recorded points, 90 to 4716 DOFs. | **PASS** |
| **D2** | Adaptive regression test passes | `tests/verification/test_adaptive_qoi_regression.py`; 1 test passed. DWR is explicitly not certified. | **PASS** |
| **E1** | Dependency lockfile committed | Universal `uv.lock`, 88 packages. | **PASS** |
| **E2** | Primary CI matrix uses locked dependencies | Primary matrix uses `uv sync --locked --extra test --extra amg`. | **PASS** |
| **E3** | Latest-dependency drift job remains operational | Separate `upstream-dependency-drift` job remains unpinned and passed in the recorded run. | **PASS** |
| **F1** | ADR-013 wording reconciled without fabricated authorization | `research/phase5/PHASE_5_DECISION_REGISTER.md` reflects the recorded Session 2 authorization reference. Verbatim owner text is not embedded in git history. | **PASS** |
| **G1** | Existing test suite remains green in the recorded locked environment | Windows/Python 3.13 gate job: 452 passed, 14 skipped, 0 failed. | **PASS** |
| **G2** | All required CI jobs complete successfully | Run [45876161338](https://github.com/delythassociates/GDEC/actions/runs/45876161338): 15/15 jobs completed successfully. | **PASS** |
| **G3** | Preserved user files remain untouched by this work package | Change scope and branch diff exclude modifications to `src/gdec/core/analyser.py` and `src/gdec/runtime/`; they remain outside tracked repository changes. | **PASS** |
| **G4** | Closure report and supporting evidence are committed and traceable on the remote branch | The branch tree contains this matrix, master report, risk register, changelog, coverage, mutation, MMS and adaptive evidence records. Local uncommitted working-tree state is not remotely observable and is not asserted here. | **PASS** |

---

## Interpretation

- **17/17 technical and evidence gates are recorded PASS.**
- The 62.16% calibration reference, 62.22% latest CI-job measurement, 62.28% local CPU-with-`nvidia-smi` measurement and 65.08% local GPU measurement are distinct observations; do not interchange them.
- The targeted mutation campaign is not whole-repository mutation coverage.
- The adaptive DWR regression is not a certified numerical error bound.
- **Formal owner acceptance remains pending.** This matrix records evidence status; it does not itself authorize WP3.
