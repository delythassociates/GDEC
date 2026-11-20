# GDEC v0.2.1 Audit: Reference Mesh Convergence, GCI & Analytical Cross-Validation

**Audit Identifier**: `GDEC-v021-AUDIT-04`  
**Date**: 2026-11-20  
**Status**: VERIFIED & REPRODUCED DIRECTLY FROM SOURCE  
**Role**: Principal Computational Mechanics Researcher & Independent Scientific Auditor  

---

## 1. Executive Summary

All reference finite-element calculations for the `CantileverDemo` benchmark problem were recomputed directly from the underlying numerical solver without manual entry. The reference sequence was expanded to four progressively refined meshes up to 45,000 DOFs. Observed convergence rates, Richardson extrapolation, Roache's Grid Convergence Index (GCI), and classical 1D Timoshenko beam comparisons were systematically executed.

### Core Audit Findings
1. **Recomputed Reference Sequence**:
   - Level 1 (10,368 DOFs): $J_1 = -1.90336667\text{ mm}$ (0.093 s)
   - Level 2 (19,208 DOFs): $J_2 = -1.90612982\text{ mm}$ (0.200 s)
   - Level 3 (29,768 DOFs): $J_3 = -1.90729549\text{ mm}$ (0.345 s)
   - Level 4 (45,000 DOFs): $J_4 = -1.90802421\text{ mm}$ (0.621 s)
2. **Richardson Extrapolation & GCI**:
   - Observed order of convergence for the boundary displacement functional: **$p = 2.198 \approx 2.0$** (quadratic convergence of the functional under linear elements).
   - Richardson Extrapolated continuum limit: **$J_\infty = -1.90923950\text{ mm}$**.
   - Roache Grid Convergence Index on finest mesh ($F_s = 1.25$): **$\text{GCI} = 0.0796\%$**.
   - Discretization uncertainty between Level 2 and Level 3: **$0.0611\%$**; between Level 3 and Level 4: **$0.0382\%$**.
3. **Analytical Beam Theory Cross-Validation**:
   - Timoshenko deflection: **$-1.919771\text{ mm}$** (EB: $-1.828571$ mm, shear: $-0.091200$ mm).
   - Discrepancy between Level 4 FEM and Timoshenko: **$0.612\%$**.
   - Physical cause: Root clamping ($u_x = u_y = 0$ along $x=0$) prevents lateral Poisson expansion at the support in 2D continuum mechanics, a 2D boundary layer constraint absent from 1D beam theories.

---

## 2. Multi-Resolution Reference Data Table

Audited via `scratch/test_stage4_reference_and_benchmark.py` on Intel CPU (Windows 11, 64-bit):

