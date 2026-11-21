# GDEC Phase 5.1.2 — Risk Register

**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.2-evidence-integrity-closure`  
**Parent Commit:** `17d997874370b90b2b2e4ae441711bf945ce2bec`

---

## Risk Analysis & Mitigation Matrix

| Risk ID | Category | Risk Description | Pre-Mitigation Severity / Likelihood | Remediation / Mitigation Action Taken | Residual Risk | Monitoring Strategy |
|---|---|---|---|---|---|---|
| **RSK-512-01** | Numerical | **Indefinite or Non-SPD Breakdown in CG**: Symmetric indefinite matrices passing diagonal check causing CG divergence or breakdown. | **HIGH / MEDIUM** | Implemented `SPDVerificationStatus`, strict eigenvalue bounds checking ($\lambda_{\min} > 0$), and `caller_certified_spd` contract. | **LOW** | Automated unit tests on indefinite matrices ($A=[[1, 2], [2, 1]]$); runtime failure logging. |
| **RSK-512-02** | Solver Contract | **Zero RHS Solver Instability**: $b = 0$ causing division by zero or ill-defined residual reduction in CG. | **MEDIUM / HIGH** | Added explicit short-circuit: if $\|b\|_2 == 0$, return $x = 0$, $0$ iterations, $0.0$ residual immediately. | **VERY LOW** | Tested on both CPU and CUDA backends in unit test suite. |
| **RSK-512-03** | Architecture | **PCIe Bandwidth Bottleneck in GPU Validation**: Host-device memory round-trips negating GPU speedup during matrix verification. | **HIGH / HIGH** | Implemented `_validate_device_resident_matrix` in CuPy VRAM; structural screening runs entirely in device memory. | **LOW** | Telemetry logs `host_matrix_transfers` and `device_resident_validation`. |
| **RSK-512-04** | Solver Safety | **Invalid Custom Preconditioners on GPU**: Passing CPU `LinearOperator` or non-SPD operators to CuPy solver leading to crashes or silent wrong answers. | **HIGH / MEDIUM** | Hardened `CUDABackend` preconditioner gate: CPU operators raise `UnsupportedCapabilityError`; missing `is_spd=True` raises `NumericalBackendError`. | **LOW** | Adversarial tests reject CPU operators and uncertified GPU operators. |
| **RSK-512-05** | Decision Safety | **Masking Discredited Evidence Records**: A valid high-level category status masking tainted or discredited individual simulation records. | **CRITICAL / MEDIUM** | Implemented record-level auditing: a category fails closed if it contains any `REJECTED` record, regardless of accepted records. | **LOW** | 20 adversarial DSE tests verifying fail-closed behavior across all permutations. |
| **RSK-512-06** | Decision Safety | **Silent Discretisation Quality Bypass**: Evaluating engineering decisions without DWR mesh error bounds when required by contract. | **CRITICAL / LOW** | Made Gate 3 strictly non-omittable: if numerical quality is required and DWR evidence is missing, evaluation fails closed. | **LOW** | Automated tests `test_14_missing_dwr_record_fails_closed` and `test_17_dwr_metric_missing_value_fails_closed`. |
| **RSK-512-07** | Modeling | **Misapplying Linear Elastic Scaling to Compliance or Stress**: Users applying $J(E, P) = (P/P_0)(E_0/E)J_0$ to compliance ($P^2/E$) or von Mises stress. | **HIGH / MEDIUM** | Strict validation of QoI type in `AnalyticalScalingLaw`; negative validation in test suite verifying error refusal. | **LOW** | Independent `scikit-fem` benchmark confirms quadratic compliance law and test assertions enforce QoI check. |
| **RSK-512-08** | Packaging | **Premature Fused Kernel Complexity**: Implementing custom C++/CUDA kernels leading to compilation failures across differing CUDA/MSVC toolchains. | **MEDIUM / HIGH** | Formally investigated and deferred custom C++/CUDA kernel compilation to Phase 5.2; maintained vendor CuPy kernels. | **LOW** | Standardised on CuPy 14.2.0 wheel distribution without raw C++ compiler dependency. |

---

## Residual Risk Summary

All critical and high severity risks identified during the Phase 5.1.1 audit have been mitigated to LOW or VERY LOW. The codebase enforces fail-closed operations at all entry points.
