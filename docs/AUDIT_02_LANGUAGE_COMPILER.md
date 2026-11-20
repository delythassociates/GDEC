# GDEC Audit Phase 2: Language, Parser, and Compiler Audit

**Audit Date**: 2026-11-20  
**Auditor**: Independent Technical Software Auditor & Verification Specialist  
**Target Codebase**: GDEC Version 0.2 (`src/gdec/language/`, `src/gdec/compiler/`)  
**Status**: VERIFIED  

---

## 1. Executive Summary

A forensic review and empirical execution of the GDEC domain-specific language (DSL), Lark parser, AST generation, semantic analysis, and Intermediate Representation (IR) compiler pipeline was conducted.

The language and compiler subsystem is **technically sound, genuinely implemented, and free of hardcoded bypasses**. Parameter variations in `.gdc` source files propagate faithfully through the AST and IR into the numerical finite element solver.

---

## 2. Verification of Language & Parser Architecture

### 2.1 Grammar Specification (`src/gdec/language/grammar.lark`)
- **Inspection**: `grammar.lark` (25 lines) defines an EBNF grammar using Lark's declarative syntax.
- **Rules**: Defines statements `CNAME "=" expr`, function calls `CNAME "(" [arg_list] ")"`, named arguments `CNAME "=" expr`, positional arguments, numbers, strings, and identifiers.
- **Safety**: The grammar prohibits Python statements, imports, arithmetic operators (`+`, `-`, `*`, `/` outside numeric literals), control flow, and arbitrary expressions.
- **Verdict**: **VERIFIED**. Genuine formal grammar.

### 2.2 Parser Implementation (`src/gdec/language/parser.py`)
- **Inspection**: Class `GDECParser` initializes `Lark(..., parser="lalr", maybe_placeholders=False)` on line 110.
- **AST Lowering**: Class `_TreeToAST` subclasses `lark.Transformer` (lines 42–102), translating parse tokens directly into typed dataclass nodes (`ProblemNode`, `Statement`, `FunctionCall`, `Identifier`, `NumberLiteral`, `StringLiteral`).
- **Source Coordinates**: Tokens extract `line` and `column` numbers, encapsulated into `SourceLocation` dataclasses for every AST node.
- **Verdict**: **VERIFIED**. Uses genuine LALR parser and AST transformer without `eval()` or `exec()`.

---

## 3. Semantic Validation and Error Diagnostics

We tested semantic validation against deliberate syntax and parameter errors using `scratch/test_compiler_audit.py`:

| Test Case | Injected Fault | Expected Behavior | Observed Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| Negative Young's Modulus | `E = -70e9` | Semantic rejection | `Semantic Error: Young's modulus 'E' must be a strictly positive number (received -70000000000.0).` | **VERIFIED** |
| Zero Young's Modulus | `E = 0.0` | Semantic rejection | `Semantic Error: Young's modulus 'E' must be a strictly positive number (received 0.0).` | **VERIFIED** |
| Unphysical Poisson Ratio | `nu = 0.5` (plane strain) | Semantic rejection | `Semantic Error: Poisson's ratio 'nu' must satisfy -1.0 < nu < 0.5 (received 0.5).` | **VERIFIED** |
| Unsupported Physics | `physics = quantum_gravity` | Semantic rejection | `Semantic Error: Unsupported physics model 'quantum_gravity'. Version 0.1 only supports 'linear_elasticity'.` | **VERIFIED** |
| Invalid Boundary Name | `boundary = ceiling` | Semantic rejection | `Semantic Error: Invalid load boundary 'ceiling'. Must be one of {'top', 'right', 'bottom', 'left'}.` | **VERIFIED** |
| Unsupported Backend | `backend = tpu` | Semantic rejection | `Semantic Error: Unknown backend device 'tpu'. Supported: 'cpu', 'cuda', 'hip', 'sycl'.` | **VERIFIED** |
| Non-positive Dimensions | `height = 0.0` | Semantic rejection | `Semantic Error: Geometry 'height' must be a positive number.` | **VERIFIED** |
| Arbitrary Code Injection | `physics = __import__("os").system(...)` | Syntax rejection | `Syntax Error: Syntax error unexpected input 's = __import__("os").system("echo VULNER'` | **VERIFIED** |

---

## 4. Parameter Sensitivity & Anti-Hardcoding Audit

To definitively test whether the solver uses hardcoded outputs or truly responds to compiled input, identical cantilever simulations were compiled with varied physical parameters:

### Test 4.1: Material Stiffness Sensitivity ($E$)
- Base Case: Aluminium ($E = 70.0\text{ GPa}$): Solved initial $J_{\text{alum}} = -1.594282 \times 10^{-3}$ m.
- Modified Case: Structural Steel ($E = 210.0\text{ GPa}$): Solved initial $J_{\text{steel}} = -5.314273 \times 10^{-4}$ m.
- Ratio $\frac{J_{\text{alum}}}{J_{\text{steel}}} = \mathbf{3.000000}$ (exact inverse proportionality $E_{\text{steel}} / E_{\text{alum}} = 3.0$).

### Test 4.2: Load Linearity Sensitivity ($t_y$)
- Base Case: Traction $t_y = -1.0\text{ MPa}$: Initial $J = -1.594282 \times 10^{-3}$ m.
- Doubled Case: Traction $t_y = -2.0\text{ MPa}$: Initial $J = -3.188564 \times 10^{-3}$ m.
- Ratio $\frac{J_{2\times}}{J_{1\times}} = \mathbf{2.000000}$ (exact physical linear elasticity scaling).

**Conclusion**: The finite element engine and runtime are genuinely coupled to the compiled IR. No hardcoded or pre-canned solution outputs exist.

---

## 5. Intermediate Representation (IR) Audit

- **Schema Engine**: Pydantic v2 (`src/gdec/language/ir.py`).
- **Roundtrip Fidelity**: Serializing to JSON (`model_dump_json()`) and deserializing (`model_validate_json()`) produces an exact bit-identical `ProblemIR` object (`deserialized == original` is `True`).
- **Schema Versioning Finding (LOW Severity)**:
  `src/gdec/language/ir.py` line 13 still specifies `IR_SCHEMA_VERSION = "gdec_ir_v0.1"` despite the codebase being upgraded to v0.2. While harmless to execution, schema version tagging was not bumped to `v0.2`.

---

## 6. Audit Verdict: Language and Compiler
- **Severity**: PASS (No critical or high issues).
- **Subsystem Integrity**: **VERIFIED**.
