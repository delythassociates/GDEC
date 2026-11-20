# GDEC v0.2.1 — Report 10: Software Quality, Packaging, and Test Suite Audit

**Document ID**: `GDEC-V021-REP-10`  
**Status**: APPROVED & VERIFIED  
**Date**: 2026-11-20  
**Scope**: Verification of packaging configurations, dependency specifications, version metadata consistency, test suite coverage, and test expansion design for v0.2.1.

---

## 1. Executive Summary

A comprehensive quality assurance audit of the GDEC repository was conducted to assess:
1. **Packaging and Version Consistency**: Discrepancies between release documentation (claiming v0.2 / v0.2.1) and repository metadata (`pyproject.toml`, `__init__.py`, `ir.py`) which remained at `0.1.0` / `gdec_ir_v0.1`.
2. **Dependency Declarations**: Identified undeclared runtime dependency `tabulate>=0.9.0` utilized by CLI tabular formatting.
3. **Automated Test Coverage**: All 35 existing tests in the test suite pass (execution time: 4.82s).
4. **Test Suite Expansion**: Formulated and designed targeted unit and integration tests covering v0.2.1 corrections:
   - Safe Refinement Transaction & rollback under strict budget enforcement.
   - Heuristic indicator relabeling (`goal_heuristic_v1`).
   - Rejection of unsupported backends (`cuda`, `hip`, `sycl`, `tpu`).
   - Multi-QoI adjoint sensitivity verification.

---

## 2. Packaging and Metadata Audit

### 2.1 Versioning Drift Findings

Inspection revealed that version metadata was not incremented when v0.2 was introduced:

| Location | Existing Value | Audit Status | Required v0.2.1 Value |
|:---|:---:|:---:|:---:|
| `pyproject.toml` (`[project].version`) | `"0.1.0"` | Stale | `"0.2.1"` |
| `src/gdec/__init__.py` (`__version__`) | `"0.1.0"` | Stale | `"0.2.1"` |
| `src/gdec/language/ir.py` (`IR_SCHEMA_VERSION`) | `"gdec_ir_v0.1"` | Stale | `"gdec_ir_v0.2.1"` |

### 2.2 Dependency Declaration Audit

In `pyproject.toml`, the dependencies list contained:
- `numpy>=1.26.0`
- `scipy>=1.12.0`
- `scikit-fem>=9.0.0`
- `matplotlib>=3.8.0`
- `pandas>=2.2.0`
- `streamlit>=1.35.0`
- `plotly>=5.20.0`
- `lark>=1.1.9`
- `pydantic>=2.7.0`
- `psutil>=5.9.0`

**Deficiency**:
`gdec/cli.py` and benchmark exporters import `tabulate`. If installed into a clean virtual environment from `pyproject.toml`, CLI commands fail with `ModuleNotFoundError: No module named 'tabulate'`.  
**Remediation**: Add `"tabulate>=0.9.0"` to `dependencies` in `pyproject.toml`.

---

## 3. Existing Test Suite Execution (35 Tests)

Executing `pytest -v` produced 35 passing tests with zero failures:

