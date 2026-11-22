# GDEC Language Specification — Implemented Profile 0.1

**Status:** Normative description of the implemented Phase 5.1.3 language frontend  
**Implementation:** Lark LALR parser, AST transformer and SemanticAnalyzer  
**Compatibility:** Existing source programs are to remain valid unless a future language version explicitly states otherwise.

## 1. Scope and conformance terminology

This document specifies what the current parser and semantic analyser accept. It deliberately does not specify proposed features as if they already existed.

The words MUST, MUST NOT, SHOULD and MAY express requirements for implementations claiming conformance to this profile.

The language currently describes one named engineering problem per source file and lowers it to the elasticity-specific ProblemIR. The profile is not a general equation language and is not yet a general multiphysics language.

## 2. Concrete syntax

The current Lark grammar is equivalent to the following grammar, with token definitions inherited from Lark's common terminals:

~~~text
start          ::= problem
problem        ::= "problem" CNAME "{" statement* "}"
statement      ::= CNAME "=" expression
expression     ::= function_call | CNAME | SIGNED_NUMBER | ESCAPED_STRING
function_call  ::= CNAME "(" [argument_list] ")"
argument_list  ::= argument ("," argument)* [","]
argument       ::= CNAME "=" expression | expression

CNAME          ::= Lark common.CNAME
SIGNED_NUMBER  ::= Lark common.SIGNED_NUMBER
ESCAPED_STRING ::= Lark common.ESCAPED_STRING
COMMENT        ::= "#" characters_until_newline
                 | "//" characters_until_newline
WHITESPACE     ::= Lark common.WS
~~~

Whitespace and COMMENT tokens are ignored. The parser uses Lark's LALR parser.

### 2.1 Consequences of the grammar

- Exactly one problem block is accepted by the start rule.
- A problem name and declaration names use CNAME identifiers.
- A declaration has one expression on its right-hand side.
- Function calls can syntactically contain positional and named arguments, including nested calls.
- A trailing comma in an argument list is syntactically accepted.
- Comments beginning with # or // are ignored.
- Arithmetic operators, comparison operators, arrays, lists, maps, imports, user-defined functions and multiple problem blocks are not part of this profile.
- Boolean words are parsed as identifiers, not as a dedicated Boolean token.
- Numeric tokens are converted to Python float by the AST transformer; the original numeric spelling is retained in NumberLiteral.raw.
- String handling currently removes the surrounding quote characters. Full escape-sequence semantics are not specified by this implementation and MUST NOT be assumed.

Syntactic acceptance does not imply semantic acceptance. For example, a generic positional argument is parseable but most current engineering constructors require named arguments.

## 3. Abstract syntax

The current AST contains:

- ProblemNode: problem name, ordered statements and source location.
- Statement: declaration key, expression value and source location.
- Identifier: identifier text.
- NumberLiteral: floating-point value, original token text and source location.
- StringLiteral: string value and source location.
- FunctionCall: function name, ordered positional arguments, named-argument mapping and source location.
- SourceLocation: one-based line and column.

The AST is a syntax tree, not the canonical engineering model. It preserves the declaration structure needed by the current analyser but does not represent dimensions, coordinate frames, fields, equations, weak forms or verification obligations.

## 4. Declaration semantics

The semantic analyser accepts the declaration keys below. Unknown keys MUST be rejected. Singleton declarations MUST NOT occur more than once.

| Declaration | Cardinality | Required / accepted value | Defaults and constraints |
|---|---|---|---|
| physics | exactly one | identifier linear_elasticity | Required; no other physics is implemented |
| geometry | exactly one | rectangle(width, height, thickness) | width and height required named finite positive numbers; thickness defaults to 1.0 |
| material | exactly one | isotropic(E, nu, assumption) | E and nu required named finite numbers; E > 0; -1 < nu < 0.5; assumption defaults to plane_stress and may be plane_stress or plane_strain |
| fix | one or more combined with boundary_condition | boundary(name) or a boundary identifier | At least one fixed boundary is required; valid names: left, right, top, bottom; duplicate fixed boundaries are rejected |
| boundary_condition | alias of fix | Same as fix | Same cardinality and semantics as fix |
| load | one or more | traction(boundary, tx, ty) | boundary required as named argument; tx and ty default to 0.0; all numeric values finite; valid boundary names only |
| objective | exactly one | average_displacement(boundary, component) | Required; boundary defaults to right; component defaults to y; component is x or y |
| accuracy | zero or one | successive_qoi_change(percent) | Defaults to 1.0 percent when omitted; percent must be finite and positive |
| budget | zero or one | max_dofs(value, max_iterations) | Defaults to value 25000 and max_iterations 15; value may be one positional or named argument; both values must be positive whole numbers |
| adaptivity | zero or one | goal_aware, recovery, uniform, dwr, goal_oriented_dwr, optionally as a call with fraction and cost_aware | Defaults to goal_aware, fraction 0.3 and cost_aware true; 0 < fraction <= 1 |
| backend | zero or one | cpu | Defaults to cpu; non-CPU requests are explicitly rejected by the semantic analyser |

