# GDEC — PHASE C DATASET DESIGN
## Factorial Experimental Design, Independence Rules & Dataset Manifests

**Repository:** `delythassociates/GDEC`  
**Document Date:** 2026-11-20  
**Status:** Frozen Dataset Specification  
**Location:** `reports/phase_c/PHASE_C_DATASET_DESIGN.md`

---

## 1. Principle of Independent Configurations

A critical flaw identified in prior pilot evaluations was the treating of sequential iterations along two trajectories as 24 independent samples. In Phase C, the statistical unit is **strictly an independent problem configuration**.

### Independence Rules
1. A new mesh refinement level or subsequent iteration of an existing problem does **not** constitute an independent configuration.
2. Each Tier 1 configuration possesses:
   - A distinct analytical manufactured displacement field.
   - Distinct parameter coefficients ($a, b, k, \sigma, x_0, y_0$).
   - An independent random mesh perturbation seed.
   - An exact analytical reference QoI.
3. Factorial balance is maintained across manufactured families, QoI types, constitutive assumptions, and target tolerances.

---

## 2. Tier 1 Dataset Specification (40 Independent Configurations)

Tier 1 contains **40 genuinely independent configurations** evenly distributed across 5 distinct mathematical families:

### Family 1: Polynomial / Monomial Fields (Configs T1_01 to T1_08)
- $u_x(x, y) = a_i x^2 + b_i y^2$, $u_y(x, y) = a_i x y$.
- Tests exact polynomial representation, spatial gradient balance, and pure bending behavior.
- Parameters $a_i \in [0.001, 0.008]$, $b_i \in [-0.004, -0.0005]$.

### Family 2: Trigonometric / Bi-Harmonic Fields (Configs T1_09 to T1_16)
- $u_x(x, y) = A \sin(\omega_i \pi x) \cos(\omega_i \pi y)$, $u_y(x, y) = A \cos(\omega_i \pi x) \sin(\omega_i \pi y)$.
- Tests continuous spatially periodic strain fields with zero boundary locking.
- Frequencies $\omega_i \in [1.0, 2.75]$.

### Family 3: Localized Gaussian Features (Configs T1_17 to T1_24)
- $u_x(x, y) = A \exp\left(-\frac{(x - x_{0,i})^2 + (y - y_{0,i})^2}{\sigma_i^2}\right)$, $u_y = 0.5 u_x$.
- Tests spatial localization, feature resolution, and steep displacement gradients.
- Feature widths $\sigma_i \in [0.15, 0.29]$, centers $(x_{0,i}, y_{0,i}) \in [0.3, 0.65] \times [0.4, 0.68]$.

### Family 4: Anisotropic Shear Fields (Configs T1_25 to T1_32)
- $u_x(x, y) = k_{x,i} x y + k_{y,i} y^2$, $u_y(x, y) = -k_{y,i} x^2 + k_{x,i} x y$.
- Tests mixed shear/normal stress states, non-aligned principal strain directions, and Poisson ratio sensitivity.

### Family 5: Multi-Scale Oscillatory Fields (Configs T1_33 to T1_40)
- $u_x(x, y) = A \left[ \sin(k_{1,i} \pi x) + 0.2 \sin(k_{2,i} \pi x) \right]$, $u_y(x, y) = A \left[ \cos(k_{1,i} \pi y) + 0.2 \cos(k_{2,i} \pi y) \right]$.
- Tests simultaneous coarse-scale bending and fine-scale oscillatory deformation.

### Factorial Distribution Matrix
- **QoI Classes:** 20 global boundary displacement averages, 20 regularized domain patch displacement averages.
- **Constitutive Models:** 20 plane stress, 20 plane strain.
- **Initial Mesh Topologies:** 20 structured Delaunay, 20 perturbed Delaunay with distinct seeds.
- **Accuracy Targets:** 14 at 1.0% tolerance, 13 at 0.5% tolerance, 13 at 0.25% tolerance.
- **M3 Validation Subset:** 10 configurations (2 per family) include Level $M_3$ evaluation for 4-grid order stability testing.

---

## 3. Tier 2 Dataset Specification (10 Difficult & Singular Problems)

Tier 2 evaluates performance in singular and gradient-concentrated regimes:
1. **Configs T2_01 to T2_04:** Williams Mode-I corner singularities on L-shaped domains across 4 re-entrant opening angles ($\omega \in \{270^\circ, 280^\circ, 290^\circ, 300^\circ\}$).
2. **Configs T2_05 to T2_08:** Weakly singular volume-loaded elasticity fields with algebraic exponents $\alpha \in \{1.2, 1.3, 1.4, 1.6\}$.
3. **Config T2_09:** Circular hole stress concentration plate under uniaxial tension ($U_{\text{ref}} \le 0.1 E_{\text{smallest}}$).
4. **Config T2_10:** Notched tensile bar asymptotic ligament stretch benchmark ($U_{\text{ref}} \le 0.1 E_{\text{smallest}}$).

---

## 4. Tier 3 Refusal Suite (64 Verified Refusal Cases)

Tier 3 contains 64 independent test cases (8 per category) to verify deterministic diagnosis and refusal:
1. `ill_posed_qoi` (8 cases): Singular corner point stress, notch-tip stress, Dirac point force.
2. `unsupported_qoi` (8 cases): Unregularized point displacement, point rotation, 3D tensor requests.
3. `unverified_order` (8 cases): Super-asymptotic orders ($p > 3.5$), sub-asymptotic orders ($p < 0.5$).
4. `unverified_non_asymptotic` (8 cases): Oscillating error differences ($d_{01} d_{12} < 0$), diverging grids ($q \le 1.0$).
5. `unverified_difference_below_numerical_floor` (8 cases): Differences below $1.0 \times 10^{-13}$ m.
6. `mesh_quality_failure` (8 cases): Triangles with minimum interior angle $\theta_{\min} < 10.0^\circ$.
7. `solver_not_converged` (8 cases): Linear solver relative backward error $> 1.0 \times 10^{-10}$.
8. `budget_exhausted` (8 cases): Refinement budget exhausted before target tolerance met.
