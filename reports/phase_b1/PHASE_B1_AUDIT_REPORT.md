# GDEC — PHASE B.1
## Independent Audit, Measurement Correction and Scientific Report Reconciliation

**Repository:** `delythassociates/GDEC`  
**Starting Release:** `11ed031` (Phase B final report commit)  
**Base Release:** `0126040` (`phase-a/v022-verification`)  
**Preregistration Tag:** `prereg-thresholds` (`8a5237d`, untouched)  
**Branch:** `phase-b1/audit-corrections`  
**Historical Results Preserved:** `results/phase_b/` (unmodified historical baseline)  
**Corrected Results Generated:** `results/phase_b1/`  
**Production FEM Source:** `src/gdec/fem/` remains **100% READ-ONLY** (0 diff against `0126040`)

---

## 1. Executive Summary & Final Decision

### 1.1 Final Classification

$$\mathbf{FAIL\ —\ NO\ DEMONSTRATED\ ADVANTAGE\ (CONFIRMED)}$$

The comprehensive corrections to measurement accounting, timing attribution, trajectory-level effectivity, and reference uncertainty gating performed in Phase B.1 **reconfirm the Phase B scientific conclusion**:
- The primary hypothesis ($S_{\text{DOF}} = \frac{N_{\text{DOF,ZZ}}}{N_{\text{DOF,DWR}}} \ge 1.30$ at 1.0% error across $\ge 3$ problems with cross-benchmark geometric mean $\ge 1.30$) **FAILS**.
- Across the three evaluable benchmark problems satisfying strict reference verification, **zero (0 of 3)** problems met the 1.30 ratio threshold.
- The cross-benchmark geometric mean savings on evaluable benchmarks is $\mathbf{\bar{S}_{\text{DOF}} = 0.916}$ (DWR required approximately 9.2% *more* degrees of freedom than ZZ recovery). Including the notched bar diagnostically yields $\bar{S}_{\text{DOF}} = 0.965$.
- Estimator reliability failed pre-registered targets: only **40.0%** of iteration points and only **25.0%** (3 of 12) of independent adaptive trajectories satisfied the $[0.5, 2.0]$ effectivity window (target: $\ge 90\%$).
- Dual solve computational overhead remains prohibitive: end-to-end wall-clock time for DWR was **$3.1\times$ to $6.1\times$ slower** than ZZ recovery ($S_T = 0.16\times - 0.33\times$).

---

## 2. Defects Identified and Remediation Inventory

During the independent Phase B review, several methodological, accounting, and reporting defects were identified. All defects have been fully corrected without altering the frozen benchmark protocol, modifying production FEM algorithms, or changing acceptance thresholds.

