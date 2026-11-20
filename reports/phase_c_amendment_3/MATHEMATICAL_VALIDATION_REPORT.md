# GDEC Phase C Amendment 3: Mathematical Verification & Tier 1 BVP Audit Report
**Remediates:** AM3-02  
**Target:** Rigorous derivation of Family 4 displacement functionals, sign reconciliation, and independent verification of all 40 Tier 1 BVPs.  
**Script:** `verification/phase_c/amendment_3/audit_qois.py`  
**Data:** `results/phase_c_amendment_3/exact_qoi_audit.json`  

---

## 1. Executive Summary

During the Phase C Amendment 2 audit, an independent source inspection identified an ambiguity in the Family 4 patch QoI documentation:
- The report stated: `Patch average on [0.25, 0.75]^2: J_exact = 0.25 kx + (13/48) ky`.
- While this formula correctly represents the horizontal displacement component $u_x$, if interpreted as the vertical displacement component $u_y$, the sign of the $k_y$ term is negative ($-\frac{13}{48} k_y$).

In Amendment 3, we have:
1. Reconciled both horizontal ($u_x$) and vertical ($u_y$) displacement formulas with closed-form step-by-step integrations.
2. Verified that in `tier1_manifest.json`, the patch configurations (T1_26, T1_28, T1_30, T1_32) unambiguously target $u_x$, for which $+ \frac{13}{48} k_y$ is exact.
3. Added closed-form definitions for both components to prevent future misinterpretation.
4. Performed independent mathematical and numerical audits across all 40 Tier 1 BVP configurations, comparing analytical closed-form values against adaptive numerical quadrature via SciPy `quad` and `dblquad` with tolerance $10^{-14}$.
5. Verified that all 40 configurations match within machine precision (global maximum difference is $4.34 \times 10^{-19} \ll 10^{-11}$).

---

## 2. Family 4 Step-by-Step Derivation and Sign Audit

### 2.1 Displacement Field
The Family 4 mixed shear displacement field is:
$$u_x(x, y) = k_x x y + k_y y^2$$
$$u_y(x, y) = -k_y x^2 + k_x x y$$

### 2.2 Boundary Average Displacements on Top Edge ($y = 1.0, x \in [0, 1]$)
Length of edge $L = 1.0$.
- **Vertical Displacement ($u_y$):**
  $$u_y(x, 1) = -k_y x^2 + k_x x$$
  $$\bar{u}_y = \int_0^1 (-k_y x^2 + k_x x) \, dx = \left[ -\frac{k_y x^3}{3} + \frac{k_x x^2}{2} \right]_0^1 = -\frac{1}{3} k_y + \frac{1}{2} k_x$$
- **Horizontal Displacement ($u_x$):**
  $$u_x(x, 1) = k_x x + k_y$$
  $$\bar{u}_x = \int_0^1 (k_x x + k_y) \, dx = \frac{1}{2} k_x + k_y$$

### 2.3 Interior Patch Average Displacements on $\Omega_p = [0.25, 0.75]^2$
Area of patch $A_p = (0.75 - 0.25) \times (0.75 - 0.25) = 0.5 \times 0.5 = 0.25 = \frac{1}{4}$.
1D component integrals:
$$\int_{0.25}^{0.75} x \, dx = \left[ \frac{x^2}{2} \right]_{0.25}^{0.75} = \frac{0.5625 - 0.0625}{2} = 0.25 = \frac{1}{4}$$
$$\int_{0.25}^{0.75} x^2 \, dx = \left[ \frac{x^3}{3} \right]_{0.25}^{0.75} = \frac{0.421875 - 0.015625}{3} = \frac{0.40625}{3} = \frac{13}{96}$$
$$\int_{0.25}^{0.75} 1 \, dx = 0.5 = \frac{1}{2}$$

