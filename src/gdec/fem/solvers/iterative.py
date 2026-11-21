"""
Iterative Solvers and Preconditioners for GDEC FEM systems.

Provides:
- ConjugateGradientSolver: Standard preconditioned Conjugate Gradient for SPD systems.
- IdentityPreconditioner: Unpreconditioned baseline (M = I).
- JacobiPreconditioner: Diagonal preconditioning (M = diag(A)).
- IncompleteCholeskyPreconditioner: Genuine IC(0) sparse factorization for SPD systems.
- AMGPreconditioner: Algebraic Multigrid via PyAMG (optional dependency).
- ILUPreconditioner: Incomplete LU via scipy.sparse.linalg.spilu (experimental, non-SPD).
"""

from __future__ import annotations
import abc
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from gdec.fem.matrix_diagnostics import compute_symmetry_defect


try:
    import pyamg  # type: ignore
    _PYAMG_AVAILABLE = True
except ImportError:
    _PYAMG_AVAILABLE = False


@dataclass
class CGSolverResult:
    """Detailed convergence result and telemetry for a Conjugate Gradient solve."""
    x: np.ndarray
    converged: bool
    iterations: int
    residual_norm: float
    initial_residual_norm: float
    relative_residual: float
    residual_history: List[float]
    time_sec: float
    preconditioner_name: str
    breakdown_reason: Optional[str] = None

    def summary(self) -> str:
        status = "CONVERGED" if self.converged else "FAILED/UNCONVERGED"
        if self.breakdown_reason:
            status += f" (Breakdown: {self.breakdown_reason})"
        return (
            f"CG Result: {status} in {self.iterations} iterations "
            f"({self.time_sec*1000.0:.2f} ms) [{self.preconditioner_name}]\n"
            f"  ||r_0||: {self.initial_residual_norm:.2e}, "
            f"  ||r_final||: {self.residual_norm:.2e}, "
            f"  rel_res: {self.relative_residual:.2e}"
        )


