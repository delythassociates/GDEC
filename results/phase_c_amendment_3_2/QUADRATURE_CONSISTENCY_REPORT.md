# GDEC Phase C Amendment 3.2 — Multi-Order Quadrature Sensitivity Report

**Governing Standard:** AM32-04 Quadrature Consistency and Single Source of Truth  
**Data Source:** `results/phase_c_amendment_3_2/quadrature_study_results.json`  
**Benchmark Case:** Case B — Singular Elasticity Manufactured Solution (alpha = 1.40)  
**Exact Analytical QoI:** `0.2838096843988563`  
**M3 Spatial Error Reference:** `5.279145e-05` (computed with Duffy Order 26: `0.2838624758465632`)  
**Residual Quadrature Threshold:** <= 1.0% of spatial error  
**Convergence Classification:** **`EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE`**  

---

## 1. Single Source of Truth Notice

This report is generated directly and programmatically from `quadrature_study_results.json`.
Every number displayed matches the machine-readable record to all significant digits, eliminating the transcription error identified in the Amendment 3.1 audit.

---

## 2. Multi-Order Sensitivity Table

| Level | Elements | Nodes | Order 14 (14^2) | Order 18 (18^2) | Order 22 (22^2) | Order 26 (26^2) | delta_22_26 | Observed rho | Tail Estimate E_tail | Tail Ratio % | Status |
|:-----:|:--------:|:-----:|:---------------:|:---------------:|:---------------:|:---------------:|:-----------:|:------------:|:--------------------:|:------------:|:------:|
| `M1` | 200 | 121 | 0.28465221 | 0.28465306 | 0.28465343 | 0.28465362 | 1.90e-07 | 0.5086 | 3.86e-07 | 0.7317% | **`CONVERGED_GEOMETRIC`** |
| `M2` | 800 | 441 | 0.28402032 | 0.28402064 | 0.28402078 | 0.28402086 | 7.18e-08 | 0.5086 | 1.46e-07 | 0.2768% | **`CONVERGED_GEOMETRIC`** |
| `M3` | 3200 | 1681 | 0.28386227 | 0.28386240 | 0.28386245 | 0.28386248 | 2.72e-08 | 0.5086 | 5.54e-08 | 0.1049% | **`CONVERGED_GEOMETRIC`** |

---

## 3. Strict Zero-Difference and Convergence Semantics

In accordance with AM32-04:
1. **Precision-Floor Precondition:** A plateau to zero differences (delta_18_22 = 0, delta_22_26 = 0) is accepted ONLY when preceding differences satisfy delta_14_18 <= 1e-12.
2. **Rejection of Unjustified Plateau:** If delta_14_18 > 1e-12 and subsequent differences are zero, the evaluation returns `INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE` and verification fails closed.
3. **Strict Geometric Monotonicity:** Quadrature sensitivities must decrease strictly monotonically (delta_14_18 > delta_18_22 > delta_22_26 > 0) with contractive decay ratio 0 < rho < 1.
4. **Tail Error Bound:**
   E_tail = delta_22_26 / (1 - rho) = 2.720354e-8 / (1 - 0.508580) = 5.535700e-8
   Tail Ratio = E_tail / E_spatial(M3) = 5.535700e-8 / 5.279145e-5 = 0.1049% <= 1.0%

**Conclusion:** Residual quadrature error contributes only 0.1049% of spatial discretisation error, safely satisfying the frozen 1.0% threshold.