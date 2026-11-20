# GDEC — PHASE B RECONCILIATION REPORT
## Historical Scientific Determination & Reference Uncertainty Audit

**Repository:** `delythassociates/GDEC`  
**Audit Date:** 2026-11-20  
**Audit Baseline Commit:** `85721d88b2817eb2a132ed04966bd3085ff256e4` (`phase-b1/audit-corrections`)  
**Preregistration Frozen File:** `verification/phase_b_thresholds.json` (frozen at commit `a336cc9`)  
**Preregistration Tag:** `prereg-thresholds` (`8a5237d`, untouched)  
**Historical Determination:**
$$\mathbf{INCOMPLETE\ —\ INSUFFICIENT\ QUALIFYING\ REFERENCE\ SOLUTIONS}$$

---

## 1. Objective of this Reconciliation

This report documents a critical reconciliation between the frozen preregistration requirements established in `verification/phase_b_thresholds.json` and the retrospective evaluations published in Phase B (`PHASE_B_EXPERIMENT_REPORT.md`) and Phase B.1 (`PHASE_B1_AUDIT_REPORT.md`).

This reconciliation is performed **without modifying the frozen threshold file**, **without rewriting historical git history**, **without modifying historical raw experiment outputs**, and **without rerunning the 48 simulations**.

---

## 2. Frozen Reference-Uncertainty Discrepancy

### 2.1 The Pre-Registered Requirement
In `verification/phase_b_thresholds.json` (committed at `a336cc9` before execution):
```json
"reference_uncertainty_threshold_max": 0.0005,
"decision_rules": {
  "PASS": "DWR consistency checks pass; S_DOF >= 1.30 on >= 3 problems at 1% error; geomean S_DOF >= 1.30; I_eff in [0.5, 2.0] for >= 90% runs; reference uncertainty <= 0.05%",
  "PARTIAL": "DWR consistency checks pass; demonstrates advantage on some problems/QoIs but misses broad 3-problem/geomean threshold",
  "FAIL": "DWR consistency checks pass but fails to achieve meaningful DOF savings or reliable effectivity",
  "INCOMPLETE": "DWR consistency checks fail, reference solutions uncertain, or experimental controls violated"
}
```
The frozen limit `0.0005` corresponds to **$0.05\%$** numerical uncertainty.

### 2.2 Actual Reference Solution GCI Uncertainties
The Grid Convergence Index (GCI) uncertainties calculated via Richardson extrapolation in `verification/dwr/reference_solutions.py` are:

| Benchmark Problem | Quantity of Interest (QoI) | Finest DOFs | Apparent Order $p$ | Reported GCI | Frozen Protocol Gate ($\le 0.05\%$) | Compliance Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Cantilever** | Boundary-average vertical displacement | 411,522 | 1.85 | **0.0132%** | $\le 0.05\%$ | **QUALIFIED (VERIFIED)** |
| **Plate with Hole** | Patch-average horizontal displacement | 71,264 | 2.00 | **0.2097%** | $> 0.05\%$ | **DISQUALIFIED (REF_UNCERTAIN)** |
| **Notched Bar** | Patch-average vertical displacement | 207,042 | 2.00 | **1.7582%** | $> 0.05\%$ | **DISQUALIFIED (REF_UNCERTAIN)** |
| **L-Shaped Domain** | Patch-average vertical displacement | 99,330 | 2.00 | **0.2356%** | $> 0.05\%$ | **DISQUALIFIED (REF_UNCERTAIN)** |

### 2.3 The Material Discrepancy
In Phase B and Phase B.1, the evaluation scripts relaxed the reference uncertainty check at the 1.0% error target (in Phase B.1, only Notched Bar with $\text{GCI} = 1.76\% > 1.0\%$ was gated out, while Plate with Hole and L-Shaped Domain were treated as evaluable).

