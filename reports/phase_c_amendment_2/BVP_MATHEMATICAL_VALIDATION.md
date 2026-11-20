# GDEC Phase C Amendment 2 — Tier 1 Manufactured BVP Mathematical Validation

**Source Manifest:** `verification/phase_c/amendment_2/tier1_manifest.json`  
**Test Suite:** `tests/test_phase_c_amendment_2.py`  

---

## 1. Governing Equations & Elasticity Convention

For 2D linear isotropic elasticity:
$$\boldsymbol{\sigma} = \begin{bmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \sigma_{xy} \end{bmatrix} = \begin{bmatrix} c_{11} & c_{12} & 0 \\ c_{12} & c_{11} & 0 \\ 0 & 0 & c_{33} \end{bmatrix} \begin{bmatrix} u_{x,x} \\ u_{y,y} \\ u_{x,y} + u_{y,x} \end{bmatrix}$$
where $c_{33} = \frac{c_{11} - c_{12}}{2}$.
The manufactured body force is defined by equilibrium:
$$\mathbf{f} = -\nabla \cdot \boldsymbol{\sigma} \implies \begin{cases} f_x = - (\sigma_{xx,x} + \sigma_{xy,y}) = - [c_{11} u_{x,xx} + c_{33} u_{x,yy} + (c_{12} + c_{33}) u_{y,xy}] \\ f_y = - (\sigma_{xy,x} + \sigma_{yy,y}) = - [c_{11} u_{y,yy} + c_{33} u_{y,xx} + (c_{12} + c_{33}) u_{x,xy}] \end{cases}$$

---

## 2. Derivations by Family

### 2.1 Family 1: Polynomial Field
- **Displacement:**
  $$u_x = a x^2 + b y^2, \quad u_y = a x y$$
- **Derivatives:**
  $$u_{x,xx} = 2a, \quad u_{x,yy} = 2b, \quad u_{x,xy} = 0, \quad u_{y,xx} = 0, \quad u_{y,yy} = 0, \quad u_{y,xy} = a$$
- **Correct Body Force:**
  $$f_x = - [2 a c_{11} + 2 b c_{33} + a (c_{12} + c_{33})] = - a (2 c_{11} + c_{12}) - c_{33} (a + 2b)$$
  $$f_y = 0$$
  *(Remediates the previous omission of the $a c_{12}$ contribution).*
- **Exact QoIs:**
  - Boundary average on $y=1, x \in [0, 1]$: $J_{\text{exact}} = \int_0^1 a x dx = \frac{1}{2} a$.
  - Patch average on $[0.25, 0.75]^2$: $J_{\text{exact}} = \frac{13}{48} (a + b)$.

### 2.2 Family 2: Trigonometric Field
- **Displacement:**
  $$u_x = A \sin(\omega \pi x) \cos(\omega \pi y), \quad u_y = A \cos(\omega \pi x) \sin(\omega \pi y)$$
- **Body Force:**
  $$f_x = 2 c_{11} (\omega \pi)^2 A \sin(\omega \pi x) \cos(\omega \pi y), \quad f_y = 2 c_{11} (\omega \pi)^2 A \cos(\omega \pi x) \sin(\omega \pi y)$$
- **Exact QoIs:**
  - Boundary average on $y=1$: $J_{\text{exact}} = A \frac{\sin^2(\omega \pi)}{\omega \pi}$ (non-integer frequencies ensure $J \ne 0$).
  - Patch average on $[0.25, 0.75]^2$: Exact double sine/cosine integral.

### 2.3 Family 3: Localized Gaussian Field
- **Displacement:**
  $$\phi(x, y) = A \exp\left(-\frac{(x-x_0)^2 + (y-y_0)^2}{s^2}\right), \quad u_x = \phi, \quad u_y = 0.5 \phi$$
- **Exact Body Force:**
  $$f_x = - [c_{11} \phi_{xx} + c_{33} \phi_{yy} + 0.5 (c_{12} + c_{33}) \phi_{xy}]$$
  $$f_y = - [0.5 c_{11} \phi_{yy} + 0.5 c_{33} \phi_{xx} + (c_{12} + c_{33}) \phi_{xy}]$$
  where $\phi_{xx} = \left(-\frac{2}{s^2} + \frac{4(x-x_0)^2}{s^4}\right) \phi$, $\phi_{yy} = \left(-\frac{2}{s^2} + \frac{4(y-y_0)^2}{s^4}\right) \phi$, $\phi_{xy} = \frac{4(x-x_0)(y-y_0)}{s^4} \phi$.
- **Exact QoIs:**
  - Computed analytically in closed form via error function $\text{erf}$.

### 2.4 Family 4: Mixed Shear Field (Isotropic)
- **Displacement:**
  $$u_x = k_x x y + k_y y^2, \quad u_y = -k_y x^2 + k_x x y$$
- **Body Force:**
  $$f_x = - [2 c_{33} k_y + (c_{12} + c_{33}) k_x], \quad f_y = 2 c_{33} k_y - (c_{12} + c_{33}) k_x$$
- **Exact QoIs:**
  - Boundary average on $y=1$: $J_{\text{exact}} = -\frac{1}{3} k_y + \frac{1}{2} k_x$.
  - Patch average on $[0.25, 0.75]^2$: $J_{\text{exact}} = 0.25 k_x + \frac{13}{48} k_y$.

### 2.5 Family 5: Multiscale Oscillatory Field
- **Displacement:**
  $$u_x = A (\sin(k_1 \pi x) + \beta \sin(k_2 \pi x)), \quad u_y = A (\cos(k_1 \pi y) + \beta \cos(k_2 \pi y))$$
- **Body Force:**
  $$f_x = c_{11} \pi^2 A [k_1^2 \sin(k_1 \pi x) + \beta k_2^2 \sin(k_2 \pi x)]$$
  $$f_y = c_{11} \pi^2 A [k_1^2 \cos(k_1 \pi y) + \beta k_2^2 \cos(k_2 \pi y)]$$
- **Exact QoIs:**
  - Closed-form exact 1D integrals.

---

## 3. Automated Symbolic Verification Results

All 40 configurations were verified using SymPy in `test_tier1_bvp_symbolic_equilibrium()`:
- Equilibrium residual $\|\mathbf{f} + \nabla \cdot \boldsymbol{\sigma}\| = 0$ holds identically.
- All 40 exact analytical QoI values were compared against SciPy `quad` and `dblquad` numerical quadrature, with absolute differences $< 10^{-11}$.
