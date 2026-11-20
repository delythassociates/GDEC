# GDEC Phase C Amendment 1 — Final Amendment Report

**Repository:** `delythassociates/GDEC`  
**Working Branch:** `phase-c/amendment-1`  
**Base Commit:** `02b5f072311fe2ce831e47ef384844dd417981e8` (`prereg-c`)  
**Target Release Tag:** `prereg-c-amendment-1`  
**Foundation Tag:** `prereg-thresholds` (`8a5237d`)  
**Status:** **AMENDMENT READY FOR INDEPENDENT REVIEW**  

---

## 1. Executive Summary

Phase C Amendment 1 resolves all 25 independent audit findings (AM1-01 through AM1-25) identified in the Phase C preflight, Problem Analyser, exploratory pilots, and confirmatory preregistration manifests.

The remediation has been completed under strict audit discipline:
1. **0 Lines of Code Modified in Production FEM:** `src/gdec/fem/` remains bit-identical to the verified foundation commit `01260409a0e11d8dcf97729ea25a61f20e2a4772`.
2. **Historical Integrity Preserved:** Tags `prereg-thresholds` and `prereg-c` remain completely untouched. Raw results from Phase B (`results/phase_b/`), Phase B.1 (`results/phase_b1/`), and Phase C (`results/phase_c/`) are intact.
3. **No Confirmatory Runs Launched:** Confirmatory 40-configuration Tier 1, 10-configuration Tier 2, and 80-case Tier 3 runs were NOT executed. All exploratory pilots remain properly isolated in `verification/phase_c/amendment_1/` and `results/phase_c_amendment_1/`.
4. **Complete Manifest Concordance:** All manifests have been regenerated with exact required counts, balanced distributions, and unambiguous statistical denominators.

---

## 2. Summary of Remediated Audit Findings

| ID | Description | Severity | Remediation Summary |
|:---|:---|:---:|:---|
| **AM1-01** | $M_3$ stability failure did not refuse contract | CRITICAL | Added `require_m3_stability` parameter to `ProblemAnalyser.evaluate_contract()`. Refuses with `RefusalCode.UNVERIFIED_NON_ASYMPTOTIC` if $|p_{012}-p_{123}| > 0.50$ or non-monotonic. |
| **AM1-02** | Williams patch pilot classified as 4-grid verified | HIGH | Correctly classified as failing four-grid stability in amended pilot runner and reports. |
| **AM1-03** | Williams global QoI differences below $10^{-13}$ floor | HIGH | Strictly refused with `RefusalCode.UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR` (Priority 7). |
| **AM1-04** | Case B weakly singular benchmark non-monotonic | HIGH | Evaluated on aligned mesh guaranteeing invariant domain area and monotonic convergence ($p_{012}=1.993, p_{123}=1.998$). |
| **AM1-05** | Case B quadrature denominator used $|J_{M_3} - 1.0|$ | MEDIUM | Corrected denominator to $|J_{M_3} - J_{\text{exact}}|$, passing the $1.0\%$ quadrature error gate. |
| **AM1-06** | Centroid patch selection varied domain area | HIGH | Replaced with domain-aligned mesh partitioning preserving exact area across all refinements. |
| **AM1-07** | Markdown table discrepancies with JSON | MEDIUM | Regenerated report programmatically directly from `pilot_results.json` (100% concordance). |
| **AM1-08** | Point-stress pilot bypassed contract engine | MEDIUM | Point-stress pilot executes directly through `ProblemAnalyser.evaluate_contract()`. |
| **AM1-09** | `check_qoi_support` permitted `patch_average_stress` | HIGH | Modified to strictly refuse `patch_average_stress` and `patch_stress` with `RefusalCode.UNSUPPORTED_QOI`. |
| **AM1-10** | 3-grid GCI vs 4-grid stability not decoupled in status | MEDIUM | Status string distinguishes standard 3-grid (`verified_contract_issued`) from 4-grid (`four_grid_verified_contract_issued`). |
| **AM1-11** | Relative target evaluation fell back without `qoi_scale` | HIGH | Enforced strict requirement: `qoi_scale` must be an explicit positive finite float; raises `ValueError` if missing or non-positive. |
| **AM1-12** | Contradictory accuracy statuses on budget exhaustion | MEDIUM | Enforced consistency: `status` is `'estimated_target_met'` iff `estimated_target_met` is True; `budget_exhausted` is a separate flag. |
| **AM1-13** | Law of cosines clamping masked degenerate triangles | HIGH | Added explicit zero-area and degenerate edge checks prior to law of cosines, returning `(False, 0.0)`. |
| **AM1-14** | `invalid_geometry` missing from refusal workflow | MEDIUM | Added `RefusalCode.INVALID_GEOMETRY` and exposed `validate_geometry()` and `validate_sequence()` in `ProblemAnalyser`. |
| **AM1-15** | Tier 1 manifest tolerance indexing omitted 0.0025 | HIGH | Corrected manifest to produce exactly 14 @ 1.0%, 13 @ 0.5%, 13 @ 0.25%. |
| **AM1-16** | Tier 1 $M_3$ subset selected only items 0 and 4 | MEDIUM | Rebalanced $M_3$ subset across families, QoIs, meshes, and constitutive models (10 configs). |
| **AM1-17** | Lack of parameter diversity in multiscale & anisotropic | MEDIUM | Varied orthotropy ratios ($E_x/E_y \in [1.5, 4.0]$) and multiscale wavenumbers across all configs. |
| **AM1-18** | Tier 1 lacked complete analytical BVP definitions | HIGH | Included explicit domain dimensions, boundary expressions, and body forces for all 40 configurations. |
| **AM1-19** | Tier 2 singular exponents in docs disagreed with code | MEDIUM | Reconciled singular exponents with Williams characteristic roots across all corner angles. |
| **AM1-20** | Tier 2 lacked analytical eigenfunction reference specs | HIGH | Documented full closed-form Williams displacement and stress eigenfunction solutions. |
| **AM1-21** | Tier 3 used generic repeated templates for 8 categories | HIGH | Built complete 10-category priority refusal hierarchy covering all 10 priority categories. |
| **AM1-22** | Tier 3 lacked 80 distinct executable test cases | HIGH | Generated exactly 80 distinct, executable Tier 3 test cases (8 per category across all 10 categories). |
| **AM1-23** | H5a/H5b statistical denominators were ambiguous | HIGH | Explicitly defined H5a as $C_1 = N_{\text{covered}} / N_{\text{issued}}$ and H5b as $I_1 = N_{\text{met\_and\_true}} / N_{\text{claims}}$. |
| **AM1-24** | H8 numerical acceptance rules incomplete | MEDIUM | Completed H8 criteria including exact bounds, effectivity windows, and failure thresholds. |
| **AM1-25** | CI matrix execution evidence was unlinked | LOW | Linked GitHub Actions workflow configuration and execution proof in `CI_EVIDENCE.md`. |

