# GDEC Architectural Risk Register

**Document Reference:** `research/phase5/architecture/ARCHITECTURAL_RISK_REGISTER.md`  
**Workstream:** Agent 5 — GDEC Architecture and Integration Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Architectural Risks Identified  

---

## 1. Architectural Risks and Mitigation Strategies

| Risk ID | Category | Description | Severity | Likelihood | Mitigation Strategy |
|:---:|---|---|:---:|:---:|---|
| **R-ARCH-01** | **Backend Coupling** | Leaking CuPy or CUDA types into the high-level compiler, AST, or DSE layer, creating hard dependencies. | High | High | Enforce strict typing barrier at `GDECComputeBackend`. High-level code only handles NumPy arrays and Python primitives. |
| **R-ARCH-02** | **Code Bloat / Premature Scope** | Attempting to implement multi-physics, 3D non-linear mechanics, and full Bayesian GP regression simultaneously. | High | High | Enforce strict phase gates. Phase 5.1 is restricted to 2D linear elasticity and standalone SpMV/PCG GPU prototype. |
| **R-ARCH-03** | **Untracked File Desynchronization** | User untracked files (`src/gdec/core/analyser.py`, `src/gdec/runtime/`) being accidentally overwritten or diverged. | High | Medium | Strictly preserve untracked files during research; create formal integration plan with dedicated tests in Phase 5.1. |
| **R-ARCH-04** | **VoI Premature Termination** | Flawed calibration in the VoI cost model causing DSE to halt refinement prematurely in non-asymptotic mesh regimes. | High | Medium | Enforce mandatory Margin-to-Error check ($\text{MER} \ge 3.0$) as a secondary safety floor that overrides VoI stopping. |
| **R-ARCH-05** | **GPU Latency Dominance** | In small 2D meshes ($N < 10,000$), PCIe transfer overhead makes GPU execution slower than direct SuperLU. | High | High | Implement automatic DOF crossover heuristic: route $N < 20,000$ to CPU direct solver automatically. |
| **R-ARCH-06** | **State Mutation in Evidence DAG** | In-place mutation of evidence nodes corrupting cryptographic SHA-256 hash chains across design iterations. | High | Low | Enforce deep immutability via `types.MappingProxyType` and frozen dataclasses (proven in Phase C AM32-03). |
| **R-ARCH-07** | **Solver Inadmissibility Drift** | Unverified iterative solvers or unsymmetric preconditioners bypassing eligibility checks on GPU backends. | High | Low | Invariant structural checks (finiteness, symmetry, diagonal positivity, preconditioner `is_spd`) remain mandatory on all backends. |
