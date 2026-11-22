# GDEC — Antigravity Work-Package Prompts

Target repo: `delythassociates/GDEC`. Start from branch `research/phase-5.2.1b-expression-input-integrity` (tip `7cd9738`, 358 passed / 13 CUDA-skipped).

**North star ("Samsung of mechanical engineers"):** engineers can trust a GDEC number without re-checking it. Differentiator = *evidence + refusal*: every result carries provenance and a verified-accuracy statement, and GDEC refuses when it cannot back a claim. Reliability first, features second, hardware last.

**How to use:** paste the SHARED PREAMBLE, then ONE work package, per Antigravity run. Make sure the actual repo files are attached or the workspace is mounted (last time modules were rebuilt from specs because files weren't attached). Run in the order below; WP0 and WP1 can run in parallel.

| Order | WP | Why it matters |
|---|---|---|
| 1 | WP0 Repo integrity & front door | main is stale (README says 42 tests, CPU-only); zips and scratch committed |
| 1 | WP1 EIR hardening (adversarial) | 5.2.x was written fast with no independent review |
| 2 | WP2 V&V suite + CI matrix | trust = reproducible evidence; README says Windows-only, CI is Linux |
| 3 | WP3 Evidence & refusal engine | the core differentiator |
| 4 | WP4 Numerical contract (software-only) | links QoI tolerance to admissible execution; includes a kill-test |
| 5 | WP5 Heat-conduction physics | your research domain; proves GDEC is not elasticity-only |
| 6 | WP6 Certified-bound research | turns "DWR estimate" into something defensible, only if feasible |
| 7 | WP7 Longevity: docs, versioning, release | "lasts forever" |
| Later | Performance/GPU | only batched UQ; do not revisit hardware synthesis now |

---

## SHARED PREAMBLE (paste before every WP)

```
ROLE: You are a senior numerical-software engineer working on GDEC (Goal-Driven
Engineering Computation), repo delythassociates/GDEC. You work like a reviewer who
must be able to defend every claim to a hostile referee.

BRANCHING: Create a NEW branch from the tip of
research/phase-5.2.1b-expression-input-integrity named <wp-id>-<short-name>.
Never force-push, never rewrite history, never touch main. Small commits with
conventional messages.

READ FIRST (before any edit):
- docs/GDEC_ENGINEERING_STATUS.md  (status taxonomy PLANNED..INDEPENDENTLY VALIDATED)
- docs/RESEARCH_LIMITATIONS.md, docs/known_limitations.md
- research/phase5/PHASE_5_DECISION_REGISTER.md and PHASE_5_IMPLEMENTATION_ROADMAP.md
- research/phase5.1.3/* (latest closure reports)
- The source and tests for the area you are changing.

HARD RULES
1. Baseline: all 358 current tests keep passing; the only skips allowed are CUDA
   tests on hosts without a GPU. Never delete, weaken, or skip an existing test.
   Never loosen a numerical tolerance without a written ADR entry in
   docs/adr/ADR_REGISTER.md giving the numerical reason.
2. Claims discipline: you may upgrade a capability's status only by citing the exact
   test file/function that justifies it. Never use the words "certified",
   "guaranteed", or "proven" unless a bound is actually proven in the repo.
   Heuristics and asymptotic estimates must be labelled as such.
3. No silent fallbacks. If something cannot be done, raise a typed, source-located
   error. No broad `except`. No hidden CPU fallback for requested accelerators.
4. Determinism: seeded RNG, no wall-clock-dependent assertions, no reliance on dict
   or set ordering for numeric results or hashes.
5. Scope: do exactly the package below. Anything adjacent goes in "Deferred items",
   not into the diff.
6. Stop condition: if an acceptance gate fails, STOP and report the failure with
   evidence. Do not paper over it, and do not mark it done.

DELIVERABLES (same format as existing research/phase5.x folders), under
research/<wp-id>/ :
- <WP>_MASTER_REPORT.md   (what was done, why, what was NOT done)
- <WP>_ACCEPTANCE_MATRIX.md  (each gate -> PASS/FAIL -> evidence: command + output)
- <WP>_CHANGELOG.md
- <WP>_RISK_REGISTER.md  (include residual risks you could not close)
Finish with the full pytest output and the exact command used.
```

---

## WP0 — Repo integrity & front door

```
OBJECTIVE: Make main-facing repo state truthful, clean, and credible to a first-time
reader. Today main is v0.2.2: README badge says 42 tests, "CPU only", no mention of
Phase 5.x; install step says `cd fem-edit-benchmark`; doc links are
file:///f:/fem-edit-benchmark/... (broken for everyone else); binary zips
(GDEC_v0.2.2_PRIVATE_REVIEW.zip, materials-simulation-skills-main.zip) and a
scratch/ directory sit in the repo.

TASKS
1. Audit the repo root: list every file/dir that is not source, test, doc, example, or
   config. For each, propose keep / move to docs/archive / git-ignore. Do NOT delete
   history; remove from the working tree only with a justification table.
2. Rewrite README.md: truthful status (derive test count and Python versions from the
   real CI, not by hand), a short "What GDEC is / is not", a 10-minute quickstart that
   works from a clean clone on Linux, macOS, and Windows, correct relative doc links,
   and a link to the status register. No performance claim without a link to the
   result file that produced it.
3. Add: CHANGELOG.md (Keep-a-Changelog), CITATION.cff, SECURITY.md, CONTRIBUTING.md,
   CODE_OF_CONDUCT.md, issue/PR templates.
4. Version policy: reconcile pyproject version with the actual state (propose
   0.3.0-alpha), define how version appears in IR and result files.
5. Write a MERGE PLAN document: the ordered chain of research/* branches into main,
   with the exact PR sequence, what each PR contains, and conflict risks. Do not
   perform the merge.

ACCEPTANCE GATES
- Fresh clone + the README quickstart reproduces a run on a clean venv (show log).
- Every README link and badge resolves; a link-checker run is attached.
- No claim in README that is not backed by a file path in the repo.
- 358 tests still pass.

DO NOT: change any numerical code; rewrite history; delete archive material without
the justification table.
```

---

## WP1 — Adversarial hardening of the EIR / expression type system

```
OBJECTIVE: Independently attack the Phase 5.2.x engineering-IR (EIR) type system and
typed expression inference (commits 1636419 .. 7cd9738) and fix what breaks. Treat
the existing code as written by someone else and presumed buggy.

TASKS
1. Read the code under src/gdec for units, SI normalization, expression typing,
   canonical EIR hashing, and their tests. Write a short "assumptions list": every
   implicit assumption the code makes.
2. Add property-based tests (hypothesis) for: unit algebra (associativity,
   commutativity, identity, dimensional consistency), SI normalization round-trips,
   rational-exponent arithmetic (no float leakage), and expression inference.
3. Hash determinism: prove canonical EIR hashes are identical across (a) dict
   insertion order, (b) Python 3.10-3.13, (c) Windows vs Linux path/line-ending
   differences, (d) numerically-equal-but-differently-written inputs (1e3 vs 1000.0
   vs 1000). Define and test what MUST differ.
4. Fuzz: malformed, huge, deeply nested, NaN/inf, unicode-confusable, and
   adversarial-exponent inputs must produce typed errors, never crashes, hangs
   (>1 s), or silent coercions. Add a recursion/size limit with a test.
5. Immutability: show that no public EIR or type-environment object can be mutated
   after construction, including via aliasing of lists/dicts passed in.
6. Every bug found: failing test first, then fix, then a one-paragraph entry in
   the report (symptom, root cause, fix).

ACCEPTANCE GATES
- >= 1 property test per public function in the typing API.
- Hash-determinism test matrix passes in CI on >= 2 OSes (coordinate with WP2).
- Fuzz suite runs < 60 s in CI; 0 unhandled exceptions types.
- Report lists every defect found, or states plainly "found none" with the
  attack list attempted.

DO NOT: redesign the type system; add new language features.
```

---

## WP2 — Verification & validation suite as a product + CI matrix

```
OBJECTIVE: Turn GDEC's verification evidence into a reproducible, automated, versioned
suite so that "NUMERICALLY VERIFIED" in the status register is regenerated by CI,
not asserted by hand.

TASKS
1. CI matrix: Linux + Windows (+ macOS if cheap) x Python 3.10-3.13, with pinned
   dependency lockfile and a separate job that tests against latest dependencies
   (scikit-fem, numpy, scipy) to catch upstream drift. CUDA tests remain skipped
   on CI but must be import-safe.
2. Convergence-order tests: for the P1 elasticity solver, assert the observed
   convergence ORDER (not just that error shrinks) with a fitted slope and tolerance
   band, on manufactured solutions. Same for the adaptive loop: QoI error vs DOFs
   curve stored as a locked baseline with a regression threshold.
3. Reference-problem library: >= 8 problems with analytical or manufactured exact
   solutions (patch test, bending, Lame cylinder / plate with hole where applicable,
   singular corner for adaptivity). Each has an ID, source reference, expected value,
   tolerance, and rationale.
4. Independent cross-check: every solver output on the library is compared against
   scikit-fem and, where available, a second independent implementation. Log the
   max discrepancy.
5. Status-register traceability: generate a machine-readable
   status_register.json from test markers (e.g. @pytest.mark.capability("...")),
   and a CI check that fails if a capability is marked NUMERICALLY VERIFIED but has
   no passing marked test.
6. Coverage gate (branch coverage) with a floor equal to the current value that
   can only ratchet up. Mutation-test the core FEM and estimator modules
   (mutmut or cosmic-ray) and report the surviving mutants.

ACCEPTANCE GATES
- CI green on the full matrix; link to a run or attach logs.
- Status register is generated, and a deliberately broken capability makes CI fail
  (show the failing run).
- Mutation score reported per module with every survivor classified as
  equivalent / test gap; gaps get new tests.

DO NOT: relax tolerances to get green; change solver numerics.
```

---

## WP3 — Evidence graph & refusal engine (the differentiator)

```
PRECONDITION: Phase 5.2 was marked "await explicit approval". Before starting,
confirm in research/ that approval is recorded; if not, add a one-line decision record
to PHASE_5_DECISION_REGISTER.md stating the owner approved Phase 5.2 on today's date
and flag it for the owner to confirm in your report.

OBJECTIVE: Every GDEC result ships with a machine-checkable EVIDENCE RECORD, and GDEC
REFUSES to return an unqualified number when it cannot support one.

TASKS
1. Design (ADR first, then code): an evidence record containing: EIR hash, mesh
   hash, solver + settings, library versions, backend, DOFs, estimator type and its
   status label (heuristic / DWR-asymptotic / bound), the QoI value, the error
   estimate with its stated meaning, the effectivity evidence available for this
   problem class (or "none"), and a result hash chaining all of the above.
2. Refusal rules (explicit, versioned, each with a test): examples -- budget
   exhausted before the accuracy target; estimator not valid for this problem class;
   reference-adequacy unknown; QoI evaluated on a constrained boundary; DOF count
   below the minimum for the estimator's validity. A refusal is a first-class
   result with reasons, not an exception.
3. Verifier: a separate small module + CLI (`gdec verify <result.json>`) that
   recomputes the hashes and re-checks the refusal rules without running the solver,
   and re-runs the solve optionally to confirm the QoI within tolerance.
4. Tamper tests: modify any field in a saved result -> verify fails with a precise
   reason.
5. Integrate with the existing decision contract and evaluator (src/gdec/dse/*)
   without changing their tested behaviour.

ACCEPTANCE GATES
- Round-trip: run -> save -> verify passes; every tamper case fails correctly.
- >= 10 refusal rules, each with a positive and a negative test.
- The result JSON schema is exported and versioned.
- No result path can return a number without an evidence record (test by
  static check or an exhaustive entry-point test).

DO NOT: claim certified accuracy; add GPU work; change estimator math.
```

---

## WP4 — Numerical contract (software-only first)

```
OBJECTIVE: Implement a "numerical contract" checker: the engineer's QoI tolerance
(and reproducibility requirement) is decomposed into error sources, and GDEC rejects
any execution configuration whose estimated total error can violate it, even if that
configuration is faster. SOFTWARE ONLY. No FPGA/HLS/hardware work.

STEP 0 — KILL TEST (do this first, report before continuing)
On 3 reference problems from WP2, measure separately, as QoI error: (a) discretization
error (vs a high-resolution / Richardson reference), (b) linear-solver error (iterative
tolerance vs direct), (c) floating-point rounding error (FP64 vs a high-precision or
FP32-perturbed run). Tabulate magnitudes. If (c) is < 1e-6 of (a) in FP64 and FP32,
conclude that rounding is negligible in this regime, say so plainly, and restrict the
contract to sources (a)+(b) plus an FP32/FP16 admissibility check.

TASKS (after Step 0)
1. Contract schema: QoI tolerance, error-source budget split (declared or
   auto-allocated), reproducibility class (bitwise / tolerance-level).
2. Allocator: cheapest (mesh refinement level, solver tolerance, precision) that
   satisfies the budget using the existing estimator output; document the
   assumptions and the estimator status label for each error source.
3. Admissibility: reject configurations that violate the contract; the rejection is
   a WP3 refusal with reasons.
4. Tests: a configuration that is faster but violates the contract must be rejected;
   a slower compliant one must be chosen.
5. Literature note (max 2 pages): relation to running-error-bound and rounding-error
   analysis work in FEM kernels, and verified-HLS work. State what you READ versus only
   saw titles for. Do not claim novelty you have not checked.

ACCEPTANCE GATES
- Step 0 table delivered with a clear go/no-go statement.
- Contract allocator beats a naive fixed-config baseline on cost at equal
  verified QoI error on >= 2 problems, or the report says it does not.

DO NOT: write hardware code; assert novelty; extend to hardware planning.
```

---

## WP5 — Steady heat-conduction physics (second physics, via a physics interface)

```
OBJECTIVE: Prove GDEC is a framework, not an elasticity script: add steady-state
heat conduction as a second physics through a clean physics interface, reusing the
adjoint, estimator, adaptive loop, DOF-budget runtime, and evidence/refusal engine.

TASKS
1. ADR: a physics plugin interface (weak form, BC types, QoI types, estimator
   hooks). Refactor elasticity behind it with ZERO behaviour change (all 358 tests
   pass unmodified).
2. Heat conduction: 2D steady conduction, isotropic k, Dirichlet / Neumann (flux) /
   Robin (convection) boundaries, volumetric source. DSL keywords + typed IR + units
   (W/m-K, W/m2, K).
3. QoIs: average temperature over a boundary/region, boundary heat flow (computed
   consistently, not by naive gradient differencing), point temperature (only if
   the interpolation semantics are implemented and tested).
4. Verification: 1D slab (exact linear profile), composite slab, fin with convection
   (analytical), manufactured solution, global energy balance to machine precision.
   Independent cross-check vs scikit-fem.
5. Adjoint and DWR for the heat QoIs; effectivity tests like the elasticity ones.
   If the estimator cannot be validated, label it a heuristic. Do not claim DWR.

ACCEPTANCE GATES
- Elasticity regression: byte-identical results on the existing reference runs.
- >= 5 analytical/manufactured heat problems pass with stated tolerances.
- Heat goal-driven run produces an evidence record (WP3 format).

DO NOT: add transient, nonlinear, 3D, or coupling; touch hardware backends.
```

---

## WP6 — Certified-bound feasibility study (research package)

```
OBJECTIVE: Decide, with evidence, whether GDEC can offer a PROVEN upper bound on the
QoI error for a restricted problem class. Current state: DWR is an asymptotic
estimate (effectivity 0.51 -> 0.91), explicitly not a bound. This package produces a
feasibility verdict and, only if feasible, a prototype.

TASKS
1. Literature survey (primary sources; list exactly which you read in full): flux
   equilibration (Prager-Synge) energy-norm bounds, complementary-energy goal-oriented
   bounds, hybrid/equilibrated residual methods, guaranteed goal-oriented error
   estimates. For each: assumptions, constants required, applicability to P1
   triangles in 2D elasticity and heat conduction.
2. Pick the single most feasible method for a restricted class (homogeneous isotropic,
   polygonal domain, specified BCs). State the exact theorem and every constant.
3. Prototype on a problem with a known exact solution. Report effectivity index
   (bound / true error): it MUST be >= 1 on every test or the method is wrong.
   Include adversarial meshes (anisotropic, graded).
4. Verdict document: FEASIBLE-NOW / FEASIBLE-WITH-WORK / NOT-FEASIBLE, with what
   would be needed and an honest estimate of effort.

ACCEPTANCE GATES
- Bound >= true error on 100% of test cases (any violation => stop and report).
- No "certified" label in code or docs unless the theorem's assumptions are
  machine-checked at runtime for the given problem; otherwise label "bound under
  stated assumptions".

DO NOT: integrate into the production estimator path; change existing labels.
```

---

## WP7 — Longevity: docs, versioning, release

```
OBJECTIVE: Make GDEC something that still works, and can still be understood, in 10
years.

TASKS
1. Docs site (mkdocs-material): getting started, concepts (goal-driven workflow,
   evidence, refusal), DSL reference generated from the grammar, IR schema reference
   generated from the Pydantic models, verification report generated from CI, and a
   "known limitations" page that cannot drift (generated from the status register).
2. Consolidate docs/: ~45 audit/report files are mixed with living docs. Move
   historical reports to docs/archive with an index; keep one living page per topic.
3. Compatibility policy: semantic versioning; IR schema versioning with an automatic
   migration path (v0.1 -> current) and tests that old saved IR/result files still
   load or fail with a clear migration message. Deprecation policy (>= 1 minor
   version of warning).
4. Release pipeline: build sdist+wheel, install into a clean venv and run the smoke
   suite, tag, attach SBOM, publish to TestPyPI on tags. Document a Zenodo DOI
   release.
5. Reproducibility package: `gdec repro <result.json>` prints the exact commands and
   environment to reproduce a recorded run.

ACCEPTANCE GATES
- Docs build with 0 warnings; every code sample in docs is executed in CI.
- An old (v0.1) IR file from results/ still loads or fails with a migration message.
- Wheel installs and passes the smoke suite on a clean environment.

DO NOT: rename public APIs; change numerics.
```

---

## Parking lot (explicitly NOT now)
- Custom GPU/ISA or FPGA/HLS work. Revisit only after WP3-WP4 give a measured, evidence-backed reason (a specific kernel that dominates runtime).
- Adjoint-weighted condensation (idea for the AHCE/EAIMC codebase, not GDEC).
- 3D elements, P2, nonlinear, transient: after WP5, one at a time.
