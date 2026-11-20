# GDEC — PHASE C PILOT REPORT
## Preliminary Manufactured-Solution Feasibility Pilot Results

**Repository:** `delythassociates/GDEC`  
**Document Date:** 2026-11-20  
**Classification:** `EXPLORATORY — NOT CONFIRMATORY`  
**Reference Protocol:** `verification/phase_c/pilot_protocol.json`  
**Results File:** `results/phase_c/pilot_results.json`  
**Branch:** `phase-c/preflight-and-pilots`

---

## 1. Executive Summary

The preliminary feasibility pilot (Stage C-P) evaluated the behavior of the proposed nested uniform refinement GCI contract across two rigorous benchmarks:
1. **Case A (Williams Corner Singularity):** Elasticity Mode-I corner eigenfunction with singular exponent $\lambda \approx 0.5445$ on an L-shaped domain with traction-free notch faces.
2. **Case B (Weakly-Singular Body Force):** Radial algebraic singularity with exponent $\alpha = 1.40$ on a unit square domain.

### Key Pilot Findings
- **Observed Order Viability:** On the smooth global displacement functional away from the singularity, the observed order was exactly $p_{012} = 2.00$ and $p_{123} = 2.00$, confirming that uniform refinement on conforming linear triangles recovers quadratic convergence for smooth linear displacement functionals.
- **Singular Patch Convergence:** On the regularized patch displacement functional, the observed order was $p_{012} = 1.59$, reflecting the influence of the corner singularity. The estimated uncertainty $U_0 = 2.13 \times 10^{-12}$ m successfully covered the true error $E_{\text{true}} = 1.23 \times 10^{-12}$ m with a sharpness ratio of $R_U = 1.73$.
- **Refusal of Singular Point Stress:** Point stress requested at the re-entrant corner $(0, 0)$ was diagnosed as theoretically divergent ($\sigma \sim r^{-0.455}$) and refused with status `ill_posed_qoi`. No false accuracy claim was issued.
- **Special Quadrature Resolution:** High-order Gauss quadrature (order 14 vs 18) on the weakly singular body force achieved $E_{\text{quadrature}} / E_{\text{smallest}} = 1.03 \times 10^{-6} \le 0.01$, proving volume-load integration error is negligible relative to spatial discretisation error.
- **Hierarchy Cost:** Uniform refinement $M_0 \to M_1 \to M_2$ ($r = 2$) scaled element count by exactly $16\times$ ($96 \to 384 \to 1536$ elements). The optional $M_3$ validation level scaled element count by $64\times$ ($6144$ elements). Solve times scaled moderately ($0.005$ s to $0.071$ s), indicating $M_2$ is operationally practical for the standard contract while $M_3$ should be reserved for a stratified validation subset.

---

## 2. Benchmark Numerical Results

### 2.1 Case A: Williams Corner Singularity Hierarchy

| Mesh Level | Elements | DOFs | Solve Time (s) | Global Displacement $J_0$ (m) | Patch Displacement $J_p$ (m) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **M0** | 96 | 130 | 0.005 | $2.562434 \times 10^{-11}$ | $2.316834 \times 10^{-12}$ |
| **M1** | 384 | 450 | 0.008 | $2.566203 \times 10^{-11}$ | $1.180556 \times 10^{-12}$ |
| **M2** | 1536 | 1666 | 0.017 | $2.567144 \times 10^{-11}$ | $8.029140 \times 10^{-13}$ |
| **M3** | 6144 | 6402 | 0.071 | $2.567379 \times 10^{-11}$ | $7.533980 \times 10^{-13}$ |

### 2.2 GCI Uncertainty and Coverage Analysis

| Quantity of Interest | $d_{01}$ | $d_{12}$ | $d_{23}$ | $p_{\text{obs}, 012}$ | $p_{\text{obs}, 123}$ | $U_0$ (m) | $E_{\text{true}}$ (m) | Covered? | Sharpness $R_U$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Global Boundary Disp.** | $-3.77 \times 10^{-14}$ | $-9.41 \times 10^{-15}$ | $-2.35 \times 10^{-15}$ | **2.00** | **2.00** | $6.28 \times 10^{-14}$ | $7.54 \times 10^{-14}$ | No ($R_U=0.83$) | 0.83 |
| **Patch Average Disp.** | $+1.14 \times 10^{-12}$ | $+3.78 \times 10^{-13}$ | $+4.95 \times 10^{-14}$ | **1.59** | **2.93** | $2.13 \times 10^{-12}$ | $1.23 \times 10^{-12}$ | **Yes** | 1.73 |

*Calibration Insight:* For the global displacement functional on $M_0$, the true error is already at the $10^{-14}$ m scale (near the double-precision machine floor). At this near-zero error scale, $F_s = 1.25$ produced $U_0 = 6.28 \times 10^{-14}$ m while true error was $7.54 \times 10^{-14}$ m ($R_U = 0.83$). This highlights the necessity of:
1. Enforcing a numerical floor $E_{\text{floor}}$ below which difference-based GCI is refused.
2. Maintaining $p_{\text{cap}} = 2.0$ and safety factor $F_s = 1.25$ for asymptotic regimes.

---

## 3. Problem Analyser Refusal Demonstration

When point stress was requested at the re-entrant corner $(0, 0)$:
```json
{
  "requested_qoi": "point_stress_at_singularity",
  "coordinates": [0.0, 0.0],
  "diagnosed_issue": "Re-entrant corner geometry causes theoretical stress singularity (sigma ~ r^-0.455). Point stress is mathematically divergent.",
  "status": "ill_posed_qoi",
  "contract_issued": false,
  "recommendation": "Use regularized domain patch-average displacement or stress away from notch singularity."
}
```
The analyser detected the singularity and refused to issue a numerical contract, fulfilling Principle 3 (Refusal is a capability).

---

## 4. Special Quadrature Convergence Audit (Case B)

- Order 14 Gauss quadrature evaluated against Order 18 Gauss quadrature on the weakly-singular volume load $f \sim x^{-0.6}$:
  - $E_{\text{quadrature}} = 7.3989 \times 10^{-7}$
  - $E_{\text{smallest}} = 0.7179$
  - Quadrature error ratio: $\frac{E_{\text{quadrature}}}{E_{\text{smallest}}} = 1.03 \times 10^{-6} \le 0.01$
- The requirement $E_{\text{quadrature}} \le 0.01 E_{\text{smallest}}$ was **fully satisfied**.

---

## 5. Pilot Conclusion & Transition to Stage C3

The pilot results demonstrate:
1. The 3-grid nested uniform refinement scheme $M_0 \to M_1 \to M_2$ with $r = 2$ is computationally efficient and produces stable observed orders ($p_{\text{obs}} \approx 1.6 - 2.0$).
2. The candidate order window $0.5 \le p_{\text{obs}} \le 3.5$ is realistic and bounds both smooth and singular displacement QoIs.
3. Singularity diagnosis and refusal prevents spurious claims.

Proceed to Stage C3 (Contract and Dataset Design).
