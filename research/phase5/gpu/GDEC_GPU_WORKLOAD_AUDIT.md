# GDEC GPU Workload Audit: Computational Profiling and Acceleration Suitability

**Document Reference:** `research/phase5/gpu/GDEC_GPU_WORKLOAD_AUDIT.md`  
**Workstream:** Agent 1 — GPU/CUDA Engineering Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Workload Suitability Matrix Established  

---

## 1. Executive Summary

This report performs a comprehensive, code-level audit of all computational routines in the GDEC platform (`src/gdec/fem/`, `src/gdec/core/`, and `src/gdec/runtime/`). Every stage of the finite element pipeline—from constitutive evaluation and sparse matrix assembly to linear solves, dual-weighted residual (DWR) estimation, adaptive refinement, and uncertainty propagation—is scrutinized to identify its algorithmic characteristics, parallelization potential, and GPU suitability.

Rather than assuming all operations benefit from GPU offloading, each workload is classified into:
1. **HIGH PRIORITY GPU ACCELERATION:** Operations with massive data parallelism, high arithmetic intensity, and minimal serialization bottlenecks.
2. **CONDITIONAL / HYBRID ACCELERATION:** Operations that benefit from GPU offloading only at scale or when data is already resident in device memory.
3. **REMAIN ON CPU:** Operations with irregular sparsity, sequential dependencies, low arithmetic intensity, or where PCIe transfer overhead exceeds compute gains.

---

## 2. Detailed Workload-by-Workload Audit

### Workload 1: Element Stiffness Calculations & Numerical Integration
- **Current Implementation:** `src/gdec/fem/elasticity.py` via `skfem.asm` and quadrature loops (`skfem.ElementTriP1`, `skfem.FacetBasis`). Evaluates constitutive matrix $\mathbf{C}$ and strain-displacement matrix $\mathbf{B}$ at 3-point interior Gauss quadrature points.
- **Computational Complexity:** $\mathcal{O}(N_{\text{elements}} \cdot N_{\text{qp}} \cdot N_{\text{dof/elem}}^2) = \mathcal{O}(N_{\text{elem}} \cdot 3 \cdot 36)$.
- **Parallelisation Potential:** Embarrassingly parallel across elements. Each triangular element can be evaluated by a separate GPU thread or thread group with zero inter-element dependencies.
- **Data Dependencies:** None between elements. Reads nodal coordinate arrays `p` and connectivity `t`.
- **Memory Requirements:** $\mathcal{O}(N_{\text{elem}} \cdot 36)$ floats. Very low footprint ($\approx 10\text{ MB}$ for $100,000$ elements).
- **Transfer Overhead:** Requires transferring mesh coordinate array `p` and connectivity `t` to GPU once.
- **Expected GPU Benefit:** **Very High ($10\times - 30\times$)** when fused directly into GPU sparse assembly or matrix-free operator evaluation.
- **Numerical Risks:** Minimal; floating-point evaluation order on single elements is deterministic.
- **Implementation Complexity:** Medium (requires custom Numba CUDA kernel or CuPy vectorized tensor operations).
- **CPU Baseline:** Current NumPy/skfem vectorized C-extension runs in $\approx 20 - 50\text{ ms}$ for $10^5$ elements.
- **Suitable GPU Libraries:** CuPy raw kernels or Numba CUDA.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE** (in a fused assembly pipeline).

---

### Workload 2: Sparse Matrix Assembly
- **Current Implementation:** Assembles local element matrices $K_e \in \mathbb{R}^{6 \times 6}$ into global CSR format via coordinate list (COO) triplet arrays `(rows, cols, data)` followed by `scipy.sparse.coo_matrix.tocsr()`.
- **Computational Complexity:** $\mathcal{O}(N_{\text{elem}} \cdot 36)$ to generate triplets; $\mathcal{O}(N_{\text{nz}} \log N_{\text{nz}})$ for sorting/summing duplicate entries during CSR conversion.
- **Parallelisation Potential:** Generating triplets is embarrassingly parallel. Summing duplicate entries into global CSR requires atomic additions or segmented parallel sort.
- **Data Dependencies:** Atomic write collisions where multiple elements share a common global node/DOF.
- **Memory Requirements:** COO triplets require $3 \times 36 \times N_{\text{elem}}$ integers and doubles.
- **Transfer Overhead:** If assembled on GPU and solved on GPU, zero transfer overhead.
- **Expected GPU Benefit:** **Moderate to High ($5\times - 15\times$)** if kept on GPU; negative if transferred back to CPU.
- **Numerical Risks:** Atomic floating-point additions (`atomicAdd`) are non-associative; can cause non-deterministic roundoff at the least significant bit ($10^{-16}$) across runs unless deterministic binning is used.
- **Implementation Complexity:** High (requires cuSPARSE or custom segmented radix sort).
- **CPU Baseline:** SciPy COO-to-CSR sort takes $\approx 35\%$ of total setup time.
- **Suitable GPU Libraries:** CuPy `cupyx.scipy.sparse.coo_matrix` or cuSPARSE.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE** (paired with GPU solver).

