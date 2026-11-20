# GDEC — PHASE B.1.1
## Accounting Corrections & Telemetry Consistency Report

**Repository:** `delythassociates/GDEC`  
**Audit Date:** 2026-11-20  
**Baseline Commit:** `85721d88b2817eb2a132ed04966bd3085ff256e4`  
**Foundation Commit:** `01260409a0e11d8dcf97729ea25a61f20e2a4772`  
**Branch:** `phase-c/preflight-and-pilots`  
**Immutable Constraint:** Zero simulations were rerun. All historical raw files in `results/phase_b/` and `results/phase_b1/` remain untouched.

---

## 1. Objective

Phase B.1.1 resolves three accounting and telemetry defects identified in the Phase B/B.1 experimental framework:
1. **DWR Internal Primal Recomputation**: The timing breakdown previously lumped internal $P_1$ recomputation inside the DWR estimator rather than explicitly distinguishing outer vs. inner primal solves.
2. **Time-to-Target Post-Refinement Deduction**: The target evaluator charged the refinement time of the target iteration itself, even though the solution on that iteration had already satisfied the error target before refinement was invoked.
3. **Mesh Telemetry Consistency**: Ambiguities in reporting element counts vs. DOF counts across refined states have been resolved by introducing explicit, immutable state descriptors.

---

## 2. DWR Internal Primal Solve Accounting

### 2.1 The Issue
In the Phase B/B.1 experimental harness:
1. The outer adaptive runner assembled and solved the primal $P_1$ problem on the current mesh $\mathcal{T}_h$ to obtain the solution $u_h$ and compute true error ($t_{\text{primal}}$).
2. Inside `DWREstimator.estimate(mesh)`, the estimator was structured to be self-contained for standalone unit testing, and therefore independently re-assembled and re-solved the $P_1$ primal system.
3. In Phase B, this redundant inner solve was included in the total wall-clock time, but was not broken down separately in component-level telemetry.

### 2.2 Corrected Timing Decomposition
In `verification/dwr/dwr_estimator.py` and `verification/dwr/adaptive_runner.py`, the execution phases are now explicitly and non-overlappingly instrumented:

$$\begin{aligned}
T_{\text{total,iter}} &\ge t_{\text{primal,outer}} + t_{\text{dwr,internal\_primal}} + t_{\text{p2\_assembly}} + t_{\text{p2\_adjoint\_solve}} \\
&\quad + t_{\text{estimator}} + t_{\text{marking}} + t_{\text{refinement}}
\end{aligned}$$

Where:
- $t_{\text{primal,outer}}$: Primal $P_1$ basis setup, stiffness assembly, boundary conditions, linear solve, and QoI evaluation.
- $t_{\text{dwr,internal\_primal}}$: Standalone internal $P_1$ re-assembly and re-solve within the DWR estimator.
- $t_{\text{p2\_assembly}}$: Enriched $P_2$ basis, stiffness matrix $K_2$, load vector $f_2$, adjoint load $g_2$, prolongation operator $P$, and boundary conditions.
- $t_{\text{p2\_adjoint\_solve}}$: Enriched $P_2$ adjoint linear solve ($K_2 z_2 = g_2$).
- $t_{\text{estimator}}$: Dual-weighted residual evaluation $\psi^T (f_2 - K_2 P u_1)$ and elemental indicator calculation.
- $t_{\text{marking}}$: Dörfler marking.
- $t_{\text{refinement}}$: Mesh subdivision and adjacency reconstruction.

*Note:* Historical total wall-clock measurements contain this redundant internal work, reflecting the actual unoptimised execution time. In this phase, no DWR solver optimizations were applied; only the accounting has been made transparent.

---

## 3. Time-to-Target Accounting Correction

### 3.1 The Issue
When evaluating whether a method meets an error target (e.g. 1.0% error) at iteration $k$:
- Iterations $0, \dots, k-1$ required their full iteration time, including their refinement time to produce mesh $k$.
- At iteration $k$, the solution $u_k$ is computed and tested against the target.
- If $u_k$ satisfies the target, the simulation has **already reached its goal**. Any subsequent refinement of mesh $k$ generates mesh $k+1$, which is unnecessary for attaining the target at iteration $k$.
- Previously, `find_target_metrics` summed $\sum_{i=0}^k t_{\text{total,iter}, i}$, erroneously including the post-target refinement $t_{\text{refinement}, k}$.

### 3.2 Corrected Time-to-Target Formula
In `verification/dwr/evaluator.py`:
$$T_{\text{target}}(k) = \sum_{i=0}^{k-1} t_{\text{total,iter}, i} + \left( t_{\text{total,iter}, k} - t_{\text{refinement}, k} \right)$$

This formula was tested in `tests/test_phase_b1_1_accounting.py::test_time_to_target_excludes_post_target_refinement` and recomputed across all existing Phase B.1 records without rerunning simulations.

### 3.3 Impact on Speedup Ratio ($S_T = \frac{T_{\text{ZZ}}}{T_{\text{DWR}}}$) at 1.0% Error Target

| Benchmark Problem | Phase B (Excl. Refine) | Phase B.1 (Full Wall-Clock) | Phase B.1.1 (Excl. Post-Target Refine) | Speedup Ratio $S_T$ |
| :--- | :---: | :---: | :---: | :---: |
| **Cantilever** | $0.103\times$ | $0.163\times$ | **$0.151\times$** | **$6.6\times$ slower** |
| **Plate with Hole** | $0.137\times$ | $0.202\times$ | **$0.198\times$** | **$5.1\times$ slower** |
| **Notched Bar** | $0.196\times$ | $0.228\times$ | **$0.213\times$** | **$4.7\times$ slower** |
| **L-Shaped Domain** | $0.283\times$ | $0.325\times$ | **$0.325\times$** | **$3.1\times$ slower** |

*Conclusion:* Properly deducting post-target refinement from the target iteration leaves DWR between **$3.1\times$ and $6.6\times$ slower** than ZZ recovery across all benchmarks.

---

## 4. Mesh Telemetry Consistency

To eliminate state confusion between pre-refinement and post-refinement mesh data, future telemetry schemas define:
- `solved_mesh_elements`: Exact triangle count of the mesh on which the primal problem was solved.
- `solved_mesh_dofs`: Exact primal DOF count ($2 \times N_{\text{nodes}}$) of the solved mesh.
- `next_mesh_elements`: Triangle count after refinement (or `None` if terminal step).
- `next_mesh_dofs`: `None` until basis assembly on next iteration.
- `mesh_state_id`: Deterministic identifier `f"{problem}_{method}_var{variant}_iter{iteration}"`.

Legacy fields `nelements` and `primal_dofs` are preserved for backward compatibility and are strictly mapped to `solved_mesh_elements` and `solved_mesh_dofs`.

---

## 5. Verification Test Suite Output
```text
tests/test_phase_b1_1_accounting.py::test_time_to_target_excludes_post_target_refinement PASSED
tests/test_phase_b1_1_accounting.py::test_dwr_internal_primal_decomposition_non_overlapping PASSED
tests/test_phase_b1_1_accounting.py::test_mesh_telemetry_consistency PASSED
============================== 3 passed in 1.24s ==============================
```
**Exit Code:** `0`.
