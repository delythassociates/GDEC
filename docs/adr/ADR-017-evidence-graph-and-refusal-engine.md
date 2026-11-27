# ADR-017: Engineering Evidence Record, Refusal Engine, and Independent Verifier (WP3)

**Status:** Proposed / Implemented for WP3 (`research/wp3-evidence-refusal-engine`)  
**Date:** 2026-11-27  
**Context:** WP2 established V&V benchmarks, branch coverage gating, and targeted mutation resilience, while retaining explicit limitations: DWR is an asymptotic error indicator (not a certified upper bound), and `GDECRuntime.execute()` / `gdec run` previously emitted raw numerical traces without a machine-checkable evidence record or deterministic refusal evaluation.

## Decision

1. **Versioned Engineering Evidence Record (`schema_version = "1.1.0"`, preserving `1.0.0` schema artifact):**
   - Implement `EngineeringEvidenceRecord` using strict Pydantic v2 models (`frozen=True`, `extra="forbid"`, `StrictInt`, `allow_inf_nan=False`) with canonical sorted-key JSON serialization and SHA-256 `canonical_result_hash`.
   - Separate 7 orthogonal epistemic/governance states: `refused`, `numerical_convergence_status`, `model_applicability_status` (+ `model_applicability_reasons`), `verification_status`, `validation_status`, `qualification_status`, and `qoi_epistemic_role`, with `@model_validator` forbidding `qualification_status="QUALIFIED"` unless all prerequisites are satisfied.
   - Include canonical `problem_ir_hash`, `execution_plan_hash`, `source_revision`, mesh/geometry identity and hash, material/BC identities, solver identity/version/config, `linear_solver_type`, `compute_device`, backend/precision, dependency versions, DOF count, QoI and units, estimator classification (`heuristic`, `dwr_asymptotic_estimate`, `reference_based_estimate`, `mathematically_established_bound`), `error_estimate_units`, `error_estimate_quantity`, structured `ReferenceEffectivityEvidence` / `BoundCertificateEvidence`, compact problem-feature vector, outcome metrics (`final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`), refusal evaluations, resource consumption, and parent-artifact provenance.
   - **Migration / Compatibility:** `schemas/engineering_evidence_record_v1.0.0.json` is preserved untouched; `schemas/engineering_evidence_record_v1.1.0.json` is the active schema, and the verifier strictly enforces `1.1.0` requirements.
   - **Explicit Non-Claim:** A SHA-256 hash verifies byte-level structural integrity only; it does not prove scientific correctness, physical validity, authorship, or cryptographic authenticity.
2. **Deterministic Refusal Engine (`REF-001`–`REF-012`, with `REF-002`/`003`/`005`/`006`/`007`/`010` at `1.1.0`):**
   - Implement 12 versioned, deterministic refusal rules returning first-class structured `RefusalRuleEvaluation` and `RefusalResult` objects.
   - `REF-002` rejects `mathematically_established_bound` unless verified by an explicitly supported `SUPPORTED_CERT_CHECKERS` entry (currently empty -> fail-closed).
   - `REF-005` enforces structural mesh preconditions (`free_dof_count`, `interior_facet_count`, `interior_node_count`, `min_total_dofs >= 8` or `>= 18` for DWR).
   - `REF-006` checks both primal and adjoint convergence/residuals; `REF-010` checks all 64-hex hashes and parent artifact provenance links.
3. **Fail-Closed Independent Verifier (`gdec verify <result.json> [--json] [--require-qualified]`):**
   - Separate verification module (`gdec.dse.verifier`) enforcing `MAX_EVIDENCE_BYTES` (5 MB), duplicate-key & `NaN`/`Infinity` JSON rejection, structural depth/item bounds, strict type checks, raw-vs-normalized hash verification, full per-rule refusal comparison, and canonical `REF-005` floor enforcement without executing the solver by default.
4. **Public vs. Low-Level API Separation & Trust Boundaries:**
   - Low-level `LinearElasticitySolver.solve()` continues returning `FEMSolution` unchanged.
   - User-facing `GDECRuntime.execute()` and `gdec run` persist durable evidence JSON (`-o` or default `results/evidence/<name>_<hash>.json`), surface epistemic/qualification state, and never present refused/unvalidated QoI as qualified.
   - `gdec.benchmark` propagates refusal/qualification metadata and marks reports `RESEARCH BENCHMARK — NOT A QUALIFIED ENGINEERING DECISION`.

## Consequences

- Public engineering workflows cannot silently present unqualified numbers when budget, applicability, convergence, provenance, or estimator validity fails.
- Existing solver and estimator mathematics remain untouched.
