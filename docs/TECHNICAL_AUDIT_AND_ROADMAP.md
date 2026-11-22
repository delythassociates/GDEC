# GDEC v0.2.2 — Targeted Technical Audit and Research Roadmap

**Audit date:** 2026-11-21  
**Reviewed ref:** `main` (latest observed commit `05d9a70b2bafc722b6098dd5d164cedf3f8415ea`)  
**Scope:** Read-only inspection of README, project metadata, language/compiler, IR, planner, FEM solver, estimators, adaptivity, runtime/controller, benchmark/evaluator, selected tests, and documentation.  
**Execution status:** No repository code was executed in this audit. No test, benchmark, fuzz, or numerical verification result is claimed.

## Executive assessment

GDEC v0.2.2 is a real, focused 2D linear-elasticity FEM prototype with a declarative front end, typed Pydantic IR, sparse direct solve, adjoint calculation, adaptive mesh refinement, budget checks, CLI/Studio, and comparative benchmark machinery.

The strongest research direction is the compiler-to-runtime pipeline that translates an engineering QoI and resource constraints into a solver/adaptivity plan. The implementation is materially more concrete than a concept-only framework.

However, several correctness and evidence gaps must be resolved before GDEC can be described as a reliable goal-driven engineering computation platform. The highest-risk issues found in source inspection are:

1. `point_displacement` is accepted by the IR/compiler but the runtime QoI path always assembles a boundary-average displacement functional. This is a semantic correctness defect.
2. The convergence target is successive QoI change, not a certified error estimate or reference-relative accuracy. Two consecutive small changes reduce false stopping risk but do not certify engineering accuracy.
3. Benchmark hypothesis support is determined from mean DOF advantage only; wall-clock advantage is calculated but not included in the support decision.
4. Benchmark time-to-target is accumulated from iteration durations, while mesh refinement occurs outside the measured iteration interval. The reported equal-accuracy time comparison therefore needs reconciliation with actual wall time.
5. Cost-model descriptions and implementation parameters do not agree. The runtime also has multiple different per-element cost assumptions.
6. Semantic validation is permissive in several places: duplicate declarations/named arguments can silently overwrite earlier values; unknown arguments are not consistently rejected; missing traction components default to zero; finite numeric values and integer-valued budgets need explicit validation.
7. The current architecture is CPU-only and supports one narrow physics/element family. GPU/HPC backends and broad multiphysics support are future work, not current capabilities.

## Repository facts observed

- Repository: `delythassociates/GDEC`, private, default branch `main`.
- README and package metadata identify version `0.2.2`.
- `pyproject.toml` and `requirements.txt` both declare `tabulate`; the dependency discrepancy recorded in an older audit is no longer present in the inspected current metadata.
- README reports 42 tests passed. This audit did not execute them or independently verify the badge.
- README describes 2D static linear elasticity with P1 triangular elements, sparse LU, adjoint QoI analysis, ZZ recovery, an adjoint-informed heuristic, Dörfler marking, red-green refinement, CLI, and Streamlit Studio.
- README explicitly says the current runtime is CPU-only; GPU hardware detection is informational and accelerator requests are rejected.
- The documented goal-aware indicator is explicitly classified as a heuristic, not a certified DWR estimator. Preserve this distinction.

## Confirmed source-level findings

### P0 — QoI semantics mismatch

**Evidence:** `src/gdec/language/ir.py` permits `ObjectiveIR.kind` to be either `average_displacement` or `point_displacement`. `src/gdec/language/semantic.py` accepts both. However, `GDECRuntime.execute` passes only boundary and component to the solver, and `LinearElasticitySolver.assemble_qoi_adjoint_vector` constructs the normalized boundary integral functional. The objective kind is not used to change the functional.

**Impact:** A source file declaring `point_displacement` can be compiled and executed with a different mathematical objective than requested.

