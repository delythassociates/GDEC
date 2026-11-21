"""
CPU execution backend implementation for GDEC using NumPy and SciPy.
Preserves production SuperLU direct solver defaults and strict SPD safety contracts.
"""

from __future__ import annotations
import platform
import psutil
import numpy as np
import scipy
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from typing import Dict, Any, Tuple, Optional

from gdec.core.backend.capabilities import BackendCapabilities, CapabilityStatus
from gdec.core.backend.spd_check import verify_cg_eligibility
from gdec.core.backend.exceptions import (
    InputValidationError,
    NumericalBackendError,
    UnsupportedCapabilityError,
)


class CPUBackend:
    """
    Standard CPU computational backend for GDEC.
    Executes sparse linear algebra via SciPy / SuperLU and vectorized NumPy routines.
    """

    def __init__(self) -> None:
        self._name = "cpu"
        self._capabilities = BackendCapabilities(
            sparse_matvec=True,
            sparse_direct_solve=True,
            sparse_cg_solve=True,
            multiple_rhs=True,
            factorization_reuse=True,
            device_resident_memory=False,
            device_synchronization=True,
            asynchronous_streams=False,
            batched_analytical_scaling=True,
            fem_assembly=False,
            mesh_refinement=False,
            dwr_evaluation=False,
            capability_status={
                "sparse_matvec": CapabilityStatus.SUPPORTED,
                "sparse_direct_solve": CapabilityStatus.SUPPORTED,
                "sparse_cg_solve": CapabilityStatus.SUPPORTED,
                "multiple_rhs": CapabilityStatus.SUPPORTED,
                "factorization_reuse": CapabilityStatus.SUPPORTED,
                "batched_analytical_scaling": CapabilityStatus.SUPPORTED,
                "fem_assembly": CapabilityStatus.UNSUPPORTED,
            },
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return True

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def get_device_info(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        return {
            "backend": "cpu",
            "processor": platform.processor() or platform.machine(),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "total_ram_gb": round(mem.total / (1024**3), 2),
            "available_ram_gb": round(mem.available / (1024**3), 2),
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "libraries": {
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
        }

    def spmv(self, A: Any, x: Any) -> np.ndarray:
        """
        Sparse matrix-vector multiplication y = A @ x.
        """
        if not sp.issparse(A):
            raise InputValidationError("Matrix A must be a scipy.sparse matrix.")
        x_arr = np.asarray(x)
        if x_arr.ndim != 1:
            raise InputValidationError(f"Expected 1D vector x, got ndim={x_arr.ndim}")
        if A.shape[1] != x_arr.shape[0]:
            raise InputValidationError(
                f"Dimension mismatch: A is {A.shape}, but x has length {x_arr.shape[0]}"
            )
        if not np.all(np.isfinite(x_arr)):
            raise NumericalBackendError("Vector x contains non-finite values (NaN or Inf).")

        return A @ x_arr

    def solve_direct(self, A: Any, b: Any) -> np.ndarray:
        """
        Solve linear system A x = b using sparse direct SuperLU.
        """
        if not sp.issparse(A):
            raise InputValidationError("Matrix A must be a scipy.sparse matrix.")
        b_arr = np.asarray(b)
        if A.shape[0] != A.shape[1]:
            raise InputValidationError(f"Matrix A must be square, got {A.shape}")
        if A.shape[0] != b_arr.shape[0]:
            raise InputValidationError(
                f"Dimension mismatch: A is {A.shape}, but b has length {b_arr.shape[0]}"
            )
        if not np.all(np.isfinite(b_arr)):
            raise NumericalBackendError("Right-hand side vector contains NaN or Inf.")

        try:
            x = spla.spsolve(A.tocsc(), b_arr)
        except Exception as e:
            raise NumericalBackendError(f"Sparse direct solve failed: {str(e)}") from e

        if not np.all(np.isfinite(x)):
            raise NumericalBackendError("Sparse direct solve produced non-finite solution values.")
        return x

    def solve_multiple_rhs(self, A: Any, B: Any) -> np.ndarray:
        """
        Solve linear system A X = B for multiple right-hand sides using single LU factorization.
        """
        if not sp.issparse(A):
            raise InputValidationError("Matrix A must be a scipy.sparse matrix.")
        B_arr = np.asarray(B)
        if B_arr.ndim != 2:
            raise InputValidationError(f"Expected 2D matrix B for multiple RHS, got ndim={B_arr.ndim}")
        if A.shape[0] != A.shape[1]:
            raise InputValidationError(f"Matrix A must be square, got {A.shape}")
        if A.shape[0] != B_arr.shape[0]:
            raise InputValidationError(
                f"Dimension mismatch: A is {A.shape}, but B has {B_arr.shape[0]} rows"
            )
        if not np.all(np.isfinite(B_arr)):
            raise NumericalBackendError("RHS matrix B contains non-finite values (NaN or Inf).")

        try:
            # Factorize once using SuperLU
            lu = spla.splu(A.tocsc())
            X = lu.solve(B_arr)
        except Exception as e:
            raise NumericalBackendError(f"Multiple RHS solve failed: {str(e)}") from e

        if not np.all(np.isfinite(X)):
            raise NumericalBackendError("Multiple RHS solve produced non-finite solution values.")
        return X

    def solve_cg(
        self,
        A: Any,
        b: Any,
        rtol: float = 1e-8,
        atol: float = 1e-12,
        max_iter: Optional[int] = None,
        M: Optional[Any] = None,
        caller_certified_spd: bool = False,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Solve linear system A x = b using Conjugate Gradient with strict SPD validation.
        """
        if not sp.issparse(A):
            raise InputValidationError("Matrix A must be a scipy.sparse matrix.")
        b_arr = np.asarray(b)

        # Enforce unified structural and SPD eligibility checks
        n, _, _ = verify_cg_eligibility(
            A=A,
            b=b_arr,
            rtol=rtol,
            atol=atol,
            max_iter=max_iter,
            caller_certified_spd=caller_certified_spd,
        )

        # Preconditioner SPD check
        if M is not None:
            if not getattr(M, "is_spd", False):
                p_name = getattr(M, "name", type(M).__name__)
                raise NumericalBackendError(
                    f"Preconditioner '{p_name}' does not declare is_spd=True. "
                    "Conjugate Gradient strictly requires an SPD preconditioner."
                )

        if max_iter is None:
            max_iter = n * 2

        it_count = 0
        def callback(xk: np.ndarray) -> None:
            nonlocal it_count
            it_count += 1

        A_csr = A.tocsr()
        x, info = spla.cg(A_csr, b_arr, rtol=rtol, atol=atol, maxiter=max_iter, M=M, callback=callback)
        res_norm = float(np.linalg.norm(b_arr - A_csr @ x))
        converged = (info == 0)

        if not converged and not np.all(np.isfinite(x)):
            raise NumericalBackendError("CG solver diverged or encountered non-finite values.")

        return x, {
            "converged": converged,
            "iterations": it_count,
            "residual_norm": res_norm,
            "exit_code": info,
            "breakdown_reason": None if converged else f"SciPy CG exit code {info}",
        }

    def synchronize(self) -> None:
        """No-op on CPU."""
        pass

    def evaluate_parameter_scaling_batch(
        self,
        E_vals: Any,
        P_vals: Any,
        J_0: float,
        E_0: float,
        P_0: float,
    ) -> np.ndarray:
        """
        Vectorized analytical scaling: J(E, P) = (P / P_0) * (E_0 / E) * J_0.
        """
        E_arr = np.asarray(E_vals, dtype=np.float64)
        P_arr = np.asarray(P_vals, dtype=np.float64)

        if E_arr.shape != P_arr.shape:
            raise InputValidationError(
                f"Shape mismatch: E_vals {E_arr.shape} != P_vals {P_arr.shape}"
            )
        if E_0 <= 0.0:
            raise InputValidationError(f"Reference Young's modulus E_0 must be strictly positive, got {E_0}")
        if P_0 == 0.0:
            raise InputValidationError("Reference load factor P_0 cannot be zero.")
        if np.any(E_arr <= 0.0):
            raise NumericalBackendError("Sampled Young's modulus E must be strictly positive.")

        return (P_arr / P_0) * (E_0 / E_arr) * J_0
