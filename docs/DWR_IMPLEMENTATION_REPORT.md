# GDEC — Dual-Weighted Residual (DWR) Implementation Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `audit/v0.2.2-deep-review`  
**Primary Module:** `src/gdec/fem/estimators.py`  
**Integration:** `src/gdec/core/runtime.py`, `src/gdec/core/planner.py`, `src/gdec/language/ir.py`, `src/gdec/language/semantic.py`  
**Verification Suite:** `tests/test_dwr_verification.py`  
**Date:** 2026-11-21  

---

## 1. Architectural Overview

The Dual-Weighted Residual (DWR) framework in GDEC is implemented through a modular, decoupled architecture adhering to strict software engineering and numerical mechanics standards:

```
+-------------------------------------------------------------------------------+
|                             RefinementEstimator                                |
+---------------------------------------+---------------------------------------+
                                        | delegates
       +--------------------------------+-------------------------------+
       |                                |                               |
+------v-----------------------+ +------v-----------------------+ +-----v-----------------------+
|  FacetTractionJumpEvaluator  | |     DualWeightEvaluator      | |  ElementResidualEvaluator   |
+------------------------------+ +------------------------------+ +-----------------------------+
| - Element-facet topology     | | - Area-weighted patch        | | - Interior equilibrium      |
| - Outward facet normals      | |   gradient recovery          | |   residual: b + div(sigma)  |
| - Interior traction jumps    | | - Cubic Hermite edge bubble  | | - (Identically 0 for P1     |
| - Neumann boundary residuals | | - Dirichlet zero-weighting   | |    without body forces)     |
+--------------+---------------+ +--------------+---------------+ +-------------+---------------+
               |                                |                             |
               +--------------------------------+-----------------------------+
                                                |
                                  +-------------v-------------+
                                  |       DWREstimator        |
                                  +---------------------------+
                                  | - Signed QoI estimate     |
                                  | - Conservative 50/50      |
                                  |   facet distribution      |
                                  | - Cost-aware priorities   |
                                  +---------------------------+
```

---

## 2. Core Components and Data Structures

### 2.1 `FacetResidualData` (`src/gdec/fem/estimators.py`)
Encapsulates all topological and numerical information associated with mesh edges (facets):
- `facet_nodes`: `(2, nfacets)` array of vertex indices.
- `element_0`, `element_1`: `(nfacets,)` indices of adjacent elements (`element_1 = -1` for boundary facets).
- `is_interior`: `(nfacets,)` boolean mask identifying interior versus boundary edges.
- `normals`: `(2, nfacets)` unit normal vectors oriented outward from `element_0` towards `element_1`.
- `lengths`: `(nfacets,)` facet edge lengths $h_F$.
- `traction_jumps`: `(2, nfacets)` interior facet traction jump vectors $[\![\boldsymbol{\sigma}_h \mathbf{n}]\!]_F$.
- `boundary_residuals`: `(2, nfacets)` Neumann boundary traction residual vectors $\mathbf{t}_N - \boldsymbol{\sigma}_h \mathbf{n}$.
- `dual_weights`: `(2, nfacets)` integrated adjoint error weights $\mathbf{W}_F = \int_F (\mathbf{z} - \Pi_h \mathbf{z}) \, ds$.

### 2.2 `FacetTractionJumpEvaluator`
Constructs facet connectivity from triangle adjacency without external C-extensions:
- For each facet, the outward normal is computed as:
  $$
  \mathbf{t} = \frac{\mathbf{x}_1 - \mathbf{x}_0}{\|\mathbf{x}_1 - \mathbf{x}_0\|}, \quad \mathbf{n}_{\text{candidate}} = [t_y, -t_x]^T.
  $$
- Verified outward orientation: if $\mathbf{n}_{\text{candidate}} \cdot (\mathbf{x}_{\text{mid}} - \mathbf{x}_{\text{centroid}, 0}) < 0$, $\mathbf{n} = -\mathbf{n}_{\text{candidate}}$.
- Interior traction jump:
  $$
  [\![\boldsymbol{\sigma}_h \mathbf{n}]\!]_F = (\boldsymbol{\sigma}_{e_1} - \boldsymbol{\sigma}_{e_0}) \mathbf{n}_F.
  $$
- Boundary traction residual:
  $$
  \mathbf{r}_F = \mathbf{t}_{\text{applied}} - \boldsymbol{\sigma}_{e_0} \mathbf{n}_F.
  $$

### 2.3 `DualWeightEvaluator`
Evaluates the dual solution error weight $\mathbf{z} - \Pi_h \mathbf{z}$ along facets using area-weighted patch gradient recovery:
1. Recovers continuous nodal gradient $\nabla \mathbf{z}^*$ at all mesh vertices:
   $$
   \nabla \mathbf{z}^*(v) = \frac{\sum_{K \in \omega_v} A_K \nabla \mathbf{z}|_K}{\sum_{K \in \omega_v} A_K}.
   $$
