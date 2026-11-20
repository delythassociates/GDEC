# GDEC v0.2 — Baseline Implementation Audit

**Date**: November 2026  
**Auditor**: GDEC Research & Numerical Methods Team  
**Scope**: Codebase audit of GDEC v0.1 prototype before v0.2 enhancements.

---

## 1. Executive Summary

GDEC v0.1 established a working end-to-end prototype encompassing:
1. Declarative `.gdc` domain-specific engineering language.
2. Lark-based lexer/parser, AST, and semantic analyzer lowering to typed `ProblemIR`.
3. 2D linear elasticity FEM formulation with P1 triangular elements.
4. Three distinct refinement strategies: Uniform, Zienkiewicz-Zhu (ZZ) stress recovery, and an Adjoint-informed QoI sensitivity heuristic.
5. An automated benchmark runner, Streamlit dashboard, and 27 passing automated tests.

However, a rigorous numerical and software audit reveals key inconsistencies, heuristic assumptions, and methodological gaps that must be corrected to elevate GDEC into a scientifically defensible research platform.

---

## 2. Detailed Findings & Inconsistencies Identified

### 2.1 Inaccurate Timing Breakdown in Runtime Telemetry
- **Location**: `src/gdec/core/runtime.py` (lines 76–83 in v0.1).
- **Issue**:
  ```python
  t0 = self.telemetry.now()
  sol = self.solver.solve(...)
  t_solve = self.telemetry.now() - t0
  # Separation of assembly vs solver
  assembly_time = t_solve * 0.4
  solver_time = t_solve * 0.6
  ```
  The runtime grouped FEM assembly, boundary enforcement, and sparse linear solves into a single `t_solve` timing block and split it using an arbitrary 40%/60% heuristic.
- **Scientific Impact**: Measured assembly times and solver times in v0.1 iteration logs were synthetic estimates rather than discrete physical measurements.
- **Remediation for v0.2**: Instrument every stage (mesh generation, matrix assembly, boundary condition condensation, sparse factorization, primal solve, adjoint solve, error estimation, element ranking, and mesh refinement) with independent `time.perf_counter()` calls.

### 2.2 Lack of Factorization Reuse Between Primal and Adjoint Solves
- **Location**: `src/gdec/fem/elasticity.py` (`LinearElasticitySolver.solve`).
- **Issue**:
  `fem.condense` and `fem.solve` are invoked separately for the primal system ($\mathbf{K} \mathbf{u} = \mathbf{f}$) and the adjoint system ($\mathbf{K}^T \mathbf{z} = \mathbf{g}$).
  Because $\mathbf{K}$ is symmetric ($\mathbf{K} = \mathbf{K}^T$) and the constrained boundary DOFs are identical, the condensed system matrix $\mathbf{K}_{\text{free}}$ is identical. Factoring $\mathbf{K}_{\text{free}}$ twice incurs a redundant $\mathcal{O}(N^{1.5})$ or $\mathcal{O}(N^3)$ computational cost.
- **Remediation for v0.2**: Factorize $\mathbf{K}_{\text{free}}$ once via `scipy.sparse.linalg.splu` or `factorized`, then perform two rapid $\mathcal{O}(N)$ back-solves for $\mathbf{u}$ and $\mathbf{z}$. Profile and document the exact speedup.

### 2.3 Conflation of Convergence Metric and Benchmark Error Metric
- **Location**: `src/gdec/core/controller.py` vs `src/gdec/benchmark/runner.py`.
- **Issue**:
  The runtime stopping criterion evaluates successive mesh change:
  $$e_{\text{change}} = \frac{|J_k - J_{k-1}|}{\max(|J_k|, \varepsilon)} \times 100\%$$
  The benchmark evaluated accuracy relative to an offline high-resolution reference solution:
  $$e_{\text{ref}} = \frac{|J_k - J_{\text{ref}}|}{\max(|J_{\text{ref}}|, \varepsilon)} \times 100\%$$
  In v0.1, whether an algorithm was deemed "successful" in the benchmark summary table depended on whether it satisfied $e_{\text{change}} \le \text{percent}$ within budget, not whether it reached equivalent reference-relative accuracy.
- **Remediation for v0.2**: Implement an **Equal-Accuracy Benchmark Evaluation Module** that tests all strategies at identical reference-relative error thresholds ($2.0\%$, $1.0\%$, $0.5\%$, $0.25\%$), tracking DOFs, wall time, and iterations to reach each threshold.

