# GDEC Canonical Engineering IR — Draft 0.1

**Status:** Architecture proposal; not implemented  
**Purpose:** Define the semantic contract between engineering authoring interfaces, numerical methods, execution backends and independent verification.  
**Compatibility baseline:** Existing ProblemIR remains supported and unchanged during the first migration stages.

## 1. Design objective

GDEC needs an intermediate representation that captures engineering meaning independently of:

- the source syntax used by an engineer;
- a particular physics module;
- a finite-element library;
- a mesh representation;
- a linear algebra package;
- a CPU or accelerator backend.

The current ProblemIR is a useful elasticity-specific problem record. It is not a general engineering IR. The canonical IR proposed here is a versioned semantic model with explicit references, types, dimensions, units, domains and verification obligations.

The IR is not intended to be a universal programming language. It is a typed engineering model from which domain-specific mathematical formulations and execution plans can be derived.

## 2. Architectural separation

The proposed pipeline is:

~~~text
.gdc / Python API / CAD / visual authoring / reviewed natural-language draft
                                  |
                                  v
                         Frontend-specific AST
                                  |
                                  v
                    Name resolution and type checking
                                  |
                                  v
                     Canonical Engineering IR (EIR)
                                  |
                  +---------------+----------------+
                  |               |                |
                  v               v                v
            Physics lowering  QoI/intent       Verification
                  |           obligations      obligations
                  v               |                |
          Variational IR           |                |
                  |                |                |
                  v                v                v
          Discretisation IR   Decision contract  Certificate spec
                  |
                  v
           Execution plan / backend lowering
                  |
                  v
          Solver output and proposed evidence
                  |
                  v
        Independent checker and evidence report
~~~

All authoring frontends MUST lower to the same semantic EIR for equivalent engineering problems. Frontends MUST NOT define separate physical semantics.

## 3. Required representation layers

The EIR is logically layered. Implementations MAY store the layers in one serialized document, but their types and responsibilities MUST remain distinct.

### 3.1 Problem identity and engineering intent

Represent:

- stable problem identifier;
- human-readable name and description;
- requirements and acceptance criteria;
- quantities of interest (QoIs);
- decision context and consequence class, when supplied;
- operating envelope and applicability conditions;
- computational resource constraints;
- explicit assumptions and unresolved questions.

An acceptance criterion is not a numerical solver tolerance. A QoI target is not an error estimator. These concepts MUST remain distinct.

### 3.2 Physical model

Represent:

- spatial and temporal domains;
- coordinate frames and transformations;
- physical fields and their value types;
- parameters and material properties;
- constitutive relations;
- governing balance equations;
- source terms;
- initial and boundary conditions;
- interfaces and coupling relations;
- model assumptions and applicability restrictions.

Every referenced entity MUST have a stable identifier and a declared type.

### 3.3 Mathematical and variational formulation

Represent the mathematical operators needed by supported physics modules, including:

- scalar and vector fields;
- gradients, divergences, symmetric gradients and traces;
- tensor products, contractions and inner products;
- volume and boundary integration;
- normal and tangential components;
- trial and test functions;
- bilinear and linear forms;
- constraints and admissible function spaces.

This layer is the source of truth for deriving primal and adjoint problems and for generating residuals, sensitivities and estimator obligations. A solver-specific stiffness matrix MUST NOT be treated as the governing physical model.

### 3.4 Discretisation

Represent:

- mesh/domain association;
- element or approximation family;
- polynomial order;
- trial and test spaces;
- quadrature rules and order;
- geometry mapping;
- approximation constraints;
- refinement/coarsening policy;
- discretisation assumptions.

Discretisation choices MUST be traceable to the mathematical formulation and the requested QoI.

### 3.5 Execution policy

Represent requests and constraints, not facts about achieved execution:

- solver family and admissible alternatives;
- preconditioner requirements;
- precision policy;
- CPU/GPU capability requirements;
- memory and wall-time budgets;
- parallelism and partitioning constraints;
- reproducibility policy.

The actual backend, device, precision and solver used MUST be recorded in an execution record, separate from the requested policy. A request for CUDA MUST NOT be silently represented as a completed CUDA execution if CPU fallback occurred.

### 3.6 Verification and evidence obligations

Represent what must be established:

- well-posedness or admissibility conditions relevant to the chosen formulation;
- algebraic solve obligations;
- discretisation error-estimation or guaranteed-bound requirements;
- QoI error obligations;
- conservation/equilibrium checks;
- model validation requirements;
- uncertainty and applicability requirements;
- provenance and reproducibility requirements;
- checker identity and verification result.

A requested assurance level is an obligation, not a claim that the obligation has been satisfied.

## 4. Dimension-aware physical type system

