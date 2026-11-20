# GDEC Phase C Amendment 1 — Dataset Reconciliation Report

**Target Preregistration:** `verification/phase_c/amendment_1/`  
**Manifests:** `tier1_manifest.json`, `tier2_manifest.json`, `tier3_manifest.json`  

---

## 1. Tier 1 Dataset Reconciliation (40 Configurations)

### 1.1 Tolerance Distribution Correction (AM1-15)
In the initial Phase C manifest generator, the expression `tolerances[(item_idx // 4) % len(tolerances)]` for `item_idx` in `0..7` evaluated only indices 0 and 1, completely omitting tolerance `0.0025` (0.25%).
In the amended manifest, tolerances are assigned deterministically to yield the exact required counts:
- **1.0% (0.0100):** Exactly 14 configurations (35.0%)
- **0.5% (0.0050):** Exactly 13 configurations (32.5%)
- **0.25% (0.0025):** Exactly 13 configurations (32.5%)
- **Total:** 40 configurations (100.0%)

### 1.2 Four-Grid ($M_3$) Subset Balancing (AM1-16)
In the initial generator, items 0 and 4 in each family were selected for level $M_3$, resulting in 100% structured meshes, 100% boundary average QoIs, and 100% plane stress.
In the amended manifest, the 10 configurations designated for $M_3$ validation are strictly balanced:
- **QoI Type:** 5 Boundary Average Displacement, 5 Patch Average Displacement
- **Initial Mesh:** 5 Structured Grid, 5 Perturbed Delaunay Grid
- **Constitutive Model:** 5 Plane Stress, 5 Plane Strain
- **Family Distribution:** Exactly 2 configurations per family across all 5 families

### 1.3 Parametric Diversity & Boundary Value Problem Completeness (AM1-17, AM1-18)
- **Family 4 (Anisotropic Shear):** Orthotropy ratios $E_x / E_y$ vary from $1.5$ to $4.0$ with distinct shear coupling terms.
- **Family 5 (Multiscale Oscillatory):** Diverse wave number pairs $(k_1, k_2) \in \{(2, 6), (3, 8), (4, 10), (5, 12), (3, 7), (4, 9), (2, 8), (5, 15)\}$ ensure distinct spatial frequency spectra.
- **BVP Definitions:** Every configuration entry contains explicit mathematical definitions of the displacement field $(u_x, u_y)$, the body force vector $(f_x, f_y) = -\nabla \cdot \sigma$, the boundary partition $\partial \Omega = \Gamma_D \cup \Gamma_N$, and the exact QoI integral.

---

## 2. Tier 2 Dataset Reconciliation (10 Configurations)

### 2.1 Singular Exponent Concordance (AM1-19)
The singular exponents $\lambda_1$ correspond strictly to the roots of Williams' characteristic equation:
$$\sin(\lambda \omega) + \lambda \sin(\omega) = 0$$
- $\omega = 270^\circ$ ($3\pi/2$, L-shape): $\lambda_1 \approx 0.544483736782464$
- $\omega = 300^\circ$ ($5\pi/3$, wedge): $\lambda_1 \approx 0.512221405106197$
- $\omega = 315^\circ$ ($7\pi/4$, wedge): $\lambda_1 \approx 0.504990924760086$
- $\omega = 360^\circ$ ($2\pi$, slit crack): $\lambda_1 = 0.500000000000000$

All 10 Tier 2 configurations are documented with exact closed-form eigenfunctions, boundary conditions, and high-order quadrature verification standards.

---

## 3. Tier 3 Refusal Dataset Reconciliation (80 Test Cases)

### 3.1 10-Category Priority Architecture (AM1-21, AM1-22)
The amended Tier 3 manifest expands from generic repeated templates across 8 categories to **exactly 80 distinct, executable test cases** (8 per category across all 10 priority categories):
1. **Priority 1 (`ill_posed_qoi`):** 8 cases (singular point stresses at notch and crack tips)
2. **Priority 2 (`unsupported_qoi`):** 8 cases (unregularized point displacements, patch-average stresses)
3. **Priority 3 (`invalid_geometry`):** 8 cases (NaN/Inf coordinates, degenerate topologies, self-intersections)
4. **Priority 4 (`mesh_quality_failure`):** 8 cases (angles $< 10^\circ$, zero-area triangles, slivers)
5. **Priority 5 (`solver_not_converged`):** 8 cases (unconstrained rigid body modes, volumetric locking, stagnation)
6. **Priority 6 (`unverified_insufficient_levels`):** 8 cases (1 or 2 levels only, non-nested sequences)
7. **Priority 7 (`unverified_difference_below_numerical_floor`):** 8 cases (differences $< 10^{-13}$ m, machine zero)
8. **Priority 8 (`unverified_order`):** 8 cases (observed order $p_{\text{obs}} < 0.5$ or $> 3.5$)
9. **Priority 9 (`unverified_non_asymptotic`):** 8 cases (non-monotonicity, divergence $q \le 1$, $M_3$ drift $> 0.50$)
10. **Priority 10 (`reference_uncertain`):** 8 cases (reference uncertainty $> 0.05\%$, unverified quadrature)
