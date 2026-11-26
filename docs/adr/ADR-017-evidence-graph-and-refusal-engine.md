# ADR-017: Engineering Evidence Record, Refusal Engine, and Independent Verifier (WP3)

**Status:** Proposed / Implemented for WP3 (`research/wp3-evidence-refusal-engine`)  
**Date:** 2026-11-27  
**Context:** WP2 established V&V benchmarks, branch coverage gating, and targeted mutation resilience, while retaining explicit limitations: DWR is an asymptotic error indicator (not a certified upper bound), and `GDECRuntime.execute()` / `gdec run` previously emitted raw numerical traces without a machine-checkable evidence record or deterministic refusal evaluation.

## Decision

1. **Versioned Engineering Evidence Record (`schema_version = "1.0.0"`):**
   - Implement `EngineeringEvidenceRecord` using strict Pydantic v2 models (`frozen=True`, `extra="forbid"`) with canonical sorted-key JSON serialization and SHA-256 `canonical_result_hash`.
   - Include canonical EIR hash, mesh/geometry identity and hash, material/BC identities, solver identity/version/config, backend/precision, dependency versions, DOF count, QoI and units, estimator classification (`heuristic`, `dwr_asymptotic_estimate`, `reference_based_estimate`, `mathematically_established_bound`), effectivity/reference evidence (or `"NONE"`), model applicability, V&V status, compact problem-feature vector, outcome metrics (`final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`), refusal evaluations, resource consumption, and parent-artifact provenance.
   - **Explicit Non-Claim:** A SHA-256 hash verifies byte-level structural integrity only; it does not prove scientific correctness, physical validity, authorship, or cryptographic authenticity.
2. **Deterministic Refusal Engine (`REF-001`–`REF-012`):**
   - Implement 12 versioned, deterministic refusal rules returning first-class structured `RefusalRuleEvaluation` and `RefusalResult` objects.
   - Never label `DWREstimator` as `mathematically_established_bound` (`REF-002` refuses misclassified DWR).
3. **Independent Verifier (`gdec verify <result.json>`):**
   - Separate verification module (`gdec.dse.verifier`) validating schema, recomputing canonical hashes, checking parent provenance, re-evaluating refusal rules, checking estimator classifications, units, and dependencies without executing the solver by default.
4. **Public vs. Low-Level API Separation:**
   - Low-level `LinearElasticitySolver.solve()` continues returning `FEMSolution` unchanged.
   - User-facing `GDECRuntime.execute()` and `gdec run` produce evidence-bearing `ExecutionTrace` / JSON artifacts with explicit refusal status.

## Consequences

- Public engineering workflows cannot silently present unqualified numbers when budget, applicability, convergence, provenance, or estimator validity fails.
- Existing solver and estimator mathematics remain untouched.
