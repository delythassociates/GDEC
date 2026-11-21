# DSE Adversarial Validation & Test Suite (Phase 5.1.1)

## 1. Adversarial Test Objectives

To verify the fail-closed robustness of the Decision Sufficiency Engine, an extensive suite of adversarial test cases was constructed covering:
1. Missing, partial, and unvalidated evidence records.
2. Cross-domain and cross-model spoofing.
3. Boundary discretisation breaches under small margins.
4. Degenerate and non-finite distribution parameters.
5. Exact risk ties and precision boundaries.
6. Bypass attempt invalidation.

---

## 2. Adversarial Test Catalog (18 Cases)

| Test ID | Adversarial Vector | Expected Result | Verified in Phase 5.1.1 |
| :--- | :--- | :--- | :--- |
| **ADV-DSE-01** | `assessment = None` passed to `SingleQoIEvaluator.evaluate` | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-02** | Empty `assessment.records` when required categories declared | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-03** | Partial categories (e.g. mesh convergence present, material char missing) | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-04** | Record marked `ValidationStatus.UNVALIDATED` | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-05** | Record marked `ValidationStatus.REJECTED` | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-06** | Record marked `ValidationStatus.EXPIRED` | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-07** | Domain reference mismatch (`"cantilever_2d"` vs `"bracket_3d"`) | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-08** | Model reference mismatch (`"linear_elastic_v1"` vs `"nonlinear_v2"`) | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-09** | Missing required assumption attestation | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-10** | DWR error exceeds tolerance with `allow_refine=False` bypass attempt | `REFINE` (bypass ignored) | Yes |
| **ADV-DSE-11** | Near-zero mean QoI ($\mu = 10^{-12}$) with fixed reference scale | Stable relative error | Yes |
| **ADV-DSE-12** | Predictive distribution with $\sigma = 0$ | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-13** | Predictive distribution with $\sigma < 0$ | `ContractValidationError` | Yes |
| **ADV-DSE-14** | Predictive distribution with $\mu = \text{NaN}$ | `ContractValidationError` | Yes |
| **ADV-DSE-15** | Predictive distribution with $\sigma = \text{Inf}$ | `ContractValidationError` | Yes |
| **ADV-DSE-16** | Exact risk tie ($R_{\text{release}} == R_{\text{revise}}$) | `REFINE` | Yes |
| **ADV-DSE-17** | Non-finite DWR error metric ($\eta = \text{NaN}$) | `INSUFFICIENT_EVIDENCE` | Yes |
| **ADV-DSE-18** | Missing reference scale for DWR normalization | Safe fallback / refusal | Yes |

---

## 3. Results Summary

All 18 adversarial scenarios are systematically tested and verified in `tests/test_dse.py` and `tests/test_phase5_1_1_adversarial.py`. Zero unhandled exceptions or spurious `RELEASE` verdicts occurred.
