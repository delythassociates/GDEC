# GDEC Phase C Amendment 3.1: Mathematical Verification Scope Report

**Finding:** AM31-05 (MEDIUM)  
**Script:** `verification/phase_c/amendment_3_1/verify_tier1_bvps.py`  
**Record:** `results/phase_c_amendment_3_1/tier1_bvp_verification_record.json`  
**Test:** `tests/test_phase_c_amendment_3_1.py` (A31-T15)  
**Status:** FULLY VERIFIED & PROVEN  

---

## 1. Distinction: BVP Verification vs. QoI Quadrature Concordance

In previous amendments, mathematical verification primarily checked whether analytical QoI values agreed with numerical quadrature (SciPy `quad`/`dblquad`). While this establishes that the target functional $J(u)$ was integrated accurately, it does **not** prove that the underlying field $u$ solves the linear elasticity boundary-value problem.

Amendment 3.1 formally establishes and distinguishes two separate verification levels:

```mermaid
flowchart LR
    subgraph Level 1: Complete BVP Verification
        A[Displacement Field u] --> B[Kinematic Strains eps = sym grad u]
        B --> C[Hooke's Law sigma = C : eps]
        C --> D[Equilibrium PDE: div sigma + f == 0]
        E[Dirichlet BCs: u = u_exact on dOmega] --> F[Well-Posed Boundary Value Problem]
        D --> F
    end

    subgraph Level 2: QoI Quadrature Concordance
        F --> G[Quantity of Interest Functional J u]
        G --> H[Analytical Closed Form vs SciPy High-Precision Quad]
    end

    Level 1 --> I{Overall Verified}
    Level 2 --> I
```

1. **Complete BVP Mathematical Verification:**
   - Kinematics: $\boldsymbol{\epsilon} = \frac{1}{2}(\nabla \mathbf{u} + (\nabla \mathbf{u})^T)$.
   - Constitutive: $\boldsymbol{\sigma} = \mathbf{C} : \boldsymbol{\epsilon}$ (plane stress / plane strain isotropic tensor).
   - Governing PDE: $-\nabla \cdot \boldsymbol{\sigma} = \mathbf{f}$ across domain $\Omega = [0, 1]^2$.
   - Boundary Data: $\mathbf{u}|_{\partial \Omega} = \mathbf{u}^{\text{exact}}|_{\partial \Omega}$ on all 4 boundaries (bottom, top, left, right).
2. **QoI Quadrature Concordance:**
   - Numerical integration agreement: $|J_{\text{analytical}} - J_{\text{quadrature}}| < 10^{-11}$.

---

## 2. Mathematical Proof of Equilibrium for All 5 Families

In isotropic linear elasticity, the constitutive matrix $\mathbf{C}$ satisfies:
$$C_{33} = G = \frac{E}{2(1 + \nu)}$$
Under plane stress:
$$C_{11} = \frac{E}{1 - \nu^2}, \quad C_{12} = \frac{\nu E}{1 - \nu^2} \implies C_{11} - C_{12} = \frac{E(1 - \nu)}{1 - \nu^2} = \frac{E}{1 + \nu} = 2 C_{33}$$
Under plane strain:
$$C_{11} = \frac{E(1 - \nu)}{(1 + \nu)(1 - 2\nu)}, \quad C_{12} = \frac{\nu E}{(1 + \nu)(1 - 2\nu)} \implies C_{11} - C_{12} = \frac{E(1 - 2\nu)}{(1 + \nu)(1 - 2\nu)} = 2 C_{33}$$
Thus, for all isotropic 2D elasticity problems:
$$C_{11} - C_{12} - 2 C_{33} \equiv 0$$

### Family 1: Polynomial Field (Configs T1_01 – T1_08)
- Displacements: $u_x = a x^2 + b y^2$, $u_y = a x y$.
- Strains: $\epsilon_{xx} = 2 a x$, $\epsilon_{yy} = a x$, $\gamma_{xy} = (a + 2 b) y$.
- Stresses: $\sigma_{xx} = a(2 C_{11} + C_{12}) x$, $\sigma_{yy} = a(2 C_{12} + C_{11}) x$, $\tau_{xy} = C_{33}(a + 2 b) y$.
- Divergence:
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = a(2 C_{11} + C_{12}) + C_{33}(a + 2 b)$$
  $$\partial_x \tau_{xy} + \partial_y \sigma_{yy} = 0$$
- Body Force: $f_x = -a(2 C_{11} + C_{12}) - C_{33}(a + 2 b)$, $f_y = 0$.
- Equilibrium Residual: $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$.

### Family 2: Trigonometric Field (Configs T1_09 – T1_16)
- Displacements: $u_x = A \sin(\omega x) \cos(\omega y)$, $u_y = A \cos(\omega x) \sin(\omega y)$, with $\omega = f \pi$.
- Strains: $\epsilon_{xx} = A \omega \cos(\omega x) \cos(\omega y)$, $\epsilon_{yy} = A \omega \cos(\omega x) \cos(\omega y)$, $\gamma_{xy} = -2 A \omega \sin(\omega x) \sin(\omega y)$.
- Stresses: $\sigma_{xx} = (C_{11} + C_{12}) A \omega \cos(\omega x) \cos(\omega y)$, $\tau_{xy} = -2 C_{33} A \omega \sin(\omega x) \sin(\omega y)$.
- Divergence:
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = -(C_{11} + C_{12} + 2 C_{33}) A \omega^2 \sin(\omega x) \cos(\omega y)$$
  Using $C_{11} - C_{12} = 2 C_{33}$, the factor simplifies: $C_{11} + C_{12} + 2 C_{33} = 2 C_{11}$.
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = -2 C_{11} A \omega^2 \sin(\omega x) \cos(\omega y)$$
- Body Force: $f_x = 2 C_{11} \omega^2 A \sin(\omega x) \cos(\omega y)$, $f_y = 2 C_{11} \omega^2 A \cos(\omega x) \sin(\omega y)$.
- Equilibrium Residual: $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$.

