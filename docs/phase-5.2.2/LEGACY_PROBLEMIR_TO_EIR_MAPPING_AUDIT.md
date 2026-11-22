# Phase 5.2.2A — Legacy ProblemIR to Canonical EIR Mapping Audit

**Status:** Independent source audit; adapter NOT implemented  
**Repository:** `delythassociates/GDEC`  
**Audited source ref:** `research/phase-5.2.1b-expression-input-integrity`  
**Audit branch:** `research/phase-5.2.2a-legacy-eir-audit-review`  
**Scope:** Existing `.gdc` grammar, AST, semantic lowering, legacy `ProblemIR`, compiler boundary, and migration contract.

> This document records source-verified behaviour separately from migration proposals. It is not a claim that a canonical EIR migration has been implemented, numerically validated, or approved for production.

## 1. Executive conclusion

The legacy `ProblemIR` is a compact, solver-decoupled representation of one specific problem family: 2D, small-strain, linear isotropic elasticity on a rectangular domain, with edge-labelled constraints, edge traction, and an average-displacement quantity of interest. It is not a general-purpose engineering IR.

A safe migration is feasible only as a **partial, one-way, version-pinned lowering** from legacy `ProblemIR` into a canonical EIR version whose required fields and semantics have been explicitly fixed. The adapter must not silently invent geometry, units, coordinate frames, field distributions, solver semantics, or provenance. Cases outside the representable subset must return structured diagnostics and no EIR object.

**Recommendation:** approve adapter design only after the target EIR schema version and unit/frame conventions are ratified. Implement the adapter later as a separate package/module with no changes to the legacy parser, semantic analyser, `ProblemIR`, or FEM solver in this audit phase.

## 2. Evidence inspected

The following files were fetched from the audited remote ref:

| Source | Verified content |
|---|---|
| `src/gdec/language/grammar.lark` | Actual Lark grammar: problem block, declarations, expressions, calls, positional/named arguments, comments. |
| `src/gdec/language/ast.py` | Dataclass AST nodes and source location representation. |
| `src/gdec/language/parser.py` | AST transformer, numeric parsing, argument handling, parser error conversion. |
| `src/gdec/language/semantic.py` | Declaration validation, semantic extraction, defaults, cross-field checks, lowering. |
| `src/gdec/language/ir.py` | Pydantic v2 legacy IR models, field constraints, cross-field invariants, JSON methods. |
| `src/gdec/compiler/compiler.py` | Source → AST → semantic lowering → `ProblemIR`; diagnostic handling. |
| `src/gdec/compiler/validation.py` | Compiler diagnostic data model. |
| `examples/cantilever.gdc` | Concrete checked-in legacy source example. |
| `docs/language_specification.md` | User-facing language declarations and example. |
| `docs/intermediate_representation.md` | Legacy IR JSON example and stated schema purpose. |

The README identifies the legacy schema as `gdec_ir_v0.1`. The audited branch also contains a separate `gdec.eir.expressions` static expression-typing layer. That expression layer is not, by itself, a complete persisted canonical Problem/EIR schema or a legacy adapter.

**Evidence limitation:** only one checked-in `.gdc` example was located and fetched in this audit. The other example paths probed were not present at those paths. Accordingly, this report traces one actual example and supplies two explicit *synthetic test fixtures* as proposed acceptance cases; it does not misrepresent those fixtures as repository examples. A complete audit of all examples and test fixtures remains an open verification item.

## 3. Actual source-to-IR pipeline

```text
.gdc source
  └─ Lark grammar (grammar.lark)
       └─ ProblemNode / Statement / Expression AST (ast.py)
            └─ SemanticAnalyzer.analyze()
                 ├─ declaration allowlist + singleton checks
                 ├─ geometry/material/BC/load/QoI/accuracy/budget/adaptivity/backend extraction
                 ├─ selected cross-field boundary checks
                 └─ Pydantic ProblemIR construction (ir.py)
                      └─ JSON serialization (model_dump_json)
```

The AST is not a lossless concrete syntax tree. It retains a problem name, statement keys, expression nodes, and a line/column location. Numeric literals are converted to Python `float` while their raw token text is retained on `NumberLiteral`; the legacy IR receives the numeric value, not the original token spelling. String literal parsing strips the surrounding quotes and does not implement a full escape-decoding pass in the transformer.

