# GDEC Benchmark Evidence Audit: Protocol Integrity and Reproducibility

**Document Reference:** `research/phase5/legacy/BENCHMARK_EVIDENCE_AUDIT.md`  
**Workstream:** Agent 2 — Legacy Research and Verification Closure  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Benchmark Evidence Cataloged and Frozen  

---

## 1. Audit Principles and Integrity Standards

Under the GDEC Evidence Verification Standard v1.0, benchmark claims must satisfy six mandatory criteria to be accepted as verified evidence:
1. **Preregistration:** The benchmark problem, geometry, mesh hierarchy, boundary conditions, acceptance thresholds, and statistical test hypotheses must be frozen prior to data generation.
2. **Deterministic Inputs:** All material constants, mesh coordinates, loads, random seeds (where applicable), and linear solver tolerances must be strictly specified in machine-readable JSON manifests.
3. **Explicit Denominators:** Relative error formulas must explicitly document their normalization denominators, completely avoiding arbitrary floating-point floors or unregularized singular values.
4. **Independent Reference Values:** Reference solutions must be derived from independent analytical solutions (Method of Manufactured Solutions) or verified multi-level Richardson extrapolations ($\text{GCI} < 0.1\%$).
5. **Raw Result Artifacts:** Benchmark runs must emit raw machine-readable JSON results with timestamped SHA-256 signatures, not manually transcribed numbers.
6. **Environment Manifest:** Full hardware, OS, Python version, NumPy, SciPy, and compiler flags must be recorded.

---

## 2. Audit of Existing Benchmark Suites

### 2.1 The Cantilever Elasticity Benchmark (Phases 1 - 4.1)
- **Geometry & BCs:** $L = 2.0\text{ m}, H = 0.5\text{ m}$, parabolic shear traction $P = -1000\text{ N}$ at tip, clamped at $x = 0$.
- **Reference Solution:**
  - Historical Level 3 reference ($N = 29,768$ DOFs): $J_3 = -1.907295\text{ mm}$.
  - Extrapolated Celik continuum reference: $J_{\infty,\text{Celik}} = -1.90952476\text{ mm}$ ($p = 1.898, \text{GCI}_{21} = 0.098\%$).
- **Integrity Status:** **VERIFIED**. Evaluated against $J_{\infty}$, goal-aware adaptivity achieves:
  - $\le 2.0\%$ target error: 1,908 DOFs vs 2,618 DOFs for Uniform ($1.37\times$ reduction).
  - $\le 1.0\%$ target error: 4,034 DOFs vs 10,098 DOFs for Uniform ($2.50\times$ reduction).
  - $\le 0.5\%$ target error: 8,328 DOFs vs 10,098 DOFs for Uniform ($1.21\times$ reduction).
  - $\le 0.25\%$ target error: Target reached at Iteration 7 (17,030 DOFs, error $0.1802\%$). However, because the margin ($0.0698\%$) is smaller than reference GCI ($0.0983\%$), this is formally classified as *"achieved against extrapolated reference; robustness to reference uncertainty not conclusively established."*
- **Computational Cost Truth:** While goal-aware adaptivity achieves up to $2.5\times$ DOF reduction, total wall-clock runtime of the adaptive pipeline (including primal solve, adjoint solve, patch enrichment, and mesh subdivision) is currently $1.2\times - 1.8\times$ higher than uniform refinement. Total computational-cost superiority is **NOT DEMONSTRATED**.

### 2.2 The Linear Solver Scaling Benchmark (Phase 4 / 4.1)
- **Scope:** Direct SuperLU vs. Jacobi-PCG vs. Incomplete Cholesky IC(0) on 2D cantilever meshes ($N \in [56, 9120]$ DOFs).
- **Power-Law Calibrated Regressions:**
  - Direct Sparse (SuperLU with reuse): $T_{\text{direct}} \approx 2.9 \times 10^{-4} \cdot N^{1.31}\text{ ms}$ ($R^2 = 0.9992$).
  - Jacobi-PCG (without reuse): $T_{\text{pcg}} \approx 2.5 \times 10^{-2} \cdot N^{0.98}\text{ ms}$ ($R^2 = 0.9984$).
- **Integrity Status:** **VERIFIED**. Across all measured 2D scales ($N \le 9,120$), direct SuperLU is **$4.1\times$ to $10.3\times$ faster** than Jacobi-PCG. Asymptotic crossover claims are strictly restricted to 3D models and ill-conditioned topologies.

### 2.3 Phase C Verification Suite (Tier 1, Tier 2, Tier 3)
- **Tier 1 (40 Manufactured BVP Cases):**
  - Full BVP verification: 40/40 confirmed in `tier1_bvp_verification_record.json`.
  - Static equilibrium, boundary displacement traces, and corner compatibility independently audited.
- **Tier 3 (80 Refusal Cases):**
  - Refusal verification: 80/80 confirmed in `tier3_harness_results.json`.
  - Correct refusal on point stress singularities, unregularized point displacements, non-positive-definite inputs, non-finite geometry, and incompatible refinement topologies.
- **Integrity Status:** **PREREGISTERED & FROZEN** under tag `prereg-c-amendment-3.2`. Confirmatory evaluation runs remain frozen.
