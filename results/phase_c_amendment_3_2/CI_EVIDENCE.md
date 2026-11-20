# GDEC Phase C Amendment 3.2 — Continuous Integration & Verification Evidence

**Repository:** `delythassociates/GDEC`  
**Working Branch:** `phase-c/amendment-3.2`  
**Base Preregistration Tag:** `prereg-c-amendment-3.1` (`1adf18e1156a9956f9024088cdd1882ff60fb120`)  
**Phase A Foundation Commit:** `01260409a0e11d8dcf97729ea25a61f20e2a4772`  
**Python Environment:** Python 3.13.14 (Win64) | Skfem 10.0.2 | SymPy 1.13.3 | NumPy 2.2.3 | SciPy 1.15.2 | Pytest 9.2.0 | Ruff 0.8.2 | Mypy 1.13.0  

---

## 1. Non-Confirmatory Test Suite Execution

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- .venv\Scripts\python.exe
rootdir: F:\fem-edit-benchmark
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collected 218 items

tests/test_a2_adjoint.py .................................... [  2%]
tests/test_a2_determinism.py ...                              [  3%]
tests/test_a2_independent_assembler.py ......                 [  6%]
tests/test_a2_manufactured_solution.py ....                   [  8%]
tests/test_a2_patch_operator.py ...                           [  9%]
tests/test_a2_reference_scale.py ...                          [ 11%]
tests/test_a2_refinement.py ..                                [ 11%]
tests/test_a2_zz_effectivity.py .................             [ 22%]
tests/test_benchmark.py ...                                   [ 23%]
tests/test_cantilever.py ..                                   [ 24%]
tests/test_compiler.py ............                           [ 30%]
tests/test_fem.py ......                                      [ 33%]
tests/test_language.py ........................               [ 44%]
tests/test_mesh.py .                                          [ 44%]
tests/test_mesh_hierarchy.py .....                            [ 46%]
tests/test_phase_c_amendment_1.py ........                    [ 50%]
tests/test_phase_c_amendment_2.py ................            [ 57%]
tests/test_phase_c_amendment_3.py ..........                  [ 62%]
tests/test_phase_c_amendment_3_1.py ................          [ 69%]
tests/test_phase_c_amendment_3_2.py ...........................[ 82%]
tests/test_phase_c_amendment_3_2_reproductions.py ....        [ 84%]
tests/test_phase_c_analyser.py ....................           [ 93%]
tests/test_runtime.py ..                                      [ 94%]
tests/test_v021_corrections.py .......                        [ 97%]
tests/test_v02_adjoint.py .                                   [ 98%]
tests/test_v02_cost_model.py .                                [ 98%]
tests/test_v02_evaluator.py .                                 [ 99%]
tests/test_v02_profiling_and_reuse.py ..                      [100%]
tests/test_v02_reference.py ..                                [100%]
tests/test_v02_scaling.py .                                   [100%]

============================ 218 passed in 53.36s =============================
```

- **Total Non-Confirmatory Tests:** 218
- **Passed:** 218 (100.0%)
- **Failed:** 0
- **Confirmatory Runs Executed:** 0 (Strict freeze maintained)

---

## 2. Static Code Analysis & Type Checking

### A. Ruff Linter
```
Command: ruff check src/gdec/core/analyser.py src/gdec/runtime/mesh_evidence.py verification/phase_c/amendment_3_2/ tests/test_phase_c_amendment_3_2.py tests/test_phase_c_amendment_3_2_reproductions.py
Output: All checks passed!
Status: PASS (0 errors, 0 warnings)
```

### B. Mypy Type Checker
```
Command: mypy src/gdec/core/analyser.py src/gdec/runtime/mesh_evidence.py
Output: Success: no issues found in 2 source files
Status: PASS (0 errors)
```

---

## 3. Scientific Invariant Integrity Verification

### A. Phase A FEM Solver Immutability
```
Command: git diff --stat 01260409a0e11d8dcf97729ea25a61f20e2a4772 -- src/gdec/fem/
Output: (empty)
Status: STRICTLY IMMUTABLE (0 files changed, 0 lines inserted, 0 lines deleted)
```

### B. Git Tag Immutability
- `prereg-thresholds` (`8a5237d`): Unmodified
- `prereg-c` (`02b5f07`): Unmodified
- `prereg-c-amendment-1` (`8c25ff0`): Unmodified
- `prereg-c-amendment-2` (`a13749c`): Unmodified
- `prereg-c-amendment-3` (`4173ab5`): Unmodified
- `prereg-c-amendment-3.1` (`1adf18e`): Unmodified