The grammar permits both positional and named function arguments. The semantic layer then applies per-function restrictions. Duplicate named arguments raise `ValueError` during AST transformation and are converted by the parser to a `GDECParseError`; this path does not preserve a precise source location in the same manner as ordinary Lark syntax errors.

## 4. Field-by-field mapping inventory

Classification meanings:

- **DIRECT** — representable without changing meaning, subject to explicit unit/frame interpretation.
- **DERIVED** — can be constructed deterministically from legacy data and a versioned, documented convention.
- **MISSING** — legacy source does not carry the information required by a general canonical representation.
- **UNSUPPORTED** — legacy model constrains the value to a smaller fixed set; do not widen by guessing.
- **AMBIGUOUS** — data exists but its physical meaning, provenance, or interpretation is insufficiently explicit for safe automatic conversion.

| Legacy field / source | Legacy meaning and constraints | Mapping classification | Safe migration rule |
|---|---|---|---|
| `schema_version` | Defaults to `gdec_ir_v0.1`; model field is a string. | DIRECT + validation required | Preserve as source-schema identifier; reject unknown legacy schema versions. Never confuse with target EIR version. |
| `name` | Problem identifier string from the `problem` block. | DIRECT | Preserve exactly after validating target identifier constraints; retain source provenance. |
| `physics` | Literal `linear_elasticity` only. | DIRECT for this physics | Map to the target elasticity physics identifier only if its formulation assumptions match. |
| `geometry.kind` | Literal `rectangle`. | DIRECT within restricted geometry subset | Map only to an axis-aligned rectangular 2D domain. No general geometry inference. |
| `geometry.width`, `height` | Positive finite lengths; documentation describes meters. | AMBIGUOUS → DERIVED only under pinned legacy convention | Treat as metres only under an explicit legacy profile declaring the documented convention. Store original value and conversion provenance. Reject if source profile is unknown. |
| `geometry.thickness` | Positive finite out-of-plane thickness; default 1.0 in model and semantic lowering; documentation describes meters. | AMBIGUOUS | Preserve whether explicitly supplied. If omitted, represent as an inferred legacy default with provenance; do not silently label as user input. |
| `material.kind` | Literal `isotropic`. | DIRECT | Map to isotropic linear elastic material. |
| `material.E` | Positive finite Young's modulus; docs describe Pa. | AMBIGUOUS → DERIVED under pinned SI profile | Apply Pa convention only under the versioned legacy profile; no implicit unit guessing. |
| `material.nu` | Finite scalar constrained to `-1 < nu < 0.5`. | DIRECT | Preserve as dimensionless Poisson ratio. Revalidate target admissibility. |
| `material.assumption` | `plane_stress` or `plane_strain`; defaults to plane stress. | DIRECT + provenance | Preserve the exact assumption and whether it was explicit or defaulted. Never choose based on thickness or geometry heuristics. |
| `boundary_conditions[]` | Boundary label in `left/right/top/bottom`; constrained components are always `["x","y"]`. | DIRECT for full-edge/full-component subset; otherwise UNSUPPORTED | Map edge identity only for canonical rectangle orientation. Preserve full x/y constraints. Do not infer partial constraints or nonzero prescribed values. |
| `loads[]` | `TractionLoadIR`: boundary plus scalar `tx`, `ty`; defaults to zero. | AMBIGUOUS / restricted | Values documented as Pa; traction is uniform per named edge in current model. Map only if target explicitly represents uniform edge traction in the same coordinate convention. Preserve explicit-vs-defaulted components. |
| `objective.kind` | `average_displacement` only. | DIRECT for matching QoI definition | Confirm target averaging measure, sign, component basis, and boundary integration convention. If any differ, reject or require explicit conversion semantics. |
| `objective.boundary` | Rectangle edge label; defaults to right. | DIRECT within rectangle subset; provenance required | Map named edge; retain whether defaulted. Reject if target domain has no equivalent edge identity. |
| `objective.component` | x or y; defaults to y. | DIRECT only under same global coordinate basis | Preserve basis explicitly; do not silently transform frames. |
| `accuracy.kind` | `successive_qoi_change`. | DIRECT as a stopping criterion, not as a certified error bound | Map to a convergence/stopping policy, never to an EIR error certificate or guaranteed accuracy claim. |
| `accuracy.percent` | Positive percentage; defaults to 1.0. | DIRECT + provenance | Preserve as a relative successive-iterate QoI change threshold. It is not a bound on true QoI error. |
| `budget.kind/value` | `max_dofs`, positive integer; default 25,000. | DIRECT for DOF budget | Map only to a target budget with the same DOF counting convention. Record legacy default provenance. |
| `budget.max_iterations` | Positive integer; default 15. | DIRECT for iteration cap | Preserve as an iteration limit, not as a convergence guarantee. |
| `adaptivity.strategy` | goal_aware, recovery, uniform, dwr, goal_oriented_dwr. | DIRECT only as a strategy label; semantic support must be checked | Preserve requested strategy separately from implementation availability. Never infer that a label implies a certified estimator. |
| `adaptivity.marking_fraction` | Positive fraction ≤1; default 0.3. | DIRECT | Preserve numeric value and default provenance. |
| `adaptivity.cost_aware` | Boolean; default true. | DIRECT | Preserve as planner policy, not a physical property. |
| `backend.device` | IR permits cpu/cuda/hip/sycl/tpu; semantic compiler currently rejects non-CPU requests. | DIRECT as request metadata; execution state must not be inferred | Preserve requested backend separately from actual backend. If source is an already constructed IR with non-CPU device, do not claim it was executable. |

