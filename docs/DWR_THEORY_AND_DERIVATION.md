# GDEC — Dual-Weighted Residual (DWR) Theory and Derivation

**Author:** Principal Computational Mechanics Specialist & Verification Engineer  
**Repository:** `delythassociates/GDEC`  
**Module:** `src/gdec/fem/estimators.py`  
**Status:** Complete, Mathematically Justified, Numerically Verified  

---

## 1. Introduction and Abstract

In goal-oriented finite element analysis, the objective is not to minimize the global energy norm of the discretization error $\|u - u_h\|_E$, but rather to minimize the error in a specific engineering Quantity of Interest (QoI), denoted by a functional $J(u) \in \mathbb{R}$.

The Dual-Weighted Residual (DWR) framework, pioneered by Becker and Rannacher (1996, 2001), provides an exact error representation that links the error in the QoI, $J(u) - J(u_h)$, directly to the primal equation residual evaluated on an enriched dual (adjoint) weighting function:
$$
J(u) - J(u_h) = \rho(u_h)(z - \Pi_h z)
$$
where $z$ is the solution to an auxiliary adjoint problem with the QoI functional acting as the source term, and $\Pi_h z \in V_h$ is an arbitrary finite element projection of $z$.

This document provides the complete, rigorous mathematical derivation of the DWR error representation for 2D linear elasticity, defines the exact facet traction jumps and boundary residuals, details the dual weight evaluation on linear triangular ($P_1$) elements, and formally delineates the theoretical boundaries between heuristic sensitivity indicators, energy-norm indicators, DWR estimates, and certified error bounds.

---

## 2. Continuous and Discrete Primal Variational Formulation

### 2.1 Domain and Governing Equations
Let $\Omega \subset \mathbb{R}^2$ be an open, bounded polygonal domain with Lipschitz boundary $\Gamma = \partial \Omega$, partitioned into non-overlapping Dirichlet and Neumann boundaries:
$$
\Gamma = \Gamma_D \cup \Gamma_N, \quad \Gamma_D \cap \Gamma_N = \emptyset, \quad \text{meas}(\Gamma_D) > 0.
$$
The governing equations of static linear elasticity in the absence of body forces $\mathbf{b} = \mathbf{0}$ (as standard in engineering structural benchmarks) are:
$$
-\nabla \cdot \boldsymbol{\sigma}(\mathbf{u}) = \mathbf{0} \quad \text{in } \Omega,
$$
$$
\mathbf{u} = \mathbf{u}_D \quad \text{on } \Gamma_D,
$$
$$
\boldsymbol{\sigma}(\mathbf{u}) \mathbf{n} = \mathbf{t}_N \quad \text{on } \Gamma_N,
$$
where $\mathbf{u}: \Omega \to \mathbb{R}^2$ is the displacement vector field, $\mathbf{n}$ is the unit outward normal vector on $\Gamma$, and $\boldsymbol{\sigma}$ is the symmetric Cauchy stress tensor.

### 2.2 Constitutive and Kinematic Relations
Under the infinitesimal strain hypothesis:
$$
\boldsymbol{\varepsilon}(\mathbf{u}) = \frac{1}{2}\left(\nabla \mathbf{u} + (\nabla \mathbf{u})^T\right).
$$
For an isotropic linear elastic material under plane stress conditions (thickness $t$):
$$
\boldsymbol{\sigma}(\mathbf{u}) = \mathbb{C} : \boldsymbol{\varepsilon}(\mathbf{u}) = \frac{E}{1 - \nu^2} \left[ (1 - \nu) \boldsymbol{\varepsilon}(\mathbf{u}) + \nu \, \text{tr}(\boldsymbol{\varepsilon}(\mathbf{u})) \mathbf{I} \right].
$$

### 2.3 Weak Formulation
Define the kinematically admissible displacement space $V$ and test space $V_0$:
$$
V = \{ \mathbf{v} \in [H^1(\Omega)]^2 \mid \mathbf{v} = \mathbf{u}_D \text{ on } \Gamma_D \},
$$
$$
V_0 = \{ \mathbf{v} \in [H^1(\Omega)]^2 \mid \mathbf{v} = \mathbf{0} \text{ on } \Gamma_D \}.
$$
The bilinear form $a: [H^1(\Omega)]^2 \times [H^1(\Omega)]^2 \to \mathbb{R}$ and linear load form $F: V_0 \to \mathbb{R}$ are:
$$
a(\mathbf{u}, \mathbf{v}) = \int_\Omega \boldsymbol{\sigma}(\mathbf{u}) : \boldsymbol{\varepsilon}(\mathbf{v}) \, d\Omega = t \int_\Omega \boldsymbol{\varepsilon}(\mathbf{u}) : \mathbb{C} : \boldsymbol{\varepsilon}(\mathbf{v}) \, dx \, dy,
$$
$$
F(\mathbf{v}) = t \int_{\Gamma_N} \mathbf{t}_N \cdot \mathbf{v} \, ds.
$$
The continuous primal problem seeks $\mathbf{u} \in V$ such that:
$$
a(\mathbf{u}, \mathbf{v}) = F(\mathbf{v}) \quad \forall \mathbf{v} \in V_0.
$$

