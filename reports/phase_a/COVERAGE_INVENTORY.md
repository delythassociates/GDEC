# Phase A Coverage Inventory & Gap Analysis

**Release Baseline**: GDEC v0.2.2 (`789f1f1f8fd43fc1fca65d098ca17bd5714158ea`)  
**Phase**: Stage 0 + Numerical Verification  

---

## 1. Existing Test Suite Inventory

| Test File | Test Functions | Scope & Capabilities Tested |
| :--- | :--- | :--- |
| `tests/test_elasticity.py` | `test_stiffness_matrix_symmetry`, `test_cantilever_solve_and_displacement_direction`, `test_static_reactions_equilibrium`, `test_linear_elastic_patch_test` | Basic stiffness symmetry ($10^{-10}$ tol), cantilever deflection direction, reaction balance, linear patch test on $5\times 3$ mesh. |
| `tests/test_v02_adjoint.py` | `test_adjoint_qoi_and_force_sensitivity` | Adjoint sensitivity against finite difference on cantilever beam. |
| `tests/test_mesh.py` | `test_initial_mesh_creation`, `test_boundary_facet_tagging`, `test_uniform_refinement_preserves_boundaries`, `test_local_refinement` | Initial mesh node counts, boundary facets, red-green refinement. |
| `tests/test_estimators.py` | `test_estimator_indicators` | Basic non-zero checks on Uniform, ZZ, and Goal-Aware indicators. |
| `tests/test_v02_cost_model.py` | `test_topological_cost_model` | Verifies cost model prediction ranges. |
| `tests/test_v02_reference.py` | `test_reference_multi_resolution_convergence`, `test_timoshenko_analytical_comparison` | 3-level convergence and Timoshenko beam deflection calculation. |
| `tests/test_benchmark.py` | `test_benchmark_suite_execution` | End-to-end benchmark suite execution. |

---

## 2. Requirement Coverage & Gap Analysis Map

| Requirement | Existing Test / File | Gap | Planned Verification Action |
| :--- | :--- | :--- | :--- |
| **A2.1a Linear Patch Test** | `test_elasticity.py::test_linear_elastic_patch_test` | Existing patch test uses coarse structured mesh, lacks $\le 10^{-10}$ displacement/stress tolerance on perturbed mesh, only tests plane stress. | Extend with exact A0-1 perturbed mesh ($5\times 5$), test both plane stress and plane strain to $\le 10^{-10}$. |
| **A2.1b Uniform Tension Solve** | *None* | No production `solve()` test against analytical uniform tension fields. | Implement `A2_1b` testing production `solve()` against exact plane-stress and plane-strain fields to $\le 10^{-10}$. |
| **A2.2 Operator Checks** | `test_elasticity.py::test_stiffness_matrix_symmetry`, `test_static_reactions_equilibrium` | Symmetry tested only to $10^{-10}$; eigenvalue spectrum, rigid-body null space (3 zero modes, 4th $\ge 10^{-4}$), and projection residual unverified. | Implement exact A0-4 mesh ($4\times 3$ elements, $5\times 4$ nodes), full eigenvalue spectrum, null-space projection, cantilever residual $\le 10^{-10}$, reactions $\le 10^{-8}$. |
| **A2.3 Independent Reimplementation** | *None* | No independent assembler exists; production relies exclusively on `scikit-fem` element assembly. | Implement pure-NumPy loop assembler with zero `scikit-fem` dependency; compare on 3 meshes (tensor $17\times 9$, perturbed $5\times 5$, cantilever $20\times 5$) to $\le 10^{-10}$. |
| **A2.4 Manufactured Solution** | *None* | No continuous manufactured solution ($u_x = \sin\pi x\sin\pi y, u_y = x(1-x)y(1-y)(1+x+2y)$); convergence rates unverified. | Use SymPy to derive $b = -\nabla\cdot\sigma$ and exact $J_1, J_2$; test $n=8, 16, 32, 64, 128$ on structured & perturbed meshes; verify $L^2$, energy, and QoI rates. |
| **A2.5 Adjoint Verification** | `test_v02_adjoint.py::test_adjoint_qoi_and_force_sensitivity` | Only 1 FD check on cantilever; exact discrete duality identity $J(u_h) - J(w) = z_h^T(f_h - K_h w)$ and $u = -10^4 z$ proportionality unverified. | Implement A2.5a (FD on 10 random DOFs and $E$), A2.5b (exact discrete identity to $10^{-9}$), A2.5c (ref diagnostic), A2.5d (cantilever proportionality to $10^{-10}$). |
| **A2.6 Refinement Verification** | `test_mesh.py::test_local_refinement` | Refinement tested for single step; 8-cycle angle bounds, edge sharing, angle sum $2\pi \pm 10^{-9}$, area conservation $\le 10^{-12} LH$ unverified. | Implement 8-cycle adaptive loop verification for Goal-Aware and ZZ; check angles, aspect ratio, no hanging nodes, angle sum, area conservation. |
| **A2.7 ZZ Effectivity** | *None* | No effectivity index $I_{op} = \|\sigma^* - \sigma_h\|_E / \|\sigma - \sigma_h\|_E$ comparison against manufactured exact stress. | Implement exact-quadrature energy-norm effectivity index; evaluate $0.7 \le I_{op} \le 1.3$ on $n=64, 128$; verify goal indicator regression to $10^{-10}$. |
| **A2.8 Reference & Scale** | `test_v02_reference.py` | 4-level study reproduction, Celik GCI independent check, SI vs dimensionless scale invariance unverified. | Recompute 4-level study; independently calculate Celik GCI ($10^{-6}$ agreement); test SI vs dimensionless formulation ($10^{-9}$ agreement). |
| **A2.9 Determinism** | *None* | No test verifying identical DOF sequences and QoIs through production `GDECRuntime`. | Execute production `GDECRuntime` for Uniform, ZZ, Goal-Aware; verify exact DOF sequences and QoI to $\le 10^{-8}$. |
