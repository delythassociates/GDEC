# Work Package 1 (WP1) Risk Register

**Document Identifier:** `GDEC-WP1-RISK-REGISTER`  
**Work Package:** WP1 — Adversarial Hardening of the EIR / Expression Type System  
**Date:** 2026-11-22  

---

## Residual Risks & Mitigations

| Risk ID | Description | Severity | Probability | Mitigation Strategy | Owner / Next Phase |
|---|---|---|---|---|---|
| **RISK-WP1-01** | `hypothesis` library not installed in offline execution environment; property tests currently run via seeded deterministic pseudo-random generators. | Low | Medium | Property test suite in `test_adversarial_hardening.py` executes 50+ deterministic trials per property; in WP2, CI matrix will run full Hypothesis engine in container environments. | WP2 V&V Suite & CI |
| **RISK-WP1-02** | Deep expression trees with depth $100 < d \le 128$ evaluate successfully but approach recursion limit on platforms with constrained stack sizes. | Low | Low | `MAX_EXPRESSION_DEPTH` set to 128 by default, which is safely within Python's 1000-frame default recursion limit. If complex mathematical expressions require larger trees, convert `infer_expression_type` to iterative stack traversal in WP7. | WP7 Longevity |
| **RISK-WP1-03** | CuPy warning `CUDA path could not be detected` persists in stderr even though NVIDIA GPU and cuSPARSE execute properly. | Low | High | Documented in `test_cuda_backend.py`. The warning stems from CuPy's optional nvrtc runtime path discovery and does not impair execution. Addressed in WP2 CI environment configuration. | WP2 CI Matrix |
