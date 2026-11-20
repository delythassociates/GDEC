"""
Tests for Adjoint Sensitivity and QoI Mathematical Validation (v0.2).
"""

from gdec.compiler import GDECCompiler
from gdec.benchmark.adjoint_validation import AdjointValidator


def test_adjoint_qoi_and_force_sensitivity():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    assert comp.success is True

    report = AdjointValidator.validate(comp.ir, nx=6, ny=3)
    # QoI direct trapezoidal boundary integral vs g^T u must match to < 1e-10
    assert report.qoi_direct_agreement_abs_err < 1e-10
    # Force sensitivity dJ/df_k must match adjoint z_k to < 1e-8
    assert report.force_sensitivity_agreement_rel_err < 1e-8
    assert report.is_mathematically_verified is True
    assert len(report.stiffness_sensitivity_sample_results) == 3
