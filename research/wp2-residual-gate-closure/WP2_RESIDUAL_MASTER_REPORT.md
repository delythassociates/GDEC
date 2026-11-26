# GDEC WP2 — Residual Acceptance-Gate Closure Master Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/wp2-residual-gate-closure`  
**Implementation/evidence commit:** `20baa84cbb4ec305450e715a6a2b000a35ca0d3e`  
**Documentation closeout:** 2026-11-27  
**Status:** Technical acceptance gates complete; formal owner acceptance pending.

---

## 1. Executive Summary

This work package completes the remaining technical WP2 acceptance work and records the evidence without modifying production solver mathematics, estimator mathematics, or the preserved user-owned files (`src/gdec/core/analyser.py`, `src/gdec/runtime/`). The branch is ready for formal owner review; it is not declared owner-accepted by this report.

1. **WP2-A (Branch Coverage Gate):** Committed a measured calibration reference of **1043 / 1678 = 62.16%**, with a ratcheting floor of **62.15%**, and implemented `scripts/check_branch_coverage.py` with negative/positive tests. The later official GitHub Actions run on this branch reported **1044 / 1678 = 62.22%** in its Windows/Python 3.13 mutation-and-coverage job. These are distinct measurements and are reported separately.
2. **WP2-B (FEM & Estimator Mutation Coverage):** Expanded the targeted runtime mutation campaign to **20 mutants across 8 production modules**. The recorded campaign killed **20/20 (100%)**; this is a targeted campaign, not whole-repository mutation coverage.
3. **WP2-C (P1 Elasticity MMS Convergence Order):** The production `LinearElasticitySolver.solve()` path was tested using a smooth 2D vector manufactured solution. Plane stress observed (p_{L^2}=1.9714), (p_{H^1}=0.9864); plane strain observed (p_{L^2}=1.9705), (p_{H^1}=0.9876). The reported fits have (R^2) between 0.99995 and 0.99996.
4. **WP2-D (Adaptive QoI-vs-DOFs Baseline):** Locked a deterministic six-point DWR adaptive regression trajectory from **90 to 4716 DOFs**, with reference-QoI relative error falling from **29.81% to 0.45%**. This is a regression against a fine-mesh reference; it is not a certified error bound.
5. **WP2-E (Dependency Lockfile):** Committed the universal `uv.lock` (88 packages), changed the primary CI matrix and verification gates to use locked dependencies, and retained the separate unpinned upstream dependency-drift job.
6. **WP2-F (ADR-013 Consistency Audit):** Reconciled stale ADR-013 status wording with the recorded WP0 Session 2 owner authorization reference, without fabricating or embedding a verbatim owner quote that is not present in the repository history.

## 2. CI Verification

GitHub Actions run [45876161338](https://github.com/delythassociates/GDEC/actions/runs/45876161338), associated with implementation commit `20baa84cbb4ec305450e715a6a2b000a35ca0d3e`, completed **15/15 jobs successfully**:

- 12 operating-system/Python-version matrix jobs;
- status-register and traceability gate;
- mutation-resilience and branch-coverage gate;
- upstream dependency-drift check.

The Windows/Python 3.13 mutation-and-coverage job reported **452 passed, 14 skipped**, branch coverage **1044/1678 = 62.22%** against the **62.15%** floor, and **20/20 targeted mutants killed**. The log does not establish the exact `nvidia-smi` availability of that hosted runner; therefore its 62.22% result is recorded as the observed CI-job measurement, not re-labelled as the calibration environment.

This run verifies the implementation/evidence commit above. A documentation-only follow-up commit is recorded separately and will trigger its own CI workflow.

## 3. Evidence Index

All links below are repository-relative and portable:

- [Coverage methodology and baseline](COVERAGE_BASELINE.md)
- [Mutation results by module](MUTATION_RESULTS_BY_MODULE.md)
- [Elasticity MMS results](ELASTICITY_MMS_RESULTS.md)
- [Adaptive QoI-vs-DOFs results](ADAPTIVE_QOI_DOF_RESULTS.md)
- [Acceptance matrix](WP2_RESIDUAL_ACCEPTANCE_MATRIX.md)
- [Changelog](WP2_RESIDUAL_CHANGELOG.md)
- [Risk register](WP2_RESIDUAL_RISK_REGISTER.md)
- [Machine-readable coverage baseline](../wp2/coverage-baseline.json)
- [Machine-readable adaptive QoI baseline](../wp2/adaptive_qoi_dof_baseline.json)

## 4. Acceptance and Remaining Governance Step

The 17 technical/evidence gates in the residual acceptance matrix are recorded as passed. CI completion is now reflected in that matrix. The matrix does not substitute for formal owner acceptance.

**Next required action:** owner reviews the WP2 report, acceptance matrix, risk register and linked CI evidence, then explicitly records acceptance or returns specific findings. WP3 remains unstarted until that acceptance is recorded.

## 5. Scope Boundaries

- No production solver or estimator mathematics was changed in this closure package.
- The DWR trajectory remains an empirical/reference regression, not a certified bound.
- The 20-mutant campaign is targeted to eight modules; whole-repository mutation analysis remains deferred.
- The repository record references the Session 2 ADR-013 authorization but does not contain a verbatim owner statement.
- GitHub can verify the pushed branch and committed files, but cannot independently establish the state of a contributor's local uncommitted working tree.