class Preconditioner(abc.ABC):
    """Abstract base class for linear system preconditioners M^{-1}."""

    @abc.abstractmethod
    def apply(self, r: np.ndarray) -> np.ndarray:
        """Apply preconditioning operation z = M^{-1} r."""
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable identifier of the preconditioner."""
        pass

    @property
    def is_spd(self) -> bool:
        """Whether the preconditioner is mathematically guaranteed to be SPD."""
        return True


class IdentityPreconditioner(Preconditioner):
    """Identity preconditioner M = I (Unpreconditioned CG)."""

    def apply(self, r: np.ndarray) -> np.ndarray:
        return r.copy()

    @property
    def name(self) -> str:
        return "Identity (None)"


class JacobiPreconditioner(Preconditioner):
    r"""
    Jacobi (diagonal) preconditioner:
      M = \operatorname{diag}(A)
      M^{-1} r = r / \operatorname{diag}(A)
    """

    def __init__(self, A: sp.spmatrix | np.ndarray):
        if sp.issparse(A):
            diag = A.diagonal().astype(float)
        else:
            diag = np.diag(np.asarray(A)).astype(float)

        if np.any(np.isnan(diag)) or np.any(np.isinf(diag)):
            raise ValueError("Jacobi preconditioner failed: matrix diagonal contains NaN or Inf.")

        min_val = float(np.min(diag)) if len(diag) > 0 else 0.0
        if min_val <= 0.0:
            n_neg = int(np.sum(diag <= 0.0))
            raise ValueError(
                f"Jacobi preconditioner failed: encountered {n_neg} non-positive diagonal entries "
                f"(min value = {min_val:.2e}). Matrix is not strictly SPD."
            )

        self.inv_diag = 1.0 / diag
        self._n = len(diag)

    def apply(self, r: np.ndarray) -> np.ndarray:
        if len(r) != self._n:
            raise ValueError(f"RHS dimension mismatch: expected {self._n}, got {len(r)}.")
        return self.inv_diag * r

    @property
    def name(self) -> str:
        return "Jacobi (Diagonal)"


class IncompleteCholeskyPreconditioner(Preconditioner):
    r"""
    Genuine Incomplete Cholesky factorization IC(0) preserving the exact
    lower-triangular sparsity pattern of A:
      A \approx L L^T
      M^{-1} r = L^{-T} L^{-1} r
    Solved via forward/backward sparse triangular substitutions.
    """

    def __init__(self, A: sp.spmatrix):
        if not sp.issparse(A):
            A = sp.csr_matrix(A)
        A_csr = A.tocsr()
        n = A_csr.shape[0]

        # Extract lower-triangular part with initial values
        L = sp.tril(A_csr, format="lil").astype(float)

        # Standard IC(0) factorization algorithm
        for i in range(n):
            row_cols = L.rows[i]
            for j in row_cols:
                # Common column indices k < j where both L[i,k] and L[j,k] exist
                common_k = set(L.rows[i]).intersection(L.rows[j])
                common_k = [k for k in common_k if k < j]
                s = A_csr[i, j]
                for k in common_k:
                    s -= L[i, k] * L[j, k]

                if i == j:
                    if s <= 0.0:
                        raise ValueError(
                            f"Incomplete Cholesky IC(0) breakdown: zero or negative pivot "
                            f"at row {i} (pivot = {s:.2e}). Matrix is not an H-matrix or SPD."
                        )
                    L[i, j] = np.sqrt(s)
                else:
                    L[i, j] = s / L[j, j]

        self.L_csr = L.tocsr()
        self.LT_csr = self.L_csr.T.tocsr()
        self._n = n

    def apply(self, r: np.ndarray) -> np.ndarray:
        # Solve L y = r
        y = spla.spsolve_triangular(self.L_csr, r, lower=True)
        # Solve L^T z = y
        z = spla.spsolve_triangular(self.LT_csr, y, lower=False)
        return z

    @property
    def name(self) -> str:
        return "Incomplete Cholesky IC(0)"


class AMGPreconditioner(Preconditioner):
    """
    Algebraic Multigrid (AMG) preconditioner using PyAMG smoothed aggregation.
    """

    def __init__(self, A: sp.spmatrix, **pyamg_kwargs):
        if not _PYAMG_AVAILABLE:
            raise ImportError(
                "PyAMG is not installed in the current environment. "
                "To enable AMG preconditioning, install pyamg (`pip install pyamg`)."
            )
        if not sp.issparse(A):
            A = sp.csr_matrix(A)
        self.ml = pyamg.smoothed_aggregation_solver(A.tocsr(), **pyamg_kwargs)
        self.M = self.ml.aspreconditioner(cycle="V")

    @classmethod
    def is_available(cls) -> bool:
        """Check if PyAMG is installed and available."""
        return _PYAMG_AVAILABLE

    def apply(self, r: np.ndarray) -> np.ndarray:
        return self.M.matvec(r)

    @property
    def name(self) -> str:
        return "Algebraic Multigrid (PyAMG Smoothed Aggregation)"


class ILUPreconditioner(Preconditioner):
    r"""
    Incomplete LU factorization via scipy.sparse.linalg.spilu.
    Note: ILU produces M = L U where U != L^T. It is generally NOT symmetric positive-definite.
    Using ILU inside ordinary symmetric CG is mathematically uncertified and can cause
    loss of conjugacy or breakdown. It is included for comparative evaluation only.
    """

    def __init__(self, A: sp.spmatrix, drop_tol: float = 1e-4, fill_factor: float = 10.0):
        if not sp.issparse(A):
            A = sp.csc_matrix(A)
        else:
            A = A.tocsc()
        self.ilu = spla.spilu(A, drop_tol=drop_tol, fill_factor=fill_factor)
        self._n = A.shape[0]

    def apply(self, r: np.ndarray) -> np.ndarray:
        return self.ilu.solve(r)

    @property
    def name(self) -> str:
        return "Incomplete LU (ILU - Warning: Non-SPD)"

    @property
    def is_spd(self) -> bool:
        return False


class ConjugateGradientSolver:
    """
    Standard Preconditioned Conjugate Gradient (PCG) solver for symmetric
    positive-definite linear systems K x = b.
    """

    def __init__(
        self,
        default_rtol: float = 1e-8,
        default_atol: float = 1e-12,
        default_max_iter: Optional[int] = None,
        sym_tol: float = 1e-8,
    ):
        self.default_rtol = default_rtol
        self.default_atol = default_atol
        self.default_max_iter = default_max_iter
        self.sym_tol = sym_tol

    def solve(
        self,
        K: sp.spmatrix | np.ndarray,
        b: np.ndarray,
        x0: Optional[np.ndarray] = None,
        preconditioner: Optional[Preconditioner] = None,
        rtol: Optional[float] = None,
        atol: Optional[float] = None,
        max_iter: Optional[int] = None,
        check_eligibility: bool = True,
    ) -> CGSolverResult:
        r"""
        Solve K x = b using preconditioned conjugate gradient.

        Parameters
        ----------
        K : spmatrix or ndarray
            Symmetric positive-definite system matrix (n, n).
        b : ndarray
            Right-hand side vector (n,).
        x0 : ndarray, optional
            Initial displacement guess (n,). Defaults to zeros.
        preconditioner : Preconditioner, optional
            Preconditioner M^{-1}. Defaults to IdentityPreconditioner.
        rtol : float, optional
            Relative residual tolerance.
        atol : float, optional
            Absolute residual tolerance.
        max_iter : int, optional
            Maximum allowed iterations. Defaults to min(10000, 10 * n).
        check_eligibility : bool
            Whether to enforce symmetry and diagonal positivity checks.

        Returns
        -------
        CGSolverResult
        """
        t_start = time.perf_counter()

        if sp.issparse(K):
            K_mat = K.tocsr()
        else:
            K_mat = sp.csr_matrix(K)

        n_rows, n_cols = K_mat.shape
        if n_rows != n_cols:
            raise ValueError(f"CG solver requires a square matrix, got {n_rows} x {n_cols}.")
        if len(b) != n_rows:
            raise ValueError(f"RHS dimension mismatch: matrix has {n_rows} rows, b has {len(b)} elements.")

        # Check eligibility
        if check_eligibility:
            delta_sym = compute_symmetry_defect(K_mat)
            if delta_sym > self.sym_tol:
                raise ValueError(
                    f"Matrix is not symmetric (delta_sym = {delta_sym:.2e} > tol {self.sym_tol:.2e}). "
                    "Conjugate Gradient requires a symmetric matrix."
                )
            diag = K_mat.diagonal()
            if np.any(diag <= 0.0):
                min_d = float(np.min(diag))
                raise ValueError(
                    f"Matrix diagonal contains non-positive entries (min: {min_d:.2e}). "
                    "Conjugate Gradient requires a positive-definite matrix."
                )

        M = preconditioner if preconditioner is not None else IdentityPreconditioner()

        _rtol = rtol if rtol is not None else self.default_rtol
        _atol = atol if atol is not None else self.default_atol
        _max_iter = max_iter if max_iter is not None else (
            self.default_max_iter if self.default_max_iter is not None else max(100, min(10000, 10 * n_rows))
        )

        b_norm = float(np.linalg.norm(b))
        stopping_threshold = max(_atol, _rtol * b_norm)

        # Initial state
        if x0 is not None:
            if len(x0) != n_rows:
                raise ValueError(f"Initial guess x0 shape mismatch: expected {n_rows}, got {len(x0)}.")
            x = np.asarray(x0, dtype=float).copy()
            r = b - K_mat.dot(x)
        else:
            x = np.zeros(n_rows, dtype=float)
            r = b.copy().astype(float)

        r_norm = float(np.linalg.norm(r))
        initial_r_norm = r_norm
        history = [r_norm]

        # Early exit if initial residual already satisfies tolerance
        if r_norm <= stopping_threshold:
            t_elapsed = time.perf_counter() - t_start
            return CGSolverResult(
                x=x,
                converged=True,
                iterations=0,
                residual_norm=r_norm,
                initial_residual_norm=initial_r_norm,
                relative_residual=r_norm / max(b_norm, 1e-15),
                residual_history=history,
                time_sec=t_elapsed,
                preconditioner_name=M.name,
                breakdown_reason=None,
            )

        z = M.apply(r)
        p = z.copy()
        rho = float(np.dot(r, z))

        converged = False
        breakdown_reason: Optional[str] = None
        iters = 0

        for k in range(_max_iter):
            iters += 1
            w = K_mat.dot(p)
            kappa = float(np.dot(p, w))

            # Breakdown detection: non-positive curvature
            if kappa <= 0.0 or np.isnan(kappa) or np.isinf(kappa):
                breakdown_reason = (
                    f"Non-positive curvature or invalid value at iteration {k}: "
                    f"p^T K p = {kappa:.2e} <= 0."
                )
                break

            alpha = rho / kappa
            x += alpha * p
            r -= alpha * w
            r_norm = float(np.linalg.norm(r))
            history.append(r_norm)

            if r_norm <= stopping_threshold:
                converged = True
                break

            z = M.apply(r)
            rho_next = float(np.dot(r, z))

            # Underflow / breakdown in inner product
            if abs(rho) < 1e-35:
                breakdown_reason = f"Inner product underflow at iteration {k}: |r^T z| = {abs(rho):.2e}."
                break

            beta = rho_next / rho
            p = z + beta * p
            rho = rho_next

        t_elapsed = time.perf_counter() - t_start

        return CGSolverResult(
            x=x,
            converged=converged,
            iterations=iters,
            residual_norm=r_norm,
            initial_residual_norm=initial_r_norm,
            relative_residual=r_norm / max(b_norm, 1e-15),
            residual_history=history,
            time_sec=t_elapsed,
            preconditioner_name=M.name,
            breakdown_reason=breakdown_reason,
        )
