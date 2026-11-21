# GDEC — Engineering Status & Capability Register

**Document Reference:** `docs/GDEC_ENGINEERING_STATUS.md`  
**Last Updated:** 2026-11-21  
**Repository:** `delythassociates/GDEC`  
**Current Development Branch:** `audit/v0.2.2-deep-review`  
**Pull Request:** PR #1 (https://github.com/delythassociates/GDEC/pull/1)  
**Living Document:** Maintained continuously across engineering cycles.

---

## 1. Status Taxonomy & State Definitions

To prevent scientific overclaiming and preserve engineering integrity, every capability in GDEC is tracked under one of six strictly defined states:

1. **PLANNED**: Documented in architectural roadmaps or specifications; no functional code implemented yet.
2. **IMPLEMENTED**: Code exists in the repository, but has not yet undergone rigorous automated testing or verification.
3. **EXECUTED**: Code runs to completion without unhandled crashes on at least one real problem input.
4. **TESTED**: Functionality covered by automated software unit/integration tests with explicit assertion gates.
5. **NUMERICALLY VERIFIED**: Mathematical correctness independently verified against analytical closed-form solutions, manufactured boundary-value problems, conservation laws, or known asymptotic convergence rates with strict, non-relaxed tolerances.
6. **INDEPENDENTLY VALIDATED**: Results replicated by an independent reviewer, external code baseline, or preregistered protocol.

---

## 2. Feature & Capability Register

### 2.1 Compiler and Language Frontend

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Lark EBNF Lexer & Parser** | **TESTED** | `tests/test_language.py`, `tests/test_compiler_validation.py` | LALR grammar in `grammar.lark`. Duplicate named arguments rejected in AST transformer. |
| **Strict Top-Level Declarations** | **TESTED** | `tests/test_compiler_validation.py` | Only known declarations accepted; unknown statements trigger source-located syntax errors. |
| **Singleton Declaration Enforcement** | **TESTED** | `tests/test_compiler_validation.py` | `physics`, `geometry`, `material`, `objective`, `accuracy`, `budget`, `adaptivity`, `backend` rejected if duplicated. |
| **Positional Arity & Named Args** | **TESTED** | `tests/test_compiler_validation.py` | Positional arguments strictly rejected on functions requiring named parameters (`rectangle`, `isotropic`, `traction`, etc.). |
| **Scalar & Type Validation** | **TESTED** | `tests/test_compiler_validation.py` | Rejects `NaN`, `inf`, float overflow (`1e999`), boolean-as-float, fractional budget DOFs/iterations. |
| **Material Constant Bounds** | **TESTED** | `tests/test_compiler_validation.py`, `tests/test_language.py` | Strictly enforces $E > 0$ and $-1.0 < \nu < 0.5$. |
| **Conflicting Boundary Detection** | **TESTED** | `tests/test_compiler_validation.py` | Rejects traction load on clamped Dirichlet boundary; rejects duplicate fixes on same boundary. |
| **Conflicting Objective Detection** | **TESTED** | `tests/test_compiler_validation.py` | Rejects displacement QoI evaluated on a clamped Dirichlet boundary ($u=0$). |
| **Unsupported QoI Rejection** | **TESTED** | `tests/test_audit_regressions.py`, `tests/test_compiler_validation.py` | `point_displacement` rejected at compile time until point interpolation semantics are implemented. |
| **Hardware Backend Rejections** | **TESTED** | `tests/test_v021_corrections.py`, `tests/test_compiler_validation.py` | Accelerator backends (`cuda`, `hip`, `sycl`, `tpu`) strictly rejected with diagnostic; no silent CPU routing. |
| **Typed ProblemIR Contract** | **TESTED** | `tests/test_ir.py`, `tests/test_compiler_validation.py` | Pydantic v2 model with `@model_validator(mode="after")` enforcing cross-field engineering invariants. |

### 2.2 Numerical Mechanics & FEM Engine

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **2D Linear Elasticity (P1 Triangles)** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 1) | Constant-strain patch test on distorted mesh passes with error $< 10^{-11} \text{ m}$. |
| **Bilinear Stiffness Assembly** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 8, 9) | Symmetric positive-definite; unconstrained nullity exactly 3 with residuals $< 10^{-12}$. |
| **Dirichlet Elimination (Condensation)** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 1, 2, 4) | Correct partition and elimination via `skfem.condense`. |
| **Traction Boundary Assembly** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 3, 5, 6) | Total force balances to machine precision; reaction force on root equals load ($10,000 \text{ N}$). |
| **Global Equilibrium Conservation** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 5) | Linear force balance $< 10^{-9} \text{ N}$; moment balance about origin $< 10^{-8} \text{ N}\cdot\text{m}$. |
| **Analytical Beam Convergence** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 3) | Tip deflection monotonically converges from below; finest mesh ($65\times 33$) within $1.29\%$ of Timoshenko. |
| **Manufactured Pure Bending Solution** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 4) | Exact quadratic bending field with $\nabla\cdot\boldsymbol{\sigma}=\mathbf{0}$ reproduced to $< 10^{-11} \text{ m}$. |
| **Rayleigh-Ritz Energy Monotonicity** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 7) | Strain energy $U_h$ strictly increases monotonically under conforming uniform refinement. |
| **Plane Strain Out-of-Plane Stress** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 10) | $\sigma_{zz} = \nu(\sigma_{xx} + \sigma_{yy})$ accurately included in 3D Von Mises invariant calculation. |
| **Primal-Adjoint Factorization Reuse** | **TESTED** | `tests/test_elasticity.py`, `tests/test_v02_profiling_and_reuse.py` | Single Cholesky/LU factorization shared between primal solve $Ku=f$ and dual solve $Kz=g$. |
| **Nonlinear / 3D / Higher-Order Elements** | **PLANNED** | Roadmap Phase 7 | Not implemented in v0.2.2. CPU 2D P1 triangles only. |

