# GDEC — Engineering Status & Capability Register

**Document Reference:** `docs/GDEC_ENGINEERING_STATUS.md`  
**Last Updated:** 2026-11-22  
**Repository:** `delythassociates/GDEC`  
**Reference Baseline:** `research/phase-5.2.1b-expression-input-integrity` (`7cd9738`)\n**WP0 Repository-Integrity Overlay:** `research/wp0-repo-integrity`  
**Historical Pull Request:** PR #1 (v0.2.2 audit/remediation); this status register is a capability snapshot, not a live branch pointer.  
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
| **Bilinear Stiffness Assembly** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 8, 9) | Unconstrained global assembled matrix is positive-semidefinite with exactly 3 rigid-body null modes; becomes strictly SPD after applying Dirichlet constraints eliminating rigid-body motion. |
| **Dirichlet Elimination (Condensation)** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 1, 2, 4) | Correct partition and elimination via `skfem.condense`. |
| **Traction Boundary Assembly** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 3, 5, 6) | Total force balances to machine precision; reaction force on root equals load ($10,000 \text{ N}$). |
| **Global Equilibrium Conservation** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 5) | Linear force balance $< 10^{-9} \text{ N}$; moment balance about origin $< 10^{-8} \text{ N}\cdot\text{m}$. |
| **Analytical Beam Convergence** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 3) | Tip deflection monotonically converges from below; finest mesh ($65\times 33$) within $1.29\%$ of Timoshenko. |
| **Manufactured Pure Bending Solution** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 4) | Exact quadratic bending field with $\nabla\cdot\boldsymbol{\sigma}=\mathbf{0}$ reproduced to $< 10^{-11} \text{ m}$. |
| **Rayleigh-Ritz Energy Monotonicity** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 7) | Strain energy $U_h$ strictly increases monotonically under conforming uniform refinement. |
| **Plane Strain Out-of-Plane Stress** | **NUMERICALLY VERIFIED** | `tests/test_fem_mathematical_verification.py` (Test 10) | $\sigma_{zz} = \nu(\sigma_{xx} + \sigma_{yy})$ accurately included in 3D Von Mises invariant calculation. |
| **Primal-Adjoint Factorization Reuse** | **TESTED** | `tests/test_elasticity.py`, `tests/test_v02_profiling_and_reuse.py` | Single SuperLU sparse LU factorization shared between primal solve $Ku=f$ and dual solve $Kz=g$. |
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

### 2.5 Linear Solvers, Preconditioning & Matrix Diagnostics (Phase 4 & Phase 4.1.2 Hardening)

