# GDEC Future Research Roadmap Addendum
## WP9 — Adaptive Computation and Solver Intelligence

**Status:** PROPOSED / NOT APPROVED FOR IMPLEMENTATION  
**Branch:** `research/wp9-adaptive-computation-roadmap`  
**Planning basis:** Current GDEC work-package campaign (WP0–WP7) and the research directions discussed for FEA, CFD and portable scientific computing.

---

## 1. Purpose

This addendum records the next research and engineering capabilities to consider after the current reliability, language/IR, verification, evidence, numerical-contract, heat-physics, certified-bound feasibility and release work.

The aim is not to build another monolithic FEM or CFD solver. GDEC should become an engineering computation orchestration and verification platform: it interprets engineering intent, represents the mathematical problem, selects suitable computational strategies, invokes appropriate numerical components, and checks the evidence supporting the result.

**North-star constraint:** affordable hardware should not be a barrier to useful engineering simulation. CPU execution remains a first-class path. GPU acceleration is optional, capability-gated and justified by measured end-to-end benefit.

This is a roadmap, not evidence that any listed capability exists or has been implemented.

## 2. Scheduling and campaign constraints

1. Do not interrupt or silently expand the currently active WP0–WP7 campaign.
2. The current master campaign explicitly prohibits hardware/GPU work during that campaign. This addendum does not override that restriction.
3. WP9 may begin only after the current campaign reaches its declared gates, or the owner explicitly re-baselines the campaign and approves the new dependency plan.
4. Before implementation, inspect the then-current orchestration state, active branches, decision register, baseline tests and latest reports. Do not assume old branch names, test counts or SHAs remain current.
5. Create a fresh implementation branch from the then-current approved successor branch. Never implement this roadmap directly on `main`.
6. Every integration must pass licensing, dependency, platform, maintenance and reproducibility review before adoption.
7. Do not claim certified/guaranteed accuracy unless a mathematically valid bound and its assumptions are implemented and independently checked.

## 3. WP9 — Adaptive Computation and Solver Intelligence

### WP9.1 — Solver portfolio and eligibility registry

**Objective:** replace implicit solver assumptions with explicit, inspectable solver capabilities and eligibility decisions.

Candidate capabilities:
- Conjugate Gradient for eligible symmetric positive-definite systems.
- GMRES and BiCGSTAB for suitable nonsymmetric systems.
- MINRES for eligible symmetric indefinite systems.
- Direct sparse solvers where appropriate.
- Jacobi, SSOR and incomplete-factorisation preconditioners where supported.
- Algebraic/geometric multigrid integrations after validation.

Requirements:
- Define a typed solver capability contract: supported operator properties, symmetry/SPD assumptions, precision, device, matrix format, constraints and known limitations.
- Distinguish verified properties from caller-declared assumptions.
- Reject unsupported combinations with typed, source-located diagnostics.
- Never silently substitute a solver or backend.
- Record the selection rationale and configuration in the execution/evidence record.

**Acceptance evidence:** solver eligibility test matrix, adversarial negative tests, reference-problem comparisons, deterministic selection records and no regression to the existing baseline.

### WP9.2 — Matrix-free operator framework

**Objective:** support operator application without requiring assembly/storage of a global sparse matrix for eligible problem classes, while preserving the assembled path.

Candidate work:
- Define a common linear-operator interface.
- Implement element-local operator application for the existing FEM vertical slice.
- Explore Jacobian-vector products (JVPs) and automatic differentiation only where they are numerically justified.
- Preserve an assembled reference implementation for cross-checking.
- Measure memory, setup cost and total solve time, including data movement.
- Add suitable preconditioning; matrix-free execution without an effective preconditioner is not automatically an improvement.

**Acceptance evidence:** assembled-versus-matrix-free QoI and residual comparisons, independent reference checks, memory measurements, scaling experiments and documented workload limits.

### WP9.3 — Multi-estimator and error-evidence framework

**Objective:** provide a common interface for error indicators and estimators without conflating their mathematical guarantees.

Candidate estimator families:
- Existing DWR indicators.
- Zienkiewicz–Zhu (ZZ) recovery.
- Residual-based a posteriori estimators.
- Energy-norm estimates.
- Goal-oriented/QoI error estimates.
- Equilibrated-flux or other mathematically certified bounds where their assumptions are satisfied.

Required status distinctions:
- heuristic indicator;
- asymptotic estimator;
- validated estimator for a specified problem class;
- mathematically certified bound under explicit assumptions.

Each estimator must declare its applicability conditions, required inputs, output meaning, assumptions, known failure modes and validation evidence. The system must refuse to present an inapplicable estimator as a bound.

