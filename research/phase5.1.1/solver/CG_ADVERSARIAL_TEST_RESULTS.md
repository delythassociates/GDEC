# GDEC Phase 5.1.1 CG Adversarial Test Results

**Document ID:** `GDEC-SOLV-ADV-001`  
**Date:** 2026-11-22  
**Author:** Lead Engineering Research Orchestrator  
**Status:** Tested & Passed  

---

## 1. Adversarial Test Matrix

All 15 required failure and edge-case classes were executed against both `CPUBackend` and `CUDABackend`.

| Test ID | Adversarial Input Case | Expected Failure Mode | CPU Backend Result | CUDA Backend Result | Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **ADV-CG-01** | Symmetric positive-diagonal indefinite matrix $A = \begin{bmatrix} 1 & 2 \\ 2 & 1 \end{bmatrix}$ (`caller_certified_spd=False`) | `NumericalBackendError` (Indefinite: $\lambda_{\min} = -1.0$) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-02** | Symmetric positive-diagonal indefinite matrix (`caller_certified_spd=True`) | Solves under caller certification assertion | **CONVERGED** | **CONVERGED** | **PASS** |
| **ADV-CG-03** | Non-symmetric matrix $A = \begin{bmatrix} 4 & 2 \\ 1 & 3 \end{bmatrix}$ | `NumericalBackendError` (Symmetry defect $\delta_{\text{sym}} > 10^{-8}$) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-04** | Singular matrix with rigid body mode $\lambda_{\min} = 0.0$ | `NumericalBackendError` (Singular / semidefinite) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-05** | Matrix with negative diagonal entry $A_{11} = -2.0$ | `NumericalBackendError` (Non-positive diagonal) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-06** | Matrix containing non-finite entry ($A_{00} = \text{NaN}$) | `NumericalBackendError` (Non-finite entries) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-07** | Right-hand side containing $\infty$ ($b_0 = \infty$) | `NumericalBackendError` (Non-finite RHS) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-08** | Non-square matrix ($3 \times 2$) | `InputValidationError` (Non-square matrix) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-09** | Dimension mismatch between $A$ ($2 \times 2$) and $b$ ($3$) | `InputValidationError` (Dimension mismatch) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-10** | Negative relative tolerance ($\text{rtol} = -10^{-5}$) | `InputValidationError` (Tolerance must be positive) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-11** | Zero or negative iteration count ($\text{max\_iter} = 0$) | `InputValidationError` (Max iter must be positive) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-12** | Non-SPD preconditioner ($M$ with `is_spd=False`) | `NumericalBackendError` (Preconditioner not SPD) | **REJECTED** | **REJECTED** | **PASS** |
| **ADV-CG-13** | Unsupported CPU `LinearOperator` passed to CUDA | `UnsupportedCapabilityError` | N/A | **REJECTED** | **PASS** |
| **ADV-CG-14** | GPU Jacobi preconditioner ($M = \text{diag}(A)^{-1}$) on CUDA | Correct device-resident preconditioned solve | N/A | **CONVERGED** | **PASS** |
| **ADV-CG-15** | Strictly positive-definite Poisson-like tridiagonal system | Exact numerical convergence, $\|r\|_2 < 10^{-8}$ | **CONVERGED** | **CONVERGED** | **PASS** |

---

## 2. Conclusion

Neither backend accepts symmetric indefinite matrices with positive diagonals under default settings. Caller certification is strictly respected without weakening structural checks. Preconditioners are validated and GPU Jacobi preconditioning executes natively on device.