### 4.1 Dimension model

Represent a physical dimension as a vector of rational exponents over the seven SI base dimensions, in this fixed order:

~~~text
(M, L, T, I, Theta, N, J)
~~~

where M is mass, L length, T time, I electric current, Theta thermodynamic temperature, N amount of substance, and J luminous intensity.

For example:

- length: (0, 1, 0, 0, 0, 0, 0)
- time: (0, 0, 1, 0, 0, 0, 0)
- velocity: (0, 1, -1, 0, 0, 0, 0)
- force: (1, 1, -2, 0, 0, 0, 0)
- pressure: (1, -1, -2, 0, 0, 0, 0)
- energy: (1, 2, -2, 0, 0, 0, 0)

Rational exponents are proposed so that dimension rules can represent operations such as square roots where mathematically valid. Each operation MUST still define its domain and result type.

### 4.2 Quantity and unit are different

A physical quantity has a numerical value and a dimension. A unit is a representation of that quantity.

The type system MUST distinguish:

- dimension;
- unit symbol and unit definition;
- conversion scale;
- conversion offset, where applicable;
- quantity kind, including absolute versus differential temperature where relevant.

Canonical internal numerical values SHOULD use coherent SI units. Source units SHOULD be preserved as metadata for diagnostics and reporting.

Affine units require special treatment. Absolute temperature and temperature difference are not interchangeable. Offset conversion MUST NOT be applied to temperature intervals or arbitrary derived quantities.

### 4.3 Core value types

The minimum type universe SHOULD include:

- Bool and enumeration types;
- Integer and real scalar types;
- Quantity[Dimension];
- Vector[Dimension, Frame, Length];
- Tensor[Dimension, Frame, Shape];
- Field[ValueType, Domain, FunctionSpace];
- Parameter[ValueType];
- Coordinate[Frame, Dimension];
- BoundaryField[ValueType, BoundaryRef].

A field type MUST identify the domain on which it is defined. A vector or tensor MUST identify its coordinate frame or explicitly state that it is frame-independent.

### 4.4 Dimensional typing rules

At minimum:

- Addition and subtraction require compatible dimensions and compatible quantity kinds.
- Multiplication adds dimension exponents.
- Division subtracts dimension exponents.
- Equality and ordering require compatible dimensions and compatible quantity kinds.
- Transcendental functions require dimensionless inputs unless a domain-specific rule says otherwise.
- Differentiation with respect to a coordinate subtracts the coordinate dimension.
- Integration multiplies the integrand dimension by the integration-measure dimension.
- Dot products, tensor contractions and traces MUST validate shape, frame and dimension rules.
- Assignment and function calls MUST enforce declared types.
- Unit conversion MUST preserve the physical quantity.

The compiler MUST reject an ill-typed expression before numerical execution. It MUST NOT silently drop incompatible units or infer a conversion from a field name.

### 4.5 Physical admissibility is not dimensional consistency

Dimensional consistency alone does not prove a model physically valid.

Physics modules MUST add domain-specific constraints, for example:

- positive conductivity for a coercive scalar diffusion problem;
- admissible elastic material parameters;
- compatible boundary and initial conditions;
- valid geometry and coordinate mappings;
- constitutive symmetry or positive-definiteness when required by the formulation.

The compiler MUST report which checks are syntactic, dimensional, physical-model-specific or numerical. These categories MUST NOT be conflated.

## 5. Stable identifiers, references and source maps

Every semantic entity MUST have a stable identifier within the EIR document. References MUST resolve to exactly one entity of the expected kind.

The frontend SHOULD preserve source maps from EIR entities and expressions back to source file, line, column and span. Source maps are diagnostic metadata and MUST NOT change physical semantics.

The EIR MUST reject dangling references, duplicate identifiers, invalid ownership, incompatible domain references and cyclic definitions unless a specific recursive construct is explicitly supported.

## 6. Serialization and versioning

The wire format is proposed as JSON with:

- a stable top-level kind;
- an explicit schema version;
- stable entity identifiers;
- explicit type and dimension objects;
- explicit unit metadata;
- deterministic serialization rules;
- no executable Python objects or arbitrary code payloads.

Proposed identifiers:

- document kind: gdec.engineering_problem
- draft schema version: 0.1.0

This draft identifier is not the current gdec_ir_v0.1 identifier. Do not reuse or overwrite the existing schema version.

Schema versioning policy:

- patch: clarify metadata or fix serialization without changing semantic interpretation;
- minor: add optional backward-compatible fields or entity kinds;
- major: change existing meaning, required fields, typing rules or reference semantics.

A reader MUST reject an unsupported major schema version. Unknown extension fields MUST be handled according to an explicit extension policy; they MUST NOT be silently interpreted as known physical semantics.

