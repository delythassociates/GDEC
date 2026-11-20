"""
Parser for GDEC Language using Lark.
Converts source text into AST without arbitrary expression evaluation.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, List, Union

from lark import Lark, Transformer, v_args, UnexpectedInput, Token, Tree
from gdec.language.ast import (
    SourceLocation,
    Expression,
    Identifier,
    NumberLiteral,
    StringLiteral,
    FunctionCall,
    Statement,
    ProblemNode,
)


class GDECParseError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0, source_text: str = ""):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.source_text = source_text

    def __str__(self) -> str:
        ctx = ""
        if self.source_text and self.line > 0:
            lines = self.source_text.splitlines()
            if 1 <= self.line <= len(lines):
                line_content = lines[self.line - 1]
                pointer = " " * (max(0, self.column - 1)) + "^"
                ctx = f"\n  {self.line} | {line_content}\n    | {pointer}"
        return f"Parse Error at {self.line}:{self.column}: {self.message}{ctx}"


class _TreeToAST(Transformer):
    def start(self, items: List[Any]) -> ProblemNode:
        return items[0]

    def problem(self, items: List[Any]) -> ProblemNode:
        name_token = items[0]
        statements = items[1:]
        loc = SourceLocation(getattr(name_token, "line", 1), getattr(name_token, "column", 1))
        return ProblemNode(name=str(name_token), statements=statements, loc=loc)

    def statement(self, items: List[Any]) -> Statement:
        key_token, value_expr = items
        loc = SourceLocation(getattr(key_token, "line", 1), getattr(key_token, "column", 1))
        return Statement(key=str(key_token), value=value_expr, loc=loc)

    def identifier(self, items: List[Any]) -> Identifier:
        token = items[0]
        loc = SourceLocation(getattr(token, "line", 1), getattr(token, "column", 1))
        return Identifier(name=str(token), loc=loc)

    def number(self, items: List[Any]) -> NumberLiteral:
        token = items[0]
        raw = str(token)
        loc = SourceLocation(getattr(token, "line", 1), getattr(token, "column", 1))
        return NumberLiteral(value=float(raw), raw=raw, loc=loc)

    def string(self, items: List[Any]) -> StringLiteral:
        token = items[0]
        val = str(token)[1:-1]
        loc = SourceLocation(getattr(token, "line", 1), getattr(token, "column", 1))
        return StringLiteral(value=val, loc=loc)

    def call(self, items: List[Any]) -> FunctionCall:
        func_token = items[0]
        args = items[1] if len(items) > 1 and items[1] is not None else ([], {})
        pos_args, named_args = args
        loc = SourceLocation(getattr(func_token, "line", 1), getattr(func_token, "column", 1))
        return FunctionCall(
            func_name=str(func_token),
            positional_args=pos_args,
            named_args=named_args,
            loc=loc,
        )

    def arg_list(self, items: List[Any]) -> tuple[List[Expression], dict[str, Expression]]:
        pos_args: List[Expression] = []
        named_args: dict[str, Expression] = {}
        for item in items:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
                named_args[item[0]] = item[1]
            elif isinstance(item, Expression):
                pos_args.append(item)
        return pos_args, named_args

    def named_arg(self, items: List[Any]) -> tuple[str, Expression]:
        name_token, expr = items
        return (str(name_token), expr)

    def positional_arg(self, items: List[Any]) -> Expression:
        return items[0]


class GDECParser:
    def __init__(self, grammar_path: Path | None = None):
        if grammar_path is None:
            grammar_path = Path(__file__).parent / "grammar.lark"
        with open(grammar_path, "r", encoding="utf-8") as f:
            grammar_text = f.read()
        self.lark = Lark(grammar_text, parser="lalr", maybe_placeholders=False)
        self.transformer = _TreeToAST()

    def parse(self, text: str) -> ProblemNode:
        try:
            tree = self.lark.parse(text)
            return self.transformer.transform(tree)
        except UnexpectedInput as e:
            raise GDECParseError(
                message=f"Syntax error unexpected input '{e.get_context(text, 20).strip()}'",
                line=getattr(e, "line", 0),
                column=getattr(e, "column", 0),
                source_text=text,
            ) from e
        except Exception as e:
            raise GDECParseError(message=str(e), source_text=text) from e
