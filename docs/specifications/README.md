# GDEC Language and Engineering IR Specifications

This directory separates the **implemented language profile** from the **proposed future architecture**. A design document is not evidence that a feature is implemented.

## Documents

1. [Implemented .gdc Language Profile 0.1](GDEC_LANGUAGE_SPECIFICATION_0.1.md) — normative description of the grammar and semantics currently implemented at the Phase 5.1.3 baseline.
2. [Canonical Engineering IR Draft 0.1](CANONICAL_ENGINEERING_IR_DRAFT_0.1.md) — proposed semantic model for a solver-independent, dimension-aware engineering representation.
3. [Language and IR Conformance Matrix](GDEC_LANGUAGE_IR_CONFORMANCE.md) — implementation-to-specification traceability and acceptance tests.

## Status and compatibility

- Language Profile 0.1 documents current behaviour; it does not claim that future quantity syntax, multiple physics, weak forms, or dimensional typing are implemented.
- Canonical Engineering IR Draft 0.1 is a design proposal, not a production schema or a replacement for the current ProblemIR.
- The current ProblemIR schema identifier remains gdec_ir_v0.1.
- Existing .gdc files and the current elasticity execution path are to remain supported during migration.
- Changes to these documents require review through the ADR register.

## Design rule

The source language expresses engineering intent. The canonical IR represents engineering meaning. Solver-specific matrices, meshes, kernels and backend details belong to later lowering and execution stages. Verification obligations and evidence must remain explicit and must not be inferred from solver success.
