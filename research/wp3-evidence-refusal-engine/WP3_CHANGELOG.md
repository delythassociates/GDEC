# WP3 Evidence Graph & Refusal Engine — Changelog

## [Unreleased] - 2026-11-27 (Hardening Pass — Findings A–G)

### Added
- `schemas/engineering_evidence_record_v1.1.0.json`: Exported v1.1.0 JSON schema (preserving `v1.0.0` untouched).
- `src/gdec/dse/evidence_graph.py`: Added `QualificationStatus`, `QoIEpistemicRole`, `ReferenceEffectivityEvidence`, `BoundCertificateEvidence`, 7 orthogonal epistemic/governance state fields, `@model_validator` enforcing qualification invariants, `problem_ir_hash`, `execution_plan_hash`, `source_revision`, `linear_solver_type`, `compute_device`, `error_estimate_units`, `error_estimate_quantity`, `StrictInt`, and `allow_inf_nan=False`.
- `src/gdec/dse/refusal.py`: Added `structural_min_dofs_for_estimator`, bumped `REF-002`/`003`/`005`/`006`/`007`/`010` to `"1.1.0"`, enforced structural mesh preconditions (`free_dof_count`, `interior_facet_count`, `interior_node_count`, `min_total_dofs`), primal+adjoint convergence checks, and fail-closed `BoundCertificateEvidence` checker validation.
- `src/gdec/dse/verifier.py`: Added `MAX_EVIDENCE_BYTES` (5 MB), duplicate-key and `NaN`/`Infinity` JSON parse rejection, `_validate_json_structure` (depth/item/string/int bounds), strict type helpers, raw-vs-normalized hash checks, full per-rule refusal evaluation comparison, and canonical `REF-005` floor enforcement.
- `tests/verification/test_wp3_refusal_engine.py`: Added `REF-005` structural floor boundary tests, `REF-002` non-DWR bound rejection, and `REF-006` adjoint non-convergence tests.
- `tests/verification/test_wp3_evidence_verifier_and_tamper.py`: Added 14+ hostile verifier attack vectors, Finding A qualification & `--require-qualified` tests, Finding B provenance collision-resistance tests, Finding D/E CLI default persistence, `dwr` runtime, `--json`, and benchmark trust-boundary tests, and review-fix regression tests.

### Changed
- `src/gdec/core/controller.py`: Added `budget_exhausted: bool = False` to `ControllerDecision`.
- `src/gdec/core/telemetry.py`: Changed `ExecutionTrace.final_qoi_mm` to `Optional[float]` (`None` when empty) and added fail-closed `ExecutionTrace.qualified_qoi_mm`.
- `src/gdec/core/runtime.py`: Fixed `fixed_boundaries` -> `fixed_bcs` DWR crash, wired `budget_exhausted`, added complete `ProblemIR` & `ExecutionPlan` hashing, `_get_source_revision()`, `_assess_model_applicability()`, DWR unit consistency (`mm`), and v1.1.0 record generation.
- `src/gdec/cli.py`: Added collision-safe default evidence persistence under `results/evidence/`, fail-closed `OSError` handling, epistemic QoI labelling, `--strategy dwr`/`goal_oriented_dwr`, and `gdec verify --json` / `--require-qualified` (exit 0/1/2).
- `src/gdec/benchmark/{runner,metrics,reporting}.py`: Propagated refusal/qualification metadata and marked benchmark outputs `RESEARCH BENCHMARK — NOT A QUALIFIED ENGINEERING DECISION` / `RESEARCH_BENCHMARK_ONLY`.
- `docs/adr/ADR-017-evidence-graph-and-refusal-engine.md`: Updated to document v1.1.0 schema, orthogonal states, and verifier/CLI/benchmark trust boundaries.
