# GDEC Phase 4.1.4 — PyAMG Configuration Contract & Evidence Finalization Report

**Document Reference:** `docs/PHASE_4_1_4_AMG_CONTRACT_FINALIZATION_REPORT.md`  
**Repository:** `delythassociates/GDEC`  
**Branch:** `audit/v0.2.2-deep-review`  
**Starting Commit / Baseline HEAD:** `bf583406f36933990a5fd14f2347f87bd85f2a24`  
**Pull Request:** #1 (`https://github.com/delythassociates/GDEC/pull/1`) — Open, draft, unmerged  
**Status:** Complete — All Contract, Mapping, and Evidence Requirements Finalized; 174 Tests Passing (100%)

---

## 1. Executive Summary & Starting Baseline

Following Phase 4.1.3 closure, an independent audit examined commit `bf583406f36933990a5fd14f2347f87bd85f2a24`. While independent CG eligibility bypass was eliminated and the adjoint sweep pair for Gauss-Seidel was introduced, specific contract ambiguities and configuration mismatches remained in PyAMG smoothed aggregation integration:
1. **PyAMG Smoother Name Mismatch:** `"symmetric_gauss_seidel"` was passed directly as a PyAMG smoother name. In PyAMG 5.4.1, relaxation methods are registered under `"gauss_seidel"` with sweep direction specified via `sweep="symmetric"`. Passing `"symmetric_gauss_seidel"` was an unregistered token.
2. **Coarse Solver "default" Token Mismatch:** `"default"` was listed in `VERIFIED_COARSE_SOLVERS`, but passing `coarse_solver="default"` caused PyAMG to raise `ValueError: unknown solver: default`. When omitted or `None`, PyAMG defaults to `"pinv"`.
3. **Semantics of `is_spd`:** The meaning of `AMGPreconditioner.is_spd` required precise delineation: it certifies that the operator is mathematically admissible as an SPD preconditioner *for an SPD input matrix*, not that AMG independently proves positive-definiteness of an uncertified matrix.
4. **Finite-Dimensional Operator Evidence:** Sampled random-vector tests needed to be supplemented with a complete finite-dimensional coordinate basis matrix assembly ($M^{-1} e_j$) and full spectrum positive-definiteness check.
5. **CG `check_eligibility` Deprecation & Invariant Checks:** The docstring for `check_eligibility` was clarified to document that structural checks are unconditional and invariant, and tests were added ensuring both `check_eligibility=True, caller_certified_spd=True` and `check_eligibility=False, caller_certified_spd=True` strictly enforce all structural invariants.

All issues have been remediated, verified with targeted regression tests, confirmed across Python 3.10–3.12 CI matrix, and documented.

---

## 2. Supported Smoother & Coarse-Solver Whitelists and PyAMG Mappings

### 2.1 Smoother Configuration Mapping
In `src/gdec/fem/solvers/iterative.py`, smoothers are validated and mapped to PyAMG arguments as follows:

| GDEC `smoother` Option | PyAMG Pre-Smoother Setting | PyAMG Post-Smoother Setting | Admissible SPD (`is_spd`) | Notes |
|---|---|---|---|---|
| `"gauss_seidel"` | `('gauss_seidel', {'sweep': 'forward'})` | `('gauss_seidel', {'sweep': 'backward'})` | **`True`** | Exact adjoint sweep pair guaranteeing self-adjointness |
| `"symmetric_gauss_seidel"` | `('gauss_seidel', {'sweep': 'symmetric'})` | `('gauss_seidel', {'sweep': 'symmetric'})` | **`True`** | Symmetric sweep relaxation for both sweeps |
| `"jacobi"` | `('jacobi', {})` | `('jacobi', {})` | **`True`** | Diagonal Jacobi relaxation |
| `None` (Default) | `('block_gauss_seidel', {'sweep': 'symmetric'})` | `('block_gauss_seidel', {'sweep': 'symmetric'})` | **`True`** | PyAMG's documented default smoothed aggregation relaxation |
| `"sor"` | `('sor', {})` | `('sor', {})` | **`False`** | Forward SOR is unsymmetric; fail closed |
| Any unrecognized token | N/A | N/A | Raises `ValueError` | Explicit validation prevents unhandled internal errors or silent defaults |

*Contract Guarantee:* Unsupported smoother options are **never** silently ignored or replaced with defaults.

### 2.2 Coarse-Grid Solver Configuration Mapping

| GDEC `coarse_solver` Option | PyAMG Coarse Solver Argument | Effective Coarse Solver in PyAMG 5.4.1 | Admissible SPD (`is_spd`) | Notes |
|---|---|---|---|---|
| `"splu"` | `"splu"` | `coarse_grid_solver('splu')` | **`True`** | Sparse direct LU factorization on coarse Galerkin matrix |
| `"pinv"` | `"pinv"` | `coarse_grid_solver('pinv')` | **`True`** | Dense pseudoinverse via SVD |
| `"pinv2"` | `"pinv2"` | `coarse_grid_solver('pinv2')` | **`True`** | Dense pseudoinverse via SVD |
| `"default"` | (omitted from kwargs) | `coarse_grid_solver('pinv')` | **`True`** | Normalized to omit argument, selecting PyAMG's default |
| `None` | (omitted from kwargs) | `coarse_grid_solver('pinv')` | **`True`** | Omitted from kwargs, selecting PyAMG's default (`pinv`) |
| `"lu"` | `"lu"` | `coarse_grid_solver('lu')` | **`False`** | Dense unsymmetric LU; fail closed |
| Callable | `callable` | Custom solver | **`False`** | Arbitrary user callables; fail closed |
| Any unrecognized token | N/A | N/A | Raises `ValueError` | Explicit validation prevents internal PyAMG errors |

