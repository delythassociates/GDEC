# WP3 Evidence Graph & Refusal Engine — Risk Register

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Status |
|---|---|---|---|---|---|
| **RISK-WP3-01** | Canonical SHA-256 hash mistaken for scientific correctness or cryptographic authenticity | Medium | Medium | Explicit non-claim in `ADR-017`, `evidence_graph.py`, and `WP3_EVIDENCE_SCHEMA.md` | Managed |
| **RISK-WP3-02** | DWR indicator mislabelled as certified mathematical bound | High | Low | `REF-002` and `VER-ESTIMATOR-CLASS-INVALID` reject DWR labelled as `mathematically_established_bound` | Closed |
| **RISK-WP3-03** | Empty optional metadata dicts bypassing refusal re-evaluation | Medium | Low | `verifier.py` fails closed with `VER-METADATA-INCONSISTENT` and `VER-REFUSAL-MISMATCH` if required keys are missing | Closed |
| **RISK-WP3-04** | Non-GPU CI runners skip 14 CUDA tests; 20/20 targeted mutation campaign is not whole-repo | Low | High | WP2 limitations preserved verbatim; no GPU work added in WP3 | Managed |
