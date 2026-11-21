# GDEC Outstanding Requirements and Blockers Register

**Document Reference:** `research/phase5/legacy/OUTSTANDING_REQUIREMENTS_REGISTER.md`  
**Workstream:** Agent 2 — Legacy Research and Verification Closure  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Blockers Categorized and Action Plans Defined  

---

## 1. Executive Summary

This register catalogs all remaining open items, partial closures, and documentation amendments identified across historical phases. Each item is evaluated for its blocking status relative to future development (Phase 5.1 prototyping and confirmatory benchmarks).

---

## 2. Outstanding Requirements & Blockers Analysis

| ID | Workstream / Domain | Description | Current Status | Blocker For | Action Required for Complete Closure |
|:---:|---|---|:---:|:---:|---|
| **REQ-01** | **DWR Certification Claim** | Historical reports describe DWR as a "certified error bound", conflating asymptotic residual indicators with guaranteed two-sided mathematical bounds. | **AMENDMENT REQUIRED** | Publication & External Audit | Amend `docs/DWR_THEORY_AND_DERIVATION.md` to state that DWR is an asymptotic estimator subject to higher-order remainder terms and local patch heuristics. |
| **REQ-02** | **Confirmatory Benchmarks** | Phase C confirmatory benchmarks on the full Tier 1 / Tier 2 suite were intentionally frozen pending protocol freeze. | **OPEN** | Final v0.2.2 Confirmatory Sign-off | Execute confirmatory runs strictly in accordance with frozen `prereg-c-amendment-3.2` manifest without modifying production code. |
| **REQ-03** | **Multi-Core / MPI Scaling** | GDEC direct solve and assembly operate on a single node; distributed memory parallelization (MPI) is not implemented. | **DEFERRED (Phase 6)** | Massive Distributed Solves | Document single-node shared-memory / GPU scope clearly; do not claim distributed cluster scalability. |
| **REQ-04** | **3D Continuum Mechanics** | Current verified implementation is restricted to 2D plane stress and plane strain. | **DEFERRED (Phase 5.4+)** | 3D Structural Applications | Maintain explicit 2D scope boundary in DSL and solver documentation until 3D tetrahedral/hexahedral elements are verified. |
| **REQ-05** | **Plasticity & Geometric Nonlinearity** | Current verified solver supports linear elasticity. Large deformations and elastoplasticity are unverified. | **DEFERRED (Phase 6)** | Nonlinear Mechanics | Refuse nonlinear constitutive inputs at the compiler and IR boundary. |
| **REQ-06** | **Phase C Code Integration** | `src/gdec/core/analyser.py` and `src/gdec/runtime/mesh_evidence.py` exist in the working tree as untracked user files from Phase C amendments. | **PARTIALLY CLOSED** | Core Platform Integration | Formally integrate and package Phase C analyser and mesh evidence into the primary test suite once Phase 5.0 research is approved. |

---

## 3. Explicit Blocking Declaration

1. **What is genuinely closed?**
   - Phase 4.1 linear solver reliability, scale-aware near-null detection, fail-closed preconditioner contracts, and PyAMG adjoint sweep verification are 100% closed and verified across CI.
   - Phase C mesh topology verification, BVP mathematical equilibrium, and 80-case deterministic refusal are 100% verified.
2. **What still blocks further research?**
   - Nothing blocks Phase 5.0 research. However, **confirmatory benchmark runs must remain frozen** until the benchmark protocol is formally locked.
3. **What can safely be treated as the v0.2.2 baseline?**
   - Commit `b8572d5bb4bbd7f6136d1ffae09fa8510fc99ab0` on branch `audit/v0.2.2-deep-review` represents the verified foundation.
