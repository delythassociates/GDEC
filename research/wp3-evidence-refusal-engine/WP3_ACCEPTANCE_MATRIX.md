# WP3 Evidence Graph & Refusal Engine — Acceptance Matrix

| Gate | Requirement | Observed Evidence | Status |
|---|---|---|---|
| **WP3-01** | Round-trip verification (`run -> save -> verify`) succeeds | `test_complete_round_trip_run_save_verify` (`gdec run ... -o ...` + `gdec verify ...` returns `VER-OK`) | **PASS** |
| **WP3-02** | Every deliberate tamper case fails with precise diagnostic | `test_wp3_evidence_verifier_and_tamper.py` (`VER-HASH-MISMATCH`, `VER-METADATA-INCONSISTENT`, `VER-PROVENANCE-INVALID`, `VER-ESTIMATOR-CLASS-INVALID`, `VER-UNITS-INCONSISTENT`, `VER-MISSING-DEPENDENCY`, `VER-STALE-OR-INVALIDATED`, `VER-REFUSAL-MISMATCH`, `VER-APPLICABILITY-UNESTABLISHED`, `VER-SCHEMA-INVALID`) | **PASS** |
| **WP3-03** | At least 10 refusal rules have positive and negative tests | 12 rules (`REF-001`..`REF-012`) all tested positively and negatively in `test_wp3_refusal_engine.py` | **PASS** |
| **WP3-04** | JSON schema exported and versioned | `schemas/engineering_evidence_record_v1.0.0.json` (`schema_version = "1.0.0"`) | **PASS** |
| **WP3-05** | Public result paths attach evidence & refusal evaluation | `GDECRuntime.execute()` and `gdec run` always populate `EngineeringEvidenceRecord` and `RefusalResult`; low-level `LinearElasticitySolver.solve()` remains distinct | **PASS** |
| **WP3-06** | Existing WP2 baseline tests remain passing | Full suite: 481 passed, 14 skipped, 0 failed; branch coverage 63.04% >= 62.15% floor | **PASS** |
| **WP3-07** | No solver or estimator mathematics changed | `git diff -- src/gdec/fem/` is empty | **PASS** |
| **WP3-08** | No unsupported certification claims introduced | DWR classified `dwr_asymptotic_estimate`; `REF-002` and `verifier.py` block `mathematically_established_bound` for DWR | **PASS** |
| **WP3-09** | CI passes on supported Python matrix | Pending CI run on pushed commit | **IN PROGRESS** |
| **WP3-10** | Independent review completed | Independent Reviewer audited WP3; 5 findings resolved and regression-tested | **PASS** |
