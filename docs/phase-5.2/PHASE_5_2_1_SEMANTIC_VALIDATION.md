# GDEC Phase 5.2.1 — EIR Semantic Expression Typing

**Status:** Implemented on a feature branch; draft and unmerged.  
**Base:** Phase 5.2 foundational type system and restricted EIR 0.1 core.  
**Scope:** Static type inference only. No numerical evaluation, code generation, or solver execution.

## Purpose

The first EIR core can validate entities, units, dimensions, shapes, and references, but it does not yet validate mathematical expressions that combine engineering quantities. Phase 5.2.1 adds a solver-independent expression AST and a deterministic type-inference pass.

The type pass answers whether an expression is meaningful with respect to:
- Physical dimensions.
- Quantity kinds (linear, absolute temperature, temperature interval).
- Tensor value shape.
- Coordinate-frame identity.
- Parameter, field, and named-expression references.

It does not calculate the expression's numerical value.

## Expression nodes

The initial expression vocabulary is intentionally small:

- `Literal`: finite real scalar with an explicit `ValueType`.
- `ParameterRef`: reference to a declared scalar parameter.
- `FieldRef`: reference to a declared field.
- `ExpressionRef`: reference to a named expression in the supplied environment.

Expression construction rejects non-finite/boolean literals, missing or malformed literal types, and blank/non-string reference IDs. `ValueType` rejects malformed shape containers instead of coercing arbitrary iterables. `ExpressionEnvironment` validates its mapping contents and takes immutable snapshots, so later caller mutation cannot alter an in-progress or repeated inference result.
- `Negate`: unary negation.
- `Binary`: add, subtract, multiply, or divide.
- `Power`: exact integer or `fractions.Fraction` exponent. Floating-point exponents are rejected because silently rationalizing a binary float can change the intended physical dimension.

Unknown references, unknown operators, unsupported nodes, and cyclic named-expression references are rejected.

## Type rules

### Addition and subtraction

Addition/subtraction require equal dimensions, equal tensor shapes, and equal coordinate-frame identities. No implicit broadcasting or frame transformation is performed.

Temperature rules follow affine-temperature semantics:

| Operation | Result |
|---|---|
| absolute + interval | absolute |
| interval + absolute | absolute |
| interval + interval | interval |
| absolute + absolute | rejected |
| absolute - absolute | interval |
| absolute - interval | absolute |
| interval - absolute | rejected |

Linear quantities can only be added to/subtracted from linear quantities of equal dimension.

### Multiplication and division

- Absolute temperatures cannot be multiplied or divided.
- Scalar linear/interval dimensions compose using exact dimension algebra.
- A temperature interval multiplied/divided by a dimensionless scalar remains a temperature interval.
- Tensor multiplication/division is rejected until explicit contraction, outer-product, and indexing operators are specified.

### Powers

Only linear scalar quantities can be raised to rational powers. Temperature-kind and tensor powers are rejected until their semantics are explicitly designed.

## EIR integration

`environment_from_eir()` derives parameter and field types from a validated `EngineeringProblemIR`. This prevents callers from independently restating type metadata when an EIR document is available.

The expression subsystem is currently a separate semantic layer. EIR 0.1 does not yet persist expression graphs or attach expression roots to QoIs. That schema integration requires a deliberate versioned change rather than silently extending the current wire contract.

## Tests

The new suite covers:
- Reference resolution and missing-reference refusal.
- Dimensional addition and multiplication/division.
- Absolute-temperature and temperature-interval rules.
- Exact rational dimension propagation.
- Shape and frame mismatches.
- Rejection of implicit broadcasting and tensor products.
- Expression-reference memoization and cycle detection.
- Non-finite and boolean literal rejection at node construction.
- Invalid reference IDs, malformed shape metadata, invalid environment mappings, and environment mutation isolation.
- Environment derivation from a validated EIR document.

## Explicit limitations

- No expression evaluation or constant folding.
- No tensor contraction, dot/cross product, broadcasting, indexing, or reduction.
- No explicit coordinate transforms.
- No symbolic differentiation or automatic adjoints.
- No parser syntax or .gdc grammar changes.
- No integration into the legacy ProblemIR, compiler, runtime, or FEM solver.
- No numerical certification or physical validation claims.

These constraints are deliberate: an unsupported engineering operation must fail explicitly rather than acquire guessed semantics.
