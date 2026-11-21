# GDEC Phase 4.8 — Solver Eligibility, Prediction & Selection Architecture

## 1. Architectural Overview

The goal of this design specification is to provide a mathematically grounded, empirically calibrated decision framework for linear solver selection in GDEC.

The architecture strictly decouples three distinct responsibilities:
1. **Eligibility Analysis:** Determines which numerical algorithms are mathematically permissible for a given linear system.
2. **Performance Prediction:** Estimates computational cost (FLOPs, wall-clock time, and memory) based on benchmarked empirical models.
3. **Solver Selection Policy:** Selects the lowest-cost verified solver satisfying the engineering Quantity of Interest (QoI) accuracy requirement.

```
                           +------------------------+
                           | Condensed System K_ff  |
                           +------------------------+
                                       |
                                       v
                    +--------------------------------------+
                    | Stage 1: Eligibility Analysis        |
                    | - Square: n == m                     |
                    | - Symmetry: delta_sym < 1e-8         |
                    | - Definiteness: null_modes == 0, SPD |
                    | - Memory feasibility                 |
                    +--------------------------------------+
                                       |
                         Eligible Solver Candidates
                                       |
                                       v
                    +--------------------------------------+
                    | Stage 2: Performance Prediction      |
                    | - Predict Factorization Time (Direct)|
                    | - Predict Reuse Speedup (Adjoint)    |
                    | - Predict Iteration Count (Krylov)   |
                    | - Predict Memory Footprint           |
                    +--------------------------------------+
                                       |
                         Predicted Cost & Memory
                                       |
                                       v
                    +--------------------------------------+
                    | Stage 3: Selection Policy            |
                    | - Primal + Adjoint Workload          |
                    | - Engineering QoI Target Accuracy    |
                    | - Recommendation & Validation Gate   |
                    +--------------------------------------+
```

---

## 2. Stage 1: Eligibility Analysis

Before applying any solver, the system matrix $K_{ff}$ must pass mathematical eligibility gates:

| Gate | Check Metric | Requirement for Direct (SuperLU) | Requirement for Standard CG | Requirement for Preconditioned CG (PCG) |
|---|---|---|---|---|
| **Dimensionality** | Matrix dimensions | $n_{\text{rows}} == n_{\text{cols}}$ | $n_{\text{rows}} == n_{\text{cols}}$ | $n_{\text{rows}} == n_{\text{cols}}$ |
| **Symmetry** | $\delta_{\text{sym}} = \frac{\|K - K^T\|_F}{\max(\|K\|_F, \epsilon)}$ | Any (SuperLU supports unsymmetric) | $\delta_{\text{sym}} \le 10^{-8}$ | $\delta_{\text{sym}} \le 10^{-8}$ |
| **Positive Definiteness** | Smallest eigenvalue $\lambda_{\min}$ | $\lambda_{\min} \ne 0$ (Non-singular) | $\lambda_{\min} > 0$ (SPD) | $\lambda_{\min} > 0$ (SPD) |
| **Rigid-Body Null Modes** | $\lambda_i / \lambda_{\max} < 10^{-10}$ | $0$ null modes | $0$ null modes | $0$ null modes |
| **Preconditioner Symmetry** | $M \approx K$ operator | N/A | N/A | $M = M^T$ (SPD) — ILU rejected |

If a matrix fails CG eligibility (e.g., asymmetric or non-positive-definite due to unconstrained rigid-body motion), the system must reject CG immediately with a clear diagnostic error rather than silently falling back.

---

## 3. Stage 2: Performance Prediction Models

Based on Phase 4 empirical measurements across 2D linear elasticity problems ($N \in [50, 10,000]$ DOFs):

### 3.1 Direct Sparse Solver (SuperLU via `factorized`)
- **Factorization Time:**
  $$T_{\text{fac}}(N) \approx 4.6 \times 10^{-5} \cdot N^{1.5} \text{ ms}$$
  (e.g., $2.3\text{ ms}$ at $N=1,000$; $43\text{ ms}$ at $N=9,120$).
- **Triangular Backsolve Time (Per RHS):**
  $$T_{\text{solve}}(N) \approx 2.0 \times 10^{-4} \cdot N \text{ ms}$$
  (e.g., $0.12\text{ ms}$ at $N=1,000$; $1.8\text{ ms}$ at $N=9,120$).
- **Combined Primal + Adjoint Solve (with Factorization Reuse):**
  $$T_{\text{direct, total}}(N) = T_{\text{fac}}(N) + 2 \cdot T_{\text{solve}}(N)$$

### 3.2 Preconditioned Conjugate Gradient (Jacobi-PCG)
- **Setup Time:** $T_{\text{setup}}(N) \approx 1.2 \times 10^{-5} \cdot N \text{ ms}$ (negligible).
- **Per-Iteration Time:** $T_{\text{iter}}(N) \approx 8.5 \times 10^{-5} \cdot N \text{ ms}$.
- **Iteration Count Scaling:**
  For quasi-uniform 2D elasticity:
  $$N_{\text{iter}}(N) \approx 12 \cdot \sqrt{N}$$
  (e.g., 380 iterations at $N=1,000$; 1,100 iterations at $N=9,120$).
- **Combined Primal + Adjoint Solve (Without Reuse):**
  Since the adjoint problem must be solved from scratch:
  $$T_{\text{pcg, total}}(N) = T_{\text{setup}}(N) + 2 \cdot \left( N_{\text{iter}}(N) \cdot T_{\text{iter}}(N) \right) \approx 2.0 \times 10^{-3} \cdot N^{1.5} \text{ ms}$$

### 3.3 Complexity Ratio and Crossover Analysis
Comparing $T_{\text{pcg, total}}(N)$ to $T_{\text{direct, total}}(N)$:
$$\frac{T_{\text{pcg, total}}(N)}{T_{\text{direct, total}}(N)} \approx \frac{2.0 \times 10^{-3} \cdot N^{1.5}}{4.6 \times 10^{-5} \cdot N^{1.5}} \approx 4.3$$
Across all tested 2D problem sizes, **the direct sparse solver with factorization reuse is between $4\times$ and $8\times$ faster than Jacobi-PCG**.

---

## 4. Stage 3: Solver Selection Policy

### 4.1 Production Recommendation
1. **Production Default Solver:**
   The direct sparse solver (`scipy.sparse.linalg.factorized` via SuperLU) must remain the **production default** for all current 2D linear elasticity computations in GDEC.
2. **Experimental Interface:**
   Expose iterative solvers via explicit, opt-in configuration in `LinearElasticitySolver` and execution plans:
   - `solver_type="direct"` (Default, production-verified).
   - `solver_type="cg"` (Experimental unpreconditioned CG).
   - `solver_type="pcg_jacobi"` (Experimental Jacobi-PCG).
   - `solver_type="pcg_ic0"` (Experimental $IC(0)$-PCG).
   - `solver_type="pcg_amg"` (Experimental AMG, available only when `pyamg` is installed).
3. **Adaptive QoI-Driven Tolerance Calibration:**
   When iterative solvers are selected for large-scale systems, the solver tolerance should be calibrated to the required engineering accuracy:
   $$\text{rtol} = \min\left(10^{-4}, \, 0.1 \cdot \frac{\text{target\_accuracy\_pct}}{100}\right)$$
   For a $1\%$ target QoI accuracy, $\text{rtol} = 10^{-3}$ provides $10^{-8}$ engineering QoI precision, reducing Krylov iterations by $30\text{--}40\%$ compared to standard $\text{rtol} = 10^{-8}$.
