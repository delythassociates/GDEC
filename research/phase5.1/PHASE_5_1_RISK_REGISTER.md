# GDEC Phase 5.1 Risk & Blocker Register

**Document ID:** `GDEC-RISK-P51-001`
**Date:** 2026-11-22
**Author:** Lead Engineering Research Orchestrator
**Status:** Monitored & Mitigated

---

## 1. Technical Risk Status & Mitigations

| Risk ID | Category | Risk Description | Severity | Probability | Phase 5.1 Status | Mitigation Strategy & Verification Evidence |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **RSK-51-01** | GPU / PCIe | Host-to-Device transfer latency eliminates speedup on single SpMV operations ($N < 100,000$). | High | High | **Verified & Documented** | Kept CPU SuperLU as default for small/medium 2D meshes. Architected `CUDABackend` to support `host_output=False` so data remains GPU-resident across iterative PCG solves. |
| **RSK-51-02** | Packaging | CuPy wheels require matching CUDA runtime DLLs (nvJitLink, cublasLt), risking import crashes. | High | Medium | **Mitigated** | Implemented multi-tiered `detect_cuda_capability()`. If any runtime DLL fails to load, GDEC catches the exception and falls back to `CPUBackend` with an actionable diagnostic. |
| **RSK-51-03** | Scientific / DSE | Misrepresenting asymptotic DWR gradient recovery indicator as a guaranteed upper bound. | Critical | Low | **Enforced Guardrail** | Explicitly labeled field as `dwr_asymptotic_indicator`. Implemented automated REFINE trigger when DWR relative error exceeds quality threshold. Strictly forbidden from merging with physical $\sigma$. |
| **RSK-51-04** | DSE / Math | Engineers apply linear-elastic analytical scaling to nonlinear, multi-material, or stress problems. | High | Medium | **Enforced Guardrail** | Built `ScalingAssumptions` validator in `src/gdec/dse/scaling.py`. Explicitly rejects non-uniform materials, varying Poisson ratios, and non-displacement QoIs. |
| **RSK-51-05** | Regression | Introducing backend interfaces disrupts existing production FEM solvers. | High | Low | **Zero Regression** | `LinearElasticitySolver.solve()` was intentionally left unrefactored as an isolated prototype. All 174 legacy baseline tests pass with zero diff in outputs. |

---

## 2. Blockers & Dependencies Analysis

- **Hardware Testing Blocker:** None. NVIDIA GeForce RTX 3050 Laptop GPU was fully operational and tested directly on the host machine.
- **Dependency Blocker:** None. Pydantic v2 was already installed in `.venv`. Optional GPU wheels (`cupy-cuda12x`, `cuda-toolkit`) installed cleanly.
- **Git / Repository Blocker:** None. Untracked files (`src/gdec/core/analyser.py`, `src/gdec/runtime/`) were preserved intact. PR #1 remains open and draft.
