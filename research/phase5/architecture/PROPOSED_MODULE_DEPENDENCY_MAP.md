# GDEC Proposed Module Dependency Map

**Document Reference:** `research/phase5/architecture/PROPOSED_MODULE_DEPENDENCY_MAP.md`  
**Workstream:** Agent 5 — GDEC Architecture and Integration Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Module Dependency Topology Frozen  

---

## 1. Executive Summary

This document formalizes the package structure, import directions, and dependency boundaries for the Phase 5 target architecture. Circular dependencies are strictly forbidden, and high-level decision layers depend only downward on abstract compute interfaces.

---

## 2. Module Directory Structure

```
src/gdec/
├── __init__.py                     # Package root & version
├── cli.py                          # CLI interface & banner
├── language/                       # Front-end compiler & DSL
│   ├── ast.py                      # Abstract Syntax Tree nodes
│   ├── parser.py                   # Lark/PLY grammar parser
│   ├── ir.py                       # Pydantic typed Intermediate Representation
│   └── analyser.py                 # Semantic compile-time checks
├── dse/                            # Decision Sufficiency Engine (New)
│   ├── contract.py                 # Decision Contract schema & validation
│   ├── engine.py                   # DSE Orchestrator & MER evaluation
│   ├── stopping.py                 # Value-of-Information (VoI) stopping rules
│   └── evidence_graph.py           # Cryptographic Evidence DAG & hashing
├── core/                           # System Governance & Auditing
│   └── analyser.py                 # Problem Analyser & Refusal Engine (Phase C)
├── runtime/                        # Transactional Execution & Budgets
│   ├── cost_model.py               # Calibrated runtime power-law models
│   └── mesh_evidence.py            # Safe Refinement Transaction & GCI evidence
└── fem/                            # Verified Finite Element Engine
    ├── elasticity.py               # 2D Linear Elasticity BVP formulation
    ├── mesh.py                     # Mesh representation & red-green subdivision
    ├── matrix_diagnostics.py       # Scale-invariant symmetry, ARPACK eigensolves
    ├── backend.py                  # Abstract GDECComputeBackend interface (New)
    ├── backends/                   # Concrete Execution Backends
    │   ├── cpu.py                  # CPU Backend (SuperLU direct + SciPy)
    │   └── cuda.py                 # CUDA Backend (CuPy + cuSPARSE) (New)
    ├── dwr/                        # Dual-Weighted Residual Error Estimation
    │   ├── element_residual.py     # Interior element residual evaluator
    │   ├── facet_jump.py           # Facet traction jump evaluator
    │   └── dual_weight.py          # Quadratic patch dual weight evaluator
    └── solvers/                    # Linear Solvers & Preconditioners
        ├── direct.py               # Direct sparse solver wrapper
        └── iterative.py            # CG, PCG, Jacobi, IC(0), AMG Preconditioners
```

---

## 3. Strict Layered Dependency Rules

To prevent architectural regression, module imports must satisfy the strict unidirectional dependency graph:

```
[ language/ (DSL & IR) ]
          |
          v
    [ dse/ (Contracts, VoI, Evidence Graph) ]
          |
          v
    [ core/ (Problem Analyser & Refusal) ]
          |
          v
    [ runtime/ (Cost Models & Safe Transactions) ]
          |
          v
    [ fem/ (Continuum Physics, DWR, Solvers) ]
          |
          v
    [ fem/backend.py (Abstract Compute Interface) ]
         /           \
        v             v
[ fem/backends/cpu.py ]  [ fem/backends/cuda.py ]
```

### Dependency Invariants:
1. `fem/` modules must **NEVER** import from `dse/` or `language/`.
2. `fem/backend.py` must **NEVER** import CuPy or PyCUDA.
3. `fem/backends/cuda.py` may import CuPy, but must be imported dynamically only when CUDA is requested and available.
4. `core/analyser.py` operates as an independent audit gate and does not depend on specific linear solver backends.

---

## 4. Answers to Core Architecture Questions

1. **What architecture should GDEC evolve toward?**
   *Answer:* A 4-layer architecture: User/DSL Interface $\to$ Decision Intelligence (DSE) $\to$ Verified FEM Core $\to$ Modular Compute Backends (CPU/CUDA).
2. **Which existing components should remain unchanged?**
   *Answer:* Continuum elasticity physics (`elasticity.py`), DWR estimators (`dwr/`), matrix diagnostics (`matrix_diagnostics.py`), and SuperLU direct solver (`direct.py`).
3. **Which interfaces should be introduced first?**
   *Answer:* `GDECComputeBackend` (abstract compute layer) and `DecisionContract` schema.
4. **How should GPU and CPU execution coexist?**
   *Answer:* Transparently behind `DeviceManager`. CPU direct SuperLU handles small/medium 2D solves ($N < 20,000$); GPU handles large iterative systems ($N \ge 20,000$), batched multi-case sweeps, and vectorized DWR evaluation.
5. **How should DSE interact with solver backends?**
   *Answer:* DSE requests abstract primal/adjoint evaluations, receives scalar QoIs and error indicators, and evaluates stopping criteria independently of backend hardware.
6. **Which components are prerequisites?**
   *Answer:* `GDECComputeBackend` abstraction is a prerequisite for CUDA prototyping; `DecisionContract` schema is a prerequisite for DSE engine prototyping.
7. **What should be deferred?**
   *Answer:* 3D continuum mechanics, distributed-memory MPI, full Gaussian Process model-form calibration, and non-NVIDIA GPU backends (HIP/Metal).
