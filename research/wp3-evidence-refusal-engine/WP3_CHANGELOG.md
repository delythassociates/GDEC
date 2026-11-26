# WP3 Evidence Graph & Refusal Engine — Changelog

## [Unreleased] - 2026-11-27

### Added
- `docs/adr/ADR-017-evidence-graph-and-refusal-engine.md`: Architecture Decision Record for WP3.
- `src/gdec/dse/evidence_graph.py`: Versioned `EngineeringEvidenceRecord` (`v1.0.0`), `CompactProblemFeatureVector`, `OutcomeMetrics`, `EstimatorClassification`, canonical JSON serialization, and SHA-256 `canonical_result_hash`.
- `src/gdec/dse/refusal.py`: Deterministic `RefusalEngine` with 12 versioned refusal rules (`REF-001`..`REF-012`).
- `src/gdec/dse/verifier.py`: Independent `verify_evidence_payload` and `verify_evidence_file` (does not run solver by default; optional `rerun=True`).
- `schemas/engineering_evidence_record_v1.0.0.json`: Exported JSON Schema.
- `tests/verification/test_wp3_refusal_engine.py`: 15 positive/negative refusal-rule and runtime tests.
- `tests/verification/test_wp3_evidence_verifier_and_tamper.py`: 14 round-trip, tamper, optional-rerun, and mutation tests.

### Changed
- `src/gdec/core/telemetry.py`: Added `evidence_record` and `refusal_result` fields to `ExecutionTrace`.
- `src/gdec/core/runtime.py`: Integrated `_attach_evidence_and_refusal()` into `GDECRuntime.execute()` (with full mesh coordinate/connectivity SHA-256 hashing and `UNASSESSED` V&V status when no reference is compared).
- `src/gdec/cli.py`: Added `gdec verify <result.json>` and `--output` / refusal reporting to `gdec run`.
- `src/gdec/dse/__init__.py`: Exported WP3 evidence, refusal, and verifier APIs.
