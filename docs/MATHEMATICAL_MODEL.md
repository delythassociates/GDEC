# Mathematical Formulation and Error Estimation (v0.1)

## 1. Governing Primal Elasticity Equations

In linear static elasticity over domain $\Omega \subset \mathbb{R}^2$ with boundary $\partial \Omega = \Gamma_D \cup \Gamma_N$:

$$
\nabla \cdot \boldsymbol{\sigma} + \mathbf{b} = \mathbf{0} \quad \text{in } \Omega
$$

$$
\boldsymbol{\epsilon}(\mathbf{u}) = \frac{1}{2}\left(\nabla \mathbf{u} + (\nabla \mathbf{u})^T\right)
$$

$$
\boldsymbol{\sigma} = \mathbf{C} : \boldsymbol{\epsilon}(\mathbf{u})
$$

### Boundary Conditions
- **Essential (Dirichlet)**: $\mathbf{u} = \mathbf{0}$ on $\Gamma_L$ (left clamped vertical edge).
- **Natural (Neumann)**: $\boldsymbol{\sigma} \cdot \mathbf{n} = \mathbf{t}$ on $\Gamma_R$ (right edge), with $\mathbf{t} = [0, -1.0 \times 10^6]^T\text{ Pa}$.

### Constitutive Tensor (Plane Stress)
For plate thickness $t$:

$$
\begin{bmatrix}
\sigma_{xx} \\
\sigma_{yy} \\
\tau_{xy}
\end{bmatrix}
=
\frac{E}{1 - \nu^2}
\begin{bmatrix}
1 & \nu & 0 \\
\nu & 1 & 0 \\
0 & 0 & \frac{1-\nu}{2}
\end{bmatrix}
\begin{bmatrix}
\epsilon_{xx} \\
\epsilon_{yy} \\
2\epsilon_{xy}
\end{bmatrix}
$$

Weak form: Find $\mathbf{u} \in \mathcal{V}$ such that:

$$
a(\mathbf{u}, \mathbf{v}) = l(\mathbf{v}) \quad \forall \mathbf{v} \in \mathcal{V}_0
$$

where:

$$
a(\mathbf{u}, \mathbf{v}) = \int_\Omega \boldsymbol{\sigma}(\mathbf{u}) : \boldsymbol{\epsilon}(\mathbf{v}) \, t \, d\Omega, \quad l(\mathbf{v}) = \int_{\Gamma_R} \mathbf{t} \cdot \mathbf{v} \, t \, d\Gamma
$$

---

## 2. Quantity of Interest (QoI) and Adjoint Problem

The target engineering output is average vertical displacement on the right edge:

$$
J(\mathbf{u}) = \frac{1}{L_b} \int_{\Gamma_R} u_y \, d\Gamma
$$

Because $J(\cdot)$ is linear, there exists a unique discrete load vector $\mathbf{g}$ such that:

$$
J(\mathbf{u}) = \mathbf{g}^T \mathbf{u}
$$

The adjoint (dual) problem seeks $\mathbf{z} \in \mathcal{V}_0$ such that:

$$
a(\mathbf{w}, \mathbf{z}) = J(\mathbf{w}) \quad \forall \mathbf{w} \in \mathcal{V}_0
$$

In matrix form:

$$
\mathbf{K}^T \mathbf{z} = \mathbf{g} \quad \text{subject to } \mathbf{z}|_{\Gamma_L} = \mathbf{0}
$$

Since $\mathbf{K}$ is symmetric, $\mathbf{K} \mathbf{z} = \mathbf{g}$.

---

## 3. Refinement Indicators

### Strategy 1: Uniform Refinement
Globally refines every triangular element $e$:

$$
\eta_e^{\text{unif}} = 1.0
$$

### Strategy 2: Zienkiewicz-Zhu (ZZ) Stress Recovery
Averages centroid stresses $\boldsymbol{\sigma}_e$ to vertices weighted by element area:

$$
\boldsymbol{\sigma}_i^* = \frac{\sum_{e \in \mathcal{N}_i} A_e \boldsymbol{\sigma}_e}{\sum_{e \in \mathcal{N}_i} A_e}
$$

The recovered element stress is $\bar{\boldsymbol{\sigma}}_e^* = \frac{1}{3}\sum_{k=1}^3 \boldsymbol{\sigma}_{i_k}^*$. The local energy error jump is:

$$
\eta_e^{\text{ZZ}} = \sqrt{A_e \, t \, (\bar{\boldsymbol{\sigma}}_e^* - \boldsymbol{\sigma}_e)^T \, \mathbf{C}^{-1} \, (\bar{\boldsymbol{\sigma}}_e^* - \boldsymbol{\sigma}_e)}
$$

### Strategy 3: Goal-Aware Adjoint Sensitivity Heuristic
Measures the local contribution of element $e$ to the error in $J(\mathbf{u})$:

$$
\eta_e^{\text{goal}} = h_e^2 A_e \left| \boldsymbol{\epsilon}_e(\mathbf{u}) : \mathbf{C} : \boldsymbol{\epsilon}_e(\mathbf{z}) \right|
$$

where $h_e = \sqrt{2 A_e}$.

### Cost-Aware Marking Priority
To account for mesh closure cost, the priority measure is:

$$
P_e = \frac{\eta_e^{\text{goal}}}{\Delta \text{Cost}_e}
$$

where $\Delta \text{Cost}_e \approx 4 \text{ to } 6 \text{ DOFs}$.
