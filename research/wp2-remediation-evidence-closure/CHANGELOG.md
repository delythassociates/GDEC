# GDEC WP2 Final Evidence-Integrity Remediation — Changelog

## [WP2-Remediation-Evidence-Closure] - 2026-11-23

### Added
- `src/gdec/verification/status_register.py`:
  - Added `required_test_node_ids: List[str]` and `verification_criteria: str` to `CapabilityEntry`.
  - Added explicit test node IDs and criteria to all 24 capabilities in `SYSTEM_CAPABILITIES`.
  - Added `get_provenance_info()` to capture execution context (`is_ci`, `github_run_id`, `github_workflow`, `github_sha`, `local_execution`).
  - Added collection error tracking and exit code tracking to `PytestCollector`.
  - Added `repo_dir` argument to `get_git_info` and `verify_traceability` to enable isolated git repository verification.
  - Added `--untracked-files=all` (`-uall`) to git status invocation in `get_git_info` to ensure untracked directories are deeply inspected without false negatives.
- `tests/verification/test_status_register_traceability.py`:
  - Added `test_isolated_git_repo_cleanliness_and_preservation` using `tmp_path` fixture to verify clean tree, tracked modification detection, untracked file detection, and preserved user-file protection.
  - Added negative test `test_traceability_enforcement_fails_on_collection_error`.
  - Added negative test `test_traceability_enforcement_fails_on_nonzero_exit_code`.
  - Added negative test `test_traceability_fails_on_skipped_required_tests`.
- `tests/verification/test_reference_library.py`:
  - Implemented area-weighted element $L_2$ error norm evaluation across 3-level refinement hierarchy for `REF-05` (Lamé thick cylinder).
  - Formulated element Cauchy stress calculation and polar transformation for $\sigma_{rr}$, $\sigma_{\theta\theta}$, and $\sigma_{zz}$.
  - Added monotonic convergence rate verification for displacement ($p_u \approx 1.98$) and stresses ($p_\sigma \approx 0.97$).
  - Implemented area-weighted element patch recovery $\bar{\sigma}_{xx}$ for `REF-06` (Kirsch plate with hole) converging to $K_t(h) \to 3.000$ (fine mesh error $0.0610\%$).
  - Added `test_ref_06_kirsch_production_defect_sensitivity`: verified that assembling plane-strain stiffness on a thin plane-stress plate yields $K_t = 2.6229$, failing the acceptance gate.
- `scripts/run_mutation_campaign.py`:
  - Re-titled and documented as "Targeted Production-Function Runtime Mutation Testing Campaign".
  - Added unmutated baseline pre-validation: all 13 unique target test nodes verified before introducing mutations.
  - Fixed module patching across runtime imports for all 14 targeted mutants.
  - Recorded detailed JSON artifact at `results/mutation_campaign_report.json`.

### Changed
- `src/gdec/verification/status_register.py`:
  - Completely eliminated subsystem string matching (`if cap.subsystem in ...`) for determining `demonstrated_status`.
  - Derived `demonstrated_status` strictly from execution results of `required_test_node_ids`.
  - Bumped schema version to `1.1.0`.
- `src/gdec/verification/reference_problems.py`:
  - Updated specifications for `REF-05` and `REF-06` to document area-weighted element error norms, patch stress recovery, and convergence criteria.

### Preserved
- `src/gdec/core/analyser.py`: Untouched and preserved.
- `src/gdec/runtime/`: Untouched and preserved.
