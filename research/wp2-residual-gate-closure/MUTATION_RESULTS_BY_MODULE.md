# WP2 Residual Closure — Per-Module Mutation Results

**Runner:** `scripts/run_mutation_campaign.py`  
**Command:** `.venv\Scripts\python.exe scripts/run_mutation_campaign.py --output results/mutation_campaign_report.json`  
**Total Targeted Mutants:** 20 across 8 core production modules  
**Overall Targeted Kill Rate:** **20 / 20 (100.0%)** — 0 survived, 0 invalid mutants, 0 execution errors  

> **Scope & Denominator Disclosure:** This campaign executes 20 mathematically meaningful runtime mutations across 8 core production modules (14 pre-existing mutants preserved + 6 newly added FEM/estimator mutants). It is a targeted runtime mutation campaign rather than whole-repository AST source mutation (mutmut is restricted on Windows per issue #397).

---

## 1. Per-Module Mutation Score Summary

| Production Module | Killed | Total | Survived | Invalid | Errors | Mutation Score |
|---|---|---|---|---|---|---|
| `gdec.fem.elasticity` | 3 | 3 | 0 | 0 | 0 | **100.0%** |
| `gdec.fem.estimators` | 5 | 5 | 0 | 0 | 0 | **100.0%** |
| `gdec.fem.matrix_diagnostics` | 2 | 2 | 0 | 0 | 0 | **100.0%** |
| `gdec.fem.adaptivity` | 2 | 2 | 0 | 0 | 0 | **100.0%** |
| `gdec.dse.scaling` | 2 | 2 | 0 | 0 | 0 | **100.0%** |
| `gdec.dse.evaluator` | 3 | 3 | 0 | 0 | 0 | **100.0%** |
| `gdec.eir.expressions` | 2 | 2 | 0 | 0 | 0 | **100.0%** |
| `gdec.eir.models` | 1 | 1 | 0 | 0 | 0 | **100.0%** |
| **Total** | **20** | **20** | **0** | **0** | **0** | **100.0%** |

---

## 2. Newly Added Core FEM & Estimator Mutants (WP2-B)

| Mutation ID | Module | Production Function | Mutant Description | Target Test | Baseline | Classification | Rationale |
|---|---|---|---|---|---|---|---|
| `MUT-FEM-03` | `gdec.fem.elasticity` | `LinearElasticitySolver.assemble_stiffness` | Scale global stiffness matrix `K` by `0.5` while preserving SPD structure | `tests/test_fem_mathematical_verification.py::test_cantilever_beam_timoshenko_analytical_comparison` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Timoshenko deflection comparison fails when stiffness is halved |
| `MUT-EST-01` | `gdec.fem.estimators` | `FacetTractionJumpEvaluator.evaluate` | Negate inter-element traction jumps `[[sigma_h n]]` across interior facets | `tests/test_dwr_verification.py::test_dwr_qoi_error_estimation_and_effectivity_convergence` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Effectivity index becomes negative and fails bounds |
| `MUT-EST-02` | `gdec.fem.estimators` | `DualWeightEvaluator.compute_edge_bubble_integral` | Corrupt Hermite edge bubble constant from `h_F^2/12` to `h_F^2/6` | `tests/test_dwr_verification.py::test_dwr_manufactured_polynomial_bubble_integration` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Manufactured polynomial bubble integral doubles and fails exactness check |
| `MUT-EST-03` | `gdec.fem.estimators` | `ElementResidualEvaluator.evaluate` | Ignore constitutive `thickness` parameter (force `thickness=1.0`) | `tests/test_dwr_verification.py::test_dwr_element_volume_residual_thickness_scaling` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Volume residual fails linear thickness scaling assertion |
| `MUT-EST-04` | `gdec.fem.estimators` | `DWREstimator.estimate` | Invert `signed_qoi_error_estimate` sign in `DWREstimator.estimate` | `tests/test_estimators.py::test_estimator_indicators` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Sign check (`signed_qoi_error_estimate < 0.0`) fails |
| `MUT-EST-05` | `gdec.fem.estimators` | `RefinementEstimator.compute_zz_recovery_indicator` | Zero out ZZ recovery energy norm indicators and priorities | `tests/test_estimators.py::test_estimator_indicators` | `BASELINE_PASS` | `KILLED` (`AssertionError`) | Non-zero ZZ indicator assertion (`max > 0.0`) fails |

*(All 14 pre-existing mutants `MUT-FEM-01`, `MUT-FEM-02`, `MUT-SOLV-01`, `MUT-SOLV-02`, `MUT-AMR-01`, `MUT-AMR-02`, `MUT-DSE-01..05`, `MUT-EIR-01..03` remain preserved and killed 14/14.)*
