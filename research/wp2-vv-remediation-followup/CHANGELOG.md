# GDEC WP2 Final Remediation Follow-up — Changelog

All changes implemented on branch `research/wp2-vv-remediation-followup`.

---

## [WP2-Remediation-Followup] - 2026-11-23

### Fixed & Enhanced
- **Status Register & Traceability Architecture (`src/gdec/verification/status_register.py`, `scripts/generate_status_register.py`)**:
  - Removed `-uno` from `get_git_info()`; now detects both tracked modifications and untracked files while explicitly preserving user files (`src/gdec/core/analyser.py`, `src/gdec/runtime/`).
  - Untracked `results/status_register.json` from git and added to `.gitignore`. Status registers are now authoritative CI artifacts generated per run, eliminating self-referential commit SHA chicken-and-egg issues.
  - Implemented rigorously computed `demonstrated_status` based on actual executed test node IDs and outcomes.
  - Added strict hierarchy check: gate fails if `claimed_status` exceeds `demonstrated_status`, if required tests did not execute, or if tests were skipped.
  - Added `--input` argument to `generate_status_register.py` for flexible verification without modifying working tree.
  - Updated `tests/verification/test_status_register_traceability.py` to use isolated `tmp_path` across all tests. Added tests for demonstrated status enforcement, skipped test rejection, and untracked file detection.

- **REF-06 Kirsch Plate with Circular Hole (`src/gdec/verification/reference_problems.py`, `tests/verification/test_reference_library.py`)**:
  - Added authoritative closed-form function `kirsch_plate_hole_analytical`.
  - Implemented 3-level graded refinement series ($12\times 16 \to 24\times 32 \to 48\times 64$).
  - Implemented area-weighted patch stress recovery at hole boundary $(0, a)$.
  - Demonstrated monotonic convergence of $K_t \to 3.000$ ($2.9524 \to 2.9964 \to 3.0018$) with relative error dropping to $0.06\%$.
  - Added `test_ref_06_kirsch_perturbation_sensitivity`: proves deliberate $+15\%$ traction perturbation causes benchmark failure ($K_t = 3.4521$).

- **REF-05 Lamé Thick Cylinder (`src/gdec/verification/reference_problems.py`, `tests/verification/test_reference_library.py`)**:
  - Added authoritative closed-form functions `lame_cylinder_analytical_plane_stress` and `lame_cylinder_analytical_plane_strain`.
  - Independently solved and verified 2D elasticity for both Plane Stress and Plane Strain.
  - Compared full radial displacement profiles $u_r(r)$ across $r \in [a, b]$.
  - Verified 3-level mesh refinement convergence: $p_{\text{obs}} = 2.002$ (plane stress) and $p_{\text{obs}} = 2.000$ (plane strain). Fine mesh $L^2$ error $< 0.08\%$.

- **REF-07 L-Shaped Singular Corner (`src/gdec/verification/reference_problems.py`, `tests/verification/test_reference_library.py`)**:
  - Clarified theoretical relationship: asymptotic Mode I rate is $\mathcal{O}(h^{2\lambda})$ with $\lambda \approx 0.54448$.
  - Extended solve to 4 refinement levels ($k=1, 2, 3, 4$).
  - Verified monotonic strain energy convergence ($U_0 < U_1 < U_2 < U_3$) from below.
  - Verified monotonic increment reduction ($\Delta U_{01} > \Delta U_{12} > \Delta U_{23}$).
  - Fitted and reported observed pre-asymptotic rate $\lambda_{\text{obs}} \in [0.497, 0.706] < 1.0$.

- **Mutation Testing (`src/gdec/verification/mutation_harness.py`, `scripts/run_mutation_campaign.py`)**:
  - Fixed Mutant 2 in `mutation_harness.py` to mutate production module `gdec.fem.matrix_diagnostics.compute_symmetry_defect`.
  - Investigated `mutmut` 3.8.1 platform compatibility (documented native Windows limitation per issue #397).
  - Built bounded source-level mutation campaign runner `scripts/run_mutation_campaign.py` covering 14 substantive mutants across 6 core production modules (`fem.constitutive`, `fem.matrix_diagnostics`, `fem.adaptivity`, `dse.evaluator`, `dse.scaling`, `eir.expressions`).
  - Achieved $14/14$ ($100.0\%$) kill rate.

- **CI Workflow (`.github/workflows/ci.yml`)**:
  - Added `fetch-depth: 0` to all checkout steps across all 4 workflow jobs.
  - Configured status register generation, verification, and artifact upload (`actions/upload-artifact@v4`).
  - Added post-test clean-working-tree check (`git status --porcelain`).
  - Added mutation campaign execution and artifact upload.
