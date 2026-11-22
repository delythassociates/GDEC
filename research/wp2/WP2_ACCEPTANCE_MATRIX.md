# GDEC Work Package 2 (WP2) Acceptance Matrix
## Verification & Validation Suite as a Product + CI Matrix

**Branch:** `research/wp2-vv-suite-and-ci-matrix`  
**Parent Tip:** `1c55628d64afed670b813b9d04e97a2249235c3c`  
**Verification Date:** 2026-11-23  
**Status:** ALL GATES PASSED (4 / 4)

---

## 1. Acceptance Gates

| Gate | Requirement Description | Target Criteria | Empirical Evidence / Command | Result |
|---|---|---|---|---|
| **Gate 1** | Cross-Platform CI Matrix & Drift Checks | Matrix configured for Linux, Windows, macOS x Python 3.10–3.13; separate drift & register jobs | `.github/workflows/ci.yml` inspection; 12 matrix targets + 3 dedicated audit jobs | **PASS** |
| **Gate 2** | Traceable Reference Problem Suite & Status Register | $\ge 8$ reference problems documented; status register generated; strict traceability enforced | `python scripts/generate_status_register.py --check` -> 24 capabilities, 16 verified, 0 unbacked | **PASS** |
| **Gate 3** | Convergence Order Proof & Mutation Resilience | Smooth MMS order $p \in [1.85, 2.15]$ ($L^2$), $[0.85, 1.15]$ ($H^1$); corner rate degradation; 100% mutation kill rate | `pytest tests/verification/test_convergence_order.py tests/verification/test_mutation_resilience.py` (10 passed) | **PASS** |
| **Gate 4** | Complete Test Suite Integrity & Safe Isolation | All unit/verification tests pass; no regressions; untracked user files preserved | `pytest tests/` -> 426 passed, 0 failed in 11.40s; untracked files preserved | **PASS** |

---

## 2. Gate Verification Evidence

### Gate 1: CI Matrix Configuration
- **File:** `.github/workflows/ci.yml`
- **Jobs Defined:**
  1. `matrix-tests`: `os: [ubuntu-latest, windows-latest, macos-latest]`, `python-version: ["3.10", "3.11", "3.12", "3.13"]`.
  2. `status-register-traceability`: Enforces `python scripts/generate_status_register.py --check`.
  3. `upstream-dependency-drift`: Installs unpinned latest dependencies (`numpy`, `scipy`, `skfem`, `matplotlib`, `pandas`, `pydantic`, `lark`, `sympy`) on weekly cron and PRs.
  4. `coverage-and-mutation`: Measures code coverage with `pytest-cov` and runs mutation resilience harness.

### Gate 2: Status Register & Traceability Enforcement
- **Command:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/generate_status_register.py --check
  ```
- **Output:**
  ```text
  Generating GDEC Status Register -> results/status_register.json
  Generated status register with 24 capabilities.
  Summary:
    NUMERICALLY VERIFIED: 16
    TESTED: 8
    IMPLEMENTED: 0
    PLANNED: 0

  Enforcing strict traceability for NUMERICALLY VERIFIED capabilities...
  [PASS] All NUMERICALLY VERIFIED capabilities are backed by passing tests.
  ```

### Gate 3: Convergence Order & Mutation Testing
- **Command:**
  ```powershell
  .\.venv\Scripts\pytest.exe tests/verification/test_convergence_order.py tests/verification/test_mutation_resilience.py -v
  ```
- **Output:**
  ```text
  tests/verification/test_convergence_order.py::TestMeshConvergenceAndObservedOrder::test_smooth_mms_convergence_l2_and_h1 PASSED
  tests/verification/test_convergence_order.py::TestMeshConvergenceAndObservedOrder::test_reentrant_corner_singularity_rate_degradation PASSED
  tests/verification/test_convergence_order.py::TestMeshConvergenceAndObservedOrder::test_fit_convergence_rate_edge_cases PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_full_mutation_suite_100_percent_kill_rate PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_1_shear_modulus_sign_flip PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_2_poisson_ratio_zeroing PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_3_omit_interior_facet_jumps PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_4_zero_dorfler_fraction PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_5_stiffness_matrix_asymmetry PASSED
  tests/verification/test_mutation_resilience.py::TestMutationResilience::test_mutant_6_invert_adjoint_load_sign PASSED
  ============================== 10 passed in 1.48s ==============================
  ```

### Gate 4: Full Repository Test Suite
- **Command:**
  ```powershell
  .\.venv\Scripts\pytest.exe -v
  ```
- **Output:**
  ```text
  ======================= 426 passed, 1 warning in 11.40s =======================
  ```
- **Untracked File Check:**
  `src/gdec/core/analyser.py` and `src/gdec/runtime/` preserved in working directory without git modification.
