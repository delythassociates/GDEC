# GPU vs CPU Benchmark Results & Performance Analysis (Phase 5.1.1)

## 1. Overview of Experimental Results

Hardware Platform: NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM, SM 8.6) | AMD Ryzen Host | CuPy 14.2.0 | SciPy 1.15.2.

---

## 2. Sparse Matrix-Vector Multiplication (SpMV)

Evaluated on true 2D Kronecker Laplacian matrices ($A = I_y \otimes T_x + T_y \otimes I_x$). 30 repetitions per scale.

| Workload | Grid / DOFs ($N$) | Nonzeros (NNZ) | CPU Wall Mean | GPU Resident Mean | GPU E2E Mean | Resident Speedup | E2E Speedup | Rel $L_2$ Error |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Small** | $70 \times 70$ (4,900) | 24,220 | 0.0230 ms | 0.1379 ms | 0.7324 ms | **0.17x** (CPU faster) | **0.03x** | $1.10 \times 10^{-16}$ |
| **Medium** | $160 \times 160$ (25,600) | 127,360 | 0.0745 ms | 0.1292 ms | 1.0464 ms | **0.58x** (CPU faster) | **0.07x** | $1.14 \times 10^{-16}$ |
| **Large** | $320 \times 320$ (102,400) | 510,720 | 0.5084 ms | 0.1934 ms | 2.0020 ms | **2.63x** (GPU faster) | **0.25x** | $1.14 \times 10^{-16}$ |

### SpMV Analysis:
- **Crossover Threshold:** Device-resident GPU SpMV becomes faster than single-threaded CPU between $N \approx 50,000$ and $N \approx 75,000$ DOFs. At $N = 102,400$, GPU kernel speedup is $2.63\times$.
- **PCIe Transfer Overhead:** End-to-end SpMV (including H2D matrix/vector transfer and D2H result retrieval) is dominated by PCIe bus latency (0.7 to 2.0 ms), meaning single one-off SpMV should never be offloaded to GPU.

---

## 3. Batched Analytical Parameter Scaling

Evaluated evaluating $(P / P_0)(E_0 / E) J_0$ across sample batches from 1,000 to 1,000,000 Monte Carlo samples. 30 repetitions.

| Batch Size | CPU Vectorized Mean | GPU Resident Mean | GPU E2E Mean | Resident Speedup | E2E Speedup | Rel $L_2$ Error |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1,000** | 0.0081 ms | 0.1270 ms | 0.4740 ms | 0.06x | 0.02x | $0.00 \times 10^{0}$ |
| **10,000** | 0.0557 ms | 0.2388 ms | 0.5328 ms | 0.23x | 0.10x | $0.00 \times 10^{0}$ |
| **100,000** | 0.2377 ms | 0.1962 ms | 0.9106 ms | **1.21x** | 0.26x | $0.00 \times 10^{0}$ |
| **1,000,000** | 5.6409 ms | 0.6666 ms | 3.8974 ms | **8.46x** | **1.45x** | $0.00 \times 10^{0}$ |

### Parameter Scaling Analysis:
- For large Monte Carlo UQ ensembles ($10^6$ evaluations), device-resident execution is **$8.46\times$ faster** than optimized NumPy vectorization.
- Even including full host-to-device and device-to-host array copies, end-to-end GPU execution is **$1.45\times$ faster** ($3.90$ ms vs $5.64$ ms).

---

## 4. Preconditioned Conjugate Gradient (PCG with Jacobi)

Evaluated solving $A x = b$ on 2D Laplacian grids to target relative residual $\|b - Ax\|_2 / \|b\|_2 \le 10^{-6}$.

| Scale | DOFs ($N$) | CPU PCG Mean | CPU Final Rel Res | GPU Res PCG Mean | GPU Final Rel Res | Speedup (Resident) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Small** | 4,900 | 7.89 ms | $8.89 \times 10^{-7}$ | 103.42 ms | $8.89 \times 10^{-7}$ | **0.08x** (CPU $13\times$ faster) |
| **Medium** | 25,600 | 164.45 ms | $9.94 \times 10^{-7}$ | 229.90 ms | $9.94 \times 10^{-7}$ | **0.72x** (CPU $1.4\times$ faster) |

### Iterative Solver Analysis:
- CuPy's iterative solver executes the CG iteration loop via Python / host dispatch. At $N \le 25,600$, kernel launch overhead per iteration dwarfs raw compute throughput.
- Consequently, CPU PCG remains substantially faster than GPU PCG for small-to-medium systems. GPU iterative solvers require either $N > 100,000$ or fused C++/CUDA iterative kernels (deferred to Phase 5.2).

---

## 5. CPU Multiple-RHS Factorization Reuse vs Direct Solves

Evaluated on $N = 10,000$ DOFs with 2 load cases (primal & adjoint systems).

| Strategy | Execution Details | Mean Time | Speedup vs Independent |
| :--- | :--- | :--- | :--- |
| **Independent Solves** | 2x SuperLU factorizations (`spla.spsolve`) | 7.349 ms | $1.00\times$ (Baseline) |
| **Factorization Reuse** | 1x `spla.splu` + 2x triangular solves | 3.704 ms | **$1.98\times$** |
| **Multi-RHS Block Solve**| 1x `spla.splu` + 1x block solve (`lu.solve(B)`) | 3.449 ms | **$2.13\times$** |

### Finding:
Reusing SuperLU LU factors for primal and adjoint systems achieves an immediate **$2\times$ throughput speedup** on CPU without any GPU offload requirements.