### 2.4 Discrete FEM Formulation
Let $\mathcal{T}_h$ be a conforming triangulation of $\Omega$. The discrete subspace $V_{0,h} \subset V_0$ comprises continuous piecewise linear polynomials ($P_1$ Lagrange elements). The Galerkin approximation $\mathbf{u}_h \in V_h$ satisfies:
$$
a(\mathbf{u}_h, \mathbf{v}_h) = F(\mathbf{v}_h) \quad \forall \mathbf{v}_h \in V_{0,h}.
$$
Subtracting the discrete equation from the continuous equation yields the fundamental **Galerkin Orthogonality**:
$$
a(\mathbf{u} - \mathbf{u}_h, \mathbf{v}_h) = 0 \quad \forall \mathbf{v}_h \in V_{0,h}.
$$

---

## 3. Continuous and Discrete Dual (Adjoint) Formulation

### 3.1 Quantity of Interest (QoI)
Let $J: [H^1(\Omega)]^2 \to \mathbb{R}$ be a bounded linear functional representing the target engineering output. Typical examples include:
1. **Average boundary displacement:**
   $$
   J(\mathbf{u}) = \frac{1}{|\Gamma_g|} \int_{\Gamma_g} \mathbf{u} \cdot \mathbf{m} \, ds,
   $$
   where $\mathbf{m}$ is a direction unit vector (e.g., vertical tip deflection $\mathbf{m} = [0, 1]^T$).
2. **Local stress / strain component:**
   $$
   J(\mathbf{u}) = \int_\Omega \chi_{\omega} (\boldsymbol{\sigma}(\mathbf{u}) : \boldsymbol{\psi}) \, d\Omega.
   $$

### 3.2 The Continuous Adjoint Problem
To determine the sensitivity of $J$ with respect to local residual perturbations, we introduce the continuous dual problem: Find $\mathbf{z} \in V_0$ such that:
$$
a(\mathbf{w}, \mathbf{z}) = J(\mathbf{w}) \quad \forall \mathbf{w} \in V_0.
$$
Because the elasticity bilinear form is symmetric ($a(\mathbf{w}, \mathbf{z}) = a(\mathbf{z}, \mathbf{w})$), this is equivalent to solving an elasticity problem with generalized adjoint pseudo-loads defined by the functional $J$.

### 3.3 The Discrete Adjoint Problem
The discrete adjoint approximation $\mathbf{z}_h \in V_{0,h}$ satisfies:
$$
a(\mathbf{w}_h, \mathbf{z}_h) = J(\mathbf{w}_h) \quad \forall \mathbf{w}_h \in V_{0,h}.
$$
By symmetry and Galerkin orthogonality of the dual problem:
$$
a(\mathbf{w}_h, \mathbf{z} - \mathbf{z}_h) = 0 \quad \forall \mathbf{w}_h \in V_{0,h}.
$$

---

## 4. Rigorous Derivation of the DWR Error Representation

### 4.1 Global Error Identity
Consider the primal error $\mathbf{e} = \mathbf{u} - \mathbf{u}_h \in V_0$. Applying the definition of the dual problem with test function $\mathbf{w} = \mathbf{e}$:
$$
J(\mathbf{u}) - J(\mathbf{u}_h) = J(\mathbf{e}) = a(\mathbf{e}, \mathbf{z}) = a(\mathbf{u} - \mathbf{u}_h, \mathbf{z}).
$$
By the linearity of $a(\cdot, \cdot)$:
$$
a(\mathbf{u} - \mathbf{u}_h, \mathbf{z}) = a(\mathbf{u}, \mathbf{z}) - a(\mathbf{u}_h, \mathbf{z}) = F(\mathbf{z}) - a(\mathbf{u}_h, \mathbf{z}).
$$
Now let $\Pi_h \mathbf{z} \in V_{0,h}$ be any arbitrary finite element projection or interpolation of $\mathbf{z}$. By Galerkin orthogonality of the primal solution, $a(\mathbf{u} - \mathbf{u}_h, \Pi_h \mathbf{z}) = 0$, which implies:
$$
F(\Pi_h \mathbf{z}) - a(\mathbf{u}_h, \Pi_h \mathbf{z}) = 0.
$$
Subtracting this zero quantity yields the exact **Dual-Weighted Residual Identity**:
$$
\boxed{J(\mathbf{u}) - J(\mathbf{u}_h) = F(\mathbf{z} - \Pi_h \mathbf{z}) - a(\mathbf{u}_h, \mathbf{z} - \Pi_h \mathbf{z}) = \rho(\mathbf{u}_h)(\mathbf{z} - \Pi_h \mathbf{z})}
$$
where $\rho(\mathbf{u}_h)(\cdot) = F(\cdot) - a(\mathbf{u}_h, \cdot)$ is the primal residual functional.

