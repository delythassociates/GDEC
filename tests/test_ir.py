"""
Tests for Intermediate Representation (IR) serialization and deserialization.
"""

from gdec.compiler import GDECCompiler
from gdec.language.ir import ProblemIR


def test_ir_roundtrip_json():
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    assert res.success is True
    ir = res.ir

    json_str = ir.to_json(indent=2)
    deserialized = ProblemIR.from_json(json_str)

    assert deserialized.name == ir.name
    assert deserialized.geometry.width == ir.geometry.width
    assert deserialized.material.E == ir.material.E
    assert deserialized.accuracy.percent == ir.accuracy.percent
    assert deserialized.budget.value == ir.budget.value
    assert deserialized.schema_version == "gdec_ir_v0.1"