| Level | Resolution ($n_x \times n_y$) | Elements | Nodes | DOFs ($2N$) | Solved QoI $J$ (mm) | Element Size $h$ (m) | Wall Time (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Level 1** | $144 \times 36$ | 10,010 | 5,184 | 10,368 | $-1.90336667$ | $0.013986$ | $0.093$ |
| **Level 2** | $196 \times 49$ | 18,720 | 9,604 | 19,208 | $-1.90612982$ | $0.010256$ | $0.200$ |
| **Level 3** | $244 \times 61$ | 29,160 | 14,884 | 29,768 | $-1.90729549$ | $0.008230$ | $0.345$ |
| **Level 4** | $300 \times 75$ | 44,252 | 22,500 | 45,000 | $-1.90802421$ | $0.006689$ | $0.621$ |

---

## 3. Asymptotic Convergence & Grid Convergence Index (GCI)

### 3.1 Observed Order of Convergence
Let $r_{32} = h_2 / h_3 = 1.246$, $r_{43} = h_3 / h_4 = 1.230$. The mean grid refinement ratio is $r \approx 1.238$.
The ratio of successive solution differences is:
$$\frac{f_2 - f_3}{f_3 - f_4} = \frac{-1.906130 - (-1.907295)}{-1.907295 - (-1.908024)} = \frac{0.00116567}{0.00072872} = 1.5996$$
The apparent order of convergence is:
$$p = \frac{\ln(1.5996)}{\ln(1.238)} = \mathbf{2.1978}$$
This confirms that the displacement functional converges quadratically $O(h^2)$, in accordance with finite element superconvergence for linear functionals on symmetric uniform meshes.

### 3.2 Richardson Extrapolation
Extrapolating to the hypothetical $h \to 0$ continuum limit:
$$J_\infty = f_4 + \frac{f_4 - f_3}{r^p - 1} = -1.90802421 + \frac{-0.00072872}{1.5996 - 1} = \mathbf{-1.90923950\text{ mm}}$$

### 3.3 Roache's Grid Convergence Index (GCI)
Applying the standard safety factor $F_s = 1.25$ for three or more grid resolutions:
$$\text{GCI}_{43} = \frac{F_s \cdot |(f_4 - f_3)/f_4|}{r^p - 1} = \frac{1.25 \times (3.819 \times 10^{-4})}{0.5996} = \mathbf{0.0796\%}$$
- **Discretization Uncertainty Conclusion**:
  - The Level 3 reference mesh ($29,768$ DOFs) has an estimated numerical uncertainty of $\approx 0.061\%$.
  - This uncertainty is adequate for benchmarking accuracy thresholds of $2.0\%$, $1.0\%$, and $0.5\%$.
  - However, for the $0.25\%$ threshold, the numerical uncertainty represents roughly one-third of the target accuracy, meaning $0.25\%$ results must be interpreted with caution.

---

## 4. Analytical Beam Theory Cross-Validation

### 4.1 Theoretical Equations
For end-loaded cantilever beam under downward tip traction $t_y = -1.0\text{ MPa}$ ($P = t_y H t = -10,000$ N):
- Length $L = 2.0$ m, Height $H = 0.5$ m, Thickness $t = 0.02$ m
- Cross-sectional area $A = H t = 0.01\text{ m}^2$
- Second moment of area $I = \frac{t H^3}{12} = \frac{0.02 \times (0.5)^3}{12} = 2.083333 \times 10^{-4}\text{ m}^4$
- Shear modulus $G = \frac{E}{2(1 + \nu)} = \frac{70 \times 10^9}{2(1 + 0.33)} = 2.631579 \times 10^{10}\text{ Pa}$
- Shear coefficient $\kappa = \frac{5}{6}$ (rectangular cross-section)

$$\delta_{\text{EB}} = \frac{P L^3}{3 E I} = \frac{-10000 \times 8.0}{3 \times 70 \times 10^9 \times 2.083333 \times 10^{-4}} = \mathbf{-1.828571\text{ mm}}$$
$$\delta_{\text{shear}} = \frac{P L}{\kappa G A} = \frac{-10000 \times 2.0}{(5/6) \times 2.631579 \times 10^{10} \times 0.01} = \mathbf{-0.091200\text{ mm}}$$
$$\delta_{\text{analytical}} = \delta_{\text{EB}} + \delta_{\text{shear}} = \mathbf{-1.919771\text{ mm}}$$

### 4.2 Discrepancy Explanation (2D Root Boundary Layer)
The finest 2D FEM solution (Level 4, $-1.908024$ mm) differs from 1D Timoshenko beam theory ($-1.919771$ mm) by **$0.612\%$**.
In 1D beam theory, cross-sections are assumed free to expand and contract laterally due to Poisson effect ($\varepsilon_{yy} = -\nu \sigma_{xx} / E$). In 2D continuum elasticity, the fixed Dirichlet boundary condition $\mathbf{u}(0, y) = \mathbf{0}$ clamps both $u_x$ and $u_y$, constraining lateral Poisson expansion along the root. This constraint induces a localized 2D transverse stress $\sigma_{yy} \neq 0$ that artificially stiffens the beam near the support, slightly reducing the tip deflection. The $< 0.7\%$ agreement confirms the physical fidelity of the finite element solver.

---

## 5. Audit Stage 4A Sign-Off
Reference values are reproducible from source, GCI uncertainty is quantified at $0.0796\%$, and analytical cross-validation is verified.
