# GDEC Benchmark Methodology & Reproduction

## 1. Standard Benchmark Problem: 2D Cantilever Beam
- **Domain**: Length $L = 2.0\text{ m}$, Height $H = 0.5\text{ m}$, Thickness $t = 0.02\text{ m}$.
- **Material**: Isotropic linear elasticity, $E = 70.0\text{ GPa}$, $\nu = 0.33$, Plane Stress.
- **Boundary Conditions**:
  - Clamped at $x = 0$: $u_x(0, y) = u_y(0, y) = 0$.
  - Distributed tip shear at $x = L$: $t_y = -1.0 \times 10^6\text{ Pa}$, $t_x = 0$.
- **Quantity of Interest (QoI)**: Average vertical displacement along the loaded right edge:
  $$J = \frac{1}{H} \int_0^H u_y(L, y) \, dy$$

## 2. Reference Solutions
1. **Primary Continuum Reference (Celik ASME 2008)**:
   $$J_{\infty,\text{Celik}} = -1.909525\text{ mm}, \quad p = 1.898, \quad \text{GCI} = 0.0983\%$$
2. **Sensitivity Reference (Roache 1998)**:
   $$J_{\infty,\text{Roache}} = -1.909240\text{ mm}, \quad p = 2.184, \quad \text{GCI} = 0.0796\%$$
3. **Discrete Fine-Mesh Reference (Level 3)**:
   $$J_{\text{ref,29k}} = -1.907295\text{ mm} \quad (29,768\text{ DOFs})$$

## 3. Equal-Accuracy Evaluation Protocol
Strategies are evaluated by determining the minimum DOFs and execution time required to reach fixed relative accuracy targets against the continuum reference:
- Targets: $\le 2.0\%$, $\le 1.0\%$, $\le 0.5\%$, $\le 0.25\%$.
- Results (v0.2.2):
  - $\le 2.0\%$ Error: Goal-Aware achieves target with **1,908 DOFs** ($1.37\times$ reduction vs Uniform 2,618 DOFs).
  - $\le 1.0\%$ Error: Goal-Aware achieves target with **4,034 DOFs** ($2.50\times$ reduction vs Uniform 10,098 DOFs).
  - $\le 0.5\%$ Error: Goal-Aware achieves target with **8,328 DOFs** ($1.21\times$ reduction vs Uniform 10,098 DOFs).
  - $\le 0.25\%$ Error: Goal-Aware achieves $0.1802\%$ at 17,030 DOFs (Uniform fails within budget).
