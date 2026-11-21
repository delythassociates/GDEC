# GDEC Legacy Research and Verification Closure Audit

**Document Reference:** `research/phase5/legacy/LEGACY_VERIFICATION_CLOSURE_AUDIT.md`  
**Workstream:** Agent 2 — Legacy Research and Verification Closure  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Historical Audit and Classification Frozen  

---

## 1. Executive Summary

This report performs a comprehensive, code- and evidence-backed audit across all historical development phases of GDEC—spanning Phase 3 (Goal-Oriented Adaptivity & Dual-Weighted Residuals), Phase 4 (Linear Solvers, Matrix Conditioning, Iterative PCG, and AMG), and the Phase C Verification Amendments (Amendments 1 through 3.2).

Historical claims and verification artifacts are categorized using the strict five-tier classification standard:
- **CLOSED:** Fully supported by implemented code, passing automated tests, mathematical derivation, and reproducible data records.
- **PARTIALLY CLOSED:** Significant mathematical or code implementation exists, but specific verification gaps, reference uncertainties, or benchmark qualifications remain.
- **OPEN:** Formulated requirement or benchmark claim that has not been executed, tested, or verified.
- **SUPERSEDED:** Requirement or architectural approach that was rendered obsolete or replaced by subsequent verified designs.
- **AMENDMENT REQUIRED:** Previous documentation, reports, or claims that contain numerical inaccuracies, overgeneralized conclusions, or unverified claims requiring formal correction.

---

## 2. Detailed Audit Across Development Phases

### 2.1 Phase 3: Goal-Oriented Adaptivity and Dual-Weighted Residuals (DWR)
- **Mathematical Scope:** 2D linear elasticity under plane stress/plane strain. Primal system: $a(u, v) = l(v)$; Adjoint system: $a(w, \psi) = J(w)$. Goal-oriented error representation: $J(u) - J(u_h) \approx \rho(u_h)(\psi - \pi_h \psi)$.
- **Audit Findings:**
  1. *Facet Classification and Boundary Tractions:* In Phase 3.1/3.2, `DualWeightEvaluator` was corrected to classify facets based on actual Dirichlet boundary conditions rather than hardcoded left-boundary assumptions (`AM3-01`). **[CLOSED]**
  2. *Interior vs. Boundary Facets:* Fixed defect where interior facets whose vertices both had constrained DOFs were falsely zeroed out. Boundary facet masking is now restricted strictly to domain exterior boundaries. **[CLOSED]**
  3. *Body-Force Quadrature Contract:* In Phase 3.3 and Phase 3 Closure, `ElementResidualEvaluator` was formally restricted to globally constant body forces $b(x) = (b_x, b_y) = \text{const}$, matching the degree-two exactness of the 3-point interior Gauss quadrature rule against the quadratic reconstructed dual field. Spatially varying body forces are rejected at the API boundary. **[CLOSED]**
  4. *Certified Error Bounds vs. Asymptotic Indicators:* Historical reports occasionally described DWR as a "certified error bound." **[AMENDMENT REQUIRED]**. DWR in GDEC is an *asymptotic dual-weighted residual error estimator* subject to higher-order remainder terms $\mathcal{O}(\|u - u_h\|_E \|\psi - \pi_h \psi\|_E)$ and local patch reconstruction heuristics; it is **not** a guaranteed two-sided mathematical bound (such as an explicit hypercircle or Prager-Synge certified bound).

