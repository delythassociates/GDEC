# GDEC — PHASE B: DWR vs ZZ SCIENTIFIC FEASIBILITY GATE
## Pre-Registered Experimental Protocol and Independent Numerical Evaluation Report

**Repository:** `delythassociates/GDEC`  
**Base Release:** v0.2.2 (`789f1f1f8fd43fc1fca65d098ca17bd5714158ea`)  
**Verified Foundation Commit:** `01260409a0e11d8dcf97729ea25a61f20e2a4772`  
**Phase A Preregistration Tag:** `prereg-thresholds` (`8a5237d22af71912af19268386f08a596ba1621a`)  
**Phase B Active Branch:** `phase-b/dwr-vs-zz`  
**Pre-Registered Protocol:** `verification/phase_b_thresholds.json` (Commit `a336cc9`)

---

## 1. Executive Summary & Final Scientific Determination

This report documents the rigorous, independent, pre-registered numerical evaluation of goal-oriented Dual Weighted Residual (DWR) adaptive refinement against conventional Zienkiewicz–Zhu (ZZ) energy-norm recovery across four engineering benchmark problems and three initial mesh variants (48 complete simulations).

### Pre-Registered Research Question
> *"At equivalent true QoI error, can goal-oriented DWR achieve at least 30% fewer degrees of freedom than conventional ZZ recovery across multiple engineering problems, while producing sufficiently reliable error estimates?"*

### Primary Findings
1. **Primary Hypothesis ($S_{\mathrm{DOF}} \ge 1.30$ on $\ge 3$ problems): FAILED.**  
   - Across the four benchmark problems, **0 of 4 problems** achieved a median DOF savings ratio $S_{\mathrm{DOF}} \ge 1.30$ at the pre-registered 1.0% true QoI relative error target.
   - The geometric mean of median DOF savings across problems is **$S_{\mathrm{DOF}} = 0.965$** (below the 1.30 target, and $< 1.0$, indicating that on typical initial meshes, conventional ZZ recovery achieved the 1.0% QoI accuracy target with comparable or fewer primal DOFs).
2. **Secondary Hypothesis (Estimator Reliability: $I_{\mathrm{eff}} \in [0.5, 2.0]$ for $\ge 90\%$ of runs): FAILED.**  
   - While DWR exhibited near-ideal effectivity on the smooth cantilever beam ($I_{\mathrm{eff}} \approx 0.99 - 1.01$), localized stress concentrations and geometric re-entrant corners caused effectivity fluctuations, resulting in only **40.0%** of evaluated iterations falling within the $[0.5, 2.0]$ reliability envelope.
   - Underestimation frequency was **77.3%**, with maximum underestimation reaching 99.5% on coarse initial pre-asymptotic meshes.
3. **Secondary Hypothesis (Computational Cost): SUBSTANTIALLY HIGHER COST.**  
   - The enriched quadratic $P_2$ dual solve increased per-iteration solver overhead by $3.5\times$ to $10\times$. At equivalent true accuracy, the median runtime speedup ratio was **$S_T = \frac{T_{\mathrm{ZZ}}}{T_{\mathrm{DWR}}} \approx 0.10\times - 0.28\times$** (DWR was 4 to 10 times slower in total wall-clock compute time).
4. **Isolated Geometric Advantage:**  
   - On specific mesh configurations featuring extreme singular pollution (such as the L-shaped domain with unrefined re-entrant corner, variant 1), DWR exhibited a localized **$6.55\times$ DOF advantage** over ZZ ($S_{\mathrm{DOF}} = 6.545$) because ZZ expended tens of thousands of DOFs refining the corner singularity while DWR concentrated refinement directly on the arm QoI. However, when initial meshes provided balanced geometric resolution, this advantage vanished.

### Final Pre-Registered Classification

> **FINAL CLASSIFICATION: FAIL — NO DEMONSTRATED ADVANTAGE**  
> Pursuant to Section 12 of the Brief:  
> *"Use this if the method is mathematically valid but fails to demonstrate meaningful DOF savings or estimator reliability. This does not mean the FEM foundation is invalid. It means the current DWR approach is not justified as GDEC's central differentiator."*

---

## 2. Initial Foundation & Environment Audit