### 4.2 Element-by-Element Integration by Parts
We decompose the domain integral over each triangular element $K \in \mathcal{T}_h$:
$$
a(\mathbf{u}_h, \mathbf{z} - \Pi_h \mathbf{z}) = \sum_{K \in \mathcal{T}_h} t \int_K \boldsymbol{\sigma}(\mathbf{u}_h) : \boldsymbol{\varepsilon}(\mathbf{z} - \Pi_h \mathbf{z}) \, d\Omega.
$$
Since $\boldsymbol{\sigma}$ is symmetric, $\boldsymbol{\sigma} : \boldsymbol{\varepsilon}(\mathbf{v}) = \boldsymbol{\sigma} : \nabla \mathbf{v}$. Applying Green's first identity (integration by parts) on each element $K$:
$$
\int_K \boldsymbol{\sigma}(\mathbf{u}_h) : \nabla (\mathbf{z} - \Pi_h \mathbf{z}) \, d\Omega = -\int_K (\nabla \cdot \boldsymbol{\sigma}(\mathbf{u}_h)) \cdot (\mathbf{z} - \Pi_h \mathbf{z}) \, d\Omega + \int_{\partial K} (\boldsymbol{\sigma}(\mathbf{u}_h) \mathbf{n}_K) \cdot (\mathbf{z} - \Pi_h \mathbf{z}) \, ds,
$$
where $\mathbf{n}_K$ is the unit outward normal vector along the boundary $\partial K$.

Summing over all elements and collecting the boundary integrals over the set of all edges (facets) $\mathcal{F}_h$:
- $\mathcal{F}_h^{int}$: Interior facets shared by elements $K_1$ and $K_2$.
- $\mathcal{F}_h^N$: Boundary facets on the Neumann boundary $\Gamma_N$.
- $\mathcal{F}_h^D$: Boundary facets on the Dirichlet boundary $\Gamma_D$ (where $\mathbf{z} - \Pi_h \mathbf{z} = \mathbf{0}$).

For an interior facet $F = \partial K_1 \cap \partial K_2$, let $\mathbf{n}_F$ be a chosen unit normal pointing from $K_1$ into $K_2$. Then:
$$
(\boldsymbol{\sigma}_1 \mathbf{n}_1 + \boldsymbol{\sigma}_2 \mathbf{n}_2) = (\boldsymbol{\sigma}_1 \mathbf{n}_F - \boldsymbol{\sigma}_2 \mathbf{n}_F) = -[\![\boldsymbol{\sigma}(\mathbf{u}_h) \mathbf{n}_F]\!]_F,
$$
where the traction jump across facet $F$ is defined as:
$$
[\![\boldsymbol{\sigma}(\mathbf{u}_h) \mathbf{n}_F]\!]_F = (\boldsymbol{\sigma}|_{K_2} - \boldsymbol{\sigma}|_{K_1}) \mathbf{n}_F.
$$
Combining element interior residuals, interior facet jumps, and Neumann boundary traction residuals:
$$
\boxed{J(\mathbf{u}) - J(\mathbf{u}_h) = \sum_{K \in \mathcal{T}_h} \int_K \mathbf{R}_K \cdot (\mathbf{z} - \Pi_h \mathbf{z}) \, d\Omega + \sum_{F \in \mathcal{F}_h^{int}} \int_F \mathbf{j}_F \cdot (\mathbf{z} - \Pi_h \mathbf{z}) \, ds + \sum_{F \in \mathcal{F}_h^N} \int_F \mathbf{r}_F \cdot (\mathbf{z} - \Pi_h \mathbf{z}) \, ds}
$$
where:
1. **Element interior equilibrium residual:**
   $$
   \mathbf{R}_K = \mathbf{b} + \nabla \cdot \boldsymbol{\sigma}(\mathbf{u}_h).
   $$