| Capability / Subsystem | Current State | Verification Evidence / Reference | Notes & Limitations |
| :--- | :--- | :--- | :--- |
| **Stiffness Matrix Diagnostics** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `docs/MATRIX_CONDITIONING_REPORT.md` | Reports dimensions, NNZ, sparsity, $\delta_{\mathrm{sym}}$, $\lambda_{\min}$, $\lambda_{\max}$, $\kappa_2$, scale-invariant null modes, warnings. Algebraic smallest eigenvalue via `which="SA"` in sparse ARPACK. Strict scale invariance across $10^{-14} \le c \le 10^{14}$. |
| **Matrix Symmetry Metric $\delta_{\mathrm{sym}}$** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `src/gdec/fem/matrix_diagnostics.py` | Strictly scale-invariant relative Frobenius defect $\|K - K^T\|_F / \|K\|_F$ without denominator floor; exact zero matrix returns 0.0. Nonsymmetric matrices bypass symmetric eigensolvers. |
| **Rigid-Body Null Mode Multiplicity** | **NUMERICALLY VERIFIED** | `tests/test_matrix_diagnostics.py`, `docs/MATRIX_CONDITIONING_REPORT.md` | Accurately detects null modes in requested spectrum (`null_modes_detected`), exact nullity in dense mode (`exact_nullity`), and distinguishes near-singular from indefinite matrices. |
| **Conditioning Scaling $\mathcal{O}(h^{-2})$ & Aspect Ratio** | **NUMERICALLY VERIFIED** | `docs/CONDITIONING_SCALING_STUDY.md` | Scaling verified under quasi-uniform mesh refinement ($\kappa_2 \propto N$) and 5-point aspect ratio sweep ($\kappa_2 \approx 2090 AR^{2.95}$, combining element angle collapse and $EI/L^3$ flexural stiffness scaling; descriptive fit, not universal asymptotic law). |
| **Volumetric Locking & Near-Incompressibility** | **NUMERICALLY VERIFIED** | `docs/CONDITIONING_SCALING_STUDY.md` | Contrast verified: plane stress remains bounded ($\kappa_2 \approx 10^5$), plane strain explodes ($\kappa_2 \approx 2.2 \times 10^6$ at $\nu=0.499$). |
| **Direct Sparse Solver (SuperLU via `factorized`)** | **NUMERICALLY VERIFIED** | `docs/SOLVER_RECONNAISSANCE.md`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Identified as SuperLU $P_r A P_c = L U$ (not sparse Cholesky). Reference solver in GDEC production. |
| **Primal-Adjoint Factorization Reuse** | **NUMERICALLY VERIFIED** | `tests/test_v02_profiling_and_reuse.py`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Factorization computed once; reused across primal and adjoint solves, yielding 4.1x–10.3x wall-clock speedup over PCG across the measured 2D dataset. |
| **Conjugate Gradient Solver & Compatibility Gates** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Enforces default `caller_certified_spd=False`, scale-aware near-null rejection ($\lambda_{\min} \le \tau_{\text{null}} \lambda_{\text{scale}}$), fail-closed preconditioner `is_spd` gate, runtime non-positive curvature checks, and `SolverConvergenceError` contract. |
| **Jacobi Preconditioner** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Strict diagonal positivity validation ($D_{ii} > 0$), modest 6–10% iteration reduction in 2D elasticity; verified SPD (`is_spd=True`). |
| **Incomplete Cholesky Preconditioner $IC(0)$** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | True symmetric $IC(0)$ sparse factorization with breakdown detection; 4.17x iteration reduction; verified SPD (`is_spd=True`). |
| **Algebraic Multigrid (PyAMG Interface)** | **IMPLEMENTED** | `tests/test_iterative_solvers.py`, `src/gdec/fem/solvers/iterative.py` | Verified configuration check: supported symmetric V/W cycles and symmetric smoothers declare `is_spd=True`; unsymmetric configurations declare `is_spd=False` and are rejected for CG. |
| **Solver Selection Architecture & Policy** | **TESTED** | `docs/GDEC_SOLVER_SELECTION_DESIGN.md` | Decoupled eligibility analysis, calibrated performance prediction, and selection policy. Direct solver retained as production default. |
| **Engineering QoI Error Bounds & Scaling** | **NUMERICALLY VERIFIED** | `tests/test_iterative_solvers.py`, `docs/SOLVER_PERFORMANCE_BENCHMARK.md` | Verified Cauchy-Schwarz bounds and functional/load-dependent convergence of QoI error (rapid decay under cantilever bending; linear decay under axial loads). |

---

## 3. Test Suite Summary Statistics

- **Total Unit & Regression Tests:** 174 tests.
- **Passing:** 174 (100%).
- **Failing:** 0.
- **Skipped / XFailed:** 0.
- **Total Test Execution Time:** ~7.4 seconds.
- **Python Compilation (`compileall`):** Clean across all `src/` and `tests/` modules (Python 3.10–3.13).
- **Static Analysis (Ruff):** No syntax errors or import execution issues in compiler/FEM code.

---

## 4. Next Priorities

1. **Phase 4 (Closed & Hardened — Solver Reliability, Matrix Conditioning & Iterative Solver Research):**
   - Reconnaissance: confirmed `scipy.sparse.linalg.factorized` uses SuperLU ($P_r A P_c = L U$), not sparse Cholesky.
   - Matrix Diagnostics: scale-invariant relative symmetry defect $\|K - K^T\|_F / \|K\|_F$; ARPACK `which="SA"` for algebraic smallest eigenvalues; scale-aware null mode detection ($\lambda_{\min} \le \tau_{\text{null}} \lambda_{\text{scale}}$); bypass of symmetric eigensolvers for nonsymmetric operators.
   - Conditioning Study: validated $\mathcal{O}(h^{-2}) = \mathcal{O}(N)$ refinement scaling; 5-point aspect ratio empirical fit ($\kappa_2 \approx 2090 AR^{2.95}$, combining element distortion and cantilever flexural stiffness $EI/L^3$ scaling); near-incompressibility volumetric locking in plane strain ($\kappa_2 \to 2.19 \times 10^6$ at $\nu=0.499$).
   - Iterative Solvers: Conjugate Gradient with fail-safe default `caller_certified_spd=False`; scale-aware near-null rejection; fail-closed preconditioner `is_spd` contract; verified symmetric AMG configuration gates; `SolverConvergenceError` on non-convergence.
   - Solver Benchmarks: direct SuperLU sparse solver with single-factorization reuse is $4.1\times$ to $10.3\times$ faster than Jacobi-PCG across the measured 2D dataset ($N \in [56, 9120]$).
   - QoI Accuracy: established Cauchy-Schwarz and energy-norm bounds; demonstrated that rapid QoI error decay is functional- and load-dependent (bending vs axial).
   - Selection Architecture: user-controlled linear solver tolerance policy; direct solver maintained as production default; iterative solvers available via explicit opt-in.
2. **Phase 5:** Benchmark protocol re-registration and reproducibility checks.
