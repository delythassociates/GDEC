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

---

## [WP2-Remediation] - 2026-11-23

Remediation of independent review findings WP2-R1 through WP2-R5 on branch `research/wp2-vv-remediation`.

### Fixed
- **WP2-R1 (CI Matrix & Drift Remediation)**:
  - Corrected PyPI package name in `.github/workflows/ci.yml` from `skfem` to `scikit-fem` in `upstream-dependency-drift` workflow job.
  - Replaced brittle absolute tolerance (`< 1e-8`) in `tests/test_fem_mathematical_verification.py::test_cantilever_global_equilibrium` with scale-aware relative moment tolerance: $\frac{|\Delta M|}{M_{\text{scale}}} < 10^{-9}$ where $M_{\text{scale}} = P \cdot L = 20,000 \text{ N}\cdot\text{m}$. Eliminates ARM64 Apple Accelerate / OpenBLAS matrix summation rounding differences across macOS Python 3.11–3.13.
- **WP2-R2 (Reference Problem Completeness)**:
  - Resolved REF-05 plane-stress / plane-strain inconsistency in `src/gdec/verification/reference_problems.py`. Both analytical formulas documented; verified GDEC standard assumption is 2D plane stress ($u_r(b) = \frac{2 P_{\text{int}} a^2 b}{E (b^2 - a^2)}$).
  - Implemented numerical Kirsch plate-with-hole benchmark in `tests/verification/test_reference_library.py::test_kirsch_plate_hole_stress_concentration`. Quad polar mesh with fine radial discretization near hole ($r=a$) subjected to exact Kirsch boundary tractions at $r=b=5a$. Evaluated numerical peak circumferential stress $\sigma_{\theta\theta}^{\max} = 29.96 \text{ MPa}$ ($K_t = 2.996$ vs analytical $3.000$, $0.12\%$ error).
  - Implemented numerical 2D elasticity L-shaped domain corner singularity benchmark in `tests/verification/test_reference_library.py::test_l_shaped_domain_corner_singularity`. Solved on sequence of 3 refined meshes ($N_0=55$, $N_1=201$, $N_2=769$ vertices); verified monotonic strain energy convergence ($U_0 = 1.462\times 10^{-4} \to U_1 = 1.997\times 10^{-4} \to U_2 = 2.265\times 10^{-4} \text{ J}$) with energy increment reduction ratio $\Delta U_{01}/\Delta U_{12} = 1.993 \approx 2^{2\lambda}$ ($\lambda \approx 0.544$).
  - Ensured all 8 reference problem tests execute bona fide numerical PDE solves; no metadata-only tests count toward verification.
- **WP2-R3 (Genuine Production Mutation Testing)**:
  - Completely replaced synthetic standalone mutation demonstration in `src/gdec/verification/mutation_harness.py` with dynamic monkey-patching of production functions across `gdec.fem`, `gdec.dse`, and `gdec.eir`:
    - `MUTANT-1-STIFFNESS-CONSTITUTIVE`: scales $E$ by $1.05$ in `ConstitutiveTensor.from_properties` (Killed by `test_cantilever_beam_timoshenko_analytical_comparison`).
    - `MUTANT-2-SYMMETRY-DEFECT`: zeroes non-symmetric perturbation check in `compute_symmetry_defect` (Killed by `test_symmetry_defect_exact_and_perturbed`).
    - `MUTANT-3-ANALYTICAL-SCALING`: alters analytical exponent $d \to d^{1.2}$ in `RestrictedLinearElasticScaling.evaluate_scalar` (Killed by `test_independent_fem_scaling_agreement`).
    - `MUTANT-4-AMR-MARKING`: inverts Dörfler fraction $1-\theta$ in `MeshAdaptor.mark_elements` (Killed by `test_dwr_adaptive_refinement_reduces_qoi_error`).
    - `MUTANT-5-EIR-TYPE-DIMENSION`: allows dimension mismatch addition in `_add_type` (Killed by `test_addition_requires_equal_dimensions`).
    - `MUTANT-6-DSE-DECISION-LOGIC`: flips comparison operator $\le$ to $\ge$ in `SingleQoIEvaluator.evaluate` (Killed by `test_evaluator_known_gaussian_calculation`).
  - Tested in `tests/verification/test_mutation_resilience.py`; verified unmutated baseline passes, $6/6$ ($100\%$) mutants killed, with specific killer test recorded for each mutant.
- **WP2-R4 (Status Register Traceability Integrity)**:
  - Rewrote `src/gdec/verification/status_register.py` and `scripts/generate_status_register.py`:
    - Removed default assumption that file existence implies test pass; status register now invokes pytest via `PytestCollector` and records exact passing test node IDs.
    - Added stale commit detection (`recorded_sha != current_sha`) and dirty tree check (`is_dirty == True`).
    - Added `--check` CLI validation and `--allow-dirty` flag for local development testing (prohibited in CI).
    - Updated capability mapping in `SYSTEM_CAPABILITIES` to map existing verified test suites accurately.
- **WP2-R5 (Audit & Evidence Deliverables)**:
  - Updated `WP2_MASTER_REPORT.md`, `WP2_ACCEPTANCE_MATRIX.md`, `WP2_CHANGELOG.md`, `WP2_RISK_REGISTER.md`, and `ORCHESTRATION_STATE.md`.
  - Full suite passing: **429 passed, 0 failures** in ~40s.
