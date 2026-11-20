"""
Tests for GDEC Compiler frontend and diagnostics.
"""

from pathlib import Path
from gdec.compiler import GDECCompiler


def test_compiler_success():
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    assert res.success is True
    assert res.ir is not None
    assert res.ir.name == "CantileverDemo"
    assert res.ir.material.E == 70e9
    assert res.ir.material.nu == 0.33
    assert res.ir.schema_version == "gdec_ir_v0.1"


def test_compiler_source_reproducibility():
    compiler = GDECCompiler()
    src = Path("examples/cantilever.gdc").read_text(encoding="utf-8")
    res1 = compiler.compile_source(src)
    res2 = compiler.compile_source(src)
    assert res1.ir.to_json() == res2.ir.to_json()


def test_compiler_diagnostic_context():
    compiler = GDECCompiler()
    bad_src = """problem BadProb {
    physics = unknown_model
}"""
    res = compiler.compile_source(bad_src)
    assert res.success is False
    assert len(res.diagnostics) > 0
    diag = res.diagnostics[0]
    assert diag.line == 2
    assert "unknown_model" in diag.message
    assert "^" in diag.source_context
