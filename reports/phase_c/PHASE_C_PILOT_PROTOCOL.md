# GDEC — PHASE C PILOT PROTOCOL
## Preliminary Manufactured-Solution Feasibility Pilot Specification

**Repository:** `delythassociates/GDEC`  
**Classification:** `EXPLORATORY — NOT CONFIRMATORY`  
**Date Frozen:** 2026-11-20  
**Baseline Commit:** `85721d88b2817eb2a132ed04966bd3085ff256e4`  
**Branch:** `phase-c/preflight-and-pilots`

---

## 1. Pilot Mission

The objective of this exploratory pilot is to evaluate whether the proposed nested-uniform-refinement Grid Convergence Index (GCI) verification contract:
$$U_0 = F_s |J_0 - J_1| \frac{2^{p_{\text{used}}}}{2^{p_{\text{used}}} - 1}, \quad p_{\text{used}} = \min(p_{\text{obs}}, p_{\text{cap}})$$
is viable across both smooth and singular solution regimes in 2D linear elasticity.

This pilot will establish:
1. Observed order distribution for smooth vs. corner-singular elasticity fields.
2. The empirical validity of the provisional order window $0.5 \le p_{\text{obs}} \le 3.5$.
3. The necessity and behaviour of refusing singular point stress QoIs.
4. The exact computational and memory costs of $M_2$ ($16\times$ elements) and $M_3$ ($64\times$ elements) uniform refinement.

---

## 2. Frozen Pilot Benchmarks

### Case A — Williams Re-entrant Corner Singularity (Traction-Free Corner)
- **Domain:** L-shaped domain $\Omega = (-1, 1)^2 \setminus [0, 1] \times [-1, 0]$ with re-entrant corner at $(0, 0)$ and internal angle $\omega = 3\pi/2$.
- **Governing Field:** Exact Mode-I symmetric opening Williams eigenfunction with singular exponent $\lambda \approx 0.544483736782$.
- **Material:** $E = 100 \times 10^9$ Pa, $\nu = 0.30$, plane strain ($\kappa = 3 - 4\nu = 1.80$).
- **Equilibrium:** Exact analytical solution of Navier-Cauchy equations: body force $\mathbf{f} \equiv \mathbf{0}$. Volume quadrature error is zero.
- **Boundary Data:** Traction-free on corner faces $\theta \in \{0, 3\pi/2\}$; exact displacement Dirichlet conditions on all outer boundaries.

### Case B — Manufactured Weakly-Singular Elastic Field
- **Domain:** Unit square $[0, 1]^2$.
- **Displacement Field:** Radial singular displacement with exponent $\alpha = 1.40$ ($u \sim r^{1.4}$).
- **Material:** $E = 200 \times 10^9$ Pa, $\nu = 0.25$, plane stress.
- **Body Force:** Derived analytically via $-\nabla \cdot \boldsymbol{\sigma}(\mathbf{u})$.
- **Special Quadrature:** High-order Gauss-Legendre quadrature (order 14) ensuring $E_{\text{quadrature}} \le 0.01 E_{\text{smallest}}$.

---

## 3. Pilot Quantities of Interest (QoIs)

1. **`qoi_smooth_global`**: Boundary-average vertical displacement on top edge: $J(u) = \int_{\Gamma_{\text{top}}} u_y\, ds$. Target status: **SUPPORTED**.
2. **`qoi_patch_regularized`**: Domain patch-average displacement: $J(u) = \frac{1}{|\Omega_p|} \int_{\Omega_p} u_x\, d\Omega$ away from the singularity. Target status: **SUPPORTED**.
3. **`qoi_point_stress_singular`**: Point von Mises stress at the re-entrant corner $(0, 0)$. Target status: **REFUSED (`ill_posed_qoi`)**. Point stress does not converge in $H^1$ under mesh refinement at a sharp re-entrant corner.
4. **`qoi_finite_area_stress`**: Domain patch-average von Mises stress: $J(u) = \frac{1}{|\Omega_p|} \int_{\Omega_p} \sigma_{\text{vM}}\, d\Omega$. Target status: **EXPLORATORY CAPABILITY TEST ONLY**.

---

## 4. Nested Refinement Hierarchy & Hierarchy Rules

- **Refinement Ratio:** $r = 2.0$ via regular 1-to-4 triangle subdivision.
- **Mesh Sequence:** $M_0 \to M_1 \to M_2$ ($r = 2$), with $M_3$ evaluated on a validation subset to test asymptotic order stability:
  $$p_{012} = \frac{\ln(|J_0 - J_1| / |J_1 - J_2|)}{\ln 2}, \quad p_{123} = \frac{\ln(|J_1 - J_2| / |J_2 - J_3|)}{\ln 2}$$
- **Safety Factor:** $F_s = 1.25$.
- **Order Cap:** $p_{\text{cap}} = 2.0$.
- **Plausibility Window:** $0.5 \le p_{\text{obs}} \le 3.5$.
