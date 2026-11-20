"""
Compiler validation and error presentation utilities.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CompilerDiagnostic:
    severity: str  # "error" or "warning"
    message: str
    line: int = 0
    column: int = 0
    source_context: str = ""

    def format(self) -> str:
        prefix = f"[{self.severity.upper()}]"
        pos = f" at line {self.line}, col {self.column}" if self.line > 0 else ""
        res = f"{prefix}{pos}: {self.message}"
        if self.source_context:
            res += f"\n{self.source_context}"
        return res
