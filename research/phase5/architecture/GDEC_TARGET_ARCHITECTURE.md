# GDEC Target Platform Architecture: The Engineering Decision Intelligence Platform

**Document Reference:** `research/phase5/architecture/GDEC_TARGET_ARCHITECTURE.md`  
**Workstream:** Agent 5 — GDEC Architecture and Integration Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Target Architecture Specification Established  

---

## 1. Executive Architectural Vision

The target architecture for GDEC unifies its three foundational capabilities into a coherent, layered system:
1. **The Decision Intelligence Layer (DSE):** Governs engineering intent, parses decision contracts, formulates Bayesian risk models, and drives Value-of-Information (VoI) stopping rules.
2. **The Verified Goal-Oriented Computational Mechanics Core:** Executes multi-level finite element analysis, primal and adjoint solves, and Dual-Weighted Residual (DWR) spatial discretization error estimation with transactional budget safeguards.
3. **The Modular Compute Backend Layer:** Provides abstract compute execution across CPU (NumPy/SciPy/SuperLU) and GPU (CuPy/cuSPARSE/CUDA streams) with automated capability detection and graceful fallback.

```
+-----------------------------------------------------------------------------------+
| LAYER 1: USER INTERACTION & DECISION CONTRACT INTERFACE                           |
| - GDEC Declarative DSL & Compiler (`src/gdec/language/`)                          |
| - CLI & Decision Studio Interface (`src/gdec/cli.py`)                             |
| - Decision Contract & QoI Requirement Specification                               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| LAYER 2: DECISION SUFFICIENCY & EVIDENCE ORCHESTRATION (DSE)                      |
| - Decision Sufficiency Engine & Margin-to-Error Calculator                        |
| - Deterministic Refusal & Problem Analyser (`src/gdec/core/analyser.py`)          |
| - Engineering Evidence Graph (EEG) & Cryptographic Provenance DAG                 |
| - Value-of-Information (VoI) Refinement Planner & Stopping Controller             |
| - Transactional DOF & Iteration Budget Controller (`src/gdec/runtime/`)           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| LAYER 3: VERIFIED CONTINUUM MECHANICS & DWR ESTIMATION CORE                       |
| - Linear Elasticity Continuum Formulation (`src/gdec/fem/elasticity.py`)          |
| - Goal-Oriented Dual-Weighted Residual Engine (`src/gdec/fem/dwr/`)               |
| - Primal & Adjoint BVP Solvers (`LinearElasticitySolver`)                         |
| - Matrix Diagnostics & Conditioning Analyzer (`matrix_diagnostics.py`)            |
| - Multi-Level Mesh Topology & Red-Green Subdivision (`mesh.py`)                   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| LAYER 4: MODULAR ACCELERATED COMPUTE BACKENDS                                     |
| - Abstract Compute Interface: `GDECComputeBackend`                                |
|   ├── `CPUBackend` (Production Default: SuperLU 5.3.0, SciPy Sparse, Pure CG)     |
|   └── `CUDABackend` (Accelerated Plugin: CuPy, cuSPARSE, Dual-Stream Solves)      |
| - Hardware Device Manager & Automated Fallback Router                             |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Architectural Subsystems

### 2.1 Subsystem A: Decision Intelligence & Governance
- **`DecisionContractParser`:** Parses high-level decision requirements from the GDEC DSL or structured JSON contracts.
- **`ProblemAnalyser` (Existing & Enhanced):** Performs pre-solve well-posedness audits, inspects re-entrant singularities, validates Dirichlet kinematics, checks 4-grid asymptotic stability ($M_0 - M_3$), and issues deterministic refusal certificates when required.
- **`DecisionSufficiencyEvaluator`:** Evaluates the Margin-to-Error Ratio ($\text{MER}$) combining DWR discretization uncertainty $U_{\text{num}}$ and parameter uncertainty $U_{\text{param}}$. Computes Expected Net Gain (ENG) to govern automated early stopping.
- **`EvidenceGraphManager`:** Tracks mathematical artifact lineage in an immutable DAG with SHA-256 signatures, enforcing selective invalidation and cross-revision evidence inheritance.

### 2.2 Subsystem B: Verified FEM & Error Estimation Engine
- **`LinearElasticitySolver` (Existing):** Assembles and solves primal and adjoint boundary value problems. Enforces strict fail-safe defaults (`caller_certified_spd=False`), scale-aware near-null detection, and fail-closed preconditioner contracts.
- **`DWRErrorEstimator` (Existing):** Evaluates element interior residuals $\eta_K^{\text{elem}}$, facet traction jumps $\eta_F^{\text{jump}}$, and reconstructed dual weights $\psi - \pi_h \psi$.
- **`SafeRefinementTransaction` (Existing):** Guarantees that mesh refinement never commits a mesh exceeding the user's declared hard DOF budget, executing clean transactional rollbacks upon budget exhaustion.

### 2.3 Subsystem C: Modular Backend Abstraction
- **`GDECComputeBackend`:** Abstract Base Class defining standard array, matrix, SpMV, linear solve, and boundary integration primitives.
- **`CPUBackend`:** Concrete implementation wrapping `scipy.sparse`, `skfem`, and SuperLU direct solver.
- **`CUDABackend`:** Concrete implementation wrapping CuPy and cuSPARSE. Implements asynchronous dual-stream primal/adjoint solves, mixed-precision iterative refinement, and data-resident boundary integration.
- **`DeviceManager`:** Probes CUDA drivers, inspects GPU compute capability and VRAM capacity, and transparently routes computational workloads.

---

## 3. Interaction Between DSE and Solver Backends

A critical architectural requirement is that DSE remains completely agnostic to whether computation occurs on CPU or GPU:
1. DSE submits an abstract evaluation request: `backend.solve_primal_and_dual(K, f, g, options)`.
2. The `DeviceManager` inspects problem size:
   - If $N < 20,000$ DOFs, it selects `CPUBackend` (direct SuperLU is faster).
   - If $N \ge 20,000$ DOFs or a batched 50-case sweep is requested, it selects `CUDABackend`.
3. The selected backend computes $u, \psi$ and returns the scalar QoI $J$ and element error indicators $\eta_K$.
4. DSE evaluates decision sufficiency. If $\text{MER} \ge 3.0$, DSE signals completion, bypassing further mesh refinement iterations regardless of remaining compute budget.
