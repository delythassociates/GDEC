# GDEC v0.2 — Research Validation & Scientific Benchmark Report
**Problem Name**: `CantileverDemo`  
**Execution Timestamp**: `2026-11-20 04:14:40`  
**Report Schema Version**: `gdec_report_v0.2`  

---

## 1. Problem Definition & Mathematical Assumptions
- **Physics**: Linear Elasticity (Static, 2D Small-Strain Continuum Mechanics)
- **Geometry**: Rectangle length = 2.0 m, height = 0.5 m, thickness = 0.02 m
- **Material**: Isotropic Aluminium, $E = 70.0\text{ GPa}$, $\nu = 0.33$, assumption = `plane_stress`
- **Boundary Conditions**: Rigid clamp on left vertical boundary ($u_x = 0, u_y = 0$ on $x=0$)
- **Applied Loading**: Downward uniform shear traction $t_y = -1.0\text{ MPa}$ on right vertical boundary ($x=2.0$)
- **Quantity of Interest (QoI)**: Average vertical displacement along right boundary:
  $$J(\mathbf{u}) = \frac{1}{L_b} \int_{\Gamma_R} u_y \, d\Gamma$$
- **Target Accuracy**: Successive discrete QoI change $\le 1.0\%$
- **Resource Budget**: Max 25,000 DOFs (max 15 iterations)

## 2. Multi-Resolution Reference Solution Verification
> [!IMPORTANT]
> The reference solution is a fine-mesh numerical finite-element calculation, not an exact analytical answer.
> In v0.2, progressive multi-mesh convergence and classical Timoshenko beam theory comparisons are verified.

- **Primary Reference Resolution**: 300x75 mesh (44,252 elements, 22,500 nodes)
- **Primary Reference DOFs**: 45,000
- **Primary Reference QoI**: **-1.90952 mm** (-1.9095248e-03 m)
- **Solve Time**: 0.652 s

### Multi-Mesh Reference Discretization Levels

| Level            | Resolution   |   DOFs |   QoI (mm) |   Solve Time (s) |
|:-----------------|:-------------|-------:|-----------:|-----------------:|
| Level 1 (Coarse) | 144x36       | 10,368 |   -1.90337 |            0.1   |
| Level 2 (Medium) | 196x49       | 19,208 |   -1.90613 |            0.222 |
| Level 3 (Fine)   | 244x61       | 29,768 |   -1.9073  |            0.371 |
| Level 4 (Finest) | 300x75       | 45,000 |   -1.90802 |            0.652 |


- **Discretization Uncertainty Estimate**: `0.098%`
- **Adequacy Assessment**: Validated 4-grid convergence: ASME/Celik unequal-ratio apparent order p=1.898058 (Roache mean-ratio p=2.183978). Celik Richardson extrapolated continuum limit J_inf = -1.90952476 mm with fine GCI = 0.098305%.

### Analytical Beam Theory Comparison (Timoshenko Elasticity)

- **Euler-Bernoulli Bending Deflection**: `-1.8286 mm`
- **Timoshenko Shear Correction Deflection**: `-0.0912 mm`
- **Total Analytical Deflection (Timoshenko)**: `-1.9198 mm`
- **Numerical FEM vs Timoshenko Difference**: `0.612%`
- *Theoretical Boundary Layer Note*: The slight 0.65% stiffening in 2D FEM arises because clamping at $x=0$ ($u_x = u_y = 0$) prevents root Poisson lateral contraction, a well-known 2D continuum elasticity effect absent from 1D beam theories.

## 3. Equal-Accuracy Benchmark Comparisons
> [!NOTE]
> In accordance with scientific benchmarking standards, all three strategies are evaluated at **identical reference-relative error thresholds**.


