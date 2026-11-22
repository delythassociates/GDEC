# GDEC Architecture Decision Record Register

**Status:** Proposed baseline for maintainer review  
**Applies to:** Language, compiler, canonical IR, execution and verification architecture  
**Rule:** An ADR marked PROPOSED is not an accepted project-wide decision until explicitly ratified by maintainers.

## ADR-001 — Retain native declarative .gdc language

**Status:** PROPOSED — adopt  
**Decision:** Keep .gdc as a first-class native declarative language. Python, CAD, visual and reviewed natural-language interfaces may be added as frontends, but must lower to the same canonical semantic representation.  
**Rationale:** Preserves GDEC's language identity while allowing integrations.  
**Consequences:** The grammar, semantics and versioning policy become controlled public contracts.  
**Rejected alternative:** Replace .gdc with Python as the only authoring interface.

## ADR-002 — Freeze current syntax as Language Profile 0.1

**Status:** PROPOSED — adopt  
**Decision:** Document the existing Lark grammar and semantic behaviour as a compatibility profile before adding new syntax.  
**Rationale:** Current documentation does not exactly match the parser. Expanding syntax before resolving that gap would make compatibility harder.  
**Consequences:** Existing parser and AST remain the baseline; new constructs require a versioned change proposal and conformance tests.

## ADR-003 — Keep syntax AST distinct from engineering semantics

**Status:** PROPOSED — adopt  
**Decision:** AST represents source structure and locations. It must not become a solver-facing engineering model.  
**Rationale:** Multiple frontends need a common semantic target.  
**Consequences:** Introduce explicit semantic analysis and lowering into the canonical EIR.

## ADR-004 — Introduce a canonical, layered Engineering IR

**Status:** PROPOSED — adopt  
**Decision:** Define separate layers for intent, physical model, mathematical/variational formulation, discretisation, execution policy and verification obligations.  
**Rationale:** Current ProblemIR is a useful elasticity-specific record but cannot serve as the general semantic contract.  
**Consequences:** Existing ProblemIR remains supported through a legacy adapter. The canonical EIR receives its own schema version and validation rules.  
**Rejected alternative:** Expand ProblemIR in place into a universal schema.

## ADR-005 — Dimensional and physical types are compile-time semantics

**Status:** PROPOSED — adopt  
**Decision:** Quantities carry dimensions and unit metadata. The compiler checks dimensions and supported physical constraints before numerical execution.  
**Rationale:** Field descriptions and unit strings are not enforceable types.  
**Consequences:** Define dimension algebra, unit conversions, quantity kinds, tensor shapes, frames and domain associations. Do not silently reinterpret existing bare numeric fields.

## ADR-006 — Separate physical model from numerical lowering

**Status:** PROPOSED — adopt  
**Decision:** Governing equations and variational forms are represented independently of mesh, matrix and backend implementation.  
**Rationale:** Enables consistent derivation of primal, adjoint, residual, QoI and estimator obligations.  
**Consequences:** Solver-specific matrices and kernels are execution artifacts, not canonical engineering semantics.

## ADR-007 — Solver and planner are outside the trusted verification boundary

**Status:** PROPOSED — adopt  
**Decision:** Solver output and planner decisions are claims to be checked, not authoritative proof. A separate checker evaluates explicitly specified obligations.  
**Rationale:** A solver must not certify itself.  
**Consequences:** Certificate formats, checker identity, assumptions, provenance and failure states require explicit specification. Caller-supplied verified flags are insufficient.

## ADR-008 — Keep estimates distinct from guaranteed bounds

**Status:** PROPOSED — adopt  
**Decision:** Algebraic residuals, successive QoI changes, recovery estimates, DWR indicators, guaranteed mathematical bounds, physical uncertainty and model-form uncertainty remain separate evidence categories.  
**Rationale:** They answer different questions and have different mathematical guarantees.  
**Consequences:** No estimate may be relabelled as a certified bound by a threshold or status string.

## ADR-009 — Preserve existing elasticity implementation

**Status:** PROPOSED — adopt  
**Decision:** Keep the current elasticity parser-to-runtime path operational while the canonical IR is introduced.  
**Rationale:** Protects existing work and provides a real compatibility regression case.  
**Consequences:** Introduce an explicit adapter and dual-path parity tests before migration of the runtime.

## ADR-010 — Steady heat conduction as first certification candidate

**Status:** PROPOSED — conditional  
**Decision:** Evaluate a restricted steady linear heat-conduction problem as the first certified vertical slice; do not start implementation until the EIR and checker contracts are reviewed.  
**Rationale:** Scalar diffusion offers a tractable path to equilibrated-flux error bounds.  
**Consequences:** Compare proof obligations, implementation cost and reuse against elasticity. Existing elasticity remains the compatibility and second-domain target.  
**Open condition:** A mathematical feasibility note must state regularity, coercivity, boundary and data assumptions.

## ADR-011 — CPU is first-class; accelerator support is capability-specific

**Status:** PROPOSED — adopt  
**Decision:** CPU execution remains a supported baseline. CUDA/HIP/SYCL capabilities are advertised only for operations actually integrated and tested in the normal execution path.  
**Rationale:** Backend presence or device detection does not establish end-to-end acceleration.  
**Consequences:** Distinguish isolated kernels, integrated solver paths and validated performance claims.

## ADR-012 — Defer custom compiler infrastructure until measured need

**Status:** PROPOSED — adopt  
**Decision:** Do not immediately build a custom GPU compiler, instruction set or adopt MLIR as a prerequisite.  
**Rationale:** Current language and semantic contracts are not stable yet.  
**Consequences:** Reconsider compiler infrastructure only when a measured workload or lowering requirement justifies it.

## ADR-013 — DSE must consume provenance-bound evidence

**Status:** PROPOSED — adopt  
**Decision:** DSE may make conditional decision recommendations only from evidence whose eligibility, model, domain, metric semantics and provenance are validated. A future certificate checker result is distinct from caller-attested evidence.  
**Rationale:** Evidence eligibility is necessary but does not itself independently prove the underlying engineering claim.  
**Consequences:** Keep the current evaluator scoped and do not describe it as a fully closed-loop computation-sufficiency engine.

## ADR-014 — Public claims must track evidence level

**Status:** PROPOSED — adopt  
**Decision:** Every capability and benchmark claim must be labelled as implemented, tested, CI-verified, independently reproduced, proposed or not implemented.  
**Rationale:** Trust depends on precise, falsifiable claims.  
**Consequences:** README, papers and demos must not imply general GPU execution, certified DWR bounds, physical validation or broad multiphysics support without evidence.

## ADR-015 — Version schemas independently from package releases

**Status:** PROPOSED — adopt  
**Decision:** Language profile, AST contract, EIR schema, certificate schema and package version each have independent version identifiers.  
**Rationale:** Software release version does not identify the semantics of serialized engineering artifacts.  
**Consequences:** Current gdec_ir_v0.1 remains unchanged; proposed EIR draft 0.1.0 receives a distinct namespace.

## ADR-016 — Refusal and incompleteness are first-class outcomes

**Status:** PROPOSED — adopt  
**Decision:** Compiler, planner and checker must report unsupported, ambiguous, inapplicable or insufficiently evidenced requests explicitly.  
**Rationale:** Silent fallback or unsupported certainty is unsafe.  
**Consequences:** Result types include explicit refusal and incomplete states with reasons and next actions.
