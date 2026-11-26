# WP3 Evidence Schema Specification (`v1.0.0`)

- **Model:** `gdec.dse.evidence_graph.EngineeringEvidenceRecord` (Pydantic v2, `frozen=True`, `extra="forbid"`)
- **Exported JSON Schema:** `schemas/engineering_evidence_record_v1.0.0.json`
- **Canonical Serialization:** Sorted-key compact JSON (`allow_nan=False`, UTF-8) with SHA-256 `canonical_result_hash` computed over the normalized payload excluding `canonical_result_hash`.
- **Non-Claim:** A canonical SHA-256 hash verifies structural/byte integrity only; it does not prove scientific correctness, physical validity, authorship, or cryptographic authenticity.

## Required Fields

- **Identity & Provenance:** `schema_version` (`"1.0.0"`), `record_id`, `canonical_eir_hash`, `mesh_identity`, `mesh_hash`, `material_identity`, `boundary_conditions_identity`, `parent_artifacts` (`artifact_id`, `artifact_type`, `sha256_hash`).
- **Solver & Environment:** `solver_identity`, `solver_version`, `solver_config`, `backend`, `numerical_precision`, `dependency_versions` (`numpy`, `scipy`, `scikit-fem`).
- **Discretization & QoI:** `dof_count`, `mesh_metadata`, `qoi_id`, `qoi_name`, `qoi_units`, `qoi_value`.
- **Estimator & Applicability:** `estimator_identity`, `estimator_classification` (`heuristic`, `dwr_asymptotic_estimate`, `reference_based_estimate`, `mathematically_established_bound`), `error_estimate`, `error_estimate_interpretation`, `effectivity_evidence` (or `"NONE"`), `model_applicability_status`, `verification_validation_status`.
- **Compact Problem-Feature Vector & Outcome Metrics (Session 2 Owner Directive):**
  - `problem_features`: `domain_width`, `domain_height`, `aspect_ratio`, `num_loads`, `num_fixed_boundaries`, `youngs_modulus`, `poissons_ratio`, `constitutive_assumption`, `refinement_strategy`, `initial_dofs`, `max_dofs_budget`.
  - `outcome_metrics`: `final_dofs`, `refinement_steps`, `wall_time_sec`, `estimator_value`.
- **Refusal & Integrity State:** `refusal_evaluations`, `refused`, `refusal_reasons`, `resource_consumption`, `evidence_stale`, `evidence_invalidated`, `canonical_result_hash`.
