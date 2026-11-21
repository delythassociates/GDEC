# GDEC GPU Implementation Roadmap: Staged Development and Minimum Credible POC

**Document Reference:** `research/phase5/gpu/GPU_IMPLEMENTATION_ROADMAP.md`  
**Workstream:** Agent 1 — GPU/CUDA Engineering Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Staged Execution Plan Established  

---

## 1. Staged Roadmap Architecture

GPU implementation is divided into four strictly sequential, gate-controlled stages. No stage may commence until the preceding stage has met its explicit verification and benchmark acceptance criteria:

```
+-----------------------------------------------------------------------------------+
| Stage 5.1: Smallest Credible Proof of Concept (POC)                               |
| - Focus: GPU-Accelerated SpMV and Iterative PCG via CuPy                         |
| - Key Goal: Benchmark isolated vs. end-to-end speedup on fixed cantilever meshes  |
| - Prerequisite: Frozen benchmark protocol (Phase 5.0)                             |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Stage 5.2: End-to-End Data Resident Pipeline                                      |
| - Focus: Dual-stream concurrent primal/adjoint solve + fused GPU QoI evaluation   |
| - Key Goal: Eliminate PCIe ping-pong; achieve >= 2x end-to-end speedup at N=50k    |
| - Prerequisite: Stage 5.1 acceptance gate passed                                  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Stage 5.3: High-Value DWR & Batched Sweep Acceleration                            |
| - Focus: GPU DWR element/facet residual evaluation + 50-case batched Monte Carlo  |
| - Key Goal: Demonstrate >= 15x speedup on parameter sweeps & decision sampling   |
| - Prerequisite: Stage 5.2 acceptance gate passed                                  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Stage 5.4: Production Hardening & Modular Accelerator Backend                     |
| - Focus: Mixed-precision iterative refinement + automated fallback to CPU        |
| - Key Goal: Full packaging in `pyproject.toml` as `gdec[cuda]`; 100% CI pass      |
| - Prerequisite: Stage 5.3 acceptance gate passed                                  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Detailed Stage Breakdown

### Stage 5.1: Smallest Credible Proof of Concept (POC)
- **Objective:** Construct the minimal non-intrusive GPU prototype using CuPy to test sparse matrix-vector multiplication and iterative CG.
- **Scope:**
  - Prototype `CUDACGSolver` using `cupyx.scipy.sparse.csr_matrix` and CuPy linear algebra.
  - Implement CuPy Jacobi preconditioner.
  - Test on frozen 2D cantilever meshes ($N \in [992, 9120, 40320]$ DOFs).
- **Deliverables:**
  - Standalone prototype module `src/gdec/fem/solvers/cuda_iterative.py` (isolated from production paths).
  - Benchmark report comparing CPU SuperLU, CPU PCG, and CuPy PCG.
- **Acceptance Criteria:**
  - Numerical agreement with CPU CG solution: relative error $< 10^{-12}$.
  - Measured PCIe transfer cost and kernel timing breakdown accurately logged.

### Stage 5.2: End-to-End Data Resident Pipeline
- **Objective:** Keep data resident on GPU across primal solve, adjoint solve, and boundary QoI evaluation.
- **Scope:**
  - Fused CuPy boundary integration for displacement/stress QoIs.
  - Asynchronous dual-stream primal and adjoint execution (`cupy.cuda.Stream`).
  - Benchmark total elapsed wall-clock time against SuperLU direct solver with factorization reuse.
- **Acceptance Criteria:**
  - End-to-end speedup of $\ge 2.0\times$ against direct SuperLU at $N \ge 40,000$ DOFs.

### Stage 5.3: High-Value DWR & Batched Sweep Acceleration
- **Objective:** Accelerate the most computationally intensive phases of goal-oriented adaptivity and decision analysis.
- **Scope:**
  - Vectorized GPU element residual and facet traction jump evaluation for DWR.
  - Batched concurrent linear solves across 50 Monte Carlo parameter variations.
- **Acceptance Criteria:**
  - DWR estimation time reduced by $\ge 5.0\times$ compared to CPU skfem/NumPy implementation.
  - 50-case parameter sweep achieves $\ge 15.0\times$ speedup over serial CPU execution.

### Stage 5.4: Production Hardening & Packaging
- **Objective:** Productionize CUDA backend with zero disruption to CPU users.
- **Scope:**
  - Optional dependency specification in `pyproject.toml` (`[project.optional-dependencies] cuda = ["cupy-cuda12x>=13.0.0"]`).
  - Automated detection and graceful fallback in `DeviceManager`.
  - Windows, Linux, and WSL2 packaging verification.
- **Acceptance Criteria:**
  - 100% test pass on systems with CUDA; 100% test pass on systems without CUDA (clean fallback).

---

## 3. Answers to Core GPU Architectural Questions

1. **Which GDEC operations should be accelerated first?**
   *Answer:* Iterative SpMV/PCG linear solves at scale ($N > 20,000$) and batched multi-case parameter sweeps.
2. **Which should remain on CPU?**
   *Answer:* Small-scale direct solves ($N < 20,000$), Incomplete Cholesky factorizations, mesh red-green subdivision topology, and high-level decision logic.
3. **Which CUDA libraries are most appropriate?**
   *Answer:* **CuPy** for high-level sparse linear algebra (providing seamless drop-in parity with SciPy) backed by native **cuSPARSE** and **cuBLAS**.
4. **What hardware is required?**
   *Answer:* Minimum Compute Capability 7.0 (Volta V100), Recommended CC 8.0+ (Ampere/Ada/Hopper) with $\ge 8\text{ GB}$ VRAM.
5. **What is the smallest credible GPU proof of concept?**
   *Answer:* A standalone CuPy-based Conjugate Gradient solver solving the 4,032-DOF and 9,120-DOF cantilever systems, logging PCIe transfer vs. SpMV kernel time.
6. **What benchmark would demonstrate a meaningful advantage?**
   *Answer:* A 50-case parameter sweep on a 50,000-DOF mesh, where GPU stream batching outperforms CPU multiprocessing by $> 15\times$.
7. **What should be deferred?**
   *Answer:* GPU direct sparse LU factorizations, GPU mesh generation/subdivision, and non-NVIDIA GPU backends (HIP/Metal).
8. **Is GPU acceleration a worthwhile strategic investment for GDEC?**
   *Answer:* **YES, WITH CONDITIONS.** For isolated single 2D solves, CPU direct SuperLU is already exceptionally fast ($46\text{ ms}$). GPU acceleration is transformative specifically for **batched parameter sweeps, Monte Carlo uncertainty propagation, 3D continuum problems, and fused DWR estimation pipelines**.
