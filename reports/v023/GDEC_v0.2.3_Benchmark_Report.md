# GDEC v0.2.3 — Scientific Benchmark & Verification Report

**Problem**: 2D Elastic Cantilever Beam Deflection (`CantileverDemo`)  
**Geometry**: $L = 2.0\text{ m}, H = 0.5\text{ m}, t = 0.02\text{ m}$  
**Material**: Aluminium ($E = 70.0\text{ GPa}, \nu = 0.33$, Plane Stress)  
**Quantity of Interest**: Tip Average Vertical Displacement $J(\mathbf{u}) = \frac{1}{H} \int_{\Gamma_R} u_y \, d\Gamma$  
**Continuum Reference**: $J_{\infty,\text{Celik}} = -1.909525\text{ mm}$ (GCI = $0.0983\%$)  
**Target Accuracy**: Successive change $\le 1.0\%$ | **Budget**: Max 25,000 DOFs  

---

## 1. Equal-Accuracy Comparison Matrix

Scientific benchmarking requires comparing competing adaptive strategies at **matched reference error thresholds** rather than comparing different accuracies at arbitrary iteration counts.

| Target Error | Strategy | Target Met? | Iteration | DOFs Required | Wall Time (s) | Actual Error (%) | DOF Ratio vs Goal | Time Ratio vs Goal | Peak RAM (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$\le 2.0\%$** | **Uniform** | YES | 3 | 2,618 | 0.080 | 1.312% | 1.28x | 1.03x | 207.5 |
| | **Recovery (ZZ)** | YES | 4 | 1,730 | 0.067 | 1.390% | 0.85x | 0.86x | 206.5 |
| | **Goal-Aware** | YES | 4 | 2,040 | 0.078 | 1.421% | 1.00x | 1.00x | 185.0 |
| **$\le 1.0\%$** | **Uniform** | YES | 4 | 10,098 | 0.187 | 0.350% | 2.34x | 1.35x | 218.3 |
| | **Recovery (ZZ)** | YES | 5 | 3,760 | 0.111 | 0.678% | 0.87x | 0.80x | 213.6 |
| | **Goal-Aware** | YES | 5 | 4,324 | 0.139 | 0.701% | 1.00x | 1.00x | 172.4 |
| **$\le 0.5\%$** | **Uniform** | YES | 4 | 10,098 | 0.187 | 0.350% | 1.12x | 0.69x | 218.3 |
| | **Recovery (ZZ)** | YES | 6 | 7,806 | 0.232 | 0.304% | 0.87x | 0.86x | 223.1 |
| | **Goal-Aware** | YES | 6 | 9,014 | 0.271 | 0.337% | 1.00x | 1.00x | 190.2 |
| **$\le 0.25\%$** | **Uniform** | NO | N/A | N/A | N/A | 0.350% | N/A | N/A | N/A |
| | **Recovery (ZZ)** | NO | N/A | N/A | N/A | 0.304% | N/A | N/A | N/A |
| | **Goal-Aware** | NO | N/A | N/A | N/A | 0.337% | N/A | N/A | N/A |

---

## 2. Run-to-Completion Strategy Summary

| Strategy | Converged? | Final DOFs | Final QoI (mm) | Final Ref Error (%) | Wall Time (s) | Iterations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Uniform** | NO (Budget) | 10,098 | -1.902844 | 0.350% | 0.187 s | 4 |
| **Recovery (ZZ)** | YES | 7,806 | -1.903729 | 0.304% | 0.233 s | 6 |
| **Goal-Aware** | YES | 9,014 | -1.903084 | 0.337% | 0.273 s | 6 |

---

## 3. Rigorous Evaluation of the Central Research Hypothesis

> **Research Hypothesis**: *Can a coordinated, goal-driven computational runtime achieve a specified engineering-output accuracy with less computational cost than conventional, carefully configured simulation workflows?*

### Dimensional Breakdown

| Evaluation Dimension | Metric Evaluated | Empirical Verdict | Rationale & Scientific Evidence |
| :--- | :--- | :--- | :--- |
| **1. DOF Efficiency vs Uniform** | Spatial degree of freedom count at matched error | **SUPPORTED** | Goal-Aware achieves an average **$1.58\times$ DOF reduction** (up to **$2.34\times$ reduction** at $1.0\%$ error threshold). |
| **2. DOF Efficiency vs Recovery** | Spatial degree of freedom count at matched error | **NOT_SUPPORTED** | In this bending-dominated domain, global stress recovery achieves comparable or slightly superior spatial DOF efficiency ($0.87\times$). |
| **3. Runtime Efficiency vs Uniform** | Wall-clock execution time to target error | **PARTIALLY_SUPPORTED** | Goal-Aware is $1.35\times$ faster than Uniform at $1.0\%$ error ($0.139\text{ s}$ vs $0.187\text{ s}$), but slower at $0.5\%$ error due to multi-iteration Python overhead. |
| **4. Runtime Efficiency vs Recovery** | Wall-clock execution time to target error | **NOT_SUPPORTED** | Recovery solves only the primal problem, whereas Goal-Aware solves both primal and adjoint systems at each adaptive iteration. |
| **5. Combined Cost Superiority** | Joint DOF and Wall-Clock Advantage | **PARTIALLY_SUPPORTED** | Spatial DOF efficiency is conclusively demonstrated against Uniform, but wall-clock time superiority is not universally established. |
| **6. Target Attainment** | Reaching required tolerance within budget | **PARTIALLY_SUPPORTED** | Attained $3/4$ standardized error thresholds ($2.0\%, 1.0\%, 0.5\%$). |

### Overall Scientific Conclusion: **PARTIALLY_SUPPORTED**

The research hypothesis is **partially supported**. Spatial degree of freedom efficiency is verified against uniform refinement across all achievable error levels. However, in small 2D finite-element problems ($< 10^4$ DOFs), Python runtime overhead, mesh bisection operations, and the requirement of dual (primal + adjoint) solves prevent a consistent net wall-clock time advantage. Wall-clock superiority is expected to become pronounced in 3D large-scale systems where linear solver costs scale superlinearly ($O(N^{1.5}) - O(N^2)$).
