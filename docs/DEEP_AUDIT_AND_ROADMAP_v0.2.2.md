# GDEC v0.2.2 — Deep Repository Audit and Engineering Roadmap

**Audit date:** 2026-11-21  
**Audited ref:** `main` (latest observed commit `05d9a70b2bafc722b6098dd5d164cedf3f8415ea`, 2026-11-20 22:42:49 UTC)  
**Baseline release:** README identifies v0.2.2.  
**Audit type:** Static source and documentation inspection through GitHub. No code was executed; no test suite was run. Findings below are source-level findings unless explicitly labelled as README claims.

## 1. Executive assessment

GDEC is a real, focused engineering-computation prototype, not merely an architecture proposal. The inspected repository documents and contains a declarative `.gdc` language, Lark parser, typed Pydantic IR, 2D small-strain linear-elasticity FEM solver, primal/adjoint solves, adaptive mesh refinement, a resource-budget controller, CLI, Streamlit application, and comparative benchmark infrastructure.

The correct current product description is:

> A CPU-only, 2D P1 triangular FEM research prototype for goal-aware adaptive linear elasticity, with a declarative front end and an experimental runtime/benchmarking framework.

It is not yet a general-purpose engineering compiler, multi-physics platform, GPU/HPC execution system, or certified goal-oriented error-control system.

The README advertises 42 passing tests and benchmark outcomes. Those are repository claims, not independently reproduced in this audit.

## 2. Repository facts observed

- Repository: `delythassociates/GDEC`; private; default branch `main`.
- Repository metadata reports size 3,423 KB.
- Latest observed commit: `05d9a70b2bafc722b6098dd5d164cedf3f8415ea` ("Add files via upload").
- Prior release commit: `789f1f1f8fd43fc1fca65d098ca17bd5714158ea` ("GDEC v0.2.2 - Initial private review release").
- `pyproject.toml` and package `__version__` both report 0.2.2. This resolves the earlier version mismatch for the currently inspected main branch.
- `tabulate>=0.9.0` is now declared in both `pyproject.toml` and `requirements.txt`. This resolves the earlier dependency omission in the currently inspected main branch.
- Declared core dependencies include NumPy, SciPy, scikit-fem, Matplotlib, pandas, Streamlit, Plotly, Lark, Pydantic, psutil and tabulate; pytest is an optional test dependency in project metadata and appears in requirements.
- README reports 42 tests. The inspected test samples cover compiler reproducibility/diagnostics and runtime convergence/budget behavior.
- README explicitly limits execution to CPU, 2D linear elasticity, P1 triangles. GPU backends, higher-order elements and 3D elasticity are future work.

## 3. Architecture assessment

### Existing implemented path (source inspected)

`.gdc` source → Lark parser → mutable dataclass AST → semantic analyzer/lowering → Pydantic `ProblemIR` → execution planner → CPU FEM runtime → primal/adjoint solves → QoI and indicators → adaptive refinement → telemetry/benchmark exports.

### Strengths

1. Declarative problem description is a useful abstraction boundary.
2. The IR is solver-independent in intent and JSON serializable.
3. The FEM implementation uses sparse assembly and sparse direct factorization.
4. For the symmetric linear-elasticity operator, primal/adjoint factorization reuse is a sound optimization.
5. The runtime checks actual candidate mesh DOFs before committing a refinement.
6. The benchmark code separates runtime successive-change convergence from reference-relative error in its reported iteration data.
7. The README and limitations document correctly distinguish the adjoint heuristic from a certified DWR estimator and explicitly state CPU-only support.

### Architectural gaps

- The planner currently selects a fixed initial grid from geometry aspect ratio and carries through user-selected strategy; it is not yet an optimizer over solver, discretization, backend and resource choices.
- The runtime is specialized to the current FEM engine rather than using a formal solver/backend capability contract.
- The IR schema version remains `gdec_ir_v0.1`; schema evolution and migration policy need formal tests before broadening the language.
- Units are embedded in documentation/conventions rather than represented as typed IR quantities.
- The DSL's current grammar and semantic lowering are much narrower than a general engineering language.
- The runtime's accuracy target is successive QoI change, not a certified error bound or a guarantee of error relative to the continuum solution.

