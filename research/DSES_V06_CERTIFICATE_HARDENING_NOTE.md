# DSES v0.6 certificate-verifier hardening delta

**Branch:** `research/dses-envelope-comparative-benchmarks-v0.6`  
**Scope:** research prototype only; no GDEC production or FEM integration.

## Implemented

The v0.6 verifier now enforces the supported certificate metadata rather than merely accepting any self-consistent metadata protected by a recomputed SHA-256 digest:

- `assurance_class` must equal `ANALYTICAL_EXACT_RATIONAL_ENCLOSURE`.
- `proof_rule_version` must equal `v0.6.1`.
- `sqrt_upper_scale` must be the supported integer constant `10^6`; a numerically equal float is not accepted.
- `max_depth` must be an integer (not bool) in the supported range.
- Every tree node's `depth` must be an integer equal to its actual traversal depth.
- No node may exceed the certificate's declared maximum depth.

Adversarial tests alter each metadata field and recompute the digest before verification. This ensures the checks are semantic and not just digest-mismatch detection.

## Verification status

- IMPLEMENTED: verifier metadata and actual-tree-depth checks.
- TESTS ADDED: unsupported assurance class, unsupported proof-rule version, unsupported square-root scale, overstated tree depth, altered node depth, and boolean maximum depth.
- CI: a branch-scoped Python 3.10–3.13 workflow was added.
- CI EXECUTED & PASSED: workflow [45966199112](https://github.com/delythassociates/GDEC/actions/runs/45966199112), commit `27504b268a648662f2613aaa7493a3e9e5982072`; Python 3.10, 3.11, 3.12 and 3.13 each report 16 passed, 0 failed (64 test executions total).
- NATIVE IBEX: still not built or executed.
- FEM / physical validation: not performed.
- Assurance boundary: this remains an exact-rational analytical certificate for the declared synthetic model. It does not authenticate the producer or validate physical model applicability.
