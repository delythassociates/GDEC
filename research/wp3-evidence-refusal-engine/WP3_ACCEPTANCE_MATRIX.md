# WP3 Evidence Graph & Refusal Engine — Acceptance Matrix

| Gate | Requirement | Observed Evidence | Status |
|---|---|---|---|
| **WP3-01** | Round-trip verification (`run -> save -> verify`) succeeds | `test_complete_round_trip_run_save_verify` (`gdec run ... -o ...` + `gdec verify ...` returns `VER-OK`) | **PASS** |
| **WP3-02** | Every deliberate tamper case fails with precise diagnostic | `test_wp3_evidence_verifier_and_tamper.py` (`VER-HASH-MISMATCH`, `VER-METADATA-INCONSISTENT`, `VER-PROVENANCE-INVALID`, `VER-UNITS-INCONSISTENT`, `VER-MISSING-DEPENDENCY`, `VER-REFUSAL-MISMATCH`, `VER-SCHEMA-INVALID`, `VER-NONFINITE`, `VER-MALFORMED-INPUT`) | **PASS** |
| **WP3-03** | At least 10 refusal rules have positive and negative tests | 12 rules (`REF-001`..`REF-012`, with `REF-002`/`003`/`005`/`006`/`007`/`010` at `1.1.0`) all tested positively and negatively in `test_wp3_refusal_engine.py` | **PASS** |
| **WP3-04** | JSON schema exported and versioned | `schemas/engineering_evidence_record_v1.0.0.json` (preserved) & `schemas/engineering_evidence_record_v1.1.0.json` (`schema_version = "1.1.0"`) | **PASS** |
| **WP3-05** | Public result paths attach evidence & refusal evaluation | `GDECRuntime.execute()` and `gdec run` always populate & persist `EngineeringEvidenceRecord` and `RefusalResult`; `gdec.benchmark` propagates refusal/qualification & marks research-only; low-level `LinearElasticitySolver.solve()` remains distinct | **PASS** |
| **WP3-06** | Existing WP2 baseline tests remain passing | Full suite: `488 passed, 14 skipped, 0 failed`; branch coverage `64.48% (1238/1920)` >= `62.15%` floor; `20/20` targeted mutants killed | **PASS** |
| **WP3-07** | No solver or estimator mathematics changed | `git diff -- src/gdec/fem/` is empty | **PASS** |
| **WP3-08** | No unsupported certification claims introduced | DWR classified `dwr_asymptotic_estimate`; `SUPPORTED_CERT_CHECKERS` empty (fail-closed); `REF-002` & `verifier.py` block `mathematically_established_bound` for DWR | **PASS** |
| **WP3-09** | CI passes on supported Python matrix | GitHub Actions run [`45964259196`](https://github.com/delythassociates/GDEC/actions/runs/45964259196) on `8e43d0129a89dd00a3e3a89df7f7d94b376cbbf2`: `15/15` jobs succeeded (`12` OS/Python matrix + `status-register-traceability` + `upstream-dependency-drift` + `coverage-and-mutation`). Note: CI pass does not independently prove physical validity; new closure commits require a fresh CI run. | **PASS** |
| **WP3-10** | Independent reviews completed | Two independent reviews (`WP3 Adversarial Semantics Reviewer` & `WP3 CLI & Benchmark Reviewer`) completed; 3 semantics/verifier findings resolved and regression-tested | **PASS** |