## 4. High-priority source findings

### GDEC-AUD-001 — Objective kind is not honored by the numerical engine
**Severity:** Critical semantic correctness  
**Evidence:** `ObjectiveIR.kind` allows both `average_displacement` and `point_displacement`. The semantic analyzer accepts both. The FEM solver's `assemble_qoi_adjoint_vector` always assembles a boundary-average functional; it receives only boundary and component, not point coordinates. The runtime passes only boundary and component.  
**Impact:** A source file declaring `point_displacement` can compile but be evaluated as a boundary-average displacement. The output can be numerically plausible while representing the wrong engineering objective.  
**Required action:** Either reject `point_displacement` at compile time until implemented, or add explicit point coordinates, point-location/interpolation semantics, mesh-boundary behavior and corresponding adjoint-vector tests. Do not silently reinterpret it.

### GDEC-AUD-002 — Semantic validation can leak Pydantic exceptions
**Severity:** High reliability  
**Evidence:** Semantic lowering constructs `ProblemIR` directly. The compiler catches `GDECSemanticError` but does not catch Pydantic `ValidationError`. Some user-provided values are converted and passed through to Pydantic (for example adaptivity fraction and max iterations).  
**Impact:** Invalid but syntactically valid user input may raise an uncaught exception rather than produce a normal compiler diagnostic.  
**Required action:** Validate values explicitly and convert model-validation failures into structured source-located compiler diagnostics. Avoid using Pydantic exceptions as user-facing control flow.

### GDEC-AUD-003 — Unknown and duplicate declarations/arguments are silently accepted
**Severity:** High language integrity  
**Evidence:** Semantic analysis groups statements and commonly selects the last occurrence. Parser `arg_list` stores named arguments in a dict, overwriting duplicate names. Unrecognized top-level statements and extra named arguments are not comprehensively rejected.  
**Impact:** Typographical errors can be ignored; duplicated declarations can change meaning silently; an engineer may believe a parameter was applied when it was not.  
**Required action:** Define an explicit declaration schema, reject unknown declarations and unknown arguments, reject duplicate singleton declarations and duplicate named arguments, and preserve precise source locations.

### GDEC-AUD-004 — Numeric validation is incomplete
**Severity:** High numerical safety  
**Evidence:** Positive checks are mostly comparisons against zero; finite-value checks are absent. Budget conversion uses `int(val)`, which can silently truncate fractional values. `max_iterations` is converted to int before a dedicated source-level integer/range check.  
**Impact:** Non-finite or fractional inputs may produce invalid physical models, silent budget changes or unexpected runtime errors.  
**Required action:** Require finite real values for all physical/numerical scalars; require exact positive integers for DOF and iteration budgets; enforce explicit bounds for marking fractions and reject booleans where numeric scalars are expected.

### GDEC-AUD-005 — Accuracy target semantics can be mistaken for actual error
**Severity:** Critical scientific-claim risk  
**Evidence:** Runtime controller checks relative change between successive mesh QoI values and requires two consecutive passes. The benchmark runner separately computes error relative to a high-resolution numerical reference.  
**Impact:** Runtime convergence does not establish continuum accuracy, model adequacy or a certified error bound. A plateau or a poor reference/model can still satisfy successive-change tolerance.  
**Required action:** Rename/report the target as `successive_qoi_change_pct`; report reference-relative error separately when a reference exists; expose convergence status and evidence type distinctly. Never label this as a guaranteed physical accuracy percentage.

