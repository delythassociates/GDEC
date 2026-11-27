"""
Tests for GDEC Command-Line Interface.
"""

from gdec.cli import main
import sys


def test_cli_hardware(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gdec", "hardware"])
    assert main() == 0


def test_cli_validate(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gdec", "validate", "examples/cantilever.gdc"])
    assert main() == 0


def test_cli_compile(monkeypatch, tmp_path):
    out = tmp_path / "compiled_ir.json"
    monkeypatch.setattr(sys, "argv", ["gdec", "compile", "examples/cantilever.gdc", "-o", str(out)])
    assert main() == 0
    assert out.exists()


def test_cli_run(monkeypatch, tmp_path):
    out = tmp_path / "cantilever_evidence.json"
    monkeypatch.setattr(
        sys, "argv", ["gdec", "run", "examples/cantilever.gdc", "--strategy", "goal_aware", "-o", str(out)]
    )
    assert main() == 0
    assert out.is_file()
