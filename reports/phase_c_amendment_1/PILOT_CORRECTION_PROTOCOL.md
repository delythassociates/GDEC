# GDEC Phase C Amendment 1 — Pilot Correction Protocol

**Repository:** `delythassociates/GDEC`  
**Working Branch:** `phase-c/amendment-1`  
**Base Preregistration Tag:** `prereg-c`  
**Target Tag:** `prereg-c-amendment-1`  

---

## 1. Scope and Purpose

This protocol specifies the corrective actions taken to resolve the six pilot-related audit findings identified during independent review of Phase C preflight results:
- **AM1-02:** Williams patch pilot stability classification.
- **AM1-03:** Williams global displacement difference floor refusal.
- **AM1-04:** Weakly singular Case B non-monotonicity.
- **AM1-05:** Case B quadrature denominator formulation.
- **AM1-06:** Invariant patch integration domain clipping.
- **AM1-07:** Concordance between markdown reporting and raw JSON evidence.
- **AM1-08:** Direct invocation of `ProblemAnalyser.evaluate_contract()` for point stress refusal.

---

## 2. Mathematical Formulations & Protocols

### 2.1 Invariant Patch Integration (AM1-06)
In previous pilots, patch selection was performed by checking whether element centroids fell within $[x_{\min}, x_{\max}] \times [y_{\min}, y_{\max}]$. On unstructured or non-aligned meshes, the boundary elements varied with refinement level, producing a grid-dependent effective domain $\Omega_{\text{patch}}(h) \ne \Omega_{\text{patch}}$.

**Amended Protocol:**
All patch integrals must be evaluated on meshes specifically partitioned such that $\partial \Omega_{\text{patch}}$ coincides with mesh element boundaries across all refinement levels $M_0 \to M_3$.
For Case B on $[0, 1]^2$, using initial mesh step $h_0 = 0.20$ ensures that $[0.2, 0.6]^2$ is bounded exactly by mesh edges at every level $M_k$, maintaining exact domain area $|\Omega_{\text{patch}}| = 0.160000$ identically for all $k \in \{0, 1, 2, 3\}$.

### 2.2 Case B Quadrature Audit Formulation (AM1-05)
The quadrature audit ensures that numerical integration error $E_{\text{quad}} = |J_{\text{quad1}} - J_{\text{quad2}}|$ is negligible compared to the spatial discretisation error on the finest mesh $M_3$.

**Corrected Formulation:**
$$E_{\text{smallest}} = |J_{M_3} - J_{\text{exact}}|$$
$$\text{Ratio} = \frac{E_{\text{quad}}}{E_{\text{smallest}}} \le 0.010 \quad (1.0\%)$$
The erroneous denominator $|J_{M_3} - 1.0|$ is strictly prohibited.

### 2.3 Numerical Floor Enforcement (AM1-03)
When successive mesh differences $|d_{01}| = |J_0 - J_1|$ or $|d_{12}| = |J_1 - J_2|$ are below $10^{-13}$ m, finite element arithmetic is dominated by machine epsilon and conditioning noise.
The Problem Analyser must strictly refuse contract issuance with:
`RefusalCode.UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR` (Priority 7).

### 2.4 Four-Grid Stability Assessment (AM1-01, AM1-02, AM1-10)
When level $M_3$ is available:
$$q_{012} = \frac{|d_{01}|}{|d_{12}|}, \quad p_{012} = \frac{\ln(q_{012})}{\ln(2.0)}$$
$$q_{123} = \frac{|d_{12}|}{|d_{23}|}, \quad p_{123} = \frac{\ln(q_{123})}{\ln(2.0)}$$
$$\Delta p = |p_{012} - p_{123}| \le 0.50$$
If $\Delta p > 0.50$ or $d_{12} \cdot d_{23} \le 0$, the sequence is classified as `four_grid_stability_failed` or `four_grid_non_monotonic`. When `require_m3_stability=True`, this triggers deterministic refusal with `RefusalCode.UNVERIFIED_NON_ASYMPTOTIC`.
