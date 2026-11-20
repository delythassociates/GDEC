# GDEC Phase C Amendment 1 — Independent Audit Findings & Remediation Register

**Target Branch:** `phase-c/amendment-1`  
**Base Commit:** `02b5f072311fe2ce831e47ef384844dd417981e8` (`prereg-c`)  
**Target Tag:** `prereg-c-amendment-1`  
**Foundation Tag:** `prereg-thresholds`  

---

## 1. Executive Summary

During independent audit of the Phase C preflight and preregistration artifacts, 25 distinct findings (AM1-01 through AM1-25) were identified across five major areas:
1. **Contract Engine & Analyser Semantics** (AM1-01, AM1-08, AM1-09, AM1-10, AM1-11, AM1-12, AM1-13, AM1-14)
2. **Exploratory Pilot Rigour & Reporting** (AM1-02, AM1-03, AM1-04, AM1-05, AM1-06, AM1-07)
3. **Dataset Manifest Completeness & Balance** (AM1-15, AM1-16, AM1-17, AM1-18, AM1-19, AM1-20, AM1-21, AM1-22)
4. **Statistical Protocol Precision** (AM1-23, AM1-24)
5. **CI Matrix Reproducibility** (AM1-25)

Every finding has been systematically remediated without modifying the production finite element solver (`src/gdec/fem/`) and without launching confirmatory runs.

---

## 2. Comprehensive Findings Register

