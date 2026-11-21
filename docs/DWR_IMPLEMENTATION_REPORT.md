# GDEC — Dual-Weighted Residual (DWR) Implementation Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `audit/v0.2.2-deep-review`  
**Primary Module:** `src/gdec/fem/estimators.py`  
**Integration:** `src/gdec/core/runtime.py`, `src/gdec/core/planner.py`, `src/gdec/language/ir.py`, `src/gdec/language/semantic.py`  
**Verification Suite:** `tests/test_dwr_verification.py`  
**Date:** 2026-11-21 (Phase 3.1 Corrected Baseline)  

---

## 1. Architectural Design & Component Responsibility

The DWR framework in GDEC is implemented through modular, decoupled classes with clear separation of concerns:

```
+---------------------------------------------------------------------------------------+
|                                  RefinementEstimator                                  |
+-------------------------------------------+-------------------------------------------+
                                            | delegates
       +------------------------------------+-----------------------------------+
       |                                    |                                   |
+------v---------------------------+ +------v---------------------------+ +-----v---------------------------+
|    FacetTractionJumpEvaluator    | |       DualWeightEvaluator        | |     ElementResidualEvaluator    |
+----------------------------------+ +----------------------------------+ +---------------------------------+
| - Facet connectivity & lengths   | | - Area-weighted patch gradient   | | - R_K = b + div(sigma_h)        |
| - Outward facet unit normals     | |   recovery: grad_z*              | | - Zero for P1 without body force|
| - Interior traction jumps:       | | - Cubic Hermite edge bubble      | | - 3-point midpoint quadrature   |
|   [[sigma_h n]] = T_0 - T_1      | |   integration: (h^2/12)(z0 - z1) | |   for nonzero body force        |
| - Boundary traction residuals:   | | - Component-wise Dirichlet trace | | - Volume contribution logging   |
|   r_F = t_applied - T_0          | |   zeroing via sol.dofs_fixed     | |                                 |
+------------------+---------------+ +------------------+---------------+ +-----------------+---------------+
                   |                                    |                                 |
                   +------------------------------------+---------------------------------+
                                                        |
                                          +-------------v-------------+
                                          |       DWREstimator        |
                                          +---------------------------+
                                          | - Exact signed residual:  |
                                          |   - [[sigma n]] . W_F     |
                                          |   + r_F . W_F             |
                                          |   + int_K R_K . w dOmega  |
                                          | - Conservative 50/50 cell |
                                          |   distribution            |
                                          | - Cost-aware priorities   |
                                          +---------------------------+
```

---

## 2. Phase 3.1 Audit Corrections

### 2.1 Boundary-Agnostic Dual Weight Evaluation (`DualWeightEvaluator`)
- **Defect Identified in Audit:** Previous implementation hardcoded `fixed_names = set(fixed_boundary_names or ["left"])`, assuming that only the left boundary could be Dirichlet and checking coordinate boxes ($x \approx 0.0$).
- **Correction Implemented:**
  - Evaluator inspects `sol.dofs_fixed` directly from the condensed finite element system.
  - Component-by-component trace vanishing:
    ```python
    if sol.dofs_fixed is not None and len(sol.dofs_fixed) > 0:
        is_dof_fixed = np.zeros(sol.basis.N, dtype=bool)
        is_dof_fixed[sol.dofs_fixed] = True
        for comp in range(2):
            dofs_v0 = sol.basis.nodal_dofs[comp, v0]
            dofs_v1 = sol.basis.nodal_dofs[comp, v1]
            facet_constrained = is_dof_fixed[dofs_v0] & is_dof_fixed[dofs_v1]
            dual_weights[comp, facet_constrained] = 0.0
    ```
  - Correctly handles left-only, right-only, multiple boundaries, mixed roller/clamped boundaries, and missing or incorrect metadata.

### 2.2 Re-derived First-Principles Edge Bubble Integration
- **Derivation from Cardinal Hermite Basis:**
  $$\int_F (p(s) - \Pi_h z(s)) \, ds = \frac{h_F^2}{12} (z'_0 - z'_1) = \frac{h_F^2}{12} \left[ \nabla \mathbf{z}^*(\mathbf{x}_0) - \nabla \mathbf{z}^*(\mathbf{x}_1) \right] \cdot \mathbf{t}_F.$$
- **Documentation Discrepancy Resolved:** The documentation formula was corrected from $(x_2 - x_1)$ to $(x_0 - x_1)$, matching the exact integration of Hermite cubic shape functions $\int \hat{H}_0 = +1/12$ and $\int \hat{H}_1 = -1/12$.
- **Orientation Invariance Verified:** Proven and tested that reversing facet endpoints $(v_0 \leftrightarrow v_1)$ and tangent $(\mathbf{t}_F \to -\mathbf{t}_F)$ leaves the signed integral strictly invariant.
- **Dimensional Scaling Verified:** $[W_F] = \text{m} \times [z]$, matching the arc length integral.

