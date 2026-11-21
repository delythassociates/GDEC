"""
ExecutionBackend Protocol definition for GDEC.
Provides a minimal, strictly typed interface for CPU and accelerator hardware execution.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable, Dict, Any, Tuple, Optional
from gdec.core.backend.capabilities import BackendCapabilities


@runtime_checkable
class ExecutionBackend(Protocol):
    """
    Protocol defining the execution contract for GDEC computational backends.
    Distinguishes foundational linear algebra, optional iterative solves,
    and batch evaluation without making speculative claims about FEM assembly.
    """

    @property
    def name(self) -> str:
        """Unique backend identifier (e.g. 'cpu', 'cuda')."""
        ...

    @property
    def is_available(self) -> bool:
        """True if the backend is fully operational on this host machine."""
        ...

    @property
    def capabilities(self) -> BackendCapabilities:
        """Structured capability metadata and operational status."""
        ...

    def get_device_info(self) -> Dict[str, Any]:
        """Hardware, library, and driver diagnostic information."""
        ...

    def spmv(self, A: Any, x: Any) -> Any:
        """
        Compute sparse matrix-vector product: y = A @ x.

        Parameters
        ----------
        A : scipy.sparse.csr_matrix or backend-native matrix
            Sparse matrix in CSR format (m, n).
        x : numpy.ndarray or backend-native array
            Vector of length n.

        Returns
        -------
        y : numpy.ndarray or backend-native array
            Resulting vector of length m.
        """
        ...

    def solve_direct(self, A: Any, b: Any) -> Any:
        """
        Solve linear system A x = b using a sparse direct method (SuperLU).

        Parameters
        ----------
        A : scipy.sparse.spmatrix or backend-native matrix
            Square, non-singular sparse matrix (n, n).
        b : numpy.ndarray or backend-native array
            Right-hand side vector of length n.

        Returns
        -------
        x : numpy.ndarray or backend-native array
            Solution vector of length n.
        """
        ...

    def solve_cg(
        self,
        A: Any,
        b: Any,
        rtol: float = 1e-8,
        atol: float = 1e-12,
        max_iter: Optional[int] = None,
        M: Optional[Any] = None,
        caller_certified_spd: bool = False,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Solve linear system A x = b using Conjugate Gradient with strict SPD checks.

        Parameters
        ----------
        A : scipy.sparse.spmatrix or backend-native matrix
            Symmetric positive definite sparse matrix (n, n).
        b : numpy.ndarray or backend-native array
            Right-hand side vector of length n.
        rtol : float
            Relative convergence tolerance.
        atol : float
            Absolute convergence tolerance.
        max_iter : int, optional
            Maximum allowed CG iterations.
        M : preconditioner, optional
            LinearOperator or matrix preconditioner.
        caller_certified_spd : bool
            Whether caller explicitly certifies SPD structure to bypass eigenvalue check.

        Returns
        -------
        x : solution vector
        info : dict containing iteration count, final residual norm, and convergence status.
        """
        ...

    def solve_multiple_rhs(self, A: Any, B: Any) -> Any:
        """
        Solve linear system A X = B for multiple right-hand sides simultaneously.

        Parameters
        ----------
        A : scipy.sparse.spmatrix or backend-native matrix
            Square, non-singular sparse matrix (n, n).
        B : numpy.ndarray or backend-native array
            Right-hand side matrix of shape (n, k).

        Returns
        -------
        X : solution matrix of shape (n, k).
        """
        ...

    def synchronize(self) -> None:
        """
        Block until all pending operations on the device queue have finished.
        No-op on synchronous CPU backends.
        """
        ...

    def evaluate_parameter_scaling_batch(
        self,
        E_vals: Any,
        P_vals: Any,
        J_0: float,
        E_0: float,
        P_0: float,
    ) -> Any:
        """
        Compute analytical linear-elastic parameter scaling for an array of (E, P) samples:
        J(E, P) = (P / P_0) * (E_0 / E) * J_0

        Parameters
        ----------
        E_vals : 1D array of sampled Young's moduli (E > 0)
        P_vals : 1D array of sampled load factors (P)
        J_0 : Reference QoI value at (E_0, P_0)
        E_0 : Reference Young's modulus (E_0 > 0)
        P_0 : Reference load factor (P_0 != 0)

        Returns
        -------
        1D array of scaled QoI values.
        """
        ...
