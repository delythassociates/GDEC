# GDEC Phase 4.1.1 — Matrix Diagnostics, CG Eligibility & Numerical Evidence Remediation Report

**Document Reference:** `docs/PHASE_4_1_1_REMEDIATION_REPORT.md`  
**Repository:** `delythassociates/GDEC`  
**Branch:** `audit/v0.2.2-deep-review`  
**Starting Commit:** `997e0c8c2ec0f9acd96ebcac57f980a0dedecf16`  
**Pull Request:** #1 (`https://github.com/delythassociates/GDEC/pull/1`)  
**Status:** Complete — All P0 and P1 Issues Remediated; 168 Tests Passing (100%)

---

## Section A: Executive Summary & Audit Context

Phase 4 introduced matrix diagnostics, iterative Krylov solvers, preconditioners, conditioning scaling studies, solver benchmarks, and a solver selection architecture. Following completion of Phase 4, an independent scientific and numerical software audit identified critical gaps and mathematical inconsistencies:
1. **Matrix Diagnostics Algorithm Flaw:** Sparse shift-invert mode (`which="LM"` at $\sigma=0.0$) targeted eigenvalues of smallest *magnitude*, failing to identify negative eigenvalues and misclassifying indefinite matrices as SPD.
2. **Arbitrary Scale Factor:** Normalization scale used `max(abs(lambda_max), 1.0)`, breaking scale-invariance for small physical units.
3. **Null Mode Multiplicity Overclaim:** Claiming exact dimension of nullspace in sparse mode without full rank calculation.
4. **Permissive CG Eligibility & Missing Preconditioner Gates:** CG accepted indefinite or singular matrices, accepted non-SPD preconditioners (like ILU) without error, and lacked runtime curvature breakdown safeguards.
5. **Non-Convergence Silently Ignored:** Non-converged Krylov iterations silently produced inaccurate displacement fields without raising an exception or flagging failure in `FEMSolution`.
6. **Inaccurate Iterative Telemetry:** Iterative solvers reported direct factorization reuse when `reuse_factorization=True` was passed, conflating iterative setup with direct factorization.
7. **Aspect Ratio Conditioning Arithmetic & Mechanics Slip:** Claiming $\mathcal{O}(AR^2)$ scaling and writing $5,550 \approx 14^2$ ($14^2 = 196$), missing the actual $\kappa_2 \propto AR^{2.95}$ empirical power law and the physical structural flexural stiffness ($EI/L^3$) mechanism.
8. **Solver Selection Arithmetic Discrepancy:** Stating formulas with ratio $\approx 43.5$ while asserting a $4.3\times$ speedup ratio.
9. **Universal QoI Super-Convergence Overclaim:** Claiming universal $\mathcal{O}(e_u^2)$ QoI super-convergence without noting load- and functional-dependence or stating the Cauchy-Schwarz bound.

Phase 4.1.1 resolves every one of these issues with rigorous mathematics, clean software engineering, thorough documentation reconciliation, and automated regression tests.

---

## Section B: Matrix Diagnostics & Smallest Eigenvalue Algorithm Correction

### The Mathematical Defect in Shift-Invert `which="LM"`
In ARPACK via `scipy.sparse.linalg.eigsh`, setting `sigma=0.0, which="LM"` solves the spectral transformation:
$$(K - \sigma I)^{-1} v = \mu v \implies \mu = \frac{1}{\lambda}$$
Requesting `which="LM"` (Largest Magnitude) searches for the largest $|\mu| = 1 / |\lambda|$, which corresponds to eigenvalues of smallest *absolute value* $|\lambda|$.
For an indefinite symmetric matrix whose spectrum contains negative eigenvalues (e.g. $\lambda_1 = -1.0, \lambda_2 = +3.0$), $|\lambda_1| = 1.0 < 3.0$. But if the matrix has positive eigenvalues closer to zero or clustered near zero, or if shift-invert converges to a small positive eigenvalue, it can completely miss the negative eigenvalue $\lambda = -1.0$.
More critically, shift-invert does not distinguish between negative and positive eigenvalues, meaning `which="LM"` is not an algebraic minimum search.