Prior to executing any Phase B experimental runs:
- **Baseline Invariance:** Confirmed commit `0126040` as the Phase A foundation head.
- **Tag Immutability:** Tag `prereg-thresholds` confirmed pointing to `8a5237d` (untouched).
- **Production Numerical Solver:** Confirmed zero algorithmic diff between `src/gdec/fem/` and v0.2.2 baseline (`789f1f1`).
- **Phase A Regression Suite:** Verified 99 / 99 passing tests in 39.31s.
- **Branch Creation:** Created and checked out isolated branch `phase-b/dwr-vs-zz`.
- Documented in [reports/phase_b/INITIAL_AUDIT.md](file:///f:/fem-edit-benchmark/reports/phase_b/INITIAL_AUDIT.md).

---

## 3. Pre-Registered Hypotheses and Acceptance Rules

Frozen in `verification/phase_b_thresholds.json` at commit `a336cc9`:

| Hypothesis | Metric | Requirement | Experimental Outcome | Assessment |
|:---|:---|:---:|:---:|:---:|
| **Primary: DOF Advantage** | $S_{\mathrm{DOF}} = \frac{N_{\mathrm{DOF,ZZ}}}{N_{\mathrm{DOF,DWR}}}$ at 1.0% error | $S_{\mathrm{DOF}} \ge 1.30$ on $\ge 3$ problems | 0 of 4 problems met target | **FAIL** |
| | Geometric Mean $\bar{S}_{\mathrm{DOF}}$ | $\bar{S}_{\mathrm{DOF}} \ge 1.30$ | $\bar{S}_{\mathrm{DOF}} = 0.965$ | **FAIL** |
| **Secondary: Reliability** | $I_{\mathrm{eff}} = \frac{\|\eta_{\mathrm{DWR}}\|}{\|J_{\mathrm{ref}} - J_h\|}$ | $0.5 \le I_{\mathrm{eff}} \le 2.0$ for $\ge 90\%$ runs | 40.0% in $[0.5, 2.0]$ | **FAIL** |
| | Underestimation Frequency | Report percentage $I_{\mathrm{eff}} < 1.0$ | 77.3% underestimation | **HIGH RISK** |
| **Secondary: Runtime** | $S_T = \frac{T_{\mathrm{ZZ}}}{T_{\mathrm{DWR}}}$ | Report wall-clock time at accuracy | $S_T \approx 0.10\times - 0.28\times$ | **SLOWER** |
| **Reference Uncertainty** | $U_{\mathrm{ref}} = \frac{1.25 \|J_3 - J_2\|}{(r^p - 1) \|J_3\|}$ | $U_{\mathrm{ref}} \le 0.05\%$ for 0.5% target | 1 of 4 verified ($0.013\%$) | **REF_UNCERTAIN (3)** |

---

## 4. Benchmark Problems and Regularised QoI Definitions

Four engineering benchmark problems were implemented in [verification/dwr/geometries.py](file:///f:/fem-edit-benchmark/verification/dwr/geometries.py):

```
Problem 1: Cantilever Beam            Problem 2: Plate with Circular Hole
+------------------------------+      +-------------------+
|                              |      |        (o)        |
|                              |-> ty |  ux=0       tx=1e7|->
+------------------------------+      +-------------------+
  x=0 clamped            x=2.0          x=0 roller        x=2.0

Problem 3: Notched Tensile Bar        Problem 4: L-Shaped Domain
+---------+  +---------+              +-----+
|         \__/         |-> ty         |     |
|                      |              |  Q  |
|         /--\         |              +-----+-----+
+---------+  +---------+              |     |     |-> ty
  y=0 clamped            y=0.8        +-----+-----+
                                        y=0 clamped
```

1. **Problem 1 — Cantilever Beam:**
   - Domain: $L = 2.0$, $H = 0.5$, thickness $t = 0.02$ m.
   - Material: $E = 70$ GPa, $\nu = 0.33$, plane stress.
   - Loading: Left boundary clamped ($u_x = 0, u_y = 0$), right boundary traction $t_y = -10^6$ N/m.
   - QoI: Boundary-average vertical displacement: $J(u) = \frac{1}{0.5} \int_{\Gamma_R} u_y \, d\Gamma$.
   - Variants: `structured_10x5`, `perturbed_10x5_seed12345`, `structured_16x8`.
2. **Problem 2 — Plate with Circular Hole:**
   - Domain: $L = 2.0$, $H = 1.0$, hole center $(1.0, 0.5)$, radius $R = 0.25$, thickness $t = 0.01$ m.
   - Material: $E = 200$ GPa, $\nu = 0.30$, plane stress.
   - Loading: Left boundary roller ($u_x = 0$), bottom-left corner pinned ($u_y(0,0) = 0$), right boundary tension $t_x = 10^7$ N/m.
   - QoI: Ligament patch average horizontal displacement: $\Omega_p = [0.95, 1.05] \times [0.75, 0.95]$ (area $|\Omega_p| = 0.020$ m$^2$), $J(u) = \frac{1}{|\Omega_p|} \int_{\Omega_p} u_x \, d\Omega$.
   - Variants: Conforming meshes `h014`, `h011`, `h009`.
3. **Problem 3 — Notched Tensile Bar:**
   - Domain: $L = 2.0$, $H = 0.8$, semicircular notches at $x = 1.0$ with $R = 0.15$ on top and bottom, thickness $t = 0.015$ m.
   - Material: $E = 210$ GPa, $\nu = 0.28$, plane stress.
   - Loading: Bottom edge clamped ($u_x = 0, u_y = 0$), top edge tension $t_y = 1.5 \times 10^7$ N/m.
   - QoI: Center ligament patch average vertical displacement: $\Omega_p = [0.90, 1.10] \times [0.35, 0.45]$ (area $|\Omega_p| = 0.020$ m$^2$), $J(u) = \frac{1}{|\Omega_p|} \int_{\Omega_p} u_y \, d\Omega$.
   - Variants: Conforming meshes `h014`, `h011`, `h009`.
4. **Problem 4 — L-Shaped Domain:**
   - Domain: $[0, 1.0]^2 \setminus (0.5, 1.0) \times (0.5, 1.0)$, thickness $t = 1.0$ m (plane strain).
   - Material: $E = 100$ GPa, $\nu = 0.25$, plane strain.
   - Loading: Bottom edge clamped ($y = 0$), bottom leg right edge shear $t_y = -5 \times 10^6$ N/m ($x = 1.0, y \in [0, 0.5]$).
   - Re-entrant corner at $(0.5, 0.5)$ generates stress singularity.
   - QoI: Top arm patch average vertical displacement: $\Omega_p = [0.10, 0.40] \times [0.60, 0.90]$ (area $|\Omega_p| = 0.090$ m$^2$), $J(u) = \frac{1}{|\Omega_p|} \int_{\Omega_p} u_y \, d\Omega$.
   - Variants: Conforming composite meshes `n4`, `n6`, `n8`.

All 12 problem/variant combinations pass unit test suite [tests/test_phase_b_geometries.py](file:///f:/fem-edit-benchmark/tests/test_phase_b_geometries.py).

---

## 5. Reference Solution Verification & Uncertainty Analysis

Reference solutions were computed via multi-level uniform refinement ($N_{\mathrm{DOFs}}$ up to 411,522) with Richardson extrapolation:

| Problem | Reference QoI $J_{\mathrm{ref}}$ | Highest DOFs | Apparent Order $p$ | GCI Uncertainty | Reference Status |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Cantilever** | $-1.909147 \times 10^{-3}$ m | 411,522 | 1.85 | **0.0132%** | **VERIFIED** ($\le 0.05\%$) |
| **Plate with Hole** | $6.977929 \times 10^{-5}$ m | 71,264 | 2.00 | **0.2097%** | `REF_UNCERTAIN_FINE` |
| **Notched Bar** | $1.987127 \times 10^{-5}$ m | 207,042 | 2.00 | **1.7582%** | `REF_UNCERTAIN` |
| **L-Shaped Domain** | $1.264247 \times 10^{-6}$ m | 99,330 | 2.00 | **0.2356%** | `REF_UNCERTAIN_FINE` |

- **Verification Determination:** Cantilever satisfies the strict $\le 0.05\%$ bound. Plate with hole and L-shaped domain exhibit GCI uncertainties ($\approx 0.21\% - 0.24\%$) suitable for 2.0% and 1.0% error evaluations, but exceed the $0.05\%$ criterion for the 0.5% target. Notched bar exhibits spatial gradient sensitivity yielding 1.76% GCI uncertainty, marked `REF_UNCERTAIN` pursuant to Section 9.

---

## 6. DWR Mathematical Implementation & Consistency Verification

The DWR reference estimator was implemented in [verification/dwr/dwr_estimator.py](file:///f:/fem-edit-benchmark/verification/dwr/dwr_estimator.py):
1. **Mathematical Representation:**
   The continuous dual-weighted residual error representation:
   $$J(u) - J(u_h) = R(u_h)(z - z_h)$$
   where $R(u_h)(v) = l(v) - a(u_h, v)$ is the weak residual.
2. **Enriched Space Selection:**
   Quadratic continuous Lagrange elements $V_{P_2} = \text{ElementTriP2()}$ on the triangulation $\mathcal{T}_h$.
   - Vertex values of $z^+ \in V_{P_2}$ define the $P_1$ projection $I_h z^+$.
   - Fluctuation $\psi = z^+ - I_h z^+ \in V_{P_2}$ vanishes identically at all vertices.
   - Nodal prolongation $P: V_{P_1} \to V_{P_2}$ embeds $u_h \in V_{P_1}$ into $V_{P_2}$.
   - Exact discrete error representation:
     $$\eta_{\mathrm{DWR}} = \psi^T (f_{P_2} - K_{P_2} P u_h) = (z^+)^T (f_{P_2} - K_{P_2} P u_h)$$
3. **Element-Level Indicator:**
   On each element $K \in \mathcal{T}_h$, local indicators $\eta_K$ are evaluated from weak element equilibrium:
   $$\eta_K = | \text{tr\_elem}_K(\psi) - a_K(u_h, \psi) |$$
   satisfying $\sum_K \eta_K \approx |\eta_{\mathrm{DWR}}|$.
4. **Consistency Verification (5/5 Passing Tests in [tests/test_dwr_consistency.py](file:///f:/fem-edit-benchmark/tests/test_dwr_consistency.py)):**
   - *Linear equilibrium zero residual:* Error $\le 10^{-14} \le 10^{-12}$ (**PASS**).
   - *Galerkin orthogonality:* $\|P^T (f_2 - K_2 P u_1)\|_{\infty} / \|f_1\|_{\infty} \le 10^{-13} \le 10^{-10}$ (**PASS**).
   - *Algebraic identity on enriched space:* $|g_2^T (u_2 - P u_1) - \eta_{\mathrm{DWR}}| \le 10^{-12}$ (**PASS**).
   - *Elemental indicator sum:* Consistent across all 4 geometries (**PASS**).
   - *Monotonic refinement convergence:* $\eta_{\mathrm{DWR}}(h/2) / \eta_{\mathrm{DWR}}(h) \ge 1.5$ (**PASS**).

---

## 7. Comparative Performance at Accuracy Targets

Evaluated across 48 adaptive simulations with Dörfler marking fraction $\theta = 0.40$:

### Primary Hypothesis Evaluation: 1.0% True Relative Error Target

| Benchmark Problem | Median $N_{\mathrm{DOF,ZZ}}$ | Median $N_{\mathrm{DOF,DWR}}$ | Median Savings $S_{\mathrm{DOF}}$ | Variant 0 $S_{\mathrm{DOF}}$ | Variant 1 $S_{\mathrm{DOF}}$ | Variant 2 $S_{\mathrm{DOF}}$ | Target Met? |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Cantilever** | 3,904 | 5,016 | **0.838** | 0.778 | 1.577 | 0.838 | **NO** |
| **Plate with Hole** | 2,058 | 2,834 | **0.886** | 0.886 | 2.548 | 0.520 | **NO** |
| **Notched Bar** | 782 | 1,250 | **1.128** | 2.335 | 1.128 | 0.626 | **NO** |
| **L-Shaped Domain** | 450 | 450 | **1.035** | 1.035 | 6.545 | 1.000 | **NO** |
| **Geometric Mean** | — | — | **0.965** | — | — | — | **FAIL** |

### Computational Time Comparison: 1.0% Target

| Benchmark Problem | Cumulative Time $T_{\mathrm{ZZ}}$ | Cumulative Time $T_{\mathrm{DWR}}$ | Speedup Ratio $S_T = \frac{T_{\mathrm{ZZ}}}{T_{\mathrm{DWR}}}$ | DWR Overhead Factor |
|:---|:---:|:---:|:---:|:---:|
| **Cantilever** | 0.108 s | 1.050 s | **0.103x** | $9.75\times$ slower |
| **Plate with Hole** | 0.061 s | 0.635 s | **0.137x** | $7.30\times$ slower |
| **Notched Bar** | 0.019 s | 0.184 s | **0.196x** | $5.10\times$ slower |
| **L-Shaped Domain** | 0.014 s | 0.053 s | **0.283x** | $3.53\times$ slower |

---

## 8. Estimator Reliability & Effectivity Analysis

Evaluation of $\eta_{\mathrm{DWR}}$ across all 75 eligible simulation iterations:

```
Effectivity Distribution:
  < 0.5 (Severe Underestimation):  [##########] 41.3%
  [0.5, 2.0] (Reliable Bound):     [##########] 40.0%  <-- Target >= 90%
  > 2.0 (Overestimation):          [#####     ] 18.7%
```

- **In-Bounds Fraction:** 40.0% (Target $\ge 90\% \implies$ **FAIL**).
- **Mean Signed Effectivity:** 1.134.
- **Median Absolute Effectivity:** 0.445.
- **Fraction Below 1.0 (Underestimation):** **77.3%**.
- **Maximum Underestimation:** 99.5% ($I_{\mathrm{eff}} = 0.005$).

### Analysis of Effectivity Underestimation
On pre-asymptotic meshes with stress concentrations, the $P_2$ dual solution captures higher-gradient curvature than the coarse $P_1$ primal mesh can support. Consequently, the dual weighted residual underestimates the true continuum error during early iterations. This presents a safety risk if used as a stopping criterion in engineering design.

---

## 9. Failure Analysis & Detailed Observations

### Why Did DWR Fail to Consistently Outperform ZZ?
1. **Regularised Patch Integrals Dampen Error Localization:**  
   Unlike idealized point evaluations (which are mathematically unbounded in $H^1$), engineering patch averages integrate displacements over a finite region $\Omega_p$. On rectangular or smooth domains, global energy norm recovery (ZZ) refines the high-stress regions that drive compliance, which simultaneously reduces errors in downstream patch displacements at a lower cost than a localized dual solve.
2. **Dual-Solve Computational Overhead:**  
   The $P_2$ enriched adjoint requires $(N_v + N_f) \times 2$ DOFs (roughly $4\times$ the primal system size) and a full sparse factorization at every adaptive iteration. Even when DWR reduced primal DOFs on specific meshes, its wall-clock runtime was $4\times$ to $10\times$ worse than ZZ.
3. **Sensitivity to Initial Mesh Configuration:**  
   On coarse unrefined meshes (e.g. L-shaped variant 1), DWR achieved an $84.7\%$ DOF reduction ($S_{\mathrm{DOF}} = 6.55$) because ZZ wasted elements refining the non-critical corner singularity. But when initial meshes were uniformly graded (variant 0 and 2), ZZ achieved equivalent QoI accuracy at lower or identical DOF counts ($S_{\mathrm{DOF}} = 1.00 - 1.03$).

---

## 10. Publication Figures & Archival Artifacts

All figures have been generated directly from the 48 raw simulation records in `results/phase_b/raw/` and are archived in [results/phase_b/plots/](file:///f:/fem-edit-benchmark/results/phase_b/plots/):
- `dof_vs_error_cantilever.png`
- `dof_vs_error_plate_with_hole.png`
- `dof_vs_error_notched_bar.png`
- `dof_vs_error_l_shaped.png`
- `effectivity_distribution.png`
- `runtime_vs_error.png`
- `repeated_mesh_sensitivity.png`

---

## 11. Conclusion & Next Steps

Phase B demonstrates that **goal-oriented DWR does not justify continuation as GDEC's central architectural differentiator**.

While the DWR implementation passed all mathematical and algebraic consistency checks, its pre-registered performance fell substantially short of the 30% DOF savings target (achieving a geometric mean of only 0.965), exhibited frequent error underestimation (77.3%), and incurred severe computational overhead ($4\times - 10\times$ slower runtime).

In accordance with Section 15 of the brief, all Phase B deliverables are completed and frozen on branch `phase-b/dwr-vs-zz`. No further development (such as compiler expansion, P2 production FEM, 3D, or CUDA) will be initiated without explicit instruction.