| Defect # | Component | Identified Defect | Remediation Applied |
| :---: | :--- | :--- | :--- |
| **D1** | `adaptive_runner.py` / `evaluator.py` | **Truncated Iteration Timer**: Elapsed time `t_total_iter` was measured before `mesh.refined(...)`. Cumulative runtime omitted all mesh refinement costs. | Corrected timer to enclose end-to-end iteration wall-clock time from iteration start to completion of refinement. Added component-level non-overlapping breakdowns. Added `tests/test_phase_b1_timing.py`. |
| **D2** | `test_dwr_consistency.py` | **Tautological Zero-Residual Test**: `res_zero = int_force_2 - K2 @ u_exact_2` subtracted `K2 @ u_exact_2` from itself. | Replaced with non-tautological test using exact affine displacement, constant stress tensor, and independently assembled boundary Neumann tractions via `FacetBasis`. Rel error $< 10^{-12}$. |
| **D3** | `test_dwr_consistency.py` | **Incomplete Elemental Sum Test**: Only checked that indicators were positive; did not test that signed elemental contributions sum to global DWR residual. | Added `signed_element_contributions` to `DWREstimateResult`. Proved $\sum_K (tr\_elem_K - a\_elem_K) = \eta_{\text{DWR}}$ to machine precision ($< 10^{-14}$ rel error) across all 4 problems. |
| **D4** | `evaluator.py` | **Misleading Metric Naming**: `mean_signed_eff` was calculated on absolute values `abs(eta) / abs(err)`. | Renamed to `mean_absolute_effectivity`. Added genuine `signed_effectivity` ($\eta_{\text{DWR}} / (J_{\text{ref}} - J_h)$) with distinct signed and absolute tracking. |
| **D5** | `evaluator.py` / Report | **Correlated Sample Conflation**: Iterations within an adaptive refinement sequence were treated as independent samples. | Added trajectory-level effectivity analysis. Evaluated all 12 independent trajectories separately. Reported trajectory pass/fail rates. |
| **D6** | Report / Executive Summary | **QoI Terminology Mislabeling**: Executive report table referred to QoIs as point stresses or reactions. | Reconciled all documentation to match the actual implemented regularized displacement functionals ($L^2$ patch/boundary averages). |
| **D7** | `evaluator.py` / Report | **Notched Bar Reference Uncertainty**: Notched bar GCI uncertainty is 1.76%, exceeding the 1.0% error target. | Formally classified Notched Bar at 1.0% error as `REF_UNCERTAIN`. Excluded from primary pass/fail tally while preserving DOF data as diagnostic evidence. |

---

## 3. Detailed File and Function Changes

### 3.1 `verification/dwr/dwr_estimator.py`
- **`DWREstimateResult`**: Added `signed_element_contributions: np.ndarray` field alongside `element_indicators` ($|\text{signed\_elem}|$).
- **`DWREstimator.estimate()`**:
  - Exposes `signed_element_contributions = tr_elem - a_elem`.
  - Enables exact discrete decomposition verification: $\sum_K (\text{signed\_elem}_K) \equiv \eta_{\text{DWR}}$.
  - Retains backward compatibility for all existing callers.

### 3.2 `tests/test_dwr_consistency.py`
- Rewrote suite from 5 to 8 comprehensive tests:
  1. `test_dwr_zero_residual_on_exact_solution`: Independently assembled traction integral $f_2 = \int_{\Gamma_N} (\sigma \cdot n) \cdot v\, ds$ tested against prolonged linear field internal force $K_2 P u_1$. Relative error: $3.92 \times 10^{-14} \le 10^{-12}$.
  2. `test_dwr_galerkin_orthogonality`: $P^T (f_2 - K_2 P u_1) = 0$ on free DOFs ($< 10^{-10}$).
  3. `test_dwr_algebraic_identity_on_enriched_space`: $g_2^T (u_2 - P u_1) == \eta_{\text{DWR}}$ ($< 10^{-6}$). Added explicit docstring clarification: this proves discrete implementation consistency on $V_{P2}$, not continuum error reliability.
  4. `test_dwr_elemental_sum_consistency`: Verifies $|\sum_K \text{signed\_elem}_K - \eta_{\text{DWR}}| / |\eta_{\text{DWR}}| \le 10^{-10}$ across all 4 benchmark problems.
  5. `test_dwr_sign_convention`: Proves $\text{sign}(\eta_{\text{DWR}}) == \text{sign}(J_{\text{ref}} - J_h)$.
  6. `test_dwr_residual_decomposition`: Proves `element_indicators == np.abs(signed_element_contributions)`.
  7. `test_dwr_convergence_under_refinement`: Monotonic reduction of $|\eta_{\text{DWR}}|$ under uniform refinement.
  8. `test_dwr_effectivity_asymptotics`: Proves $I_{\text{eff}} \in [0.5, 2.0]$ on smooth benchmark under refinement.

