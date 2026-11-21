# GDEC Phase 5.1.1 — Technical & Numerical Risk Register

| Risk ID | Category | Description | Severity | Likelihood | Mitigation Strategy in Phase 5.1.1 | Residual Risk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-NUM-01** | Linear Algebra | Symmetric indefinite matrix passed to CG without detection | High | Low | Unified structural and spectral screening via ARPACK/dense eigensolve in `spd_check.py`. | Negligible; requires explicit `caller_certified_spd=True` to bypass. |
| **RSK-NUM-02** | Linear Algebra | Preconditioner is not positive definite, leading to CG divergence | High | Low | Enforced `getattr(M, "is_spd", False)` check across all CPU and GPU backends. | Negligible. |
| **RSK-NUM-03** | GPU Runtime | Host CPU LinearOperator passed to CUDA CG causing host-device memory crash | High | Medium | Explicit type and memory residency validation; raises `UnsupportedCapabilityError`. | Zero. |
| **RSK-DSE-01** | Decision Quality | Engineering design released under severe numerical discretisation error | Critical | Low | Removal of `allow_refine` bypass; DWR quality breaches unconditionally force `REFINE`. | Zero. |
| **RSK-DSE-02** | Evidence Integrity | Simulation results from Domain A spoofed to release design in Domain B | Critical | Low | Strict string and metadata matching of `applicable_domain` and `model_reference`. | Zero. |
| **RSK-DSE-03** | Decision Quality | Arbitrary release on exact Bayesian expected loss tie | Medium | Low | Conservative tie-breaking policy: exact risk ties unconditionally recommend `REFINE`. | Zero. |
| **RSK-UQ-01** | Analytical Scaling | Compliance energy scaled linearly ($P/E$) instead of quadratically ($P^2/E$) | High | Low | Explicit `qoi_type` validation in `ScalingAssumptions`; compliance is rejected with error. | Zero. |
| **RSK-UQ-02** | Analytical Scaling | Unattested assumptions applied without engineer provenance | Medium | Low | `attested_by` field is strictly required; empty strings trigger `ScalingAssumptionError`. | Zero. |
| **RSK-PERF-01** | GPU Performance | Launching small iterative solves ($N \le 25,600$) on GPU without realizing CPU is faster | Medium | High | Documented crossover thresholds in benchmark report; CuPy iterative launch overhead disclosed. | Low (operational guidance provided). |
| **RSK-MEM-01** | CUDA VRAM | Large sparse matrix allocation exceeding VRAM capacity (6GB) | Medium | Medium | Catch and map `cp.cuda.memory.OutOfMemoryError` to `DeviceOutOfMemoryError`. | Controlled. |