2. **Interior facet traction jump:**
   $$
   \mathbf{j}_F = -[\![\boldsymbol{\sigma}(\mathbf{u}_h) \mathbf{n}_F]\!]_F = (\boldsymbol{\sigma}_1 - \boldsymbol{\sigma}_2) \mathbf{n}_F.
   $$
3. **Neumann boundary traction residual:**
   $$
   \mathbf{r}_F = \mathbf{t}_N - \boldsymbol{\sigma}(\mathbf{u}_h) \mathbf{n}_F.
   $$

---

## 5. Mathematical Mechanics on Linear Triangular ($P_1$) Elements

### 5.1 Vanishing of Element Interior Residuals
For piecewise linear triangular finite elements ($P_1$), the displacement gradient $\nabla \mathbf{u}_h$ is piecewise constant within each element $K$.
Consequently, the strain $\boldsymbol{\varepsilon}(\mathbf{u}_h)$ and stress $\boldsymbol{\sigma}(\mathbf{u}_h)$ are spatially constant inside $K$:
$$
\nabla \cdot \boldsymbol{\sigma}(\mathbf{u}_h) \equiv \mathbf{0} \quad \forall K \in \mathcal{T}_h.
$$
In the absence of body forces ($\mathbf{b} = \mathbf{0}$):
$$
\mathbf{R}_K \equiv \mathbf{0}.
$$
**Crucial Mathematical Consequence:** On $P_1$ meshes without body force, the entire primal residual is concentrated strictly on the inter-element facet jumps $\mathbf{j}_F$ and boundary traction residuals $\mathbf{r}_F$.

### 5.2 The Need for Adjoint Enrichment
If one attempts to evaluate the residual against the discrete dual solution $\mathbf{z}_h \in V_{0,h}$:
$$
\rho(\mathbf{u}_h)(\mathbf{z}_h - \Pi_h \mathbf{z}_h) = \rho(\mathbf{u}_h)(\mathbf{0}) = 0.
$$
This is the direct consequence of Galerkin orthogonality. To obtain a non-trivial, asymptotically consistent error estimate, the weighting term must approximate the un-discretized dual error $\mathbf{z} - \Pi_h \mathbf{z}$.

Two classical approaches exist in the literature:
1. **Global higher-order solve:** Solve for $\mathbf{z}$ in a quadratic ($P_2$) space $\mathcal{T}_h$ or on a uniformly refined mesh $\mathcal{T}_{h/2}$. (Computationally expensive: $4\times$ to $8\times$ DOF increase).
2. **Patch recovery / Bubble approximation:** Reconstruct higher-order gradients $\nabla \mathbf{z}^*$ via area-weighted patch averaging, and evaluate the edge bubble integral analytically.

### 5.3 Analytical Facet Dual Weight via Cubic Hermite Edge Bubble
On each facet $F$ connecting vertices $\mathbf{x}_1$ and $\mathbf{x}_2$ of length $h_F$, the linear interpolant $\Pi_h \mathbf{z}$ matches the values at $\mathbf{x}_1$ and $\mathbf{x}_2$.
The dual displacement error $\tilde{\mathbf{z}} - \Pi_h \tilde{\mathbf{z}}$ along $F$ vanishes at both endpoints and is modeled by a quadratic/cubic bubble function:
$$
(\tilde{\mathbf{z}} - \Pi_h \tilde{\mathbf{z}})(s) = 4 \frac{s}{h_F}\left(1 - \frac{s}{h_F}\right) \mathbf{w}_F.
$$
Integrating this bubble along facet $F$:
$$
\int_F 4 \frac{s}{h_F}\left(1 - \frac{s}{h_F}\right) ds = \frac{2}{3} h_F.
$$
The peak bubble amplitude $\mathbf{w}_F$ is determined by the directional second derivative or tangential gradient jump:
$$
\mathbf{w}_F = \frac{h_F^2}{8} \left[ \frac{\partial \mathbf{z}^*}{\partial \mathbf{t}_F}(\mathbf{x}_2) - \frac{\partial \mathbf{z}^*}{\partial \mathbf{t}_F}(\mathbf{x}_1) \right],
$$
leading to the facet weight formula:
$$
\mathbf{W}_F = \int_F (\mathbf{z} - \Pi_h \mathbf{z}) \, ds = \frac{h_F^2}{12} \left[ \nabla \mathbf{z}^*(\mathbf{x}_2) \mathbf{t}_F - \nabla \mathbf{z}^*(\mathbf{x}_1) \mathbf{t}_F \right],
$$
where $\nabla \mathbf{z}^*$ is the continuous reconstructed adjoint gradient obtained via area-weighted patch averaging of the element gradients, and $\mathbf{t}_F$ is the unit tangent along facet $F$.