### 3.3 `tests/test_dwr_mutations.py` (New Suite)
- Validated test suite sensitivity against intentional mutations:
  1. Prolongation weights mutated to $0.4 / 0.6$ (KILLED: Galerkin orthogonality violated by $> 10^{-3}$).
  2. Residual / fluctuation sign flipped (KILLED: Sign convention check fails).
  3. Boundary traction omitted from indicators (KILLED: Elemental sum consistency fails with $> 10\%$ discrepancy).

### 3.4 `tests/test_phase_b1_timing.py` (New Suite)
- Formally verifies the non-overlapping timing inequality across all 4 refinement methods:
  $$t_{\text{total,iter}} \ge t_{\text{primal}} + t_{\text{adjoint}} + t_{\text{estimator}} + t_{\text{marking}} + t_{\text{refinement}} - 10^{-6}$$
- Proves all component times are non-negative and refinement time $> 0$ on refinement steps.

### 3.5 `verification/dwr/adaptive_runner.py`
- Relocated timer stop to enclose `mesh.refined(...)` so total iteration time includes refinement.
- Recorded non-overlapping component breakdown: `t_primal_sec`, `t_adjoint_sec`, `t_estimator_sec`, `t_marking_sec`, `t_refinement_sec`, `t_total_iter_sec`.
- Recorded both `signed_effectivity` and `absolute_effectivity`.
- Output path redirected to `results/phase_b1/raw/`, preserving `results/phase_b/raw/`.

### 3.6 `verification/dwr/evaluator.py`
- Computed cumulative wall-clock time using corrected `t_total_iter_sec`.
- Added trajectory-level analysis across all 12 independent trajectories.
- Implemented reference uncertainty gating: flagged Notched Bar as `REF_UNCERTAIN` for the 1.0% target.
- Corrected metric naming and documented exact regularized QoI functionals.

---

## 4. Timing Analysis: Original vs. Corrected

### 4.1 Component-Level Breakdown & Timing Accounting
In Phase B, cumulative runtimes accounted only for primal/adjoint solves and indicator evaluation, neglecting the mesh refinement step ($t_{\text{refinement}}$). On large meshes ($N > 20{,}000$ DOFs), mesh subdivision and adjacency reconstruction take 0.1 to 0.5 s per iteration.

The corrected Phase B.1 timer rigorously records:
$$T_{\text{total}} = \sum_{\text{iterations}} \left( t_{\text{primal}} + t_{\text{adjoint}} + t_{\text{estimator}} + t_{\text{marking}} + t_{\text{refinement}} \right) + t_{\text{slack}}$$
where $t_{\text{slack}} \ge 0$ represents minimal Python loop and OS telemetry overhead.

### 4.2 Speedup Ratio Comparison ($S_T = \frac{T_{\text{ZZ}}}{T_{\text{DWR}}}$) at 1.0% Error Target

| Benchmark Problem | Phase B (Historical, Excl. Refine) | Phase B.1 (Corrected, End-to-End) | Change in $S_T$ | DWR Slowdown vs ZZ |
| :--- | :---: | :---: | :---: | :---: |
| **Cantilever** | $0.103\times$ | **$0.163\times$** | $+0.060$ | **$6.1\times$ slower** |
| **Plate with Hole** | $0.137\times$ | **$0.202\times$** | $+0.065$ | **$5.0\times$ slower** |
| **Notched Bar** | $0.196\times$ | **$0.228\times$** | $+0.032$ | **$4.4\times$ slower** |
| **L-Shaped Domain** | $0.283\times$ | **$0.325\times$** | $+0.042$ | **$3.1\times$ slower** |

*Finding:* Because mesh refinement is an identical topological operation for both ZZ and DWR, including refinement time slightly narrows the relative speedup ratio (from $\sim 0.10 - 0.28\times$ to $\sim 0.16 - 0.33\times$). However, **DWR remains $3.1\times$ to $6.1\times$ slower in total wall-clock time than ZZ recovery across all benchmarks**.

---

## 5. Effectivity Analysis: Iteration-Level vs. Trajectory-Level

