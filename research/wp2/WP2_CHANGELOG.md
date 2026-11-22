# GDEC Work Package 2 (WP2) Changelog

All notable changes introduced in Work Package 2 (`research/wp2-vv-suite-and-ci-matrix`) are documented here.

---

## [WP2] - 2026-11-23

### Added
- **Reference Problem Library (`src/gdec/verification/reference_problems.py`)**:
  - Defined `ReferenceProblemSpec` dataclass capturing literature citations, governing PDEs, domain, boundary conditions, exact QoI formulas, expected convergence orders, error tolerances, and limitations.
  - Implemented 8 traceable reference problems (`REF-01` through `REF-08`):
    - `REF-01-PATCH-TEST`: Constant strain patch test on distorted mesh (Irons & Razzaque).
    - `REF-02-UNIAXIAL-TENSION`: Uniaxial tension bar with lateral Poisson contraction (Timoshenko & Goodier).
    - `REF-03-TIMOSHENKO-CANTILEVER`: Slender cantilever beam bending with parabolic shear traction (Timoshenko).
    - `REF-04-PURE-BENDING-MANUFACTURED`: Exact manufactured quadratic displacement field (Szabo & Babuska).
    - `REF-05-LAME-CYLINDER`: Thick cylinder quadrant under internal radial pressure (Lame).
    - `REF-06-PLATE-HOLE-KIRSCH`: Stress concentration around circular hole ($K_t \sim 3.0$, Kirsch).
    - `REF-07-L-SHAPED-DOMAIN-SINGULAR`: $3\pi/2$ re-entrant corner singularity rate degradation (Babuska & Rheinboldt).
    - `REF-08-RIGID-BODY-NULLSPACE`: Unconstrained 2D elasticity stiffness nullspace multiplicity (Bathe).
- **Automated Reference Problem Tests (`tests/verification/test_reference_library.py`)**:
  - Implemented numerical solves for all 8 reference problems using vector P1 finite elements (`skfem.ElementVector(skfem.ElementTriP1())`).
  - Implemented exact Delaunay triangulation for distorted patch test, achieving machine precision error ($4.34 \times 10^{-19}$ m).
  - Implemented outward normal dot-product traction boundary integration (`dot(v, w.n)`) for Lame cylinder, achieving $0.18\%$ agreement with exact theory.
- **Convergence Order Verification (`tests/verification/test_convergence_order.py`)**:
  - Implemented `fit_convergence_rate` function for log-log linear regression with $R^2$ goodness-of-fit.
  - Implemented smooth Poisson MMS test verifying $p_{obs} \in [1.85, 2.15]$ for $L^2$ ($p = 1.956$) and $[0.85, 1.15]$ for $H^1$ ($p = 0.983$).
  - Implemented L-shaped domain singular corner test verifying asymptotic rate degradation to $p_{obs} \in [1.20, 1.45]$ ($p = 1.334$), proving the theoretical limitation of uniform refinement on non-smooth solutions.
- **Status Register Generator & Traceability Gate (`src/gdec/verification/status_register.py`, `scripts/generate_status_register.py`)**:
  - Mapped 24 capabilities 1-to-1 with `docs/GDEC_ENGINEERING_STATUS.md`.
  - Machine-readable JSON output at `results/status_register.json` with commit SHA, branch, dirty status, Python and scientific environment versions.
  - Implemented `verify_traceability` raising `TraceabilityVerificationError` if any `NUMERICALLY VERIFIED` capability lacks passing test evidence.
  - Added CLI runner script `scripts/generate_status_register.py --check`.
- **Targeted Mutation Testing (`src/gdec/verification/mutation_harness.py`, `tests/verification/test_mutation_resilience.py`)**:
  - Synthetically injected 6 lethal mathematical mutations into constitutive, kinematic, and adjoint kernels.
  - Automated test suite detects and kills 100% of injected mutants ($6/6$).
- **Cross-Platform CI Matrix (`.github/workflows/ci.yml`)**:
  - Matrix expansion across Linux, Windows, macOS x Python 3.10–3.13 (12 matrix jobs).
  - Added dedicated `status-register-traceability` job.
  - Added dedicated `upstream-dependency-drift` job with weekly cron and manual trigger.
  - Added dedicated `coverage-and-mutation` job.

### Changed
- Total passing tests increased from 401 to 426 (+25 verification tests, 0 failures).
- Updated git environment query in status register to report working tree dirty flag.
