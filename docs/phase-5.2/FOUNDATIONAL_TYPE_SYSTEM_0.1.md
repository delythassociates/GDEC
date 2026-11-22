# GDEC Phase 5.2 — Foundational Engineering Type System 0.1

**Status:** Initial implementation on a feature branch; not yet merged or independently certified.  
**Scope:** Solver-independent type primitives. Existing language, ProblemIR, elasticity solver and runtime are unchanged.

## Implemented

- Exact seven-base-SI-dimension algebra using rational exponents.
- Common derived dimensions: velocity, acceleration, force, pressure, energy and power.
- Explicit unit registry with scale and affine offset conversions.
- Common engineering units for length, time, mass, current, temperature, amount, luminous intensity, force, pressure, energy and power.
- Absolute-temperature and temperature-interval distinction; Celsius/Fahrenheit affine conversions.
- Scalar Quantity with dimension-checked arithmetic and temperature-specific operation guards.
- Tensor shape metadata, coordinate-frame identifiers and domain/function-space field metadata.
- Structured type-system exceptions.
- Independent tests under tests/types/.

## Deliberate limits

- This is a primitive library, not yet wired into the .gdc parser, AST, semantic analysis or ProblemIR.
- No implicit unit inference, parser syntax, EIR serializer, field arithmetic, frame transformation, tensor contraction or automatic differentiation is implemented.
- The unit registry is intentionally small and extensible; it is not a complete UCUM/ISO 80000 catalogue.
- Quantity.value is stored in the coherent base unit for its dimension. Quantity.unit records optional source-unit metadata; arithmetic results do not claim a source display unit.
- Temperature intervals use interval units (delta_degC, delta_K) and are never interchangeable with absolute-temperature units.
- A coordinate frame is metadata only; no transform graph or rotation matrix is applied.

## Safety and compatibility

The implementation does not modify src/gdec/language/, src/gdec/compiler/, src/gdec/core/, existing solver code or historical gdec_ir_v0.1 documents. Existing behavior remains the compatibility baseline.

## Acceptance gates still required

1. Run the full existing test suite on Python 3.10, 3.11 and 3.12.
2. Add property-based tests for dimension laws and conversion round trips.
3. Independently review affine-temperature arithmetic and unit semantics.
4. Define serialization and stable public API policy before exposing these types in EIR.
5. Review failure messages, numeric-domain checks (NaN/Inf, division by zero) and unit registry extension semantics.
6. Ratify relevant ADRs before connecting this package to the compiler.

Passing tests would establish software behavior only; it would not certify any physical model or numerical solver.