### The Remediation: Algebraic Extremes with `which="SA"`
The sparse solver algorithm in `src/gdec/fem/matrix_diagnostics.py` was replaced with direct algebraic eigenvalue computation:
- **Largest Algebraic:** `eigsh(K, k=1, which="LA")` yields $\lambda_{\max}$.
- **Smallest Algebraic:** `eigsh(K, k=k_req, which="SA")` searches directly from the negative algebraic end of the real number line ($\lambda \to -\infty$).
- Any negative eigenvalue $\lambda < - \text{null\_tol} \times \text{norm\_scale}$ is directly discovered, immediately classifying the matrix as indefinite (`is_indefinite=True, is_spd=False, is_cg_eligible=False`).

---

## Section C: Scale-Invariant Normalization & Thresholding

### The Dimensional Invariance Defect
The previous implementation defined the spectral normalization scale as:
$$\text{norm\_scale} = \max(|\lambda_{\max}|, 1.0)$$
The inclusion of `1.0` was an arbitrary, unit-dependent threshold. For physical systems where stiffness is scaled in units such that $\lambda_{\max} \ll 1$ (e.g. $10^{-3}\text{ N/m}$ or micro-mechanics), `norm_scale` evaluated to `1.0`. Consequently, an eigenvalue of $10^{-11}$ had ratio $10^{-11} / 1.0 = 10^{-11} \le 10^{-10}$, falsely classifying an invertible matrix as singular!

### The Scale-Invariant Implementation
GDEC replaces the arbitrary `1.0` baseline with machine epsilon floor:
$$\text{norm\_scale} = \max(|\lambda_{\max}|, \epsilon_{\text{tiny}})$$
where $\epsilon_{\text{tiny}} = \text{np.finfo(float).tiny} \approx 2.22 \times 10^{-308}$.
This guarantees exact scale invariance under scalar multiplication:
$$\forall c > 0, \quad \text{diagnostics}(c K) \equiv \text{diagnostics}(K)$$
Verified across 30 orders of magnitude ($c \in [10^{-12}, 10^{18}]$) in `tests/test_matrix_diagnostics.py`.

---

## Section D: Rigid-Body Mode Multiplicity & Spectrum Telemetry

### Mathematical Distinction: Detected Modes vs Exact Nullity
In dense linear algebra ($N \le 400$), full eigensolvers (`scipy.linalg.eigh`) compute all $N$ eigenvalues. The exact nullity is:
$$\text{nullity}(K) = \dim(\text{ker}(K)) = \sum_{i=1}^N \mathbb{I}(|\lambda_i| \le \text{null\_tol} \times \text{norm\_scale})$$
In sparse mode ($N > 400$), computing the complete nullspace dimension is computationally equivalent to a full factorization or rank-revealing SVD ($\mathcal{O}(N^3)$), which defeats the purpose of sparse computation.

### Telemetry Contract
`MatrixDiagnosticsResult` now provides explicit, mathematically precise fields:
1. `null_modes_detected: int`: The count of null modes discovered among the $k$ requested eigenvalues ($k = \min(6, n-2)$). For unconstrained 2D elasticity ($N=576$), requesting $k=6$ algebraic eigenvalues with `which="SA"` discovers all 3 rigid-body modes ($T_x, T_y, R_z$), yielding `null_modes_detected = 3`.
2. `exact_nullity: Optional[int]`: Returns the exact algebraic nullity in dense mode ($N \le 400$), and `None` in sparse mode to prevent false claims of full spectrum resolution.
3. `has_null_modes: bool`: True if `null_modes_detected > 0`.
4. `null_modes_count: int`: Backward-compatibility property returning `null_modes_detected`.

---

## Section E: Conjugate Gradient Eligibility Contract & Upfront Validations

In `src/gdec/fem/solvers/iterative.py`, `ConjugateGradientSolver.solve()` enforces a rigorous eligibility contract:

1. **Input Finiteness:** Validates that $A$, $b$, and $x_0$ contain only finite real values (rejects NaN and $\pm\infty$ with `ValueError`).
2. **Dimension Consistency:** Validates $A$ is 2D square ($n \times n$) and matches $b$ ($n$).
3. **Necessary Diagonal Positivity:** Scans diagonal entries. For any SPD matrix, $A_{ii} = e_i^T A e_i > 0$. If any $A_{ii} \le 0$, the matrix is strictly non-SPD and rejected immediately with `ValueError`.
4. **Symmetry Check:** Measures relative Frobenius defect $\delta_{\mathrm{sym}} \le 10^{-8}$. Asymmetric matrices are rejected with `ValueError`.
5. **Eigenvalue Verification (`caller_certified_spd=False`):**
   When `caller_certified_spd=False`, computes smallest algebraic eigenvalue using ARPACK `which="SA"`. If $\lambda_{\min} \le \text{null\_tol} \times \text{norm\_scale}$, raises `ValueError`.
6. **Runtime Curvature Safeguard:**
   When `caller_certified_spd=True`, verifies positive curvature at every iteration:
   $$\kappa_k = p_k^T A p_k > 0$$
   If $\kappa_k \le 0$, the algorithm halts immediately with a non-positive curvature breakdown notice.

---

## Section F: Preconditioner SPD Compatibility Gate

Ordinary Conjugate Gradient requires the preconditioner $M$ to be symmetric positive-definite. If an unsymmetric preconditioner is used (such as Incomplete LU from `scipy.sparse.linalg.spilu`), the preconditioned operator $M^{-1} A$ is not self-adjoint with respect to the energy inner product $\langle u, v \rangle_M = u^T M v$, leading to loss of conjugacy, residual oscillations, or breakdown.

### The Gate Implementation
- All GDEC preconditioners expose `is_spd: bool`.
  - `IdentityPreconditioner`: `is_spd = True`
  - `JacobiPreconditioner`: `is_spd = True`
  - `IncompleteCholeskyPreconditioner`: `is_spd = True`
  - `AMGPreconditioner`: `is_spd = self.symmetric` (defaults to `True`)
  - `ILUPreconditioner`: `is_spd = False`
- `ConjugateGradientSolver.solve()` enforces:
  ```python
  if preconditioner is not None and not preconditioner.is_spd:
      raise ValueError(
          f"Preconditioner '{preconditioner.__class__.__name__}' is not symmetric positive-definite. "
          "Standard Conjugate Gradient strictly requires an SPD preconditioner. "
          "Use IncompleteCholeskyPreconditioner or JacobiPreconditioner for CG, "
          "or use GMRES/BiCGSTAB for unsymmetric preconditioners like ILU."
      )
  ```
- Regression-tested in `test_cg_preconditioner_spd_compatibility_gate`.

---

## Section G: Non-Convergence Handling & `SolverConvergenceError` Contract

Previously, if an iterative solver failed to converge within `max_iter`, the solver terminated and returned the non-converged displacement vector without signalling an error to the caller.

### The Remediation
1. Defined `SolverConvergenceError(RuntimeError)` in `src/gdec/fem/elasticity.py` and exported via `src/gdec/fem/__init__.py`.
   - Encapsulates `result: LinearSolverResult` and `system: str` ("primal" or "adjoint").
2. Added `raise_on_nonconvergence: bool = True` (default) to `LinearElasticitySolver.solve()`.
   - If primal or adjoint iterative solve fails to reach tolerance, raises `SolverConvergenceError` with exact breakdown reason and iteration count.
3. Added non-convergence handling when `raise_on_nonconvergence=False`:
   - Returns `FEMSolution` with `converged=False`, `primal_converged=False`, `adjoint_converged=False`, and detailed diagnostic strings in `termination_reason`.
4. Exposed `solver_max_iter: Optional[int] = None` in `LinearElasticitySolver.solve()` to allow explicit iteration bounding.

---

## Section H: Solver Telemetry Corrections

Previously, `FEMSolution.factorization_reused` was set to `True` if `reuse_factorization=True` was passed, regardless of whether the solver was direct or iterative!

### The Remediation
- In `LinearElasticitySolver.solve()`:
  - When `solver_type != "direct"`, explicitly sets `actual_fac_reused = False` and `t_factor = 0.0`.
  - Records preconditioner setup wall-clock time in `preconditioner_setup_time_sec`.
  - Direct solvers set `preconditioner_setup_time_sec = 0.0` and report `factorization_time_sec > 0.0`.
- Verified in `test_linear_elasticity_solver_telemetry_corrections`.

---

