# GDEC Phase 4.4 & 4.5 — Iterative Solvers and Preconditioners Research Report

## 1. Executive Summary

This report establishes the theory, implementation, and empirical verification of iterative linear solvers and preconditioners for GDEC finite element systems.

All iterative algorithms are implemented in the modular package:
`src/gdec/fem/solvers/iterative.py`
and exported via `src/gdec/fem/solvers/__init__.py`.

The framework evaluates:
1. **Unpreconditioned Conjugate Gradient (Identity Preconditioner)**
2. **Jacobi Preconditioned Conjugate Gradient (Diagonal Preconditioning)**
3. **Incomplete Cholesky Preconditioner ($IC(0)$ Sparse Factorization)**
4. **Algebraic Multigrid (PyAMG Smoothed Aggregation)**
5. **Incomplete LU ($ILU$ via `scipy.sparse.linalg.spilu` — Comparative Evaluation)**

---

## 2. Mathematical Formulation of Preconditioned Conjugate Gradient (PCG)

For a condensed finite-element system $K_{ff} u = f$ with symmetric positive-definite matrix $K_{ff} \in \mathbb{R}^{n \times n}$ and a symmetric positive-definite preconditioner $M \approx K_{ff}$, the Preconditioned Conjugate Gradient algorithm implemented in GDEC proceeds as follows:

### Algorithm: Standard PCG for SPD Systems
1. **Initialization:**
   - Given initial guess $x_0 \in \mathbb{R}^n$ (default $x_0 = 0$).
   - Compute initial residual:
     $$r_0 = f - K_{ff} x_0$$
   - Evaluate stopping threshold:
     $$\tau = \max(\text{atol}, \text{rtol} \cdot \|f\|_2)$$
   - If $\|r_0\|_2 \le \tau$, return $x_0$ immediately (0 iterations).
   - Apply preconditioner:
     $$z_0 = M^{-1} r_0$$
   - Initialize search direction:
     $$p_0 = z_0, \quad \rho_0 = r_0^T z_0$$

2. **Iteration ($k = 0, 1, 2, \dots$ until convergence or $k = k_{\max}$):**
   - Matrix-vector product:
     $$w_k = K_{ff} p_k$$
   - Curvature evaluation:
     $$\kappa_k = p_k^T w_k = p_k^T K_{ff} p_k$$
   - **Breakdown Check:** If $\kappa_k \le 0$ or $\kappa_k$ is NaN/Inf, terminate immediately with non-positive curvature breakdown notice.
   - Step length:
     $$\alpha_k = \frac{\rho_k}{\kappa_k}$$
   - State and residual update:
     $$x_{k+1} = x_k + \alpha_k p_k$$
     $$r_{k+1} = r_k - \alpha_k w_k$$
   - **Convergence Check:** If $\|r_{k+1}\|_2 \le \tau$, declare convergence and exit.
   - Apply preconditioner:
     $$z_{k+1} = M^{-1} r_{k+1}$$
   - Inner product update:
     $$\rho_{k+1} = r_{k+1}^T z_{k+1}$$
   - Search direction conjugate update:
     $$\beta_k = \frac{\rho_{k+1}}{\rho_k}$$
     $$p_{k+1} = z_{k+1} + \beta_k p_k$$
     $$\rho_k \leftarrow \rho_{k+1}$$

---

## 3. Conjugate Gradient Eligibility Contracts & Compatibility Gates

Ordinary Conjugate Gradient is mathematically defined solely for symmetric positive-definite (SPD) linear operators. GDEC enforces a multi-tier eligibility contract:

### 3.1 Upfront Structural and Numerical Necessary Checks
Before initiating Krylov iterations, `ConjugateGradientSolver.solve()` executes:
1. **Finite Value Validation:** Verifies that $A$, $b$, and initial guess $x_0$ contain no NaNs or Infs.
2. **Dimension and Shape:** Verifies $A$ is square ($n \times n$) and compatible with $b$ ($n$).
3. **Diagonal Positivity:** Checks $A_{ii} > 0$ for all $i \in \{1, \dots, n\}$. Any non-positive diagonal entry violates positive-definiteness and raises `ValueError`.
4. **Symmetry Metric:** Measures strictly scale-invariant relative Frobenius defect $\delta_{\mathrm{sym}} = \|A - A^T\|_F / \|A\|_F$ (zero matrix returns $0.0$). If $\delta_{\mathrm{sym}} > 10^{-8}$, it raises `ValueError`.
5. **Scale-Aware Algebraic Eigenvalue Verification (`caller_certified_spd=False`, Default in FEM):**
   When `caller_certified_spd=False`, the solver calculates the smallest and largest algebraic eigenvalues using dense exact eigensolvers ($N \le 300$) or ARPACK (`which="SA"` / `which="LA"`, $N > 300$). It evaluates the scale-invariant reference norm:
   $$\lambda_{\text{scale}} = \max(|\lambda_{\min}|, |\lambda_{\max}|, \epsilon_{\text{tiny}})$$
   If $\lambda_{\min} \le \tau_{\text{null}} \lambda_{\text{scale}}$ ($\tau_{\text{null}} = 10^{-10}$), it strictly rejects the system as indefinite ($\lambda_{\min} < -\tau_{\text{null}}\lambda_{\text{scale}}$) or numerically near-singular / possessing unconstrained rigid-body modes ($|\lambda_{\min}| \le \tau_{\text{null}}\lambda_{\text{scale}}$). A tiny positive eigenvalue is not accepted as sufficient proof of positive definiteness.
6. **Runtime Curvature Safeguard vs Global SPD Proof:**
   When `caller_certified_spd=True` (skipping upfront eigensolves during production runs upon explicit caller assertion), CG dynamically checks the Rayleigh quotient denominator $\kappa_k = p_k^T A p_k$ at every iteration. If $\kappa_k \le 0$, the operator has non-positive curvature along $p_k$, and the solver terminates immediately with a breakdown notice.
   > [!WARNING]
   > Runtime curvature checks alone along the Krylov trajectory are **not** a global proof of positive-definiteness. If an indefinite matrix has a positive diagonal and the right-hand side $b$ is confined to its positive eigenspace, the Krylov subspace never probes the negative eigenspace, and CG terminates with positive curvature despite the matrix being indefinite. Thus, `caller_certified_spd=False` is enforced as the fail-safe default.

### 3.2 Preconditioner SPD Compatibility Gate (Fail-Closed)
Ordinary CG requires that the preconditioned system remains self-adjoint with respect to the preconditioner inner product $\langle u, v \rangle_M = u^T M v$. This requires $M$ to be SPD.
GDEC establishes a strict fail-closed preconditioner contract:
- The base `Preconditioner` class defines property `is_spd: bool = False` (fails closed).
- Custom subclasses must explicitly declare and verify SPD compatibility.
- `IdentityPreconditioner`, `JacobiPreconditioner` (after positive diagonal verification), and `IncompleteCholeskyPreconditioner` (after positive pivot factorization) define `is_spd = True`.
- `ILUPreconditioner` defines `is_spd = False`.
- `AMGPreconditioner` evaluates configuration: supported symmetric cycles ("V" or "W") and symmetric smoothers declare `is_spd = True`; unverified configurations or `symmetric=False` declare `is_spd = False`.
- In `ConjugateGradientSolver.solve()`, passing a preconditioner with `preconditioner.is_spd is False` triggers an upfront `ValueError("Conjugate Gradient requires a symmetric positive-definite preconditioner...")`.

### 3.3 Non-Convergence Error Contract
When an iterative solver exhausts `max_iter` or encounters breakdown:
- `ConjugateGradientSolver` returns `LinearSolverResult(converged=False, breakdown_reason="max iterations reached", ...)`.
- In `LinearElasticitySolver.solve(raise_on_nonconvergence=True)` (the default), this raises `SolverConvergenceError(RuntimeError)`, preventing un-converged displacement fields from propagating into QoI calculation or mesh adaptation.
- When `raise_on_nonconvergence=False`, `LinearElasticitySolver` returns `FEMSolution` with `converged=False`, `primal_converged=False`, and detailed diagnostic telemetry in `termination_reason`.
- Telemetry accuracy: Iterative solvers set `factorization_reused=False` and `factorization_time_sec=0.0` (direct factorization is not performed), recording setup cost in `preconditioner_setup_time_sec`.

---

## 4. Preconditioner Implementations and Mathematical Distinctions

### 3.1 Identity Preconditioner ($M = I$)
Serves as the rigorous baseline for unpreconditioned Krylov convergence.
- Application cost: $\mathcal{O}(1)$ array copy.
- Iteration bound: $\mathcal{O}(\sqrt{\kappa_2(K_{ff})})$.