### GDEC-AUD-006 — Benchmark hypothesis decision ignores wall-clock performance
**Severity:** High research validity  
**Evidence:** `BenchmarkRunner._evaluate_hypothesis` computes mean DOF and time advantages but sets `hypothesis_supported = mean_dof_adv > 1.05`. The time ratio is not part of the decision. If no threshold is jointly achieved, the default DOF ratio of 1.0 leads to a negative result, but the criterion still only tests DOFs.  
**Impact:** The report can claim the central computational-efficiency hypothesis is supported even if wall-clock time is worse. This conflicts with the broader research hypothesis that includes computational cost.  
**Required action:** Separate hypotheses: (H1) DOF efficiency at matched reference error; (H2) wall-clock efficiency at matched reference error; (H3) memory efficiency. Report each independently, with uncertainty and repetitions. Avoid one combined “supported” badge unless the acceptance rule is pre-registered.

### GDEC-AUD-007 — Reference adequacy is calculated but not enforced
**Severity:** High benchmark validity  
**Evidence:** Reference solver calculates a three-level successive change and a boolean adequacy flag using a 0.15% threshold. Benchmark runner continues to evaluate thresholds even if the reference is inadequate.  
**Impact:** Comparisons at 0.25% (or finer) may be made against a reference whose own estimated discretization uncertainty is too high.  
**Required action:** Mark comparisons invalid/inconclusive when reference adequacy fails; adaptively increase reference resolution until an explicit criterion is met or a reference budget is reached. Include reference uncertainty in every comparison.

### GDEC-AUD-008 — Reference mesh target is approximate, not an enforced DOF target
**Severity:** Medium benchmark reproducibility  
**Evidence:** ReferenceSolver derives `nx` and `ny` from target DOFs using an aspect-ratio formula, then uses actual resulting mesh DOFs. The resulting DOF count can differ from the requested target.  
**Impact:** Benchmark labels can imply a target resolution not exactly achieved.  
**Required action:** Record requested and actual DOFs; optionally solve for integer mesh dimensions that approach the target without exceeding memory/budget.

### GDEC-AUD-009 — Runtime can stop on a predicted budget violation before testing a feasible candidate
**Severity:** Medium resource efficiency  
**Evidence:** The controller stops when predicted next DOFs exceed budget. Runtime later performs exact candidate refinement and checks actual DOFs before commit, but this exact check is bypassed when the prediction alone causes an earlier stop.  
**Impact:** A conservative or inaccurate predictor may terminate refinement even when the candidate would fit. The transactional exact check is valuable, but its potential is partly underused.  
**Required action:** Use the cost model to rank/select a subset of marked elements or to trigger a safe candidate construction; let exact candidate DOFs be the authoritative commit gate. Preserve memory/time safeguards for candidate generation.

### GDEC-AUD-013 — Equal-accuracy timing excludes mesh-refinement work
**Severity:** High research validity  
**Evidence:** The benchmark runner accumulates `IterationRecord.total_iteration_time_sec`. The runtime finalizes that interval before it performs the next mesh refinement; refinement duration is stored separately in `refinement_time_sec`.  
**Impact:** Time-to-target can omit the cost of generating the mesh on which the next QoI is measured, overstating goal-aware wall-clock efficiency.  
**Required action:** Include the preceding refinement duration in elapsed time at each QoI observation, and reconcile cumulative observation times with total runtime wall time.

### GDEC-AUD-014 — Cost model, marking policy and estimator cost metadata disagree
**Severity:** Medium resource-planning reliability  
**Evidence:** `docs/cost_model.md` reports approximately 1.8–2.4 DOFs per marked element; `CostModel` clamps predictions to 3.5–9.0; `MeshAdaptor.mark_elements` uses 6 DOFs per marked element; estimators expose 3 or 4 in per-element metadata.  
**Impact:** Different runtime layers reason about different refinement costs, making planning and budget efficiency hard to interpret.  
**Required action:** Establish one cost-estimation contract, record predicted-versus-observed residuals, and keep exact candidate DOFs as the authoritative budget gate.

### GDEC-AUD-010 — Documentation and implementation drift
**Severity:** Medium maintainability  
**Evidence:** Several source diagnostics and hardware strings still mention v0.1/v0.2.1 while package and README identify v0.2.2. Compiler design documentation says AST has end-line/end-column tracking, while the inspected `SourceLocation` stores only line and column. The independent review guide asks whether AST nodes are immutable, while inspected dataclasses are not frozen.  
**Impact:** Users and reviewers cannot reliably distinguish actual guarantees from intended design.  
**Required action:** Make documentation reflect current behavior, or implement the claimed behavior. Add documentation consistency checks.

