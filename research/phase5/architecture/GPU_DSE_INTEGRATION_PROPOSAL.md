# GDEC GPU and Decision Sufficiency Engine Integration Proposal

**Document Reference:** `research/phase5/architecture/GPU_DSE_INTEGRATION_PROPOSAL.md`  
**Workstream:** Agent 5 — GDEC Architecture and Integration Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Synergistic Integration Proposed  

---

## 1. The Synergistic Coupling of GPU and DSE

The two primary technical thrusts of GDEC Phase 5—GPU acceleration and the Decision Sufficiency Engine (DSE)—are not competing priorities; they are **fundamentally complementary and mutually reinforcing**:

| Capability | Role in Engineering Computation | Structural Contribution to GDEC |
|---|---|---|
| **GPU / CUDA Acceleration** | **Computational Throughput ("How fast we compute")** | Dramatically reduces wall-clock time for batched parameter sweeps, large-scale iterative SpMV, and vectorized DWR residual evaluation. |
| **Decision Sufficiency Engine (DSE)** | **Computational Intelligence ("Why and how much we compute")** | Eliminates unnecessary simulation runs and over-refined meshes by mathematically determining when evidence is sufficient to justify an engineering decision. |

```
                                  ENGINEERING PROBLEM
                                           |
                                           v
                        +-------------------------------------+
                        | Decision Contract & Uncertainty     |
                        +-------------------------------------+
                                           |
                                           v
                        +-------------------------------------+
                        | DSE: Margin-to-Error & VoI Planner  |
                        +-------------------------------------+
                                    |              ^
                     Targeted Workload             | Updated Evidence
                                    v              | & Error Bounds
                        +-------------------------------------+
                        | CUDABackend: Batched Concurrent     |
                        | Dual-Stream Primal + Adjoint Solve  |
                        +-------------------------------------+
                                           |
                         Sufficient Evidence Established?
                                           |
                        +------------------+------------------+
                        |                                     |
                      YES                                    NO
                        v                                     v
         +-----------------------------+       +-----------------------------+
         | HALT: Decision Certificate  |       | Check Budget: Refine or     |
         | (Saves 60-80% Compute)      |       | Deterministic Refusal       |
         +-----------------------------+       +-----------------------------+
```

---

## 2. Key Integration Mechanisms

### 2.1 Concurrent Primal and Adjoint Evaluation via CUDA Streams
DSE relies on Dual-Weighted Residual (DWR) error estimation, which requires solving both the primal system $K u = f$ and the dual system $K \psi = g_{\text{dual}}$.
- **CPU Bottleneck:** On CPU direct solvers, this requires two sequential backsolves; on CPU iterative solvers, this doubles Krylov iterations.
- **GPU Integration:** `CUDABackend` spawns two concurrent, non-blocking CUDA streams (`stream_primal` and `stream_adjoint`). Both linear solves execute concurrently on the GPU, saturating SM occupancy and memory channels simultaneously.

### 2.2 Batched Monte Carlo Parameter Sampling for Bayesian UQ
DSE evaluates decision uncertainty across material stiffness ($E$) and load distributions.
- **GPU Integration:** Instead of launching 50 serial FEM solves, `CUDABackend` evaluates all 50 cases concurrently using batched cuSPARSE and cuBLAS routines. The entire Monte Carlo decision posterior is computed in seconds rather than minutes.

### 2.3 Value-of-Information (VoI) Early Halting of GPU Kernels
- **GPU Limitation:** GPU clusters consume significant electrical power and cloud GPU instances incur high financial cost.
- **DSE Integration:** If the Decision Margin-to-Error Ratio ($\text{MER}$) achieves safety threshold ($\ge 3.0$) on an intermediate mesh level, DSE **immediately halts execution**, avoiding expensive fine-mesh allocations on the GPU and preventing out-of-memory errors.

---

## 3. Data Ownership, Memory Management, and Fallback

1. **Zero-Copy Host Boundaries:**
   Mesh geometry and boundary tags are uploaded to GPU memory at the start of an adaptive level. Once on device, stiffness assembly, linear solves, DWR element indicators, and boundary QoIs are evaluated entirely in GPU VRAM. Only the scalar QoI $J$ and element refinement marker mask are copied back to host RAM across PCIe.
2. **Deterministic Reproducibility:**
   All GPU reduction operations (dot products, vector norms) use fixed-tree binary parallel reductions to guarantee that decision outcomes and stopping certificates are 100% reproducible bit-for-bit across runs.
3. **Transparent CPU Fallback:**
   If a GPU device encounters an `OutOfMemoryError` during fine-mesh evaluation, the system catches the exception, releases device buffers, and automatically reroutes the problem to the host CPU direct solver with an informational diagnostic in the decision certificate.
