"""
Stiffness Matrix Diagnostics and Conditioning Analysis for GDEC.
Provides rigorous verification of matrix properties:
- Dimension and sparsity
- Symmetry defect: delta_sym = ||K - K^T||_F / max(||K||_F, eps)
- Spectrum: smallest and largest eigenvalues via sparse/dense estimators
- Condition number: kappa_2(K) = lambda_max / lambda_min
- Solver eligibility (SPD, CG-eligible, singular, rigid-body modes)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import scipy.linalg as la


@dataclass
class MatrixDiagnostics:
    """Diagnostic metrics and eligibility assessment for a stiffness matrix."""
    n_rows: int
    n_cols: int
    nnz: int
    density: float
    sparsity_ratio: float
    symmetry_defect: float
    lambda_min: Optional[float]
    lambda_max: Optional[float]
    condition_number: Optional[float]
    is_square: bool
    is_symmetric: bool
    is_positive_definite: bool
    is_cg_eligible: bool
    null_modes_count: int
    warnings: List[str] = field(default_factory=list)
    eigenvalue_method: str = "none"

    def summary(self) -> str:
        lines = [
            f"=== Matrix Diagnostics ({self.n_rows} x {self.n_cols}) ===",
            f"Nonzeros (NNZ): {self.nnz:,} (Density: {self.density:.4%}, Sparsity: {self.sparsity_ratio:.4%})",
            f"Symmetry Defect (delta_sym): {self.symmetry_defect:.2e} (Symmetric: {self.is_symmetric})",
        ]
        if self.lambda_min is not None and self.lambda_max is not None:
            cond_str = f"{self.condition_number:.2e}" if self.condition_number is not None else "N/A"
            lines.extend([
                f"Eigenvalue Spectrum [{self.eigenvalue_method}]:",
                f"  lambda_min: {self.lambda_min:.6e}",
                f"  lambda_max: {self.lambda_max:.6e}",
                f"  kappa_2 (cond): {cond_str}",
            ])
        lines.extend([
            f"Positive Definite: {self.is_positive_definite}",
            f"CG Eligible: {self.is_cg_eligible}",
            f"Near-Zero Modes (Rigid-body/Null): {self.null_modes_count}",
        ])
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  [WARN] {w}")
        return "\n".join(lines)


def compute_symmetry_defect(
    K: sp.spmatrix | np.ndarray, eps: float = 1e-15
) -> float:
    r"""
    Compute relative Frobenius symmetry defect:
      \delta_{sym} = \frac{||K - K^T||_F}{\max(||K||_F, \epsilon)}
    """
    if sp.issparse(K):
        K_csr = K.tocsr()
        norm_K = spla.norm(K_csr, "fro")
        diff = (K_csr - K_csr.T).tocsr()
        norm_diff = spla.norm(diff, "fro")
    else:
        K_arr = np.asarray(K)
        norm_K = float(np.linalg.norm(K_arr, "fro"))
        diff = K_arr - K_arr.T
        norm_diff = float(np.linalg.norm(diff, "fro"))

    denom = max(norm_K, eps)
    return float(norm_diff / denom)


def analyze_stiffness_matrix(
    K: sp.spmatrix | np.ndarray,
    compute_spectrum: bool = True,
    dense_threshold: int = 400,
    sym_tol: float = 1e-10,
    null_tol: float = 1e-10,
) -> MatrixDiagnostics:
    r"""
    Analyze a stiffness matrix for symmetry, conditioning, null modes, and solver eligibility.

    Parameters
    ----------
    K : sparse matrix or 2D array
        The assembled or condensed stiffness matrix.
    compute_spectrum : bool
        Whether to estimate lambda_min and lambda_max.
    dense_threshold : int
        Dimension below which full dense eigensolve is used for exact spectrum.
    sym_tol : float
        Tolerance for symmetry defect delta_sym.
    null_tol : float
        Relative threshold for identifying near-zero (null or rigid-body) eigenvalues.

    Returns
    -------
    MatrixDiagnostics
    """
    warnings: List[str] = []

    if sp.issparse(K):
        n_rows, n_cols = K.shape
        nnz = K.nnz
        K_sparse = K.tocsr()
    else:
        K_arr = np.asarray(K)
        n_rows, n_cols = K_arr.shape
        nnz = int(np.count_nonzero(K_arr))
        K_sparse = sp.csr_matrix(K_arr)

    is_square = (n_rows == n_cols)
    if not is_square:
        warnings.append(f"Matrix is non-square ({n_rows} x {n_cols}).")
        return MatrixDiagnostics(
            n_rows=n_rows,
            n_cols=n_cols,
            nnz=nnz,
            density=float(nnz / (n_rows * n_cols)) if (n_rows * n_cols) > 0 else 0.0,
            sparsity_ratio=1.0 - float(nnz / (n_rows * n_cols)) if (n_rows * n_cols) > 0 else 0.0,
            symmetry_defect=float("nan"),
            lambda_min=None,
            lambda_max=None,
            condition_number=None,
            is_square=False,
            is_symmetric=False,
            is_positive_definite=False,
            is_cg_eligible=False,
            null_modes_count=0,
            warnings=warnings,
            eigenvalue_method="none",
        )

    total_entries = n_rows * n_cols
    density = float(nnz / total_entries) if total_entries > 0 else 0.0
    sparsity = 1.0 - density

    # Symmetry defect
    delta_sym = compute_symmetry_defect(K_sparse)
    is_symmetric = (delta_sym <= sym_tol)
    if not is_symmetric:
        warnings.append(f"Matrix is asymmetric: delta_sym = {delta_sym:.2e} > tol ({sym_tol:.2e}).")

    # Check diagonal elements
    diag = K_sparse.diagonal()
    if np.any(np.isnan(diag)) or np.any(np.isinf(diag)):
        warnings.append("Matrix diagonal contains NaN or Inf values.")
    min_diag = float(np.min(diag)) if len(diag) > 0 else 0.0
    if min_diag <= 0.0:
        zero_or_neg = int(np.sum(diag <= 0.0))
        warnings.append(f"Matrix diagonal contains {zero_or_neg} non-positive entries (min: {min_diag:.2e}).")

    lambda_min: Optional[float] = None
    lambda_max: Optional[float] = None
    condition_number: Optional[float] = None
    null_modes_count = 0
    is_positive_definite = False
    is_cg_eligible = False
    eigenvalue_method = "none"

    if compute_spectrum and n_rows >= 2:
        if n_rows <= dense_threshold:
            # Small systems: dense exact eigensolver
            eigenvalue_method = "dense_exact"
            K_dense = K_sparse.toarray()
            # For symmetric matrices use eigh (which uses only lower/upper triangle)
            if is_symmetric:
                eigvals = la.eigvalsh(K_dense)
            else:
                eigvals = np.real(la.eigvals(K_dense))
            eigvals = np.sort(eigvals)
            lambda_min = float(eigvals[0])
            lambda_max = float(eigvals[-1])
            norm_scale = max(abs(lambda_max), 1.0)
            null_modes_count = int(np.sum(np.abs(eigvals) < null_tol * norm_scale))
        else:
            # Large sparse systems: ARPACK via scipy.sparse.linalg.eigsh
            eigenvalue_method = "sparse_eigsh"
            try:
                # Symmetrize for eigsh to ensure numerical stability if matrix is theoretically symmetric
                K_sym = 0.5 * (K_sparse + K_sparse.T) if is_symmetric else K_sparse
                
                # Largest eigenvalue
                lmax_arr = spla.eigsh(K_sym, k=1, which="LA", return_eigenvectors=False)
                lambda_max = float(lmax_arr[0])

                # Smallest eigenvalue: shift-invert near 0 is most reliable for SPD
                try:
                    lmin_arr = spla.eigsh(K_sym, k=1, sigma=0.0, which="LM", return_eigenvectors=False)
                    lambda_min = float(lmin_arr[0])
                except Exception:
                    # Fallback to which='SA' if shift-invert encounters singular matrix
                    lmin_arr = spla.eigsh(K_sym, k=1, which="SA", return_eigenvectors=False)
                    lambda_min = float(lmin_arr[0])

                norm_scale = max(abs(lambda_max), 1.0)
                if abs(lambda_min) < null_tol * norm_scale:
                    null_modes_count = 1
            except Exception as e:
                warnings.append(f"Sparse eigenvalue computation encountered exception: {e}")

        norm_scale = max(abs(lambda_max), 1.0)
        if lambda_min is not None and lambda_max is not None:
            if null_modes_count > 0 or lambda_min <= null_tol * norm_scale:
                is_positive_definite = False
                condition_number = float("inf")
                if lambda_min <= 0.0:
                    warnings.append(
                        f"Smallest eigenvalue is non-positive (lambda_min = {lambda_min:.2e}). "
                        "Matrix is singular or indefinite."
                    )
                else:
                    warnings.append(
                        f"Smallest eigenvalue is within null/rigid-body tolerance (lambda_min = {lambda_min:.2e}, "
                        f"ratio = {lambda_min / norm_scale:.2e} <= null_tol {null_tol:.2e}). "
                        "Matrix is mathematically singular due to unconstrained rigid-body motion."
                    )
            else:
                is_positive_definite = True
                condition_number = float(lambda_max / lambda_min)
                if condition_number > 1e12:
                    warnings.append(
                        f"Matrix is severely ill-conditioned: lambda_min = {lambda_min:.2e}, "
                        f"kappa_2 = {condition_number:.2e}."
                    )

    is_cg_eligible = is_square and is_symmetric and is_positive_definite and (null_modes_count == 0)

    if null_modes_count > 0:
        warnings.append(
            f"Detected {null_modes_count} near-zero / rigid-body mode(s). "
            "Boundary conditions may be insufficient to prevent rigid-body motion."
        )

    return MatrixDiagnostics(
        n_rows=n_rows,
        n_cols=n_cols,
        nnz=nnz,
        density=density,
        sparsity_ratio=sparsity,
        symmetry_defect=delta_sym,
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        condition_number=condition_number,
        is_square=is_square,
        is_symmetric=is_symmetric,
        is_positive_definite=is_positive_definite,
        is_cg_eligible=is_cg_eligible,
        null_modes_count=null_modes_count,
        warnings=warnings,
        eigenvalue_method=eigenvalue_method,
    )
