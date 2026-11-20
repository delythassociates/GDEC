# GDEC Phase C Amendment 3: Test Evidence Reconciliation Report
**Remediates:** AM3-04  
**Target:** Transparent resolution of test count discrepancies across reports; rigorous execution logging and machine-readable evidence record.  
**Machine-Readable Record:** `results/phase_c_amendment_3/test_evidence_record.json`  
**Execution Command:** `.venv\Scripts\python.exe -m pytest tests -v --durations=10 -m "not confirmatory"`  

---

## 1. Executive Summary and Discrepancy Investigation

During the independent source review of Phase C Amendment 2, an apparent discrepancy was identified in the reported test counts across deliverables:

| Document / Artifact | Reported Result | Context & Timing |
| :--- | :--- | :--- |
| **Amendment 2 Draft Report** | 157 passed, 49.3s | Written during mid-amendment drafting prior to committing `test_phase_c_amendment_2.py` (7 tests). |
| **Amendment 2 CI Evidence Draft** | 157 passed | Captured during intermediate stage when 157 tests were collected. |
| **Amendment 2 Baseline Execution** | 161 passed, 54.73s | Executed on commit `a13749c3ae441dd9ed4c1bed8893d8ce5c86bb82` (`prereg-c-amendment-2`). |
| **Amendment 3 Final Execution** | **171 passed, 42.32s** | Executed on `phase-c/amendment-3` (+10 tests in `test_phase_c_amendment_3.py`). |

### 1.1 Root Cause Analysis
The historical discrepancy arose from progressive additions to the test suite during the execution of Amendment 2:
1. **Pre-Amendment 2 baseline:** The Phase C preflight suite contained 154 collected non-confirmatory tests.
2. **Intermediate drafting run:** During the implementation of AM2-01 body force corrections, 3 tests were added/refined in existing files, yielding 157 passed tests. The early draft of `FINAL_AMENDMENT_REPORT.md` was drafted with this interim snapshot.
3. **Final Amendment 2 integration:** The file `tests/test_phase_c_amendment_2.py` was finalized, introducing 7 comprehensive tests (AM2-01 through AM2-07), while 3 redundant exploratory tests were consolidated. The net collected test count for commit `a13749c3` was exactly **161 items**.
4. **Amendment 3 addition:** The file `tests/test_phase_c_amendment_3.py` added 10 unit and adversarial tests covering AM3-01 through AM3-03, bringing the total suite to **171 collected and passed tests**.

---

## 2. Authoritative Execution Evidence (Amendment 3)

### 2.1 Environment Specification
- **Operating System:** Microsoft Windows 11 (win32)
- **Python Version:** 3.13.14
- **Pytest Version:** 9.2.0
- **Pluggy Version:** 1.7.0
- **Virtual Environment:** `F:\fem-edit-benchmark\.venv`
- **Key Dependencies:**
  - `numpy`: 2.2.3
  - `scipy`: 1.15.2
  - `scikit-fem`: 10.0.2
  - `sympy`: 1.13.3
  - `lark`: 1.2.2

### 2.2 Execution Log Summary
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- F:\fem-edit-benchmark\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: F:\fem-edit-benchmark
configfile: pyproject.toml
plugins: anyio-4.16.0
collecting ... collected 171 items

