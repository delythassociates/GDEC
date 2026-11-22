# GDEC Phase 5.2 — Foundational Engineering Type System 0.1

**Status:** Implemented on the Phase 5.2 feature branch; awaiting final CI/code review.  
**Scope:** Solver-independent type primitives. Existing language, legacy ProblemIR, elasticity solver and runtime are unchanged.

## Implemented

- Seven-base-SI-dimension algebra using exact rational exponents.
- Common derived dimensions: velocity, acceleration, force, pressure, energy and power.
- Explicit unit definitions and registry with positive scale validation, affine offsets and atomic registration.
- Common engineering units for length, time, mass, current, temperature, amount, luminous intensity, force, pressure, energy and power.
- Absolute-temperature and temperature-interval distinction, including Celsius/Fahrenheit conversions and absolute-zero checks.
- Scalar Quantity arithmetic with dimensional compatibility checks, finite numeric validation, zero-division guards and temperature-specific operation rules.
- Temperature intervals remain affine intervals under scalar/dimensionless scaling; multiplication or division by dimensional quantities produces an ordinary derived linear quantity.
- Immutable tensor-shape metadata, coordinate-frame identifiers and field/domain/function-space metadata.
- Structured type-system exceptions.
- Adversarial tests covering rational exponents, unit aliases, non-finite inputs, absolute zero, interval arithmetic, division by zero and runtime metadata typing.

## Deliberate limits

- This is not yet wired into the .gdc parser, AST, semantic analysis, legacy ProblemIR or solver lowering.
- No implicit unit inference, parser syntax, automatic field arithmetic, frame transformation, tensor contraction or automatic differentiation is implemented.
- The registry is intentionally small; it is not a complete UCUM/ISO 80000 catalogue.
- Quantity.value is stored in coherent SI base units. Quantity.unit records optional source/display metadata; arithmetic results do not claim a source display unit.
- Coordinate frames are metadata only; no transform graph or rotation matrix is applied.

## Safety and compatibility

The implementation does not modify src/gdec/language/, src/gdec/compiler/, src/gdec/core/, existing solver code or historical gdec_ir_v0.1 documents. Existing behavior remains the compatibility baseline.

## Validation

The first successful full CI checkpoint for the type primitives and initial EIR core was GitHub Actions run 45045239079: all three Python matrix jobs succeeded; the Python 3.10 job reported 311 passed and 13 skipped. Two additional EIR tests and subsequent canonical-unit normalization were added after that checkpoint. The latest commits must pass fresh CI before this phase slice is considered closed.

## Acceptance gates still required

1. Complete CI verification after the latest canonical-unit normalization and schema-export tests on Python 3.10, 3.11 and 3.12.
2. Broader property-based tests for dimension identities and unit-conversion round trips.
3. Independent review of affine-temperature arithmetic and all pinned unit definitions.
4. Public API and stable serialization policy before compiler integration.
5. Review numeric edge cases and registry extension policy.
6. Ratify the relevant ADRs before connecting this package to parser/compiler semantics.

Passing software tests establish implementation behavior, not physical-model validity or numerical-solver correctness.
