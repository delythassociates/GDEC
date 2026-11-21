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
import scipy.linalg as la

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
        """
        Whether the preconditioner is mathematically guaranteed to be SPD.
        Base implementation fails closed (returns False) so custom subclasses
        must explicitly verify and declare SPD compatibility.
        """
        return False


class IdentityPreconditioner(Preconditioner):
    """Identity preconditioner M = I (Unpreconditioned CG)."""

    def apply(self, r: np.ndarray) -> np.ndarray:
        return r.copy()

    @property
    def name(self) -> str:
        return "Identity (None)"

    @property
    def is_spd(self) -> bool:
        return True


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

    @property
    def is_spd(self) -> bool:
        return True


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

    @property
    def is_spd(self) -> bool:
        return True


class AMGPreconditioner(Preconditioner):
    """
    Algebraic Multigrid (AMG) preconditioner using PyAMG smoothed aggregation.

    Mathematical Verification Contract:
    To be mathematically guaranteed symmetric positive-definite (SPD) for ordinary CG,
    an Algebraic Multigrid preconditioner must satisfy four strict requirements:
    1. Symmetric Galerkin hierarchy: Coarse grids formed via A_c = R A P with R = P^T.
    2. Symmetric cycling: Symmetric V-cycle or W-cycle traversal.
    3. Symmetric relaxation: The post-smoothing operation must be the exact adjoint of the
       pre-smoothing operation. When Gauss-Seidel is used, an adjoint sweep pair
       (forward pre-smoother, backward post-smoother) or symmetric Gauss-Seidel is required.
    4. Symmetric coarse solver: The coarse grid solver must produce an SPD action (e.g. direct
       sparse/dense factorizations; arbitrary callables or unsymmetric solvers are rejected).

    Any configuration not meeting these explicit verified constraints evaluates is_spd = False,
    causing ordinary Conjugate Gradient to fail-closed and reject the preconditioner.
    """

    VERIFIED_CYCLES = ("V", "W")
    VERIFIED_COARSE_SOLVERS = ("splu", "pinv", "pinv2", "default", None)
    VERIFIED_SMOOTHERS = ("gauss_seidel", "symmetric_gauss_seidel", "jacobi", None)

    def __init__(
        self,
        A: sp.spmatrix,
        cycle: str = "V",
        symmetric: bool = True,
        smoother: Optional[str] = None,
        coarse_solver: Optional[str] = None,
        **pyamg_kwargs,
    ):
        if not _PYAMG_AVAILABLE:
            raise ImportError(
                "PyAMG is not installed in the current environment. "
                "To enable AMG preconditioning, install pyamg (`pip install pyamg`)."
            )
        if not sp.issparse(A):
            A = sp.csr_matrix(A)
        self.symmetric = symmetric
        self.cycle = cycle.upper() if isinstance(cycle, str) else str(cycle)
        self.smoother = smoother
        self.coarse_solver = coarse_solver
        self.pyamg_kwargs = pyamg_kwargs

        # Verify whether the configuration satisfies SPD requirements
        self._is_verified_spd = self._verify_spd_configuration()

        # Build solver kwargs with explicit symmetric smoothing
        solver_kwargs = pyamg_kwargs.copy()
        if symmetric:
            solver_kwargs["symmetry"] = "symmetric"
        if coarse_solver is not None:
            solver_kwargs["coarse_solver"] = coarse_solver

        if smoother == "gauss_seidel":
            # Explicit adjoint sweep pair: forward pre-smoothing, backward post-smoothing
            solver_kwargs["presmoother"] = ("gauss_seidel", {"sweep": "forward"})
            solver_kwargs["postsmoother"] = ("gauss_seidel", {"sweep": "backward"})
        elif smoother == "symmetric_gauss_seidel":
            solver_kwargs["presmoother"] = ("symmetric_gauss_seidel", {})
            solver_kwargs["postsmoother"] = ("symmetric_gauss_seidel", {})
        elif smoother == "jacobi":
            solver_kwargs["presmoother"] = ("jacobi", {})
            solver_kwargs["postsmoother"] = ("jacobi", {})

        self.ml = pyamg.smoothed_aggregation_solver(A.tocsr(), **solver_kwargs)
        self.M = self.ml.aspreconditioner(cycle=self.cycle)

    def _verify_spd_configuration(self) -> bool:
        """Verify whether the requested AMG configuration satisfies strict SPD requirements."""
        if not self.symmetric:
            return False
        if self.cycle not in self.VERIFIED_CYCLES:
            return False
        if self.smoother not in self.VERIFIED_SMOOTHERS:
            return False
        if self.coarse_solver not in self.VERIFIED_COARSE_SOLVERS:
            return False
        if callable(self.coarse_solver):
            return False
        # Reject unverified arbitrary kwargs that could introduce unsymmetric operators
        unverified_keys = set(self.pyamg_kwargs.keys()) - {"max_levels", "max_coarse"}
        if unverified_keys:
            return False
        return True

    @classmethod
    def is_available(cls) -> bool:
        """Check if PyAMG is installed and available."""
        return _PYAMG_AVAILABLE

    def apply(self, r: np.ndarray) -> np.ndarray:
        return self.M.matvec(r)

    @property
    def name(self) -> str:
        return "Algebraic Multigrid (PyAMG Smoothed Aggregation)"

    @property
    def is_spd(self) -> bool:
        """
        Whether this AMG configuration is verified to be SPD.
        Returns True ONLY for supported symmetric cycle, smoother, and coarse solver configurations.
        """
        return self._is_verified_spd


