"""
Shared SPD and Conjugate Gradient eligibility verification for GDEC backends.
Enforces identical mathematical safety standards across CPU and GPU backends.
"""

from __future__ import annotations
from typing import Tuple, Optional, Any
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import scipy.linalg as la

from gdec.core.backend.exceptions import (
    InputValidationError,
    NumericalBackendError,
)


def compute_symmetry_defect(A: sp.spmatrix | np.ndarray) -> float:
    r"""
    Compute relative Frobenius symmetry defect:
      \delta_{sym} = \frac{||A - A^T||_F}{||A||_F}
    Scale-invariant for non-zero matrices.
    """
    if sp.issparse(A):
        A_csr = A.tocsr()
        norm_A = float(spla.norm(A_csr, "fro"))
        if norm_A == 0.0:
            return 0.0
        diff = (A_csr - A_csr.T).tocsr()
        norm_diff = float(spla.norm(diff, "fro"))
    else:
        A_arr = np.asarray(A)
        norm_A = float(np.linalg.norm(A_arr, "fro"))
        if norm_A == 0.0:
            return 0.0
        diff = A_arr - A_arr.T
        norm_diff = float(np.linalg.norm(diff, "fro"))

    return float(norm_diff / norm_A)


def verify_cg_eligibility(
    A: sp.spmatrix | np.ndarray,
    b: np.ndarray,
    rtol: float,
    atol: float,
    max_iter: Optional[int],
    caller_certified_spd: bool = False,
    sym_tol: float = 1e-8,
    null_tol: float = 1e-10,
) -> Tuple[int, float, float]:
    r"""
    Enforce unified structural and positive-definiteness eligibility checks for Conjugate Gradient.

    A positive diagonal is a necessary but INSUFFICIENT condition for positive definiteness.
    For example:
        A = [[1, 2],
             [2, 1]]
    is symmetric and has positive diagonal [1, 1], but eigenvalues are -1 and 3 (indefinite).

    Parameters
    ----------
    A : sparse or dense matrix (n, n)
    b : right-hand side vector (n,)
    rtol : relative convergence tolerance (> 0)
    atol : absolute convergence tolerance (>= 0)
    max_iter : maximum iteration limit (> 0)
    caller_certified_spd : bool, default False
        If True, caller explicitly asserts that A is structurally guaranteed to be SPD
        (e.g., from kinematically constrained Dirichlet FEM boundary conditions),
        skipping upfront spectral eigensolve while retaining all structural, symmetry,
        finiteness, and positive-diagonal checks.
    sym_tol : float
        Symmetry defect threshold.
    null_tol : float
        Spectral zero-mode threshold.

    Returns
    -------
    (n, lambda_min, lambda_max)
    """
    # 1. Structural Checks: Matrix Shape and Format
    if sp.issparse(A):
        A_mat = A.tocsr()
        data_arr = A_mat.data
    else:
        A_mat = np.asarray(A)
        data_arr = A_mat

    n_rows, n_cols = A_mat.shape
    if n_rows != n_cols:
        raise InputValidationError(f"Conjugate Gradient requires a square matrix, got {n_rows} x {n_cols}.")

    b_arr = np.asarray(b)
    if b_arr.ndim != 1:
        raise InputValidationError(f"Expected 1D right-hand side vector b, got ndim={b_arr.ndim}.")
    if b_arr.shape[0] != n_rows:
        raise InputValidationError(f"Dimension mismatch: A is ({n_rows}, {n_cols}), but b has length {b_arr.shape[0]}.")

    # 2. Structural Checks: Finiteness
    if np.any(np.isnan(data_arr)) or np.any(np.isinf(data_arr)):
        raise NumericalBackendError("Matrix A contains non-finite values (NaN or Inf).")
    if np.any(np.isnan(b_arr)) or np.any(np.isinf(b_arr)):
        raise NumericalBackendError("Right-hand side b contains non-finite values (NaN or Inf).")

    # 3. Solver Parameter Validation
    if rtol <= 0.0 or not np.isfinite(rtol):
        raise InputValidationError(f"Relative tolerance rtol must be positive and finite, got {rtol}.")
    if atol < 0.0 or not np.isfinite(atol):
        raise InputValidationError(f"Absolute tolerance atol must be non-negative and finite, got {atol}.")
    if max_iter is not None and max_iter <= 0:
        raise InputValidationError(f"Maximum iterations max_iter must be a positive integer, got {max_iter}.")

    # 4. Symmetry Check
    delta_sym = compute_symmetry_defect(A_mat)
    if delta_sym > sym_tol:
        raise NumericalBackendError(
            f"Matrix A is not symmetric (symmetry defect delta_sym = {delta_sym:.2e} > tolerance {sym_tol:.2e}). "
            "Conjugate Gradient strictly requires a symmetric operator."
        )

    # 5. Positive Diagonal Check (Necessary condition for positive definiteness)
    diag = A_mat.diagonal()
    if np.any(diag <= 0.0):
        min_diag = float(np.min(diag))
        raise NumericalBackendError(
            f"Matrix A diagonal contains non-positive entries (minimum diagonal value = {min_diag:.2e} <= 0). "
            "Necessary condition for positive definiteness failed."
        )

    # 6. Positive-Definiteness Policy
    lambda_min = 0.0
    lambda_max = 0.0

    if not caller_certified_spd:
        # Perform rigorous spectral verification of smallest algebraic eigenvalue
        if n_rows <= 300:
            dense_A = A_mat.toarray() if sp.issparse(A_mat) else A_mat
            eigvals = la.eigvalsh(dense_A)
            lambda_min = float(eigvals[0])
            lambda_max = float(eigvals[-1])
        else:
            try:
                ncv_val = min(n_rows - 1, 25)
                lambda_max = float(spla.eigsh(A_mat, k=1, which="LA", return_eigenvectors=False, ncv=ncv_val)[0])
                lambda_min = float(spla.eigsh(A_mat, k=1, which="SA", return_eigenvectors=False, ncv=ncv_val)[0])
            except Exception as e:
                raise NumericalBackendError(
                    f"Positive-definiteness could not be established by eigensolve: {str(e)}. "
                    "If this matrix is physically guaranteed to be SPD by boundary constraints, pass caller_certified_spd=True."
                ) from e

        scale = max(abs(lambda_min), abs(lambda_max), np.finfo(float).tiny)
        null_threshold = null_tol * scale

        # Case A: Indefinite (negative eigenvalue)
        if lambda_min < -null_threshold:
            raise NumericalBackendError(
                f"Matrix A is indefinite: smallest algebraic eigenvalue lambda_min = {lambda_min:.2e} < 0. "
                "Conjugate Gradient strictly requires a positive-definite matrix."
            )

        # Case B: Singular or Positive Semi-Definite (near-zero eigenvalue / rigid body mode)
        if abs(lambda_min) <= null_threshold:
            raise NumericalBackendError(
                f"Matrix A appears singular or positive-semidefinite: lambda_min = {lambda_min:.2e} "
                f"(within null tolerance {null_threshold:.2e}). "
                "Conjugate Gradient requires a strictly positive-definite operator without rigid body modes."
            )

    return n_rows, lambda_min, lambda_max
