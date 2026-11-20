# GDEC Phase C Amendment 2 — Statistical Protocol Report

**Source:** `verification/phase_c/amendment_2/thresholds.json`  

---

## 1. Hypothesis Formulation & Denominators

### 1.1 Hypothesis H5a: Empirical Uncertainty Coverage
$$C_1 = \frac{N_{\text{covered}}}{N_{\text{issued}}} \ge 0.90 \quad (90.0\%)$$
- **Conditioning:** Evaluated strictly over issued contracts ($N_{\text{issued}}$), conditioned on minimum availability $A_1 = \frac{N_{\text{issued}}}{40} \ge 0.80 \implies N_{\text{issued}} \ge 32$.
- **Per-Family Floor:** In any family where $N_{\text{issued, fam}} \ge 6$, the family coverage must satisfy $C_{1, \text{fam}} \ge 0.80$.
- **Sampling Model Clarification:** Evaluated on pre-registered deterministic benchmark configurations. The two-sided 95% Clopper-Pearson exact confidence interval describes the Bernoulli parameter for the fixed benchmark generation family, not an IID sample of arbitrary CAD geometries.

### 1.2 Hypothesis H5b: Accuracy Claim Integrity
$$I_1 = \frac{N_{\text{met\_and\_true}}}{N_{\text{claims}}} \ge 0.90 \quad (90.0\%)$$
- **Minimum Claims Qualification:** $N_{\text{claims}} \ge 10$.
- **Policy on Low Denominator:** If fewer than 10 positive claims are made ($N_{\text{claims}} < 10$), the claim-integrity hypothesis is formally classified as:
  `INCONCLUSIVE — INSUFFICIENT POSITIVE CLAIMS`
  This prevents a small number of positive claims from producing a misleading statistical pass.

### 1.3 Hypothesis H7: Deterministic Refusal Correctness
$$R_7 = \frac{N_{\text{correct\_refusals}}}{80} = 1.00 \quad (100.0\%)$$
- Evaluated over all 80 Tier 3 refusal cases across all 10 priority categories (8 cases per category).
- Any contract issuance or positive target attainment claim constitutes an immediate failure.

### 1.4 Hypothesis H8: Tier 2 Difficult & Singular Benchmarks
- **Availability:** $A_2 = \frac{N_{\text{issued, T2}}}{10} \ge 0.60$ (at least 6 of 10 configurations).
- **Conditional Coverage:** $C_2 = \frac{N_{\text{covered, T2}}}{N_{\text{issued, T2}}} \ge 0.80$ (at least 80% of issued contracts cover true error).
- **Automated Scope Narrowing Fallback:** If Tier 2 fails either availability or coverage, GDEC automatically restricts its operating scope:
  `"CONTRACT SCOPE RESTRICTED TO SMOOTH DISPLACEMENT QOIS ONLY"`.
