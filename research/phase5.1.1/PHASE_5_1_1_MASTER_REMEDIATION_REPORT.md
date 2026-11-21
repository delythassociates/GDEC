# GDEC Phase 5.1.1 — Master Remediation and Technical Validation Report

**Author:** Lead Engineering Research Orchestrator & Computational Mechanics Verification Specialist  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.1-correctness-remediation`  
**Base Parent Commit:** `b54c597360171e523e92f660a89af4aa2e1ed7b4` (Phase 5.1 prototype baseline)  
**Pull Request #1 State:** Kept open, draft, and strictly unmerged (`https://github.com/delythassociates/GDEC/pull/1`)

---

## 1. Executive Summary & Remediation Objectives

Phase 5.1 introduced experimental prototypes for CPU/CUDA backend execution, Decision Sufficiency Engine (DSE) evaluation, analytical parameter scaling, and GPU benchmarking. A subsequent rigorous independent software audit identified critical correctness and verification gaps:
1. **Conjugate Gradient Indefinite Vulnerability:** CPU and CUDA backends permitted symmetric indefinite matrices with positive diagonal entries to enter the CG solver, resulting in silent divergence or breakdown.
2. **DSE Evidence Bypass:** The DSE evaluator allowed decisions to be rendered without auditable evidence packages and permitted callers to bypass DWR discretization error gates via `allow_refine=False`.
3. **Analytical Scaling Over-Generalization:** Scaling assumptions defaulted to `True` without caller provenance, and formulas did not restrict displacement functionals from quadratically scaling compliance or stress.
4. **GPU Benchmark Distortions:** Benchmarks utilized an invalid 1D banded stencil rather than a true 2D Kronecker discrete Laplacian, conflated CPU factorization timings into GPU metric columns, and omitted device-resident PCG solve measurements.

Phase 5.1.1 resolves 100% of these findings. All existing test baselines and legacy features from Phases 1 through 4 remain strictly preserved, with test coverage expanding from 212 tests to **234 passing tests**.

---

## 2. Technical Classification Taxonomy

Every component, interface, and claim in Phase 5.1.1 is strictly partitioned into the following formal evidentiary categories:

### A. Implemented & Tested (234 Automated Tests)
- `verify_cg_eligibility` structural + spectral verification engine (`src/gdec/core/backend/spd_check.py`).
- CPU Conjugate Gradient safety gate rejecting asymmetric, non-positive diagonal, and indefinite matrices.
- CUDA Conjugate Gradient safety gate enforcing identical spectral guarantees on GPU.
- GPU Jacobi preconditioner evaluation and safe rejection of host CPU `LinearOperator` objects.
- GPU residual computation $\|b - Ax\|_2$ executed directly in VRAM without transferring sparse matrix $A$.
- Typed `EvidenceRecord`, `ValidationStatus`, and `EvidenceAssessment` data models (`src/gdec/dse/evidence.py`).
- Fail-closed refusal gates in `SingleQoIEvaluator` enforcing required evidence categories, assumption attestation, and domain/model reference integrity.
- Removal of `allow_refine` bypass; mandatory DWR discretisation quality gate enforcement.
- Analytical parameter scaling assumption model requiring explicit provenance (`attested_by`).
- Rejection of compliance ($P^2/E$) and stress functionals in linear-elastic displacement scaling.
- True 2D Kronecker discrete Laplacian benchmark suite ($A = I_y \otimes T_x + T_y \otimes I_x$).

### B. Numerically Verified & Independently Validated
- **Symmetric Indefinite Rejection:** Matrix $A = [[1, 2], [2, 1]]$ has $\text{diag} = [1, 1] > 0$ but eigenvalues $\lambda_1 = -1, \lambda_2 = 3$. Verified rejected by both CPU and CUDA backends under `caller_certified_spd=False`.
- **Independent FEM Validation:** Full 2D elasticity cantilever plate FEM rerun across 5 parameter variations matched analytical scaling to within $2.11 \times 10^{-12}$ relative discrepancy (`benchmarks/phase5_1_1/scaling/validate_scaling_fem.py`).
- **Exact Grid Discretisation:** Nonzero entry counts for 2D Kronecker stencils exactly match theoretical counts ($N=4,900 \implies 24,220$ NNZ; $N=25,600 \implies 127,360$ NNZ; $N=102,400 \implies 510,720$ NNZ) with zero discrepancy.

