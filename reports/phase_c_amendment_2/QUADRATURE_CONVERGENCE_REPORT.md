# GDEC Phase C Amendment 2 — Multi-Order Quadrature Convergence Report

**Script:** `verification/phase_c/amendment_2/quadrature_study.py`  
**Raw Results:** `results/phase_c_amendment_2/quadrature_study_results.json`  
**Case:** Weakly-Singular Manufactured Solution ($\alpha = 1.40$) on Unit Square $[0, 1]^2$.  
**Invariant Patch:** $[0.20, 0.60] \times [0.20, 0.60]$, Area $= 0.160000$ identically.  

---

## 1. Methodology: Duffy Tensor Gauss-Legendre Quadrature

To overcome `skfem`'s internal triangle quadrature limitation (which maxes out at order 19), a Duffy coordinate transformation was implemented:
$$\int_T f(x, y) dx dy = 2 \text{Area}(T) \int_0^1 \int_0^1 f(x(\xi, \eta), y(\xi, \eta)) (1 - \xi) d\xi d\eta$$
Using 1D Gauss-Legendre rules of orders $N \in \{7, 9, 11, 13\}$, exact 2D algebraic precisions of degrees $2N - 1 \in \{13, 17, 21, 25\}$ are generated, corresponding to quadrature orders 14, 18, 22, and 26.

---

## 2. Convergence Study Results

### 2.1 Mesh Level M1 (200 Elements, 242 DOFs)

| Quadrature Rule | 1D Points | 2D Points per Triangle | Computed Functional $J$ (m) | Consecutive Sensitivity $\delta$ (m) | Ratio $\delta_{k+1} / \delta_k$ |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **Order 14** | 7 | 49 | 0.284652206395 | — | — |
| **Order 18** | 9 | 81 | 0.284653059960 | $\delta_{14,18} = 8.5357 \times 10^{-7}$ | — |
| **Order 22** | 11 | 121 | 0.284653433166 | $\delta_{18,22} = 3.7321 \times 10^{-7}$ | 0.4372 |
| **Order 26** | 13 | 169 | 0.284653622978 | $\delta_{22,26} = 1.8981 \times 10^{-7}$ | 0.5086 |

- **Ratio against finest discretisation error ($E_{\text{smallest}, M_3} = 5.2849 \times 10^{-5}$ m):**
  $$\frac{\delta_{22,26}}{E_{\text{smallest}}} = \frac{1.8981 \times 10^{-7}}{5.2849 \times 10^{-5}} = 0.00359 \quad (0.359\% \le 1.0\%)$$

### 2.2 Mesh Level M2 (800 Elements, 882 DOFs)

| Quadrature Rule | 1D Points | 2D Points per Triangle | Computed Functional $J$ (m) | Consecutive Sensitivity $\delta$ (m) | Ratio $\delta_{k+1} / \delta_k$ |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **Order 14** | 7 | 49 | 0.284020320105 | — | — |
| **Order 18** | 9 | 81 | 0.284020643100 | $\delta_{14,18} = 3.2300 \times 10^{-7}$ | — |
| **Order 22** | 11 | 121 | 0.284020784318 | $\delta_{18,22} = 1.4122 \times 10^{-7}$ | 0.4372 |
| **Order 26** | 13 | 169 | 0.284020856139 | $\delta_{22,26} = 7.1821 \times 10^{-8}$ | 0.5086 |

- **Ratio against finest discretisation error ($E_{\text{smallest}, M_3} = 5.2849 \times 10^{-5}$ m):**
  $$\frac{\delta_{22,26}}{E_{\text{smallest}}} = \frac{7.1821 \times 10^{-8}}{5.2849 \times 10^{-5}} = 0.00136 \quad (0.136\% \le 1.0\%)$$

---

## 3. Conclusions

1. **Strict Monotonic Geometric Convergence:** Across both mesh levels, the consecutive differences decrease with a constant geometric ratio of approximately $0.44 \to 0.51$.
2. **Acceptance Gate Satisfied:** The estimated residual quadrature error is bounded well below the 1.0% preregistered gate on both levels ($0.36\%$ on M1, $0.14\%$ on M2), confirming that quadrature error does not contaminate the spatial discretisation convergence sequence.
