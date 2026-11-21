# GDEC GPU Benchmark Protocol: Rigorous End-to-End Performance and Verification Protocol

**Document Reference:** `research/phase5/gpu/GPU_BENCHMARK_PROTOCOL.md`  
**Workstream:** Agent 1 — GPU/CUDA Engineering Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Benchmark Methodology Frozen  

---

## 1. Benchmark Mandate & Scientific Rigor

A central defect identified in scientific software literature is the "isolated kernel speedup fallacy"—reporting $50\times$ speedup on a single SpMV kernel while ignoring host-to-device memory transfer, data reorganization, and convergence degradation, resulting in a total end-to-end simulation that is actually slower than optimized CPU code.

To guarantee scientific defensibility, this protocol defines a standardized, reproducible benchmark suite comparing:
1. **CPU Baseline:** Standard production GDEC direct sparse solver (SuperLU via `spla.factorized` with single-factorization reuse).
2. **CPU Iterative Baseline:** Pure CPU Jacobi-PCG / IC(0)-PCG.
3. **GPU Prototype Backend:** GPU-accelerated Jacobi-PCG and batched assembly via CuPy/cuSPARSE.
4. **Hybrid CPU/GPU Pipeline:** CPU mesh refinement coupled with GPU solve/DWR evaluation.

---

## 2. Standardized Problem Specifications

The benchmark evaluates three standardized test cases across four discretization scales:

### 2.1 Benchmark Geometries and Meshes
- **Problem 1 (Cantilever Shear):** Standard 2D elasticity benchmark ($L = 2.0\text{ m}, H = 0.5\text{ m}, E = 70\text{ GPa}, \nu = 0.33$, parabolic shear traction $P = -1000\text{ N}$ at tip, clamped at $x=0$).
- **Problem 2 (L-Shaped Re-entrant Bracket):** Singularity problem with re-entrant corner generating localized stress concentrations ($[-1, 1]^2 \setminus (0, 1] \times (-1, 0]$).
- **Problem 3 (Batched Monte Carlo / Parameter Sweep):** 50 concurrent variations of material stiffness ($E \in [60, 80]\text{ GPa}$) and load angle ($\theta \in [-15^\circ, +15^\circ]$).

### 2.2 Discretization Scales
1. **Scale S (Small):** $N \in [500, 2,000]$ DOFs (typical coarse initial mesh).
2. **Scale M (Medium):** $N \in [10,000, 50,000]$ DOFs (intermediate adaptive level).
3. **Scale L (Large):** $N \in [100,000, 500,000]$ DOFs (fine mesh).
4. **Scale XL (Extra Large):** $N \in [1,000,000, 5,000,000]$ DOFs (3D or asymptotic scaling regime).

---

## 3. Metrics and Instrumentation

Instrumentation must capture microsecond-resolution timings using non-intrusive CUDA Event timers (`cudaEventRecord`) synchronized across streams, and CPU wall-clock timers (`time.perf_counter_ns`):

| Metric | Measurement Method | Purpose |
|---|---|---|
| **$T_{\text{H2D}}$** | CUDA Event (H2D stream) | Host-to-Device transfer time of mesh coordinates and loads |
| **$T_{\text{asm}}$** | CUDA Event (kernel start/stop) | GPU local element evaluation and global CSR assembly |
| **$T_{\text{prec}}$** | CUDA Event | GPU preconditioner setup time |
| **$T_{\text{solve, primal}}$** | CUDA Event | Time to solve $K u = f$ to relative tolerance $10^{-8}$ |
| **$T_{\text{solve, adjoint}}$** | CUDA Event | Time to solve $K \psi = g$ to relative tolerance $10^{-8}$ |
| **$T_{\text{D2H}}$** | CUDA Event (D2H stream) | Device-to-Host transfer time of QoI and refinement indicators |
| **$T_{\text{e2e}}$** | Host `perf_counter` | **Primary Ground Truth:** Total elapsed wall-clock time |
| **$M_{\text{peak, VRAM}}$** | `cudaMemGetInfo` / Nsight | Peak GPU memory allocation (MB) |
| **$\epsilon_{\text{QoI}}$** | $|J_{\text{gpu}} - J_{\text{cpu}}| / |J_{\text{cpu}}|$ | Numerical agreement of engineering QoI |

---

## 4. Acceptance Criteria for GPU Viability

To justify engineering offloading, the GPU implementation must satisfy:
1. **End-to-End Speedup Gate:**
   - At Scale S ($N < 5,000$): GPU time must not be worse than $2\times$ CPU time (latency penalty bounded).
   - At Scale M ($N \approx 50,000$): GPU end-to-end time must be at least $2.0\times$ faster than CPU direct solver.
   - At Scale L ($N \approx 200,000$): GPU end-to-end time must be at least $5.0\times$ faster than CPU direct solver.
   - At Scale XL ($N \ge 1,000,000$): GPU solve must be at least $10.0\times$ faster than CPU iterative solver.
2. **Batched Sweep Gate:**
   - For 50 concurrent parameter sweeps, GPU batched execution must achieve at least a **$15.0\times$ speedup** over sequential CPU execution.
3. **Numerical Accuracy Gate:**
   - Relative QoI discrepancy between CPU and GPU solutions must be $\le 10^{-10}$.
   - DWR adaptive element refinement sets must share $\ge 95\%$ Jaccard similarity across CPU and GPU estimators.
