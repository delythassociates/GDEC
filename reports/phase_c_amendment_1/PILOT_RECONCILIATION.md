# GDEC Phase C Amendment 1 — Pilot Reconciliation Report

**Context:** Reconciliation of Preliminary Exploratory Pilots against Independent Review Findings.

---

## 1. Finding-by-Finding Reconciliation

### AM1-02: Williams Patch Pilot Stability Classification
- **Initial Defect:** In the preliminary pilot report, Williams patch displacement had $p_{012} = 1.59$ and $p_{123} = 2.93$ ($\Delta p = 1.34 > 0.50$). It was mistakenly classified as an accepted four-grid verified sample.
- **Reconciliation:** The amended pilot runner and report correctly classify Williams corner notch features as failing the asymptotic order window ($p_{\text{obs}} = 0.35 \notin [0.5, 3.5]$) or failing four-grid stability. The contract is refused with `unverified_order`, demonstrating that GDEC's Problem Analyser prevents false confidence when re-entrant corner singularities pollute local convergence.

### AM1-03: Williams Global Displacement Numerical Floor
- **Initial Defect:** Differences on the smooth boundary displacement were $|d_{01}| \approx 2.41 \times 10^{-14}$ m and $|d_{12}| \approx 6.02 \times 10^{-15}$ m, well below the $10^{-13}$ m numerical floor, but were processed by GCI.
- **Reconciliation:** Problem Analyser strictly evaluates the numerical floor rule (Priority 7). Both differences trigger `unverified_difference_below_numerical_floor`, and the contract is refused.

### AM1-04 & AM1-06: Patch Integration Domain Invariance & Case B Monotonicity
- **Initial Defect:** Element centroid selection on non-aligned grids caused the effective patch domain to vary across mesh levels, introducing non-monotonic oscillations ($J_0 = 0.3246, J_1 = 0.2925, J_2 = 0.2754, J_3 = 0.2821$).
- **Reconciliation:** Replaced arbitrary centroid filtering with domain-aligned mesh partitioning. The integration domain $[0.2, 0.6]^2$ is exactly preserved across all levels $M_0 \to M_3$. This yields strictly monotonic quadratic convergence ($p_{012} = 1.993, p_{123} = 1.998, \Delta p = 0.0052$).

### AM1-05: Case B Quadrature Denominator
- **Initial Defect:** Quadrature ratio used $|J_{M_3} - 1.0|$ in the denominator rather than $|J_{M_3} - J_{\text{exact}}|$.
- **Reconciliation:** Corrected denominator evaluates $|J_{M_3} - J_{\text{exact}}| = 5.2849 \times 10^{-5}$ m. On level $M_2$, quadrature error is $2.0808 \times 10^{-7}$ m, giving ratio $0.39\% \le 1.0\%$, passing the quadrature gate.

### AM1-07: Markdown Table vs JSON Concordance
- **Initial Defect:** Discrepancies between pilot report prose tables and raw JSON records.
- **Reconciliation:** `PILOT_RESULTS.md` was compiled directly from `results/phase_c_amendment_1/pilot_results.json` ensuring 100% numerical identity across all reported fields.

### AM1-08: Point Stress Refusal Execution Path
- **Initial Defect:** Point-stress refusal was recorded via a hardcoded dictionary rather than through `ProblemAnalyser.evaluate_contract()`.
- **Reconciliation:** Point stress functional evaluation now calls `ProblemAnalyser.evaluate_contract()`, which deterministically enforces Priority 1 refusal `ill_posed_qoi`.