## 5. Important semantic facts and information loss

### 5.1 Units are conventions, not typed quantities

The Pydantic models use ordinary floating-point fields. Descriptions mention meters, Pascals, or dimensionless values, but no unit object, unit symbol, dimensional exponent, scale, or conversion provenance is stored in `ProblemIR`. The language has no unit syntax in the audited grammar.

Therefore, a legacy number such as `E=70e9` cannot be converted safely by inspecting magnitude. The adapter must apply a named, versioned legacy unit profile (for example, the documented SI convention) or refuse conversion. It must not perform heuristic unit inference.

### 5.2 Geometry is an abstract rectangle, not a CAD/mesh description

The IR stores width, height, thickness and a literal geometry kind. It does not store an origin, orientation, coordinate frame, vertex coordinates, edge parameterisation, holes, cut-outs, curved boundaries, mesh, or geometry provenance. The edge names are symbolic labels tied to the rectangle model.

An adapter can produce a canonical rectangle only if the target schema has a defined canonical placement/orientation convention. Otherwise geometry placement is ambiguous and must be supplied explicitly or conversion refused.

### 5.3 Boundary conditions are less expressive than the target should be

The semantic analyser lowers each `fix` / `boundary_condition` declaration to a boundary and hard-coded `["x", "y"]` components. It does not preserve component-specific constraints or nonzero prescribed displacement values. The Pydantic model allows a component list, but the current frontend always emits both components.

Do not manufacture a partial constraint, displacement value, symmetry condition, roller, contact, periodic condition, or multipoint constraint. Those are unsupported by the audited legacy subset.

### 5.4 Loads are uniform edge tractions only

The legacy load model contains `boundary`, `tx`, and `ty`; it has no spatially varying traction function, point force, body force, pressure-normal semantics, moment, thermal load, time dependence, or load combination metadata. The current semantic layer accepts only `traction(...)` and named arguments.

A conversion to a target surface-load object is safe only when the target explicitly represents the same uniform traction vector, coordinate basis, and units. Mapping it to pressure or a body-force density would be a semantic error.

### 5.5 QoI and accuracy semantics must remain distinct

The legacy objective is average displacement on a named edge and a Cartesian component. It is not an arbitrary expression graph. The accuracy target is a relative change between successive QoI values. This stopping criterion does not establish true solution error, QoI error, estimator reliability, or a certified upper bound.

A canonical EIR must not upgrade this legacy target to a certificate, tolerance guarantee, or verified accuracy claim.

### 5.6 Defaults destroy input-intent information

Semantic lowering supplies defaults for thickness, accuracy, budget, adaptivity, backend, objective boundary/component, traction components, and some strategy options. Once lowered into the legacy `ProblemIR`, several explicit/default distinctions are lost.

The adapter receives only `ProblemIR`; it cannot recover whether a default was omitted or explicitly supplied. It must mark these values as **legacy-default-or-explicit-unknown** unless the original AST/source is also provided. Recommended interface: accept the validated legacy IR plus an optional immutable source/provenance envelope containing source hash, source schema, and explicit-field paths. If provenance is absent, do not claim exact source reconstruction.