**Acceptance evidence:** manufactured/reference solutions, effectivity-index studies where meaningful, adversarial applicability tests, explicit classification tests and independent checking for any claimed bound.

### WP9.4 — Adaptive computation controller

**Objective:** choose the next computational action based on the engineering objective, evidence quality, cost and resource constraints.

Potential actions:
- refine or coarsen the mesh where admissible;
- change polynomial order;
- change solver or preconditioner;
- tighten or relax algebraic tolerances only within the numerical contract;
- select assembled or matrix-free execution;
- select an admissible precision;
- request more samples or higher fidelity for uncertainty-sensitive objectives;
- stop when the acceptance criterion is supported;
- refuse or request additional evidence when it is not.

The controller must use explicit state transitions, deterministic policies where possible, recorded rationale and budget accounting. It must not infer that a small residual or a stable successive QoI value proves discretisation accuracy.

**Acceptance evidence:** controlled experiments against fixed baselines, matched-QoI comparisons, budget-exhaustion/refusal tests, reproducible decision traces and ablations showing which policy components matter.

### WP9.5 — Independent verification integration

**Objective:** preserve the separation between untrusted solver/planner output and independently checked evidence.

The checker should validate, as applicable:
- source and canonical IR identity;
- model assumptions, units and boundary conditions;
- mesh/discretisation admissibility;
- algebraic residuals and solver diagnostics;
- estimator or bound applicability;
- certificate structure, hashes and provenance;
- QoI computation and acceptance criteria.

Possible checker outcomes: `VERIFIED`, `NOT_VERIFIED`, `INCOMPLETE`, `INAPPLICABLE`. A status label or caller-supplied provenance string is not itself proof.

Begin with the simplest mathematically defensible vertical slice. The previously proposed steady linear heat-conduction problem remains a candidate, subject to the current heat-physics and certified-bound feasibility results.

**Acceptance evidence:** independent implementation or checker, tamper tests, negative cases, explicit theorem/assumption references for bounds and reproducible certificate verification.

### WP9.6 — Hardware-aware CPU/GPU workload planning

**Objective:** select execution resources based on capability and measured end-to-end benefit, without making expensive hardware mandatory.

Plan:
- Keep CPU as a first-class, tested backend.
- Define backend capability discovery and explicit device constraints.
- Model memory capacity, workload size, data-transfer overhead, supported precision and kernel coverage.
- Benchmark end-to-end execution, not only isolated kernel throughput.
- Add GPU backends incrementally only where an end-to-end workload is supported.
- Consider CUDA, HIP/ROCm and SYCL/oneAPI only after feasibility and maintenance review.
- Vulkan/OpenCL are optional research candidates, not automatic commitments.

No silent CPU fallback when a user explicitly requests an unavailable accelerator. Report the incompatibility clearly. Automatic selection may choose CPU only when the request permits it and the selection is recorded.

**Acceptance evidence:** reproducible CPU baseline, hardware inventory, backend capability tests, transfer-inclusive benchmarks, memory tests and correctness comparisons at matched QoI accuracy.

### WP9.7 — Benchmarking and research evaluation

Compare methods on identical problem definitions and acceptance criteria. Report:
- QoI error and its meaning;
- estimator/bound status and effectivity where applicable;
- DOFs/elements and refinement history;
- solver iterations and convergence diagnostics;
- wall-clock time including setup and transfers;
- peak memory;
- CPU/GPU model, software stack and precision;
- energy use where measurable;
- reproducibility and failure/refusal rate.

Do not equate fewer DOFs with faster execution. Do not compare methods at unmatched accuracy and present the result as a fair speedup.

## 4. Later research tiers

These are candidates for separate work packages after WP9 foundations. They are not part of the initial WP9 implementation scope.

### Tier 2 — Differentiable and reduced computation

1. **Differentiable simulation:** JVP/VJP, sensitivities, adjoint differentiation, inverse material identification and design optimisation. Candidate technology: JAX or PyTorch, selected per integration boundary.
2. **Reduced-order modelling:** Proper Orthogonal Decomposition (POD), reduced-basis methods, projection-based ROMs, parameter-space reduction and error estimation. Full-order fallback/correction must remain available.
3. **Mixed-precision computation:** FP64/FP32 and lower precision only where supported; iterative refinement, high-quality residual checks and explicit numerical admissibility. No precision choice based solely on speed.
4. **Multi-fidelity methods:** use lower-cost models to guide expensive computations, with discrepancy/error modelling and explicit validation.

### Tier 3 — AI-assisted engineering computation

1. Neural operators and learned surrogates for initial predictions, many-query workloads and reduced models.
2. AI-assisted preconditioner and mesh-refinement recommendations.
3. Uncertainty quantification and propagation.
4. Bayesian optimisation and active learning.
5. Digital-twin/data-assimilation workflows.

