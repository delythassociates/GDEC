# GDEC Phase 5.1 GPU Benchmark Results & Performance Analysis

**Document ID:** `GDEC-BENCH-P51-001`
**Date:** 2026-11-22
**Raw Data Source:** `research/phase5.1/gpu/GPU_BENCHMARK_RAW_RESULTS.csv`
**Benchmark Suite:** `benchmarks/phase5_1/gpu/benchmark_suite.py`
**Hardware Platform:**
- **GPU:** NVIDIA GeForce RTX 3050 Laptop GPU (6,143.5 MB GDDR6, Driver 595.97, CUDA 13.2)
- **CPU:** AMD64 Family 25 Model 68 Stepping 1 (8 Cores / 16 Threads, 23.7 GB RAM)
- **Software:** Python 3.13.14, NumPy 2.5.5, SciPy 1.18.1, CuPy 14.2.0

---

## 1. Summary of Experimental Results

All benchmarks were executed with a dedicated warm-up phase (10 iterations) and 50 timed repetitions for sparse operations (20 repetitions for batched parameter evaluations). Timings on GPU were recorded using hardware CUDA events (`cp.cuda.Event`) with explicit stream synchronization.

### Table 1: Sparse Matrix-Vector Multiplication (SpMV) Benchmarks

| Problem Scale | DOFs ($N$) | Nonzeros ($\text{nnz}$) | Sparsity | CPU SciPy Mean (ms) | GPU Resident Mean (ms) | Speedup (Resident) | GPU H2D Transfer (ms) | GPU D2H Transfer (ms) | GPU End-to-End (ms) | Speedup (End-to-End) | Rel $L_2$ Discrepancy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Scale_Small** | $5,000$ | $14,998$ | $6.00 \times 10^{-4}$ | $0.0174$ | $0.1537$ | $0.11\times$ | $0.2905$ | $0.0780$ | $0.5222$ | $0.03\times$ | $1.10 \times 10^{-16}$ |
| **Scale_Medium** | $25,000$ | $74,998$ | $1.20 \times 10^{-4}$ | $0.1525$ | $0.2017$ | $0.76\times$ | $0.4854$ | $0.1362$ | $0.8234$ | $0.19\times$ | $1.15 \times 10^{-16}$ |
| **Scale_Large** | $100,000$ | $299,998$ | $3.00 \times 10^{-5}$ | $0.8220$ | $0.2343$ | **$3.51\times$** | $1.0985$ | $0.3622$ | $1.6950$ | $0.48\times$ | $1.14 \times 10^{-16}$ |

---

### Table 2: Batched Analytical Parameter Scaling ($J = \frac{P}{P_0} \frac{E_0}{E} J_0$)

| Sample Count ($B$) | CPU NumPy Vectorized (ms) | GPU Resident Kernel (ms) | Speedup (Resident) | GPU H2D Transfer (ms) | GPU D2H Transfer (ms) | GPU End-to-End (ms) | Speedup (End-to-End) | Max Abs Discrepancy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$1,000$** | $0.0269$ | $0.1701$ | $0.16\times$ | $0.1189$ | $0.0681$ | $0.3571$ | $0.08\times$ | $0.00 \times 10^0$ |
| **$10,000$** | $0.1826$ | $0.1997$ | $0.91\times$ | $0.1873$ | $0.0883$ | $0.4753$ | $0.38\times$ | $0.00 \times 10^0$ |
| **$100,000$** | $0.9366$ | $0.1631$ | **$5.74\times$** | $0.4321$ | $0.1961$ | $0.7913$ | **$1.18\times$** | $0.00 \times 10^0$ |
| **$1,000,000$** | $8.7494$ | $0.6570$ | **$13.32\times$** | $1.8614$ | $1.1961$ | $3.7145$ | **$2.36\times$** | $0.00 \times 10^0$ |

---

### Table 3: Multi-RHS Primal-Adjoint Solve Comparison ($N = 10,000$)

| Execution Strategy | Description | Wall-Clock Time (ms) | Measured Speedup |
| :--- | :--- | :---: | :---: |
| **Independent Solves** | Re-run SuperLU `spsolve` for $Ku=f$ and $Kz=\nabla J$ independently | $6.6148$ | $1.00\times$ (Baseline) |
| **Factorization Reuse** | Factorize once with `splu(A)`, solve `lu.solve(f)` then `lu.solve(g)` | $3.3730$ | **$1.96\times$** |
| **Multi-RHS Block Solve** | Factorize once, solve block RHS matrix $B = [f \; g]$ simultaneously | $3.2481$ | **$2.04\times$** |

---

## 2. In-Depth Technical Analysis

### 2.1 The Critical Role of GPU Data Residence
The benchmark conclusively confirms the **Law of Data Residence** in scientific computing:
- For a single SpMV at $N = 100,000$, transferring matrix $A$ and vector $x$ from host RAM to GPU VRAM takes $1.0985\text{ ms}$, while transferring the result vector back takes $0.3622\text{ ms}$. The total transfer time ($1.46\text{ ms}$) exceeds the CPU computation time ($0.82\text{ ms}$).
- However, when the matrix is kept in GPU memory across an iterative loop (e.g. 50 iterations of PCG), the transfer cost is paid only once ($1.1\text{ ms}$ amortized over 50 iterations $\approx 0.02\text{ ms}$ per iteration). The resident kernel execution of $0.2343\text{ ms}$ vs CPU's $0.8220\text{ ms}$ results in an **effective speedup of $>3\times$** across the full solve.

### 2.2 Batched Parameter Evaluation Scaling
In linear elasticity parameter propagation, CPU NumPy vectorization is exceptionally fast for interactive workloads:
- For $B \le 10,000$ samples, CPU NumPy evaluates in under $0.2\text{ ms}$. Calling the GPU actually slows down execution ($0.08\times$ to $0.38\times$ speedup) due to PCIe transfer and kernel launch overhead.
- For large-scale Monte Carlo UQ ($B \ge 100,000$ samples), the GPU SIMT architecture dominates: at $1,000,000$ samples, GPU resident compute takes only $0.657\text{ ms}$ vs CPU's $8.749\text{ ms}$ (**$13.32\times$ faster**), and even including full memory transfers, GPU is **$2.36\times$ faster**.

### 2.3 Numerical Parity & Accuracy
In all cases, the numerical agreement between CPU (SciPy/NumPy) and GPU (CuPy/cuSPARSE) was near floating-point machine precision:
- SpMV relative $L_2$ error: $\approx 1.1 \times 10^{-16}$ (machine epsilon $\approx 2.22 \times 10^{-16}$).
- Analytical parameter scaling: Maximum absolute difference $= 0.0$ (bitwise identical).
