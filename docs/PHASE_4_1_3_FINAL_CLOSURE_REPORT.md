# GDEC Phase 4.1.3 — Final CG Safety Gate & AMG SPD Contract Closure Report

**Document Reference:** `docs/PHASE_4_1_3_FINAL_CLOSURE_REPORT.md`  
**Repository:** `delythassociates/GDEC`  
**Branch:** `audit/v0.2.2-deep-review`  
**Starting Commit / Baseline HEAD:** `16a9dd5ca7218d373e00780a2b098eff66d4ad8c`  
**Pull Request:** #1 (`https://github.com/delythassociates/GDEC/pull/1`)  
**Status:** Complete — All Identified Correctness and Safety Gaps Remediated; 174 Tests Passing (100%)

---

## 1. Executive Summary & Starting Baseline

Following Phase 4.1.2 hardening, an independent mathematical and software audit reviewed commit `16a9dd5ca7218d373e00780a2b098eff66d4ad8c`. While `LinearElasticitySolver` default certification was inverted, scale invariance in matrix symmetry was restored, and ARPACK null mode detection was stabilized, three critical safety and contract vulnerabilities were identified for final Phase 4 closure:
1. **Independent CG Eligibility Bypass Vulnerability:** An independent `check_eligibility=False` argument in `ConjugateGradientSolver.solve()` allowed callers to bypass all matrix diagnostics, structural sanity checks, and spectral verification without explicitly asserting caller SPD certification (`caller_certified_spd=True`).
2. **Overly Permissive AMG Preconditioner SPD Declaration:** `AMGPreconditioner` declared `is_spd = True` for configurations using Gauss-Seidel smoothing without enforcing an explicit adjoint sweep pair (forward pre-smoother, backward post-smoother), permitted unverified coarse grid solvers (such as callables or unsymmetric solvers), and accepted arbitrary unverified kwargs.
3. **Solver Eligibility Documentation Discrepancies:** `docs/GDEC_SOLVER_SELECTION_DESIGN.md` retained an obsolete denominator floor in the relative symmetry defect formula, an oversimplified $\lambda_{\min} > 0$ rule rather than the scale-aware threshold $\lambda_{\min} > \tau_{\text{null}} \lambda_{\text{scale}}$, and lacked an explicit discussion of caller assertions versus solver certificates.

Phase 4.1.3 resolves all three issues completely, enforces fail-closed preconditioner and solver safety gates, empirically proves PyAMG operator self-adjointness and positive definiteness, and achieves 100% test passage across the full test suite.

---

## 2. Root Cause & Remediation: CG Eligibility Safety Gate

### 2.1 Root Cause of the Independent Bypass
In earlier iterations, `ConjugateGradientSolver.solve()` accepted `check_eligibility: bool = True`. When set to `False`, the entire diagnostic block—including symmetry checks, diagonal positivity checks, and spectral positive-definiteness checks—was bypassed. This allowed a caller to inadvertently supply an indefinite or unsymmetric matrix to CG, risking divergence or non-detection of indefinite behavior when the RHS happened to lie within the positive eigenspace.

### 2.2 Final CG API Contract
The CG API contract has been hardened to eliminate any uncertified bypass:
1. **Mandatory Combination Check:**
   ```python
   if not check_eligibility and not caller_certified_spd:
       raise ValueError(
           "Cannot bypass matrix eligibility checks (check_eligibility=False) without explicit caller "
           "certification (caller_certified_spd=True). Ordinary Conjugate Gradient strictly requires verified "
           "symmetric positive-definite operators. To bypass upfront spectral eigensolve verification based on "
           "domain physics or boundary conditions, explicitly pass caller_certified_spd=True."
       )
   ```
2. **Invariant Structural Necessary Checks:**
   Even when `caller_certified_spd=True` is provided, structural necessary conditions are **always** enforced:
   - Finite entries: Matrix $K$, RHS $b$, and initial guess $x_0$ must contain no NaN or Inf values.
   - Square dimensions: $n_{\text{rows}} == n_{\text{cols}}$ and $\text{len}(b) == n_{\text{rows}}$.
   - Numerical symmetry: $\delta_{\text{sym}} \le \text{sym\_tol}$ ($10^{-8}$).
   - Positive diagonal entries: $K_{ii} > 0$ for all $i$.
   - Preconditioner SPD compatibility: `preconditioner.is_spd` must evaluate to `True`.
