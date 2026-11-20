# GDEC v0.2.1 Audit: Stress Recovery Mechanics & Energy Estimator Verification

**Audit Identifier**: `GDEC-v021-AUDIT-03`  
**Date**: 2026-11-20  
**Status**: VERIFIED & TERMINOLOGY RECONCILED  
**Role**: Principal Computational Mechanics Researcher & Independent Scientific Auditor  

---

## 1. Executive Summary

An audit of the energy-norm error estimator in `src/gdec/fem/estimators.py` was executed to determine the exact mathematical procedure used for stress recovery, verify dimensional units and thickness integration, test behavior under constant strain and bending, and reconcile terminology.

### Key Audit Verdict
1. **Recovery Algorithm Classification**: The implementation performs **Area-Weighted Nodal Stress Averaging** (Classical Zienkiewicz-Zhu 1987 averaging), **not** polynomial least-squares Superconvergent Patch Recovery (SPR 1992). The documentation and code comments have been corrected to reflect this exact methodology.
2. **Mathematical Formulation & Units**: The energy-norm integral $\eta_e = \left( \int_{\Omega_e} (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h)^T \mathbf{C}^{-1} (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h) \, d\Omega \cdot t \right)^{1/2}$ is mathematically exact, properly incorporates out-of-plane thickness $t$, and has correct physical units of $\sqrt{\text{Joules}}$ ($\text{J}^{1/2} = \sqrt{\text{N}\cdot\text{m}}$).
3. **Patch Test Invariance**: Under exact uniform strain, the estimated error is $\mathbf{2.96 \times 10^{-18}}$ (exact zero).
4. **Asymptotic Convergence**: Under uniform refinement on `CantileverDemo`, the global energy norm error converges at rate $p \to 0.941 \approx 1.0$, matching the theoretical $O(h^1)$ energy-norm convergence of $P_1$ linear elements.

---

## 2. Recovery Mechanics: Implementation vs Literature

### 2.1 The Two Families of Recovery Estimators
In adaptive computational mechanics, post-processing recovery estimators fall into two distinct families:
1. **Classical Nodal Averaging (ZZ 1987)**:
   Nodal stresses are evaluated as an area-weighted average of neighboring constant element stresses:
   $$\boldsymbol{\sigma}^*(n) = \frac{\sum_{e \in \omega_n} A_e \boldsymbol{\sigma}_e}{\sum_{e \in \omega_n} A_e}$$
   Then interpolated over element $e$ using the element shape functions.
2. **Superconvergent Patch Recovery (SPR, ZZ 1992)**:
   For each vertex patch, a local polynomial $\mathbf{p}(x, y) = [1, x, y]^T \mathbf{a}$ is fit using least-squares to the superconvergent sampling points (centroids for linear triangles).

### 2.2 Forensic Inspection of `src/gdec/fem/estimators.py`
Tracing lines 99–124:
```python
# 1. Recover nodal stresses by area-weighted averaging
nodal_stresses_sum = np.zeros((3, nn), dtype=float)
nodal_weights_sum = np.zeros(nn, dtype=float)

for local_v in range(3):
    nodes = triangles[local_v, :]
    for comp in range(3):
        np.add.at(nodal_stresses_sum[comp], nodes, areas * stresses[comp])
    np.add.at(nodal_weights_sum, nodes, areas)

nodal_recovered_stresses = nodal_stresses_sum / nodal_weights_sum[None, :]

# 2. Recover element centroid stress: average of 3 vertices
recovered_elem_stresses = (
    nodal_recovered_stresses[:, v0]
    + nodal_recovered_stresses[:, v1]
    + nodal_recovered_stresses[:, v2]
) / 3.0
```
- **Finding**: The implementation strictly executes **Area-Weighted Nodal Averaging**.
- **Action for v0.2.1**: The code comments and reports now identify this estimator as `Recovery_ZZ_NodalAveraging` to avoid confusion with SPR.

---

## 3. Mathematical Formulation, Quadrature & Units

### 3.1 Energy Norm Definition
$$\| \mathbf{e} \|_E^2 = \int_\Omega (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h)^T \mathbf{C}^{-1} (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h) \cdot t \, d\Omega = \sum_{e \in \mathcal{T}_h} \eta_{\text{zz}, e}^2$$

