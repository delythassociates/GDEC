# GDEC Solver Reconnaissance & Architecture Audit

## 1. Executive Summary

This report establishes the baseline linear algebra architecture and solver lifecycle for **GDEC (Goal-Driven Engineering Computation)** as of Phase 4 (`audit/v0.2.2-deep-review`). 

The investigation examined:
- Global and condensed finite element matrix representations.
- Boundary condition condensation and partitioning.
- The actual mathematical factorization backend utilized by `scipy.sparse.linalg.factorized`.
- Solver lifecycle and single-factorization reuse across primal and adjoint solves.
- Installed sparse linear algebra dependencies, Python matrix support, and CI configuration.

### Key Architectural Finding: SuperLU vs Sparse Cholesky
A critical finding of this audit is that **`scipy.sparse.linalg.factorized` does NOT compute a sparse Cholesky factorization**. 
When provided with a CSC matrix $K_{ff}$, SciPy's `factorized()` routine delegates directly to `scipy.sparse.linalg.splu(A.tocsc()).solve` (unless the optional external package `scikits.umfpack` is installed). `splu` invokes **SuperLU**, which computes an unsymmetric sparse LU decomposition:
$$P_r A P_c = L U$$
where $P_r$ and $P_c$ are row and column permutation matrices, $L$ is unit lower triangular, and $U$ is upper triangular. Although $K_{ff}$ is symmetric positive-definite (SPD), SuperLU treats it as a general unsymmetric matrix. It does not exploit symmetry to halve floating-point operations or memory storage.

---

## 2. Solver Architecture and Component Inventory

The linear elasticity solver in GDEC is implemented primarily in `src/gdec/fem/elasticity.py` within `LinearElasticitySolver`.

```
+-----------------------------------------------------------------------+
| GDEC Finite Element Formulation: P1 Lagrange Triangles on R^2        |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| Stiffness Assembly: BilinearForm -> skfem.asm -> scipy.sparse.csr_matrix |
| External Loads:     LinearForm   -> skfem.asm -> np.ndarray (N,)      |
| QoI Adjoint Vector: LinearForm   -> skfem.asm -> np.ndarray (N,)      |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| Condensation (skfem.condense):                                        |
|   Partitions DOFs into fixed (D) and free (I) sets.                   |
|   Extracts K_free = K[I, I], f_free = f[I] - K[I, D] u_D              |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| Direct Sparse Solver Backend:                                         |
|   1. K_free.tocsc() -> spla.factorized()                              |
|      Backend: SuperLU (scipy.sparse.linalg.splu)                      |
|      Computes: P_r K_free P_c = L U                                   |
|   2. Primal Solve: u_free = solve_fac(f_free)                         |
|   3. Factorization Reuse: z_free = solve_fac(g_free) [Adjoint]        |
+-----------------------------------------------------------------------+
```

### Inspected Files
1. `src/gdec/fem/elasticity.py`:
   - `ConstitutiveTensor`: Plane stress and plane strain constitutive tensors ($C_{11}, C_{12}, C_{33}$).
   - `FEMSolution`: Solution container storing displacement vector $u$, adjoint vector $z$, stiffness matrix $K$, load vectors $f$ and $g$, fixed DOFs, QoI values, and discrete profiling timings.
   - `LinearElasticitySolver.assemble_stiffness`: Assembles global CSR matrix via `skfem.asm`.
   - `LinearElasticitySolver.solve`: Executes condensation, factorization, and primal/adjoint solves.
2. `src/gdec/fem/mesh.py`:
   - `GDECMesh`: Conforming Delaunay triangular mesh wrapper around `skfem.MeshTri`.
   - Provides boundary facet extraction and uniform/adaptive red-green refinement.
3. `src/gdec/fem/estimators.py`:
   - Dual-Weighted Residual (DWR) and recovery-based error estimators.
4. `src/gdec/core/runtime.py`:
   - Coordinates execution loop, monitoring adaptive iterations, stage profiling, and stopping criteria.
5. `src/gdec/core/planner.py`:
   - Generates initial execution plan, initial mesh aspect ratio, and solver strategy.
6. `src/gdec/language/ir.py`:
   - Typed intermediate representation (Pydantic models) validating physical constraints, loads, materials, and accuracy budgets.

---

## 3. Detailed Factorization Backend Analysis

SciPy's implementation of `scipy.sparse.linalg.factorized` was directly inspected in the active environment (`scipy 1.18.1`):

```python
def factorized(A):
    # If scikits.umfpack is available, use UmfpackContext.
    # Otherwise:
    return splu(A).solve
```

In the standard scientific Python environment (Linux, Windows, macOS wheels without `scikits.umfpack` or `scikit-sparse`):
1. **Factorization Type:** Unsymmetric Sparse LU factorization with partial pivoting ($P_r A P_c = L U$).
2. **Library Backend:** SuperLU 5.x (compiled C library embedded inside SciPy).
3. **Exploitation of Symmetry:** None. SuperLU performs column preordering (e.g., COLAMD) to preserve sparsity, but computes separate $L$ and $U$ factors.
4. **Contrast with Sparse Cholesky:**
   - **True Sparse Cholesky ($L L^T$ or $L D L^T$):** Requires only the lower-triangular sparsity pattern. It uses Approximate Minimum Degree (AMD) ordering, guarantees stability without numerical pivoting for SPD matrices, requires roughly half the FLOPs of LU, and consumes significantly less memory. Sparse Cholesky is provided by libraries like CHOLMOD (SuiteSparse), accessible in Python only via `scikit-sparse` (not installed by default).
   - **SuperLU ($L U$):** Computes both lower and upper triangular factors with permutation vectors $P_r$ and $P_c$.
5. **Lifecycle and Reusability:**
   - Calling `spla.factorized(K_free.tocsc())` returns a Python closure holding the underlying `SuperLU` C-object.
   - Calling `solve_fac(rhs)` performs a fast sparse triangular forward solve ($L y = P_r \text{rhs}$) and backward solve ($U (P_c^T x) = y$).
   - In GDEC, `reuse_factorization=True` leverages this closure to solve both the primal system $K_{ff} u_f = f_f$ and the adjoint system $K_{ff} z_f = g_f$ with zero re-factorization overhead.

---

## 4. Software Dependencies and Environment Inventory

| Package / Tool | Version in Environment | Role in GDEC |
|---|---|---|
| Python | 3.13.14 (local), 3.10-3.12 (CI) | Host programming language |
| NumPy | 1.26.4 / 2.x compatible | Vector and array operations |
| SciPy | 1.18.1 | Sparse matrices, SuperLU (`splu`), ARPACK (`eigsh`), iterative solvers |
| scikit-fem | 9.3.0 | Variational bilinear/linear forms and mesh data structures |
| PyAMG | **Not Installed** | Optional Algebraic Multigrid library |
| scikit-sparse | **Not Installed** | Optional SuiteSparse CHOLMOD direct Cholesky wrapper |
| pytest | 9.2.0 | Automated testing framework |

### CI Matrix Configuration
CI workflow `.github/workflows/ci.yml` runs on `ubuntu-latest` across:
- Python 3.10
- Python 3.11
- Python 3.12

Pre-change baseline test suite status:
- Total tests: 141 passed in 8.74 seconds.
- HEAD commit: `f7e2e1ac13b25e232b06ce8ec3c89dfd9cb21292`.