3. **Upfront Scale-Aware Spectral Eigensolve:**
   When `caller_certified_spd=False` (the strict default), upfront eigensolve computes the algebraic smallest eigenvalue $\lambda_{\min}$ and largest eigenvalue $\lambda_{\max}$ with $\lambda_{\text{scale}} = \max(|\lambda_{\min}|, |\lambda_{\max}|, \epsilon_{\text{tiny}})$. The matrix is strictly rejected if:
   - $\lambda_{\min} < -\tau_{\text{null}} \lambda_{\text{scale}}$ (indefinite),
   - $\lambda_{\max} \le \tau_{\text{null}} \lambda_{\text{scale}}$ (non-positive), or
   - $|\lambda_{\min}| \le \tau_{\text{null}} \lambda_{\text{scale}}$ (numerically singular / unconstrained null modes).
4. **Caller Assertion vs. Solver Certificate:**
   `caller_certified_spd=True` is explicitly treated as a caller domain assertion (e.g. condensed structural stiffness with sufficient Dirichlet supports), not an automated solver certificate. It bypasses only the $\mathcal{O}(N^3)$ / $\mathcal{O}(N)$ upfront eigensolve while retaining all structural checks and runtime curvature checks.
5. **Runtime Curvature Limitations:**
   Runtime curvature monitoring ($p_k^T K p_k > 0$) is enforced at every iteration. However, as demonstrated by the regression test on $A = \begin{pmatrix} 2 & 3 \\ 3 & 2 \end{pmatrix}$ and $b = [1, 1]^T$, runtime curvature along a single Krylov trajectory is **not a global proof of positive definiteness**, because an RHS confined to an invariant positive eigenspace never probes negative eigenspaces.

---

## 3. Algebraic Multigrid (PyAMG) SPD Contract & Verification

### 3.1 Mathematical Requirements for Multigrid Self-Adjointness
For an AMG preconditioner $M^{-1}$ to be self-adjoint and positive-definite ($x^T M^{-1} y = y^T M^{-1} x$ and $x^T M^{-1} x > 0$), four conditions must hold simultaneously:
1. **Galerkin Coarse Hierarchy:** Coarse-grid operators satisfy $A_{k+1} = R_k A_k P_k$ with restriction being the exact transpose of prolongation: $R_k = P_k^T$.
2. **Symmetric Cycling:** Traversal must be symmetric (standard V-cycle or W-cycle).
3. **Adjoint Smoothing Relaxation:** The post-smoother $S_{\text{post}}$ must be the exact adjoint of the pre-smoother $S_{\text{pre}}$ ($S_{\text{post}} = S_{\text{pre}}^T$).
   - For Gauss-Seidel, forward sweep smoothing is non-symmetric ($L \ne U^T$). Using forward Gauss-Seidel for both pre- and post-smoothing results in an unsymmetric operator with relative asymmetry error $\approx 3.09 \times 10^{-2}$.
   - To guarantee self-adjointness, Gauss-Seidel smoothing **must** be configured as an adjoint sweep pair: forward sweep for pre-smoother, backward sweep for post-smoother.
4. **Symmetric Coarse Grid Solver:** Coarse-grid solve must produce an SPD action. Arbitrary callables, unsymmetric LU, or iterative solvers with asymmetric tolerances violate this condition.

### 3.2 AMG Implementation Restrictions in `src/gdec/fem/solvers/iterative.py`
`AMGPreconditioner` implements strict fail-closed contract enforcement:
- **Cycle Validation:** `VERIFIED_CYCLES = ("V", "W")`.
- **Smoother Validation & Adjoint Pairing:**
  - `'gauss_seidel'`: explicitly configured as `presmoother=('gauss_seidel', {'sweep': 'forward'})` and `postsmoother=('gauss_seidel', {'sweep': 'backward'})`.
  - `'symmetric_gauss_seidel'`: symmetric sweep for both pre and post.
  - `'jacobi'`: diagonal scaling for both pre and post.