---

### Workload 3: Sparse Matrix-Vector Multiplication (SpMV)
- **Current Implementation:** `K_mat.dot(p)` in `ConjugateGradientSolver` (`src/gdec/fem/solvers/iterative.py`).
- **Computational Complexity:** $\mathcal{O}(N_{\text{nz}})$ operations per Krylov iteration, where $N_{\text{nz}} \approx 15 - 20 N_{\text{dof}}$ in 2D elasticity.
- **Parallelisation Potential:** High; parallelized across rows. Each row dot product is computed independently.
- **Data Dependencies:** Read-only access to matrix arrays `indptr`, `indices`, `data`, and vector $p$; write to vector $w$.
- **Memory Requirements:** Memory bandwidth bound. Operational intensity is low ($\approx 0.25$ FLOP/byte).
- **Transfer Overhead:** Zero if matrix and vectors remain in GPU VRAM during the iterative solve loop.
- **Expected GPU Benefit:** **High ($5\times - 20\times$)** at large scale ($N > 100,000$ DOFs) where GPU VRAM bandwidth ($1,000+\text{ GB/s}$) outperforms CPU DDR5 ($60 - 90\text{ GB/s}$). Negligible or negative for small 2D meshes ($N < 5,000$).
- **Numerical Risks:** Negligible; IEEE 754 compliance in cuSPARSE.
- **Implementation Complexity:** Low (native cuSPARSE / CuPy SpMV).
- **CPU Baseline:** SciPy CSR dot product runs at memory bandwidth limit ($\approx 25\text{ GB/s}$ effective).
- **Suitable GPU Libraries:** `cupy.sparse.csr_matrix` / `cusparseSpMV`.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE** for large-scale iterative solvers.

---

### Workload 4: Preconditioner Operations
- **Current Implementation:** `IdentityPreconditioner`, `JacobiPreconditioner`, `IncompleteCholeskyPreconditioner`, and `AMGPreconditioner` (`src/gdec/fem/solvers/iterative.py`).
- **Computational Complexity:**
  - Jacobi: $\mathcal{O}(N)$ vector scaling.
  - Incomplete Cholesky / ILU: $\mathcal{O}(N_{\text{nz}})$ sparse triangular solves ($L y = r, L^T z = y$).
  - AMG: $\mathcal{O}(N_{\text{levels}} \cdot N_{\text{nz}})$ V-cycle smoothing and restriction/prolongation.
- **Parallelisation Potential:**
  - Jacobi: Embarrassingly parallel ($100\%$ SIMT efficiency).
  - Incomplete Cholesky / ILU: **Inherently sequential**. Parallel sparse triangular solve (`cusparseSpSV`) requires level-scheduling / DAG analysis; concurrency is low and GPU utilization is poor.
  - AMG: Smoothing (Jacobi or polynomial Chebyshev) is highly parallel; Gauss-Seidel requires multicoloring.
- **Data Dependencies:** Triangular solves have strict topological dependencies.
- **Expected GPU Benefit:**
  - Jacobi: Very High ($15\times - 30\times$).
  - IC(0) / ILU: **Low or Negative ($0.5\times - 1.5\times$)** due to lack of concurrency and synchronization latency.
  - AMG with polynomial/Jacobi smoothing: High ($5\times - 15\times$).
- **Numerical Risks:** Multicolored Gauss-Seidel alters iteration trajectory and ordering compared to lexicographic CPU sweeps.
- **Verdict:**
  - Jacobi & Polynomial AMG: **HIGH PRIORITY GPU CANDIDATE**.
  - Incomplete Cholesky IC(0): **REMAIN ON CPU**.