### 2.4 Reference Solution Verification Gap
- **Location**: `src/gdec/benchmark/reference.py`.
- **Issue**:
  Only a single numerical reference mesh was generated without checking convergence against a second, finer discretization. Moreover, no comparison was made against classical beam theory (Timoshenko cantilever theory with shear correction).
- **Remediation for v0.2**:
  1. Generate multi-level progressively finer reference meshes ($N_1 \approx 25\text{k}$, $N_2 \approx 60\text{k}$, $N_3 \approx 100\text{k}+$ DOFs) and verify mesh convergence $|J_{\text{ref}, 2} - J_{\text{ref}, 1}| / |J_{\text{ref}, 2}| < 0.05\%$.
  2. Implement an analytical comparison with Timoshenko cantilever beam theory:
     $$\delta_{\text{tip}} = \frac{P L^3}{3 E I} + \frac{P L}{\kappa G A}$$
     Demonstrating consistency between continuum 2D plane-stress FEM and analytical mechanics.

### 2.5 Unverified Sensitivity Adjoint Identity
- **Location**: `src/gdec/fem/estimators.py`.
- **Issue**:
  The adjoint-informed QoI sensitivity heuristic:
  $$\eta_e = h_e^2 A_e \left| \boldsymbol{\epsilon}_e(\mathbf{u}) : \mathbf{C} : \boldsymbol{\epsilon}_e(\mathbf{z}) \right|$$
  relies on the discrete adjoint load vector $\mathbf{g}$ satisfying $J(\mathbf{u}) = \mathbf{g}^T \mathbf{u}$. While algebraically correct for linear functionals, this was not verified against finite-difference perturbations of element stiffness matrices $\frac{\partial J}{\partial E_e}$.
- **Remediation for v0.2**: Implement an automated finite-difference perturbation test verifying:
  $$\frac{\partial J}{\partial E_e} \approx \frac{J(E_e + \Delta E) - J(E_e)}{\Delta E} = - \int_{\Omega_e} \boldsymbol{\epsilon}(\mathbf{u}) : \frac{\mathbf{C}}{E} : \boldsymbol{\epsilon}(\mathbf{z}) \, t \, d\Omega$$
  Confirming the exactness of the adjoint implementation.

### 2.6 Simplified Cost Predictor
- **Location**: `src/gdec/core/cost_model.py`.
- **Issue**:
  The refinement cost model assumed a scalar multiplier of 6 DOFs per marked element with a simple moving average, ignoring element topology, aspect ratio, and boundary edge closure constraints.
- **Remediation for v0.2**: Track prediction error $\text{Error} = |\Delta \text{DOFs}_{\text{actual}} - \Delta \text{DOFs}_{\text{predicted}}|$ and improve prediction using topological connectivity and boundary refinement heuristics.

---

## 3. Baseline Reproduction Verification

- **Automated Tests**: Ran `pytest -v` across `tests/`: 27 passed in 2.68 seconds.
- **Cantilever Benchmark Baseline**:
  - Reference ($24,200$ DOFs): $J_{\text{ref}} = -1.90681\text{ mm}$
  - Uniform Refinement: 4 iterations, $10,098$ DOFs, $e_{\text{ref}} = 0.208\%$, $0.221\text{ s}$
  - ZZ Recovery Refinement: 6 iterations, $8,466$ DOFs, $e_{\text{ref}} = 0.144\%$, $0.287\text{ s}$
  - Goal-Aware Refinement: 6 iterations, $8,328$ DOFs, $e_{\text{ref}} = 0.224\%$, $0.316\text{ s}$
- **Baseline Artifacts**: Archived in `results/v01_baseline/`.

---

## 4. Audit Conclusion & v0.2 Roadmap

The core numerical and compilation infrastructure of GDEC v0.1 is sound, but its research rigor requires:
1. True discrete profiling (no heuristic time splitting).
2. Factorization reuse for the adjoint system.
3. Equal-accuracy benchmark comparison at standard error thresholds.
4. Multi-level reference solution convergence check + Timoshenko analytical validation.
5. Finite-difference validation of adjoint sensitivities.
6. Statistical correlation of predicted vs observed refinement benefits.
7. Large-scale scalability experiments ($10\text{k} \to 200\text{k}$ DOFs).
8. Streamlit Research Validation section and comprehensive scientific reporting.