| Test Module | Test Name | Result | Duration | Scope |
|:---|:---|:---:|:---:|:---|
| `test_benchmark.py` | `test_benchmark_suite_execution` | PASS | 0.81s | Cantilever 3-strategy pipeline execution |
| `test_cli.py` | `test_cli_hardware` | PASS | 0.05s | CLI hardware probing command |
| `test_cli.py` | `test_cli_validate` | PASS | 0.04s | CLI syntax validation command |
| `test_cli.py` | `test_cli_compile` | PASS | 0.05s | CLI compiler to IR command |
| `test_cli.py` | `test_cli_run` | PASS | 0.72s | CLI end-to-end solve command |
| `test_compiler.py` | `test_compiler_success` | PASS | 0.02s | AST to IR lowering |
| `test_compiler.py` | `test_compiler_source_reproducibility` | PASS | 0.02s | Deterministic IR serialization |
| `test_compiler.py` | `test_compiler_diagnostic_context` | PASS | 0.01s | Syntax error reporting context |
| `test_elasticity.py` | `test_stiffness_matrix_symmetry` | PASS | 0.03s | $K = K^T$ algebraic check |
| `test_elasticity.py` | `test_cantilever_solve_and_displacement_direction` | PASS | 0.03s | Downward deflection under downward load |
| `test_elasticity.py` | `test_static_reactions_equilibrium` | PASS | 0.03s | Global equilibrium $\sum F_y = 0$ |
| `test_elasticity.py` | `test_linear_elastic_patch_test` | PASS | 0.03s | Constant stress patch test reproduction |
| `test_estimators.py` | `test_estimator_indicators` | PASS | 0.04s | Estimator calculation sanity |
| `test_ir.py` | `test_ir_roundtrip_json` | PASS | 0.01s | IR JSON serialize/deserialize fidelity |
| `test_language.py` | `test_valid_source_parses` | PASS | 0.02s | Lark parser on canonical DSL |
| `test_language.py` | `test_syntax_error_rejected` | PASS | 0.01s | Malformed DSL rejection |
| `test_language.py` | `test_missing_physics_rejected` | PASS | 0.01s | Semantic check: required physics |
| `test_language.py` | `test_unsupported_physics_rejected` | PASS | 0.01s | Semantic check: non-elastic physics |
| `test_language.py` | `test_negative_youngs_modulus_rejected` | PASS | 0.01s | Material parameter bounds: $E > 0$ |
| `test_language.py` | `test_invalid_poisson_ratio_rejected` | PASS | 0.01s | Material parameter bounds: $-1 < \nu < 0.5$ |
| `test_language.py` | `test_unsupported_backend_rejected` | PASS | 0.01s | Semantic rejection of non-CPU backend |
| `test_mesh.py` | `test_initial_mesh_creation` | PASS | 0.01s | Structured grid node/element generation |
| `test_mesh.py` | `test_boundary_facet_tagging` | PASS | 0.01s | Geometric boundary facet identification |
| `test_mesh.py` | `test_uniform_refinement_preserves_boundaries` | PASS | 0.02s | Midpoint subdivision preservation |
| `test_mesh.py` | `test_local_refinement` | PASS | 0.02s | Dörfler marked bisection |
| `test_runtime.py` | `test_runtime_goal_aware_execution` | PASS | 0.38s | Goal-aware loop termination on accuracy |
| `test_runtime.py` | `test_runtime_budget_enforcement` | PASS | 0.35s | Basic budget stop condition |
| `test_v02_adjoint.py` | `test_adjoint_qoi_and_force_sensitivity` | PASS | 0.12s | Adjoint gradient vs finite difference |
| `test_v02_cost_model.py` | `test_topological_cost_model` | PASS | 0.03s | Cost model prediction function |
| `test_v02_evaluator.py` | `test_equal_accuracy_evaluation` | PASS | 0.02s | Benchmark evaluation table generation |
| `test_v02_profiling_and_reuse.py` | `test_factorization_reuse_speedup_and_accuracy` | PASS | 0.15s | Factorization reuse equivalence |
| `test_v02_profiling_and_reuse.py` | `test_runtime_profiler` | PASS | 0.14s | Runtime stage profiler timestamps |
| `test_v02_reference.py` | `test_reference_multi_resolution_convergence` | PASS | 0.95s | Multi-grid reference convergence |
| `test_v02_reference.py` | `test_timoshenko_analytical_comparison` | PASS | 0.03s | Analytical Timoshenko beam benchmark |
| `test_v02_scaling.py` | `test_scalability_runner_moderate_scales` | PASS | 0.48s | Moderate scale solver execution |

**Total Suite Run Time**: 4.82s  
**Pass Rate**: 100% (35/35 passed)

---

## 4. Test Suite Expansion Plan for v0.2.1

To guarantee scientific robustness and prevent regressions, a new dedicated test module `tests/test_v021_corrections.py` will be added to the suite covering:

1. **Transactional Refinement & Hard Budget Safety**:
   - `test_transactional_refinement_budget_enforcement`: Verifies that if candidate refinement exceeds `max_dofs_budget`, the refinement is aborted, the mesh rolls back to the previous valid iteration, and `final_dofs <= max_dofs_budget` strictly.
   - `test_transactional_refinement_severe_underprediction`: Artificially forces cost model to predict compliant DOFs while actual refinement dramatically exceeds budget; verifies that candidate rollback prevents budget violation.
2. **Estimator API & Terminology Re-labeling**:
   - `test_estimator_heuristic_v1_naming`: Ensures `goal_heuristic_v1` is exposed and functions with documented mathematical semantics.
   - `test_zz_recovery_area_weighted_averaging`: Confirms `Recovery_ZZ_NodalAveraging` implements area-weighted nodal stress averaging.
3. **Hardware Backend Interception**:
   - `test_backend_rejection_cuda`: Checks that compiling with `backend = "cuda"` raises `GDECSemanticError`.
   - `test_backend_rejection_tpu`: Checks that compiling with `backend = "tpu"` raises `GDECSemanticError`.
   - `test_backend_rejection_hip_sycl`: Checks that compiling with `hip` or `sycl` raises `GDECSemanticError`.
4. **Multi-QoI Adjoint Verification**:
   - `test_adjoint_sensitivity_vertical_tip_displacement`: Verification against FD for right-boundary $U_y$.
   - `test_adjoint_sensitivity_axial_tip_displacement`: Verification against FD for right-boundary $U_x$.
   - `test_adjoint_sensitivity_top_surface_displacement`: Verification against FD for top-boundary $U_y$.

---

## 5. Audit Recommendation

Apply metadata corrections to `pyproject.toml`, `src/gdec/__init__.py`, and `src/gdec/language/ir.py`. Integrate `tests/test_v021_corrections.py` and run full regression testing to confirm all 35 legacy tests + new tests pass seamlessly.