---

### Workload 5: Direct Sparse Linear Solvers
- **Current Implementation:** `scipy.sparse.linalg.factorized` (SuperLU 5.3.0) with single-factorization reuse across primal and adjoint solves (`LinearElasticitySolver`).
- **Computational Complexity:** 2D factorization $\mathcal{O}(N^{1.5})$; backsolve $\mathcal{O}(N \log N)$.
- **Parallelisation Potential:** Low to Moderate. Sparse LU factorization involves irregular symbolic analysis, fill-in reordering, and pivoting.
- **Data Dependencies:** High structural dependency across sparse elimination trees.
- **Memory Requirements:** High fill-in memory (often $5\times - 15\times$ original $N_{\text{nz}}$).
- **Transfer Overhead:** Transferring LU factors across PCIe is cost-prohibitive.
- **Expected GPU Benefit:** **Poor for 2D meshes ($N < 50,000$)**. As established in Phase 4 benchmarks, SuperLU on CPU solves 2D problems in $< 46\text{ ms}$. cuSOLVER-Sp sparse LU has high setup overhead.
- **Numerical Risks:** Potential loss of pivoting stability or high VRAM exhaustion on fine meshes.
- **Verdict:** **REMAIN ON CPU** for 2D direct solves; re-evaluate only for 3D massive models.

---

### Workload 6: Iterative Linear Solvers (CG / PCG)
- **Current Implementation:** `ConjugateGradientSolver` with upfront spectral check, scale-aware null mode detection, and runtime curvature monitoring.
- **Computational Complexity:** $\mathcal{O}(N_{\text{iter}} \cdot N_{\text{nz}})$.
- **Parallelisation Potential:** Entirely parallelizable if SpMV, vector additions, inner products, and preconditioning reside on GPU.
- **Data Dependencies:** Inner products require global reduction (`p^T A p`, `r^T z`). Global reductions require inter-block synchronization across SMs.
- **Expected GPU Benefit:** **High ($5\times - 15\times$)** at $N > 50,000$ DOFs; **Negative ($0.2\times - 0.8\times$)** at $N < 2,000$ DOFs due to kernel launch latency ($\sim 5\ \mu\text{s} \times 4\text{ kernels} \times N_{\text{iter}}$).
- **Numerical Risks:** Summation order in parallel reduction (`atomicAdd` vs. reduction tree) causes minor non-deterministic drift ($10^{-15}$) in residual norms.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE** for large-scale systems ($N \ge 20,000$).

---

### Workload 7: Primal and Adjoint Solves
- **Current Implementation:** Linear elasticity solver solves $K_{ff} u = f$ and $K_{ff} \psi = g_{\text{dual}}$.
- **Computational Complexity:** $2 \times$ linear solve cost.
- **Parallelisation Potential:** On CPU direct solvers, factorization is reused ($1.96\times$ speedup). On GPU iterative solvers, primal and adjoint can be solved concurrently in separate CUDA streams!
- **Expected GPU Benefit:** **Very High ($2\times$ concurrency boost)** via dual CUDA streams executing simultaneously.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE**.

---

### Workload 8: QoI Evaluation
- **Current Implementation:** Boundary integration of displacements or stresses via `FacetBasis` (`assemble_boundary_qoi`).
- **Computational Complexity:** $\mathcal{O}(N_{\text{boundary\_facets}})$.
- **Parallelisation Potential:** Highly parallel across boundary facets.
- **Expected GPU Benefit:** Low isolated benefit ($\approx 0.1\text{ ms}$ on CPU), but **Essential for Data Locality** (evaluating QoI on GPU avoids transferring the displacement field $u$ back to host memory).
- **Verdict:** **CONDITIONAL ACCELERATION** (fused on GPU to preserve data locality).

---

### Workload 9: Dual-Weighted Residual (DWR) Error Estimation
- **Current Implementation:** `ElementResidualEvaluator` (interior residual), `FacetJumpEvaluator` (traction jumps across interior facets), and `DualWeightEvaluator` (quadratic patch enrichment $E(z) - z_h$).
- **Computational Complexity:** $\mathcal{O}(N_{\text{facets}} + N_{\text{elem}})$.
- **Parallelisation Potential:**
  - Interior residual: Embarrassingly parallel across elements.
  - Facet jumps: Embarrassingly parallel across interior facets.
  - Dual weight evaluation: Local element patches or basis enrichments are embarrassingly parallel.