### C. Physical Hardware Tested
- Verified on physical **NVIDIA GeForce RTX 3050 6GB Laptop GPU** (Driver 595.97, CUDA 13.2 / 12.9, CuPy 14.2.0, SM 8.6 Ampere architecture).
- Recorded 30 repetitions per scale across SpMV, batched parameter propagation, PCG solves, and multi-RHS factorizations.
- Raw sample observations persisted in `research/phase5.1.1/gpu/GPU_BENCHMARK_RAW_SAMPLES.csv`.
- Summary statistics persisted in `research/phase5.1.1/gpu/GPU_BENCHMARK_SUMMARY.csv`.

### D. Deferred & Unsupported (Explicit Boundaries)
- **Deferred to Phase 5.2:** GPU native sparse direct solvers (cuDSS / CHOLMOD on device).
- **Deferred to Phase 5.2:** Fused C++/CUDA custom iterative solver kernels.
- **Unsupported:** Calling Conjugate Gradient on non-SPD or indefinite systems without explicit `caller_certified_spd=True`.
- **Unsupported:** Applying $(P/P_0)(E_0/E)$ scaling to compliance energy ($C \propto P^2/E$), von Mises stress, or geometrically nonlinear problems.
- **Unsupported:** Evaluating DSE contracts without a validated `EvidenceAssessment`.

---

## 3. Answers to the 25 Technical Review Questions

### Section I: Conjugate Gradient Safety & Preconditioning
1. **How is positive definiteness verified for CG without imposing prohibitive $O(N^3)$ dense overheads?**  
   We employ a tiered strategy in `src/gdec/core/backend/spd_check.py`:
   - Structural screening ($O(N + \text{nnz})$): checks symmetry defect $\|A - A^T\|_\infty \le 10^{-12}$ and positive diagonal entries $\min(A_{ii}) > 0$.
   - Spectral screening: for $N \le 2000$, dense `scipy.linalg.eigvalsh`; for $N > 2000$, iterative shift-invert / shift-and-invert ARPACK `spla.eigsh(A, k=1, which="SA")` to detect negative eigenvalues in $O(\text{nnz} \cdot k)$.
   - When the user explicitly guarantees SPD-ness via structural problem knowledge (e.g. standard FEM stiffness matrices with fixed Dirichlet boundaries), they specify `caller_certified_spd=True`, which bypasses spectral screening while retaining $O(N)$ diagonal screening.
2. **Why was $A = [[1, 2], [2, 1]]$ accepted previously, and how is it now handled?**  
   Previously, the check only verified that the diagonal entries were strictly positive ($A_{00} = 1 > 0, A_{11} = 1 > 0$). Because this is a necessary but not sufficient condition, the indefinite matrix with eigenvalues $\lambda \in \{-1, 3\}$ slipped through. In Phase 5.1.1, spectral screening detects $\lambda_{\min} = -1.0 < 0$ and immediately raises `NumericalBackendError("Matrix A is indefinite: smallest algebraic eigenvalue lambda_min = -1.00e+00 < 0")`.
3. **What is the caller certification contract for CG?**  
   `caller_certified_spd: bool = False`. If `False`, the backend performs rigorous structural and spectral checks. If `True`, the caller takes legal and numerical liability for the SPD property; the backend only verifies basic dimensions and non-positive diagonal entries.
4. **How are custom preconditioners checked for SPD compatibility?**  
   Preconditioners must explicitly declare `is_spd = True`. In CPUBackend, if `not getattr(M, "is_spd", False)`, `NumericalBackendError` is raised.
5. **How does CUDABackend handle host CPU `LinearOperator` preconditioners?**  
   Passing a CPU `LinearOperator` to `CUDABackend` raises `UnsupportedCapabilityError`. Only GPU-resident preconditioners (such as `cupyx.scipy.sparse.linalg.LinearOperator` or the built-in `"jacobi"` string) are executed on device.
6. **How is the GPU residual norm calculated without matrix transfer?**  
   In `CUDABackend.solve_cg`, residual $r = b - A x$ is evaluated entirely on device via `r_gpu = b_gpu - A_gpu.dot(x_gpu)` and `cp.linalg.norm(r_gpu).get()`. Matrix $A$ is never transferred back to host RAM.
7. **What is the iteration telemetry contract for CuPy CG?**  
   CuPy's `cp_spla.cg` does not implement an iteration callback or return iteration counts. Rather than reporting a fake number, `CUDABackend` reports `"iterations": None` and documents this restriction.

### Section II: DSE Evidence Enforcement & Refusal
8. **What is the schema and purpose of `EvidenceAssessment`?**  
   It is a strongly typed, frozen Pydantic model (`src/gdec/dse/evidence.py`) containing `assessment_id`, `evidence_records`, `validated_assumptions`, `model_reference`, `applicable_domain`, `validation_status`, `reference_scale`, and `provenance`. It serves as the auditable package proving that simulation evidence is legally and technically qualified.
