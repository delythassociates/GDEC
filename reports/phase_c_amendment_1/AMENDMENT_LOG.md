# GDEC Phase C Amendment 1 — Amendment Log

**Repository:** `delythassociates/GDEC`  
**Base Commit:** `02b5f072311fe2ce831e47ef384844dd417981e8` (`prereg-c`)  
**Target Working Branch:** `phase-c/amendment-1`  
**Target Release Tag:** `prereg-c-amendment-1`  
**Foundation Tag:** `prereg-thresholds`  

---

## 1. Context and Motivation

Phase C Preflight established the Problem Analyser, Accuracy Contract engine, preliminary exploratory pilots, and confirmatory preregistration manifests. An independent code and numerical audit identified 25 specific defects (AM1-01 through AM1-25) in contract issuance logic, pilot execution, dataset manifests, and statistical hypothesis definitions.

Phase C Amendment 1 executes a controlled, preregistered remediation of all 25 audit findings. In accordance with strict audit controls:
- Production FEM code (`src/gdec/fem/`) is unmodified (0 lines diff).
- Historical tags (`prereg-thresholds`, `prereg-c`) are preserved untouched.
- Confirmatory execution runs (Tier 1 40 configs, Tier 2 10 configs, Tier 3 80 cases) are NOT launched.
- The outcome is declared as `AMENDMENT READY FOR INDEPENDENT REVIEW`.

---

## 2. Chronological Record of Remediation Changes

### 2.1 Problem Analyser & Contract Engine (`src/gdec/core/analyser.py`)
1. **AM1-01 & AM1-10 (Four-grid stability enforcement):** Added `require_m3_stability: bool = False` to `ProblemAnalyser.evaluate_contract()`. When enabled and level $M_3$ is supplied, stability failure ($|p_{012} - p_{123}| > 0.50$ or non-monotonicity) triggers refusal with `RefusalCode.UNVERIFIED_NON_ASYMPTOTIC` (Priority 9). Status string distinguishes standard 3-grid GCI (`verified_contract_issued`) from validated 4-grid contracts (`four_grid_verified_contract_issued`).
2. **AM1-09 (QoI support strictness):** Modified `check_qoi_support()` to strictly refuse `patch_average_stress` and `patch_stress` with `RefusalCode.UNSUPPORTED_QOI`.
3. **AM1-11 (Relative scale validation):** Enforced that `AccuracyTarget` for relative targets must specify an explicit, positive, finite `qoi_scale`. Missing, zero, or negative values raise `ValueError`.
4. **AM1-12 (Non-contradictory budget exhaustion):** Ensured `status` in `accuracy_meta` strictly matches `estimated_target_met`. If `budget_exhausted` is True, `estimated_target_met` is set to False and `status` is `'estimated_target_not_met'`, with `budget_exhausted` recorded as an independent flag.
5. **AM1-13 (Degenerate element detection):** Added explicit element area ($A \le 10^{-14}$) and edge length checks in `check_mesh_quality()` before law-of-cosines evaluation, returning `(False, 0.0)` for degenerate triangles.
6. **AM1-14 (Validation API completeness):** Added `RefusalCode.INVALID_GEOMETRY` and exposed `validate_geometry()` and `validate_sequence()` in `ProblemAnalyser`.

### 2.2 Exploratory Pilots & Reporting (`verification/phase_c/amendment_1/`, `reports/phase_c_amendment_1/`)
1. **AM1-02 & AM1-03 (Williams pilot reconciliation):** Correctly classified Williams corner notch pilot as failing asymptotic order / stability, and smooth boundary displacement as refused due to difference floor ($< 10^{-13}$ m).
2. **AM1-04 & AM1-06 (Case B domain invariance & monotonicity):** Aligned mesh partitioning to the patch domain boundaries $[0.2, 0.6]^2$, ensuring invariant integration area across all 4 levels ($M_0 \to M_3$) and strictly monotonic convergence ($p_{012} = 1.993, p_{123} = 1.998$).
3. **AM1-05 (Quadrature denominator correction):** Evaluated quadrature error against true error $|J_{M_3} - J_{\text{exact}}|$ ($5.28 \times 10^{-5}$ m), achieving $0.39\% \le 1.0\%$ error ratio on level $M_2$.
4. **AM1-07 (Reporting concordance):** Generated `PILOT_RESULTS.md` directly from `results/phase_c_amendment_1/pilot_results.json`.
5. **AM1-08 (Point stress refusal pipeline):** Executed point stress refusal through `ProblemAnalyser.evaluate_contract()`.

### 2.3 Manifest & Statistical Protocol Design
1. **AM1-15 (Tolerance balance):** Generated exactly 14 @ 1.0%, 13 @ 0.5%, 13 @ 0.25% in Tier 1 manifest.
2. **AM1-16 (Balanced M3 subset):** Selected 10 $M_3$ configurations balanced across QoI types (5 boundary / 5 patch), mesh types (5 structured / 5 perturbed), and constitutive assumptions (5 plane stress / 5 plane strain).
3. **AM1-17 (Parameter diversity):** Varied orthotropy ratios ($E_x/E_y \in [1.5, 4.0]$) in Family 4 and wavenumbers in Family 5.
4. **AM1-18 (Complete BVP specs):** Included explicit domain dimensions, displacement fields, body force formulas, and boundary conditions for all 40 Tier 1 configurations.
5. **AM1-19 & AM1-20 (Tier 2 singular specs):** Reconciled singular exponents with Williams characteristic roots and provided complete analytical eigenfunction specs.
6. **AM1-21 & AM1-22 (Tier 3 refusal cases):** Built exactly 80 distinct executable refusal test cases (8 per category across all 10 priority categories).
7. **AM1-23 (Statistical hypothesis denominators):** Defined $C_1 = N_{\text{covered}} / N_{\text{issued}}$ (conditioned on $N_{\text{issued}} \ge 32$) and $I_1 = N_{\text{met\_and\_true}} / N_{\text{claims}}$ (conditioned on $N_{\text{claims}} \ge 10$).
8. **AM1-24 (H8 numerical acceptance criteria):** Defined complete criteria for Tier 2 performance, reference uncertainty gates, and automated scope narrowing fallback.
9. **AM1-25 (CI linkage):** Documented and linked GitHub Actions CI matrix evidence.
