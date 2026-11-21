# GDEC Phase 5.1 Next Phase Recommendations & Decisions

**Document ID:** `GDEC-REC-P51-001`
**Date:** 2026-11-22
**Author:** Lead Engineering Research Orchestrator
**Status:** Awaiting Executive Review & Approval (Do NOT Begin Phase 5.2 Automatically)

---

## 1. Workstream-by-Workstream Verdicts & Recommendations

In accordance with Phase 5.1 governance, each prototype has been independently evaluated and assigned a formal engineering verdict:

### 1. CPU ExecutionBackend: **ACCEPT**
- **Evaluation:** Clean, strictly typed Protocol abstraction (`ExecutionBackend`) in `src/gdec/core/backend/`. Preserves SuperLU production default and strict CG SPD contracts. Factorization reuse achieves a **$2.04\times$ speedup** on primal/adjoint solves on CPU.
- **Action for Phase 5.2:** Retain as the permanent reference baseline.

### 2. CUDA Proof-of-Concept: **ACCEPT WITH CONDITIONS**
- **Evaluation:** CuPy backend demonstrated on physical NVIDIA RTX 3050 GPU. Proved that GPU-resident SpMV yields $3.51\times$ speedup at $N = 100,000$, and batched parameter scaling achieves up to $13.32\times$ resident speedup. Verified that PCIe transfer latency makes single SpMV on small meshes slower than CPU.
- **Conditions:**
  1. Do NOT offload single 2D linear solves to GPU if $N < 25,000$.
  2. Implement GPU-resident Conjugate Gradient with custom Jacobi/ILU preconditioner where the matrix remains resident across iterations.
  3. Focus primary GPU roadmap on **Batched Parameter Sweeps and Monte Carlo UQ**.

### 3. Declarative Decision Contract: **ACCEPT**
- **Evaluation:** Pydantic v2 declarative schema in `src/gdec/dse/contract.py` with strict cross-field unit validation, non-positive loss rejection, and full JSON Schema export.
- **Action for Phase 5.2:** Integrate into the GDEC compiler frontend so users can declare contracts natively in GDEC scripts.

### 4. Single-QoI Decision Evaluator: **ACCEPT**
- **Evaluation:** Evaluator in `src/gdec/dse/evaluator.py` implements exact Gaussian expected loss minimization. Strict scientific guardrail separating asymptotic DWR indicators from physical uncertainty verified in unit tests. Deterministic refusal stops unsupported simulations.
- **Action for Phase 5.2:** Connect to the adaptive mesh refinement (AMR) loop to drive Value-of-Information (VoI) stopping.

### 5. Restricted Linear-Elastic Analytical Scaling: **ACCEPT**
- **Evaluation:** Mathematically exact under declared assumptions (homogeneous $E$, fixed geometry, fixed $\nu$, proportional loading, displacement QoI). Validated against independent FEM solves with $< 10^{-14}$ absolute discrepancy. Delivers $1,000,000$ evaluations in $0.65\text{ ms}$ on GPU and $8.7\text{ ms}$ on CPU with **zero additional FEM solves**.
- **Action for Phase 5.2:** Adopt as GDEC's standard linear-elastic fast UQ engine.

### 6. Phase 5.2 Authorisation: **AWAIT EXPLICIT APPROVAL**
- **Recommendation:** **ACCEPT WITH CONDITIONS**. Do NOT automatically begin Phase 5.2. Await executive review and explicit sign-off from the project leadership.

---

## 2. Proposed Phase 5.2 Engineering Milestone

When authorized, **Phase 5.2 (Evidence Graph DAG, Refusal Engine & VoI Controller)** should focus on:
1. **Engineering Evidence Graph:** Content-addressed Directed Acyclic Graph (DAG) with SHA-256 Merkle root hashing tracking provenance from contract to certificate.
2. **Deterministic Refusal Engine:** Formalizing pre-execution and in-execution geometric (inverted elements), kinematic (large strains), and algebraic (matrix ill-conditioning) refusal gates.
3. **Value-of-Information (VoI) Stopping Controller:** Halting adaptive mesh refinement early when the decision outcome is already unequivocal, saving $60\text{--}80\%$ of compute.
4. **GPU-Resident PCG Solver:** Implementing persistent-matrix PCG on CuPy with stream concurrency.
