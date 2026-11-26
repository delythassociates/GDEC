# WP3 Verification & Adversarial Tamper Report

- **Independent Verifier:** `src/gdec/dse/verifier.py` (`verify_evidence_payload`, `verify_evidence_file`)
- **CLI Entry Point:** `gdec verify <result.json>` (does **not** run the solver by default; optional `rerun=True` mode compares re-executed QoI within `rtol`).
- **Adversarial & Mutation Suites:**
  - `tests/verification/test_wp3_refusal_engine.py`: 15 tests (clean context + positive/negative for all 12 rules `REF-001`..`REF-012` + `math.inf` + runtime budget exhaustion).
  - `tests/verification/test_wp3_evidence_verifier_and_tamper.py`: 13 tests covering round-trip `gdec run` -> `gdec verify`, individual field tampering (`VER-HASH-MISMATCH`), inconsistent metadata (`VER-METADATA-INCONSISTENT`), DWR misclassification (`VER-ESTIMATOR-CLASS-INVALID`), wrong units (`VER-UNITS-INCONSISTENT`), missing dependencies (`VER-MISSING-DEPENDENCY`), stale/invalidated evidence (`VER-STALE-OR-INVALIDATED`), forged provenance (`VER-PROVENANCE-INVALID`), refusal bypass (`VER-REFUSAL-MISMATCH`), unestablished model applicability (`VER-APPLICABILITY-UNESTABLISHED`), `NaN`/`inf` (`VER-SCHEMA-INVALID`), optional `rerun=True` (`VER-RERUN-MISMATCH`), and verifier/refusal bypass mutations.
- **Observed Result:** **28 passed, 0 failed** in `6.85s`.