tests/test_a2_adjoint.py .....                                           [  2%]
tests/test_a2_determinism.py ...                                         [  4%]
tests/test_a2_independent_assembler.py ......                            [  8%]
tests/test_a2_manufactured_solution.py ....                              [ 10%]
tests/test_a2_patch_operator.py ...                                      [ 12%]
tests/test_a2_reference_scale.py ...                                     [ 14%]
tests/test_a2_refinement.py ..                                           [ 15%]
tests/test_a2_zz_effectivity.py .......................                  [ 28%]
tests/test_benchmark.py .                                                [ 29%]
tests/test_cli.py ....                                                   [ 31%]
tests/test_compiler.py ...                                               [ 33%]
tests/test_dwr_consistency.py ........                                   [ 38%]
tests/test_dwr_mutations.py ...                                          [ 39%]
tests/test_elasticity.py ....                                            [ 42%]
tests/test_estimators.py .                                               [ 42%]
tests/test_ir.py .                                                       [ 43%]
tests/test_language.py .......                                           [ 47%]
tests/test_mesh.py ....                                                  [ 49%]
tests/test_mms_symbolic.py .                                             [ 50%]
tests/test_perturbed_mesh_regression.py .......                          [ 54%]
tests/test_phase_b1_1_accounting.py ...                                  [ 56%]
tests/test_phase_b1_timing.py ....                                       [ 58%]
tests/test_phase_b_geometries.py ............                            [ 65%]
tests/test_phase_c_amendment_2.py .......                                [ 69%]
tests/test_phase_c_amendment_3.py ..........                             [ 75%]
tests/test_phase_c_analyser.py .........................                 [ 90%]
tests/test_runtime.py ..                                                 [ 91%]
tests/test_v021_corrections.py .......                                   [ 95%]
tests/test_v02_adjoint.py .                                              [ 95%]
tests/test_v02_cost_model.py .                                           [ 96%]
tests/test_v02_evaluator.py .                                            [ 97%]
tests/test_v02_profiling_and_reuse.py ..                                 [ 98%]
tests/test_v02_reference.py ..                                           [ 99%]
tests/test_v02_scaling.py .                                              [100%]

============================ 171 passed in 42.32s =============================
```

### 2.3 Slowest 10 Durations
1. `tests/test_a2_refinement.py::test_a2_6_adaptive_refinement[recovery]`: 7.54s
2. `tests/test_a2_refinement.py::test_a2_6_adaptive_refinement[goal_aware]`: 6.43s
3. `tests/test_a2_manufactured_solution.py::test_a2_4_manufactured_solution_convergence[plane_strain-structured]`: 2.30s
4. `tests/test_a2_manufactured_solution.py::test_a2_4_manufactured_solution_convergence[plane_stress-perturbed]`: 2.03s
5. `tests/test_a2_manufactured_solution.py::test_a2_4_manufactured_solution_convergence[plane_strain-perturbed]`: 1.95s
6. `tests/test_a2_manufactured_solution.py::test_a2_4_manufactured_solution_convergence[plane_stress-structured]`: 1.88s
7. `tests/test_phase_c_amendment_3.py::test_dynamic_m3_quadrature_convergence_am3_01`: 1.74s
8. `tests/test_a2_determinism.py::test_a2_9_runtime_determinism[uniform]`: 1.67s
9. `tests/test_a2_zz_effectivity.py::test_a2_7_zz_effectivity_evaluation[128-plane_strain-perturbed]`: 1.45s
10. `tests/test_a2_zz_effectivity.py::test_a2_7_zz_effectivity_evaluation[128-plane_stress-perturbed]`: 1.44s

---

## 3. Exclusion of Confirmatory Experiments

The marker `-m "not confirmatory"` strictly excludes:
- Tier 1 40-configuration confirmatory runs (`@pytest.mark.confirmatory`).
- Tier 2 singular benchmark confirmatory runs.
- Tier 3 full refusal confirmatory sweeps.

Confirmatory execution is strictly held in freeze pending independent scientific review and audit approval.

---

## 4. Reconciliation Status & Resolution

1. The interim draft figure of 157 passed is explicitly superseded by this report.
2. The authoritative baseline count for commit `a13749c3` is confirmed at **161 passed in 54.73s**.
3. The authoritative Amendment 3 count is confirmed at **171 passed in 42.32s**.
4. Both counts are traceable to actual stdout logs, git commit hashes, and machine-readable JSON records.
5. Finding **AM3-04** is declared **RESOLVED**.