Now evaluating the patch averages:
- **Horizontal Displacement ($u_x$):**
  $$\int_{\Omega_p} u_x \, dA = \int_{0.25}^{0.75} \int_{0.25}^{0.75} (k_x x y + k_y y^2) \, dx \, dy = k_x \left(\frac{1}{4}\right)\left(\frac{1}{4}\right) + k_y \left(\frac{1}{2}\right)\left(\frac{13}{96}\right) = \frac{1}{16} k_x + \frac{13}{192} k_y$$
  $$\bar{u}_x = \frac{1}{A_p} \int_{\Omega_p} u_x \, dA = \frac{\frac{1}{16} k_x + \frac{13}{192} k_y}{1/4} = \frac{1}{4} k_x + \frac{13}{48} k_y = 0.25 k_x + \frac{13}{48} k_y$$
- **Vertical Displacement ($u_y$):**
  $$\int_{\Omega_p} u_y \, dA = \int_{0.25}^{0.75} \int_{0.25}^{0.75} (-k_y x^2 + k_x x y) \, dx \, dy = -k_y \left(\frac{13}{96}\right)\left(\frac{1}{2}\right) + k_x \left(\frac{1}{4}\right)\left(\frac{1}{4}\right) = -\frac{13}{192} k_y + \frac{1}{16} k_x$$
  $$\bar{u}_y = \frac{1}{A_p} \int_{\Omega_p} u_y \, dA = \frac{-\frac{13}{192} k_y + \frac{1}{16} k_x}{1/4} = -\frac{13}{48} k_y + \frac{1}{4} k_x = 0.25 k_x - \frac{13}{48} k_y$$

**Audit Conclusion for Family 4:**
- When the QoI is patch-average horizontal displacement $u_x$, the coefficient of $k_y$ is $+ \frac{13}{48}$.
- When the QoI is patch-average vertical displacement $u_y$, the coefficient of $k_y$ is $-\frac{13}{48}$.
- In `tier1_manifest.json`, items T1_26, T1_28, T1_30, T1_32 specify `component: "x"`, so the positive sign $+ \frac{13}{48} k_y$ in the manifest is mathematically exact. The report has been updated to explicitly present both formulas to eliminate any ambiguity.

---

## 3. Comprehensive 40-Configuration Mathematical Verification Table