**Required action:** Until a real point-evaluation functional with explicit point coordinates and a defined interpolation/evaluation policy is implemented, reject `point_displacement` at compile time. Add regression tests proving the compiler rejects unsupported QoIs and that every accepted QoI has matching primal evaluation and adjoint load assembly.

### P0 — Convergence is not an error certificate

**Evidence:** `RuntimeController.calculate_successive_change` calculates relative change between consecutive discrete QoI values. The controller requires two consecutive changes below tolerance. The planner and CLI call this target “accuracy”, while the benchmark separately computes error relative to a high-resolution numerical reference.

**Impact:** A small successive change is evidence of stabilization under the chosen refinement path, not a certified bound on the true QoI error. It can be misleading under non-monotone convergence, stagnation, model error, or an inadequate reference.

**Required action:** Make the contract explicit in language, IR, CLI and reports: call this a *successive QoI stabilization tolerance*. Keep reference-relative error and estimator-derived quantities distinct. Future error targets should identify the estimator/reference basis, norm, confidence/assumptions and certification status. Do not label a heuristic as a guarantee.

### P0 — Benchmark hypothesis decision is incomplete

**Evidence:** `BenchmarkRunner._evaluate_hypothesis` computes both DOF and time ratios, but sets `supported = mean_dof_adv > 1.05`. It does not require or consider a wall-clock improvement, despite the stated hypothesis being about lower computational cost. The comparison loop also aggregates only thresholds where both goal-aware and uniform achieved the target; recovery is not part of the support predicate.

**Impact:** The report can say the central hypothesis is supported when GDEC uses fewer DOFs but takes longer, or when it has not been compared successfully against the recovery baseline. This is a narrower claim than the report wording.

**Required action:** Define separate claims: (a) DOF efficiency, (b) wall-clock efficiency, (c) memory efficiency, and (d) combined cost advantage. Report each threshold and baseline separately. A combined claim must specify a pre-registered decision rule and must not be supported by DOFs alone. Include recovery in the declared baseline set or explicitly limit the claim to uniform comparison.

### P0 — Equal-accuracy timing excludes refinement cost

**Evidence:** `BenchmarkRunner.run_all` builds cumulative time by summing `IterationRecord.total_iteration_time_sec`. In `GDECRuntime.execute`, iteration timing is finalized before the next mesh refinement is performed. The refinement duration is stored separately and associated with a later record, but is not added to that iteration's total duration. The full trace wall time is measured around the complete runtime.

**Impact:** Time-to-target comparisons may omit mesh-refinement work and cannot be assumed equivalent to wall-clock time. This can distort claimed speedups.

**Required action:** Define one consistent timing accounting model. Measure cumulative elapsed time at each recorded QoI observation using a monotonic clock, including all mesh creation/refinement and overhead between observations. Retain stage timings as a decomposition whose sum reconciles to wall time within a documented tolerance. Add tests for timing accounting with a deterministic fake clock.

### P1 — Cost-model documentation and implementation disagree

**Evidence:** `docs/cost_model.md` describes an empirical factor around 1.8–2.4 DOFs per marked element. `src/gdec/core/cost_model.py` currently uses `base_alpha = 7.5`, `density_beta = 3.0`, and clamps the estimated DOF rate to 3.5–9.0 per marked element. `src/gdec/fem/adaptivity.py` separately uses 6 DOFs per marked element for affordability, while the estimator returns 4 in its indicator metadata.

**Impact:** The planner, marking logic, cost model, estimator metadata and documentation do not share one cost contract. Predictions are empirical, mesh-topology-dependent and can be biased.

**Required action:** Centralize the predicted-cost interface. Use actual candidate-mesh DOFs as the final safety gate. Record prediction residuals by mesh density, marking topology, strategy and mesh family. Calibrate on training cases and evaluate on held-out cases. Document uncertainty and failure rates; never treat the predictor as the hard safety mechanism.

### P1 — DSL semantic validation is not strict enough