### Family 3: Localized Gaussian Field (Configs T1_17 – T1_24)
- Let $\phi(x, y) = A \exp\left(-\frac{(x - x_0)^2 + (y - y_0)^2}{\sigma^2}\right)$.
- Displacements: $u_x = \phi$, $u_y = \frac{1}{2} \phi$.
- Strains: $\epsilon_{xx} = \phi_x$, $\epsilon_{yy} = \frac{1}{2} \phi_y$, $\gamma_{xy} = \phi_y + \frac{1}{2} \phi_x$.
- Stresses: $\sigma_{xx} = C_{11} \phi_x + \frac{1}{2} C_{12} \phi_y$, $\sigma_{yy} = C_{12} \phi_x + \frac{1}{2} C_{11} \phi_y$, $\tau_{xy} = C_{33}(\phi_y + \frac{1}{2} \phi_x)$.
- Divergence:
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = C_{11} \phi_{xx} + C_{33} \phi_{yy} + \frac{1}{2}(C_{12} + C_{33}) \phi_{xy}$$
  $$\partial_x \tau_{xy} + \partial_y \sigma_{yy} = \frac{1}{2} C_{11} \phi_{yy} + \frac{1}{2} C_{33} \phi_{xx} + (C_{12} + C_{33}) \phi_{xy}$$
- Body Force: $\mathbf{f} = -\nabla \cdot \boldsymbol{\sigma}$.
- Equilibrium Residual: $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$.

### Family 4: Mixed Shear Field (Configs T1_25 – T1_32)
- Displacements: $u_x = k_x x y + k_y y^2$, $u_y = -k_y x^2 + k_x x y$.
- Strains: $\epsilon_{xx} = k_x y$, $\epsilon_{yy} = k_x x$, $\gamma_{xy} = (k_x - 2 k_y) x + (k_x + 2 k_y) y$.
- Divergence:
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = C_{12} k_x + C_{33}(k_x + 2 k_y) = (C_{12} + C_{33}) k_x + 2 C_{33} k_y$$
  $$\partial_x \tau_{xy} + \partial_y \sigma_{yy} = C_{33}(k_x - 2 k_y) + C_{12} k_x = (C_{12} + C_{33}) k_x - 2 C_{33} k_y$$
- Body Force: $f_x = -(C_{12} + C_{33}) k_x - 2 C_{33} k_y$, $f_y = 2 C_{33} k_y - (C_{12} + C_{33}) k_x$.
- Equilibrium Residual: $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$.

### Family 5: Multiscale Oscillatory Field (Configs T1_33 – T1_40)
- Displacements: $u_x = A (\sin(k_1 \pi x) + \beta \sin(k_2 \pi x))$, $u_y = A (\cos(k_1 \pi y) + \beta \cos(k_2 \pi y))$.
- Strains: $\epsilon_{xx} = \partial_x u_x(x)$, $\epsilon_{yy} = \partial_y u_y(y)$, $\gamma_{xy} = 0$.
- Stresses: $\tau_{xy} = 0$.
- Divergence:
  $$\partial_x \sigma_{xx} + \partial_y \tau_{xy} = C_{11} \partial_{xx} u_x = -C_{11} \pi^2 A (k_1^2 \sin(k_1 \pi x) + \beta k_2^2 \sin(k_2 \pi x))$$
  $$\partial_x \tau_{xy} + \partial_y \sigma_{yy} = C_{11} \partial_{yy} u_y = -C_{11} \pi^2 A (k_1^2 \cos(k_1 \pi y) + \beta k_2^2 \cos(k_2 \pi y))$$
- Body Force: $f_x = -C_{11} \partial_{xx} u_x$, $f_y = -C_{11} \partial_{yy} u_y$.
- Equilibrium Residual: $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$.

---

## 3. Comprehensive Tier 1 Verification Summary (40 Configurations)

| Family | Config IDs | Symbolic Equilibrium | Numerical Residual ($\|\mathcal{R}\| / \|\boldsymbol{\sigma}\|$) | Boundary Conditions | QoI Concordance | BVP Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Family 1 (Polynomial)** | T1_01 – T1_08 | `EXACT 0` | $< 10^{-16}$ | 4 boundaries verified | $< 10^{-12}$ | **VERIFIED** |
| **Family 2 (Trigonometric)** | T1_09 – T1_16 | `EXACT 0` | $< 10^{-14}$ | 4 boundaries verified | $< 10^{-12}$ | **VERIFIED** |
| **Family 3 (Gaussian)** | T1_17 – T1_24 | `EXACT 0` | $< 10^{-15}$ | 4 boundaries verified | $< 10^{-12}$ | **VERIFIED** |
| **Family 4 (Mixed Shear)** | T1_25 – T1_32 | `EXACT 0` | $< 10^{-16}$ | 4 boundaries verified | $< 10^{-12}$ | **VERIFIED** |
| **Family 5 (Multiscale)** | T1_33 – T1_40 | `EXACT 0` | $< 10^{-15}$ | 4 boundaries verified | $< 10^{-12}$ | **VERIFIED** |

**Summary Totals:**
- Total Configurations Audited: 40/40
- Complete BVP Mathematical Verification Passed: 40/40 (100.0%)
- QoI Numerical Quadrature Concordance Passed: 40/40 (100.0%)
- Fully Verified Configurations: 40/40 (100.0%)
- Full machine-readable record: `results/phase_c_amendment_3_1/tier1_bvp_verification_record.json`.