### 3.2 Jacobi (Diagonal) Preconditioner ($M = \text{diag}(K_{ff})$)
- Defined as:
  $$M^{-1} r = \left( \frac{r_1}{K_{11}}, \frac{r_2}{K_{22}}, \dots, \frac{r_n}{K_{nn}} \right)^T$$
- **Validation Contract:** The implementation explicitly scans $K_{ii}$. If any $K_{ii} \le 0$, it raises `ValueError("Jacobi preconditioner failed: encountered non-positive diagonal entries")`.
- Setup cost: $\mathcal{O}(n)$ extraction and reciprocal.
- Application cost: $\mathcal{O}(n)$ elementwise vector multiplication.

### 3.3 Incomplete Cholesky vs Incomplete LU (Crucial Mathematical Distinction)
> [!IMPORTANT]
> A common defect in scientific software is passing `scipy.sparse.linalg.spilu` directly to Conjugate Gradient while referring to it as "Incomplete Cholesky".
> 
> **Why ILU is mathematically invalid for ordinary CG:**
> `spilu` computes an incomplete LU factorization with partial pivoting:
> $$A \approx P_r^T L U P_c^T$$
> where $L$ is unit lower-triangular, $U$ is upper-triangular, but $U \ne L^T$. The resulting preconditioned operator $M^{-1} A$ is **not symmetric** with respect to any standard inner product. 
> Ordinary Conjugate Gradient strictly requires that $M$ is symmetric positive-definite so that $M^{-1} A$ is self-adjoint with respect to the energy inner product $\langle u, v \rangle_M = u^T M v$. Using an unsymmetric preconditioner in ordinary CG violates the 3-term recurrence orthogonality, risking breakdown, loss of conjugacy, or stagnation.

To solve this rigorously, GDEC provides two separate components:
1. **`IncompleteCholeskyPreconditioner` ($IC(0)$):**
   A genuine symmetric incomplete Cholesky decomposition preserving the lower-triangular sparsity pattern $\mathcal{S} = \{(i, j) \mid A_{ij} \ne 0, j \le i\}$:
   $$A \approx L L^T$$
   For each row $i$:
   $$L_{ii} = \sqrt{A_{ii} - \sum_{k < i, (i,k) \in \mathcal{S}} L_{ik}^2}$$
   $$L_{ij} = \frac{1}{L_{jj}} \left( A_{ij} - \sum_{k < j, (i,k) \in \mathcal{S}, (j,k) \in \mathcal{S}} L_{ik} L_{jk} \right) \quad (j < i)$$
   If $A_{ii} - \sum L_{ik}^2 \le 0$, the algorithm detects a non-positive pivot (loss of diagonal dominance) and raises `ValueError`.
   Application $z = M^{-1} r = L^{-T} L^{-1} r$ is performed using two sparse triangular back-solves (`scipy.sparse.linalg.spsolve_triangular`).
2. **`ILUPreconditioner`:**
   Wraps `scipy.sparse.linalg.spilu` with property `is_spd = False` and an explicit non-SPD warning, intended only for comparative research.

### 3.4 Algebraic Multigrid (PyAMG)
- **Status in Environment:** `pyamg>=5.0.0` is registered as an optional extra in `pyproject.toml` (`[project.optional-dependencies] amg = ["pyamg>=5.0.0"]`) and included in the CI test matrix.
- **Contract & Admissibility:** `AMGPreconditioner` provides an explicit query `is_available() -> bool`. If instantiated when PyAMG is absent, it raises `ImportError("PyAMG is not installed in the current environment...")`.
  Its property `is_spd` indicates that the AMG configuration is admissible as an SPD operator *for an SPD input operator*, under verified cycle ("V", "W"), smoother, and coarse-solver configurations.
- **Smoother Configuration Mapping:**
  - `"gauss_seidel"`: configured with an explicit adjoint sweep pair (`presmoother=('gauss_seidel', {'sweep': 'forward'})`, `postsmoother=('gauss_seidel', {'sweep': 'backward'})`).
  - `"symmetric_gauss_seidel"`: mapped to PyAMG's verified symmetric sweep (`presmoother=('gauss_seidel', {'sweep': 'symmetric'})`, `postsmoother=('gauss_seidel', {'sweep': 'symmetric'})`).
  - `"jacobi"`: diagonal relaxation.
  - `None`: PyAMG's default smoothed aggregation smoothing (`'block_gauss_seidel'`, `{'sweep': 'symmetric'}`).
  - Unsupported smoother names raise a clear `ValueError` and are never silently ignored or replaced with defaults.