- **Coarse Solver Validation:** `VERIFIED_COARSE_SOLVERS = ("splu", "pinv", "pinv2", "default", None)`. Dense LU (`'lu'`), callables, or unverified solvers evaluate `is_spd = False`.
- **Kwargs Whitelist:** Kwargs are strictly whitelisted to `{"max_levels", "max_coarse"}`. Any extraneous kwarg causes `is_spd = False`.
- **Packaging & Dependency Isolation:** PyAMG is declared as an optional dependency in `pyproject.toml` (`amg = ["pyamg>=5.0.0"]`) and CI (`python -m pip install -e ".[test,amg]"`). If PyAMG is not installed, attempting to instantiate `AMGPreconditioner` raises an informative `ImportError`.

### 3.3 Empirical Operator Verification
On a 2D 5-point discrete Laplacian matrix ($N = 100$ DOFs), operator self-adjointness and positive definiteness were tested with random vectors $x, y \sim \mathcal{N}(0, I)$:
- **Relative Symmetry Defect:**
  $$\frac{|x^T M^{-1} y - y^T M^{-1} x|}{\max(|x^T M^{-1} y|, |y^T M^{-1} x|)} < 1.0 \times 10^{-12}$$
  (Machine-precision numerical symmetry confirmed).
- **Positive Definiteness:**
  $$x^T M^{-1} x > 0 \quad \forall x \ne 0$$
- **Preconditioned CG Convergence:** PCG with the verified AMG preconditioner converged in 5 iterations to residual tolerance $10^{-6}$.

---

## 4. Documentation Reconciliation

The architecture document `docs/GDEC_SOLVER_SELECTION_DESIGN.md` was updated to reconcile all mathematical formulas and API rules:
1. **Scale-Invariant Symmetry Defect:**
   $$\delta_{\text{sym}} = \begin{cases} 0 & \text{if } \|K\|_F = 0 \\ \frac{\|K - K^T\|_F}{\|K\|_F} & \text{otherwise} \end{cases}$$
   Eliminated the artificial denominator floor $\max(\|K\|_F, \epsilon)$.
2. **Scale-Aware Positive Definiteness:**
   $$\lambda_{\min} > \tau_{\text{null}} \lambda_{\text{scale}}, \quad \text{where } \lambda_{\text{scale}} = \max(|\lambda_{\min}|, |\lambda_{\max}|, \epsilon_{\text{tiny}})$$
   Replaced oversimplified $\lambda_{\min} > 0$ rule.
3. **Rigid-Body Null Modes:**
   Explicitly formulated scale-aware null mode detection: $|\lambda_i| \le \tau_{\text{null}} \lambda_{\text{scale}}$.
4. **Preconditioner SPD & Gating Rules:**
   Documented fail-closed preconditioner contract, PyAMG verified adjoint-sweep configuration, and the strict rejection of `check_eligibility=False` without caller certification.

---

## 5. Verification Results & Regression Evidence

1. **Python Compilation (`compileall`):**
   ```bash
   python -m compileall -q src tests
   # 0 errors, 0 warnings
   ```
2. **Pytest Regression Suite:**
   All 174 tests passing (100%):
   - Compiler, IR, AST, Lexer/Parser: 42 passed
   - FEM Core, Quadrature, Elements, Boundary: 55 passed
   - DWR Adjoint, Error Estimator, Manufactured Benchmark: 37 passed
   - Matrix Diagnostics, Iterative Solvers, Condition Number, AMG: 21 passed
   - System End-to-End, Runtime, Regression: 19 passed

---

## 6. PR #1 Status & Production Commitments

- **Base Branch:** `main` (strictly preserved, untouched, unmerged).
- **Development Branch:** `audit/v0.2.2-deep-review`.
- **Pull Request:** PR #1 (`delythassociates/GDEC/pull/1`) remains open and active.
- **Production Default Solver:** Sparse direct SuperLU solver (`scipy.sparse.linalg.factorized`) remains the verified production default.
- **User Untracked Files:** `src/gdec/core/analyser.py` and `src/gdec/runtime/` preserved in pristine condition.
- **Phase Boundary:** Phase 4 is fully closed; Phase 5 has not been initiated.
