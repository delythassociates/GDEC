# WP3 Refusal-Rule Catalog (`REF-001` through `REF-012`)

All rules are implemented in `src/gdec/dse/refusal.py` (`RefusalEngine`) and return structured `RefusalRuleEvaluation` objects (`rule_id`, `version`, `triggered`, `reason`, `diagnostic_context`).

| Rule ID | Version | Description | Deterministic Precondition | Positive & Negative Tests |
|---|---|---|---|---|
| **REF-001** | `1.0.0` | Computation budget exhausted before QoI tolerance met | `budget_exhausted and not target_tolerance_met` | `test_wp3_refusal_engine.py` + `test_runtime_budget_exhaustion_produces_refused_evidence_record` |
| **REF-002** | `1.0.0` | Estimator invalid or misclassified for problem class | `problem_class not in {"linear_elasticity_2d"}` or DWR labelled `mathematically_established_bound` | `test_wp3_refusal_engine.py` |
| **REF-003** | `1.0.0` | Reference adequacy unknown when required by contract | `reference_required and reference_adequate is not True` | `test_wp3_refusal_engine.py` |
| **REF-004** | `1.0.0` | QoI evaluated on unsupported or Dirichlet-constrained boundary | `qoi_boundary not in supported_boundaries` or `qoi_boundary in fixed_boundaries` | `test_wp3_refusal_engine.py` |
| **REF-005** | `1.0.0` | Insufficient DOFs for estimator validity regime | `dof_count < min_required_dofs` | `test_wp3_refusal_engine.py` |
| **REF-006** | `1.0.0` | Solver non-convergence or numerical breakdown | `not solver_converged` | `test_wp3_refusal_engine.py` |
| **REF-007** | `1.0.0` | Non-finite QoI, residual, or error estimate | `NaN` or `inf` in `qoi_value`, `residual_norm`, or `error_estimate` | `test_wp3_refusal_engine.py` (`test_ref_007_rejects_infinity`) |
| **REF-008** | `1.0.0` | Invalid or unsupported mesh conditions | `not mesh_valid or mesh_element_count <= 0` | `test_wp3_refusal_engine.py` |
| **REF-009** | `1.0.0` | Model applicability not established | `model_applicability_status != "established"` | `test_wp3_refusal_engine.py` |
| **REF-010** | `1.0.0` | Missing or inconsistent provenance | Invalid 64-hex `canonical_eir_hash`/`mesh_hash` or empty/invalid `parent_artifacts` | `test_wp3_refusal_engine.py` |
| **REF-011** | `1.0.0` | Missing mandatory evidence | `not mandatory_evidence_present or missing_evidence_fields or qoi_value is None` | `test_wp3_refusal_engine.py` |
| **REF-012** | `1.0.0` | Stale or invalidated evidence | `evidence_stale or evidence_invalidated` | `test_wp3_refusal_engine.py` |
