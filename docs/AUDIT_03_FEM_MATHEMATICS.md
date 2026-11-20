# GDEC Audit Phase 3: FEM Mathematical Formulation & Mesh Integrity Audit

**Audit Date**: 2026-11-20  
**Auditor**: Independent Technical Software Auditor & Verification Specialist  
**Target Codebase**: GDEC Version 0.2 (`src/gdec/fem/elasticity.py`, `src/gdec/fem/mesh.py`)  
**Status**: VERIFIED  

---

## 1. Executive Summary

An independent mathematical derivation and numerical forensic analysis was conducted on the 2D linear elasticity continuum formulation, element bilinear form quadrature, sparse matrix assembly, Dirichlet boundary condensation, and red-green mesh refinement routines.

The finite-element implementation is **mathematically sound, strictly symmetric, positive definite on unconstrained DOFs, and satisfies physical equilibrium and constant-strain patch tests to machine precision**.

---

## 2. Mathematical Formulation Review

### 2.1 Constitutive Tensor (`ConstitutiveTensor`)
The constitutive law relates stress $\boldsymbol{\sigma}$ to strain $\boldsymbol{\varepsilon}$:

$$\begin{bmatrix} \sigma_{11} \\ \sigma_{22} \\ \sigma_{12} \end{bmatrix} = \begin{bmatrix} c_{11} & c_{12} & 0 \\ c_{12} & c_{11} & 0 \\ 0 & 0 & c_{33} \end{bmatrix} \begin{bmatrix} \varepsilon_{11} \\ \varepsilon_{22} \\ 2\varepsilon_{12} \end{bmatrix}$$

- **Plane Stress ($t \ll L, H$)**:
  $$c_{11} = \frac{E}{1 - \nu^2}, \quad c_{12} = \frac{\nu E}{1 - \nu^2}, \quad c_{33} = G = \frac{E}{2(1 + \nu)}$$
  *Audit Verification*: Lines 36–38 of `src/gdec/fem/elasticity.py` match the exact theoretical equations.
- **Plane Strain**:
  $$\lambda = \frac{E \nu}{(1 + \nu)(1 - 2\nu)}, \quad \mu = \frac{E}{2(1 + \nu)}, \quad c_{11} = \lambda + 2\mu, \quad c_{12} = \lambda, \quad c_{33} = \mu$$
  *Audit Verification*: Lines 40–44 of `src/gdec/fem/elasticity.py` match the exact Lamé parameters.

### 2.2 Bilinear Form and Stiffness Assembly
The internal virtual work for thickness $t$ is:

$$a(\mathbf{u}, \mathbf{v}) = t \int_\Omega \boldsymbol{\sigma}(\mathbf{u}) : \boldsymbol{\varepsilon}(\mathbf{v}) \, d\Omega = t \int_\Omega \left( \sigma_{11} \varepsilon_{11}(\mathbf{v}) + \sigma_{22} \varepsilon_{22}(\mathbf{v}) + 2 \sigma_{12} \varepsilon_{12}(\mathbf{v}) \right) d\Omega$$

In `src/gdec/fem/elasticity.py` (lines 101–106):
```python
sig_11 = c11 * eps_u[0, 0] + c12 * eps_u[1, 1]
sig_22 = c12 * eps_u[0, 0] + c11 * eps_u[1, 1]
sig_12 = 2.0 * c33 * eps_u[0, 1]
return thickness * (
    sig_11 * eps_v[0, 0] + sig_22 * eps_v[1, 1] + 2.0 * sig_12 * eps_v[0, 1]
)
```
*Mathematical Verification*: Because tensorial shear strain $\varepsilon_{12} = \frac{1}{2}\gamma_{12}$, the shear stress is $\sigma_{12} = 2 c_{33} \varepsilon_{12}$. In the virtual work integrand, double contraction produces $2 \sigma_{12} \varepsilon_{12}(\mathbf{v}) = 4 c_{33} \varepsilon_{12}(\mathbf{u}) \varepsilon_{12}(\mathbf{v}) = G \gamma_{12}(\mathbf{u}) \gamma_{12}(\mathbf{v})$. The implementation is verified to be exact.

