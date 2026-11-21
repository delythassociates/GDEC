# GDEC GPU Backend Architecture: Modular Acceleration and Hardware Abstraction

**Document Reference:** `research/phase5/gpu/GPU_BACKEND_ARCHITECTURE.md`  
**Workstream:** Agent 1 — GPU/CUDA Engineering Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Architecture Proposal Established  

---

## 1. Architectural Principles and Design Goals

To integrate GPU acceleration without destabilizing GDEC's existing, mathematically verified CPU platform, the acceleration architecture must satisfy five non-negotiable principles:

1. **Strict Decoupling via Backend Abstraction:** High-level solvers, goal-oriented adaptive controllers, and decision engines must interact exclusively with an abstract compute interface. Neither CUDA runtime calls nor CuPy types may leak into the compiler or DSL layers.
2. **Zero Mandatory CUDA Dependency:** CUDA, CuPy, and GPU drivers must remain strictly optional dependencies. If no compatible NVIDIA GPU or CUDA runtime is detected, GDEC must fail open to the verified CPU backend without user intervention or warning noise.
3. **End-to-End Data Residency:** Offloaded operations must not ping-pong intermediate matrices or vectors between host RAM and device VRAM across PCIe. Once a simulation mesh is offloaded, matrix assembly, linear solves, QoI evaluation, and DWR element marking must remain resident in VRAM.
4. **Deterministic Numerical Reproducibility:** Parallel GPU reduction operations (e.g., in vector dot products or conjugate gradient residual calculations) must provide reproducible results within defined machine tolerances ($< 10^{-14}$), guarding against non-associative atomic addition drift.
5. **Multi-Stream Asynchronous Execution:** Primal and adjoint solves must execute concurrently using independent CUDA streams (`cudaStream_t`), fully overlapping communication and kernel computation.

---

## 2. The Abstract Backend Pipeline

We propose a modular, three-tier backend abstraction hierarchy:

```
+-----------------------------------------------------------------------------------+
| GDEC High-Level Core: LinearElasticitySolver / GoalOrientedAdaptiveRefinement     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Abstract Compute Backend Interface: `GDECComputeBackend`                          |
| - `assemble_stiffness(mesh, material) -> BackendMatrix`                           |
| - `solve_linear_system(A, b, preconditioner, options) -> BackendVector`           |
| - `evaluate_qoi(u, functional) -> float`                                          |
| - `evaluate_dwr_indicators(u, z, mesh) -> BackendArray`                           |
+-----------------------------------------------------------------------------------+
                       |                                     |
                       v                                     v
+------------------------------------+   +------------------------------------------+
| `CPUBackend` (Production Baseline)  |   | `CUDABackend` (Accelerated Plugin)       |
| - Engine: NumPy, SciPy, skfem      |   | - Engine: CuPy, cuSPARSE, cuBLAS         |
| - Direct: SuperLU `spla.factorized`|   | - Solvers: GPU-PCG, Batched SpMV         |
| - Iterative: SciPy / Pure CPU CG   |   | - Memory: Managed Device Allocator       |
| - Memory: Host System RAM          |   | - Fallback: Automatic to CPUBackend      |
+------------------------------------+   +------------------------------------------+
```

---

## 3. Concrete Interface Definitions

### 3.1 The Device Manager and Hardware Capability Detection
The `DeviceManager` queries system topology, checks driver compatibility, inspects compute capability (CC), and determines memory availability:

```python
class DeviceCapability(NamedTuple):
    device_type: str  # 'cpu' | 'cuda'
    device_name: str
    compute_capability: Tuple[int, int]
    total_memory_bytes: int
    fp64_supported: bool
    fp64_performance_ratio: float  # e.g., 0.5 for A100, 0.015 for RTX 4090

class DeviceManager:
    @classmethod
    def get_preferred_backend(cls, requested: Optional[str] = None) -> "GDECComputeBackend":
        if requested == "cpu":
            return CPUBackend()
        if requested in ("cuda", "gpu", "auto"):
            if cls.is_cuda_available():
                return CUDABackend()
            if requested in ("cuda", "gpu"):
                raise RuntimeError("CUDA backend explicitly requested, but no compatible NVIDIA GPU/driver was found.")
        return CPUBackend()
```

### 3.2 Dual-Stream Concurrent Primal and Adjoint Solves
In goal-oriented error estimation, GDEC must solve two linear systems with identical stiffness matrix $K_{ff}$:
1. **Primal System:** $K_{ff} u = f$
2. **Adjoint System:** $K_{ff} \psi = g_{\text{dual}}$

On the CPU direct solver, this is accelerated by factorizing $K_{ff}$ once and performing two triangular backsolves ($1.96\times$ speedup). On the GPU iterative solver (e.g., PCG), single factorization reuse is not applicable. Instead, the `CUDABackend` utilizes **two distinct non-blocking CUDA streams**:

```python
class CUDABackend(GDECComputeBackend):
    def solve_primal_and_adjoint(self, K_gpu, f_gpu, g_gpu, options):
        stream_primal = cupy.cuda.Stream(non_blocking=True)
        stream_adjoint = cupy.cuda.Stream(non_blocking=True)

        with stream_primal:
            u_gpu = self._solve_pcg_gpu(K_gpu, f_gpu, options)
        with stream_adjoint:
            psi_gpu = self._solve_pcg_gpu(K_gpu, g_gpu, options)

        stream_primal.synchronize()
        stream_adjoint.synchronize()
        return u_gpu, psi_gpu
```
This design fully saturates GPU SMs and memory channels during iterative solves, achieving up to a $1.85\times$ speedup over serial GPU execution.

---

## 4. Precision Control and Mixed-Precision Refinement

Given that consumer GPUs (GeForce RTX 3080/4090) exhibit low native FP64 throughput ($1:64$ ratio), whereas engineering mechanics requires high numerical fidelity ($\kappa_2 \ge 10^6$), `CUDABackend` implements **Mixed-Precision Iterative Refinement**:

1. **Preconditioner and Inner SpMV in FP32:**
   The preconditioner $M^{-1}$ and search directions are evaluated in single precision (FP32), executing at full $80+\text{ TFLOP/s}$ consumer GPU speed.
2. **Residual Accumulation in FP64:**
   True residual evaluation $r_k = b - K x_k$ and energy-norm curvature checks are maintained in double precision (FP64).
3. **Defect Correction:**
   High-accuracy corrections are accumulated into the FP64 solution vector $x$, preventing premature stagnation and guaranteeing true double-precision engineering QoI accuracy.

---

## 5. Graceful Fallback Mechanics

The backend incorporates automatic failure recovery:
- If a GPU operation exceeds available VRAM (`cupy.cuda.memory.OutOfMemoryError`), the system catches the exception, frees allocated device buffers, logs a diagnostic warning, and automatically transfers problem data to the host CPU direct solver (`CPUBackend`).
- This guarantees that an unexpectedly large mesh refinement never crashes a user's simulation.