## Section I: Aspect Ratio Conditioning Mechanics

### The Defect
`docs/CONDITIONING_SCALING_STUDY.md` contained:
$$\frac{\kappa_2(AR=20)}{\kappa_2(AR=1)} = \frac{1.16 \times 10^7}{2.09 \times 10^3} \approx 5,550 \approx 14^2$$
This had an arithmetic error ($14^2 = 196 \ne 5,550$) and claimed $\mathcal{O}(AR^2)$ scaling.

### The Corrected Mechanics & Empirical Model
Log-log regression across measured data points ($AR \in \{1, 2, 5, 10, 20\}$):
$$\kappa_2(AR) \approx 2,090 \times AR^{2.95} \quad (R^2 = 0.9978)$$
$$\frac{\kappa_2(AR=20)}{\kappa_2(AR=1)} = \frac{1.16 \times 10^7}{2.09 \times 10^3} \approx 5,550 \approx 20^{2.88}$$

### Physical Explanation
The condition number growth combines two physical and numerical mechanisms:
1. **Local Element Distortion:** Anisotropic stretching collapses element angles from $45^\circ$ to $2.86^\circ$, causing an $\mathcal{O}(AR^2)$ local stiffness ratio.
2. **Global Structural Bending Mechanics:** A cantilever beam of length $L$ and height $H$ has flexural bending stiffness $k_{\text{flex}} \sim E I / L^3 = \frac{E b}{12} (H/L)^3 \propto AR^{-3}$, while axial stiffness $k_{\text{axial}} \sim E A / L = E b (H/L) \propto AR^{-1}$. The structural operator's spectral condition number $\kappa_2 = \lambda_{\max} / \lambda_{\min}$ is bounded from below by $k_{\text{axial}} / k_{\text{flex}} \propto AR^2$ to $AR^3$.

---

## Section J: Performance Prediction Model Reconciliation

### The Defect
`docs/GDEC_SOLVER_SELECTION_DESIGN.md` contained conflicting formulas:
$$\frac{T_{\text{pcg, total}}(N)}{T_{\text{direct, total}}(N)} \approx \frac{2.0 \times 10^{-3} \cdot N^{1.5}}{4.6 \times 10^{-5} \cdot N^{1.5}} \approx 4.3$$
The fraction $2.0 \times 10^{-3} / 4.6 \times 10^{-5} = 43.48$, yet the text claimed $4.3$.

### The Corrected Empirical Model
We replaced the conflicting formulas with power-law fits directly calibrated to Table 1 measurements:
- Direct with reuse: $T_{\text{direct, total}}(N) \approx 2.9 \times 10^{-4} \cdot N^{1.31}\text{ ms}$
- Jacobi-PCG: $T_{\text{pcg, total}}(N) \approx 2.5 \times 10^{-2} \cdot N^{0.98}\text{ ms}$
- Direct Table Ratios:
  - $N = 56$: $1.80\text{ ms} / 0.22\text{ ms} = \mathbf{8.18\times}$
  - $N = 240$: $5.16\text{ ms} / 0.50\text{ ms} = \mathbf{10.32\times}$
  - $N = 992$: $21.78\text{ ms} / 2.51\text{ ms} = \mathbf{8.68\times}$
  - $N = 4,032$: $69.96\text{ ms} / 16.17\text{ ms} = \mathbf{4.33\times}$
  - $N = 9,120$: $190.54\text{ ms} / 46.21\text{ ms} = \mathbf{4.12\times}$
- Validated conclusion: Direct sparse solver with single-factorization reuse is **$4.1\times$ to $10.3\times$ faster** than Jacobi-PCG for 2D elasticity across all tested mesh scales ($N \le 9,120$).

---

## Section K: Engineering QoI Accuracy & Cauchy-Schwarz Bound Analysis

### Reassessment of Super-Convergence Claims
The previous report claimed universal $\mathcal{O}(e_u^2)$ super-convergence of the Quantity of Interest.
GDEC has qualified this claim with rigorous theoretical and numerical analysis:
1. **Theoretical Bounds:**
   $$|J(u) - J(u_{\text{iter}})| = |g^T (u - u_{\text{iter}})| \le \|g\|_2 \|u - u_{\text{iter}}\|_2$$
   $$|J(u) - J(u_{\text{iter}})| \le \|g\|_{K^{-1}} \|u - u_{\text{iter}}\|_K$$
   Both bounds are linear in displacement error.