class ILUPreconditioner(Preconditioner):
    r"""
    Incomplete LU factorization via scipy.sparse.linalg.spilu.
    Note: ILU produces M = L U where U != L^T. It is NOT symmetric positive-definite.
    Using ILU inside ordinary symmetric CG is mathematically invalid and rejected by
    the CG eligibility compatibility gate.
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
        return "Incomplete LU (ILU - Non-SPD)"

    @property
    def is_spd(self) -> bool:
        return False


class ConjugateGradientSolver:
    """
    Standard Preconditioned Conjugate Gradient (PCG) solver for symmetric
    positive-definite linear systems K x = b.

    Eligibility contract:
    - Verifies matrix dimensions, finiteness, symmetry (delta_sym <= sym_tol),
      and positive diagonal entries upfront.
    - Rejects non-SPD preconditioners (such as ILU) via preconditioner.is_spd.
    - If caller_certified_spd is False, performs algebraic eigenvalue checks to
      verify positive definiteness before iterating.
    - Detects non-positive curvature (p^T K p <= 0) during iterations.
    """

    def __init__(
        self,
        default_rtol: float = 1e-8,
        default_atol: float = 1e-12,
        default_max_iter: Optional[int] = None,
        sym_tol: float = 1e-8,
        null_tol: float = 1e-10,
    ):
        self.default_rtol = default_rtol
        self.default_atol = default_atol
        self.default_max_iter = default_max_iter
        self.sym_tol = sym_tol
        self.null_tol = null_tol

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
        caller_certified_spd: bool = False,
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
            Must have preconditioner.is_spd == True.
        rtol : float, optional
            Relative residual tolerance. Must be > 0 and finite.
        atol : float, optional
            Absolute residual tolerance. Must be >= 0 and finite.
        max_iter : int, optional
            Maximum allowed iterations. Must be > 0.
        check_eligibility : bool
            Whether to enforce symmetry, diagonal positivity, and definiteness checks.
        caller_certified_spd : bool
            If True, caller certifies that K is SPD by structural/domain physics
            (e.g., condensed FEM matrix with fixed Dirichlet boundaries), skipping
            upfront eigenvalue solve while still performing necessary diagonal, symmetry,
            and runtime curvature checks.

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

        # Check finiteness of matrix entries
        if np.any(np.isnan(K_mat.data)) or np.any(np.isinf(K_mat.data)):
            raise ValueError("Matrix K contains non-finite (NaN or Inf) values.")
        if np.any(np.isnan(b)) or np.any(np.isinf(b)):
            raise ValueError("Right-hand side b contains non-finite (NaN or Inf) values.")
        if x0 is not None:
            if len(x0) != n_rows:
                raise ValueError(f"Initial guess x0 shape mismatch: expected {n_rows}, got {len(x0)}.")
            if np.any(np.isnan(x0)) or np.any(np.isinf(x0)):
                raise ValueError("Initial guess x0 contains non-finite (NaN or Inf) values.")

        _rtol = rtol if rtol is not None else self.default_rtol
        _atol = atol if atol is not None else self.default_atol
        _max_iter = max_iter if max_iter is not None else (
            self.default_max_iter if self.default_max_iter is not None else max(100, min(10000, 10 * n_rows))
        )

        if _rtol <= 0 or not np.isfinite(_rtol):
            raise ValueError(f"Relative tolerance rtol must be positive and finite, got {_rtol}.")
        if _atol < 0 or not np.isfinite(_atol):
            raise ValueError(f"Absolute tolerance atol must be non-negative and finite, got {_atol}.")
        if _max_iter <= 0:
            raise ValueError(f"Maximum iterations max_iter must be positive, got {_max_iter}.")

        # Check preconditioner SPD compatibility gate
        M = preconditioner if preconditioner is not None else IdentityPreconditioner()
        if not M.is_spd:
            raise ValueError(
                f"Preconditioner '{M.name}' is not symmetric positive-definite (is_spd=False). "
                "Ordinary Conjugate Gradient strictly requires an SPD preconditioner to guarantee "
                "energy-norm self-adjointness and prevent breakdown or divergence."
            )

        # Mandatory Safety Gate: Eligibility checks may only be skipped when caller_certified_spd=True
        # is explicitly provided. The combination check_eligibility=False and caller_certified_spd=False
        # is strictly forbidden.
        if not check_eligibility and not caller_certified_spd:
            raise ValueError(
                "Cannot bypass matrix eligibility checks (check_eligibility=False) without explicit caller "
                "certification (caller_certified_spd=True). Ordinary Conjugate Gradient strictly requires verified "
                "symmetric positive-definite operators. To bypass upfront spectral eigensolve verification based on "
                "domain physics or boundary conditions, explicitly pass caller_certified_spd=True."
            )

        # Structural necessary checks: always enforced
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
                "Necessary condition for positive definiteness failed."
            )

        # Scale-aware SPD verification if not caller-certified
        if not caller_certified_spd:
            if n_rows <= 300:
                eigvals = la.eigvalsh(K_mat.toarray())
                lambda_min = float(eigvals[0])
                lambda_max = float(eigvals[-1])
            else:
                try:
                    ncv_val = min(n_rows - 1, 25)
                    lambda_max = float(spla.eigsh(K_mat, k=1, which="LA", return_eigenvectors=False, ncv=ncv_val)[0])
                    lambda_min = float(spla.eigsh(K_mat, k=1, which="SA", return_eigenvectors=False, ncv=ncv_val)[0])
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise
                    raise ValueError(
                        f"Positive-definiteness could not be established by eigensolve: {e}. "
                        "If this matrix is physically guaranteed to be SPD, pass caller_certified_spd=True."
                    )

            scale = max(abs(lambda_min), abs(lambda_max), np.finfo(float).tiny)
            null_threshold = self.null_tol * scale

            # 1. Indefinite: smallest algebraic eigenvalue is negative
            if lambda_min < -null_threshold:
                raise ValueError(
                    f"Matrix is not positive-definite: matrix is indefinite "
                    f"(lambda_min = {lambda_min:.2e}, lambda_scale = {scale:.2e}, "
                    f"ratio = {lambda_min / scale:.2e} < -{self.null_tol:.2e}). "
                    "Conjugate Gradient strictly requires a symmetric positive-definite matrix."
                )
            # 2. Non-positive: largest algebraic eigenvalue is non-positive
            if lambda_max <= null_threshold:
                raise ValueError(
                    f"Matrix is not positive-definite: largest algebraic eigenvalue is non-positive "
                    f"(lambda_max = {lambda_max:.2e}, lambda_scale = {scale:.2e}). "
                    "Conjugate Gradient strictly requires a positive-definite matrix."
                )
            # 3. Numerically near-singular / null modes: |lambda_min| <= null_threshold
            if abs(lambda_min) <= null_threshold:
                raise ValueError(
                    f"Matrix is not positive-definite: matrix is numerically near-singular or possesses "
                    f"unconstrained null modes (lambda_min = {lambda_min:.2e}, lambda_scale = {scale:.2e}, "
                    f"ratio = {lambda_min / scale:.2e} <= null_tol {self.null_tol:.2e}). "
                    "Conjugate Gradient strictly requires a positive-definite matrix."
                )

        b_norm = float(np.linalg.norm(b))
        stopping_threshold = max(_atol, _rtol * b_norm)

        # Initial state
        if x0 is not None:
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