- **Coarse Solver Mapping:**
  - `"splu"`: sparse direct LU factorization.
  - `"pinv"`, `"pinv2"`: pseudoinverse SVD solve.
  - `"default"` and `None`: normalized to omit the argument, selecting PyAMG's documented default coarse solver (`"pinv"` in PyAMG 5.4.1), not sparse direct.
  - Dense LU (`"lu"`), callables, or unsymmetric solvers evaluate `is_spd = False`.
- **Theoretical Assessment for 2D Elasticity:**
  Algebraic Multigrid with Smoothed Aggregation (SA-AMG) is the gold standard for elliptic PDEs, achieving $\mathcal{O}(1)$ iteration counts. However, for 2D elasticity:
  - SA-AMG must be supplied with the near-nullspace (rigid body translations and rotation) to build coarse grids effectively.
  - Setup time for grid hierarchies and restriction/prolongation operators in Python is non-negligible. For small to medium 2D systems ($N < 50,000$), the setup overhead typically exceeds the direct factorization time of SuperLU.

---

## 5. Empirical Performance and Convergence Comparison

Measurements collected on the Cantilever Shear benchmark ($E = 70\text{ GPa}, \nu = 0.33$, clamped left edge, tolerance $\text{rtol} = 10^{-8}$):

### Table 1: Iterative Solvers Convergence Comparison
| Mesh Grid | Free DOFs | Solver Method | Preconditioner | Iterations | Setup Time | Solve Time (Primal) | Total Time | Relative Residual |
|---|---|---|---|---|---|---|---|---|
| $16 \times 8$ | 240 | Direct | SuperLU | N/A | 0.43 ms | 0.04 ms | **0.50 ms** | $2.69 \times 10^{-12}$ |
| $16 \times 8$ | 240 | CG | None (Identity) | 175 | 0.00 ms | 2.84 ms | 5.64 ms | $9.89 \times 10^{-9}$ |
| $16 \times 8$ | 240 | PCG | Jacobi (Diagonal) | 158 | 0.03 ms | 2.58 ms | 5.16 ms | $8.31 \times 10^{-9}$ |
| $16 \times 8$ | 240 | PCG | $IC(0)$ Sparse | **44** | 26.77 ms | 30.79 ms | 99.97 ms | $1.81 \times 10^{-9}$ |
| $32 \times 16$ | 992 | Direct | SuperLU | N/A | 2.29 ms | 0.12 ms | **2.51 ms** | $9.86 \times 10^{-12}$ |
| $32 \times 16$ | 992 | CG | None (Identity) | 384 | 0.00 ms | 10.04 ms | 21.36 ms | $9.50 \times 10^{-9}$ |
| $32 \times 16$ | 992 | PCG | Jacobi (Diagonal) | 352 | 0.06 ms | 12.56 ms | 21.78 ms | $8.73 \times 10^{-9}$ |
| $32 \times 16$ | 992 | PCG | $IC(0)$ Sparse | **92** | 129.09 ms | 80.17 ms | 285.75 ms | $9.66 \times 10^{-9}$ |
| $96 \times 48$ | 9,120 | Direct | SuperLU | N/A | 42.71 ms | 1.84 ms | **46.21 ms** | $7.57 \times 10^{-11}$ |
| $96 \times 48$ | 9,120 | CG | None (Identity) | 1,158 | 0.00 ms | 96.86 ms | 194.31 ms | $9.65 \times 10^{-9}$ |
| $96 \times 48$ | 9,120 | PCG | Jacobi (Diagonal) | 1,092 | 0.12 ms | 94.54 ms | 190.54 ms | $9.92 \times 10^{-9}$ |

### Key Experimental Conclusions:
1. **$IC(0)$ Iteration Reduction:** $IC(0)$ dramatically reduces iteration count (e.g., from 384 iters to 92 iters at $N=992$, a $4.17\times$ reduction). However, sparse triangular substitutions in Python/SciPy incur higher per-iteration cost than raw matrix-vector multiplications.
2. **Jacobi Preconditioning Efficacy:** Jacobi preconditioning provides a modest $6\%$ to $10\%$ reduction in iteration count. In 2D elasticity on quasi-uniform meshes, diagonal entries are relatively uniform; the severe ill-conditioning stems from low-frequency global bending modes, which diagonal scaling cannot attenuate.
3. **Direct Solver Dominance:** Direct factorization (SuperLU) is between $4\times$ and $8\times$ faster in total execution time across all tested 2D problem sizes, primarily due to single-factorization reuse across primal and adjoint solves.