---

## 3. SHA-256 Checksums of Amended Manifest Artifacts

```
388c47ac2c056c38a2582bad177613bc70d417bd12a6b1bad4ccc5908b8983ab  verification/phase_c/amendment_1/tier1_manifest.json
13d2b06f040d7020650066e75e4b91127275c371742a8d6e91ff56fa5cd30f56  verification/phase_c/amendment_1/tier2_manifest.json
a861dd9844a8d7a5639b823a5db4fdb3a13952aaed457c74d03c6c1d11db2373  verification/phase_c/amendment_1/tier3_manifest.json
369d02825455d273e0af2e20945f8303f9d439b3f1f95069bef2220053e8a7a5  verification/phase_c/amendment_1/thresholds.json
908aca8d3992396a2e3ca4eef90019bdc0fe710fb5c5f8179cbb2f8c1e481032  verification/phase_c/amendment_1/refusal_schema.json
fef9f083143663378e71a535fdd11fd1856d1f54d356d62eaf46af9f4fd916f8  verification/phase_c/amendment_1/environment_manifest.json
6750d4baa0a48ddea8f88082032f5a5ff263f42e546280a262f6a371160fc4af  verification/phase_c/amendment_1/findings_register.json
4d7c9b56d220c2a695f74ccb7b6b71780547cbb556d630928073c417a5e2ba9d  results/phase_c_amendment_1/pilot_results.json
```

---

## 4. Verification and Regression Summary

- **Total Test Cases:** 150 passed (Phase A2 regression 49 tests, Phase B.1.1 accounting 3 tests, DWR consistency/mutations 27 tests, Problem Analyser 21 tests, compiler/runtime/FEM 50 tests).
- **Ruff Code Quality:** 0 errors, 0 warnings.
- **Mypy Static Typing:** 0 errors.
- **FEM Solver Diff:** Exactly 0 lines modified in `src/gdec/fem/`.
- **Declaration:** **AMENDMENT READY FOR INDEPENDENT REVIEW**.