## 6. Cross-field checks and gaps

Verified checks in the semantic layer / Pydantic model include:
- required physics, geometry, material, at least one boundary condition, at least one load, and objective;
- singleton declarations for physics, geometry, material, objective, accuracy, budget, adaptivity and backend;
- rejection of unknown declaration names;
- duplicate edge constraints;
- fixed-edge versus traction conflict;
- fixed-edge versus displacement-objective conflict;
- finite numeric values for selected scalar fields and positive dimensions/material modulus;
- isotropic Poisson ratio range;
- supported rectangle edges and x/y components;
- rejection of non-CPU backend requests by the current source compiler.

These checks do **not** establish:
- equilibrium, solvability, uniqueness, sufficient constraints, or absence of rigid-body modes for arbitrary combinations;
- physically valid traction direction or coordinate orientation;
- dimensional consistency of all inputs (units are not represented);
- load/resultant consistency;
- mesh quality, element validity, solver convergence, or estimator reliability;
- compatibility with arbitrary target coordinate frames;
- that `dwr` or `goal_oriented_dwr` denotes a certified estimator;
- that an IR constructed directly through Pydantic passed the source compiler's semantic rules.

The adapter must revalidate target invariants independently. Successful Pydantic construction alone is not a proof of engineering well-posedness.

## 7. Proposed one-way adapter contract (NOT IMPLEMENTED)

Suggested conceptual API:

```python
adapt_legacy_problem_ir(
    legacy_ir: ProblemIR,
    *,
    legacy_profile: LegacyProfile,
    provenance: SourceProvenance | None = None,
    target_schema_version: str,
) -> AdaptationResult
```

The names are proposals, not existing APIs.

### 7.1 Required behaviour

1. **Version gate:** accept only explicitly supported `gdec_ir_v0.1` and an explicitly supported target EIR version.
2. **No reverse path:** canonical EIR is authoritative; no EIR → legacy downgrade in this adapter.
3. **No guessing:** require a named legacy profile for unit conventions and a target geometry/frame convention. Missing profile → refusal.
4. **Explicit mapping table:** every emitted target field records source field(s), conversion rule, and whether the value was explicit, defaulted, or unknown.
5. **Determinism:** identical legacy IR, profile, provenance, and target schema version yield byte-equivalent canonical payload after canonical serialization.
6. **No silent defaults:** adapter-created required target fields must be derived by a documented deterministic rule or cause refusal.
7. **Fail closed:** any unsupported, ambiguous, invalid, or lossy field blocks creation of an executable EIR. No partially executable EIR.
8. **Diagnostics:** structured code, severity, source path, target path, message, and remediation; no exception text parsing.
9. **Preserve source:** retain original legacy JSON/hash and schema version in provenance; do not mutate the input model.
10. **Separation:** adapter is isolated from parser, semantic analyser, legacy ProblemIR and solver. No runtime execution is performed by conversion.

### 7.2 Result model

A proposed result should contain:
- `success: bool`;
- `eir: CanonicalProblem | None` (must be null on blocking diagnostics);
- ordered diagnostics with stable codes;
- mapping/provenance manifest;
- source and target schema versions;
- canonical payload hash (only on success).

Potential stable diagnostic families:
- `LEGACY_SCHEMA_UNSUPPORTED`
- `TARGET_SCHEMA_UNSUPPORTED`
- `UNIT_PROFILE_REQUIRED`
- `GEOMETRY_FRAME_UNSPECIFIED`
- `FIELD_UNREPRESENTABLE`
- `DEFAULT_PROVENANCE_UNKNOWN`
- `QOI_SEMANTICS_MISMATCH`
- `LOAD_SEMANTICS_MISMATCH`
- `TARGET_INVARIANT_FAILED`

## 8. Source-to-target trace: actual and proposed fixtures

### 8.1 Actual checked-in example: `examples/cantilever.gdc`

The checked-in source declares:
- physics: `linear_elasticity`;
- rectangle: width 2.0, height 0.5, thickness 0.02;
- isotropic material: E=70e9, nu=0.33, plane_stress;
- fixed left edge;
- right-edge traction tx=0, ty=-1.0e6;
- right-edge average y-displacement objective;
- 1.0% successive QoI-change criterion;
- 25,000 DOF budget;
- goal_aware adaptivity;
- CPU backend.

