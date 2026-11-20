# GDEC Phase C Amendment 3.1: Adversarial Test Report

**Module:** `tests/test_phase_c_amendment_3_1.py`  
**Test Suite:** 16-Case Adversarial & Integrity Matrix (Section 10)  
**Total Executed:** 16  
**Passed:** 16 (100.0%)  
**Failed:** 0 (0.0%)  
**Status:** ALL TESTS GREEN  

---

## 1. Objective and Scope

This adversarial test suite was designed to probe the verification boundaries of GDEC Phase C. Each test injects specific anomalies, falsified claims, distorted geometries, numerical non-convergences, provenance corruptions, or mutation attempts to confirm that GDEC fails closed deterministically.

---

## 2. Adversarial Test Matrix Results

| Test ID | Adversarial Anomaly | Injected Defect | Expected Behavior | Actual Observed Outcome | Verdict |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **A31-T01** | Fabricated Parent Hashes | Unrelated mesh claiming to be child of coarse mesh | Reject topology & refuse hierarchy | Rejected: element count ratio mismatch and domain non-containment | **PASSED** |
| **A31-T02** | Corrupted Child Node Coordinates | Perturbed vertex $(x+0.05)$ away from true edge midpoint | Reject midpoint provenance check | Rejected: `Child vertex is neither a parent vertex nor edge midpoint` | **PASSED** |
| **A31-T03** | Bare Claim of Nestedness | `nestedness_verified=True` asserted without topological evidence | Validator ignores assertion & checks proof | Refused: `Mesh level lacks independent topological verification evidence` | **PASSED** |
| **A31-T04** | Out-of-Bounds Child Mesh | Child mesh shifted outside $[0, 1]^2$ domain | Reject centroid / node inheritance | Refused: `Child mesh fails node inheritance` | **PASSED** |
| **A31-T05** | Incomplete Refinement Mapping | Partially refined mesh ($N_e$ ratio $\ne 4.0$) | Reject refinement ratio & topology | Refused: `Element count ratio does not match uniform doubling` | **PASSED** |
| **A31-T06** | Supported Non-Nested Method | `independent_conforming` method with resolution doubling | Accept hierarchy; mark nestedness unproven | Accepted: `conforming_hierarchy_verified=True`, `nestedness_proven=False` | **PASSED** |
| **A31-T07** | Unknown Refinement Scheme | Unrecognized method `unknown_adaptive_octree` | Fail closed on unknown method | Refused: `Unsupported or unknown refinement method` | **PASSED** |
| **A31-T08** | Non-Uniform Mesh with Giant Element | Mesh with tiny element ($h=0.1$) and giant element ($h=14.14$) | $h_{\max}$ captures maximum diameter ($14.14$) | Verified: $h_{\max} = 14.1421$, $h_{\text{avg}} < 0.6 h_{\max}$ | **PASSED** |
| **A31-T09** | Area-Average Substituted for $h_{\max}$ | Non-uniform mesh with severe size disparity | Discrepancy between $h_{\max}$ and $h_{\text{avg}}$ flagged | Discrepancy confirmed: $> 40\%$ disparity detected | **PASSED** |
| **A31-T10** | Non-Geometric Quadrature Sensitivities | Growing sensitivities, $\rho \ge 1.0$, or zero denominator | Fail closed; refuse tail bound substitution | Refused: `FAILED_NON_GEOMETRIC` / `INCOMPLETE_ZERO_DENOMINATOR`, `E_tail=None` | **PASSED** |
| **A31-T11** | Non-Finite Quadrature Values | Quadrature evaluations contain NaN or Inf | Reject immediately; refuse evaluation | Refused: `FAILED_NON_FINITE`, `passes_verification=False` | **PASSED** |
| **A31-T12** | Excessive Quadrature Residual Tail | Geometric decay with tail ratio $5.0\% > 1.0\%$ | Fail frozen threshold criterion | Refused: `FAILED_THRESHOLD_EXCEEDED`, `ratio=0.05` | **PASSED** |
| **A31-T13** | Provenance Commit Hash Mismatch | Evidence record references wrong commit SHA | Reject test evidence record | Rejected: Provenance validator detected hash mismatch | **PASSED** |
| **A31-T14** | Test Count Disparity | Evidence record claims 45 tests when log shows 42 | Reject evidence on count mismatch | Rejected: Discrepancy between claimed and actual detected | **PASSED** |
| **A31-T15** | Incomplete BVP Labeled Verified | Corrupted boundary condition trace or body force | Reject claim of complete BVP verification | Rejected: `bvp_and_qoi_fully_verified=False` | **PASSED** |
| **A31-T16** | Mutating Frozen Evidence Object | Attempt to reassign `ev.nestedness_verified = True` | Raise `dataclasses.FrozenInstanceError` | Raised: `FrozenInstanceError` on all attribute modifications | **PASSED** |

---

## 3. Regression Safety

Execution of the existing test suite (`tests/test_phase_c_amendment_3.py` and `tests/test_phase_c_analyser.py`) along with the full non-confirmatory repository suite confirmed 100% pass rates (187 passed, 0 failed), proving zero regressions across all historical contracts.