---

## 6. Formal Taxonomy of Error Indicators and Estimates

A major defect in heuristic FEM implementations is confounding sensitivity indicators with certified error bounds. We formally establish the taxonomy of indicators in GDEC:

| Indicator / Estimate | Symbol | Mathematical Formulation | Target Space | Property |
| :--- | :--- | :--- | :--- | :--- |
| **Heuristic Sensitivity Indicator** | `goal_heuristic_v1` | $\eta_K = h_K^2 A_K \|\boldsymbol{\sigma}(u_h) : \boldsymbol{\varepsilon}(z_h)\|$ | Element | Adjoint sensitivity heuristic. No relation to actual error magnitude. |
| **Residual Energy-Norm Indicator** | `Residual_Energy_Norm` | $\eta_K^2 = h_K \sum_{F \in \partial K} \|[\![\boldsymbol{\sigma}_h \mathbf{n}]\!]\|^2$ | Element | Estimates global energy error $\|u - u_h\|_E$. Blind to localized QoIs. |
| **Goal-Oriented DWR Estimate** | `Goal_Oriented_DWR` | $\mathcal{E}_{\text{DWR}} = \sum_F \mathbf{j}_F \cdot \mathbf{W}_F$ | Facet / Element | Asymptotic estimate of signed QoI error $J(u) - J(u_h)$. Effectivity $I_{\text{eff}} \to 1.0$. |
| **Certified Error Bounds** | Certified Bound | $|J(u) - J(u_h)| \le C \eta_{\text{cert}}$ | Global | Requires guaranteed Sobolev constants (e.g., via equilibrated fluxes). |

> [!IMPORTANT]
> **Scientific Integrity Mandate:**
> GDEC's `Goal_Oriented_DWR` implementation is an **asymptotically consistent a posteriori error estimate** with localized cell indicators $\eta_K$. It is **not** an analytically certified mathematical upper bound, as it does not evaluate guaranteed global trace constants $C_{\text{trace}}$. In all user-facing reports and logs, GDEC explicitly identifies `is_certified_dwr_bound = False`.

---

## 7. Facet Orientation Invariance and Conservative Distribution

### 7.1 Orientation Invariance
Let $F$ be an interior facet shared by elements $K_1$ and $K_2$. If the ordering of elements is inverted ($K_1 \leftrightarrow K_2$), the outward normal flips sign: $\mathbf{n}_{21} = -\mathbf{n}_{12}$.
The traction jump transforms as:
$$
[\![\boldsymbol{\sigma} \mathbf{n}]\!]_{21} = (\boldsymbol{\sigma}_1 - \boldsymbol{\sigma}_2) \mathbf{n}_{21} = (\boldsymbol{\sigma}_1 - \boldsymbol{\sigma}_2)(-\mathbf{n}_{12}) = (\boldsymbol{\sigma}_2 - \boldsymbol{\sigma}_1)\mathbf{n}_{12} = [\![\boldsymbol{\sigma} \mathbf{n}]\!]_{12}.
$$
Hence, the jump vector $[\![\boldsymbol{\sigma} \mathbf{n}]\!]$ is identically invariant to facet orientation.

### 7.2 Element Error Distribution
Because facet residuals $F \in \mathcal{F}_h^{int}$ represent interaction between pairs of elements, their absolute error contributions must be distributed to adjacent elements for cell-based adaptive mesh refinement:
$$
\eta_K = \sum_{F \in \partial K \cap \mathcal{F}_h^{int}} \frac{1}{2} |\mathbf{j}_F \cdot \mathbf{W}_F| + \sum_{F \in \partial K \cap \mathcal{F}_h^N} |\mathbf{r}_F \cdot \mathbf{W}_F|.
$$
The factor of $1/2$ ensures exact conservation:
$$
\sum_{K \in \mathcal{T}_h} \eta_K = \sum_{F \in \mathcal{F}_h} |\rho_F \cdot \mathbf{W}_F|.
$$

### 7.3 Cost-Aware Priority Formulation
In adaptive mesh refinement, dividing an element adds new degrees of freedom. In regions of high geometric complexity or near boundary transitions, refining an element induces closure subdivisions in neighboring elements (green-refinement closures).
GDEC defines the refinement priority $P_K$ as:
$$
P_K = \frac{\eta_K}{\Delta \text{Cost}_K}, \quad \Delta \text{Cost}_K \approx 4 \text{ DOFs}.
$$
Elements are sorted descending by $P_K$ and marked using a Dörfler bulk criterion or top-fraction marking.