---

## 3. Admissibility Semantics of `is_spd`

The mathematical definition of `AMGPreconditioner.is_spd` is formalized:
- `AMGPreconditioner.is_spd` denotes that the preconditioner configuration satisfies the four structural requirements for operator self-adjointness and positive-definiteness ($M = M^T > 0$) **when applied to a symmetric positive-definite input matrix**.
- It does **not** imply that configuring PyAMG with `symmetry="symmetric"` proves positive-definiteness for an arbitrary, indefinite, or singular input matrix.
- System positive-definiteness remains governed by:
  1. Default upfront spectral eigensolve ($\lambda_{\min} > \tau_{\text{null}} \lambda_{\text{scale}}$) when `caller_certified_spd=False`.
  2. Explicit domain physics assertion when `caller_certified_spd=True`.

---

## 4. Empirical and Finite-Dimensional Operator Verification

### 4.1 Complete Finite-Dimensional Operator Matrix Check ($N = 100$)
On a standardized 2D 5-point discrete Laplacian matrix ($10 \times 10$ grid, $N = 100$ DOFs), the complete preconditioner operator matrix was constructed by applying $M^{-1}$ to each coordinate basis vector $e_j$ ($j = 1 \dots 100$):
$$M^{-1} = \begin{bmatrix} M^{-1} e_1 & M^{-1} e_2 & \dots & M^{-1} e_N \end{bmatrix}$$

1. **Complete Operator Symmetry Defect:**
   $$\delta_{\text{sym}}(M^{-1}) = \frac{\|M^{-1} - (M^{-1})^T\|_F}{\|M^{-1}\|_F} = 1.63 \times 10^{-16} < 1.0 \times 10^{-12}$$
   Numerical self-adjointness holds to machine precision across all 100 dimensions.
2. **Complete Full-Spectrum Positive Definiteness:**
   Algebraic eigensolve (`scipy.linalg.eigvalsh`) across all 100 eigenvalues:
   $$\lambda_{\min}(M^{-1}) \approx 0.1155 > 0, \quad \lambda_{\max}(M^{-1}) \approx 6.1211$$
   $$\frac{\lambda_{\min}}{\lambda_{\max}} \approx 1.89 \times 10^{-2} \gg 10^{-10}$$
   Every eigenvalue of the preconditioner operator is strictly positive.
3. **Contrast with Unsymmetric Relaxation:**
   When Gauss-Seidel is misconfigured with forward sweeps in both pre- and post-smoothing, the complete operator symmetry defect increases to:
   $$\delta_{\text{sym}}(M^{-1}) = 7.17 \times 10^{-2}$$
   confirming the mathematical necessity of the forward/backward adjoint sweep pair.

### 4.2 Sampled Random-Vector Sanity Checks
As complementary empirical evidence, five random vectors $x, y \sim \mathcal{N}(0, I)$ were evaluated:
- $|x^T M^{-1} y - y^T M^{-1} x| / \max(|x^T M^{-1} y|, |y^T M^{-1} x|) < 1.0 \times 10^{-12}$.
- $x^T M^{-1} x > 0$ for all sampled vectors.

---

## 5. CG Invariant Structural Checks Regression

Tests in `tests/test_iterative_solvers.py` verify that structural necessary conditions are enforced unconditionally for both `check_eligibility=True` and `check_eligibility=False` when `caller_certified_spd=True`:
1. **Nonsymmetric matrix:** Rejected with `ValueError("Matrix is not symmetric")`.
2. **Non-positive diagonal matrix:** Rejected with `ValueError("Matrix diagonal contains non-positive entries")`.
3. **Non-SPD preconditioner (ILU):** Rejected with `ValueError("not symmetric positive-definite")`.
4. **Non-finite entries (NaN/Inf):** Rejected with `ValueError("non-finite")`.

---

## 6. Verification Results

1. **Python Compilation (`compileall`):**
   ```bash
   python -m compileall -q src tests
   # 0 errors, 0 warnings
   ```
2. **Pytest Regression Suite:**
   All 174 tests passing (100%):
   ```
   ============================ 174 passed in 17.5s =============================
   ```
3. **PyAMG Environment Details:**
   - Active PyAMG Version: `5.4.1`
   - SciPy Version: `1.15.2`
   - NumPy Version: `2.2.3`

---

## 7. PR #1 Status & Production Commitments

- **Base Branch:** `main` (strictly preserved, untouched, unmerged).
- **Development Branch:** `audit/v0.2.2-deep-review`.
- **Pull Request:** PR #1 (`delythassociates/GDEC/pull/1`) remains open, draft, and unmerged.
- **Production Default Solver:** Sparse direct SuperLU solver (`scipy.sparse.linalg.factorized`) remains the production default.
- **Phase Boundary:** Phase 4 is formally closed; Phase 5 has not been initiated.