---

## 3. Independent Numerical Verification Tests

Tests were executed using independent scripts (`scratch/fem_math_audit.py`):

### 3.1 Stiffness Matrix Symmetry
- **Equation**: $\|\mathbf{K} - \mathbf{K}^T\|_\infty$
- **Measured**: **`0.0`** (exact floating-point symmetry).

### 3.2 Positive Definiteness
- **Test**: Minimum eigenvalue of condensed stiffness matrix $\mathbf{K}_{FF}$.
- **Measured**: $\lambda_{\min} = 17.376 > 0$. Strictly positive definite.

### 3.3 Constant Strain Patch Tests
- **Pure Shear**: Linear displacement field $u_x = \gamma_0 y$, $u_y = 0$ with $\gamma_0 = 0.01$.
  - Theoretical strain energy: $U = \frac{1}{2} G \gamma_0^2 A t = 0.0200000000$ J.
  - Finite Element energy $\frac{1}{2}\mathbf{u}^T \mathbf{K} \mathbf{u} = 0.0200000000$ J.
  - Relative discrepancy: **$4.16 \times 10^{-15}$**.
- **Pure Uniaxial Tension**: $u_x = \varepsilon_0 x$, $u_y = -\nu \varepsilon_0 y$ with $\varepsilon_0 = 0.005$.
  - Theoretical strain energy: $U = \frac{1}{2} E \varepsilon_0^2 A t = 0.0125000000$ J.
  - Finite Element energy $\frac{1}{2}\mathbf{u}^T \mathbf{K} \mathbf{u} = 0.0125000000$ J.
  - Relative discrepancy: **$1.80 \times 10^{-15}$**.

### 3.4 Static Reaction Equilibrium
On `CantileverDemo` under transverse tip traction $t_y = -1.0\text{ MPa}$ ($F_y = -10,000$ N):
- Reaction vector $\mathbf{R} = \mathbf{K}\mathbf{u} - \mathbf{f}$.
- Sum of horizontal reactions $\sum R_x = -2.11 \times 10^{-10}$ N.
- Sum of vertical reactions $\sum R_y = +9,999.9999999971$ N.
- Total net equilibrium balance $\left|\sum R_y + F_{y,\text{applied}}\right| = \mathbf{2.86 \times 10^{-9}}$ N.
- Relative residual: $\mathbf{2.86 \times 10^{-13}}$.

---

## 4. Mesh Topology & Refinement Conformance Audit

Audited via `scratch/mesh_audit.py` across 5 consecutive adaptive refinement cycles:
1. **Geometric Area Conservation**: Initial domain area $A = 2.0 \times 0.5 = 1.0\text{ m}^2$. After 5 refinement cycles (16,924 elements), total area $| \sum A_e - 1.0 | < 10^{-12}\text{ m}^2$. Zero area loss or domain shrinkage.
2. **Element Jacobians & Non-Degeneracy**: Minimum element area across all cycles remained strictly positive ($A_e > 0$). Zero inverted or degenerate triangles.
3. **Conforming Red-Green Closure**: Mesh bisection uses `skfem.MeshTri.refined(marked)`, which automatically applies green closure splits to neighboring non-marked triangles, eliminating hanging nodes and preserving $H^1$-conformity.
4. **Boundary Predicate Preservation**: Left fixed boundary facets doubled predictably under local root refinement (4 $\to$ 8 $\to$ 16 $\to$ 32 $\to$ 64 $\to$ 128 facets) without boundary detachment or orphan nodes.

---

## 5. Audit Verdict: FEM Mathematical Formulation
- **Severity**: PASS (No issues found).
- **Mathematical Integrity**: **VERIFIED**.
