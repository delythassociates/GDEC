# WP2 Residual Acceptance-Gate Closure — Changelog

## [Unreleased] - 2026-11-26

### Added
- **Branch Coverage Gate (`WP2-A`)**:
  - Added `[tool.coverage.run]` (`branch = true`, `source = ["src/gdec"]`, omitting untracked user-owned `src/gdec/core/analyser.py` and `src/gdec/runtime/*`) in `pyproject.toml`.
  - Committed measured branch coverage baseline in `research/wp2/coverage-baseline.json` (`62.28%`, `1045 / 1678` branches in locked CPU-only CI environment).
  - Created `scripts/check_branch_coverage.py` enforcing ratcheting floor and failing closed on missing, malformed, or zero-branch data.
  - Added `tests/verification/test_coverage_gate.py` with 4 negative/positive tests.
- **Core FEM & Estimator Mutation Coverage (`WP2-B`)**:
  - Expanded `scripts/run_mutation_campaign.py` with 6 new mathematically meaningful mutants (`MUT-FEM-03`, `MUT-EST-01` through `MUT-EST-05`) covering `LinearElasticitySolver.assemble_stiffness`, `FacetTractionJumpEvaluator.evaluate`, `DualWeightEvaluator.compute_edge_bubble_integral`, `ElementResidualEvaluator.evaluate`, `DWREstimator.estimate`, and `RefinementEstimator.compute_zz_recovery_indicator`.
  - Added `per_module_summary` reporting to `results/mutation_campaign_report.json`.
- **P1 Elasticity MMS Convergence Verification (`WP2-C`)**:
  - Created `tests/verification/test_elasticity_mms_convergence.py` exercising `LinearElasticitySolver.solve()` on a smooth 2D vector manufactured solution under both `plane_stress` and `plane_strain`.
- **Adaptive QoI-vs-DOFs Regression Baseline (`WP2-D`)**:
  - Locked deterministic 5-step DWR adaptive trajectory in `research/wp2/adaptive_qoi_dof_baseline.json`.
  - Created `tests/verification/test_adaptive_qoi_regression.py` verifying strict DOF ordering, monotonic error reduction, non-certified DWR labelling, and no regression against the locked baseline.
- **Dependency Lockfile (`WP2-E`)**:
  - Added `pytest-cov>=5.0.0` to `[project.optional-dependencies].test` in `pyproject.toml`.
  - Generated universal cross-platform `uv.lock` covering Python 3.10–3.13 across Linux, Windows, and macOS.
  - Updated `.github/workflows/ci.yml` primary matrix, status register gate, and coverage/mutation gate to use `uv sync --locked --extra test --extra amg` and `uv run --no-sync`, while keeping `upstream-dependency-drift` unpinned.

### Fixed
- **ADR-013 Consistency Audit (`WP2-F`)**:
  - Reconciled stale `(OWNER MUST CONFIRM)` heading and `*Action Required:*` consequence in `research/phase5/PHASE_5_DECISION_REGISTER.md` to match the recorded `Confirmed by Owner (Session 2 Owner Authorization)` status without fabricating new owner statements.
