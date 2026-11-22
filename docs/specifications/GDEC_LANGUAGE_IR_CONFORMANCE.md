# GDEC Language and IR Conformance Matrix

**Baseline:** Phase 5.1.3, commit d532cae8a16d5c2c2465d73175efd004d295aee9  
**Purpose:** Prevent implemented behaviour, proposed semantics and future work from being conflated.

## 1. Implemented language profile 0.1

| Requirement | Current implementation | Status |
|---|---|---|
| Single named problem block | Lark start rule and ProblemNode | Implemented |
| Identifiers, numbers, strings | CNAME, SIGNED_NUMBER, ESCAPED_STRING | Implemented |
| Function calls with positional/named args | FunctionCall AST | Implemented syntactically |
| Comments and whitespace | #, // and Lark WS ignored | Implemented |
| Arithmetic expressions | No grammar productions | Not implemented |
| Unit-bearing literals | No grammar or AST type | Not implemented |
| Dimensional analysis | No dimension algebra | Not implemented |
| General equations / weak forms | No AST or IR representation | Not implemented |
| One 2D linear-elasticity model | SemanticAnalyzer and ProblemIR | Implemented |
| CPU-only normal FEM execution | Current runtime path | Implemented |
| General accelerator execution | Backend requests rejected by semantic analyser | Not implemented in normal FEM path |
| General canonical engineering IR | Current ProblemIR is elasticity-specific | Proposed only |
| Independent certificate checker | No complete checker interface or certificate implementation | Not implemented |

## 2. Required parser conformance cases

The following fixtures SHOULD be added to the automated parser suite before claiming formal conformance to Profile 0.1.

### Positive syntax fixtures

1. Minimal problem block with one declaration.
2. Full existing cantilever example.
3. Comments using #.
4. Comments using //.
5. Whitespace and newlines between tokens.
6. Function call with positional arguments.
7. Function call with named arguments.
8. Mixed positional and named arguments where the semantic constructor permits it.
9. Trailing comma.
10. Negative and scientific-notation numbers.
11. Quoted strings.
12. Nested function calls at the parser layer.

### Negative syntax fixtures

1. Missing problem identifier.
2. Missing opening or closing brace.
3. Missing equals sign.
4. Missing right-hand expression.
5. Unterminated string.
6. Missing closing parenthesis.
7. Invalid token between declarations.
8. Two problem blocks in one file.
9. Arithmetic expression such as width=2.0 * 3.0.
10. Duplicate named argument.

Parser-only acceptance MUST be separated from semantic acceptance. A nested function call may parse but remain invalid for the current elasticity constructors.

## 3. Required semantic conformance cases

The semantic test suite SHOULD explicitly cover:

- required declaration omissions;
- unknown and duplicate singleton declarations;
- repeated fix and load declarations;
- fix and boundary_condition alias handling;
- duplicate fixed boundaries;
- unsupported physics, geometry, material, objective and backend;
- unknown and missing constructor arguments;
- positional versus named argument constraints;
- all numerical finiteness and range conditions;
- conflicting fixed and traction boundaries;
- objective on a fixed boundary;
- defaults for thickness, material assumption, objective, accuracy, budget, adaptivity and backend.

## 4. Canonical IR future acceptance matrix

These tests are acceptance criteria for a future implementation; they are not tests that currently pass.

| Test | Expected result |
|---|---|
| 2 m + 300 mm | Valid; canonical result 2.3 m |
| 2 m + 3 s | Compile-time dimensional error |
| 70 GPa assigned to Young's modulus | Valid pressure dimension |
| 70 GPa assigned to displacement | Compile-time dimensional error |
| 1 MPa traction | Valid pressure dimension |
| 5 mm displacement | Valid length dimension |
| Gradient of displacement by length | Dimensionless strain |
| Divergence of stress | Force per volume |
| Vector addition in incompatible frames | Rejected unless explicit valid transform is applied |
| Field used on unrelated domain | Rejected |
| Dangling entity reference | Rejected |
| Duplicate stable entity ID | Rejected |
| Unsupported EIR major version | Rejected |
| Solver payload says verified=true without checker result | Not accepted as a certificate |
| Requested CUDA but CPU used | Execution record MUST state CPU; no CUDA success claim |

## 5. Migration acceptance criteria

The compatibility migration is acceptable only when:

1. Existing .gdc examples still parse and lower to the current ProblemIR.
2. Existing ProblemIR JSON round-trips without semantic change.
3. Existing numerical results remain equivalent within declared tolerances.
4. Legacy diagnostics remain stable unless a documented improvement is approved.
5. The canonical IR adapter is one-way and explicit; it does not silently rewrite legacy source.
6. The old runtime remains usable until the canonical path passes parity tests.
7. New unit checks reject invalid inputs before numerical execution.
8. A failed migration does not mutate or corrupt the legacy ProblemIR.

## 6. Evidence labels

Use these labels in reports:

- IMPLEMENTED: code exists in the referenced branch.
- TESTED: an identified automated test exercises the behaviour.
- CI-VERIFIED: the identified GitHub Actions run passed for the exact commit.
- INDEPENDENTLY-REPRODUCED: a separate implementation or external user reproduced the result.
- PROPOSED: design only; no implementation claim.
- NOT-IMPLEMENTED: explicitly absent.
- UNKNOWN: not inspected or not established.

A passing test suite is evidence of tested software behaviour. It is not, by itself, evidence of physical validity or a certified numerical error bound.
