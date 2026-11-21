# GDEC Existing Component Reuse Matrix

**Document Reference:** `research/phase5/architecture/EXISTING_COMPONENT_REUSE_MATRIX.md`  
**Workstream:** Agent 5 — GDEC Architecture and Integration Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Platform Reuse Audit Established  

---

## 1. Executive Summary

This matrix audits the complete existing GDEC codebase (`src/gdec/`, `docs/`, `verification/`) to evaluate component reusability for the Phase 5 target architecture. We classify every subsystem and candidate component into six explicit maturity tiers:
1. **DIRECTLY REUSABLE (DR):** Implemented, tested, numerically verified, and ready for production reuse without modification.
2. **REUSABLE WITH MODIFICATION (RM):** Core mathematical or software logic exists, but interfaces require adaptation for backend abstraction or decision contracts.
3. **PARTIALLY IMPLEMENTED (PI):** Prototype or partial implementation exists in working tree (e.g. untracked Phase C modules) requiring formal integration.
4. **NEW COMPONENT REQUIRED (NC):** Entirely new subsystem to be implemented in Phase 5.1+.
5. **EXTERNAL DEPENDENCY (ED):** Provided by mature third-party open-source libraries.
6. **RESEARCH NEEDED (RN):** Theoretical formulation required prior to software design.

---

## 2. Component Reuse Audit Table

| Component Name | Existing Location / File | Current Maturity Status | Target Architectural Role | Classification | Prerequisites / Action Needed |
|---|---|---|---|:---:|---|
| **DSL Lexer & Parser** | `src/gdec/language/parser.py` | 42 passing validation tests | Front-end input grammar | **RM** | Add grammar syntax for `contract`, `decision`, `confidence`. |
| **Typed AST & IR** | `src/gdec/language/ir.py` | Pydantic v2 IR schema | Canonical problem representation | **RM** | Extend IR schema to hold Decision Contract fields. |
| **Semantic Analyser** | `src/gdec/language/analyser.py` | Validated type/budget checks | Compile-time semantic validation | **RM** | Validate decision constraints and consequence weights. |
| **Problem Analyser (Refusal Engine)** | `src/gdec/core/analyser.py` | 80/80 passing refusal harness | Pre-solve well-posedness audit | **PI / DR** | Formally integrate untracked user file into main package. |
| **Linear Elasticity Formulation** | `src/gdec/fem/elasticity.py` | Verified 2D plane stress/strain | Continuum physics core | **DR** | Reusable as-is for 2D continuum problems. |
| **SuperLU Direct Solver Engine** | `src/gdec/fem/solvers/direct.py` | Verified factorization reuse | Production default CPU solver | **DR** | Reusable as-is in `CPUBackend`. |
| **Iterative CG/PCG Solver** | `src/gdec/fem/solvers/iterative.py`| Hardened scale-aware checks | Iterative Krylov solver | **DR** | Reusable as-is on CPU; model for GPU-PCG. |
| **AMG Preconditioner** | `src/gdec/fem/solvers/iterative.py`| PyAMG 5.4.1 adjoint sweeps | Multi-level elliptic preconditioning| **DR** | Reusable as-is (optional extra `gdec[amg]`). |
| **Matrix Diagnostics** | `src/gdec/fem/matrix_diagnostics.py`| Scale-invariant symmetry, ARPACK| Pre-solve numerical safety gate | **DR** | Reusable as-is across all backends. |
| **DWR Element Residual Evaluator** | `src/gdec/fem/dwr/element_residual.py`| Verified constant body forces | Spatial interior error estimation | **DR** | Reusable as-is on CPU; candidate for GPU vectorization. |
| **DWR Facet Jump Evaluator** | `src/gdec/fem/dwr/facet_jump.py` | Verified interior jump integrals | Spatial traction jump estimation | **DR** | Reusable as-is on CPU; candidate for GPU vectorization. |
| **DWR Dual Weight Evaluator** | `src/gdec/fem/dwr/dual_weight.py` | Verified boundary masking | Quadratic dual patch enrichment | **DR** | Reusable as-is on CPU. |
| **Safe Refinement Transaction** | `src/gdec/runtime/mesh_evidence.py` | 100% verified budget adherence | Transactional DOF protection | **PI / DR** | Formally track and package `mesh_evidence.py`. |
| **Mesh Infrastructure & Subdivision**| `src/gdec/fem/mesh.py` | Red-green triangular refinement | Geometric hierarchy management | **DR** | Reusable as-is on CPU. |
| **Calibrated Cost Model** | `src/gdec/runtime/cost_model.py` | $R^2 = 0.999$ power-law models | Runtime prediction & VoI stopping | **DR** | Directly provides $\hat{C}_{\text{refine}}(N)$ for VoI engine. |
| **Abstract Compute Backend** | `src/gdec/fem/backend.py` | Does not exist | Decouples CPU and GPU backends | **NC** | Implement `GDECComputeBackend` in Phase 5.1. |
| **CuPy / CUDA Solver Backend** | `src/gdec/fem/backends/cuda.py` | Does not exist | Accelerated SpMV / PCG engine | **NC / ED** | Implement `CUDABackend` wrapping CuPy in Phase 5.1. |
| **Decision Sufficiency Engine (DSE)**| `src/gdec/dse/engine.py` | Does not exist | Margin-to-Error & VoI stopping | **NC** | Implement in Phase 5.2 based on frozen math. |
| **Engineering Evidence Graph (EEG)** | `src/gdec/dse/evidence_graph.py`| Provenance hashes exist in analyser| Cryptographic DAG of evidence | **NC** | Implement DAG node manager in Phase 5.2. |
| **Model Discrepancy GP Estimator** | `src/gdec/dse/model_discrepancy.py`| Does not exist | Physical test vs FEM correction | **RN** | Defer to Phase 5.4+ pending physical test data. |
