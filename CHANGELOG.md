# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] (v0.3.0-alpha)

### Added
- **Foundational Engineering Type System (Phase 5.2):** Strongly typed dimensional algebra, SI unit conversion registry, scalar physical quantities, temperature scale semantics (absolute vs interval), and spatial tensors.
- **Canonical Engineering IR (EIR) Core:** Versioned problem specification format (`0.1.0`) with canonical content hashing (SHA-256).
- **Execution Backend Protocol Layer:** Hardware-agnostic compute abstraction decoupling NumPy/SciPy CPU execution from optional CUDA/CuPy GPU acceleration.
- **CuPy GPU Backend Prototype:** Device-resident sparse matrix-vector multiplication (SpMV), PCG iterative linear solver, and vectorized analytical parameter scaling.
- **Decision Sufficiency Engine (DSE):** Declarative decision contracts, Bayesian expected loss formulation with asymmetric linear loss, and single-QoI decision evaluator. No formal ASME V&V 10/40 conformance claim is made.
- **Analytical Parameter Scaling:** Exact zero-solve Monte Carlo parameter sampling ($E, P$) for linear elasticity with linear/quadratic QoIs.
- **Standard Community Health Files:** `CHANGELOG.md`, `CITATION.cff`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and GitHub issue/PR templates.
- **Merge Plan & Version Policy:** Documentation of research branch integration path and versioning contracts in `docs/VERSION_POLICY.md` and `research/wp0/WP0_MERGE_PLAN.md`.

### Changed
- Reconciled package version to `0.3.0a0` across `pyproject.toml` and `src/gdec/__init__.py`.
- Modernized `README.md` with the reported 371-test suite size, platform setup guidance, current CI scope, quickstart instructions, and relative documentation links.
- Archived legacy audit reports and temporary scratch scripts to `docs/archive/`.
- Removed tracked binary zip files (`GDEC_v0.2.2_PRIVATE_REVIEW.zip`, `materials-simulation-skills-main.zip`) from working tree while preserving commit history.

---

## [0.2.2] - 2026-11-20

### Added
- Matrix diagnostic suite and condition number estimators in `src/gdec/solver/diagnostics.py`.
- Preconditioned Conjugate Gradient (PCG) iterative solver with Jacobi, Incomplete Cholesky, and PyAMG preconditioners.
- Rigorous SPD matrix eligibility contract for iterative solvers.
- Consolidated audit documentation and reproducibility manifests.

### Fixed
- CG indefinite breakdown detection and non-SPD matrix rejection.
- Scale-invariance verification in matrix conditioning diagnostics.
- PyAMG smoother configuration whitelist and structural checks.

---

## [0.2.1] - 2026-11-20

### Added
- Goal-oriented DWR adjoint recovery validation against manufactured benchmarks.
- Refinement cost model calibration and Safe Refinement Transaction Protocol.
- 3-way comparative benchmark suite against high-resolution reference solutions.

### Fixed
- ZZ nodal stress averaging gradient boundary effects.
- Transactional budget bounds preventing DOF ceiling overshoot.

---

## [0.2.0] - 2026-11-19

### Added
- Lark LALR(1) compiler frontend for `.gdc` declarative language.
- Intermediate Representation (IR) specification (`gdec_ir_v0.1`).
- 2D Linear Elasticity FEM solver with P1 triangular elements.
- Initial goal-adaptive refinement loop with Dörfler marking.
- Streamlit interactive engineering studio.