2. Evaluates the cubic Hermite facet bubble integral along facet $F = [v_0, v_1]$:
   $$
   \mathbf{W}_F = \frac{h_F^2}{12} \left[ \nabla \mathbf{z}^*(v_1) \mathbf{t}_F - \nabla \mathbf{z}^*(v_0) \mathbf{t}_F \right].
   $$
3. Strictly zeroes the weight on Dirichlet boundaries where dual error vanishes by definition: $\mathbf{W}_F = \mathbf{0}$ on $\Gamma_D$.

### 2.4 `ElementResidualEvaluator`
Evaluates interior element residuals $\mathbf{R}_K = \mathbf{b} + \nabla \cdot \boldsymbol{\sigma}_h$. For linear triangular elements ($P_1$) under zero body force, $\mathbf{R}_K \equiv \mathbf{0}$, correctly verifying that all residual error resides on facet discontinuities.

### 2.5 `DWREstimator`
Computes the global signed QoI error estimate and localized refinement indicators:
$$
\mathcal{E}_{\text{DWR}} = \sum_{F \in \mathcal{F}_h^{int}} t \cdot \mathbf{j}_F \cdot \mathbf{W}_F + \sum_{F \in \mathcal{F}_h^N} t \cdot \mathbf{r}_F \cdot \mathbf{W}_F.
$$
Distributes facet absolute error contributions:
- Interior facets: 50% to $e_0$, 50% to $e_1$.
- Boundary facets: 100% to $e_0$.
- Priority: $P_K = \eta_K / \Delta \text{Cost}_K$.

---

## 3. End-to-End Pipeline Integration

The DWR framework is integrated across the complete GDEC stack:

1. **Intermediate Representation (`src/gdec/language/ir.py`):**
   - Expanded `AdaptivityIR.strategy` Literal to include `"dwr"` and `"goal_oriented_dwr"`.
2. **Semantic Analysis (`src/gdec/language/semantic.py`):**
   - Validates strategy names and options during DSL compilation.
3. **Execution Planner (`src/gdec/core/planner.py`):**
   - Generates plan rationales and execution metadata for DWR goal-oriented refinement.
4. **Intelligent Runtime (`src/gdec/core/runtime.py`):**
   - Automatically activates adjoint linear solve (`solve_adjoint=True`) when strategy is `"dwr"` or `"goal_oriented_dwr"`.
   - Dispatches indicator computation to `estimator.compute_dwr_indicator()`.
   - Records signed QoI error estimate and effectivity metadata in step logs.

---

## 4. Comprehensive Verification Test Suite

A dedicated verification test suite (`tests/test_dwr_verification.py`) containing 9 comprehensive numerical verification tests was constructed and passed:

| Test Case | Description | Verification Criterion | Status |
| :--- | :--- | :--- | :--- |
| `test_dwr_constant_stress_zero_residual` | Linear displacement, constant strain field | Interior traction jumps $< 10^{-6}$ Pa; Global DWR estimate $< 10^{-10}$ m | **PASSED** |
| `test_dwr_nonzero_residual_under_discretization_error` | Coarse mesh cantilever under shear | Interior traction jumps $> 0$; DWR indicators strictly positive | **PASSED** |
| `test_dwr_facet_orientation_invariance` | Invert facet element assignment and normal | Traction jump magnitude is invariant ($< 10^{-14}$); vector is identical | **PASSED** |
| `test_dwr_equal_and_opposite_traction_jump` | Action-reaction law across interface | $T_{0 \to 1} + T_{1 \to 0} = 0$ to machine precision ($< 10^{-12}$) | **PASSED** |
| `test_dwr_dual_solution_consistency` | Discrete adjoint system residual | Relative dual residual $\|K_{\text{free}} z_{\text{free}} - g_{\text{free}}\| / \|g\| < 10^{-12}$ | **PASSED** |
| `test_dwr_qoi_error_estimation_and_effectivity_convergence` | Mesh sequence $(9\times 5, 17\times 9, 33\times 17)$ vs $65\times 33$ | Signed estimate has correct sign; Effectivity $I_{\text{eff}} \in [0.5, 1.3]$ and converges | **PASSED** |
| `test_dwr_adaptive_refinement_reduces_qoi_error` | 4-iteration adaptive refinement loop | Monotonic error reduction; final error $< 5\%$ | **PASSED** |
| `test_dwr_zero_load_degenerate_behavior` | Zero applied load | Primal and dual solutions zero; all indicators strictly zero | **PASSED** |
| `test_dwr_distorted_mesh_numerical_stability` | Perturbed, non-uniform Delaunay mesh | No NaNs/Infs; indicators bounded and stable | **PASSED** |

Full suite execution: **134 passing tests in 8.68s** with zero regressions.