### 2.3 Exact Sign Convention of Primal Residual
- **Mathematical Origin:**
  $$\rho(\mathbf{u}_h)(\mathbf{w}) = \int_\Omega \mathbf{R}_K \cdot \mathbf{w} \, d\Omega - \sum_{F \in \mathcal{F}_h^{int}} \int_F [\![\boldsymbol{\sigma}_h \mathbf{n}_F]\!] \cdot \mathbf{w} \, ds + \sum_{F \in \mathcal{F}_h^N} \int_F \mathbf{r}_F \cdot \mathbf{w} \, ds.$$
- **Correction:** The interior facet jump appears with a **minus sign** ($-\int_F [\![\boldsymbol{\sigma}_h \mathbf{n}]\!] \cdot \mathbf{w} \, ds$).
- Under cantilever downward tip deflection, both the true error $J(u) - J(u_h)$ and the DWR estimate $\mathcal{E}_{\text{DWR}}$ are naturally negative. The signed effectivity index is strictly positive without taking artificial absolute values:
  $$I_{\text{eff}} = \frac{\mathcal{E}_{\text{DWR}}}{J(u) - J(u_h)} = \frac{-0.2916\text{ mm}}{-0.5680\text{ mm}} = +0.513.$$

### 2.4 Volume Residual Support (`ElementResidualEvaluator`)
- **Defect Identified in Audit:** `ElementResidualEvaluator` was instantiated in `DWREstimator` but never called in `estimate()`.
- **Correction Implemented:**
  - `ElementResidualEvaluator.evaluate()` is called directly inside `estimate()`.
  - For standard benchmark BVPs without body force, $\mathbf{R}_K = \mathbf{0}$, which is explicitly computed and recorded (`volume_residual_contribution = 0.0`, `is_zero_body_force = True`).
  - When non-zero body forces $\mathbf{b}(\mathbf{x})$ are provided, 3-point midpoint quadrature evaluates the volume integral against the reconstructed dual bubble. Residual terms are never silently omitted.

---

## 3. Comprehensive Verification Test Suite

The verification suite [tests/test_dwr_verification.py](file:///f:/fem-edit-benchmark/tests/test_dwr_verification.py) contains 12 rigorous numerical tests:

| Test Name | Physical / Numerical Capability | Acceptance Threshold | Result |
| :--- | :--- | :--- | :--- |
| `test_dwr_constant_stress_zero_residual` | Constant strain patch test (linear $u$) | Jumps $< 10^{-6}\text{ Pa}$, $\mathcal{E}_{\text{DWR}} < 10^{-10}\text{ m}$ | **PASSED** |
| `test_dwr_nonzero_residual_under_discretization_error` | Coarse cantilever with discretization error | Max jump $> 10^5\text{ Pa}$, $\eta_K > 0$ | **PASSED** |
| `test_dwr_facet_orientation_invariance` | Inverted element index order and flipped normal | Jump magnitude relative error $< 10^{-14}$ | **PASSED** |
| `test_dwr_equal_and_opposite_traction_jump` | Newton's action-reaction law across facet | $T_{0 \to 1} + T_{1 \to 0} = \mathbf{0}$ ($< 10^{-12}$) | **PASSED** |
| `test_dwr_dual_solution_consistency` | Discrete adjoint residual $\|K_{\text{free}} z - g\|$ | Relative residual $< 10^{-12}$ | **PASSED** |
| `test_dwr_qoi_error_estimation_and_effectivity_convergence` | Multi-reference convergence ($65\times 33$, $129\times 65$) | Correct sign ($< 0$), $I_{\text{eff}} \in [0.45, 1.05]$ | **PASSED** |
| `test_dwr_adaptive_refinement_reduces_qoi_error` | 4-iteration adaptive refinement sequence | Error reduction over sequence, final $< 5\%$ | **PASSED** |
| `test_dwr_zero_load_degenerate_behavior` | Zero applied load | $\mathcal{E}_{\text{DWR}} = 0$, all indicators $= 0$ | **PASSED** |
| `test_dwr_distorted_mesh_numerical_stability` | Perturbed non-uniform Delaunay mesh | Finite, positive indicators, no NaNs | **PASSED** |
| `test_dwr_dual_boundary_treatments` | Left-only, right-only, multi-, mixed-roller/clamped | Trace vanishes strictly on constrained DOFs | **PASSED** |
| `test_dwr_manufactured_polynomial_bubble_integration` | Exact calculus on $[0, h_F]$ for $P_1, P_2, P_3$ | Matches exact integrals to machine precision ($10^{-14}$) | **PASSED** |
| `test_dwr_element_volume_residual_support` | Zero body force and non-zero body force | Exact zero logging; non-zero quadrature evaluated | **PASSED** |

Execution: **12/12 passed in 1.33s**. Full suite: **137/137 passed in 9.06s**.