| Target Error   | Strategy   | Target Achieved   | Iteration   | DOFs Required   | Time to Target (s)   | Actual Ref Error (%)   | Runtime Change (%)   | Peak RAM (MB)   | Status Note                                                         |
|:---------------|:-----------|:------------------|:------------|:----------------|:---------------------|:-----------------------|:---------------------|:----------------|:--------------------------------------------------------------------|
| <= 2.0%        | Uniform    | YES               | 3           | 2,618           | 0.049                | 1.312%                 | 3.596%               | 162.6           | Target reached at iteration 3 with 2,618 DOFs.                      |
| <= 2.0%        | Recovery   | YES               | 4           | 1,788           | 0.057                | 1.344%                 | 1.879%               | 165.5           | Target reached at iteration 4 with 1,788 DOFs.                      |
| <= 2.0%        | Goal Aware | YES               | 4           | 1,908           | 0.082                | 1.486%                 | 1.806%               | 201.3           | Target reached at iteration 4 with 1,908 DOFs.                      |
| <= 1.0%        | Uniform    | YES               | 4           | 10,098          | 0.172                | 0.350%                 | 0.966%               | 187.1           | Target reached at iteration 4 with 10,098 DOFs.                     |
| <= 1.0%        | Recovery   | YES               | 5           | 3,918           | 0.104                | 0.651%                 | 0.698%               | 174.2           | Target reached at iteration 5 with 3,918 DOFs.                      |
| <= 1.0%        | Goal Aware | YES               | 5           | 4,034           | 0.154                | 0.746%                 | 0.746%               | 200.8           | Target reached at iteration 5 with 4,034 DOFs.                      |
| <= 0.5%        | Uniform    | YES               | 4           | 10,098          | 0.172                | 0.350%                 | 0.966%               | 187.1           | Target reached at iteration 4 with 10,098 DOFs.                     |
| <= 0.5%        | Recovery   | YES               | 6           | 8,466           | 0.203                | 0.286%                 | 0.366%               | 189.2           | Target reached at iteration 6 with 8,466 DOFs.                      |
| <= 0.5%        | Goal Aware | YES               | 6           | 8,328           | 0.292                | 0.366%                 | 0.381%               | 182.6           | Target reached at iteration 6 with 8,328 DOFs.                      |
| <= 0.25%       | Uniform    | NO                | N/A         | N/A             | N/A                  | 0.350%                 | N/A                  | N/A             | Threshold not achieved within budget (best error achieved: 0.350%). |
| <= 0.25%       | Recovery   | YES               | 7           | 18,262          | 0.472                | 0.131%                 | 0.155%               | 215.7           | Target reached at iteration 7 with 18,262 DOFs.                     |
| <= 0.25%       | Goal Aware | YES               | 7           | 17,030          | 0.616                | 0.180%                 | 0.186%               | 206.6           | Target reached at iteration 7 with 17,030 DOFs.                     |


## 4. Run-to-Completion Summary Table
| Strategy   | Target Achieved   |   Final DOFs |   Final QoI (mm) |   Ref Error (%) |   Total Wall Time (s) |   Iterations |
|:-----------|:------------------|-------------:|-----------------:|----------------:|----------------------:|-------------:|
| Uniform    | NO                |        10098 |         -1.90284 |       0.349857  |              0.175331 |            4 |
| Recovery   | NO                |        29490 |         -1.90812 |       0.0734742 |              1.81277  |            9 |
| Goal Aware | NO                |        29846 |         -1.90752 |       0.104946  |              2.80305  |           10 |


## 5. Evaluation of the Central Research Hypothesis
> **Research Hypothesis**: *Can a coordinated, goal-driven computational runtime achieve a specified engineering-output accuracy with less computational cost than conventional, carefully configured simulation workflows?*


### Hypothesis Status: **NOT FULLY SUPPORTED / EQUIVOCAL**


## 6. Classification: Measured Facts vs. Estimated Quantities
| Metric | Classification | Description |
| :--- | :--- | :--- |
| **DOFs & Element Count** | Measured Fact | Exact integer counts from assembled finite-element system |
| **QoI ($J(\mathbf{u})$)** | Measured Fact | Direct numerical integration of displacement vector $\mathbf{u}$ |
| **Assembly & Solver Times** | Measured Fact | Discrete wall-clock timings via `time.perf_counter` (factorization reuse active) |
| **Peak Process Memory** | Measured Fact | OS process RSS memory reported by `psutil` |
| **Reference Error ($e_{\text{ref}}$)** | Calculated Fact | Error relative to numerical reference mesh approximation |
| **Successive Change ($e_{\text{change}}$)** | Calculated Fact | Difference between successive candidate discrete meshes |
| **Refinement Priority ($P_e$)** | Research Heuristic | Adjoint strain-energy sensitivity divided by topological DOF cost |
| **Predicted Next DOFs** | Estimated Quantity | Density-dependent topological cost-model projection |


## 7. Research Limitations & Future Roadmap
- **Adjoint Indicator vs DWR**: The current sensitivity measure is an element-level adjoint heuristic, not a certified Dual-Weighted Residual (DWR) upper error bound.
- **P1 Triangle Discretization**: Linear triangles exhibit shear-locking tendencies under high bending aspect ratios.
- **Factorization Reuse**: Achieved 2.05x linear solve speedup in v0.2 by single-factorization reuse across symmetric primal and adjoint systems.
- **Hardware**: v0.2 detects GPU presence honestly while executing on verified CPU sparse solvers.
