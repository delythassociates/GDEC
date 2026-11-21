# GDEC Phase 5.1.1 CG Safety Remediation Report

**Document ID:** `GDEC-SOLV-REMED-001`  
**Date:** 2026-11-22  
**Workstream:** A — Solver Safety & Conjugate Gradient Contract  
**Author:** Lead Engineering Research Orchestrator  
**Status:** Remediated, Verified, Adversarially Tested  

---

## 1. Identified Defects in Phase 5.1

In the Phase 5.1 implementation:
1. `CPUBackend.solve_cg` checked only matrix symmetry ($\|A - A^T\|_F / \|A\|_F \le 10^{-10}$) and positive diagonal ($\min(\text{diag}(A)) > 0$).
2. `CUDABackend.solve_cg` checked positive diagonal but omitted full spectral eigensolve checks and ignored `caller_certified_spd`.

### Mathematical Counterexample
Consider the $2 \times 2$ symmetric matrix:
$$A = \begin{bmatrix} 1 & 2 \\ 2 & 1 \end{bmatrix}$$
- **Symmetry Defect:** $\delta_{\text{sym}} = 0.0$ (perfectly symmetric).
- **Diagonal:** $\text{diag}(A) = [1.0, 1.0] > 0$ (strictly positive).
- **Eigenvalues:** $\det(A - \lambda I) = (1 - \lambda)^2 - 4 = 0 \implies \lambda_1 = -1.0, \; \lambda_2 = 3.0$.

Matrix $A$ is **indefinite** despite having a positive diagonal and exact symmetry. In Phase 5.1, both backends accepted this matrix as "SPD" and attempted CG iteration.

---

## 2. Reconciled CG Eligibility Policy

Phase 5.1.1 introduces a unified mathematical eligibility checker in `src/gdec/core/backend/spd_check.py` shared by both `CPUBackend` and `CUDABackend`.

### 2.1 Structural Preconditions (Always Enforced)
- Matrix must be square ($n \times n$).
- Right-hand side $b$ must be a 1D array of length $n$.
- All entries of $A$ and $b$ must be finite (rejects NaN and $\pm\infty$).
- Residual tolerances must be non-negative and finite ($\text{rtol} > 0, \text{atol} \ge 0$).
- Iteration limit $\text{max\_iter}$ must be a positive integer ($> 0$).
- Matrix symmetry must satisfy $\delta_{\text{sym}} = \frac{\|A - A^T\|_F}{\|A\|_F} \le 10^{-8}$.
- Diagonal entries must be strictly positive ($\min(\text{diag}(A)) > 0$).

### 2.2 Positive-Definiteness Policy
- **When `caller_certified_spd=False` (Default Safe Mode):**
  - An upfront spectral eigensolve is unconditionally performed:
    - For $n \le 300$: computes full spectrum via dense eigensolver `scipy.linalg.eigvalsh`.
    - For $n > 300$: computes extremal eigenvalues $\lambda_{\min}$ (`which="SA"`) and $\lambda_{\max}$ (`which="LA"`) via ARPACK `scipy.sparse.linalg.eigsh`.
  - Enforces scale-invariant null threshold: $\tau_{\text{null}} = 10^{-10} \cdot \max(|\lambda_{\min}|, |\lambda_{\max}|)$.
  - **Rejection Conditions:**
    1. If $\lambda_{\min} < -\tau_{\text{null}}$: raises `NumericalBackendError("Matrix A is indefinite...")`.
    2. If $|\lambda_{\min}| \le \tau_{\text{null}}$: raises `NumericalBackendError("Matrix A appears singular or positive-semidefinite (rigid body modes detected)...")`.
- **When `caller_certified_spd=True`:**
  - Caller explicitly asserts physical positive-definiteness (e.g., from Dirichlet boundary constraints eliminating rigid body modes).
  - Skips spectral eigensolve while **unconditionally enforcing all structural checks** (finiteness, symmetry, positive diagonal, dimension match).

---

## 3. Preconditioner Handling on CPU and CUDA

- **CPUBackend:** Validates that if preconditioner $M$ declares `is_spd`, it must be `True`. Rejects non-SPD preconditioners (e.g., ILU) with `NumericalBackendError`.
- **CUDABackend:** 
  - Strictly rejects arbitrary CPU `LinearOperator` instances with `UnsupportedCapabilityError`.
  - Supports GPU-resident Jacobi preconditioning: passing `M="jacobi"` or a valid Jacobi preconditioner constructs a GPU-resident `cupyx.scipy.sparse.linalg.LinearOperator` with $M^{-1} v = v / \text{diag}(A)$ executing on device.
  - Never silently ignores $M$.

---

## 4. CUDA Diagnostics & Residual Calculation

- **GPU Residual Evaluation:** Evaluates $r = b - A x$ directly in GPU VRAM and computes $\|r\|_2$ using `cp.linalg.norm(r)` on device. Eliminates unnecessary PCIe host transfers of matrix $A$.
- **Telemetry Integrity:** CuPy 14 CG does not expose iteration telemetry. `CUDABackend` reports `iterations: None` and records breakdown reasons without inventing fabricated `max_iter` counts.