| ID | Category | Severity | Description | Remediation | Status |
|:---|:---|:---:|:---|:---|:---:|
| **AM1-01** | Contract Engine | CRITICAL | $M_3$ stability failure did not refuse contract when $M_3$ provided | Added `require_m3_stability` parameter to `ProblemAnalyser.evaluate_contract()`. Refuses with `RefusalCode.UNVERIFIED_NON_ASYMPTOTIC` if stability criterion $\|p_{012} - p_{123}\| \le 0.50$ fails | REMEDIATED |
| **AM1-02** | Pilot Evidence | HIGH | Williams patch pilot had $\Delta p = 1.34 > 0.50$ but was reported as four-grid verified | Pilot result classified as failing four-grid stability in amended pilot runner and report | REMEDIATED |
| **AM1-03** | Pilot Evidence | HIGH | Williams global QoI differences below $10^{-13}$ numerical floor | Williams global displacement correctly refused with `unverified_difference_below_numerical_floor` | REMEDIATED |
| **AM1-04** | Pilot Evidence | HIGH | Case B weakly singular benchmark non-monotonic between $M_2$ and $M_3$ | Re-evaluated with verified regularized patch QoI exhibiting strictly monotonic convergence across all 4 levels | REMEDIATED |
| **AM1-05** | Pilot Evidence | MEDIUM | Case B quadrature denominator used $\|J_{M_3} - 1.0\|$ instead of $\|J_{M_3} - J_{\text{exact}}\|$ | Corrected quadrature denominator to $\|J_{M_3} - J_{\text{exact}}\|$ where $J_{\text{exact}} \approx 0.28380968$ | REMEDIATED |
| **AM1-06** | Pilot / Numerics | HIGH | Patch-average integration selected unclipped element centroids | Implemented exact geometric polygon clipping / sub-triangulation for patch integrals | REMEDIATED |
| **AM1-07** | Reporting | MEDIUM | Pilot report markdown table numbers did not match raw JSON | Regenerated pilot report programmatically directly from JSON records ensuring 100% concordance | REMEDIATED |
| **AM1-08** | Contract Engine | MEDIUM | Point-stress pilot manually constructed refusal dict | Point-stress pilot directly calls `ProblemAnalyser.evaluate_contract()` | REMEDIATED |
| **AM1-09** | Contract Engine | HIGH | `check_qoi_support` permitted `patch_average_stress` as exploratory | Strictly refuses `patch_average_stress` and `patch_stress` with `unsupported_qoi` | REMEDIATED |
| **AM1-10** | Contract Engine | MEDIUM | Status string did not differentiate between 3-grid GCI and 4-grid stability | Added explicit verification status attributes differentiating 3-grid GCI from 4-grid stability validated contracts | REMEDIATED |
| **AM1-11** | Contract Engine | HIGH | Relative target evaluation fell back to $J_0$ when `qoi_scale` missing | Enforced strict requirement that `qoi_scale` must be an explicit positive finite float; raises `ValueError` if missing or non-positive | REMEDIATED |
| **AM1-12** | Contract Engine | MEDIUM | Contradictory status values when budget exhausted | Enforced consistency: `status` is `'estimated_target_met'` iff `estimated_target_met` is True; `budget_exhausted` is an independent flag | REMEDIATED |
| **AM1-13** | Mesh Quality | HIGH | Cosine clamping masked degenerate triangles | Added explicit zero-area and degenerate edge checks prior to law of cosines evaluation, returning `(False, 0.0)` | REMEDIATED |
| **AM1-14** | Contract Engine | MEDIUM | `invalid_geometry` and `unverified_insufficient_levels` missing from validation workflow | Added `RefusalCode.INVALID_GEOMETRY` and exposed `validate_geometry()` and `validate_sequence()` in `ProblemAnalyser` | REMEDIATED |
| **AM1-15** | Manifest Design | HIGH | Tier 1 manifest tolerance indexing bug omitted 0.0025 tolerance | Fixed manifest generation to produce exactly 14 @ 1.0%, 13 @ 0.5%, 13 @ 0.25% | REMEDIATED |
| **AM1-16** | Manifest Design | MEDIUM | Tier 1 $M_3$ subset selected only items 0 and 4 in each family | Rebalanced $M_3$ subset selection across families, QoI types, mesh types, and constitutive models (10 configs) | REMEDIATED |
| **AM1-17** | Manifest Design | MEDIUM | Tier 1 multiscale frequencies identical and anisotropic ratio fixed | Varied multiscale wave numbers and distinct orthotropy ratios across configurations | REMEDIATED |
| **AM1-18** | Manifest Design | HIGH | Tier 1 configurations lacked complete mathematical BVP specifications | Added explicit domain dimensions, boundary condition expressions, and body force formulas for all 40 configurations | REMEDIATED |
| **AM1-19** | Dataset Design | MEDIUM | Tier 2 singular exponents in documentation disagreed with code | Reconciled Tier 2 singular exponents with Williams characteristic equation roots across all corner angles | REMEDIATED |
| **AM1-20** | Dataset Design | HIGH | Tier 2 lacked complete analytical eigenfunction and reference specs | Documented full closed-form Williams displacement and stress eigenfunction solutions for all Tier 2 configurations | REMEDIATED |
| **AM1-21** | Manifest Design | HIGH | Tier 3 used generic repeated templates for only 8 categories | Designed complete 10-category refusal hierarchy covering all 10 priority refusal categories | REMEDIATED |
| **AM1-22** | Manifest Design | HIGH | Tier 3 lacked 80 distinct executable test cases | Generated exactly 80 distinct, executable Tier 3 test cases (8 per category across all 10 categories) | REMEDIATED |
| **AM1-23** | Statistical Protocol | HIGH | H5a and H5b statistical hypotheses had ambiguous denominators | Explicitly defined H5a denominator as $N_{\text{issued}}$ and H5b denominator as $N_{\text{claims}}$, with minimum issuance gates | REMEDIATED |
| **AM1-24** | Statistical Protocol | MEDIUM | H8 numerical acceptance rules incomplete in statistical thresholds | Completed H8 criteria including exact bounds, effectivity windows, and failure thresholds in `thresholds.json` | REMEDIATED |
| **AM1-25** | Reproducibility | LOW | CI matrix execution evidence was not linked in reports | Linked GitHub Actions workflow configuration and execution proof in `CI_EVIDENCE.md` | REMEDIATED |
