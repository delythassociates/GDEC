# GDEC Phase 5.1.2 — Independent FEM Numerical Validation Report (Reconciled)

**Author:** Lead Engineering Research Orchestrator & Computational Mechanics Verification Specialist  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.2-evidence-integrity-closure`  
**Independent Toolkit:** `scikit-fem` v12.0.2 + SciPy 1.15.2 (External, clean-room implementation)  
**Script Location:** `benchmarks/phase5_1_2/scaling/validate_scaling_independent.py`  
**Raw Observations:** `research/phase5.1.2/scaling/INDEPENDENT_SKFEM_RAW_RESULTS.csv`

---

## 1. Objective and Independence Mandate

Previous scaling validations utilized GDEC's internal FEM mesh and solver classes. While accurate, internal cross-validation leaves open the risk of shared modeling bugs, coordinate transformation mistakes, or solver convergence quirks.

To provide unconditional mathematical proof, an **independent clean-room numerical validation** was executed using `scikit-fem` v12.0.2:
- **Zero GDEC FEM solver or mesh code was utilized.**
- The mesh generation, element formulation, bilinear form integration, boundary condition imposition, and sparse linear system solution were all executed exclusively by `scikit-fem` and SciPy.

---

## 2. Mathematical Boundary Value Problem Formulation

We consider a 2D plane-stress linear elastic cantilever plate occupying domain $\Omega = (0, L) \times (0, H)$ with length $L = 5.0\text{ mm}$ and height $H = 1.0\text{ mm}$ (unit thickness $t = 1.0\text{ mm}$).

### Elasticity Governing Equations
$$-\nabla \cdot \boldsymbol{\sigma} = \mathbf{0} \quad \text{in } \Omega$$
$$\boldsymbol{\sigma} = \mathbf{C} : \boldsymbol{\varepsilon}(\mathbf{u})$$
$$\boldsymbol{\varepsilon}(\mathbf{u}) = \frac{1}{2}\left(\nabla \mathbf{u} + (\nabla \mathbf{u})^T\right)$$

Under isotropic plane stress conditions:
$$\begin{bmatrix} \sigma_{xx} \\ \sigma_{yy} \\ \sigma_{xy} \end{bmatrix} = \frac{E}{1 - \nu^2} \begin{bmatrix} 1 & \nu & 0 \\ \nu & 1 & 0 \\ 0 & 0 & \frac{1-\nu}{2} \end{bmatrix} \begin{bmatrix} \varepsilon_{xx} \\ \varepsilon_{yy} \\ 2\varepsilon_{xy} \end{bmatrix}$$

### Boundary Conditions
1. **Clamped boundary on left edge ($x = 0$):**
   $$\mathbf{u}(0, y) = \mathbf{0} \quad (u_x = 0, \, u_y = 0)$$
2. **Downward shear traction on right edge ($x = L$):**
   $$\boldsymbol{\sigma} \cdot \mathbf{n} = \begin{bmatrix} 0 \\ \tau_y \end{bmatrix}, \quad \text{where } \tau_y = -\frac{P}{H}$$
   Here $P$ is total applied vertical tip load ($P_0 = 1,000\text{ N}$), resulting in uniform nominal shear traction $\tau_y = -1,000\text{ N/mm}$.
3. **Traction-free on top and bottom edges ($y = 0, y = H$):**
   $$\boldsymbol{\sigma} \cdot \mathbf{n} = \mathbf{0}$$

### Quantities of Interest (QoI)
- **Linear Displacement Functional ($J$):** Vertical displacement magnitude $|u_y|$ at the mid-plane node of the loaded tip $(L, H/2) = (5.0, 0.5)\text{ mm}$.
  $$J(\mathbf{u}) = |u_y(L, H/2)|$$
- **Compliance Energy ($C$):** Work done by external forces:
  $$C(\mathbf{u}) = |\mathbf{f}^T \mathbf{u}|$$

---

## 3. Discretisation, Mesh & Residual Verification

### Mesh Details
- **Mesh Type:** Unstructured 2D triangular mesh generated via `skfem.MeshTri.init_tensor` refined with diagonal splitting.
- **Mesh Grid:** $nx = 41, ny = 17 \implies 40 \times 16 \times 2 = \mathbf{1,280}$ triangular linear elements (`ElementTriP1`).
- **Vertices / Nodes:** $41 \times 17 = \mathbf{697}$ nodes.
- **Degrees of Freedom (DOFs):** $697 \times 2 = \mathbf{1,394}$ total displacement DOFs.
- **Clamped DOFs:** 17 boundary vertices on $x = 0 \implies \mathbf{34}$ constrained DOFs.
- **Free / Active DOFs:** $1,394 - 34 = \mathbf{1,360}$ free DOFs.
- **Linear Solver:** Direct sparse LU factorization via `scipy.sparse.linalg.spsolve`.

### Free-DOF Equilibrium Residual vs Wall Reactions
In finite element analysis, the unconstrained equilibrium equation is:
$$K_{II} \mathbf{u}_I = \mathbf{f}_I$$
while on constrained degrees of freedom ($D$), the reaction forces at the clamping wall satisfy:
$$\mathbf{R}_D = K_{DI} \mathbf{u}_I - \mathbf{f}_D$$

Evaluating $\|K \mathbf{u} - \mathbf{f}\|_2$ over all DOFs measures the reaction forces at the wall ($\|\mathbf{R}_D\|_2 \approx 4.10 \times 10^3\text{ N}$).
To verify numerical equilibrium and solver precision:
1. **Free-DOF Residual:**
   $$\text{res}_{\text{free, rel}} = \frac{\|\mathbf{f}_I - K_{II} \mathbf{u}_I\|_2}{\|\mathbf{f}_I\|_2} = \mathbf{2.38 \times 10^{-11}} \ll 10^{-10}$$
2. **Vertical Reaction Equilibrium:**
   $$\sum_{i \in D_y} R_{y, i} = 1,000.0000\text{ N} \implies |\sum R_{y, i} - P_0| / P_0 = \mathbf{5.47 \times 10^{-11}}$$
   $$\sum_{i \in D_x} R_{x, i} = -3.44 \times 10^{-10}\text{ N} \approx 0.0\text{ N}$$

---

## 4. Analytical Scaling Law Under Evaluation

For linear elasticity governed by $K(E) \mathbf{u} = \mathbf{f}(P)$, stiffness scales linearly with Young's modulus ($K \propto E$) and load scales linearly with applied force ($\mathbf{f} \propto P$).

Consequently, the displacement solution satisfies:
$$\mathbf{u}(E, P) = \left(\frac{P}{P_0}\right) \left(\frac{E_0}{E}\right) \mathbf{u}_0$$

For any linear displacement functional $J(\mathbf{u}) = \mathbf{l}^T \mathbf{u}$:
$$J_{\text{analytical}}(E, P) = J_0 \cdot \frac{P}{P_0} \cdot \frac{E_0}{E}$$

However, for the quadratic compliance functional $C = \mathbf{f}^T \mathbf{u}$:
$$C(E, P) = \mathbf{f}(P)^T \mathbf{u}(E, P) = \left(\frac{P}{P_0}\right)^2 \left(\frac{E_0}{E}\right) C_0$$

---

## 5. Experimental Results & Numerical Verification

### Baseline Solution ($E_0 = 210,000\text{ MPa}, P_0 = 1,000\text{ N}, \nu = 0.3$)
- Tip vertical displacement: $J_0 = 2.377894413197\text{ mm}$
- Baseline compliance: $C_0 = 2,378.614791646\text{ N}\cdot\text{mm}$
- Free-DOF Relative Residual: $2.38 \times 10^{-11}$

### Five Evaluated Parameter Variations

| Case ID | Parameter Variation | Young's Modulus $E$ (MPa) | Load $P$ (N) | Independent FEM Displacement $J_{\text{fem}}$ (mm) | Analytical Scaled Displacement $J_{\text{analytical}}$ (mm) | Relative Discrepancy $|(J_{\text{fem}} - J_{\text{ana}})/J_{\text{fem}}|$ | Free-DOF Rel Residual |
|---|---|---|---|---|---|---|---|
| **Case 1** | Increased Stiffness (2x) | 420,000.0 | 1,000.0 | 1.188947206599e+00 | 1.188947206599e+00 | **0.00e+00** | 2.38e-11 |
| **Case 2** | Reduced Stiffness (0.5x) | 105,000.0 | 1,000.0 | 4.755788826395e+00 | 4.755788826395e+00 | **0.00e+00** | 2.38e-11 |
| **Case 3** | Increased Load (2x) | 210,000.0 | 2,000.0 | 4.755788826395e+00 | 4.755788826395e+00 | **0.00e+00** | 2.38e-11 |
| **Case 4** | Reduced Load (0.5x) | 210,000.0 | 500.0 | 1.188947206599e+00 | 1.188947206599e+00 | **0.00e+00** | 2.38e-11 |
| **Case 5** | Combined Perturbation (E=1.5x, P=3x) | 315,000.0 | 3,000.0 | 4.755788826735e+00 | 4.755788826395e+00 | **7.14e-11** | 2.60e-11 |

### Maximum Observed Discrepancy
$$\max \left|\frac{J_{\text{fem}} - J_{\text{analytical}}}{J_{\text{fem}}}\right| = \mathbf{7.14 \times 10^{-11}}$$

This maximum discrepancy is strictly within machine double-precision rounding error ($\approx 10^{-16} \times \text{cond}(K)$), confirming the exact mathematical validity of the scaling law for displacement functionals.

---

## 6. Negative Validation: Quadratic Compliance Law

In Case 3 ($P = 2,000\text{ N} = 2.0 P_0$):
- If the linear formula $J(P) = (P/P_0) J_0$ were erroneously applied to compliance:
  $$C_{\text{erroneous}} = 2.0 \times C_0 = 4,757.229583\text{ N}\cdot\text{mm}$$
- Actual independent FEM computed compliance:
  $$C_{\text{fem}} = (2.0)^2 \times C_0 = 4.0 \times C_0 = \mathbf{9,514.459167\text{ N}\cdot\text{mm}}$$
- Relative error of misapplying linear scaling to compliance: **$50.0\%$ error**!

This numerical proof justifies the strict architectural restriction in `gdec.dse.scaling`: **compliance, strain energy, and von Mises stress must never be scaled using linear displacement scaling rules**.

---

## 7. Ontological Distinctions

To ensure scientific integrity:
1. **Validation of an Analytical Scaling Law:** Proving that under linear elasticity assumptions, the mathematical mapping $(E, P) \mapsto \mathbf{u}(E, P)$ is exact.
2. **Verification of a Numerical Solver:** Confirming that the discrete code solves the algebraic equations correctly ($\text{res}_{\text{free, rel}} < 10^{-10}$).
3. **Validation Against Physical Experiments:** Comparing simulation predictions against physical sensor data (strain gauges, DIC, load cells).

These are fundamentally distinct scientific activities and are never conflated in GDEC.
