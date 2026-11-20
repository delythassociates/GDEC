# GDEC Phase C Amendment 2 — Problem Analyser & Contract Engine Validation

**Primary Module:** `src/gdec/core/analyser.py`  
**Test Suite:** `tests/test_phase_c_analyser.py`, `tests/test_phase_c_amendment_2.py`  

---

## 1. Budget Exhaustion Semantics (AM2-03)

In Amendment 2, accuracy evaluation is separated from computational resource limits:
- **Accuracy Attainment:** If $U_0 \le \text{tolerance}$, the contract evaluates `estimated_target_met = True` and `status = "estimated_target_met"`.
- **Budget Tracking:** If a predefined step/memory budget was reached, `budget_exhausted = True` is recorded as an independent factual property.
- **Non-Contradiction:** Budget exhaustion never overturns an already achieved accuracy target.

### Test Matrix Verification
| Condition | $U_0 \le \text{tolerance}$ | `budget_exhausted` | `estimated_target_met` | `status` |
|:---|:---:|:---:|:---:|:---:|
| 1. Budget exhausted before target attainment | False | True | False | `estimated_target_not_met` |
| 2. Budget exhausted after target attainment | True | True | True | `estimated_target_met` |
| 3. Normal execution with target met | True | False | True | `estimated_target_met` |
| 4. Normal execution with target unmet | False | False | False | `estimated_target_not_met` |
| 5. Valid uncertainty available but target unmet | False | False | False | `estimated_target_not_met` |

---

## 2. Four-Grid Mode Enforcement (AM2-04)

- The `verification_mode` parameter is explicitly exposed: `"three_grid"` (default) or `"four_grid"`.
- For any configuration marked `m3_validation_level: true`, `verification_mode="four_grid"` is mandatory.
- In `"four_grid"` mode:
  - Level $M_3$ ($J_3$) must be supplied; omission immediately refuses with `UNVERIFIED_INSUFFICIENT_LEVELS`.
  - The observed order difference $\Delta p = |p_{012} - p_{123}|$ is evaluated.
  - If $\Delta p > 0.50$ or $d_{12} \cdot d_{23} \le 0$, the contract is strictly refused with `UNVERIFIED_NON_ASYMPTOTIC`.
  - When stability holds ($\Delta p \le 0.50$), the contract is issued with `status = "four_grid_verified_contract_issued"`.

---

## 3. Input Validation Hardening (AM2-05, AM2-07)

1. **Finite Value Checks:** Non-finite values ($\text{NaN}, \pm\infty$) in QoI entries raise `ValueError`.
2. **Tolerance Validation:** Non-positive or non-finite tolerances raise `ValueError`.
3. **Solver Residual:** Negative or non-finite residuals raise `ValueError`. Values exceeding $10^{-10}$ trigger Priority 5 refusal `solver_not_converged`.
4. **Scale Invariance:** Element degenerate area checks evaluate dimensionless relative area $A_e / A_{\text{total}} \le 10^{-14}$, preventing false rejections for small physical models.
5. **Reference Uncertainty Gate:** Evaluates supplied reference uncertainty against the frozen $0.05\%$ gate ($0.0005$), triggering Priority 10 refusal `reference_uncertain` when exceeded.