Semantic lowering yields the corresponding legacy fields. Safe target mapping is possible only under a pinned SI legacy profile, canonical rectangle placement convention, and matching average-displacement definition. The target must label the accuracy item as a stopping criterion, not a certified error bound.

### 8.2 Proposed synthetic acceptance fixture: plane-strain cantilever

Start from the actual cantilever fixture and change `assumption=plane_strain`; retain all other values. Expected adapter behaviour: preserve `plane_strain` exactly. It must not infer plane stress from the thin rectangle or alter material constants. This is a test fixture proposal, not a second checked-in repository example.

### 8.3 Proposed synthetic acceptance fixture: defaulted thickness and objective

Remove `thickness` from `rectangle`, and omit `boundary` and `component` from `average_displacement`. Semantic lowering applies thickness=1.0, objective boundary=right, and component=y. Expected adapter behaviour: if the adapter receives only `ProblemIR`, mark explicit/default provenance as unknown; if it receives a source envelope, record the fields as defaulted. Do not report these values as explicit engineer inputs. This is a test fixture proposal, not a checked-in repository example.

## 9. Acceptance test plan for a future adapter

| ID | Test | Expected result |
|---|---|---|
| MAP-001 | Actual cantilever example under declared SI profile | Successful deterministic mapping to the pinned EIR schema. |
| MAP-002 | Plane-strain variant | Plane-strain assumption preserved exactly. |
| MAP-003 | Defaulted thickness/objective values with source envelope | Defaults recorded with provenance, not represented as explicit user values. |
| MAP-004 | Same IR without source envelope | Explicit/default status reported as unknown where irrecoverable. |
| MAP-005 | Missing or unknown unit profile | Refusal; no EIR emitted. |
| MAP-006 | Unknown legacy schema version | Refusal with stable diagnostic. |
| MAP-007 | Unsupported geometry/material/physics value | Refusal; no heuristic conversion. |
| MAP-008 | Partial-component or nonzero prescribed displacement requirement | Refusal; never fabricate unsupported BC semantics. |
| MAP-009 | Nonuniform traction / pressure / body force requirement | Refusal unless target and legacy source both explicitly support identical semantics. |
| MAP-010 | Unsupported QoI or changed averaging measure | Refusal with QoI-specific diagnostic. |
| MAP-011 | Non-CPU backend in legacy IR | Preserve request as metadata or refuse executable lowering; never claim execution availability. |
| MAP-012 | Fixed-edge/load/objective conflict in directly constructed IR | Target validation refuses it even if source compiler was bypassed. |
| MAP-013 | Malformed dimensions/material scalars / nonfinite values | Refusal before EIR emission. |
| MAP-014 | Serialization round-trip | Canonical serialization stable and validates against exact target schema version. |
| MAP-015 | Repeat identical conversion | Byte-identical canonical payload and stable provenance manifest. |
| MAP-016 | Input object mutation attempt | Adapter does not mutate caller-owned legacy IR or provenance. |
| MAP-017 | Existing legacy compiler/solver regression suite | Unchanged baseline; adapter adds no dependency or behavioural change. |
| MAP-018 | Mapping manifest completeness | Every emitted target field traces to a source field or explicit derivation rule. |

Numerical equivalence testing is separate from schema mapping. A successful structural conversion does not prove that the target solver produces the same solution. Any later solver integration needs independent reference cases, reaction/equilibrium checks, QoI comparison, and tolerance justification.

## 10. Risks and required decisions before implementation

1. **Pin canonical EIR schema.** Identify the exact target schema/version and required fields. The expression typing layer is not a substitute for a complete problem schema.
2. **Ratify unit profile.** Confirm whether all legacy v0.1 dimensions are SI as described, and document exact unit conventions for every field.
3. **Ratify coordinate convention.** Define rectangle origin, axes, edge normals, traction sign, and component basis.
4. **Define provenance envelope.** Decide whether the adapter requires original source/AST to preserve explicit/default intent.
5. **Define QoI equivalence.** Specify integration measure and averaging convention for legacy `average_displacement`.
6. **Define execution metadata semantics.** Distinguish requested backend from actual backend and strategy label from implemented numerical method.
7. **Complete fixture inventory.** Locate and audit all actual `.gdc` examples and tests before declaring the mapping inventory exhaustive.

## 11. Decision

**Audit outcome: CONDITIONALLY SUITABLE FOR ADAPTER DESIGN; NOT READY FOR IMPLEMENTATION.**

