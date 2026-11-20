"""
Abstract Syntax Tree (AST) definitions for GDEC Language.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceLocation:
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(kw_only=True)
class ASTNode:
    loc: Optional[SourceLocation] = None


@dataclass(kw_only=True)
class Expression(ASTNode):
    pass


@dataclass(kw_only=True)
class Identifier(Expression):
    name: str


@dataclass(kw_only=True)
class NumberLiteral(Expression):
    value: float
    raw: str = ""


@dataclass(kw_only=True)
class StringLiteral(Expression):
    value: str


@dataclass(kw_only=True)
class FunctionCall(Expression):
    func_name: str
    positional_args: List[Expression] = field(default_factory=list)
    named_args: Dict[str, Expression] = field(default_factory=dict)


@dataclass(kw_only=True)
class Statement(ASTNode):
    key: str
    value: Expression


@dataclass(kw_only=True)
class ProblemNode(ASTNode):
    name: str
    statements: List[Statement] = field(default_factory=list)

    def get_statement(self, key: str) -> Optional[Statement]:
        for s in self.statements:
            if s.key == key:
                return s
        return None

    def get_statements(self, key: str) -> List[Statement]:
        return [s for s in self.statements if s.key == key]
