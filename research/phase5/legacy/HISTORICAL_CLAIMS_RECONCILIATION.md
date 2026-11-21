# GDEC Historical Claims Reconciliation: Rectification of Technical Statements

**Document Reference:** `research/phase5/legacy/HISTORICAL_CLAIMS_RECONCILIATION.md`  
**Workstream:** Agent 2 — Legacy Research and Verification Closure  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Corrections and Formal Rectifications Documented  

---

## 1. Executive Summary

This document systematically reconciles historical marketing, engineering, and research claims across GDEC v0.2.0, v0.2.1, and early v0.2.2 documentation against verified ground truth. Where historical statements exceeded experimental or mathematical evidence, explicit rectifications are declared.

---

## 2. Reconciled Technical Claims

### 2.1 Claim 1: "Dual-Weighted Residuals Provide Certified Error Bounds"
- **Historical Statement:** Early Phase 3 design documents described GDEC's goal-oriented refinement as providing "certified error bounds on engineering quantities of interest."
- **Ground Truth Audit:** GDEC's DWR implementation reconstructs the dual solution $\psi$ on local patches using quadratic polynomials ($E(\psi) - \pi_h \psi$) and evaluates element/facet residuals. By standard DWR theory (Becker & Rannacher 2001), the error representation identity contains higher-order remainder terms $\mathcal{R} = \mathcal{O}(\|u - u_h\|_E \|\psi - \pi_h \psi\|_E)$ which are neglected in computation. Furthermore, patch reconstruction is heuristic.
- **Rectification:** **AMENDMENT REQUIRED & FORMALIZED**.
  *Corrected Statement:* "GDEC provides an **asymptotic dual-weighted residual error indicator** that quantifies element-wise contributions to QoI error and drives efficient mesh refinement. It does **not** provide guaranteed two-sided mathematical bounds (certified bounds), which would require explicit complementary energy formulations or global hypercircle techniques."

### 2.2 Claim 2: "Goal-Oriented Adaptivity Outperforms Uniform Refinement in Total Compute Time"
- **Historical Statement:** Early benchmarks claimed that adaptive refinement is computationally superior to uniform refinement.
- **Ground Truth Audit:** As demonstrated in the consolidated v0.2.2 audit (`GDEC_v0.2.2_Final_Consolidated_Audit.md`), goal-oriented adaptivity achieves significant **DOF savings** ($1.21\times$ to $2.50\times$ fewer DOFs for the same QoI accuracy). However, because each adaptive step requires assembling the primal system, solving the primal system, assembling the dual system, solving the dual system, calculating element residuals, evaluating facet jumps, performing local patch reconstruction, and executing red-green mesh subdivision, the **wall-clock runtime** of the adaptive loop is $1.2\times - 1.8\times$ higher than solving a single uniform mesh on the 2D cantilever.
- **Rectification:** **RECONCILED**.
  *Corrected Statement:* "GDEC's goal-oriented adaptive refinement provides verified **Degree-of-Freedom (DOF) efficiency** ($2.50\times$ reduction at $1.0\%$ accuracy on the benchmark cantilever). However, **wall-clock computational time superiority is not demonstrated** for single 2D linear solves. Wall-clock advantage requires amortization over non-linear iterations, multi-load cases, 3D discretizations, or GPU acceleration."

### 2.3 Claim 3: "Iterative PCG Surpasses Direct Sparse Solvers at Moderate 2D Mesh Sizes"
- **Historical Statement:** Early solver roadmaps anticipated iterative solvers overtaking direct solvers at $N \approx 5,000$ DOFs in 2D.
- **Ground Truth Audit:** Phase 4 empirical measurements across $N \in [56, 9120]$ DOFs established that SuperLU with single-factorization reuse is **$4.1\times$ to $10.3\times$ faster** than Jacobi-PCG. In 2D, SuperLU factorization scales as $\mathcal{O}(N^{1.31})$, and triangular backsolves take $< 1.85\text{ ms}$ even at $N = 9,120$, whereas Jacobi-PCG requires $> 2,000$ independent Krylov iterations across primal and adjoint solves.
- **Rectification:** **RECONCILED**.
  *Corrected Statement:* "For 2D linear elasticity computations ($N < 50,000$), the direct sparse solver with factorization reuse is decisively faster than unpreconditioned and Jacobi-preconditioned iterative Krylov methods. Iterative methods are maintained as experimental backends and are indicated primarily for 3D continuum mechanics or memory-constrained architectures."

### 2.4 Claim 4: "Meeting Target Accuracy at Iteration 6 (8,328 DOFs, 0.2497% Error)"
- **Historical Statement:** The v0.2.1 release report claimed goal-aware adaptivity satisfied the $\le 0.25\%$ target error at Iteration 6.
- **Ground Truth Audit:** This claim was evaluated against the finite 29,768-DOF reference mesh ($J_3 = -1.907295\text{ mm}$). When re-evaluated against the true continuum extrapolated reference $J_{\infty,\text{Celik}} = -1.90952476\text{ mm}$, the error at Iteration 6 is actually $0.3662\%$ (exceeding the $0.25\%$ threshold). The target was genuinely achieved only at Iteration 7 (17,030 DOFs, $0.1802\%$).
- **Rectification:** **AMENDED & VERIFIED**.
  *Corrected Statement:* "The prior claim of satisfying $0.25\%$ at Iteration 6 was an artifact of referencing a finite mesh. The threshold was first achieved at Iteration 7 (17,030 DOFs). Furthermore, because the margin to threshold ($0.0698\%$) is smaller than the Richardson discretization uncertainty ($\text{GCI} = 0.0983\%$), robustness to reference uncertainty is not conclusively established."

### 2.5 Claim 5: "PyAMG symmetry='symmetric' Independent SPD Proof"
- **Historical Statement:** Phase 4.1.2 documentation implied that configuring PyAMG with `symmetry="symmetric"` guarantees an SPD preconditioner.
- **Ground Truth Audit:** As resolved in Phase 4.1.3 and 4.1.4, setting `symmetry="symmetric"` merely directs PyAMG to employ symmetric coarse-grid Galerkin operators ($A_c = P^T A P$). It does not prevent unsymmetric smoothing (e.g. forward-forward Gauss-Seidel causes a $7.17\%$ asymmetry defect) and does not prove that the input matrix itself is positive-definite.
- **Rectification:** **AMENDED & VERIFIED**.
  *Corrected Statement:* "`AMGPreconditioner.is_spd` indicates configuration admissibility as an SPD operator *for an SPD input matrix*. It requires explicit adjoint smoothing pairs and verified coarse solvers, and does not replace input matrix spectral verification."
