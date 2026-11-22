# GDEC Phase 5.2 — Canonical Engineering IR Core 0.1

**Status:** Initial implementation on the Phase 5.2 feature branch; draft API, not merged or independently certified.  
**Schema kind:** `gdec.engineering_problem`  
**Schema version:** `0.1.0`  
**Pinned unit registry:** `gdec-si-engineering-0.1`

## Scope implemented

The new package `src/gdec/eir/` implements a deliberately limited, solver-independent semantic core:

- Problem identity.
- Seven-base-SI dimension vectors represented as canonical rational strings.
- Coordinate frames with parent references.
- Spatial domains linked to coordinate frames.
- Scalar quantity parameters with finite values and pinned unit semantics.
- Fields linked to domains, dimensions, units, shapes, function spaces and optional frames.
- Direct field-value quantities of interest (QoIs).
- Global entity-ID uniqueness and reference resolution.
- Coordinate-frame parent-cycle rejection and parent/domain dimensionality checks.
- Field unit/dimension/kind consistency and field/QoI reference checks.
- Deterministic canonical JSON and SHA-256 content hashing.

The pinned unit definitions are snapshotted at module import. Extending the general-purpose `SI_UNITS` registry does not silently change the meaning of an existing EIR 0.1 document.

## Explicitly not implemented

This is not yet a complete canonical Engineering IR. It does not encode:

- Governing equations or constitutive relations.
- Variational/weak forms, trial/test spaces or symbolic expression graphs.
- Boundary and initial conditions.
- Mesh/discretisation descriptions.
- Execution policies or observed execution records.
- Resource budgets and decision contracts.
- Verification obligations, certificates or independent checker results.
- Integral, average, boundary or norm QoI operators.
- Coordinate transformation matrices or explicit transform entities.
- Model-form uncertainty or physical validation evidence.

The only implemented QoI operator is `field_value`. The schema rejects unknown fields rather than silently interpreting them. New semantics require an explicit schema/version change.

## Compatibility

The new package is additive. It does not alter the existing `gdec_ir_v0.1` Pydantic `ProblemIR`, language grammar, parser, semantic analyser, compiler, runtime or elasticity solver. No automatic legacy-to-EIR conversion is claimed.

## Canonicalization

Entity collections that are semantically unordered are sorted by stable ID before canonical JSON serialization. The canonical hash is SHA-256 over UTF-8 canonical JSON with compact separators and sorted object keys. The pinned unit-registry identifier is included in the document.

This canonicalization is a first implementation and must be treated as a versioned wire contract. A future schema revision must define how floating-point source values, unit normalization and extension namespaces evolve.

## Acceptance still required

1. Full regression suite on Python 3.10, 3.11 and 3.12.
2. Property-based tests for dimensions, conversion round trips and canonicalization.
3. Independent review of temperature kinds and all supported unit definitions.
4. JSON Schema export and compatibility tests against a separately versioned schema artifact.
5. Review whether the global-ID uniqueness policy is too restrictive for frontend-generated identifiers.
6. A design decision for geometry identity and transform graphs before adding mesh/field lowering.
7. Separate specifications for variational IR and verification/certificate obligations.

Software tests establish implementation behavior, not physical-model validity or numerical-solver correctness.