### GDEC-AUD-011 — Objective/load/geometry schema needs stronger well-posedness checks
**Severity:** High engineering correctness  
**Evidence:** Semantic lowering accepts missing traction components by defaulting both to zero, and it does not explicitly reject zero net load or validate the full boundary/load/objective combination for a meaningful problem.  
**Impact:** A syntactically valid input may represent an unintended zero-load or otherwise meaningless computation.  
**Required action:** Define explicit load defaults and warnings; check net loading, constrained rigid-body modes, objective observability and boundary compatibility. Distinguish intentional zero-load test cases from likely mistakes.

### GDEC-AUD-012 — Plane stress/strain post-processing semantics need review
**Severity:** Medium physics correctness  
**Evidence:** PostProcessor labels its Von Mises expression as plane stress, while the solver accepts both plane stress and plane strain.  
**Impact:** For plane strain, the out-of-plane stress component is generally nonzero; using a plane-stress Von Mises expression can misreport equivalent stress.  
**Required action:** Implement the correct 3D stress invariant for plane strain (including `sigma_zz`) or clearly restrict/label the output. Add analytical stress-state tests.

## 5. Benchmark and research protocol redesign

The central research question should be split into measurable claims:

- **H1 — Accuracy/DOF:** At matched reference-relative QoI error, goal-aware refinement requires fewer DOFs than uniform and recovery refinement.
- **H2 — Accuracy/time:** At matched reference-relative QoI error, goal-aware refinement requires less wall-clock time.
- **H3 — Accuracy/memory:** At matched reference-relative QoI error, goal-aware refinement requires less peak memory.
- **H4 — Reliability:** The runtime never commits a mesh exceeding the declared DOF budget, and all unsuccessful terminations are reported as failures to meet the requested target rather than convergence.
- **H5 — Generality:** The observed advantage persists across a defined suite of geometries, load cases, material ratios and QoIs.

Required protocol:
1. Freeze and hash the input problem, code revision, dependency lock, machine and runtime configuration.
2. Use at least three reference levels; demonstrate reference adequacy below the strictest tested threshold, or report the threshold as inconclusive.
3. Include independent mesh families or a manufactured/exact solution where possible; a single fine mesh is not ground truth.
4. Compare at identical reference-relative QoI error thresholds, not each method's own stopping criterion.
5. Use repeated timing runs with warm-up; report medians, dispersion and all stage costs. Do not infer end-to-end speedup from isolated factorization speedup.
6. Report DOFs, elements, mesh quality, iterations, residuals, QoI, reference uncertainty, peak memory, total wall time, assembly time, solve time, indicator time and refinement time.
7. Report every failed target and budget-limited run. Do not exclude inconvenient runs.
8. Use paired runs and confidence intervals/bootstrapping where appropriate.
9. Keep the numerical reference solver and its adequacy checks independent of the strategy under test.
10. Make a benchmark result reproducible from a single documented command and archived artifacts.

## 6. Skill/framework integration plan

Use the recovered materials-simulation skill inventory as modular engineering practices, not as claims that the scripts are installed or executed.

