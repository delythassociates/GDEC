# GDEC Phase C Amendment 2 — Tier 3 Refusal Executability Report

**Manifest:** `verification/phase_c/amendment_2/tier3_manifest.json`  
**Harness:** `verification/phase_c/amendment_2/tier3_harness.py`  
**Execution Raw Output:** `results/phase_c_amendment_2/tier3_harness_results.json`  

---

## 1. System Architecture

The Tier 3 Refusal System ensures that GDEC deterministically refuses to issue unjustified numerical accuracy claims for ill-posed, unsupported, malformed, or unverified computations.

In Amendment 2, Tier 3 was rebuilt to eliminate repeated template inputs. Every one of the 80 cases possesses:
- A unique case identifier (`T3_01` through `T3_80`).
- Meaningful, distinct numerical and geometric inputs.
- Valid functional types and explicit singularity/geometry flags.
- Complete mapping to `ProblemAnalyser.evaluate_contract()`.

---

## 2. Category Breakdown & Results (80/80 Passed)

| Priority | Category Code | Meaning | Cases | Actual Refusal Code | Accuracy |
|:---:|:---|:---|:---:|:---|:---:|
| **1** | `ill_posed_qoi` | Singular point stress at re-entrant corner/notch/crack tip | 8 | `ill_posed_qoi` | 100% |
| **2** | `unsupported_qoi` | Unsupported functionals (point displacement, patch stress, SIF) | 8 | `unsupported_qoi` | 100% |
| **3** | `invalid_geometry` | NaN/Inf coords, zero-area, inverted elements, self-intersections | 8 | `invalid_geometry` | 100% |
| **4** | `mesh_quality_failure` | Minimum triangle interior angle $< 10.0^\circ$ | 8 | `mesh_quality_failure` | 100% |
| **5** | `solver_not_converged` | Linear solver residual exceeds tolerance ($> 10^{-10}$) | 8 | `solver_not_converged` | 100% |
| **6** | `unverified_insufficient_levels` | Fewer than 3 levels, non-standard $r \ne 2.0$, missing $M_3$ | 8 | `unverified_insufficient_levels` | 100% |
| **7** | `unverified_difference_below_numerical_floor` | Grid differences below $10^{-13}$ m numerical precision floor | 8 | `unverified_difference_below_numerical_floor` | 100% |
| **8** | `unverified_order` | Observed order $p_{\text{obs}}$ outside plausibility window $[0.5, 3.5]$ | 8 | `unverified_order` | 100% |
| **9** | `unverified_non_asymptotic` | Non-monotonicity, divergence ($q \le 1$), or $M_3$ order drift | 8 | `unverified_non_asymptotic` | 100% |
| **10** | `reference_uncertain` | Reference solution numerical uncertainty $> 0.05\%$ gate | 8 | `reference_uncertain` | 100% |
| **Total** | — | **All 10 Priority Categories** | **80** | **100% Concordant** | **100%** |

---

## 3. Preemption Prevention

In earlier iterations, tests for lower priorities (e.g. mesh quality or solver convergence) used generic or unsupported functional types, causing them to be preempted by Priority 2 `unsupported_qoi`.
In the amended harness:
- All cases for Priorities 3 through 10 specify valid, supported displacement functionals (`boundary_average_displacement` or `patch_average_displacement`).
- All cases specify valid geometric inputs, ensuring that the intended validation condition is reached and evaluated.
- No false positive passes or preempted evaluations occurred across all 80 executions.
