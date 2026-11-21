# GPU Benchmark Remediation & Protocol Integrity (Phase 5.1.1)

## 1. Executive Summary

In GDEC Phase 5.1, the GPU benchmark suite contained four major structural and reporting deficiencies identified during independent review:
1. **Invalid 5-Point Laplacian Stencil:** The matrix generator constructed a 1D banded matrix with arbitrary jump bands rather than a true 2D discrete Laplacian on a grid. Consequently, the declared non-zero (NNZ) counts were unreconciled with physical finite difference / finite element discretisations.
2. **Conflated CPU and GPU Metrics:** In the multiple-RHS benchmark, CPU factorization and solve timings were improperly recorded in GPU-labeled columns (`gpu_kernel_event_ms` and `gpu_end_to_end_ms`), misleading readers into believing GPU kernels had executed multiple-RHS solves.
3. **Missing Raw Sample Observations:** Only aggregate mean timings were published without raw repetition timestamps or spread metrics (median, min, max, standard deviation).
4. **Lack of GPU Iterative Solver Benchmarks:** GPU linear solving was not measured with device-resident preconditioning, leaving the actual speedup of CuPy iterative methods unverified.

Phase 5.1.1 comprehensively remediates every one of these issues.

---

## 2. True 2D Kronecker-Sum Grid Construction

The discrete 2D Laplacian operator on an $n_x \times n_y$ uniform tensor-product grid is formally defined via the Kronecker sum of 1D second-difference operators:

$$A = I_y \otimes T_x + T_y \otimes I_x$$

where $T_x \in \mathbb{R}^{n_x \times n_x}$ and $T_y \in \mathbb{R}^{n_y \times n_y}$ are standard 1D tridiagonal matrices with stencil $[-1, 2, -1]$, and $I_x, I_y$ are identity matrices.

### Exact Non-Zero (NNZ) Count Verification:
For an $n \times n$ square grid with $N = n^2$:
- Interior nodes ($(n-2)^2$): 5 entries per row $\implies 5(n-2)^2$
- Boundary edges ($4(n-2)$): 4 entries per row $\implies 16(n-2)$
- Corner nodes ($4$): 3 entries per row $\implies 12$
- **Total NNZ:** $5(n-2)^2 + 16(n-2) + 12 = 5n^2 - 4n$.

| Grid Scale | Grid Dimension ($n \times n$) | System Dimension ($N$) | Theoretical NNZ | Measured CSR NNZ | Discrepancy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Small** | $70 \times 70$ | 4,900 | $5(4900) - 4(70) = 24,220$ | 24,220 | **0 (Exact)** |
| **Medium** | $160 \times 160$ | 25,600 | $5(25600) - 4(160) = 127,360$ | 127,360 | **0 (Exact)** |
| **Large** | $320 \times 320$ | 102,400 | $5(102400) - 4(320) = 510,720$ | 510,720 | **0 (Exact)** |

---

## 3. Honest Timing & Measurement Protocol

1. **CUDA Stream Synchronization:**
   Every host-to-device and device-to-host measurement enforces strict synchronization via `cp.cuda.Stream.null.synchronize()` before timestamps are captured with `time.perf_counter()`. Device-resident kernel executions are recorded using hardware CUDA events (`cp.cuda.Event`).
2. **Clear Metric Demarcation:**
   CPU multiple-RHS factorization reuse and block solves are strictly sequestered in CPU benchmark categories. GPU columns are explicitly marked `N/A (CPU-only)`.
3. **Complete Raw & Summary Data Separation:**
   - Every individual repetition is saved in `research/phase5.1.1/gpu/GPU_BENCHMARK_RAW_SAMPLES.csv`.
   - Aggregate statistics (mean, median, std, min, max) are saved in `research/phase5.1.1/gpu/GPU_BENCHMARK_SUMMARY.csv`.
4. **Verified Relative Residuals:**
   All iterative solver tests compute and report true relative residuals $\|b - Ax\|_2 / \|b\|_2 \le 10^{-6}$.
