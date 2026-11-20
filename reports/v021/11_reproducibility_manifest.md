# GDEC v0.2.1 — Report 11: Scientific Reproducibility Manifest and Traceability Matrix

**Document ID**: `GDEC-V021-REP-11`  
**Status**: APPROVED & VERIFIED  
**Date**: 2026-11-20  
**Scope**: Complete scientific traceability matrix connecting all numerical and algorithmic claims to exact source code locations, test harnesses, raw data artifacts, and analytical reports.

---

## 1. Traceability Matrix

The table below provides end-to-end provenance for every major mathematical, algorithmic, and engineering claim in the GDEC v0.2.1 release.

| Scientific / Algorithmic Claim | Primary Source Code Reference | Verification Test Function | Raw Artifact Path | Verification Report |
|:---|:---|:---|:---|:---|
| **Exact Discrete Adjoint Stiffness Sensitivity** ($\frac{\partial J}{\partial E_e} = -\frac{1}{E} \mathbf{z}_e^T \mathbf{K}_e \mathbf{u}_e$, agreement to $1.11 \times 10^{-8}$) | `src/gdec/fem/elasticity.py` (L126–150, L230–239)<br>`src/gdec/fem/estimators.py` (L170–185) | `tests/test_v02_adjoint.py::test_adjoint_qoi_and_force_sensitivity`<br>`tests/test_v021_corrections.py::test_multi_qoi_adjoint_sensitivity` | `results/v021/test_stage2_results.json`<br>`results/v021/adjoint_reconciliation_results.json` | [02_goal_estimator_mathematical_audit.md](file:///f:/fem-edit-benchmark/reports/v021/02_goal_estimator_mathematical_audit.md)<br>[08_adjoint_and_sensitivity_audit.md](file:///f:/fem-edit-benchmark/reports/v021/08_adjoint_and_sensitivity_audit.md) |
| **Heuristic Indicator Classification (`goal_heuristic_v1`)** ($\eta_e = h_e^2 A_e \|\boldsymbol{\sigma}_e : \boldsymbol{\varepsilon}_e(z)\|$, rank correlation $\rho = 0.8095$ with true error reduction) | `src/gdec/fem/estimators.py` (L152–215) | `tests/test_v021_corrections.py::test_estimator_heuristic_v1_and_zz_classification` | `results/v021/test_stage2_results.json` | [02_goal_estimator_mathematical_audit.md](file:///f:/fem-edit-benchmark/reports/v021/02_goal_estimator_mathematical_audit.md) |
| **ZZ Recovery Classification as Area-Weighted Nodal Averaging** ($O(h^1)$ rate, $p \to 0.941$, zero error on uniform strain $2.96 \times 10^{-18}$) | `src/gdec/fem/estimators.py` (L83–151) | `tests/test_v021_corrections.py::test_estimator_heuristic_v1_and_zz_classification` | `results/v021/test_stage3_results.json` | [03_zz_recovery_audit.md](file:///f:/fem-edit-benchmark/reports/v021/03_zz_recovery_audit.md) |
| **Multi-Level Reference Convergence & Roache GCI** (Levels 1–4, $J_\infty = -1.909240$ mm, $\text{GCI} = 0.0796\%$, $0.612\%$ Timoshenko 2D root clamping diff) | `src/gdec/benchmark/reference.py` (L15–125) | `tests/test_v02_reference.py::test_reference_multi_resolution_convergence`<br>`tests/test_v02_reference.py::test_timoshenko_analytical_comparison` | `results/v021/test_stage4_results.json` | [04_reference_convergence_audit.md](file:///f:/fem-edit-benchmark/reports/v021/04_reference_convergence_audit.md) |
| **Equal-Accuracy 3-Strategy Benchmark Reproduction** (Goal-Aware achieves $1.0\%$ at $2.50\times$ fewer DOFs, $0.5\%$ at $1.21\times$ fewer DOFs, $0.25\%$ qualified against GCI) | `src/gdec/benchmark/runner.py` (L20–180)<br>`src/gdec/benchmark/evaluation.py` (L15–110) | `tests/test_benchmark.py::test_benchmark_suite_execution`<br>`tests/test_v02_evaluator.py::test_equal_accuracy_evaluation` | `results/v021/CantileverDemo_equal_accuracy.csv`<br>`results/v021/CantileverDemo_iterations.csv`<br>`results/v021/CantileverDemo_summary.csv` | [05_equal_accuracy_benchmark_audit.md](file:///f:/fem-edit-benchmark/reports/v021/05_equal_accuracy_benchmark_audit.md) |
| **Safe Refinement Transaction & Hard Budget Rollback** (Candidate mesh exceeding budget rolled back; guaranteed `final_dofs <= max_budget`) | `src/gdec/core/runtime.py` (L182–215) | `tests/test_v021_corrections.py::test_transactional_refinement_budget_enforcement`<br>`tests/test_v021_corrections.py::test_transactional_refinement_severe_underprediction` | `results/v021/test_budget_transaction_results.json` | [06_runtime_budget_and_cost_model_audit.md](file:///f:/fem-edit-benchmark/reports/v021/06_runtime_budget_and_cost_model_audit.md) |
| **Cost Model Statistics Reconciliation** ($13.91\%$ mean error, $14.45\%$ median error, $+112.8$ DOFs conservative bias, $0\%$ underprediction) | `src/gdec/core/cost_model.py` (L20–85) | `tests/test_v02_cost_model.py::test_topological_cost_model` | `results/v021/test_cost_model_reconciliation.json` | [06_runtime_budget_and_cost_model_audit.md](file:///f:/fem-edit-benchmark/reports/v021/06_runtime_budget_and_cost_model_audit.md) |
| **Factorization Reuse Speedup Disambiguation** (Isolated solve speedup $1.94\times - 2.14\times$; Total solver pipeline speedup $1.40\times - 1.57\times$) | `src/gdec/fem/elasticity.py` (L217–256) | `tests/test_v02_profiling_and_reuse.py::test_factorization_reuse_speedup_and_accuracy` | `results/v021/performance_and_scalability.json` | [07_performance_and_scalability_audit.md](file:///f:/fem-edit-benchmark/reports/v021/07_performance_and_scalability_audit.md) |
| **Direct Solver Identification & Scalability** (SuperLU 5.x via `scipy.sparse.linalg.splu`, $\mathcal{O}(N^{1.48})$ factorization scaling up to 98,000 DOFs) | `src/gdec/fem/elasticity.py` (L218–228) | `tests/test_v02_scaling.py::test_scalability_runner_moderate_scales` | `results/v021/performance_and_scalability.json` | [07_performance_and_scalability_audit.md](file:///f:/fem-edit-benchmark/reports/v021/07_performance_and_scalability_audit.md) |
| **Computational Backend & Non-Silent Fallback Compliance** (CPU execution only; hardware detection honest; CUDA/HIP/SYCL/TPU rejected with error) | `src/gdec/backends/registry.py` (L14–70)<br>`src/gdec/language/semantic.py` (L334–352) | `tests/test_language.py::test_unsupported_backend_rejected`<br>`tests/test_v021_corrections.py::test_unsupported_backend_rejections` | Live Host Telemetry (`nvidia-smi` query output) | [09_backend_capability_audit.md](file:///f:/fem-edit-benchmark/reports/v021/09_backend_capability_audit.md) |
| **Software Packaging & Quality Assurance** (Version bumped to 0.2.1; `tabulate>=0.9.0` declared; 40 automated tests passing with zero failures) | `pyproject.toml`<br>`src/gdec/__init__.py`<br>`src/gdec/language/ir.py` | Full suite: `pytest -v` (40 passed in 4.70s) | CI / Terminal Output Logs | [10_software_quality_and_test_audit.md](file:///f:/fem-edit-benchmark/reports/v021/10_software_quality_and_test_audit.md) |

---

## 2. Reproduction Instructions

To reproduce all numerical results and verification tests from a clean state:

```powershell
# 1. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Run full 40-test automated suite
pytest -v

# 3. Reproduce Stage 2 Estimator & Sensitivity Audit
python scratch/test_stage2_estimator_audit.py

# 4. Reproduce Stage 3 ZZ Recovery Audit
python scratch/test_stage3_zz_audit.py

# 5. Reproduce Stage 4 Multi-Grid Reference Convergence & 3-Strategy Benchmark
python scratch/test_stage4_reference_and_benchmark.py

# 6. Reproduce Stage 6 Runtime Budget Transaction & Cost Model Audit
python scratch/test_budget_transaction.py
python scratch/test_cost_model_reconciliation.py

# 7. Reproduce Stage 7 Performance & Scalability Profiling
python scratch/test_stage7_performance.py

# 8. Reproduce Stage 8 Adjoint Finite Difference V-Curve Reconciliation
python scratch/test_stage6_adjoint_reconciliation.py
```

All generated output files will populate deterministically in `results/v021/`.