9. **What happens if `assessment is None` is passed to `SingleQoIEvaluator`?**  
   It immediately aborts decision evaluation and returns `DecisionRecommendation.INSUFFICIENT_EVIDENCE`.
10. **How are required evidence categories enforced?**  
    The evaluator verifies that every string in `contract.evidence.required_categories` is present in `assessment.supplied_categories`. Any missing category forces `INSUFFICIENT_EVIDENCE`.
11. **How is domain applicability verified?**  
    The evaluator checks `assessment.applicable_domain == contract.evidence.applicable_domain`. A mismatch forces `INSUFFICIENT_EVIDENCE`.
12. **How is model reference consistency checked?**  
    `assessment.model_reference` must match `contract.qoi.model_reference`. Mismatched models force `INSUFFICIENT_EVIDENCE`.
13. **Can `allow_refine=False` bypass DWR quality gates in Phase 5.1.1?**  
    No. The bypass was completely removed. If relative DWR error exceeds the contract's quality threshold, the recommendation is unconditionally forced to `DecisionRecommendation.REFINE`.
14. **How is relative DWR error normalized?**  
    Normalisation by near-zero $\mu$ was eliminated. It is normalized by an explicit positive reference scale $J_{\text{ref}} > 0$ declared in `assessment.reference_scale` or the contract limit.
15. **What is the DSE policy on exact risk ties?**  
    If $R_{\text{release}} == R_{\text{revise}}$, the engine refuses to release and returns `DecisionRecommendation.REFINE`, requiring additional computational or experimental evidence.
16. **What is the legal/epistemic meaning of a `RELEASE` recommendation?**  
    `RELEASE` certifies mathematical sufficiency under the declared contract, prior distribution, loss matrix, and submitted evidence records. It does not certify unmodeled physical phenomena or guarantee immunity from uncaptured failure modes.

### Section III: Analytical Parameter Scaling
17. **What assumptions are required for exact $(P/P_0)(E_0/E)$ scaling?**  
    Linear-elastic small-strain Hookean mechanics, fixed geometry, fixed Poisson's ratio, homogeneous spatial scaling of $E$, fixed proportional loading, and a linear displacement functional QoI.
18. **Why was default `True` removed from `ScalingAssumptions`?**  
    Defaulting assumptions to `True` allowed unverified physical extrapolation. Every precondition must now be explicitly attested by the caller with a named provenance in `attested_by`.
19. **Why is compliance energy rejected from this scaling formula?**  
    Compliance $C(P, E) = f(P)^T u(P, E)$ involves the inner product of load and displacement. Because $u \propto P/E$, compliance scales as $(P/P_0)^2 (E_0/E)$, which is quadratic in $P$. Applying linear scaling to compliance is a mathematical error.
20. **Why are stress QoIs rejected?**  
    Local stress evaluation depends on spatial gradient post-processing and multiaxial tensor invariants (e.g. von Mises) which do not scale as simple scalar linear displacement functionals.
21. **How was the analytical scaling independently validated?**  
    In `benchmarks/phase5_1_1/scaling/validate_scaling_fem.py`, a 2D cantilever plate elasticity problem was assembled and solved using the full GDEC FEM engine across 5 parameter combinations. The analytical scaling matched the full FEM solutions to within $2.11 \times 10^{-12}$ relative discrepancy.

### Section IV: GPU Benchmark Methodology & Findings
22. **What was wrong with the Phase 5.1 5-point stencil?**  
    It generated a 1D banded matrix with artificial jump bands, yielding non-zero counts that did not match true 2D discrete Laplacian discretisations.
23. **How is the true 2D Laplacian constructed in Phase 5.1.1?**  
    Via the Kronecker sum $A = I_y \otimes T_x + T_y \otimes I_x$. The nonzeros match theoretical counts exactly ($5n^2 - 4n$).
24. **Where does GPU SpMV become faster than single-threaded CPU?**  
    Device-resident SpMV surpasses CPU between $N \approx 50,000$ and $N \approx 75,000$. At $N = 102,400$, GPU kernel speedup is $2.63\times$. However, end-to-end SpMV (including PCIe transfer) remains slower on GPU ($0.25\times$).
25. **Is GPU PCG faster than CPU PCG for small-to-medium meshes?**  
    No. Due to CuPy Python dispatch and kernel launch overheads per iteration, CPU PCG with Jacobi preconditioning is $13\times$ faster at $N = 4,900$ and $1.4\times$ faster at $N = 25,600$. Fused GPU iterative kernels are required for competitive GPU iterative solving (deferred to Phase 5.2).
