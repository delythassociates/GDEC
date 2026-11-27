# WP3 Evidence Schema Specification (`v1.1.0`, preserving `v1.0.0`)

- **Model:** `gdec.dse.evidence_graph.EngineeringEvidenceRecord` (Pydantic v2, `frozen=True`, `extra="forbid"`, `StrictInt`, `allow_inf_nan=False`)
- **Exported JSON Schemas:** `schemas/engineering_evidence_record_v1.1.0.json` (active), `schemas/engineering_evidence_record_v1.0.0.json` (retained historical schema artifact)
- **Compatibility & Migration Policy:**
  - `1.1.0` is the active schema version (`EVIDENCE_SCHEMA_VERSION = "1.1.0"`).
  - The current verifier (`verify_evidence_payload`) **rejects** `v1.0.0` payloads with `VER-SCHEMA-INVALID` (verified by `test_aud_01_v1_0_0_schema_rejected`).
  - `schemas/engineering_evidence_record_v1.0.0.json` is retained solely as a historical schema artifact; retaining it does **not** provide backward compatibility.
  - No automatic `v1.0.0`-to-`v1.1.0` migration is currently provided. Old `v1.0.0` evidence records must not be relabeled as `v1.1.0`, nor are their semantics equivalent.
- **Canonical Serialization:** Sorted-key compact JSON (`allow_nan=False`, UTF-8) with SHA-256 `canonical_result_hash` computed over the normalized payload excluding `canonical_result_hash`.
- **Non-Claim:** A canonical SHA-256 hash verifies structural/byte integrity only; it does not prove scientific correctness, physical validity, authorship, or cryptographic authenticity.

## Orthogonal Epistemic & Governance States (`v1.1.0`)
1. `refused` (`bool` + `refusal_reasons` + `refusal_evaluations`)
2. `numerical_convergence_status` (`converged`, `not_converged`, `not_run`)
3. `model_applicability_status` (`established`, `unestablished`, `violated`) + `model_applicability_reasons`
4. `verification_status` (`UNASSESSED`, `VERIFIED`, `VALIDATED`, `INDEPENDENTLY_VALIDATED`, `FAILED`)
5. `validation_status` (`UNASSESSED`, `VALIDATED`, `INDEPENDENTLY_VALIDATED`, `FAILED`)
6. `qualification_status` (`QUALIFIED`, `REFUSED`, `NOT_QUALIFIED_UNASSESSED_VV`, `NOT_QUALIFIED_UNCONVERGED`, `NOT_QUALIFIED_APPLICABILITY`, `NOT_QUALIFIED_STALE_OR_INVALIDATED`)
7. `qoi_epistemic_role` (`qualified_engineering_value`, `numerical_observation_not_validated`, `refused_unqualified_observation`, `unavailable`)

`@model_validator` forbids `qualification_status = "QUALIFIED"` unless `refused=False`, `numerical_convergence_status="converged"`, `model_applicability_status="established"`, `verification_status` and `validation_status` and `verification_validation_status` are verified/validated, `evidence_stale=False`, `evidence_invalidated=False`, `qoi_value is not None`, and `resource_consumption["target_tolerance_met"] is True`.

## Required Fields (`v1.1.0`)
- **Identity & Provenance:** `schema_version` (`"1.1.0"`), `record_id`, `canonical_eir_hash`, `problem_ir_hash`, `execution_plan_hash`, `source_revision`, `mesh_identity`, `mesh_hash`, `material_identity`, `boundary_conditions_identity`, `parent_artifacts` (`artifact_id`, `artifact_type`, `sha256_hash`).
- **Solver & Environment:** `solver_identity`, `solver_version`, `solver_config`, `linear_solver_type`, `compute_device`, `backend`, `numerical_precision`, `dependency_versions` (`numpy`, `scipy`, `scikit-fem`).
- **Discretization & QoI:** `dof_count`, `mesh_metadata`, `qoi_id`, `qoi_name`, `qoi_units`, `qoi_value`, `qoi_epistemic_role`.
- **Estimator & Applicability:** `estimator_identity`, `estimator_classification` (`heuristic`, `dwr_asymptotic_estimate`, `reference_based_estimate`, `mathematically_established_bound`), `error_estimate`, `error_estimate_units`, `error_estimate_quantity`, `error_estimate_interpretation`, `effectivity_evidence` (`ReferenceEffectivityEvidence` | `BoundCertificateEvidence` | `"NONE"`), `model_applicability_status`, `model_applicability_reasons`, `verification_validation_status`, `verification_status`, `validation_status`, `qualification_status`.
- **Compact Problem-Feature Vector & Outcome Metrics:**
  - `problem_features`: `domain_width`, `domain_height`, `aspect_ratio`, `num_loads`, `num_fixed_boundaries`, `youngs_modulus`, `poissons_ratio`, `constitutive_assumption`, `refinement_strategy`, `initial_dofs`, `max_dofs_budget`.
  - `outcome_metrics`: `final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`.
- **Refusal & Integrity State:** `refusal_evaluations`, `refused`, `refusal_reasons`, `resource_consumption`, `evidence_stale`, `evidence_invalidated`, `canonical_result_hash`.
