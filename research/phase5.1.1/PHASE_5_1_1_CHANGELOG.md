# GDEC Phase 5.1.1 — Changelog

**Release:** Phase 5.1.1 Correctness & Evidence Remediation  
**Branch:** `research/phase-5.1.1-correctness-remediation`  
**Base Commit:** `b54c597360171e523e92f660a89af4aa2e1ed7b4`

---

### 1. Workstream A: Solver Reliability & Conjugate Gradient Safety
- **Added:** `src/gdec/core/backend/spd_check.py` implementing `verify_cg_eligibility` and `compute_symmetry_defect`.
  - Performs structural checks: square dimension, symmetry defect $\|A - A^T\|_\infty \le 10^{-12}$, and strictly positive diagonal entries $\min(A_{ii}) > 0$.
  - Performs spectral screening when `caller_certified_spd=False`: detects negative algebraic eigenvalues via `scipy.linalg.eigvalsh` ($N \le 2000$) or ARPACK `spla.eigsh` ($N > 2000$).
  - Correctly rejects the counterexample matrix $A = [[1, 2], [2, 1]]$ ($\text{diag} = [1, 1] > 0$, $\lambda = -1, 3$).
- **Modified:** `src/gdec/core/backend/cpu.py`:
  - Updated `CPUBackend.solve_cg` to integrate `verify_cg_eligibility`.
  - Added strict preconditioner verification: rejects any preconditioner that does not declare `is_spd = True`.
- **Modified:** `src/gdec/core/backend/cuda.py`:
  - Enforced unified structural and spectral screening in `CUDABackend.solve_cg`.
  - Added support for GPU-resident Jacobi preconditioning (`M="jacobi"`).
  - Explicitly rejected host CPU `LinearOperator` preconditioners with `UnsupportedCapabilityError`.
  - Evaluated residual $\|b - Ax\|_2$ directly on device via CuPy without transferring sparse matrix $A$ to host memory.
  - Honestly reported `iterations: None` due to CuPy API limitations.

---

### 2. Workstream B: DSE Evidence Enforcement & Refusal
- **Added:** `src/gdec/dse/evidence.py` defining:
  - `ValidationStatus` enum: `UNASSESSED`, `VERIFIED`, `VALIDATED`, `INDEPENDENTLY_VALIDATED`, `CALIBRATED`.
  - `EvidenceRecord` frozen model: `id`, `category`, `provenance`, `model_reference`, `validation_status`, `applicable_domain`, `numerical_metric`.
  - `EvidenceAssessment` frozen model: comprehensive audit package required for evaluation.
- **Modified:** `src/gdec/dse/evaluator.py`:
  - Required validated `EvidenceAssessment` before computing risk or loss integrals; missing assessment yields `INSUFFICIENT_EVIDENCE`.
  - Added validation gates: required category matching, assumption attestation, applicable domain checking, and model reference consistency.
  - Removed `allow_refine` bypass; discretisation quality breaches unconditionally return `REFINE`.
  - Fixed relative DWR error normalisation to use explicit positive `reference_scale`.
  - Resolved exact risk ties to conservative `REFINE`.

---

### 3. Workstream C: Analytical Parameter Scaling
- **Modified:** `src/gdec/dse/scaling.py`:
  - Removed default `True` flags on `ScalingAssumptions`; all preconditions must be explicitly attested with `attested_by`.
  - Enforced `qoi_type == "fixed_displacement"`; explicitly rejected compliance energy ($P^2/E$) and stress functionals.
  - Validated all finite inputs on scalar and batch evaluations; rejected empty batches and non-positive Young's moduli.
- **Added:** `benchmarks/phase5_1_1/scaling/validate_scaling_fem.py`:
  - Independent FEM rerun across 5 parameter variations matching analytical scaling to within $2.11 \times 10^{-12}$.
  - Raw results documented in `research/phase5.1.1/scaling/SCALING_RAW_RESULTS.csv`.

---

### 4. Workstream D: GPU Benchmark Integrity
- **Added:** `benchmarks/phase5_1_1/gpu/benchmark_suite.py`:
  - Constructed true 2D discrete Laplacian via Kronecker sum: $A = I_y \otimes T_x + T_y \otimes I_x$.
  - Reconciled non-zero counts to physical grid formulas ($5n^2 - 4n$): Small ($24,220$), Medium ($127,360$), Large ($510,720$).
  - Implemented direct wall-clock timing with `cp.cuda.Stream.null.synchronize()`.
  - Measured actual GPU-resident PCG solve with Jacobi preconditioner vs CPU CG.
  - Strictly separated CPU setup/factorization timings from GPU columns.
  - Saved raw sample repetitions to `research/phase5.1.1/gpu/GPU_BENCHMARK_RAW_SAMPLES.csv`.
  - Saved summary statistics to `research/phase5.1.1/gpu/GPU_BENCHMARK_SUMMARY.csv`.

---

### 5. Verification & Tests
- **Added:** `tests/test_phase5_1_1_adversarial.py` containing 20 adversarial tests covering all failure classes.
- **Updated:** `tests/test_backend.py`, `tests/test_cuda_backend.py`, `tests/test_dse.py`.
- **Result:** Total test count increased from 212 to 234 passing tests (100% pass rate).
