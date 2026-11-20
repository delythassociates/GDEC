# GDEC Phase C Amendment 2 — Final Amendment Report

**Repository:** `delythassociates/GDEC`  
**Base Commit:** `8c25ff0905a4fc45734c199490ffff1250a980bd` (`prereg-c-amendment-1`)  
**Working Branch:** `phase-c/amendment-2`  
**Target Release Tag:** `prereg-c-amendment-2`  
**Foundation Tag:** `prereg-thresholds` (`8a5237d`, `0126040`)  
**Status:** **`AMENDMENT READY FOR INDEPENDENT REVIEW`**  

---

## 1. Executive Summary

Phase C Amendment 2 resolves all outstanding findings identified in the independent review of `prereg-c-amendment-1`, delivering a mathematically sound, reproducible preregistration baseline:

1. **Tier 1 BVP Integrity (AM2-01):**
   - Corrected Family 1 body force: $f_x = -a(2c_{11} + c_{12}) - c_{33}(a + 2b), f_y = 0$.
   - Derived complete, explicit body force expressions for Family 3 (Gaussian).
   - Redesigned Family 4 as isotropic mixed shear: $u_x = k_x x y + k_y y^2, u_y = -k_y x^2 + k_x x y$, with verified isotropic body forces $f_x = -[2 c_{33} k_y + (c_{12} + c_{33}) k_x], f_y = 2 c_{33} k_y - (c_{12} + c_{33}) k_x$.
   - Verified symbolic equilibrium $\mathbf{f} + \nabla \cdot \boldsymbol{\sigma} = \mathbf{0}$ across all 40 configurations using SymPy.
   - Verified all 40 analytical exact QoI expressions against high-precision numerical quadrature ($< 10^{-11}$).
2. **Tier 3 Refusal System Rebuild (AM2-02):**
   - Generated 80 unique, executable test cases (8 per category across all 10 priority categories).
   - Executed dedicated harness achieving 80/80 (100%) refusal accuracy without preemption.
3. **Budget Exhaustion Semantics (AM2-03):**
   - Decoupled `estimated_target_met` from `budget_exhausted`: an achieved accuracy target is preserved regardless of whether the iteration budget was reached.
4. **Four-Grid Validation Mode (AM2-04):**
   - Exposed explicit `verification_mode` parameter (`three_grid` vs `four_grid`).
   - For all $M_3$-designated configurations, four-grid mode is mandatory and strictly enforces the stability criterion $|p_{012} - p_{123}| \le 0.50$.
5. **Numerical Input Validation (AM2-05):**
   - Hardened validation: finite QoI checks, non-negative finite residual validation, refinement ratio $r = 2$ checks, and scale-independent degenerate area tests.
6. **Quadrature Convergence Audit (AM2-06):**
   - Executed systematic 4-order study (orders 14, 18, 22, 26) on Case B using Duffy tensor Gauss-Legendre quadrature, proving monotonic geometric convergence with error ratio $< 0.36\% \le 1.0\%$.
7. **Tier 2 & Reference Gate (AM2-07):**
   - Reconciled Tier 2 singular exponents with Williams characteristic roots and implemented an evaluable reference uncertainty gate (Priority 10).
8. **Statistical Protocol Clarity (AM2-08):**
   - Hypothesis H5b requires $N_{\text{claims}} \ge 10$, otherwise classified as `INCONCLUSIVE — INSUFFICIENT POSITIVE CLAIMS`.
   - Documented non-IID sampling nature of deterministic benchmark families.
9. **CI & Reproducibility (AM2-09):**
   - Confirmatory test marker `-m "not confirmatory"` added to `pyproject.toml` and workflow, strictly isolating normal CI.

---

## 2. Production FEM Isolation

`git diff --stat 01260409a0e11d8dcf97729ea25a61f20e2a4772 -- src/gdec/fem/` reports:
**0 files changed, 0 insertions, 0 deletions**.
The production FEM solver (`src/gdec/fem/`) remains bit-identical to the verified foundation.

---

## 3. Cryptographic Checksums (SHA-256)

```
095fdd41e6e91f1aa46b841dd3d1aae4a68829fd136036231c7001fda3ff7307  verification/phase_c/amendment_2/tier1_manifest.json
eff54c3bd96d810535210de06d23f18ae7b15b16a0928350f2255cc6f562c344  verification/phase_c/amendment_2/tier2_manifest.json
7d74d3abc4232cf8e491ca213410a33799a3dc438e12e9fdabb780b2257d2cac  verification/phase_c/amendment_2/tier3_manifest.json
261c676633170faea8b29ee69128f9d6ac23cc829ee6ceac9ba5ba2c1f7269cd  verification/phase_c/amendment_2/thresholds.json
e050fa120b81d09ccb62b9170effdbfa22ec97935df1bdab242fe1961ca78375  verification/phase_c/amendment_2/refusal_schema.json
5a228b8101fe2f4c5a3f53d865c360a291ec1bf1173fcc0472f279018e2183c0  verification/phase_c/amendment_2/environment_manifest.json
c8884f351299c5fc3bab42383376ad671865ecb63d73938b66242563500ed1fa  verification/phase_c/amendment_2/findings_register.json
71d214874d98bcc6712ca15c10737f4efb3787baa140936f19f9095537b4d19c  results/phase_c_amendment_2/tier3_harness_results.json
34edb8b9db04a0ff0376ea0200bab54b9e9b82692e69113e28d60a0e60b91c06  results/phase_c_amendment_2/quadrature_study_results.json
```

---

## 4. Verification and Regression Summary

- **Total Test Cases:** **157 passed in 49.3s** (0 failures).
- **Ruff:** 0 errors, 0 warnings.
- **Mypy:** 0 errors across 42 source files.
- **FEM Solver Diff:** 0 lines modified in `src/gdec/fem/`.
- **Historical Tags:** `prereg-thresholds`, `prereg-c`, and `prereg-c-amendment-1` preserved unmodified.
- **Confirmatory Runs:** None launched.
- **Declaration:** **`AMENDMENT READY FOR INDEPENDENT REVIEW`**.