AI-generated predictions, recommendations and surrogates remain distinct from verified numerical solutions. They must be validated for distribution shift, conservation, boundary-condition fidelity and uncertainty before being used in engineering decisions.

## 5. Candidate external integrations

Integrate selectively; do not recreate mature solver ecosystems without a demonstrated need.

| Project/library | Candidate role | Integration posture |
|---|---|---|
| PETSc | Krylov solvers, preconditioners, parallel linear algebra | High-priority feasibility study |
| hypre | Algebraic multigrid and scalable solvers | High-priority feasibility study |
| MFEM | FEM infrastructure, high-order and matrix-free methods | High-priority research/reference backend |
| deal.II | Advanced FEM, adaptivity and matrix-free methods | Research/reference backend |
| FEniCSx | FEM formulation and independent cross-checking | High-priority validation integration |
| JAX | Differentiable numerical computing and accelerator execution | Tier 2 feasibility study |
| Gmsh | Geometry and mesh generation | Practical integration candidate |
| Trilinos | Solver and scientific-computing components | Evaluate overlap with PETSc |
| Neko | Portable high-order CFD reference/backend candidate | CFD research track |
| PyTorch | Differentiable models and learned surrogates | Tier 2/3, not a core solver dependency by default |

Before adopting any dependency, record:
- licence and transitive dependency compatibility;
- supported operating systems and hardware;
- API stability and maintenance activity;
- build/install burden;
- data interchange and ownership boundaries;
- correctness/validation evidence;
- performance on representative GDEC workloads;
- fallback and long-term maintenance plan.

## 6. Suggested dependency order

```text
Current WP0-WP7 campaign
        |
        v
Re-baseline + owner approval + architecture ADRs
        |
        v
WP9.1 Solver portfolio and eligibility
        |
        +----------------------+
        |                      |
        v                      v
WP9.2 Matrix-free         WP9.3 Estimator framework
        |                      |
        +-----------+----------+
                    |
                    v
             WP9.4 Adaptive controller
                    |
                    v
             WP9.5 Independent verification
                    |
                    v
             WP9.7 Matched-QoI benchmarks
                    |
                    v
             WP9.6 Hardware-aware planning
                    |
                    v
        Tier 2: differentiable / ROM / precision
                    |
                    v
        Tier 3: AI / UQ / multi-fidelity / twins
```

The exact order may change after architecture and dependency review. Verification work should not be deferred until after performance optimisation: its interface and evidence requirements must be designed early.

## 7. Architecture decisions required before implementation

- Whether canonical IR represents operators independently of assembled matrices.
- How variational forms and discrete operators are represented and versioned.
- How solver capabilities and mathematical eligibility are encoded.
- How estimator applicability and assurance status are represented in the evidence schema.
- How the adaptive controller is prevented from weakening a numerical contract.
- How backend selection, explicit user constraints and fallback policy interact.
- Which external libraries are dependencies, optional adapters or validation-only tools.
- How the independent checker avoids sharing the same failure modes as the solver.

Each decision requires an ADR, alternatives, rationale, consequences and migration plan.

## 8. Research claims and falsifiable hypotheses

The following are hypotheses to test, not claims of novelty or established superiority:

1. For selected memory-constrained FEM workloads, matrix-free execution can reduce peak memory while maintaining matched QoI accuracy.
2. A solver eligibility registry can prevent unsupported solver/operator combinations before execution.
3. A cost-aware adaptive controller can reduce total computational cost to a specified QoI acceptance target versus fixed refinement baselines on selected benchmark families.
4. Evidence-aware refusal can reduce unsupported engineering claims without making valid cases unusably restrictive.
5. Hardware-aware dispatch can improve end-to-end performance over fixed CPU/GPU selection on representative workloads, while preserving CPU-only usability.

For each hypothesis, conduct a prior-art review, specify a baseline, define metrics, design a kill-test and report negative results.

## 9. Explicitly deferred

- Replacing established commercial FEA/CFD solvers.
- Building a complete general-purpose CFD solver before the orchestration architecture is mature.
- Supporting every GPU vendor or accelerator in one release.
- Making neural operators the default source of engineering results.
- Claiming certified results for estimator families without a proof and applicability conditions.
- Adding features solely to increase feature count or benchmark FLOPS.

## 10. Completion definition for this roadmap

This addendum is complete as a planning artifact only. It does not authorise implementation, change the current campaign's no-hardware rule, modify the main branch, or upgrade any capability status.

Implementation requires an owner-approved work-package prompt, current baseline verification, architecture ADRs, scoped acceptance gates and a separate research branch.
