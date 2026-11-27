# WP3 Evidence Graph & Refusal Engine — Risk Register

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Status |
|---|---|---|---|---|---|
| **RISK-WP3-01** | Canonical SHA-256 hash mistaken for scientific correctness or cryptographic authenticity | Medium | Medium | Explicit non-claim in `ADR-017`, `evidence_graph.py`, and `WP3_EVIDENCE_SCHEMA.md` | Managed |
| **RISK-WP3-02** | DWR indicator or uncertified estimator mislabelled as certified mathematical bound | High | Low | `REF-002`, `SUPPORTED_CERT_CHECKERS` (empty), and `verifier.py` reject `mathematically_established_bound` | Closed |
| **RISK-WP3-03** | Empty optional metadata dicts or type/JSON-parser attacks bypassing refusal re-evaluation | Medium | Low | `verifier.py` enforces 5 MB cap, duplicate-key & `NaN`/`Inf` rejection, structural bounds, strict types, and `VER-METADATA-INCONSISTENT` | Closed |
| **RISK-WP3-04** | Non-GPU CI runners skip 14 CUDA tests; 20/20 targeted mutation campaign is not whole-repo | Low | High | WP2 limitations preserved verbatim; no GPU work added in WP3 | Managed |
| **RISK-WP3-05** | Non-refused unassessed-V&V runs presented as qualified engineering values | High | Low | `qualification_status` (`NOT_QUALIFIED_UNASSESSED_VV`), fail-closed `ExecutionTrace.qualified_qoi_mm`, `gdec run` epistemic QoI labelling, and `gdec verify --require-qualified` (exit 2) | Closed |