2. **Mechanics Insight:** The apparent quadratic decay observed in cantilever tip shear is due to the fact that both load $f$ and adjoint functional $g$ excite the beam's fundamental flexural mode, which CG resolves in the first few iterations. Under axial tension or localized loads, the QoI error scales linearly with displacement error.
3. Multi-configuration behavior is verified in `test_qoi_accuracy_across_multiple_configurations`.

---

## Section L: Automated Test Verification & Regression Matrix

All unit and regression tests pass cleanly on Python 3.13:
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0
rootdir: F:\fem-edit-benchmark
configfile: pyproject.toml
testpaths: tests
collected 168 items

tests\test_audit_regressions.py ..............                           [  8%]
tests\test_benchmark.py .                                                [  8%]
tests\test_cli.py ....                                                   [ 11%]
tests\test_compiler.py ...                                               [ 13%]
tests\test_compiler_validation.py ...................................... [ 35%]
.....................                                                    [ 48%]
tests\test_dwr_verification.py ................                          [ 57%]
tests\test_elasticity.py ....                                            [ 60%]
tests\test_estimators.py .                                               [ 60%]
tests\test_fem_mathematical_verification.py ..........                   [ 66%]
tests\test_ir.py .                                                       [ 67%]
tests\test_iterative_solvers.py .................                        [ 77%]
tests\test_language.py .......                                           [ 81%]
tests\test_matrix_diagnostics.py ..........                              [ 87%]
tests\test_mesh.py ....                                                  [ 89%]
tests\test_runtime.py ..                                                 [ 91%]
tests\test_v021_corrections.py .......                                   [ 95%]
tests\test_v02_adjoint.py .                                              [ 95%]
tests\test_v02_cost_model.py .                                           [ 96%]
tests\test_v02_evaluator.py .                                            [ 97%]
tests\test_v02_profiling_and_reuse.py ..                                 [ 98%]
tests\test_v02_reference.py ..                                           [ 99%]
tests\test_v02_scaling.py .                                              [100%]

============================= 168 passed in 6.78s =============================
```

New automated tests added in Phase 4.1.1:
1. `test_sparse_indefinite_matrix_detection`: Verifies ARPACK `which="SA"` identifies negative eigenvalues in 500x500 sparse matrix and flags indefiniteness.
2. `test_scale_invariance_across_orders_of_magnitude`: Verifies scale invariance across $c \in [10^{-12}, 10^{18}]$.
3. `test_sparse_null_mode_multiplicity_and_detection`: Verifies detected null modes on 576-DOF unconstrained cantilever.
4. `test_cg_rejects_indefinite_matrix`: Verifies CG rejects indefinite matrix upfront.
5. `test_cg_rejects_singular_matrix`: Verifies CG rejects singular matrix upfront.
6. `test_cg_rejects_non_finite_inputs`: Verifies rejection of NaNs and Infs.
7. `test_cg_preconditioner_spd_compatibility_gate`: Verifies ILU rejection by CG.
8. `test_linear_elasticity_solver_non_convergence_handling`: Verifies `SolverConvergenceError` and `FEMSolution.converged=False`.
9. `test_linear_elasticity_solver_telemetry_corrections`: Verifies `factorization_reused=False` and `preconditioner_setup_time_sec`.
10. `test_qoi_accuracy_across_multiple_configurations`: Verifies QoI error bounds across shear and axial configurations.

---

## Section M: PR #1 Reconciliation & Scope Boundary Notice

- **PR #1 Reconciliation:**
  - Pull Request #1 on `delythassociates/GDEC` has been maintained without merging into `main`.
  - All references to "sparse Cholesky" have been eliminated and replaced with "SuperLU sparse LU decomposition (`scipy.sparse.linalg.factorized`)".
  - Test suite count updated to 168 passing tests.
- **Scope Boundary Notice:**
  - This completes Phase 4.1.1 remediation.
  - Phase 5 has not been initiated.
  - User untracked files (`src/gdec/core/analyser.py` and `src/gdec/runtime/`) have been strictly preserved.