However, under the **strict, original $0.05\%$ requirement** committed in `verification/phase_b_thresholds.json`:
- **Only 1 of 4 benchmark problems (the Cantilever beam) qualifies** as a verified reference solution.
- The Plate with Hole ($\text{GCI} = 0.21\%$), Notched Bar ($\text{GCI} = 1.76\%$), and L-Shaped Domain ($\text{GCI} = 0.24\%$) all exceed the $0.05\%$ maximum threshold by factors of $4.2\times$, $35\times$, and $4.7\times$, respectively.

---

## 3. Scientific Impact and Formal Determination

### 3.1 Why the Previous "FAIL" Determination is Invalid
The primary hypothesis was formulated as:
> At equivalent true QoI error, can goal-oriented DWR achieve at least 30% fewer degrees of freedom than conventional ZZ recovery across multiple engineering problems ($S_{\text{DOF}} \ge 1.30$ on $\ge 3$ of 4 problems)?

To declare a definitive scientific **FAIL** or **PASS** of a multi-problem hypothesis:
- At least 3 of the 4 benchmark problems must possess qualifying, verified reference solutions.
- If 3 of the 4 reference solutions fail the pre-registered uncertainty threshold, the hypothesis **cannot be tested across multiple problems**.
- Declaring `FAIL` on unverified reference solutions commits the same epistemological error as declaring `PASS`: it treats unverified reference numbers as ground truth.

### 3.2 Formal Classification
Per the explicit wording of Section 12 in `verification/phase_b_thresholds.json`:
> `"INCOMPLETE": "DWR consistency checks fail, reference solutions uncertain, or experimental controls violated"`

The correct, defensible historical classification for Phase B is:

$$\mathbf{INCOMPLETE\ —\ INSUFFICIENT\ QUALIFYING\ REFERENCE\ SOLUTIONS}$$

---

## 4. Required Scientific Qualifications

1. **Nature of the Quantities of Interest:**
   - Three of the four tested objectives (`plate_with_hole`, `notched_bar`, `l_shaped`) were **local displacement patch averages** ($L^2$ domain averages of $u_x$ or $u_y$).
   - One objective (`cantilever`) was a **boundary displacement average** ($L^2$ boundary average of $u_y$).
   - **Local stress objectives were never evaluated in Phase B or Phase B.1.** Specifically, notch-tip stress concentration, hole boundary stress concentration, and re-entrant corner stress intensity factors were not evaluated.
   - It is incorrect to describe the tested QoIs as purely global or purely pointwise; they were regularized displacement functionals.

2. **Reference Uncertainty vs. Estimator Effectivity:**
   - For Plate with Hole, Notched Bar, and L-Shaped Domain, the reference GCI uncertainties ($0.21\% - 1.76\%$) were comparable to or larger than the target error levels ($0.5\% - 1.0\%$) being resolved.
   - Consequently, when calculating the effectivity $I_{\text{eff}} = \frac{|\eta_{\text{DWR}}|}{|J_{\text{ref}} - J_h|}$ on refined meshes where $|J_{\text{ref}} - J_h| \approx 0.1\% - 0.5\%$, the denominator was dominated by reference solution truncation error.
   - Therefore, the previously reported **77.3% underestimation frequency is NOT a clean, reference-verified measure of DWR reliability across all problems**. On the single fully verified benchmark (the Cantilever beam), DWR achieved near-ideal effectivity ($I_{\text{eff}} \approx 0.99 - 1.01$) across all 3 initial mesh variants.

3. **Status of Observed DOF Ratios:**
   - On the Cantilever beam (the single qualifying benchmark), DWR achieved a median $S_{\text{DOF}} = 0.838$ and took $6.1\times$ longer in wall-clock time than ZZ recovery.
   - On the three disqualified benchmarks, observed DOF ratios ($S_{\text{DOF}} = 0.886$ for Plate, $1.128$ for Notched Bar, $1.035$ for L-Shaped) must be preserved as **diagnostic observations**, not hypothesis-testing evidence.
   - These diagnostic observations suggest that even if reference solutions were refined further, DWR would face severe challenges in beating ZZ recovery on $P_1$ meshes, but that conclusion cannot be stated as a formally verified multi-problem gate pass or fail under the frozen protocol.