For linear triangular elements ($P_1$), $\boldsymbol{\sigma}_h$ is constant on element $e$. The recovered stress $\boldsymbol{\sigma}^*$ at the element centroid is approximated as the arithmetic mean of the three recovered vertex stresses.

Evaluating the one-point centroid quadrature:
$$\eta_{\text{zz}, e} = \sqrt{A_e \cdot t \cdot (\Delta \boldsymbol{\sigma}_e)^T \mathbf{C}^{-1} (\Delta \boldsymbol{\sigma}_e)}$$

### 3.2 Dimensional Analysis
- Stress difference $\Delta \boldsymbol{\sigma}$: $\text{N/m}^2$.
- Compliance tensor $\mathbf{C}^{-1}$: $\text{m}^2/\text{N}$.
- Quadratic form $(\Delta \boldsymbol{\sigma})^T \mathbf{C}^{-1} (\Delta \boldsymbol{\sigma})$: $\frac{\text{N}}{\text{m}^2} \cdot \frac{\text{m}^2}{\text{N}} \cdot \frac{\text{N}}{\text{m}^2} = \frac{\text{N}}{\text{m}^2} = \frac{\text{J}}{\text{m}^3}$ (strain energy density).
- Area $A_e \cdot t$: $\text{m}^2 \cdot \text{m} = \text{m}^3$ (volume).
- Product: $\frac{\text{J}}{\text{m}^3} \cdot \text{m}^3 = \text{J}$ (strain energy).
- Square root $\eta_{\text{zz}, e}$: $\mathbf{\sqrt{\text{J}}}$ (energy norm).
- **Status**: **VERIFIED**. Units are dimensionally consistent.

---

## 4. Empirical Verification Experiments

Conducted via `scratch/test_stage3_zz_audit.py`:

### 4.1 Uniform Strain Invariance
Under pure uniaxial tension ($u_x = \varepsilon_0 x, u_y = -\nu \varepsilon_0 y$):
- Exact uniform stress field across all elements.
- Nodal averaging recovers $\boldsymbol{\sigma}^* = \boldsymbol{\sigma}_h$ exactly.
- Measured $\max_e \eta_{\text{zz}, e} = \mathbf{2.96 \times 10^{-18}}$ J$^{1/2}$.
- **Status**: **PASS**. Zero false error under uniform strain.

### 4.2 Progressive Refinement Convergence
On `CantileverDemo` under uniform mesh bisection:

| Mesh Level | Elements | DOFs | Global Energy Error $\|e\|_E$ (J$^{1/2}$) | Empirical Convergence Rate $p$ |
| :---: | :---: | :---: | :---: | :---: |
| Level 1 | 64 | 90 | $1.852158 \times 10^0$ | — |
| Level 2 | 256 | 306 | $1.218154 \times 10^0$ | $0.605$ |
| Level 3 | 1,024 | 1,122 | $6.692141 \times 10^{-1}$ | $0.864$ |
| Level 4 | 4,096 | 4,290 | $3.484937 \times 10^{-1}$ | **$0.941$** |

- As $h \to 0$, the convergence rate approaches $p = 1.0$, which is the exact theoretical energy-norm asymptotic convergence rate for $P_1$ elements in 2D linear elasticity.

---

## 5. Documented Limitations of Nodal Averaging Estimators

1. **Boundary Bias**: Along domain boundaries, fewer elements contribute to each vertex, reducing the smoothing effect of area-weighted averaging.
2. **Global Norm vs Goal Output**: The estimator measures the global energy norm $\|\mathbf{u} - \mathbf{u}_h\|_E$. In cantilever bending, it concentrates refinement heavily at the fixed clamped root where stresses are highest, spending DOFs far from the tip displacement boundary $\Gamma_R$.
3. **No Local Guaranteed Bounds**: Nodal averaging provides an asymptotic error indicator, not an upper or lower bound on the true error.

---

## 6. Audit Stage 3 Sign-Off

The energy-norm recovery estimator is mathematically sound, dimensionally consistent, and exhibits proper asymptotic convergence. The terminology has been updated to **Area-Weighted Nodal Stress Averaging**.

Proceeding to **Stage 4: Reference Convergence & Benchmark Reproduction**.
