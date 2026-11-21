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

Based on Phase 4 empirical measurements across 2D linear elasticity problems ($N \in [56, 9,120]$ DOFs) on the standardized cantilever benchmark:

### 3.1 Empirical Wall-Clock Scaling Models
GDEC explicitly distinguishes between three tiers of performance evidence:
1. **Measured Wall-Clock Benchmarks (Primary Ground Truth):** Direct wall-clock timings measured under standardized repetitions on identical hardware (cantilever shear benchmark, $N \in [56, 9,120]$).
2. **Empirical Power-Law Fits (Calibrated Interpolations):** Calibrated least-squares regressions across the measured dataset range $N \in [992, 9,120]$:
   - **Direct Sparse Solver (SuperLU via `factorized` with Reuse):**
     $$T_{\text{direct, total}}(N) \approx 2.9 \times 10^{-4} \cdot N^{1.31} \text{ ms} \quad (R^2 = 0.9992)$$
     Factorization accounts for $>92\%$ of total direct time; subsequent triangular backsolves take $< 1.85\text{ ms}$ even at $N=9,120$.
   - **Preconditioned Conjugate Gradient (Jacobi-PCG without Reuse):**
     $$T_{\text{pcg, total}}(N) \approx 2.5 \times 10^{-2} \cdot N^{0.98} \text{ ms} \quad (R^2 = 0.9984)$$
     Preconditioner setup time is negligible ($\le 0.12\text{ ms}$), but each solve requires independent Krylov iterations ($N_{\text{iter}} \approx 12 \sqrt{N}$), totaling $2,184$ iterations for primal and adjoint combined at $N=9,120$.
   - **Range of Validity & Extrapolation Limits:** These power-law fits are strictly descriptive of the 2D cantilever benchmark on the measured range $N \in [56, 9,120]$. They must not be extrapolated into universal asymptotic crossover claims or applied indiscriminately to 3D domains or ill-conditioned meshes.
3. **Theoretical Asymptotic Complexity (Upper Bounds):** For 2D sparse direct methods (nested dissection / SuperLU), theoretical factorization complexity is $\mathcal{O}(N^{1.5})$ with backsolve $\mathcal{O}(N \log N)$. For CG/PCG, complexity is $\mathcal{O}(N \cdot \sqrt{\kappa_2})$.

### 3.2 Measured Speedup Ratio and Empirical Crossover Analysis
Comparing total wall-clock times $T_{\text{pcg, total}}$ to $T_{\text{direct, total}}$ directly from the empirical benchmark table:

| DOFs $N$ | Direct Total Time (ms) | Jacobi-PCG Total Time (ms) | Measured Ratio $\frac{T_{\text{pcg}}}{T_{\text{direct}}}$ |
|---|---|---|---|
| 56 | 0.22 | 1.80 | **8.18** $\times$ |
| 240 | 0.50 | 5.16 | **10.32** $\times$ |
| 992 | 2.51 | 21.78 | **8.68** $\times$ |
| 4,032 | 16.17 | 69.96 | **4.33** $\times$ |
| 9,120 | 46.21 | 190.54 | **4.12** $\times$ |

**Summary of Empirical Scaling Findings:**
- Across all tested 2D discretization scales ($N \le 9,120$), **the direct sparse solver with factorization reuse is between $4.1\times$ and $10.3\times$ faster than Jacobi-PCG**.
- Because the direct solver scales as $\mathcal{O}(N^{1.31})$ in 2D while PCG scales as $\mathcal{O}(N^{0.98})$ empirically (due to memory-bandwidth bounds in Python/NumPy loops), direct factorization with reuse maintains a decisive speed advantage for all typical 2D mesh sizes ($N < 50,000$).
- Krylov methods become competitive only for 3D elasticity where direct fill-in scales as $\mathcal{O}(N^2)$ and memory exceeds RAM, or when multiple right-hand sides are not required.

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
3. **User-Controlled Linear Solver Tolerance Policy:**
   Linear solver convergence tolerances (`solver_rtol`, `solver_atol`, and `solver_max_iter`) must be explicitly controlled by the user or problem specification. GDEC does not employ fixed heuristic algebraic tolerance scaling formulas.
   Future goal-oriented tolerance allocation will require validated, problem-specific adjoint error estimates (such as dual-weighted residual bounds) that rigorously relate algebraic residuals to Quantity of Interest discretization errors, rather than uncertified global formulas.
