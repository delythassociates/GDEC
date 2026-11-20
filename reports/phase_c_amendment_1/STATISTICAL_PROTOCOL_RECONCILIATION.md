# GDEC Phase C Amendment 1 — Statistical Protocol Reconciliation

**Source Artifact:** `verification/phase_c/amendment_1/thresholds.json`  
**Focus:** Hypothesis Denominator Disambiguation and Numerical Gate Completeness (AM1-23, AM1-24).

---

## 1. Disambiguation of Hypothesis Denominators (AM1-23)

### 1.1 Hypothesis H5a: Empirical Uncertainty Coverage
- **Original Ambiguity:** It was unclear whether the 90% coverage target ($\ge 36 / 40$) was evaluated over all 40 Tier 1 configurations or only over configurations where an uncertainty estimate was issued. If evaluated over 40 while availability $A_1 \ge 0.80$ allows up to 8 valid refusals, H5a could fail despite 100% of issued estimates covering the true error.
- **Amended Formulation:**
  Coverage $C_1$ is evaluated strictly over **issued contracts** ($N_{\text{issued}}$):
  $$C_1 = \frac{N_{\text{covered}}}{N_{\text{issued}}} \ge 0.90$$
  - Conditioned on minimum availability: $A_1 = \frac{N_{\text{issued}}}{40} \ge 0.80 \implies N_{\text{issued}} \ge 32$.
  - Per-family floor: for any family with $N_{\text{issued, fam}} \ge 6$, the family coverage must satisfy $C_{1, \text{fam}} \ge 0.80$.
  - Statistical interval: Two-sided 95% Clopper-Pearson exact binomial confidence interval reported alongside point estimate.

### 1.2 Hypothesis H5b: Accuracy Claim Integrity
- **Original Ambiguity:** Evaluated without a specified minimum sample of positive claims.
- **Amended Formulation:**
  Integrity $I_1$ is evaluated strictly over configurations reporting `estimated_target_met` ($N_{\text{claims}}$):
  $$I_1 = \frac{N_{\text{met\_and\_true}}}{N_{\text{claims}}} \ge 0.90$$
  - Minimum qualification threshold: $N_{\text{claims}} \ge 10$.
  - If $N_{\text{claims}} < 10$, H5b is evaluated conditionally and flagged as having limited statistical power.

### 1.3 Hypothesis H7: Deterministic Refusal Accuracy
- Evaluated over all 80 Tier 3 refusal cases:
  $$R_7 = \frac{N_{\text{correct\_refusals}}}{80} = 1.00 \quad (100\%)$$
  Zero false positives permitted (`estimated_target_met` or `verified_contract_issued` strictly forbidden on Tier 3 cases).

---

## 2. Tier 2 Performance and Numerical Acceptance Gates (AM1-24)

For Tier 2 difficult and singular configurations:
1. **Total Configurations:** 10 (6 Williams corner notch/crack cases, 4 weakly-singular manufactured cases).
2. **Reference Solution Uncertainty Gate:** $\delta_{\text{ref}} \le 0.05\%$ ($0.0005$).
3. **Quadrature Error Gate:** $E_{\text{quad}} \le 0.010 \times E_{\text{smallest}}$ ($1.0\%$).
4. **Availability Gate:** Minimum 6 of 10 configurations receive a verified contract ($A_2 \ge 0.60$).
5. **Coverage Gate:** For issued contracts, $C_2 \ge 0.80$.
6. **Automated Scope Narrowing:** If Tier 2 fails to meet the availability or coverage gates, GDEC automatically triggers conditional scope narrowing:
   `"CONTRACT SCOPE RESTRICTED TO SMOOTH DISPLACEMENT QOIS ONLY"`.
