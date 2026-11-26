# GDEC WP3 — Evidence Graph & Refusal Engine Master Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/wp3-evidence-refusal-engine`  
**Starting Commit:** `053ca59dd516bce42f841cd58a34301b55c2a8b1`  
**Date:** 2026-11-27  
**Governance Status:** Technically implemented, tested, and independently reviewed; **OWNER ACCEPTANCE PENDING**  

---

## 1. Executive Summary

WP3 delivers GDEC's machine-checkable `EngineeringEvidenceRecord` (`v1.0.0`), deterministic 12-rule `RefusalEngine` (`REF-001`..`REF-012`), independent verifier (`gdec verify <result.json>`), and integration into `GDECRuntime.execute()` and `gdec run`, while preserving all WP2 limitations and leaving solver/estimator mathematics (`src/gdec/fem/`) untouched.

1. **ADR & Schema (`ADR-017`, `schemas/engineering_evidence_record_v1.0.0.json`):** Canonical sorted-key JSON serialization with SHA-256 `canonical_result_hash`, compact problem-feature vector, outcome metrics (`final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`), and explicit non-claim regarding hash semantics.
2. **Refusal Engine (`src/gdec/dse/refusal.py`):** 12 versioned deterministic rules returning first-class `RefusalResult` objects, including `REF-002` blocking DWR misclassification as `mathematically_established_bound`.
3. **Independent Verifier (`src/gdec/dse/verifier.py`, `gdec verify`):** Validates schema, recomputes canonical hashes, checks provenance, dependency versions, units, metadata consistency, and re-evaluates refusal rules without running the solver by default.
4. **Independent Review & Hardening:** Independent review identified 5 edge cases (fail-closed missing metadata keys in `verifier.py`, full mesh array hashing in `runtime.py`, `OutcomeMetrics` finiteness validation, `REF-010` hex check, and `UNASSESSED` V&V status when no reference is compared); all 5 were fixed and regression-tested.

---

## 2. Deliverable Index

- [WP3_ACCEPTANCE_MATRIX.md](WP3_ACCEPTANCE_MATRIX.md)
- [WP3_REFUSAL_RULE_CATALOG.md](WP3_REFUSAL_RULE_CATALOG.md)
- [WP3_EVIDENCE_SCHEMA.md](WP3_EVIDENCE_SCHEMA.md)
- [WP3_VERIFICATION_REPORT.md](WP3_VERIFICATION_REPORT.md)
- [WP3_CHANGELOG.md](WP3_CHANGELOG.md)
- [WP3_RISK_REGISTER.md](WP3_RISK_REGISTER.md)
- [../../docs/adr/ADR-017-evidence-graph-and-refusal-engine.md](../../docs/adr/ADR-017-evidence-graph-and-refusal-engine.md)
- [../../schemas/engineering_evidence_record_v1.0.0.json](../../schemas/engineering_evidence_record_v1.0.0.json)
