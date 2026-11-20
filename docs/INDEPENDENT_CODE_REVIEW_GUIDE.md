# GDEC v0.2.2 Independent Code Review Guide

This guide is designed for an external technical reviewer auditing GDEC v0.2.2. It poses critical review questions across all architectural layers.

---

## 1. Compiler & Language Review

- **Grammar & Lexer (`src/gdec/language/grammar.lark`)**:
  - Is the Lark LALR(1) grammar unambiguous?
  - Are numeric expressions, scientific notation, and negative coordinates parsed without `eval()`?
- **AST Typing (`src/gdec/language/ast.py`)**:
  - Are AST nodes immutable and strongly typed?
  - Is source context (line/column) preserved for diagnostics?
- **Semantic Validation (`src/gdec/language/semantic.py`)**:
  - Does the semantic analyzer reject non-physical inputs (negative Young's modulus, invalid Poisson ratio)?
  - Are unsupported hardware backends (e.g., CUDA) rejected at compile time?
- **Intermediate Representation (`src/gdec/language/ir.py`)**:
  - Is `ProblemIR` genuinely decoupled from solver-specific structures?
  - Does JSON serialization round-trip losslessly?

---

## 2. Numerical Methods & Solver Review

- **Stiffness Assembly (`src/gdec/fem/elasticity.py`)**:
  - Is the plane stress constitutive matrix correctly derived?
  - Is stiffness matrix symmetry preserved numerically ($||K - K^T|| / ||K|| < 10^{-14}$)?
  - Are boundary conditions condensed correctly without disturbing unconstrained equations?
- **Adjoint Dual Formulation (`src/gdec/fem/elasticity.py`)**:
  - Is the discrete dual load $\mathbf{g}$ consistent with the linear displacement functional $J(\mathbf{u})$?
  - Does the adjoint solve $\mathbf{K}^T \mathbf{z} = \mathbf{g}$ accurately compute the sensitivity $\partial J / \partial \mathbf{f}$?

---

## 3. Adaptivity & Error Estimation Review

- **Adjoint Indicator (`src/gdec/fem/estimators.py`)**:
  - Does $\eta_e = h_e^2 A_e |\boldsymbol{\sigma}_e(\mathbf{u}) : \boldsymbol{\epsilon}_e(\mathbf{z})|$ correlate with actual QoI error reduction?
  - Is this formulation properly documented as a heuristic rather than certified DWR?
- **ZZ Recovery (`src/gdec/fem/estimators.py`)**:
  - Is nodal stress averaging correctly implemented using element area weights?
- **Mesh Conformance (`src/gdec/fem/mesh.py`, `adaptivity.py`)**:
  - Does red-green bisection eliminate hanging nodes?
  - Are boundary facet tags preserved across successive refinements?

---

## 4. Runtime Architecture & Cost Model Review

- **Budget Enforcement (`src/gdec/core/runtime.py`)**:
  - Is the Safe Refinement Transaction Protocol robust against severe under-prediction?
  - Does the pre-solve initial check catch infeasible meshes?
- **Cost Model (`src/gdec/core/cost_model.py`)**:
  - Does the empirical DOF prediction exhibit conservative bias?
  - Are candidate mesh DOFs checked before commitment?

---

## 5. Performance & Scientific Claims Review

- **Factorization Reuse (`src/gdec/benchmark/profiling.py`)**:
  - Is linear solve speedup separated from matrix assembly and condensation overhead?
  - Are timing comparisons reported using median wall-clock times?
- **Benchmark Reproduction (`benchmarks/scripts/reproduce_benchmarks.py`)**:
  - Do reproduced results match the historical records in `results/v022/`?
  - Is the continuum Richardson reference ($J_\infty = -1.909525\text{ mm}$) properly justified?
