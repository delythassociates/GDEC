# GDEC WP3 — Evidence Graph & Refusal Engine Master Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/wp3-evidence-refusal-engine`  
**Base Commit:** `31190c18ece1cebd12982ac966ad5262e0bfc25d`  
**Date:** 2026-11-27  
**Governance Status:** Technically implemented, tested, and independently reviewed; **OWNER ACCEPTANCE PENDING**

---

## 1. Executive Summary

WP3 delivers GDEC's machine-checkable `EngineeringEvidenceRecord` (`v1.1.0`, preserving `v1.0.0`), deterministic 12-rule `RefusalEngine` (`REF-001`..`REF-012`), fail-closed independent verifier (`gdec verify <result.json> [--json] [--require-qualified]`), and trust-boundary enforcement across `GDECRuntime.execute()`, `gdec run`, and `gdec.benchmark`, while preserving all WP2 limitations and leaving solver/estimator mathematics (`src/gdec/fem/`) untouched.

1. **ADR & Schema (`ADR-017`, `schemas/engineering_evidence_record_v1.1.0.json`):** Separates 7 orthogonal epistemic/governance states, enforces `@model_validator` qualification invariants, includes `problem_ir_hash`, `execution_plan_hash`, `source_revision`, compact problem-feature vector, outcome metrics (`final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`), and explicit non-claim regarding SHA-256 hash semantics.
2. **Refusal Engine (`src/gdec/dse/refusal.py`):** 12 versioned deterministic rules returning first-class `RefusalResult` objects, including `REF-002` blocking DWR/uncertified `mathematically_established_bound` claims (`SUPPORTED_CERT_CHECKERS` empty), `REF-005` structural mesh preconditions, and `REF-006` primal+adjoint convergence checks.
3. **Fail-Closed Verifier (`src/gdec/dse/verifier.py`, `gdec verify`):** Enforces 5 MB payload cap, duplicate-key and `NaN`/`Infinity` rejection, structural depth/item bounds, strict type checks, raw-vs-normalized hash verification, and full per-rule refusal comparison without executing the solver by default.
4. **CLI & Benchmark Trust Boundaries (`src/gdec/cli.py`, `src/gdec/benchmark/`):** `gdec run` persists durable evidence JSON by default (`results/evidence/`) with fail-closed `OSError` handling and epistemic QoI labelling; `gdec.benchmark` propagates refusal/qualification status and marks outputs `RESEARCH BENCHMARK — NOT A QUALIFIED ENGINEERING DECISION`.
5. **Independent Reviews & Verification:** Two independent reviews completed; 3 semantics/verifier findings resolved and regression-tested. Full test suite: `488 passed, 14 skipped, 0 failed`; branch coverage `64.48% (1238/1920)` >= `62.15%` floor; `20/20` targeted mutants killed (not whole-repo).

---

## 2. Deliverable Index

- [WP3_HARDENING_COMPLETION_REPORT.md](WP3_HARDENING_COMPLETION_REPORT.md)
- [WP3_ACCEPTANCE_MATRIX.md](WP3_ACCEPTANCE_MATRIX.md)
- [WP3_REFUSAL_RULE_CATALOG.md](WP3_REFUSAL_RULE_CATALOG.md)
- [WP3_EVIDENCE_SCHEMA.md](WP3_EVIDENCE_SCHEMA.md)
- [WP3_VERIFICATION_REPORT.md](WP3_VERIFICATION_REPORT.md)
- [WP3_CHANGELOG.md](WP3_CHANGELOG.md)
- [WP3_RISK_REGISTER.md](WP3_RISK_REGISTER.md)
- [../../docs/adr/ADR-017-evidence-graph-and-refusal-engine.md](../../docs/adr/ADR-017-evidence-graph-and-refusal-engine.md)
- [../../schemas/engineering_evidence_record_v1.1.0.json](../../schemas/engineering_evidence_record_v1.1.0.json)
