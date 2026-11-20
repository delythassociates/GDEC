# GDEC Numerical Methods & Mathematics (v0.2.2)

## 1. Linear Elasticity Formulation

### Governing Equations
Over a bounded 2D domain $\Omega \subset \mathbb{R}^2$ with boundary $\partial \Omega = \Gamma_D \cup \Gamma_N$:
$$\nabla \cdot \boldsymbol{\sigma} + \mathbf{b} = \mathbf{0} \quad \text{in } \Omega$$
$$\boldsymbol{\epsilon}(\mathbf{u}) = \frac{1}{2}(\nabla \mathbf{u} + (\nabla \mathbf{u})^T)$$
$$\boldsymbol{\sigma} = \mathbf{C} : \boldsymbol{\epsilon}(\mathbf{u})$$

### Constitutive Law (Plane Stress)
For an isotropic material with thickness $t$:
$$\begin{bmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \tau_{xy} \end{bmatrix} = \frac{E}{1 - \nu^2} \begin{bmatrix} 1 & \nu & 0 \\ \nu & 1 & 0 \\ 0 & 0 & \frac{1-\nu}{2} \end{bmatrix} \begin{bmatrix} \epsilon_{xx} \\ \epsilon_{yy} \\ 2\epsilon_{xy} \end{bmatrix}$$

### Weak Form
Find $\mathbf{u} \in \mathcal{V}$ such that:
$$a(\mathbf{u}, \mathbf{v}) = l(\mathbf{v}) \quad \forall \mathbf{v} \in \mathcal{V}_0$$
where:
$$a(\mathbf{u}, \mathbf{v}) = \int_\Omega \boldsymbol{\sigma}(\mathbf{u}) : \boldsymbol{\epsilon}(\mathbf{v}) \, t \, d\Omega, \quad l(\mathbf{v}) = \int_{\Gamma_N} \mathbf{t} \cdot \mathbf{v} \, t \, d\Gamma$$

## 2. Finite Element Discretization

- **Element Type**: Linear 3-node triangular elements (P1, `skfem.ElementVectorH1(skfem.ElementTriP1())`).
- **Assembly**: Vectorized element stiffness matrices assembled into SciPy CSC sparse matrices.
- **Dirichlet Boundary Conditions**: Enforced via matrix condensation (eliminating constrained DOFs).
- **Direct Solver**: Sparse LU factorization via `scipy.sparse.linalg.splu` (SuperLU engine).

## 3. Adjoint Analysis & QoI Sensitivity

### Quantity of Interest
The target engineering QoI is the average vertical displacement on the right edge:
$$J(\mathbf{u}) = \frac{1}{L_{\Gamma}} \int_{\Gamma_R} u_y \, d\Gamma$$

### Dual Problem
Because $J(\mathbf{v})$ is a bounded linear functional, there exists a discrete adjoint load vector $\mathbf{g}$ such that $J(\mathbf{v}) = \mathbf{g}^T \mathbf{v}$. The adjoint solution $\mathbf{z}$ satisfies:
$$\mathbf{K}^T \mathbf{z} = \mathbf{g}$$
Since $\mathbf{K}$ is symmetric ($\mathbf{K} = \mathbf{K}^T$), the stiffness matrix is identical to the primal system, allowing factorization reuse.

## 4. Richardson Extrapolation & GCI

To obtain an objective continuum reference from a sequence of discrete meshes $M_1, M_2, M_3$:
- **Apparent Order of Convergence ($p$)**:
  $$p = \frac{\ln|\epsilon_{32}/\epsilon_{21}| + q(p)}{\ln(r_{21})}$$
- **Extrapolated Continuum Solution ($J_\infty$)**:
  $$J_\infty = J_1 + \frac{J_1 - J_2}{r_{21}^p - 1}$$
- **Grid Convergence Index (GCI)**:
  $$\text{GCI}_{21} = \frac{F_s |e_{a,21}|}{r_{21}^p - 1}$$
  where $F_s = 1.25$ is the ASME safety factor for 3-level convergence studies.

In GDEC v0.2.2, the primary continuum reference is established via the Celik unequal-ratio formulation ($J_{\infty,\text{Celik}} = -1.909525\text{ mm}$, $\text{GCI} = 0.0983\%$) with the Roache mean-ratio formulation retained as a sensitivity check ($J_{\infty,\text{Roache}} = -1.909240\text{ mm}$, $\text{GCI} = 0.0796\%$).