The supported legacy subset can be mapped in principle, but a safe adapter requires a pinned target EIR schema, explicit legacy SI profile, canonical rectangle/frame convention, and a provenance policy. Any field outside the subset must cause a structured refusal. No adapter, parser change, semantic analyser change, legacy IR change, FEM change, or solver change is included in this work.

## Appendix A — Key source anchors

- Grammar: `src/gdec/language/grammar.lark`
- AST: `src/gdec/language/ast.py`
- Parser: `src/gdec/language/parser.py`
- Semantic lowering: `src/gdec/language/semantic.py`
- Legacy models: `src/gdec/language/ir.py`
- Compiler orchestration: `src/gdec/compiler/compiler.py`
- Compiler diagnostics: `src/gdec/compiler/validation.py`
- Actual example: `examples/cantilever.gdc`
- Legacy IR overview: `docs/intermediate_representation.md`
- Language overview: `docs/language_specification.md`


## 12. Additional source and test verification (follow-up audit)

A second pass inspected the concrete grammar, AST, parser, compiler orchestration, language tests, compiler tests, IR round-trip test, and both the older language documentation and the newer normative language profile.

### 12.1 Concrete grammar limits

The grammar is materially narrower than a general expression language:

- It accepts one `problem` block as the start symbol.
- A declaration RHS is one function call, identifier, signed numeric token, or escaped string.
- It does not define arithmetic operators, comparison operators, array/list/map literals, imports, user functions, or multiple problem blocks.
- Boolean words are identifiers, not Boolean tokens.
- The AST stores number literals as Python floats while retaining their raw token spelling; the legacy `ProblemIR` does not retain that raw spelling.
- String transformation removes surrounding quotes. The parser implementation does not explicitly decode escape sequences into a defined language-level string semantics.
- The grammar accepts mixed positional/named arguments syntactically; constructor-specific semantic checks reject many combinations.
- Duplicate named arguments are rejected in AST transformation via `ValueError`, then wrapped as a parser error. This path does not preserve the token's precise line/column in the same way as ordinary syntax errors.

These are important migration constraints: the adapter should consume validated IR, not attempt to reinterpret source syntax or invent expression semantics.

### 12.2 Documentation drift

The older `docs/language_specification.md` does not accurately describe the current grammar. Its abbreviated grammar omits signed numbers, string expressions, positional arguments, trailing commas, and comments. Its declaration table also understates currently accepted adaptivity strategies and describes backend support incompletely.

The newer `docs/specifications/GDEC_LANGUAGE_SPECIFICATION_0.1.md` is substantially aligned with the actual grammar and semantic implementation. It explicitly describes the implemented profile and states that source code is authoritative if documentation disagrees.

**Audit finding:** treat `docs/specifications/GDEC_LANGUAGE_SPECIFICATION_0.1.md` and the source implementation as the migration reference pair. The older `docs/language_specification.md` should be corrected in a separate documentation-only change; this audit does not modify it.

### 12.3 Test files directly inspected

The following files were fetched and read from the audited ref:

| Test file | Directly observed coverage |
|---|---|
| `tests/test_language.py` | Valid parse, syntax rejection, missing/unsupported physics, negative Young's modulus, invalid Poisson ratio, non-CPU backend rejection. |
| `tests/test_compiler.py` | Compile checked-in cantilever example, deterministic JSON serialization for repeated source compilation, source-context diagnostic. |
| `tests/test_ir.py` | Legacy ProblemIR JSON round-trip for selected fields and schema version. |

This is a list of inspected files, not a claim that these are the only tests in the repository. The tests directly inspected do not establish comprehensive adapter coverage for unit provenance, default provenance, frame conventions, all boundary/load semantics, all schema-version failure modes, or numerical equivalence after migration.

### 12.4 Canonical EIR draft status and migration implication

The current `docs/specifications/CANONICAL_ENGINEERING_IR_DRAFT_0.1.md` explicitly labels itself an architecture proposal, not implemented. Its illustrative JSON shape is conceptual and is not a production JSON Schema. It intentionally leaves entity-specific schema details and multiple design questions unresolved.

The separate foundational EIR package and expression-typing layer are real implementation work on feature branches, but they do not turn the canonical draft into a frozen, complete target contract. The expression subsystem documentation also states that expression graphs are not yet persisted in the EIR wire schema or attached to QoIs.

