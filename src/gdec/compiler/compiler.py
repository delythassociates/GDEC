"""
GDEC Compiler Frontend.
Converts GDEC engineering language source code into verified Typed ProblemIR.
Pipeline:
  Source -> Lexer/Parser -> AST -> Semantic Analyzer -> Typed IR -> JSON Serialization
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from gdec.language.parser import GDECParser, GDECParseError
from gdec.language.semantic import SemanticAnalyzer, GDECSemanticError
from gdec.language.ast import ProblemNode
from gdec.language.ir import ProblemIR
from gdec.compiler.validation import CompilerDiagnostic


@dataclass
class CompilationResult:
    success: bool
    ast: Optional[ProblemNode] = None
    ir: Optional[ProblemIR] = None
    diagnostics: List[CompilerDiagnostic] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)


class GDECCompiler:
    def __init__(self):
        self.parser = GDECParser()
        self.analyzer = SemanticAnalyzer()

    def compile_source(self, source_text: str) -> CompilationResult:
        diagnostics: List[CompilerDiagnostic] = []
        try:
            ast = self.parser.parse(source_text)
        except GDECParseError as e:
            lines = source_text.splitlines()
            ctx = ""
            if 1 <= e.line <= len(lines):
                line_content = lines[e.line - 1]
                pointer = " " * (max(0, e.column - 1)) + "^"
                ctx = f"  {e.line} | {line_content}\n    | {pointer}"
            diagnostics.append(
                CompilerDiagnostic(
                    severity="error",
                    message=f"Syntax Error: {e.message}",
                    line=e.line,
                    column=e.column,
                    source_context=ctx,
                )
            )
            return CompilationResult(success=False, diagnostics=diagnostics)

        try:
            ir = self.analyzer.analyze(ast)
        except GDECSemanticError as e:
            line = e.loc.line if e.loc else 0
            col = e.loc.column if e.loc else 0
            lines = source_text.splitlines()
            ctx = ""
            if 1 <= line <= len(lines):
                line_content = lines[line - 1]
                pointer = " " * (max(0, col - 1)) + "^"
                ctx = f"  {line} | {line_content}\n    | {pointer}"
            diagnostics.append(
                CompilerDiagnostic(
                    severity="error",
                    message=f"Semantic Error: {e.message}",
                    line=line,
                    column=col,
                    source_context=ctx,
                )
            )
            return CompilationResult(success=False, ast=ast, diagnostics=diagnostics)

        return CompilationResult(success=True, ast=ast, ir=ir, diagnostics=diagnostics)

    def compile_file(self, file_path: str | Path) -> CompilationResult:
        p = Path(file_path)
        if not p.exists():
            return CompilationResult(
                success=False,
                diagnostics=[CompilerDiagnostic(severity="error", message=f"File not found: {p}")],
            )
        if p.suffix != ".gdc":
            # Warning for non-.gdc extension
            diag = CompilerDiagnostic(
                severity="warning",
                message=f"File '{p.name}' does not have standard '.gdc' extension.",
            )
        else:
            diag = None

        with open(p, "r", encoding="utf-8") as f:
            source = f.read()

        result = self.compile_source(source)
        if diag:
            result.diagnostics.insert(0, diag)
        return result