**Evidence:** `src/gdec/language/parser.py` stores named arguments in a dictionary, so repeated names overwrite earlier values. `SemanticAnalyzer` generally selects the last repeated top-level declaration. Several extractors do not reject unknown named arguments. Traction components default to zero if omitted. Numeric literals are converted to floats, but explicit finite-value validation is not visible in the semantic checks. Budget values are converted with `int()`, which can truncate non-integral values.

**Impact:** Invalid or ambiguous engineering specifications can compile successfully or silently change meaning.

**Required action:** Introduce strict schemas per declaration/function. Reject duplicate top-level declarations unless a construct is explicitly repeatable (e.g. loads/BCs); reject duplicate named arguments, unknown arguments, missing required arguments, non-finite numbers and non-integral integer fields. Add adversarial parser/compiler tests and preserve precise source locations.

### P1 — Planner rationale contains assumptions not derived from input

**Evidence:** `ExecutionPlanner.create_plan` always describes the plane-stress assumption as selected for a thin plate, even when the IR specifies plane strain. The initial mesh is chosen by a simple aspect-ratio formula with fixed `ny=5`, rather than a validated resolution/error model.

**Impact:** Explanations can be factually wrong, and initial mesh selection is a heuristic rather than a defensible accuracy-aware decision.

**Required action:** Generate rationales from actual IR values. Label mesh sizing as a heuristic. Add geometric aspect-ratio limits, minimum/maximum grid safeguards, and a cost/conditioning-aware initialization policy.

### P1 — Runtime/backend contract needs one source of truth

**Evidence:** `BackendIR` accepts `cpu`, `cuda`, `hip`, and `sycl`, while the semantic analyzer rejects every non-CPU device and the README describes CPU-only execution. Planner/runtime currently instantiate the CPU FEM solver directly.

**Impact:** The IR schema implies backend values that are not executable through the public compiler/runtime path. Direct IR construction can bypass semantic validation.

**Required action:** Represent backend capability as an explicit registry contract. Validate every IR entering the planner, not only DSL-compiled IR. Return a precise unsupported-backend diagnostic. Add a backend conformance interface before adding GPU implementations. Do not silently fall back to CPU.

### P2 — Documentation and release hygiene

**Evidence:** README links to local `file:///f:/...` documentation paths. The inspected repository did not contain `docs/architecture.md` or `docs/benchmark_methodology.md` at the referenced paths. Several source/doc messages still refer to v0.1 or v0.2.1 despite package version 0.2.2.

**Required action:** Replace local file links with repository-relative links, reconcile missing documents, centralize version constants, and add a documentation-link check to CI.

## Framework integration plan

Apply the engineering and software-assurance frameworks selectively, as follows:

| Framework / skill family | GDEC application | Immediate output |
|---|---|---|
| Spec-driven workflow / architecture ADRs | Define stable requirements, acceptance criteria and decision records | Versioned requirements and ADRs |
| Compiler development / PLT | Grammar, AST, type/semantic checking, lowering, IR compatibility | Strict compiler contract and diagnostics |
| TDD / senior QA | Regression-first implementation and boundary-case coverage | Tests for each P0/P1 defect |
| Computational Physics / FEM | Weak form, element formulation, estimator assumptions, mesh convergence | Verified analytical/MMS cases |
| Numerical stability / linear solvers / nonlinear solvers | Conditioning, residuals, solver tolerances, scaling and failure behavior | Solver verification suite |
| Simulation validator / convergence study / MMS planner | Independent numerical verification and convergence evidence | Manufactured-solution and mesh-study reports |
| Formal Methods (Lean/Coq/Z3) | Invariants for budget transactions, IR constraints and state transitions | Small formalized contracts where tractable |
| Software fuzzing / vulnerability discovery | Parser, serializer, malformed IR and CLI input hardening | Authorized fuzz/property-based test suite |
| Performance profiling | Stage timing reconciliation, memory, scaling and statistically sound comparisons | Reproducible profiling protocol |
| Parameter optimization | Calibrate planner/cost-model parameters on training problems only | Held-out calibration report |
| Fair simulation packaging | Capture source, environment, solver settings, seeds, raw outputs and hashes | Reproducible benchmark artifact |
| Ontology / semantic modeling | Units, physical quantities, coordinate frames and material/BC semantics | Typed engineering quantity model |
| HPC runtime / Slurm / GPU skills | Future backend adapters after CPU semantics and validation are stable | Backend contract; no premature GPU claim |

