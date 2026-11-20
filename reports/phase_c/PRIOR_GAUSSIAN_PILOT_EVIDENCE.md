# GDEC — PRIOR GAUSSIAN PILOT EVIDENCE NOTE
## Preliminary User-Reported Pilot Findings

**Repository:** `delythassociates/GDEC`  
**Document Date:** 2026-11-20  
**Status:** User-Reported Preliminary Evidence (Non-Confirmatory, Informational Only)  
**Location:** `reports/phase_c/PRIOR_GAUSSIAN_PILOT_EVIDENCE.md`

---

## 1. Summary of Prior User-Reported Pilot

Prior to the formal initiation of Phase C, an exploratory feasibility investigation using localized Gaussian displacement fields was conducted and reported by the project sponsor.

A search of the repository confirms that **no raw numerical artifacts, scripts, or output logs for this pilot exist in the version control history**. Consequently, the figures below are recorded as user-provided preliminary findings and are **not independently reproducible**.

Per Section 6.1 of the Phase C brief, these samples **must not** be counted toward the 40 independent Tier 1 configurations required for the confirmatory Phase C experiment.

---

## 2. Reported Pilot Parameters and Metrics

- **Manufactured Solution:** Localized Gaussian displacement features with two distinct characteristic widths $\sigma$.
- **Quantities of Interest:** Two QoI types (global boundary average displacement and local domain patch average displacement).
- **Total Configurations Sampled:** 24 samples.
- **Coverage on Usable Samples:** 21 of 21 usable issued estimates covered the true error ($100\%$ conditional coverage on non-refused samples).
- **Estimated Uncertainty Sharpness:** Ratio of estimated uncertainty to true error ($U_0 / E_{\text{true}}$) ranged between $1.25$ and $1.56$ for covered samples (close to the nominal safety factor $F_s = 1.25$).
- **Refusal Behaviour:** 3 refusals among 24 samples ($12.5\%$ refusal rate):
  - 2 samples refused due to implausible observed orders ($p_{\text{obs}} = 6.75$ and $p_{\text{obs}} = 7.65$, exceeding the plausibility ceiling).
  - 1 sample refused due to non-monotonic error difference sequence ($d_{01} d_{12} \le 0$).
- **Sample Independence Limitation:** All 24 evaluations were generated from only **two underlying mesh trajectories**, meaning sequential samples were strongly correlated.
- **Hierarchy Cost:** Uniform refinement $M_0 \to M_1 \to M_2$ ($r = 2$) required approximately $16\times$ the element count of $M_0$ at the finest level $M_2$.

---

## 3. Methodological Takeaways for Phase C Contract Design

1. **Observed Order Ceiling:** The occurrence of spurious observed orders ($p_{\text{obs}} > 6.0$) on coarse initial meshes with localized features demonstrates the critical necessity of an upper plausibility bound ($p_{\text{obs}} \le 3.5$) to prevent severe underestimation of uncertainty.
2. **Refusal Mechanism Validation:** The refusal of non-monotonic and super-asymptotic sequences prevented the emission of false certainty on unresolved meshes, validating the core principle that refusal is a primary reliability capability.
3. **Requirement for Genuinely Independent Configurations:** A handful of trajectories evaluated at multiple steps does not constitute statistical evidence. The confirmatory Phase C dataset must use genuinely independent parameter sets, seeds, and manufactured expressions.