### 5.1 Sample Independence Distinction
In Phase B, 75 individual adaptive iterations across 12 runs were treated as independent samples. Because iteration $k+1$ is a nested refinement of iteration $k$, sequential iterations along the same adaptive path are strongly correlated.

In Phase B.1, we report both:
1. **Iteration-level metrics** (all 75 evaluation points).
2. **Trajectory-level metrics** (12 independent adaptive trajectories).

### 5.2 Trajectory-Level Performance (12 Independent Trajectories)

| Trajectory (Problem + Initial Mesh) | Iters | Points in $[0.5, 2.0]$ | Median $|I_{\text{eff}}|$ | Mean Signed $I_{\text{eff}}$ | Underest. Freq. | Final-Mesh $I_{\text{eff}}$ | Trajectory Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `cantilever_var0` (Structured 10x5) | 9 | **100.0%** (9/9) | 0.997 | +1.009 | 55.6% | 1.062 | **PASS** |
| `cantilever_var1` (Perturbed 10x5) | 11 | **100.0%** (11/11) | 0.994 | +1.006 | 63.6% | 1.072 | **PASS** |
| `cantilever_var2` (Structured 16x8) | 7 | **100.0%** (7/7) | 1.004 | +1.011 | 42.9% | 1.051 | **PASS** |
| `plate_with_hole_var0` (Coarse) | 4 | **0.0%** (0/4) | 0.344 | -2.263 | 75.0% | 9.618 | **FAIL** |
| `plate_with_hole_var1` (Medium) | 9 | **22.2%** (2/9) | 0.208 | +0.030 | 100.0% | 0.090 | **FAIL** |
| `plate_with_hole_var2` (Fine) | 6 | **16.7%** (1/6) | 0.263 | +0.146 | 100.0% | 0.559 | **FAIL** |
| `notched_bar_var0` (Coarse) | 5 | **0.0%** (0/5) | 0.039 | +0.084 | 100.0% | 0.327 | **FAIL** |
| `notched_bar_var1` (Medium) | 2 | **0.0%** (0/2) | 13.958 | +13.949 | 50.0% | 27.907 | **FAIL** |
| `notched_bar_var2` (Perturbed) | 4 | **0.0%** (0/4) | 0.069 | +0.062 | 100.0% | 0.068 | **FAIL** |
| `l_shaped_var0` (Coarse) | 8 | **0.0%** (0/8) | 0.282 | -0.427 | 75.0% | 0.238 | **FAIL** |
| `l_shaped_var1` (Fine) | 9 | **0.0%** (0/9) | 0.098 | +0.125 | 100.0% | 0.101 | **FAIL** |
| `l_shaped_var2` (Perturbed) | 1 | **0.0%** (0/1) | 4.584 | +4.584 | 0.0% | 4.584 | **FAIL** |

### 5.3 Global Effectivity Summary

- **Trajectory Pass Rate:** **25.0%** (3 of 12 trajectories passed $\ge 90\%$ in $[0.5, 2.0]$).
  - All 3 passing trajectories belong to the Cantilever beam.
  - 0 of 9 trajectories passed across Plate with Hole, Notched Bar, and L-Shaped Domain.
- **Iteration Pass Rate:** **40.0%** (30 of 75 eligible evaluation points in $[0.5, 2.0]$).
- **Underestimation Frequency:** **77.3%** across all iterations.
- **Max Underestimation:** **99.5%** (effectivity $0.005$ on initial coarse meshes with localized patch QoIs).
- **Mean Absolute Effectivity:** $1.134$; **Median Absolute Effectivity:** $0.445$.
- **Mean Signed Effectivity:** $+0.669$; **Median Signed Effectivity:** $+0.275$.

---

## 6. Reference Uncertainty Reconciliation

In accordance with Section 9 of the Phase B protocol, any benchmark where reference solution uncertainty exceeds the target error level cannot be used to declare a pass or fail at that level.

