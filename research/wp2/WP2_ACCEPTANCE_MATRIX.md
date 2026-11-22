# GDEC Work Package 2 (WP2) Acceptance Matrix
## Verification & Validation Suite as a Product + CI Matrix (Remediated Follow-up)

**Branch:** `research/wp2-vv-remediation-followup`  
**Starting Commit:** `21c92dd6f4100423e1236210ea1d58d96357ccb4`  
**Original WP2 Baseline:** `dc3cf683db15a51177419aae68fdad357660621d`  
**Parent Tip:** `1c55628d64afed670b813b9d04e97a2249235c3c`  
**Verification Date:** 2026-11-23  
**Status:** ALL GATES PASSED (4 / 4)

---

## 1. Acceptance Gates

| Gate | Requirement Description | Target Criteria | Empirical Evidence / Command | Result |
|---|---|---|---|---|
| **Gate 1** | Cross-Platform CI Matrix & Drift Checks | Matrix configured for Linux, Windows, macOS x Python 3.10–3.13; scale-aware moment equilibrium; valid `scikit-fem` drift check; full history checkout (`fetch-depth: 0`) | `.github/workflows/ci.yml` & `tests/test_fem_mathematical_verification.py` | **PASS** |
| **Gate 2** | Traceable Reference Problem Suite & Status Register | $\ge 8$ reference problems with numerical benchmarks (Kirsch refinement $K_t \to 3.000$, Lamé dual plane stress/strain, L-shaped $\lambda_{\text{obs}} < 1.0$); live status register with `demonstrated_status` derived strictly from test evidence | `pytest tests/verification/test_reference_library.py` (11 passed); `python scripts/generate_status_register.py --check` | **PASS** |
| **Gate 3** | Convergence Order Proof & Production Mutation Resilience | Smooth MMS order $p \in [1.85, 2.15]$ ($L^2$), $[0.85, 1.15]$ ($H^1$); 100% production mutant kill rate (14/14 campaign + 6/6 targeted) | `pytest tests/verification/test_convergence_order.py tests/verification/test_mutation_resilience.py` (10 passed); `python scripts/run_mutation_campaign.py` (14/14 killed) | **PASS** |
| **Gate 4** | Complete Test Suite Integrity & Safe Isolation | All unit/verification tests pass; zero regressions; untracked user files preserved | `pytest tests/` -> 434 passed, 0 failed in 35.67s; `analyser.py` & `src/gdec/runtime/` preserved | **PASS** |

---

## 2. Gate Verification Evidence

### Gate 1: CI Matrix Configuration & Scale-Aware Equilibrium
- `.github/workflows/ci.yml` matrix targets 12 OS/Python combinations + dedicated drift, traceability, and mutation jobs.
- Upstream drift job installs `scikit-fem` (corrected from `skfem`).
- `test_global_force_and_moment_equilibrium`: scale-aware relative tolerance $\frac{|\Delta M|}{M_{scale}} < 10^{-9}$ based on $M_{scale} = 20,000 \text{ N}\cdot\text{m}$.
- Added `fetch-depth: 0` to checkout steps to support deep git commit inspections.
- Verified GitHub Actions CI Workflow Run: [45066710190](https://github.com/delythassociates/GDEC/actions/runs/45066710190) (**15/15 jobs successful — 100% green** across all OS/Python targets, drift check, mutation gate, and status register gate).

### Gate 2: Numerical Reference Problem Suite & Live Status Register
- `REF-06-PLATE-HOLE-KIRSCH`: Graded 3-level refinement series:
  - $K_t^{(0)} = 2.9524 \to K_t^{(1)} = 2.9964 \to K_t^{(2)} = 3.0018$ (relative error $1.59\% \to 0.12\% \to 0.06\%$).
  - Deliberate $+15\%$ traction perturbation causes benchmark failure ($K_t = 3.4521$), confirming test sensitivity.
- `REF-05-LAME-CYLINDER`: Dual formulation independently verified against closed-form radial profiles:
  - Plane stress: $p_{\text{obs}} = 2.002$, fine mesh $L^2$ error $0.0650\%$, max nodal error $0.2328\%$.
  - Plane strain: $p_{\text{obs}} = 2.000$, fine mesh $L^2$ error $0.0794\%$, max nodal error $0.2872\%$.
- `REF-07-L-SHAPED-DOMAIN-SINGULAR`: Full 2D elasticity FEM solve on 4-level mesh hierarchy ($k=1, 2, 3, 4$):
  - Monotonic strain energy convergence: $U_0 = 7.311 \times 10^1 \to U_1 = 9.983 \times 10^1 \to U_2 = 1.132 \times 10^2 \to U_3 = 1.183 \times 10^2$ J.
  - Monotonic increment reduction: $\Delta U_{01} = 26.72 > \Delta U_{12} = 13.41 > \Delta U_{23} = 5.04$ J.
  - Observed singularity convergence exponent: $\lambda_{\text{obs}} \in [0.497, 0.706] < 1.0$.
- Status register generated with live pytest execution:
  - 24 capabilities, 16 NUMERICALLY VERIFIED, 8 TESTED.
  - Evaluates `demonstrated_status` strictly against executed test IDs; rejects dirty tree and stale SHAs.
  - Untracked from git; generated as authoritative CI artifact.

### Gate 3: Convergence Order & Production Mutation Testing
- Smooth Poisson MMS: $p_{obs, L2} = 1.956$ ($R^2 = 0.9998$), $p_{obs, H1} = 0.983$ ($R^2 = 0.9997$).
- Production Mutation Score:
  - Targeted sensitivity suite: 100% ($6/6$ mutants killed on actual production functions).
  - Source-level mutation campaign: 100% ($14/14$ mutants killed across 6 modules).

### Gate 4: Full Repository Test Suite
- Total test count: **434 passed, 0 failed** in 35.67s.
- Untracked user files `src/gdec/core/analyser.py` and `src/gdec/runtime/` preserved untouched.
