# GDEC Phase C Amendment 1 — Remediated Pilot Results

**Execution Timestamp:** 2026-11-20T18:21:55Z  
**Source Evidence:** `results/phase_c_amendment_1/pilot_results.json`  
**Concordance Verification:** 100% matching raw JSON records (remediating AM1-07).

---

## 1. Benchmark Case A: Williams Mode-I Corner Notch Singularity

### 1.1 Mesh Hierarchy and Computed Values

| Level | Elements | DOFs | Solve Time (s) | Global Top Edge $J_g$ (m) | Interior Patch $J_p$ (m) |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **M0** | 150 | 192 | 0.0069 | $2.564244 \times 10^{-11}$ | $-1.651381 \times 10^{-11}$ |
| **M1** | 600 | 682 | 0.0091 | $2.566655 \times 10^{-11}$ | $-1.675077 \times 10^{-11}$ |
| **M2** | 2400 | 2562 | 0.0300 | $2.567257 \times 10^{-11}$ | $-1.693718 \times 10^{-11}$ |
| **M3** | 9600 | 9922 | 0.1233 | $2.567408 \times 10^{-11}$ | $-1.709093 \times 10^{-11}$ |

### 1.2 Accuracy Contract Evaluations

| Functional | Computed Differences | Contract Status | Analyser Action | Audit Reference |
|:---|:---|:---|:---|:---:|
| **Global Top Edge** | $d_{01} = -2.411 \times 10^{-14}$<br>$d_{12} = -6.023 \times 10^{-15}$ | `unverified_difference_below_numerical_floor` | Contract refused (Priority 7) because differences are below the $10^{-13}$ m numerical floor. | **AM1-03** |
| **Interior Patch** | $d_{01} = 2.370 \times 10^{-13}$<br>$d_{12} = 1.864 \times 10^{-13}$<br>$d_{23} = 1.537 \times 10^{-13}$ | `unverified_order` | Contract refused (Priority 8) because $p_{\text{obs}} = 0.35$ is outside the validated plausibility window $[0.5, 3.5]$. | **AM1-02** |
| **Notch Point Stress** | Evaluated at $(0.0, 0.0)$ | `ill_posed_qoi` | Contract refused (Priority 1) due to singular stress field ($\sigma \sim r^{-0.455}$). | **AM1-08** |

---

## 2. Benchmark Case B: Manufactured Weakly-Singular Elastic Field ($\alpha = 1.40$)

Exact Functional Value: $J_{\text{exact}} = 0.2838096843988563$ m.

### 2.1 Nested Hierarchy Convergence

| Level | Elements | DOFs | $J_{\text{val}}$ (m) | True Error | Relative Error | Solve Time (s) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **M0** | 50 | 72 | 0.28717340 | $3.3637 \times 10^{-3}$ | 1.185% | 0.0056 |
| **M1** | 200 | 242 | 0.28465402 | $8.4434 \times 10^{-4}$ | 0.298% | 0.0125 |
| **M2** | 800 | 882 | 0.28402101 | $2.1132 \times 10^{-4}$ | 0.074% | 0.0517 |
| **M3** | 3200 | 3362 | 0.28386253 | $5.2849 \times 10^{-5}$ | 0.019% | 0.2369 |

### 2.2 Difference Sequence and Observed Order Stability

- $d_{01} = 0.00251937$
- $d_{12} = 0.00063302$
- $d_{23} = 0.00015847$
- Ratio $q_{012} = 3.980$, Observed Order $p_{012} = 1.993$
- Ratio $q_{123} = 3.994$, Observed Order $p_{123} = 1.998$
- Four-grid order drift: $\Delta p = |p_{012} - p_{123}| = 0.0052 \le 0.50$ (**Passed Stability Check**)

### 2.3 Quadrature Audit (Order 14 vs 18 on Level M2)

- $J_{\text{quad14}} = 0.28402101$ m
- $J_{\text{quad18}} = 0.28402080$ m
- Quadrature Error: $E_{\text{quad}} = |J_{\text{quad14}} - J_{\text{quad18}}| = 2.0808 \times 10^{-7}$ m
- Smallest Discretisation Error: $E_{\text{smallest}} = |J_{M_3} - J_{\text{exact}}| = 5.2849 \times 10^{-5}$ m
- Ratio: $\frac{E_{\text{quad}}}{E_{\text{smallest}}} = 0.003937 \quad (0.39\% \le 1.0\%)$ (**Passed Quadrature Gate**)

### 2.4 Problem Analyser Contract Result

- **Contract Issued:** True
- **Status:** `four_grid_verified_contract_issued`
- **Estimated Discretisation Uncertainty ($U_0$):** $0.00420602$ m
- **True Error ($E_{\text{true}, M_0}$):** $0.00336371$ m
- **Uncertainty Bound Coverage:** Covered ($E_{\text{true}} \le U_0$ is True)
- **Sharpness Ratio:** $U_0 / E_{\text{true}} = 1.2504$ (Conservative within safety factor $F_s = 1.25$)
