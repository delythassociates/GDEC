# Migration Plan — Existing ProblemIR to Canonical Engineering IR

**Status:** Proposed, compatibility-first  
**Baseline:** Phase 5.1.3 commit d532cae8a16d5c2c2465d73175efd004d295aee9  
**Constraint:** Preserve current working language, elasticity solver, runtime, CLI, tests and historical IR artifacts.

## 1. Objective

Introduce a canonical Engineering IR without breaking existing .gdc programs or changing the meaning of gdec_ir_v0.1 artifacts.

The migration is additive. No in-place reinterpretation of current numeric fields, no destructive schema rewrite and no replacement of the current elasticity runtime are permitted in the first stages.

## 2. Baseline components to preserve

- src/gdec/language/grammar.lark
- src/gdec/language/ast.py
- src/gdec/language/parser.py
- src/gdec/language/semantic.py
- src/gdec/language/ir.py
- src/gdec/compiler/
- src/gdec/core/runtime.py
- existing elasticity solver and mesh/refinement implementation
- current CLI and Studio workflows
- existing examples and test fixtures
- historical gdec_ir_v0.1 JSON documents

The current ProblemIR remains the legacy compatibility contract until a successor is implemented and accepted.

## 3. Migration stages

### Stage 0 — Freeze and inventory

1. Record the exact baseline commit and representative .gdc source files.
2. Capture current parser AST snapshots, ProblemIR JSON snapshots, diagnostics and numerical outputs for regression cases.
3. Identify all consumers of ProblemIR, including CLI, runtime, tests, Studio and benchmarks.
4. Identify any undocumented assumptions in unit conventions, coordinate orientation, boundary naming and solver defaults.

**Exit gate:** a reproducible baseline inventory exists; no code is changed.

### Stage 1 — Ratify language profile and EIR semantics

1. Review and ratify Language Profile 0.1.
2. Review and ratify Canonical Engineering IR Draft 0.1.
3. Resolve open questions concerning units, coordinate frames, field spaces, variational forms and schema serialization.
4. Record decisions in the ADR register.

**Exit gate:** maintainers approve the semantic contract before implementation begins.

### Stage 2 — Implement foundational type primitives

Create a small, independently tested type subsystem for:

- seven-base-dimension vectors;
- rational exponent arithmetic;
- unit definitions and conversions;
- absolute versus differential temperature;
- scalar, vector and tensor shape metadata;
- coordinate-frame references;
- domain and field associations.

The type subsystem MUST be independent of the FEM solver and MUST NOT silently infer units from variable names.

**Exit gate:** dimensional algebra, conversion and rejection tests pass independently.

### Stage 3 — Implement EIR schema and validator

1. Introduce a new EIR package and a distinct schema namespace.
2. Define stable IDs and typed references.
3. Validate dimensions, units, shapes, frames, domains and schema version.
4. Define deterministic serialization and canonical hashing.
5. Keep source maps as metadata.
6. Reject unknown or unsupported semantic constructs rather than silently discarding them.

**Exit gate:** EIR round-trip and invalid-reference/type tests pass.

### Stage 4 — Add explicit legacy adapter

Implement a one-way adapter:

~~~text
Legacy .gdc
    |
    v
Existing parser and SemanticAnalyzer
    |
    v
ProblemIR (gdec_ir_v0.1)
    |
    v
LegacyElasticityToEIR adapter
    |
    v
Canonical EIR
~~~

Rules:

- The adapter MUST be explicit and versioned.
- It MUST preserve all current geometry, material, boundary, load, objective, accuracy, budget and adaptivity semantics.
- It MUST attach unit metadata only where current field conventions are unambiguous.
- It MUST NOT invent source unit annotations or claim that historical source values were dimensionally checked.
- It MUST record assumptions introduced by the adapter.
- It MUST fail if a legacy value cannot be mapped without guessing.

**Exit gate:** every supported legacy fixture maps deterministically; unsupported cases fail with actionable diagnostics.

### Stage 5 — Dual-path parity

For each baseline problem:

A. Compile through the existing route and execute the current runtime.

B. Compile through the existing frontend, lower to EIR, and execute through a compatibility bridge that preserves the current solver.

Compare:

- parsed problem identity;
- geometry and material parameters;
- boundary and load semantics;
- QoI definition;
- budget and adaptivity settings;
- numerical result;
- solver diagnostics;
- refinement history;
- stopping reason.

Numerical equivalence tolerances MUST be specified per quantity and solver. Exact JSON equality is not expected when schema structures differ.

**Exit gate:** no unexplained semantic or numerical divergence. The legacy route remains available.

### Stage 6 — Add second physics module

Only after EIR compatibility is established, implement the restricted steady heat-conduction model using EIR-native entities.

Do not make heat syntax a special case in the legacy elasticity ProblemIR.

**Exit gate:** heat model passes dimensional, physical, numerical and independent reference tests.

### Stage 7 — Verification/certificate integration

Specify certificate and checker contracts separately. The solver emits proposed evidence; a separate checker evaluates the claims.

**Exit gate:** tampered, incomplete, mismatched or inapplicable certificates are rejected; valid certificates are reproducibly checked.

### Stage 8 — Controlled runtime migration

Only after the new path has parity and independent validation:

1. Allow the CLI to select the canonical path for supported models.
2. Preserve legacy behavior for existing models.
3. Add explicit deprecation policy only after users have a migration path.
4. Keep old serialized artifacts readable for the documented compatibility period.

**Exit gate:** no legacy use case is removed without a tested replacement and migration documentation.

## 4. Non-goals for this migration

- Rewriting the Lark parser from scratch.
- Replacing .gdc with Python.
- Replacing the elasticity solver.
- Adding a GPU compiler or custom ISA.
- Adopting MLIR before a measured need exists.
- Implementing every engineering physics domain.
- Treating DWR indicators or successive QoI changes as guaranteed bounds.
- Claiming physical validation from comparison with another numerical code alone.

## 5. Required engineering controls

- Each stage uses a separate branch and reviewable commits.
- No migration branch modifies main directly.
- Existing untracked developer files must be preserved.
- Tests for the old path remain mandatory.
- New EIR tests must not depend on the elasticity runtime.
- No hidden unit assumptions or implicit backend fallback.
- Every unsupported conversion returns a structured error.
- Changes to schema semantics require an ADR and migration note.

## 6. Immediate next implementation issue

The first code task after specification review should be a standalone dimension/unit type package and its tests, not a new solver.

Suggested package boundary:

~~~text
src/gdec/types/
    dimensions.py
    units.py
    quantities.py
    shapes.py
    frames.py
    errors.py

tests/types/
    test_dimension_algebra.py
    test_unit_conversion.py
    test_quantity_typing.py
    test_shape_and_frame_types.py
~~~

This is a proposed layout. Do not create the package until the type-system design is ratified.