The previously recovered materials-simulation skill inventory remains incomplete: 12 versioned manifests and eight additional names were recovered; four identities and the original archive contents remain unavailable. This audit does not claim those missing skills or archive test suites were inspected.

## Prioritized implementation sequence

### Milestone 0 — Establish an auditable baseline
- Reconcile the exact source tree, release ref, package metadata and documentation.
- Reproduce the README's 42-test claim in a clean environment.
- Capture environment lock/versions and raw logs.
- Establish baseline outputs for the canonical cantilever case.

**Exit criteria:** reproducible baseline with source commit, environment, test logs and benchmark artifacts.

### Milestone 1 — Close semantic correctness defects
- Reject unsupported `point_displacement`.
- Reject duplicate/unknown/missing DSL arguments and duplicate non-repeatable declarations.
- Enforce finite numeric values and integer budgets.
- Validate direct IR entry points and backend capability.

**Exit criteria:** regression tests demonstrate that invalid/ambiguous specifications fail before execution and accepted specifications preserve their declared meaning.

### Milestone 2 — Numerical verification
- Analytical patch tests and manufactured solutions for 2D elasticity.
- Verify stiffness symmetry, rigid-body mode handling, reactions and global force/moment balance.
- Verify primal and adjoint systems independently.
- Mesh-convergence studies across geometry, material, loading and boundary-condition cases.
- Compare ZZ/goal heuristics against observed QoI error reduction without claiming certification.

**Exit criteria:** documented convergence rates, tolerances, residuals and failure cases.

### Milestone 3 — Runtime and benchmark integrity
- Reconcile stage timing with elapsed wall time.
- Rework hypothesis evaluation into explicit DOF/time/memory claims.
- Separate stabilization from reference-relative error.
- Validate hard DOF budget invariants for all strategies, including adversarial under-prediction.

**Exit criteria:** equal-accuracy comparisons can be independently reproduced and all reported metrics reconcile.

### Milestone 4 — Goal-driven planner
- Use verified QoI/error signals, predicted cost distributions and resource constraints.
- Make planner decisions inspectable and deterministic.
- Track model uncertainty and abstain when confidence is inadequate.
- Add multiple benchmark geometries and QoIs before generalizing claims.

**Exit criteria:** held-out cases show a repeatable advantage, with no hidden degradation in accuracy or reliability.

### Milestone 5 — Expand physics and hardware
Only after the previous milestones:
- Higher-order elements and additional boundary conditions.
- 3D elasticity and other physics modules.
- Iterative/preconditioned solvers.
- GPU and HPC adapters with backend conformance tests.
- Materials-specific simulation integrations.

## Release policy

For each capability, track these statuses separately:

- `planned`
- `framework_adopted`
- `implemented`
- `executed`
- `tested`
- `independently_verified`

Do not promote a capability to a stronger status without corresponding artifacts. A passing unit test is not independent numerical validation; a converged solve is not proof of model validity; a benchmark against a numerical reference is not an exact-solution proof.

## Bottom line

GDEC v0.2.2 is a credible early FEM/compiler research prototype with a potentially valuable goal-oriented adaptive computation idea. The next high-value work is not adding more domains, GPU claims or skills. It is closing the QoI semantic defect, hardening the DSL/IR contract, making convergence and benchmark claims scientifically precise, and independently verifying the numerical core.

**The project should earn its generality through verified vertical slices, not declare it in advance.**