### 2.3 Error Estimation & Adaptivity

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Uniform Refinement** | **TESTED** | `tests/test_mesh.py` | 1-to-4 triangle splitting with boundary preserving tags and exact area conservation. |
| **ZZ Recovery Estimator** | **TESTED** | `tests/test_estimators.py` | Area-weighted nodal averaging of element stresses; energy norm metric. |
| **Goal-Aware Adjoint Heuristic** | **TESTED** | `tests/test_v02_adjoint.py`, `tests/test_estimators.py` | $\eta_e = h_e^2 A_e \|\boldsymbol{\varepsilon}_u : \mathbf{C} : \boldsymbol{\varepsilon}_z\|$. Heuristic indicator (`goal_heuristic_v1`), NOT a certified DWR bound. |
| **Residual Energy-Norm Indicator** | **NUMERICALLY VERIFIED** | `tests/test_estimators.py`, `tests/test_dwr_verification.py` | Ainsworth-Oden residual energy norm indicator based on interior facet traction jumps. |
| **Goal-Oriented DWR Estimator** | **NUMERICALLY VERIFIED** | `tests/test_dwr_verification.py`, `docs/DWR_THEORY_AND_DERIVATION.md`, `docs/DWR_IMPLEMENTATION_REPORT.md`, `docs/GOAL_ORIENTED_ADAPTIVITY_REPORT.md` | Variational DWR with interior facet jumps, Neumann boundary residuals, volume residual support, boundary-agnostic DOF-based trace vanishing, first-principles cubic Hermite bubble integration, orientation invariance, and multi-reference effectivity convergence ($0.51 \to 0.91$). |
| **Cost-Aware Priority Weighting** | **TESTED** | `tests/test_v02_cost_model.py`, `tests/test_estimators.py` | Prioritizes elements by sensitivity per estimated degree of freedom. |
| **Conforming Local Red-Green Refinement**| **TESTED** | `tests/test_mesh.py` | Bisection and conforming closure via `skfem.MeshTri.refined(marked)`. |
| **Guaranteed Certified Error Bounds** | **PLANNED** | Roadmap Phase 7 | Requires analytical evaluation of domain-dependent global trace constants $C_{\text{trace}}$. DWR provides an asymptotic estimate, not a certified upper bound. |

### 2.4 Benchmarking & Research Integrity

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Multi-Strategy Comparison** | **TESTED** | `tests/test_benchmark.py`, `tests/test_audit_regressions.py` | Uniform, recovery, goal-aware, and DWR compared on identical engineering problems. |
| **Decoupled DOF & Time Efficiency** | **TESTED** | `tests/test_audit_regressions.py`, `docs/GOAL_ORIENTED_ADAPTIVITY_REPORT.md` | Separate evaluation: DOF advantage does not imply wall-clock advantage in 2D linear FEM. |
| **High-Resolution Reference Adequacy** | **TESTED** | `tests/test_v02_reference.py`, `tests/test_dwr_verification.py` | Multi-reference verification ($65\times 33$, $129\times 65$, Richardson extrapolation). |
| **Refinement Time Accounting** | **TESTED** | `src/gdec/benchmark/runner.py` | Refinement time included in total execution cost. |
| **Equal-Accuracy Interpolation** | **TESTED** | `tests/test_v02_evaluator.py`, `docs/GOAL_ORIENTED_ADAPTIVITY_REPORT.md` | Interpolates DOFs, wall time, and memory required to achieve target reference accuracy. |

