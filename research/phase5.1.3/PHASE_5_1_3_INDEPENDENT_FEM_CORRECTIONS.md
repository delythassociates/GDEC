# GDEC Phase 5.1.3 — Independent FEM Validation Corrections Report

**Author:** Principal Computational Mechanics Verification Specialist  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.3-validation-and-ci-closure`  
**Independent Engine:** `scikit-fem` v12.0.2 + SciPy 1.15.2 (clean-room external implementation)  
**Authoritative Benchmark Location:** `benchmarks/phase5_1_2/scaling/validate_scaling_independent.py`  
**Raw Observations Location:** `research/phase5.1.3/scaling/INDEPENDENT_SKFEM_RAW_RESULTS.csv`

---

## 1. Authoritative Benchmark Reconciliation

In Phase 5.1.2, a documentation discrepancy existed between the committed benchmark Python script and the accompanying markdown report:
- The script implemented a cantilever plate with $L = 5.0\text{ mm}, H = 1.0\text{ mm}, E_0 = 210,000\text{ MPa}, P_0 = 1,000\text{ N}$.
- The report described a $2.0\text{ m} \times 0.5\text{ m}$ beam with $10,000\text{ N}$ load.
- The test fixture in `test_independent_fem_validation.py` used an alternative $nx=31, ny=13, E_0=200\text{e}3\text{ MPa}$ discretization.

Phase 5.1.3 establishes a **single authoritative benchmark definition** across all four artifacts (the benchmark script, the report, the test fixture, and the raw CSV table).

### The Authoritative Benchmark Specification

| Parameter | Symbol | Value | Units | Physical Description |
|---|---|---|---|---|
| **Length** | $L$ | 5.0 | mm | Cantilever plate span |
| **Height** | $H$ | 1.0 | mm | Cantilever cross-sectional depth |
| **Thickness** | $t$ | 1.0 | mm | Out-of-plane thickness (plane stress assumption) |
| **Young's Modulus** | $E_0$ | 210,000.0 | MPa ($= \text{N/mm}^2$) | Standard structural steel modulus ($210\text{ GPa}$) |
| **Poisson's Ratio** | $\nu$ | 0.3 | dimensionless | Standard isotropic Poisson's ratio |
| **End Shear Load** | $P_0$ | 1,000.0 | N | Total downward vertical load applied at $x = L$ |
| **Traction Distribution** | $\tau_y$ | -1,000.0 | $\text{N/mm}$ ($= -P_0 / H$) | Uniform shear traction on boundary facets at $x = L$ |
| **Left Boundary** | $\Gamma_{\text{clamp}}$ | $x = 0$ | - | Clamped Dirichlet condition ($u_x = 0, u_y = 0$) |
| **Mesh Resolution** | $nx \times ny$ | $41 \times 17$ | nodes | Tensor-product vertices |
| **Element Type** | `ElementTriP1` | - | - | Linear triangular displacement elements (3 nodes, 6 DOFs) |
| **Total Elements** | $N_{\text{elem}}$ | 1,280 | triangles | $40 \times 16 \times 2 = 1,280$ elements |
| **Total Nodes** | $N_{\text{node}}$ | 697 | nodes | $41 \times 17 = 697$ vertices |
| **Total DOFs** | $N_{\text{dof}}$ | 1,394 | DOFs | $697 \times 2$ displacement degrees of freedom |
| **Clamped DOFs** | $N_{\text{clamp}}$ | 34 | DOFs | 17 nodes along $x = 0 \times 2$ components |
| **Free Active DOFs** | $N_{\text{free}}$ | 1,360 | DOFs | $1,394 - 34$ unconstrained active DOFs |
| **Tip Displacement QoI** | $J_0$ | 2.377894413197 | mm | Vertical displacement magnitude at $(x=5.0, y=0.5)$ |
| **Compliance QoI** | $C_0$ | 2,378.614791646 | $\text{N}\cdot\text{mm}$ ($=\text{mJ}$) | External work functional $C = |\mathbf{f}^T \mathbf{u}|$ |

---

## 2. Mathematical Correction of the Numerical Residual

### 2.1 The Error in the Legacy Residual Calculation
The legacy script computed the residual via:
```python
# Flawed legacy expression
res_norm = np.linalg.norm(f_vec - K_mat @ u_full) / np.linalg.norm(f_vec)
```
In any standard finite element boundary-value problem with essential (Dirichlet) boundary conditions, the global algebraic system is:
$$K \mathbf{u} = \mathbf{f} + \mathbf{R}$$
where $\mathbf{R}$ represents the reaction forces and moments exerted by the Dirichlet support.
- On unconstrained free DOFs ($I$), reaction forces are zero: $\mathbf{R}_I = \mathbf{0}$.
- On constrained DOFs ($D$), the clamped support exerts reaction forces $\mathbf{R}_D = K_{DI} \mathbf{u}_I - \mathbf{f}_D$.
Evaluating $\|\mathbf{f} - K \mathbf{u}\|_2$ over all degrees of freedom evaluates $\|\mathbf{R}_D\|_2$ (the physical reaction forces at the clamping wall). Dividing this reaction force by $\|\mathbf{f}\|_2$ produced $\approx 16.67$, which was erroneously interpreted as a non-converged solver residual.

### 2.2 The Correct Partitioned Formulation
Phase 5.1.3 correctly partitions the degrees of freedom into free ($I$) and constrained ($D$) subsets:
$$K_c \mathbf{u}_{\text{free}} = \mathbf{f}_c \quad \text{where } K_c = K_{II}, \; \mathbf{f}_c = \mathbf{f}_I$$

1. **Free-DOF Equilibrium Residual:**
   $$\mathbf{r}_{\text{free}} = \mathbf{f}_c - K_c \mathbf{u}_{\text{free}}$$
   $$\text{res}_{\text{free, rel}} = \frac{\|\mathbf{r}_{\text{free}}\|_2}{\|\mathbf{f}_c\|_2}$$
   In double-precision SciPy `spsolve` execution, this yields:
   $$\text{res}_{\text{free, rel}} = \mathbf{2.38 \times 10^{-11}} \ll 10^{-10} \quad \text{(PASS)}$$

2. **Reaction Force & Equilibrium Verification:**
   The reactions at the clamped wall are:
   $$\mathbf{R}_D = K_{DI} \mathbf{u}_{\text{free}} - \mathbf{f}_D$$
   Global static equilibrium requires:
   $$\sum_{i \in D_y} R_{y, i} = P \quad \text{and} \quad \sum_{i \in D_x} R_{x, i} = 0$$
   Our numerical audit confirms:
   - Total vertical reaction: $R_y = \mathbf{1,000.0000\text{ N}}$ (exact match with $P_0 = 1,000\text{ N}$).
   - Equilibrium error: $|\sum R_{y, i} - P_0| / P_0 = \mathbf{5.47 \times 10^{-11}}$.
   - Total horizontal reaction: $R_x = \mathbf{-3.44 \times 10^{-10}\text{ N}} \approx 0\text{ N}$.
   - Wall reaction Euclidean norm: $\|\mathbf{R}_D\|_2 = \mathbf{4.10 \times 10^3\text{ N}}$.

---

## 3. Independent Parameter Variations & Scaling Law Validation

For every parameter variation, a fresh stiffness matrix $K(E)$ and load vector $\mathbf{f}(P)$ were assembled and solved independently from scratch.

| Case ID | Parameter Variation | Young's Modulus $E$ (MPa) | Load $P$ (N) | Independent FEM Displacement $J_{\text{fem}}$ (mm) | GDEC Analytical Scaled $J_{\text{ana}}$ (mm) | Relative Discrepancy $|(J_{\text{fem}} - J_{\text{ana}})/J_{\text{fem}}|$ | Free-DOF Rel Residual | Vertical Equilibrium Rel Error | Compliance $C_{\text{fem}}$ ($\text{N}\cdot\text{mm}$) |
|---|---|---|---|---|---|---|---|---|---|
| **Case 1** | Increased Modulus (2x) | 420,000.0 | 1,000.0 | 1.188947206599e+00 | 1.188947206599e+00 | **0.00e+00** | 2.38e-11 | 5.47e-11 | 1.189307395823e+03 |
| **Case 2** | Reduced Modulus (0.5x) | 105,000.0 | 1,000.0 | 4.755788826395e+00 | 4.755788826395e+00 | **0.00e+00** | 2.38e-11 | 5.47e-11 | 4.757229583290e+03 |
| **Case 3** | Increased Load (2x) | 210,000.0 | 2,000.0 | 4.755788826395e+00 | 4.755788826395e+00 | **0.00e+00** | 2.38e-11 | 5.47e-11 | 9.514459166580e+03 |
| **Case 4** | Reduced Load (0.5x) | 210,000.0 | 500.0 | 1.188947206599e+00 | 1.188947206599e+00 | **0.00e+00** | 2.38e-11 | 5.47e-11 | 5.946536979113e+02 |
| **Case 5** | Combined Perturbation | 315,000.0 | 3,000.0 | 4.755788826735e+00 | 4.755788826395e+00 | **7.14e-11** | 2.60e-11 | 5.72e-11 | 1.427168875089e+04 |

Maximum relative discrepancy across all variations: **$7.14 \times 10^{-11}$** (cleanly within machine rounding precision).

---

## 4. Negative Validation: Quadratic Compliance Scaling

In linear elasticity, compliance is given by:
$$C = \mathbf{f}^T \mathbf{u} = \mathbf{u}^T K \mathbf{u}$$
Because $\mathbf{u} \propto P / E$ and $\mathbf{f} \propto P$:
$$C(E, P) = \left(\frac{P}{P_0}\right)^2 \left(\frac{E_0}{E}\right) C_0$$

In Case 3 ($P = 2 P_0$):
- Exact FEM compliance: $C = 4.0 \times C_0 = 9,514.459\text{ N}\cdot\text{mm}$.
- Erroneous linear displacement scaling: $C_{\text{linear}} = 2.0 \times C_0 = 4,757.230\text{ N}\cdot\text{mm}$.
- Relative error of misapplying linear scaling to compliance: **$50.0\%$ error**.

Automated test `test_scaling_api_rejects_compliance_and_stress` strictly rejects compliance and stress functionals from entering GDEC's linear scaling model.

---

## 5. Ontological Distinctions in Verification & Validation

The GDEC engineering framework strictly distinguishes:
1. **Validation of an Analytical Scaling Law:** Proving that the algebraic mapping $(E, P) \mapsto \mathbf{u}(E, P)$ is mathematically exact under linear-elastic assumptions.
2. **Verification of a Numerical Solver:** Confirming that the discrete implementation solves the discrete equations without error ($\text{res}_{\text{free, rel}} < 10^{-10}$).
3. **Validation Against Physical Experiments:** Comparing computational predictions against physical sensor observations in a laboratory or operational environment.

These activities have distinct mathematical meanings and evidentiary weights.