| Config ID | Family | Component | Target Region | Exact Analytical Expression | Exact Value | Quad Value | Abs Diff | Status | Reference |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **T1_01** | Polynomial | y | Boundary $y=1$ | $\frac{1}{2} a$ | $5.000 \times 10^{-4}$ | $5.000 \times 10^{-4}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_02** | Polynomial | x | Patch $[0.25, 0.75]^2$ | $\frac{13}{48}(a + b)$ | $3.250 \times 10^{-4}$ | $3.250 \times 10^{-4}$ | $1.08 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_03** | Polynomial | y | Boundary $y=1$ | $\frac{1}{2} a$ | $1.500 \times 10^{-3}$ | $1.500 \times 10^{-3}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_04** | Polynomial | x | Patch $[0.25, 0.75]^2$ | $\frac{13}{48}(a + b)$ | $6.500 \times 10^{-4}$ | $6.500 \times 10^{-4}$ | $2.17 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_05** | Polynomial | y | Boundary $y=1$ | $\frac{1}{2} a$ | $2.500 \times 10^{-3}$ | $2.500 \times 10^{-3}$ | $4.34 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_06** | Polynomial | x | Patch $[0.25, 0.75]^2$ | $\frac{13}{48}(a + b)$ | $9.750 \times 10^{-4}$ | $9.750 \times 10^{-4}$ | $1.08 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_07** | Polynomial | y | Boundary $y=1$ | $\frac{1}{2} a$ | $3.500 \times 10^{-3}$ | $3.500 \times 10^{-3}$ | $4.34 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_08** | Polynomial | x | Patch $[0.25, 0.75]^2$ | $\frac{13}{48}(a + b)$ | $1.300 \times 10^{-3}$ | $1.300 \times 10^{-3}$ | $4.34 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_09** | Trigonometric | y | Boundary $y=1$ | $A \sin(f \pi) \int \cos(f \pi x) dx$ | $5.093 \times 10^{-5}$ | $5.093 \times 10^{-5}$ | $6.78 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_10** | Trigonometric | x | Patch $[0.25, 0.75]^2$ | 2D separable $\sin \otimes \cos$ | $-2.282 \times 10^{-5}$ | $-2.282 \times 10^{-5}$ | $1.02 \times 10^{-20}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_11** | Trigonometric | y | Boundary $y=1$ | $A \sin(f \pi) \int \cos(f \pi x) dx$ | $2.122 \times 10^{-5}$ | $2.122 \times 10^{-5}$ | $6.78 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_12** | Trigonometric | x | Patch $[0.25, 0.75]^2$ | 2D separable $\sin \otimes \cos$ | $1.198 \times 10^{-5}$ | $1.198 \times 10^{-5}$ | $1.69 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_13** | Trigonometric | y | Boundary $y=1$ | $A \sin(f \pi) \int \cos(f \pi x) dx$ | $1.528 \times 10^{-5}$ | $1.528 \times 10^{-5}$ | $3.39 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_14** | Trigonometric | x | Patch $[0.25, 0.75]^2$ | 2D separable $\sin \otimes \cos$ | $-2.177 \times 10^{-6}$ | $-2.177 \times 10^{-6}$ | $4.24 \times 10^{-22}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_15** | Trigonometric | y | Boundary $y=1$ | $A \sin(f \pi) \int \cos(f \pi x) dx$ | $1.273 \times 10^{-5}$ | $1.273 \times 10^{-5}$ | $6.78 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_16** | Trigonometric | x | Patch $[0.25, 0.75]^2$ | 2D separable $\sin \otimes \cos$ | $1.812 \times 10^{-7}$ | $1.812 \times 10^{-7}$ | $1.19 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_17** | Gaussian | y | Boundary $y=1$ | $0.5 A \text{erf}$ product | $1.602 \times 10^{-14}$ | $1.602 \times 10^{-14}$ | $1.11 \times 10^{-23}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_18** | Gaussian | x | Patch $[0.25, 0.75]^2$ | $A \text{erf}^2 / 0.25$ | $4.478 \times 10^{-5}$ | $4.478 \times 10^{-5}$ | $6.78 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_19** | Gaussian | y | Boundary $y=1$ | $0.5 A \text{erf}$ product | $2.396 \times 10^{-9}$ | $2.396 \times 10^{-9}$ | $1.24 \times 10^{-24}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_20** | Gaussian | x | Patch $[0.25, 0.75]^2$ | $A \text{erf}^2 / 0.25$ | $7.220 \times 10^{-5}$ | $7.220 \times 10^{-5}$ | $1.36 \times 10^{-20}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_21** | Gaussian | y | Boundary $y=1$ | $0.5 A \text{erf}$ product | $1.602 \times 10^{-14}$ | $1.602 \times 10^{-14}$ | $1.11 \times 10^{-23}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_22** | Gaussian | x | Patch $[0.25, 0.75]^2$ | $A \text{erf}^2 / 0.25$ | $4.478 \times 10^{-5}$ | $4.478 \times 10^{-5}$ | $6.78 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_23** | Gaussian | y | Boundary $y=1$ | $0.5 A \text{erf}$ product | $2.396 \times 10^{-9}$ | $2.396 \times 10^{-9}$ | $1.24 \times 10^{-24}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_24** | Gaussian | x | Patch $[0.25, 0.75]^2$ | $A \text{erf}^2 / 0.25$ | $7.220 \times 10^{-5}$ | $7.220 \times 10^{-5}$ | $1.36 \times 10^{-20}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_25** | Mixed Shear | y | Boundary $y=1$ | $-\frac{1}{3} k_y + \frac{1}{2} k_x$ | $5.500 \times 10^{-4}$ | $5.500 \times 10^{-4}$ | $1.08 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_26** | Mixed Shear | x | Patch $[0.25, 0.75]^2$ | $\frac{1}{4} k_x + \frac{13}{48} k_y$ | $1.075 \times 10^{-3}$ | $1.075 \times 10^{-3}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_27** | Mixed Shear | y | Boundary $y=1$ | $-\frac{1}{3} k_y + \frac{1}{2} k_x$ | $1.650 \times 10^{-3}$ | $1.650 \times 10^{-3}$ | $2.17 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_28** | Mixed Shear | x | Patch $[0.25, 0.75]^2$ | $\frac{1}{4} k_x + \frac{13}{48} k_y$ | $2.150 \times 10^{-3}$ | $2.150 \times 10^{-3}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_29** | Mixed Shear | y | Boundary $y=1$ | $-\frac{1}{3} k_y + \frac{1}{2} k_x$ | $2.750 \times 10^{-3}$ | $2.750 \times 10^{-3}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_30** | Mixed Shear | x | Patch $[0.25, 0.75]^2$ | $\frac{1}{4} k_x + \frac{13}{48} k_y$ | $3.225 \times 10^{-3}$ | $3.225 \times 10^{-3}$ | $4.34 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_31** | Mixed Shear | y | Boundary $y=1$ | $-\frac{1}{3} k_y + \frac{1}{2} k_x$ | $3.850 \times 10^{-3}$ | $3.850 \times 10^{-3}$ | $4.34 \times 10^{-19}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_32** | Mixed Shear | x | Patch $[0.25, 0.75]^2$ | $\frac{1}{4} k_x + \frac{13}{48} k_y$ | $4.300 \times 10^{-3}$ | $4.300 \times 10^{-3}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_33** | Oscillatory | y | Boundary $y=1$ | $A \int (\cos k_1 \pi y + \dots) dx$ | $6.250 \times 10^{-5}$ | $6.250 \times 10^{-5}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_34** | Oscillatory | x | Patch $[0.25, 0.75]^2$ | $A \int (\sin k_1 \pi x + \dots) dx$ | $-1.501 \times 10^{-5}$ | $-1.501 \times 10^{-5}$ | $3.39 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_35** | Oscillatory | y | Boundary $y=1$ | $A \int (\cos k_1 \pi y + \dots) dx$ | $6.250 \times 10^{-5}$ | $6.250 \times 10^{-5}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_36** | Oscillatory | x | Patch $[0.25, 0.75]^2$ | $A \int (\sin k_1 \pi x + \dots) dx$ | $-9.003 \times 10^{-6}$ | $-9.003 \times 10^{-6}$ | $1.19 \times 10^{-20}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_37** | Oscillatory | y | Boundary $y=1$ | $A \int (\cos k_1 \pi y + \dots) dx$ | $-6.250 \times 10^{-5}$ | $-6.250 \times 10^{-5}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_38** | Oscillatory | x | Patch $[0.25, 0.75]^2$ | $A \int (\sin k_1 \pi x + \dots) dx$ | $1.250 \times 10^{-6}$ | $1.250 \times 10^{-6}$ | $2.96 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_39** | Oscillatory | y | Boundary $y=1$ | $A \int (\cos k_1 \pi y + \dots) dx$ | $6.250 \times 10^{-5}$ | $6.250 \times 10^{-5}$ | $0.00 \times 10^{0}$ | **PASS** | `test_tier1_exact_qoi` |
| **T1_40** | Oscillatory | x | Patch $[0.25, 0.75]^2$ | $A \int (\sin k_1 \pi x + \dots) dx$ | $-8.253 \times 10^{-6}$ | $-8.253 \times 10^{-6}$ | $3.39 \times 10^{-21}$ | **PASS** | `test_tier1_exact_qoi` |

---

## 4. Auditor Sign-Off & Verification Conclusion

All requirements of finding **AM3-02** are satisfied in full:
1. The sign discrepancy for Family 4 is completely resolved. Both horizontal and vertical patch integrals are rigorously derived.
2. All 40 configurations in `tier1_manifest.json` have been verified against independent numerical quadrature, with absolute differences $< 10^{-18} \ll 10^{-11}$.
3. Mathematical validation reports, manifests, and software implementations are in 100% agreement.