The exact implementation remains authoritative if this document and source code disagree. Any discrepancy found during review MUST be recorded and corrected in a follow-up change.

## 5. Constructor argument rules

- Geometry rectangle accepts named width and height, and optional named thickness. Positional arguments are rejected.
- Material isotropic accepts named E and nu, and optional named assumption. Positional arguments are rejected.
- boundary accepts one positional boundary identifier or one named boundary argument, but not both.
- traction accepts named boundary, tx and ty only; boundary is required.
- average_displacement accepts named boundary and component only; both are optional because the analyser supplies defaults.
- successive_qoi_change accepts named percent only; percent is optional because the analyser supplies a default.
- max_dofs accepts one positional value or named value, not both; max_iterations is named.
- An adaptivity strategy may be a bare identifier or a function call with named fraction and cost_aware arguments.
- Duplicate named arguments are rejected during AST construction.

## 6. Cross-declaration invariants

The analyser MUST reject:

1. A traction load applied to a boundary fixed by a Dirichlet condition.
2. An average-displacement objective evaluated on a fixed boundary.
3. Missing required physics, geometry, material, fixed boundary, load or objective declarations.
4. Unsupported physics, geometry, material, objective, accuracy, adaptivity or backend selections.
5. Non-finite numeric values and invalid physical parameter ranges described above.

These are profile-specific checks. They do not establish general dimensional consistency or general PDE well-posedness.

## 7. Unit and physical-type status

The current profile has **no enforceable dimensional type system**.

The implementation stores plain floating-point values. Units appear in field descriptions and documentation (for example, metres, Pascals and displacement units), but the parser does not accept unit-bearing literals and the semantic analyser does not derive or compare dimensions.

Therefore:

- The source values are interpreted according to the field-specific conventions of the current elasticity implementation.
- The compiler MUST NOT claim that it has statically proved dimensional consistency.
- A plain number such as 2.0 has no unit encoded in the AST.
- Unit strings used by the separate DSE evidence models are not a substitute for dimensional type checking.

## 8. Lowering contract

The current frontend lowers ProblemNode to gdec.language.ir.ProblemIR. The current schema identifier is gdec_ir_v0.1.

ProblemIR is an elasticity-specific problem record. It is not the proposed Canonical Engineering IR. It contains geometry, isotropic material data, boundary conditions, traction loads, one average-displacement objective, a successive-QoI-change target, a DOF budget, adaptivity settings and a backend request.

The analyser currently rejects accelerator backend requests. The presence of cuda, hip, sycl or tpu in a Pydantic Literal type does not mean that those devices are executable through the normal FEM runtime.

## 9. Diagnostics and source mapping

Parser and semantic errors expose a message and, where available, a one-based source line and column. The current AST does not retain end offsets, source spans, file identity, macro expansion traces or a stable declaration identifier.

A future language revision SHOULD introduce full source spans and stable diagnostic codes without changing the meaning of existing source programs.

## 10. Explicit non-goals of Profile 0.1

The following are not implemented by this profile:

- Arithmetic expression evaluation.
- General variables, constants or parameter expressions.
- Unit-bearing numeric literals or unit conversion.
- Dimensional or tensor-shape type inference.
- General coordinate systems and frames.
- General geometry or mesh declarations.
- General constitutive laws.
- General PDE or weak-form expressions.
- Time-dependent models.
- Multiphysics coupling.
- General QoI expressions or multiple QoIs.
- Uncertainty declarations in the source language.
- Proof or certificate declarations.
- A general-purpose solver or backend selection language.

## 11. Evolution and compatibility policy

Profile 0.1 is the compatibility baseline. New syntax MUST be introduced only through a versioned language change proposal containing:

1. A grammar delta.
2. Semantic typing and validation rules.
3. AST representation changes.
4. Canonical IR lowering rules.
5. Valid and invalid conformance examples.
6. Compatibility and diagnostic expectations.
7. Tests proving existing examples retain their meaning.

The next language increment SHOULD add explicit quantities and dimensions only after the unit algebra and canonical IR contracts are reviewed. It MUST NOT silently reinterpret existing bare numeric fields.

## 12. Implementation traceability

Primary implementation files:

- src/gdec/language/grammar.lark
- src/gdec/language/ast.py
- src/gdec/language/parser.py
- src/gdec/language/semantic.py
- src/gdec/language/ir.py
- tests/test_language.py
- tests/test_ir.py

This specification describes the Phase 5.1.3 baseline. A future change MUST update the conformance matrix and relevant tests in the same pull request.
