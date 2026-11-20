# GDEC — PHASE C PREREGISTRATION
## Confirmatory Experimental Protocol, Numerical Verification Contract & Refusal Architecture

**Repository:** `delythassociates/GDEC`  
**Protocol Classification:** `FROZEN_CONFIRMATORY_PROTOCOL`  
**Preregistration Tag:** `prereg-c`  
**Date Frozen:** 2026-11-20  
**Code Baseline Commit:** `85721d88b2817eb2a132ed04966bd3085ff256e4`  
**Foundation Commit:** `01260409a0e11d8dcf97729ea25a61f20e2a4772`  
**Historical Preregistration:** `prereg-thresholds` (`8a5237d`, untouched)  
**Machine-Readable Specification:** `verification/phase_c/thresholds.json`

---

## 1. Central Research Question

> **Can GDEC automatically produce useful, empirically reliable estimates of spatial discretisation uncertainty for supported engineering quantities of interest, while correctly identifying and refusing computations whose convergence evidence is inadequate?**

This protocol governs the confirmatory evaluation of GDEC's spatial discretisation verification contract.

---

## 2. Accuracy Contract Formulation & Parameters

For a supported engineering quantity of interest $J$, GDEC computes:
$$J_0 \pm U_0$$
where $U_0$ is the **estimated spatial discretisation uncertainty** derived from a 3-grid nested uniform refinement sequence $M_0 \to M_1 \to M_2$ ($r = 2$):

$$U_0 = F_s |J_0 - J_1| \frac{2^{p_{\text{used}}}}{2^{p_{\text{used}}} - 1}$$

### Pre-Registered Parameters
- **Refinement Ratio:** $r = 2.0$ (conforming 1-to-4 triangle bisection).
- **Safety Factor:** $F_s = 1.25$.
- **Observed Order:** $p_{\text{obs}} = \frac{\ln(|J_0 - J_1| / |J_1 - J_2|)}{\ln 2}$.
- **Observed Order Plausibility Window:** $0.50 \le p_{\text{obs}} \le 3.50$.
- **Order Cap:** $p_{\text{cap}} = 2.00$ ($p_{\text{used}} = \min(p_{\text{obs}}, 2.00)$).
- **Numerical Difference Floor:** $E_{\text{floor}} = 1.0 \times 10^{-13}$ m.
- **Mesh Quality Threshold:** Minimum interior triangle angle $\theta_{\min} \ge 10.0^\circ$.
- **Solver Relative Residual Bound:** $\frac{\|r\|}{\|f\|} \le 1.0 \times 10^{-10}$.
- **Four-Grid M3 Stability Bound:** $|p_{012} - p_{123}| \le 0.50$.

---

## 3. Pre-Registered Confirmatory Hypotheses

### H5a — Empirical Uncertainty Coverage
- **Formula:** For all Tier 1 configurations where GDEC issues $U_0$, require:
  $$E_{\text{true}} = |J_0 - J_{\text{exact}}| \le U_0$$
- **Primary Threshold:** $\ge 90\%$ of issued estimates ($\mathbf{36 / 40\text{ minimum covered}}$).
- **Family Floor:** No individual manufactured family may have empirical coverage below $80\%$ ($4 / 5$ or $7 / 8$).
- **Statistical Interpretation:** Evaluated with two-sided 95% Clopper–Pearson confidence intervals. This empirical acceptance gate does not establish with 95% confidence that the population coverage is $\ge 90\%$.

### H5b — Claim Integrity
- **Formula:** Among configurations reporting `estimated_target_met`, require $E_{\text{true}} \le \text{tol}$ in $\ge 90\%$ of cases.

### H6a — Estimate Availability
- **Formula:** At least $80\%$ ($32 / 40$) of eligible Tier 1 configurations must receive a valid uncertainty estimate (not refused).

### H6b — Estimate Sharpness
- **Formula:** For cases where $E_{\text{true}} > E_{\text{floor}}$, $R_U = \frac{U_0}{E_{\text{true}}}$.
- **Criteria:** $\operatorname{median}(R_U) \le 3.0$ and $P_{90}(R_U) \le 10.0$.

### H7 — Refusal Correctness
- **Formula:** $100\%$ (64 of 64) of Tier 3 refusal cases must return the exact intended refusal status.
- **Strict Prohibition:** Zero Tier 3 refusal cases may return `estimated_target_met`.

### H8 — Tier 2 Difficult/Singular Performance
- Evaluated on 10 difficult/singular elasticity benchmarks. If Tier 2 coverage drops below $80\%$, the contract scope will be explicitly restricted to **SMOOTH DISPLACEMENT QOIS ONLY**.

---

## 4. Deterministic Refusal Hierarchy

When multiple anomalies exist, GDEC diagnoses and reports according to strict deterministic priority:
1. `ill_posed_qoi`: Mathematically divergent or undefined functional (e.g. singular corner point stress).
2. `unsupported_qoi`: Functional outside supported H1 setting (e.g. unregularized point displacement).
3. `invalid_geometry`: Degenerate or intersecting boundaries.
4. `mesh_quality_failure`: Minimum triangle angle $< 10.0^\circ$.
5. `solver_not_converged`: Relative linear solver residual $> 1.0 \times 10^{-10}$.
6. `unverified_insufficient_levels`: Less than 3 valid nested mesh levels available.
7. `unverified_difference_below_numerical_floor`: $|d_{01}| \le 10^{-13}$ or $|d_{12}| \le 10^{-13}$.
8. `unverified_order`: Observed order $p_{\text{obs}} < 0.5$ or $p_{\text{obs}} > 3.5$.
9. `unverified_non_asymptotic`: Non-monotonic difference sequence ($d_{01} d_{12} \le 0$) or diverging mesh ($q \le 1.0$).
10. `budget_exhausted`: Refinement resource budget reached before target tolerance attained.

---

## 5. Confirmatory Datasets

- **Tier 1 Manifest:** `verification/phase_c/datasets/tier1_manifest.json` (40 independent smooth configurations).
- **Tier 2 Manifest:** `verification/phase_c/datasets/tier2_manifest.json` (10 singular/difficult benchmarks).
- **Tier 3 Manifest:** `verification/phase_c/datasets/tier3_refusal_manifest.json` (64 refusal test cases).

---

## 6. Execution Stop Condition

Upon freezing and tagging this protocol as `prereg-c`:
**EXECUTION IS HALTED.**  
No Tier 1, Tier 2, or Tier 3 confirmatory runs are executed within this task. Confirmatory execution requires a subsequent independent command.