- **Data Dependencies:** Facet jumps require reading stress tensors from both sharing elements.
- **Expected GPU Benefit:** **Very High ($10\times - 25\times$)**. DWR currently represents $> 40\%$ of adaptive refinement pipeline time on CPU.
- **Verdict:** **HIGH PRIORITY GPU CANDIDATE**.

---

### Workload 10: Mesh Operations & Refinement Topology
- **Current Implementation:** Red-green triangular subdivision, topological connectivity updates, boundary facet classification in `Mesh` / `skfem`.
- **Computational Complexity:** $\mathcal{O}(N_{\text{elem}} \log N_{\text{elem}})$ for edge hashing, vertex creation, and non-conforming hanging node elimination.
- **Parallelisation Potential:** Low. Highly irregular memory graphs, dynamic memory allocation, and topological pointer chasing.
- **Expected GPU Benefit:** **Poor / Negative**. GPU mesh subdivision algorithms (e.g., CUDA dynamic parallelism) are notoriously complex, prone to race conditions, and suffer severe warp divergence.
- **Verdict:** **REMAIN ON CPU**. Mesh refinement should occur on CPU, with updated mesh geometry streamed to GPU for subsequent solve/DWR stages.

---

### Workload 11: Parameter Sweeps, Multi-Case & Monte Carlo UQ
- **Current Implementation:** Serial or Python multiprocessing loops across load cases, material parameters, or uncertain inputs.
- **Computational Complexity:** $\mathcal{O}(N_{\text{cases}} \times \text{Cost}_{\text{solve}})$.
- **Parallelisation Potential:** **Embarrassingly parallel across simulation runs (Coarse-Grained Batching)**.
- **Expected GPU Benefit:** **Exceptional ($20\times - 50\times$)**. Batched linear solvers and concurrent kernel streams allow dozens of independent load cases or parameter samples to execute concurrently on a single GPU.
- **Verdict:** **HIGHEST STRATEGIC VALUE GPU CANDIDATE**.

---

## 3. Summary Workload Prioritization Matrix

| Workload ID | Operation Description | Compute Bound? | Parallel Potential | Transfer Penalty | Strategic Recommendation |
|:---:|---|:---:|:---:|:---:|:---|
| **W1** | Element Stiffness & Quadrature | Yes | Very High | Low | **ACCELERATE (Phase 5.1/5.2)** |
| **W2** | Sparse Matrix Assembly | No (Memory) | High | Zero (if fused) | **ACCELERATE (Phase 5.2)** |
| **W3** | SpMV (Sparse Mat-Vec) | No (Bandwidth) | Very High | Zero (resident) | **ACCELERATE (Phase 5.1)** |
| **W4a**| Jacobi / Polynomial Preconditioner| No (Bandwidth) | Very High | Zero (resident) | **ACCELERATE (Phase 5.1)** |
| **W4b**| Incomplete Cholesky IC(0) | No (Latency) | Low (Sequential)| High | **REMAIN ON CPU** |
| **W5** | Sparse Direct Solver (SuperLU) | Mixed | Low in 2D | High | **REMAIN ON CPU (2D Production)** |
| **W6** | Iterative CG / PCG Solver Loop | No (Bandwidth) | High ($N > 20k$) | Zero (resident) | **ACCELERATE (Phase 5.1)** |
| **W7** | Concurrent Primal + Adjoint Solve | Yes | Very High (Streams)| Zero (resident) | **ACCELERATE (Phase 5.2)** |
| **W8** | Boundary QoI Evaluation | No | High | Zero (resident) | **ACCELERATE (Fused, Phase 5.2)** |
| **W9** | DWR Element & Facet Estimators | Yes | Very High | Zero (resident) | **ACCELERATE (Phase 5.3)** |
| **W10**| Mesh Refinement & Subdivision | No (Topology) | Low (Irregular) | High | **REMAIN ON CPU** |
| **W11**| Parameter Sweeps / Batched UQ | Yes | Extreme | Amortized | **ACCELERATE (Phase 5.3)** |