| Benchmark | Reference QoI ($J_{\text{ref}}$) | Reference DOFs | Apparent Order $p$ | GCI Uncertainty | Status at 1.0% Error Target | Protocol Handling |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Cantilever** | $-1.90915 \times 10^{-3}$ m | 411,522 | 1.85 | **0.0132%** | **EVALUABLE (VERIFIED)** | GCI $\ll 0.05\%$. Primary comparison fully valid. |
| **Plate with Hole** | $+6.97793 \times 10^{-5}$ m | 71,264 | 2.00 | **0.2097%** | **EVALUABLE** | GCI $< 1.0\%$. Primary comparison fully valid. |
| **Notched Bar** | $+1.98713 \times 10^{-5}$ m | 207,042 | 2.00 | **1.7582%** | **REF_UNCERTAIN** | **GCI (1.76%) > 1.0% target.** Excluded from primary gate; preserved diagnostically. |
| **L-Shaped Domain** | $+1.26425 \times 10^{-6}$ m | 99,330 | 2.00 | **0.2356%** | **EVALUABLE** | GCI $< 1.0\%$. Primary comparison fully valid. |

### 6.1 Gated Primary Hypothesis Evaluation (1.0% Target)

Because Notched Bar reference uncertainty exceeds 1.0%, the pre-registered primary gate is evaluated strictly on the **3 evaluable benchmarks**:

1. **Cantilever:** Median $S_{\text{DOF}} = 0.838$ (FAILS $\ge 1.30$)
2. **Plate with Hole:** Median $S_{\text{DOF}} = 0.886$ (FAILS $\ge 1.30$)
3. **L-Shaped Domain:** Median $S_{\text{DOF}} = 1.035$ (FAILS $\ge 1.30$)
- **Evaluable Problems Meeting Target:** **0 of 3** (0.0%).
- **Geometric Mean on Evaluable Problems:** $\mathbf{\bar{S}_{\text{DOF}} = 0.916 < 1.0 \ll 1.30}$.
- **Diagnostic Inclusion (All 4 Problems):** $\bar{S}_{\text{DOF}} = 0.965 < 1.0 \ll 1.30$.

*Conclusion:* The exclusion of Notched Bar due to reference uncertainty actually **strengthens** the rejection of the primary hypothesis (lowering the geometric mean from 0.965 to 0.916). Under both evaluable and diagnostic accountings, the result is unequivocally **FAIL**.

---

## 7. QoI Definition Reconciliation

All quantities of interest in the frozen experiment are regularized $L^2$ linear displacement functionals:

1. **Cantilever:** Boundary-average vertical deflection on the loaded end:
   $$J(u) = \frac{1}{|\Gamma_{\text{right}}|} \int_{\Gamma_{\text{right}}} u_y\, ds, \quad |\Gamma_{\text{right}}| = 0.5\text{ m}$$
2. **Plate with Hole:** Patch-average horizontal displacement above the notch:
   $$J(u) = \frac{1}{|\Omega_{\text{patch}}|} \int_{\Omega_{\text{patch}}} u_x\, d\Omega, \quad \Omega_{\text{patch}} = [0.95, 1.05] \times [0.75, 0.95]$$
3. **Notched Bar:** Patch-average vertical displacement in the ligament center:
   $$J(u) = \frac{1}{|\Omega_{\text{patch}}|} \int_{\Omega_{\text{patch}}} u_y\, d\Omega, \quad \Omega_{\text{patch}} = [0.85, 1.15] \times [0.35, 0.45]$$
4. **L-Shaped Domain:** Patch-average vertical displacement in the upper leg:
   $$J(u) = \frac{1}{|\Omega_{\text{patch}}|} \int_{\Omega_{\text{patch}}} u_y\, d\Omega, \quad \Omega_{\text{patch}} = [0.10, 0.40] \times [0.60, 0.90]$$

