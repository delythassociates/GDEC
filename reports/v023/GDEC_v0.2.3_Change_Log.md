# GDEC v0.2.3 — Change Log

**Release Version**: v0.2.3  
**Release Date**: November 2026  
**Type**: Scientific Correctness, Numerical Integration, and Reproducibility Remediation Release  

---

## Summary of Changes

### Added
- **Point Displacement Objective**:
  - Compiler, AST, and IR support for `point_displacement(x=..., y=..., component=...)`.
  - Discrete adjoint load vector assembly via P1 triangular shape function interpolation in `LinearElasticitySolver.assemble_point_qoi_adjoint_vector`.
  - Machine-precision duality verification test ($g^T u = z^T f$).
- **Degree-2 Numerical Quadrature**:
  - Exact 3-point Dunavant/Hammer midpoint quadrature on triangles for Zienkiewicz-Zhu stress recovery energy norm calculation in `RefinementEstimator`.
- **Unequal-Ratio Richardson Extrapolation (ASME 2008 Celik Standard)**:
  - 4-level structured grid convergence sequence ($144\times 36$, $196\times 49$, $244\times 61$, $300\times 75$).
  - Brent's method solver for apparent order of convergence $p$.
  - Grid Convergence Index ($\text{GCI}_{21}$) calculation with safety factor $F_s = 1.25$.
- **Topological Refinement Cost Model**:
  - `RefinementEstimator.estimate_element_refinement_costs(gdec_mesh)` using element boundary facet counts and aspect ratios.
- **Multidimensional Hypothesis Evaluator**:
  - `HypothesisEvaluationResult` and `EqualAccuracyEvaluator.evaluate_hypothesis_rigorous()` separating spatial DOF efficiency from wall-clock runtime efficiency.
- **Automated Continuous Integration**:
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`) matrix testing Python 3.10 through 3.13 on Windows and Ubuntu.
- **Unit & Integration Test Suite**:
  - Added `tests/test_v023_remediation.py` with 12 new comprehensive tests, expanding the automated test suite to 54 tests.

### Fixed & Remediated
- **Compiler & Semantic Analyzer Hardening**:
  - Enforced detection of duplicate named arguments in grammar parser (`GDECParseError`).
  - Added strict rejection of unrecognized top-level declarations (`GDECSemanticError`).
  - Enforced rejection of duplicate single-declaration blocks (`material`, `geometry`, `physics`, `objective`, `budget`, `accuracy`).
  - Rejection of NaN and $\pm\infty$ on all numeric parameters.
  - Rejection of non-physical material properties ($E \le 0$, $\nu \notin (-1, 0.5)$) and negative geometry dimensions.
  - Rejection of out-of-bounds coordinates for point displacement objectives.
  - Rejection of non-CPU backends (`cuda`, `hip`, `sycl`) with informative architectural guidance.
- **Telemetry & Performance Profiling**:
  - Fixed `total_iteration_time_sec` calculation to include mesh bisection time.
  - Added discrete fields `initial_mesh_time_sec`, `marking_time_sec`, and `validation_time_sec`.
  - Fixed cost model element count update in runtime controller.
  - Added host RAM availability check before refinement ($< 30\text{ MB}$ guard).
- **Benchmark Reference Assertions**:
  - Added FEM solve comparison against Timoshenko analytical beam theory deflection in `tests/test_v02_reference.py`.
- **License & Metadata**:
  - Updated `LICENSE` to the full standard MIT license.
  - Unified package version `0.2.3` across `pyproject.toml`, `src/gdec/__init__.py`, and CLI banners.

### Changed
- Preserved historical benchmark results and reports under `results/v022/` and `reports/v022/`.
- Written all new benchmark artifacts and reports to `results/v023/` and `reports/v023/`.
