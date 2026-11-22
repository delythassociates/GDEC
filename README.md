# GDEC — Goal-Driven Engineering Computation (v0.2.2)
## Language, Compiler, Intelligent Runtime and Adaptive FEM Platform

[![Tests](https://img.shields.io/badge/pytest-42%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-informational.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

---

## 1. Project Overview

Traditional finite element simulation workflows require engineers to make manual, tedious decisions: selecting initial mesh densities, choosing element types, guessing localized refinement zones, setting convergence tolerances, and manually validating numerical accuracy.

**GDEC (Goal-Driven Engineering Computation)** inverts this workflow. The engineer declares:
1. The physical problem (`linear_elasticity`)
2. The domain geometry and material parameters (`rectangle`, `isotropic`)
3. The specific engineering Quantity of Interest required (`average_displacement`)
4. The required numerical accuracy threshold (`successive_qoi_change`)
5. The computational resource budget (`max_dofs`)
6. The execution compute device (`backend = cpu`)

The GDEC compiler compiles this declarative specification into a typed intermediate representation (IR). The intelligent runtime then coordinates goal-aware adaptive mesh refinement, monitors resource consumption, enforces transactional budget limits, and terminates computation once the target engineering output is achieved within budget.

---

## 2. System Architecture

```text
GDEC Engineering Language (.gdc)
              |
              v
       Compiler Frontend
              |
              v
      Engineering IR (JSON)
              |
              v
       Intelligent Runtime
              |
       +------+------+
       |             |
       v             v
 Numerical Engine  Execution Planner
       |             |
       +------+------+
              |
              v
       Engineering Results
       + Accuracy Evidence
```

### Component Status: Implemented vs Planned
- **Implemented in v0.2.2**:
  - Lark LALR(1) parser for `.gdc` engineering DSL.
  - Strongly typed AST with full line/column diagnostic tracking.
  - Semantic analyzer enforcing physical constraints ($E>0$, $-1<\nu<0.5$, boundary consistency).
  - Pydantic-based Intermediate Representation (`ProblemIR`, `gdec_ir_v0.1`).
  - 2D Linear Elasticity solver (plane stress and plane strain) using P1 triangular elements.
  - Vectorized sparse matrix assembly with boundary condensation.
  - Primal solve and Adjoint sensitivity solve with LU factorization reuse.
  - Goal Quantity of Interest (QoI) boundary integration.
  - Zienkiewicz-Zhu (ZZ) area-weighted nodal stress recovery error estimator.
  - Adjoint-informed goal sensitivity refinement heuristic (`goal_heuristic_v1`).
  - Dörfler marking and conforming red-green mesh bisection (zero hanging nodes).
  - Refinement cost model and Safe Refinement Transaction Protocol.
  - Command-Line Interface (`gdec`) and Streamlit Engineering Studio.
  - Automated test suite (42 unit and integration tests).
- **Planned for Future Versions**:
  - Native GPU accelerator execution backends (CUDA/HIP/SYCL).
  - Higher-order finite elements (P2 triangles, bilinear/biquadratic quads) and 3D elasticity.
  - Certified Dual-Weighted Residual (DWR) estimators with complete residual flux jump integration.

---

## 3. Installation

GDEC requires Python 3.10+ (tested on Python 3.10 through 3.13 on Windows 10/11).

```powershell
# 1. Clone repository and navigate to root
cd fem-edit-benchmark

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies and editable package
pip install -r requirements.txt
pip install -e .
```

---

## 4. Running GDEC

### A. Run Automated Test Suite
```powershell
pytest -v
# Or run with timing durations:
python scripts/run_tests.py
```

### B. Command-Line Interface (CLI)
```powershell
# Hardware detection & backend status
gdec hardware

# Validate a .gdc engineering source file
gdec validate examples/cantilever.gdc

# Compile source into Intermediate Representation (JSON)
gdec compile examples/cantilever.gdc -o results/cantilever_ir.json

# Execute goal-driven adaptive simulation
gdec run examples/cantilever.gdc --strategy goal_aware

# Run 3-way comparative benchmark against high-resolution reference
gdec benchmark examples/cantilever.gdc --ref-dofs 30000
```

### C. Launch Interactive Engineering Studio
```powershell
streamlit run src/gdec/app.py
```

---

## 5. Current Capabilities & Limitations

### Verified Capabilities
- **DOF Efficiency**: Goal-aware adaptivity achieves $1.0\%$ target QoI accuracy with **$2.50\times$ fewer DOFs** than uniform refinement (4,034 DOFs vs 10,098 DOFs).
- **Guaranteed Budget Safety**: The Safe Refinement Transaction Protocol unconditionally guarantees $\text{final\_dofs} \le \text{max\_dofs}$ in 100% of tested cases.
- **Factorization Reuse**: Reusing primal LU factorizations for the adjoint solve provides a **$1.96\times - 2.00\times$** speedup on isolated linear solves.

### Current Limitations
- **CPU Only**: GDEC v0.2.2 executes on CPU. Physical GPU hardware is detected for informational purposes only; requests for GPU execution are rejected at compile time.
- **2D P1 Elements Only**: Implements 2D linear static elasticity with 3-node triangular elements.
- **Heuristic Estimator**: The goal-aware indicator is an adjoint-informed ranking heuristic, not a mathematically certified DWR error bound.
- **Python Runtime Overhead**: On small coarse meshes (< 5,000 DOFs), element sorting and mesh management in Python moderate net wall-clock speedups.

---

## Language and Architecture Specifications

The language and IR architecture are being formalized separately from the current implementation:

- [Implemented .gdc Language Profile 0.1](docs/specifications/GDEC_LANGUAGE_SPECIFICATION_0.1.md) — describes the parser and semantic behaviour currently implemented.
- [Canonical Engineering IR Draft 0.1](docs/specifications/CANONICAL_ENGINEERING_IR_DRAFT_0.1.md) — proposed semantic architecture; **not yet implemented**.
- [Language and IR Conformance Matrix](docs/specifications/GDEC_LANGUAGE_IR_CONFORMANCE.md) — distinguishes implemented, proposed and missing capabilities.
- [ADR Register](docs/adr/ADR_REGISTER.md) — proposed architecture decisions requiring maintainer ratification.
- [Legacy IR Migration Plan](docs/migration/LEGACY_IR_TO_CANONICAL_IR_MIGRATION.md) — compatibility-first migration that preserves the existing elasticity path.

The existing compiler and solver still use the elasticity-specific `ProblemIR` with schema identifier `gdec_ir_v0.1`. The Phase 5.2 feature branch adds a separate, partial canonical EIR core (`gdec.engineering_problem`, schema `0.1.0`) and foundational engineering types. These additions are not yet wired into the parser, compiler, runtime or solver, and do not constitute the full canonical EIR proposal.

## Phase 5.2 Implementation (feature branch; draft review)

- [Foundational Engineering Type System 0.1](docs/phase-5.2/FOUNDATIONAL_TYPE_SYSTEM_0.1.md) — dimensions, units, scalar quantities, temperature semantics, shapes and frame metadata.
- [Canonical EIR Core 0.1](docs/phase-5.2/CANONICAL_EIR_CORE_0.1.md) — partial versioned engineering-problem model, reference validation and canonical hashing.

The Phase 5.2 code is additive and preserves the legacy `ProblemIR` execution path. It is not merged into `main`; CI and review are required before acceptance.

---

## 6. Documentation Directory
- [architecture.md](file:///f:/fem-edit-benchmark/docs/architecture.md): System architecture and data flow.
- [language_specification.md](file:///f:/fem-edit-benchmark/docs/language_specification.md): `.gdc` grammar and keyword reference.
- [compiler_design.md](file:///f:/fem-edit-benchmark/docs/compiler_design.md): Lexing, AST construction, and semantic validation.
- [intermediate_representation.md](file:///f:/fem-edit-benchmark/docs/intermediate_representation.md): Typed Pydantic IR specification.
- [runtime_architecture.md](file:///f:/fem-edit-benchmark/docs/runtime_architecture.md): Execution planning, telemetry, and transactional safety.
- [numerical_methods.md](file:///f:/fem-edit-benchmark/docs/numerical_methods.md): Elasticity formulation, assembly, adjoint solve, and GCI.
- [adaptive_refinement.md](file:///f:/fem-edit-benchmark/docs/adaptive_refinement.md): ZZ recovery, goal heuristic, and red-green bisection.
- [cost_model.md](file:///f:/fem-edit-benchmark/docs/cost_model.md): Empirical DOF prediction formulation.
- [benchmark_methodology.md](file:///f:/fem-edit-benchmark/docs/benchmark_methodology.md): 3-way comparative benchmark protocol.
- [known_limitations.md](file:///f:/fem-edit-benchmark/docs/known_limitations.md): Current algorithmic and engineering boundaries.
- [INDEPENDENT_CODE_REVIEW_GUIDE.md](file:///f:/fem-edit-benchmark/docs/INDEPENDENT_CODE_REVIEW_GUIDE.md): Technical review checklist for external auditors.
