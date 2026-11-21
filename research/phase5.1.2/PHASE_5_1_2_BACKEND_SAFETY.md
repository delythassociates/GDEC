# GDEC Phase 5.1.2 — Numerical Backend Safety Specification

**Author:** Sparse Linear Algebra Specialist & Scientific Software Architect  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.2-evidence-integrity-closure`  
**Standard:** Rigorous fail-closed matrix certification and device-resident execution

---

## 1. Motivation

The Conjugate Gradient (CG) algorithm is mathematically proven to converge if and only if the coefficient matrix $A$ and preconditioner $M$ are Symmetric Positive Definite (SPD). When applied to indefinite or asymmetric matrices, CG can exhibit silent stagnation, divide-by-zero breakdowns, or unbounded residual growth.

Phase 5.1.2 formalizes an explicit contract state machine, eliminates CPU-GPU data movement overheads during certification, and handles structural edge cases.

---

## 2. SPD Verification State Machine

In `src/gdec/core/backend/spd_check.py`, matrix eligibility is governed by:

```python
class SPDVerificationStatus(str, Enum):
    VERIFIED_SPD = "verified_spd"
    CALLER_ASSUMED_SPD = "caller_assumed_spd"
    DEMONSTRABLY_NON_SPD = "demonstrably_non_spd"
    INCONCLUSIVE = "inconclusive"
```

### Verification States and Transition Rules:
1. **Empty / Non-Square Matrix Rejection:**
   - If $A$ is not 2D, not square ($N \ne M$), or dimension $N \le 0$, immediately transition to `DEMONSTRABLY_NON_SPD` and raise `NumericalBackendError`.
2. **Caller Assumed SPD (`caller_certified_spd=True`):**
   - Structural screening ($O(N)$): diagonal elements must be finite and strictly positive ($\min A_{ii} > 0$).
   - Returns `SPDVerificationStatus.CALLER_ASSUMED_SPD`.
   - Caller assumes legal and scientific responsibility for spectral positivity.
3. **Automatic Verification (`caller_certified_spd=False`):**
   - **Step 1: Structural Screening:** Check symmetry defect $\|A - A^T\|_\infty \le 10^{-12}$. Check diagonal entries $\min A_{ii} > 0$. If violated $\implies \text{DEMONSTRABLY\_NON\_SPD}$.
   - **Step 2: Spectral Screening:**
     - For $N \le 2000$: Compute all eigenvalues via `scipy.linalg.eigvalsh`. If $\lambda_{\min} \le 0 \implies \text{DEMONSTRABLY\_NON\_SPD}$.
     - For $N > 2000$: Compute smallest algebraic eigenvalue via ARPACK `spla.eigsh(A, k=1, which="SA")`. If $\lambda_{\min} \le 0 \implies \text{DEMONSTRABLY\_NON\_SPD}$.
   - If $\lambda_{\min} > 0 \implies \text{VERIFIED\_SPD}$.
   - If eigensolver fails to converge $\implies \text{INCONCLUSIVE}$.

---

## 3. Preconditioner Safety & Compatibility Contracts

### 3.1 Shape Matching
Both CPU and GPU backends verify:
$$\text{tuple}(M.\text{shape}) == \text{tuple}(A.\text{shape})$$
Any mismatch raises `NumericalBackendError` before any solver setup occurs.

### 3.2 CPU Preconditioner Contract
In `CPUBackend`:
- Must implement matrix-vector multiplication (e.g. `scipy.sparse.linalg.LinearOperator`, `csr_matrix`, or `ndarray`).
- Custom operators must explicitly expose attribute `is_spd = True`.

### 3.3 GPU Preconditioner Contract
In `CUDABackend`:
- Passing host CPU `LinearOperator` instances is strictly forbidden: raises `UnsupportedCapabilityError`.
- GPU-resident preconditioners must declare `is_spd = True`. If omitted or `False`, raises `NumericalBackendError`.
- Built-in string `"jacobi"` constructs an inverse diagonal operator directly in device VRAM.

---

## 4. Device-Resident Matrix Validation in CuPy

In Phase 5.1.1, auditing a GPU-resident matrix transferred the sparse matrix back across the PCIe bus to host RAM, degrading throughput.

Phase 5.1.2 implements `_validate_device_resident_matrix` in `CUDABackend`:
- Operates entirely on `cp_sparse.spmatrix` or `cp.ndarray`.
- **Dimension Check:** Evaluates `A.shape[0] > 0` and `A.shape[0] == A.shape[1]` on device metadata.
- **Diagonal Positivity:** Extracts diagonal in VRAM via `A.diagonal()` and tests `cp.all(diag > 0)`.
- **Finite Data Check:** Evaluates `cp.all(cp.isfinite(A.data))` on device.
- **Zero Host Transfers:** Zero bytes of matrix entries are moved to host RAM. Telemetry confirms `host_matrix_transfers == 0`.

---

## 5. Structural Edge Cases

### Zero RHS Short-Circuit ($b = 0$)
When $\|b\|_2 = 0.0$:
- Iterative CG solvers can divide by zero during residual norm updates:
  $$\alpha_k = \frac{r_k^T r_k}{p_k^T A p_k}$$
- Both backends detect $\|b\|_2 == 0$ before solver initialization.
- Returns exact solution $x = \mathbf{0}$, $\text{iterations} = 0$, and $\text{residual} = 0.0$ immediately.