| Capability family | GDEC integration point | Immediate purpose |
|---|---|---|
| numerical-stability | FEM solver and runtime acceptance checks | Conditioning, residuals, scaling and floating-point checks |
| linear-solvers | solver adapter | Direct/iterative solver selection with residual and convergence criteria |
| nonlinear-solvers | future physics solver interface | Future nonlinear material/contact problems; not needed for current linear benchmark |
| mesh-generation | geometry/discretization adapter | Mesh quality, boundary tagging, mesh-family validation |
| time-stepping | future transient solver interface | Defer until steady-state trustworthiness is established |
| simulation-validator | validation pipeline | Equilibrium, reactions, residuals, physical constraints and invariants |
| parameter-optimization | outer-loop design/parameter study | Calibration/optimization only after validation metrics are trustworthy |
| post-processing | QoI and result pipeline | Units, field recovery, stress invariants, uncertainty and export |
| performance-profiling | runtime telemetry | End-to-end profiles, allocation/memory and repeatability |
| simulation-failure-triage | diagnostics | Classify parse, model, mesh, solver, convergence and resource failures |
| fair-simulation-packager | benchmark artifact pipeline | Freeze source, environment, inputs, outputs and provenance |
| benchmark-and-mms-planner | scientific verification | Manufactured solutions and convergence-order tests |
| slurm-job-script-generator / hpc-runtime-doctor | future execution adapter | HPC only after a real remote backend exists |
| md-analysis-planner | optional materials adapter | Separate atomistic/materials workflow; not part of current FEM core |
| ontology explorer/mapper/validator | schema and units layer | Future material/physics metadata interoperability |
| skill-evaluator | engineering governance | Track manifest provenance, evaluation state and regression evidence |
| convergence-study | verification pipeline | Formal mesh/time refinement studies |

Previously recovered archive state remains incomplete: 12 versioned manifests, eight additional names, four unknown identities; archive contents and evaluations were not freshly inspected. Preserve that uncertainty.

## 7. Prioritized roadmap

### P0 — Trust and correctness (blocker before feature expansion)
- Reject unsupported `point_displacement` or implement it fully.
- Strict DSL validation: duplicate declarations/arguments, unknown keys, finite values, exact integer budgets.
- Convert all invalid input paths to structured diagnostics.
- Correct plane-strain equivalent stress.
- Validate load/boundary well-posedness and zero-load intent.
- Add tests for every defect and regression.

### P1 — Numerical verification
- Manufactured-solution tests for elasticity where practical.
- Patch tests: constant strain/stress, affine displacement reproduction.
- Equilibrium/reaction balance and symmetry checks.
- Mesh convergence and observed-order tests.
- Compare P1 behavior against beam theory only with assumptions and boundary effects stated.
- Add independent checks for adjoint QoI derivatives/sensitivity using finite differences.

### P2 — Honest goal-oriented control
- Rename the existing stopping criterion to successive QoI change.
- Introduce estimator/acceptance metadata: heuristic, residual estimator, certified bound.
- Implement a genuine DWR residual estimator only with element residuals, interior traction jumps and boundary residuals, plus dual interpolation/error treatment.
- Do not claim certified error until a mathematically justified bound is implemented and verified.

### P3 — Benchmark integrity
- Enforce reference adequacy.
- Separate H1/H2/H3 decisions.
- Repeat timings and quantify uncertainty.
- Add multiple benchmark geometries/load cases/QoIs.
- Persist machine, environment, commit SHA and full raw data.

### P4 — Architecture maturity
- Capability-based solver/backend interfaces.
- Unit-aware IR and explicit coordinate systems.
- Versioned IR migrations.
- Plugin-like physics formulations and mesh/solver adapters.
- Keep CPU backend as the reference implementation.

### P5 — Scale-up
Only after P0–P3 are sound:
- P2 elements and quadrilaterals.
- 3D elasticity.
- Iterative solvers/preconditioners.
- Nonlinear/transient physics.
- GPU and HPC backends, each with real hardware tests and correctness parity.

## 8. Acceptance gates

A release should not be described as research-validated until:
- All P0 regressions pass in CI.
- Numerical verification tests pass with published tolerances.
- Benchmark reference adequacy is established for every claimed threshold.
- Goal-aware advantage is reported separately for DOFs, time and memory.
- Results reproduce from a clean environment.
- Unsupported capabilities fail clearly and cannot be mistaken for implemented features.

## 9. Evidence boundary

This audit inspected repository metadata, README, project metadata, language/compiler/IR/runtime/FEM/benchmark modules, example input and selected tests through GitHub file retrieval. It did **not** clone the repository, execute code, install dependencies, run pytest, run benchmark scripts, inspect every repository file, inspect the full 24-skill archive, or independently verify the README's 42-test badge and numerical performance claims.

The audit branch is intended for review; no changes have been made to `main`.
