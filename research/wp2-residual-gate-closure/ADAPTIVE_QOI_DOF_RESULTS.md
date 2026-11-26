# WP2 Residual Closure — Adaptive QoI-Error-vs-DOFs Regression Baseline

**Locked Baseline Artifact:** `research/wp2/adaptive_qoi_dof_baseline.json`  
**Regression Test:** `tests/verification/test_adaptive_qoi_regression.py::test_adaptive_qoi_dof_regression_against_locked_baseline`  
**Command:** `.venv\Scripts\python.exe -m pytest -v tests/verification/test_adaptive_qoi_regression.py`  
**Status:** **NUMERICALLY VERIFIED** (1 passed in 1.10s)  

---

## 1. Benchmark Configuration

- **Problem:** 2D Cantilever Beam under End Shear Load (`width = 2.0 m`, `height = 0.5 m`, `thickness = 0.02 m`, `E = 70 GPa`, `nu = 0.33`, plane stress, `loads = [("right", 0.0, -1.0e6)]`, `fixed_boundaries = [("left", ["x", "y"])]`).
- **QoI:** Average vertical tip displacement on the right boundary (`qoi`, meters).
- **Reference QoI:** Uniform `129 x 65` mesh (`16,770` DOFs), $J_{\text{ref}} = -0.0019055703534946412\text{ m}$.
- **Estimator:** `DWREstimator` (`goal_oriented_dwr_estimator`, `is_certified_dwr_bound = False`), marking fraction `0.3`, `max_dofs_budget = 15000`.
- **Note:** DWR is an asymptotically exact goal-oriented error indicator, not a certified mathematical upper bound. Fewer DOFs do not automatically imply wall-clock speedup.

---

## 2. Locked Error-versus-DOFs Trajectory

| Step | DOFs | Elements | QoI $J(u_h)$ [m] | Abs Error [m] | Rel Error | DWR Indicator $|\eta|$ [m] | Marked Elements |
|---|---|---|---|---|---|---|---|
| 0 | 90 | 64 | $-1.337594 \times 10^{-3}$ | $5.679765 \times 10^{-4}$ | $29.81\%$ | $2.916008 \times 10^{-4}$ | 20 |
| 1 | 178 | 146 | $-1.662845 \times 10^{-3}$ | $2.427250 \times 10^{-4}$ | $12.74\%$ | $1.638198 \times 10^{-4}$ | 44 |
| 2 | 400 | 359 | $-1.792643 \times 10^{-3}$ | $1.129278 \times 10^{-4}$ | $5.93\%$ | $8.355734 \times 10^{-5}$ | 108 |
| 3 | 924 | 861 | $-1.854762 \times 10^{-3}$ | $5.080794 \times 10^{-5}$ | $2.67\%$ | $4.172085 \times 10^{-5}$ | 259 |
| 4 | 2128 | 2038 | $-1.882336 \times 10^{-3}$ | $2.323400 \times 10^{-5}$ | $1.22\%$ | $2.056665 \times 10^{-5}$ | 612 |
| 5 | 4716 | 4569 | $-1.897063 \times 10^{-3}$ | $8.507322 \times 10^{-6}$ | $0.45\%$ | $1.013660 \times 10^{-5}$ | 0 |

- **Regression Threshold Justification:** Exact DOF match at every step (deterministic red-green refinement) and `rel_qoi_error <= baseline * 1.01 + 1e-12` (1% relative numerical margin to accommodate cross-platform BLAS/LAPACK floating-point rounding across Linux/Windows/macOS without masking algorithmic regressions).