### 2.2 Phase 4 / 4.1: Linear Solvers, Conditioning, Iterative Solvers, and AMG
- **Solver Reconnaissance:**
  1. Confirmed `scipy.sparse.linalg.factorized` utilizes SuperLU 5.3.0 ($P_r A P_c = L U$), not sparse Cholesky. **[CLOSED]**
  2. Measured single-factorization reuse speedup across primal and adjoint solves: isolated linear solve is $1.96\times - 2.00\times$ faster; total solver pipeline is $1.42\times - 1.65\times$ faster (Amdahl's law damping from non-reusable assembly and condensation). **[CLOSED]**
- **Matrix Diagnostics:**
  1. Symmetry Defect: Restored true scale invariance in `compute_symmetry_defect()` ($\delta_{\text{sym}} = \|K - K^T\|_F / \|K\|_F$), completely eliminating the arbitrary denominator floor $\max(\|K\|_F, \epsilon)$. **[CLOSED]**
  2. ARPACK Algebraic Eigensolve: Corrected Krylov subspace dimension to $ncv = \min(n_{\text{rows}} - 1, \max(4 k, 25))$, stabilizing smallest algebraic eigenvalue (`which="SA"`) and eliminating false-positive null mode jitter on unconstrained structural meshes. **[CLOSED]**
  3. Nonsymmetric Matrix Protection: Bypassed symmetric eigensolvers (`eigsh`/`eigvalsh`) on matrices with $\delta_{\text{sym}} > 10^{-8}$, preserving complex spectrum diagnostics without falsely claiming SPD. **[CLOSED]**
- **Iterative Solvers & Preconditioners (Phase 4.1.2 - 4.1.4):**
  1. Fail-Safe Default: `LinearElasticitySolver.solve()` and `ConjugateGradientSolver.solve()` strictly default to `caller_certified_spd=False`, enforcing upfront scale-aware spectral verification. **[CLOSED]**
  2. CG Safety Gate: Eliminated independent `check_eligibility=False` bypass. Attempting to bypass eligibility without `caller_certified_spd=True` raises `ValueError`. **[CLOSED]**
  3. Structural Invariants: Finiteness, square dimensions, symmetry $\le 10^{-8}$, positive diagonal $K_{ii} > 0$, and preconditioner SPD compatibility are unconditionally enforced for all calls. **[CLOSED]**
  4. PyAMG Smoother & Coarse Mapping: Mapped GDEC `"symmetric_gauss_seidel"` to `("gauss_seidel", {"sweep": "symmetric"})`, enforced forward-pre/backward-post adjoint sweeps for ordinary Gauss-Seidel, normalized `"default"` and `None` to PyAMG's documented default coarse solver (`"pinv"`), and proved complete finite-dimensional operator symmetry ($\delta_{\text{sym}} = 1.63 \times 10^{-16}$) and positive definiteness ($\lambda_{\min} \approx 0.115 > 0$) on $N=100$. **[CLOSED]**

### 2.3 Phase C Verification Amendments (Amendments 1, 2, 3, 3.1, 3.2)
- **M3 Stability and Refusal Behaviour (AM2-04):**
  - Exposed explicit `verification_mode` in `ProblemAnalyser`: `three_grid` vs `four_grid`.
  - For four-grid mode, level $M_3$ ($J_3$) is required. Observed order stability criterion $|p_{012} - p_{123}| \le 0.50$ is strictly evaluated; if unstable, the analyser executes deterministic refusal with reason code `M3_ASYMPTOTIC_INSTABILITY`. **[CLOSED]**
- **Singular-System Pilot Denominators:**
  - In Tier 2 singular pilots, normalization denominators must use analytical continuum stress/displacement scales, not raw unregularized point singularities. **[CLOSED]**
- **Patch-Average Stress vs. Displacement Scope:**
  - GDEC v0.2.2 displacement-only scope: Point stress at re-entrant corners is mathematically divergent in $H^1$ elasticity. Analyser strictly refuses point stress requests (`POINT_STRESS_DIVERGENCE_REFUSAL`), directing users to regularized boundary or patch averages. `patch_average_displacement` is fully supported; `patch_average_stress` is supported via $L^2$ projection. **[CLOSED]**
- **Mesh Topology Verification (AM32-01):**
  - Verified full triangle containment (all 3 child vertices inside parent via barycentric coordinates $w_i \ge -10^{-6}$), 4-child area conservation, and edge multiplicity conformity ($\le 2$, no hanging nodes). Verified classification: `NESTED_VERIFIED`, `CONFORMING_NON_NESTED_VERIFIED`, `UNVERIFIED`, `INVALID`. **[CLOSED]**
- **Deep Immutability of Mesh Evidence (AM32-03):**
  - `MeshLevelEvidence` enforces deep immutability via `frozen=True` and recursive `types.MappingProxyType` freezing of all nested dictionaries. Mutation attempts raise `TypeError`. Canonical SHA-256 hash generation is verified. **[CLOSED]**
- **Tier 1 BVP Exact Formulations (AM2-01, AM32-02):**
  - All 40 BVP configurations in `tier1_manifest.json` have exact analytical solutions satisfying static equilibrium $\mathbf{f} + \nabla \cdot \boldsymbol{\sigma} = \mathbf{0}$, verified isotropic elasticity tensor consistency, and exact analytical QoIs agreeing with quadrature to $< 10^{-11}$. **[CLOSED]**
- **Quadrature Zero-Difference Semantics (AM32-04):**
  - Eliminated unjustified zero-difference plateau acceptance. A zero difference is accepted only when the preceding difference satisfies $\delta_{14,18} \le 10^{-12}$. Tail estimate is strictly documented as an empirical geometric extrapolation. **[CLOSED]**

---

## 3. Comprehensive Item-by-Item Classification Table

| Item ID | Subject / Requirement | Historical Origin | Status | Evidence / Implementation Reference |
|:---:|---|:---:|:---:|---|
| **LEG-01** | M3 Stability & Refusal Behaviour | Phase C AM2-04 | **CLOSED** | `src/gdec/core/analyser.py:931-956`, `tests/test_phase_c_amendment_2.py` |
| **LEG-02** | Singular Pilot Denominators | Phase C Tier 2 | **CLOSED** | Williams characteristic roots normalization in `tier2_manifest.json` |
| **LEG-03** | Fixed Physical Patch Integration | Phase C AM32-02 | **CLOSED** | Analytical domain integration in `verify_tier1_bvps.py` |
| **LEG-04** | Raw Data & Report Reconciliation | Phase C AM32-04 | **CLOSED** | Markdown reports generated directly from canonical JSON records |
| **LEG-05** | Unsupported Patch-Average Stress | Phase C AM2-02 | **CLOSED** | Deterministic refusal in `ProblemAnalyser.validate_qoi_request()` |
| **LEG-06** | Tier 1 Tolerance Stratification | Phase C AM2-01 | **CLOSED** | Stratified $L^2$ displacement ($10^{-6}$), $H^1$ semi-norm ($10^{-5}$), Energy ($10^{-5}$) |
| **LEG-07** | Complete Tier 1 BVP Specs | Phase C AM32-02 | **CLOSED** | 40/40 configurations verified in `tier1_bvp_verification_record.json` |
| **LEG-08** | Manifest-Driven Tier 3 Refusal Cases | Phase C AM2-02 | **CLOSED** | 80/80 refusal harness passing in `tier3_harness_results.json` |
| **LEG-09** | Hypotheses H5a, H5b, H8 Thresholds | Phase C AM2-08 | **CLOSED** | Frozen in `verification/phase_c/amendment_2/thresholds.json` |
| **LEG-10** | External CI Evidence | Phase 4 / CI | **CLOSED** | GitHub Actions matrix passing on Python 3.10, 3.11, 3.12 (`44938325148`) |
| **LEG-11** | Benchmark Preregistration Protocol | Phase C / AM32 | **CLOSED** | Preregistration tags frozen (`prereg-c-amendment-3.2`) |
| **LEG-12** | Certified Error Bound Claim | Phase 3 DWR | **AMENDMENT REQUIRED** | DWR must be documented as asymptotic residual estimator, not certified bound |
| **LEG-13** | SuperLU Direct Solver Dominance | Phase 4 Benchmarks | **CLOSED** | Reconciled in `docs/SOLVER_PERFORMANCE_BENCHMARK.md` |
| **LEG-14** | CG Safety Gate & Invariant Checks | Phase 4.1.3 / 4.1.4| **CLOSED** | `src/gdec/fem/solvers/iterative.py:440-475`, `tests/test_iterative_solvers.py` |
| **LEG-15** | PyAMG Adjoint Sweeps & 'pinv' | Phase 4.1.4 | **CLOSED** | Verified complete operator spectrum on $N=100$ discrete Laplacian |
