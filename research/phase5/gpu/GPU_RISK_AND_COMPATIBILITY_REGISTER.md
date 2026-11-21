# GDEC GPU Risk and Compatibility Register

**Document Reference:** `research/phase5/gpu/GPU_RISK_AND_COMPATIBILITY_REGISTER.md`  
**Workstream:** Agent 1 — GPU/CUDA Engineering Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Risk Baselines Established  

---

## 1. Hardware, Environment, and Compatibility Risks

| Risk ID | Category | Description | Likelihood | Impact | Mitigation Strategy |
|:---:|---|---|:---:|:---:|---|
| **R-GPU-01** | **Hardware** | Consumer GPUs (RTX 30xx/40xx) have low FP64 throughput ($1:64$ ratio), risking slow double-precision solves. | High | High | Implement mixed-precision iterative refinement (FP32 preconditioner/SpMV with FP64 residual tracking). |
| **R-GPU-02** | **Memory** | Fine 3D meshes or high element counts exhaust GPU VRAM (`OutOfMemoryError`). | Medium | High | Implement memory quota checking in `DeviceManager`; catch OOM and automatically fall back to host CPU solver. |
| **R-GPU-03** | **PCIe Latency** | Frequent Host-to-Device / Device-to-Host transfers across PCIe eliminate solver speedups on small meshes ($N < 10,000$). | High | High | Enforce minimum DOF crossover threshold ($N \ge 20,000$) before dispatching to GPU; keep data resident across solve and QoI evaluation. |
| **R-GPU-04** | **Packaging** | Installing CUDA Toolkit, drivers, and precompiled CuPy wheels on Windows/Linux creates user friction. | High | Medium | Keep CUDA completely optional (`gdec[cuda]`); distribute pre-built CuPy binary wheels; ensure pure CPU path works with zero CUDA dependencies. |
| **R-GPU-05** | **Numerical Drift** | Parallel floating-point reductions (`atomicAdd`) exhibit non-associative roundoff, causing non-deterministic residual histories. | High | Low | Use deterministic parallel tree reduction algorithms for dot products and energy norm evaluations. |
| **R-GPU-06** | **OS Differences** | Windows WDDM driver introduces display watchdog timeouts (TDR) on long-running kernels ($> 2\text{ s}$). | Medium | Medium | Segment long iterative solver iterations into chunks of 100 iterations with intermediate stream yield; advise TCC mode on dedicated cards. |
| **R-GPU-07** | **Ill-Conditioning** | GPU iterative Krylov solvers fail to converge on ill-conditioned structural systems ($\kappa_2 > 10^7$) where direct SuperLU succeeds. | High | High | Maintain upfront condition number checks; fail closed and route ill-conditioned systems to direct CPU solver. |
| **R-GPU-08** | **Vendor Lock-In** | Exclusive focus on NVIDIA CUDA alienates users with AMD (ROCm), Apple (Metal), or Intel (oneAPI) hardware. | Medium | Low | Restrict CUDA-specific calls to `CUDABackend` behind `GDECComputeBackend` abstraction; evaluate HIP/ROCm in Phase 5.4. |

---

## 2. Risk Mitigation Protocols

1. **Pre-Dispatch Heuristic Filter:**
   Before routing an execution to `CUDABackend`, the solver checks:
   - System size: If $N_{\text{dof}} < 20,000$ and $N_{\text{cases}} == 1$, route to `CPUBackend` (direct solver is faster).
   - Estimated VRAM footprint: If $N_{\text{nz}} \times 16\text{ bytes} > 0.8 \times \text{Available VRAM}$, route to `CPUBackend`.
2. **Deterministic Run Flag:**
   Provide `gdec.config.deterministic = True` which forces deterministic tree reductions and reproducible random seeds.
3. **Automated CPU Fallback Testing:**
   Continuous Integration must run the full test suite with `CUDA_VISIBLE_DEVICES=""` to guarantee that all fallback paths are continuously verified.