Canonical serialization MUST define numeric formatting, ordering of semantically unordered collections, unit normalization and hash input. Hashes MUST be computed over canonicalized content, not arbitrary pretty-printed JSON.

## 7. Trust and security boundary

The EIR is untrusted input until validated. The compiler MUST validate structure, references, dimensions and physics-specific constraints before lowering.

The planner, generated kernels, numerical solvers and runtime telemetry are not independent verification authorities.

The verification subsystem MUST consume a versioned verification obligation and a certificate/evidence payload. It MUST independently check the claims it is designed to check. It MUST return an explicit result such as VERIFIED, NOT_VERIFIED, INCOMPLETE or INAPPLICABLE, together with reasons and checker identity.

A field supplied by the solver saying verified=true, a caller-provided validation status, or an unauthenticated provenance string MUST NOT be sufficient to establish a certificate.

The certificate format and checker interface require a separate specification. This EIR draft reserves references to those objects but does not claim that certificate checking is implemented.

## 8. Illustrative semantic shape

The following is a conceptual shape only. It is not a production JSON Schema and cannot currently be loaded by GDEC.

~~~json
{
  "kind": "gdec.engineering_problem",
  "schema_version": "0.1.0",
  "problem": {
    "id": "problem.cantilever",
    "requirements": [],
    "quantities_of_interest": [],
    "resource_constraints": []
  },
  "physical_model": {
    "domains": [],
    "coordinate_frames": [],
    "fields": [],
    "parameters": [],
    "constitutive_relations": [],
    "governing_equations": [],
    "boundary_conditions": [],
    "assumptions": []
  },
  "variational_formulations": [],
  "discretisation": {},
  "execution_policy": {},
  "verification_obligations": []
}
~~~

The empty arrays above are intentional. Each entity type needs a separately reviewed schema and typing rules before the wire format is frozen.

## 9. Required invariants

A conforming EIR validator MUST establish at least:

1. Unique and resolvable entity identifiers.
2. Valid references and ownership relationships.
3. Well-formed dimension vectors.
4. Valid unit definitions and conversions.
5. Dimensionally valid expression trees.
6. Shape and coordinate-frame compatibility.
7. Domain and boundary association consistency.
8. Physics-module-specific admissibility checks.
9. Explicit distinction between requested execution policy and observed execution.
10. Explicit verification obligations and evidence status.
11. Deterministic serialization and schema-version validation.
12. No execution of source-provided arbitrary code during parsing or validation.

## 10. First supported vertical slice

The first canonical IR implementation SHOULD cover only the minimum shared subset needed to represent the existing 2D linear-elasticity problem and a restricted steady heat-conduction problem.

It SHOULD NOT attempt to model every multiphysics system.

The initial type-system acceptance cases should include:

- metre plus millimetre after conversion;
- rejection of metre plus second;
- Young's modulus with pressure dimension;
- traction with pressure dimension;
- displacement with length dimension;
- gradient dimension propagation;
- boundary field/domain compatibility;
- vector component and frame compatibility;
- rejection of non-positive conductivity where the heat formulation requires positivity.

## 11. Research and prior art

A domain-specific language for finite-element modeling with awareness of physical units has already been published. GDEC MUST NOT claim that an engineering DSL, FEM DSL or unit-aware input syntax is novel by itself.

Relevant prior work includes:

- Feng et al., "Domain specific language for finite element modeling and simulation", Advances in Engineering Software 193 (2024), article 103666, DOI: 10.1016/j.advengsoft.2024.103666.
- Research on dimensional type systems and compile-time dimensional analysis in programming languages, including work presented at ICSE 2006 on validating dimensional unit correctness of C programs.

The potential GDEC contribution must be evaluated as a combination of engineering intent, goal-driven computation planning, explicit verification obligations and independently checkable evidence—not merely the existence of a new syntax or typed IR.

## 12. Open design questions

The following are intentionally unresolved and require ADRs or focused research:

1. Whether the canonical mathematical layer is a typed symbolic expression graph, a variational-form IR, or both with a defined lowering boundary.
2. How to represent nonlinear, transient and coupled systems without creating a monolithic schema.
3. Whether rational dimension exponents are sufficient for all supported engineering operations.
4. How to model affine units and absolute/difference quantities robustly.
5. How coordinate-frame transformations are represented and checked.
6. How geometry and mesh identity are bound to the physical model and certificate.
7. How model-form uncertainty and experimental validation are represented.
8. How certificate payloads are versioned and independently checked.
9. Whether JSON remains the canonical exchange format or is paired with a binary artifact format for large fields and meshes.

No implementation should silently settle these open questions.
