# GDEC Audit Phase 7: Benchmark Forensic Audit & Equal-Accuracy Verification

**Audit Date**: 2026-11-20  
**Auditor**: Independent Technical Software Auditor & Verification Specialist  
**Target Codebase**: GDEC Version 0.2 (`src/gdec/benchmark/`, `results/`)  
**Status**: VERIFIED (with critical observations on numerical tolerance margins)  

---

## 1. Executive Summary

A forensic audit of the benchmarking methodology, multi-resolution reference solution, equal-accuracy evaluation algorithm, full-precision error tolerances, wall-clock timing instrumentation, and potential hardcoding was executed.

### Core Audit Findings
1. **Dynamic Execution & Anti-Hardcoding**: No hardcoded benchmark results, synthetic convergence curves, or static fallback CSVs exist. Simulations, reference solves, and equal-accuracy evaluations execute dynamically from compiled IR.
2. **Experimental Controls**: All three strategies (Uniform, Recovery, Goal-Aware) run under identical conditions: identical geometry, material, loads, boundary conditions, initial mesh (200 DOFs), and stopping controllers.
3. **Reference Convergence Uncertainty**: The primary reference solution ($N_3 = 29,768$ DOFs) has an estimated discretization uncertainty of $\mathbf{0.061\%}$ relative to Level 2 ($N_2 = 19,208$ DOFs).
4. **Equal-Accuracy Boundary Condition**: At the strictest target ($\le 0.25\%$), Goal-Aware reaches an unrounded error of **`0.249743%`**, technically satisfying $\le 0.25\%$. However, the margin ($0.000257\%$) is smaller than the reference solution's discretization uncertainty ($0.061\%$).

---

## 2. Reference Solution Audit

The reference solver (`src/gdec/benchmark/reference.py`) solves three progressively finer meshes:
- **Level 1**: $144 \times 36$ grid, 10,368 DOFs, $J_1 = -1.903366\text{ mm}$
- **Level 2**: $196 \times 49$ grid, 19,208 DOFs, $J_2 = -1.906130\text{ mm}$
- **Level 3**: $244 \times 61$ grid, 29,768 DOFs, $J_3 = -1.907295\text{ mm}$

### Uncertainty Assessment
$$\delta_{\text{ref}} = \frac{|J_3 - J_2|}{|J_3|} = \frac{|-1.907295 - (-1.906130)|}{1.907295} = \mathbf{0.061117\%}$$
- Because $\delta_{\text{ref}} = 0.061\% \ll 1.0\%$ and $\ll 0.5\%$, the Level 3 reference is scientifically adequate for evaluating errors down to $0.5\%$.
- For evaluating $\tau = 0.25\%$, the reference uncertainty ($0.061\%$) accounts for roughly **$24\%$ of the target threshold**, which represents the resolution floor of this numerical reference.

---

## 3. Equal-Accuracy Evaluation Audit (Full Precision)

We extracted the full floating-point precision error data across all iterations (`scratch/benchmark_forensics.py`):

| Target Threshold | Strategy | Iteration | DOFs | Full-Precision Reference Error | Successive Change ($e_{\text{change}}$) | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$\le 2.0\%$** | Uniform | Iter 3 | 2,618 | **$1.196779\%$** | $3.596\%$ | PASS |
| | Recovery | Iter 4 | 1,788 | **$1.229009\%$** | $1.879\%$ | PASS |
| | Goal-Aware | Iter 4 | 1,908 | **$1.371013\%$** | $1.806\%$ | PASS |
| **$\le 1.0\%$** | Uniform | Iter 4 | 10,098 | **$0.233385\%$** | $0.966\%$ | PASS |
| | Recovery | Iter 5 | 3,918 | **$0.535145\%$** | $0.698\%$ | PASS |
| | **Goal-Aware** | **Iter 5** | **4,034** | **$0.630199\%$** | **$0.746\%$** | **PASS ($2.50\times$ fewer DOFs)** |
| **$\le 0.5\%$** | Uniform | Iter 4 | 10,098 | **$0.233385\%$** | $0.966\%$ | PASS |
| | Recovery | Iter 6 | 8,466 | **$0.169275\%$** | $0.366\%$ | PASS |
| | **Goal-Aware** | **Iter 6** | **8,328** | **$0.249743\%$** | **$0.381\%$** | **PASS ($1.21\times$ fewer DOFs)** |
| **$\le 0.25\%$** | Uniform | Iter 4 | 10,098 | **$0.233385\%$** | $0.966\%$ | PASS |
| | Recovery | Iter 6 | 8,466 | **$0.169275\%$** | $0.366\%$ | PASS |
| | **Goal-Aware** | **Iter 6** | **8,328** | **$0.249743\%$** | **$0.381\%$** | **BORDERLINE PASS** |

### Critical Finding on $\le 0.25\%$ Target (Severity: MEDIUM)
- At Iteration 6, Goal-Aware error is **$0.249743\%$**, which is rounded to $0.250\%$ in tabular displays.
- Mathematically, $0.249743\% \le 0.250000\%$ is true, so the automated evaluator flagged it as achieved.
- However, the margin is only $0.000257\%$, which is smaller than the reference solution's discretization uncertainty ($\pm 0.061\%$).
- **Scientific Caveat**: Goal-Aware should be reported as reaching $\le 0.5\%$ with solid confidence, while the $\le 0.25\%$ claim should explicitly note the reference uncertainty margin.

---

## 4. Wall-Clock Timing & Statistical Dispersion Audit

Timing instrumentation was audited via `scratch/timing_audit.py`:
- Discrete stages (assembly, condensation, factorization, backsolve, error estimation, refinement, postprocessing) account for **$97.8\%$** of measured iteration time.
- Across 5 repeated executions, total execution time exhibits typical desktop OS scheduling dispersion:
  - Uniform: Min = $0.173$ s, Median = **$0.245$ s**, Max = $0.256$ s ($\sigma = 0.033$ s)
  - Recovery: Min = $0.217$ s, Median = **$0.305$ s**, Max = $0.332$ s ($\sigma = 0.040$ s)
  - Goal-Aware: Min = $0.274$ s, Median = **$0.310$ s**, Max = $0.344$ s ($\sigma = 0.023$ s)
- **Conclusion**: Single-run speedup claims (e.g. $1.61\times$ vs $1.04\times$) vary within $\pm 15\%$ due to memory allocation and threading jitter. Performance conclusions should emphasize DOF reduction ($2.50\times$) as the primary deterministic metric.

---

## 5. Audit Verdict: Benchmark Forensics
- **Severity**: LOW/MEDIUM (honest dynamic evaluation, but tolerance margin at 0.25% must be qualified).
- **Subsystem Integrity**: **VERIFIED**.