### 2.5 Linear Solvers, Preconditioning & Matrix Diagnostics (Phase 4)

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Stiffness Matrix Diagnostics** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `docs/MATRIX_CONDITIONING_REPORT.md` | Reports dimensions, NNZ, sparsity, $\delta_{\mathrm{sym}}$, $\lambda_{\min}$, $\lambda_{\max}$, $\kappa_2$, null modes, warnings. |
| **Matrix Symmetry Metric $\delta_{\mathrm{sym}}$** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `src/gdec/fem/matrix_diagnostics.py` | Evaluates relative Frobenius defect; verified $\le 5.78 \times 10^{-17}$ across meshes, materials, and distortions. |
| **Rigid-Body Null Mode Detection** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `docs/MATRIX_CONDITIONING_REPORT.md` | Detects exactly 3 zero modes for unconstrained body, 1 mode for roller, 0 for clamped cantilever. |
| **Conditioning Scaling $\mathcal{O}(h^{-2})$** | **NUMERICALLY VERIFIED** | `docs/CONDITIONING_SCALING_STUDY.md` | Scaling verified under quasi-uniform mesh refinement ($\kappa_2 \propto N$) and aspect ratio distortion ($\kappa_2 \propto AR^2$). |
| **Volumetric Locking & Near-Incompressibility** | **NUMERICALLY VERIFIED** | `docs/CONDITIONING_SCALING_STUDY.md` | Contrast verified: plane stress remains bounded ($\kappa_2 \approx 10^5$), plane strain explodes ($\kappa_2 \approx 2.2 \times 10^6$ at $\nu=0.499$). |
| **Direct Sparse Solver (SuperLU via `factorized`)** | **NUMERICALLY VERIFIED** | `docs/SOLVER_RECONNAISSANCE.md`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Identified as SuperLU $P_r A P_c = L U$ (not sparse Cholesky). Reference solver in GDEC production. |
| **Primal-Adjoint Factorization Reuse** | **NUMERICALLY VERIFIED** | `tests/test_v02_profiling_and_reuse.py`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Factorization computed once; reused across primal and adjoint solves, yielding 4.1x–8.7x wall-clock speedup over PCG in 2D. |
| **Conjugate Gradient Solver** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Standard PCG for SPD systems with breakdown detection (non-positive curvature, inner-product underflow) and convergence history. |
| **Jacobi Preconditioner** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Strict diagonal positivity validation ($D_{ii} > 0$), modest 6–10% iteration reduction in 2D elasticity. |
| **Incomplete Cholesky Preconditioner $IC(0)$** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | True symmetric $IC(0)$ sparse factorization with breakdown detection; 4.17x iteration reduction. |
| **Algebraic Multigrid (PyAMG Interface)** | **IMPLEMENTED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Optional wrapper around PyAMG smoothed aggregation; reports availability and provides clear import guidance when absent. |
| **Solver Selection Architecture & Policy** | **TESTED** | `docs/GDEC_SOLVER_SELECTION_DESIGN.md` | Decoupled eligibility analysis, performance prediction, and selection policy. Direct solver retained as production default. |
| **Engineering QoI Tolerance Scaling** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Verified super-convergence of QoI error ($e_{\mathrm{rel},J} \sim 10^{-8}$ at $\text{rtol} = 10^{-2}$). |

---

## 3. Test Suite Summary Statistics

- **Total Unit & Regression Tests:** 157 tests.
- **Passing:** 157 (100%).
- **Failing:** 0.
- **Skipped / XFailed:** 0.
- **Total Test Execution Time:** ~7.4 seconds.
- **Python Compilation (`compileall`):** Clean across all `src/` and `tests/` modules (Python 3.10–3.13).
- **Static Analysis (Ruff):** No syntax errors or import execution issues in compiler/FEM code.

---

## 4. Next Priorities

1. **Phase 4 (Complete — Solver Reliability, Matrix Conditioning & Iterative Solver Research):**
   - Established complete reconnaissance of direct sparse solver: confirmed `scipy.sparse.linalg.factorized` uses SuperLU ($P_r A P_c = L U$), not sparse Cholesky.
   - Built modular `src/gdec/fem/matrix_diagnostics.py`: evaluated $\delta_{\mathrm{sym}} \le 5.78 \times 10^{-17}$, detected rigid-body modes (3 modes for free body, 1 mode for roller, 0 for clamped), and evaluated $\kappa_2(K_{ff})$ via sparse ARPACK `eigsh` and dense exact solvers.
   - Executed conditioning scaling study: validated $\mathcal{O}(h^{-2}) = \mathcal{O}(N)$ scaling under mesh refinement, $\mathcal{O}(AR^2)$ distortion scaling, and near-incompressibility volumetric locking in plane strain ($\kappa_2 \to 2.19 \times 10^6$ at $\nu=0.499$).
   - Implemented isolated Krylov framework in `src/gdec/fem/solvers/iterative.py`: standard CG with breakdown and curvature checks, Jacobi preconditioner, true symmetric $IC(0)$ incomplete Cholesky, and PyAMG interface.
   - Clarified mathematical distinction: documented why `scipy.sparse.linalg.spilu` (ILU) is non-symmetric and invalid for ordinary CG.
   - Established direct-solver performance superiority in 2D linear FEM: single-factorization reuse makes SuperLU 4.1x–8.7x faster than PCG across all tested mesh scales.
   - Discovered super-convergence of engineering QoI vs algebraic tolerance: $\text{rtol} = 10^{-2}$ yields $10^{-8}$ relative QoI accuracy, saving 30–40% of iterations.
   - Designed solver selection architecture in `docs/GDEC_SOLVER_SELECTION_DESIGN.md`, maintaining direct solver as production default and exposing iterative solvers via opt-in interface.
2. **Phase 5:** Benchmark protocol re-registration and reproducibility checks.