**Consequent gate:** an adapter may not claim to target “canonical EIR 0.1” merely by constructing existing type-system objects. The exact target model, serialization contract, version identifier, required fields, and invariants must be selected and reviewed first.

### 12.5 Corrections and scope notes

- The source code is the authority for implemented semantics; documentation is a separate evidence source and can drift.
- The inspected legacy tests provide basic frontend and serialization regression coverage, not proof of adapter correctness.
- No tests were executed as part of this remote source review. No test-pass claim is made.
- No changes were made to the legacy compiler, parser, AST, semantic analyser, `ProblemIR`, FEM, solver, or existing tests.


### 12.6 Concrete implemented EIR 0.1.0 model: important additional mapping blockers

A further inspection of `src/gdec/eir/models.py` establishes a more precise distinction than the architecture draft alone:

- The repository **does implement** a restricted `EngineeringProblemIR` model with `kind = gdec.engineering_problem`, `schema_version = 0.1.0`, and pinned `unit_registry_id = gdec-si-engineering-0.1`.
- The model is structurally validated, exports a Pydantic JSON Schema, provides canonical JSON and SHA-256 methods, and validates identifiers, frame/domain/field references, selected shape rules, units and direct field-value QoIs.
- This is a real, versioned restricted EIR core. It is not accurate to describe all canonical EIR implementation as merely conceptual.
- However, the implemented model is intentionally incomplete relative to the legacy elasticity `ProblemIR`. It contains problem identity, coordinate frames, domains, scalar quantity parameters, fields, and QoIs whose operation is only `field_value`. Its `PhysicalModelIR` does not yet contain constitutive relations, governing equations, material models, boundary conditions, or loads. It has no explicit rectangle geometry entity, elasticity assumption, solver/adaptivity policy, legacy accuracy stopping criterion, or DOF/iteration budget.

This yields the following concrete mapping status:

| Legacy requirement | Implemented EIR 0.1.0 support | Adapter consequence |
|---|---|---|
| Problem name/identity | `ProblemIdentity` exists | Map name and stable ID only with deterministic ID policy; source problem name alone is not guaranteed globally unique. |
| Rectangle width/height/thickness | `DomainIR` only records spatial dimension and frame reference | Cannot preserve rectangle extents or thickness in current EIR core. Refuse lossless conversion unless a separately versioned geometry entity is added. |
| Young's modulus and Poisson ratio | Scalar `QuantityParameterIR` can hold values/units | Values can be stored as parameters, but no implemented constitutive relation binds them into an isotropic elastic material. Do not claim material semantics preserved. |
| Plane stress / plane strain | No elasticity assumption field | Cannot map without extending the physics/constitutive model. |
| Fixed boundary conditions | No boundary-condition entity | Cannot map. |
| Edge traction loads | No load/traction entity | Cannot map. |
| Average displacement on a boundary | QoI supports only direct `field_value` reference | Cannot preserve boundary integration/averaging semantics. |
| Successive QoI-change stopping threshold | No accuracy/stopping policy entity | Cannot map. |
| DOF/iteration budget | No resource-budget entity in the implemented core | Cannot map. |
| Adaptivity strategy/fraction/cost-aware policy | No adaptivity policy entity | Cannot map. |
| Requested backend | No execution-policy entity in the implemented core | Cannot map as structured EIR policy. |

**Revised technical conclusion:** the current EIR 0.1.0 model is a useful typed identity/domain/field/parameter/QoI foundation, but it is not yet a target schema capable of representing the legacy elasticity problem without substantial semantic loss. A legacy-to-EIR adapter that returns a complete executable engineering problem is therefore **not implementable against the current EIR 0.1.0 model**. The safe choices are:

1. Extend a future EIR schema version with reviewed elasticity, geometry, boundary/load, QoI, execution and resource-policy entities before writing the adapter; or
2. Define an explicitly partial archival/import representation that preserves the original legacy JSON as opaque provenance and is never presented as an executable equivalent.

Option 1 is recommended for the intended canonical compiler architecture. Option 2 may be useful for migration tooling but must not be mistaken for semantic lowering.

The exact EIR model version and model source are now known; the remaining blocker is not simply selecting a version. It is specifying and implementing the missing semantic entity families, plus defining their invariants and serialization contract. This is a design blocker, not permission to add fields ad hoc in the adapter.