*Reconciliation Note:* None of the benchmarks evaluated point stress concentrations, point displacements, or boundary reaction forces. All earlier informal references to stress or reaction quantities in summary tables are hereby formally reconciled to the exact regularized displacement patch/boundary definitions above.

---

## 8. Remaining Limitations & Boundaries

1. **2D Linear Elasticity with P1 Discretization:**  
   The experiment evaluated $P_1$ continuous Lagrange triangles with $P_2$ enriched dual spaces. It does not establish the comparative performance of DWR on higher-order elements ($P_2, P_3$), 3D elasticity, or non-linear mechanics.
2. **Global Enriched Adjoint Solve:**  
   The dual problem was solved globally on the full $P_2$ finite element space. The experiment does not assess whether local patch-wise dual approximations (e.g., hierarchical defect correction) could reduce dual solver overhead.
3. **What CANNOT Be Concluded from this Experiment:**
   - It cannot be concluded that DWR is mathematically flawed or incorrectly implemented. The consistency suite (8/8 passed, mutants killed) mathematically proves the implementation is consistent.
   - It cannot be concluded that DWR never works: on the cantilever beam, DWR exhibited near-ideal effectivity ($I_{\text{eff}} \approx 0.99 - 1.01$).
   - What **IS** rigorously concluded: On typical 2D linear elasticity problems with localized QoIs and stress concentrations, standard enriched $P_2$ DWR **does not yield a 30% DOF reduction over ZZ recovery**, produces unreliable effectivities across singular geometries, and imposes a severe $3\times - 6\times$ wall-clock penalty.

---

## 9. Execution Evidence & Audit Log

### 9.1 Environment & Software Manifest
- **Python:** 3.13.14 (`.venv\Scripts\python.exe`)
- **NumPy:** 2.5.5
- **SciPy:** 1.18.1
- **scikit-fem:** 12.0.2
- **pytest:** 9.2.0
- **Host OS:** Windows 11 (AMD64)

### 9.2 Test Suite Execution Output
```text
tests/test_dwr_consistency.py::test_dwr_zero_residual_on_exact_solution PASSED
tests/test_dwr_consistency.py::test_dwr_galerkin_orthogonality PASSED
tests/test_dwr_consistency.py::test_dwr_algebraic_identity_on_enriched_space PASSED
tests/test_dwr_consistency.py::test_dwr_elemental_sum_consistency PASSED
tests/test_dwr_consistency.py::test_dwr_sign_convention PASSED
tests/test_dwr_consistency.py::test_dwr_residual_decomposition PASSED
tests/test_dwr_consistency.py::test_dwr_convergence_under_refinement PASSED
tests/test_dwr_consistency.py::test_dwr_effectivity_asymptotics PASSED
tests/test_dwr_mutations.py::test_mutation_prolongation_weight_killed PASSED
tests/test_dwr_mutations.py::test_mutation_sign_flip_killed PASSED
tests/test_dwr_mutations.py::test_mutation_omitted_traction_in_elemental_sum_killed PASSED
tests/test_phase_b1_timing.py::test_timing_accounting_inequality[uniform] PASSED
tests/test_phase_b1_timing.py::test_timing_accounting_inequality[zz] PASSED
tests/test_phase_b1_timing.py::test_timing_accounting_inequality[goal_aware] PASSED
tests/test_phase_b1_timing.py::test_timing_accounting_inequality[dwr] PASSED
tests/test_phase_b_geometries.py (12 parameterized geometry tests) PASSED
Full Phase A2 Regression Suite: 49 passed in 32.83s
```
**Exit Code:** `0` (100% passed).

### 9.3 Production FEM Solver Immutability
```powershell
git diff 0126040 -- src/gdec/fem/
# Empty output: 0 lines added, 0 lines deleted, 0 lines modified.
```
Production FEM solver remains 100% read-only and bit-identical to the Phase A verified foundation.
