"""Regression tests for defects found in the v0.2.2 deep audit."""

from pathlib import Path

import numpy as np

from gdec.compiler import GDECCompiler
from gdec.fem.elasticity import ConstitutiveTensor
from gdec.fem.postprocess import PostProcessor


def _cantilever_source() -> str:
    return Path("examples/cantilever.gdc").read_text(encoding="utf-8")


def test_point_displacement_is_rejected_until_implemented():
    source = _cantilever_source().replace(
        "average_displacement(", "point_displacement("
    )
    result = GDECCompiler().compile_source(source)

    assert result.success is False
    assert result.ir is None
    assert "point_displacement is rejected" in result.diagnostics[0].message


def test_invalid_ir_constraints_return_compiler_diagnostic():
    source = _cantilever_source().replace(
        "adaptivity = goal_aware",
        "adaptivity = goal_aware(fraction=1.5)",
    )
    result = GDECCompiler().compile_source(source)

    assert result.success is False
    assert result.ir is None
    assert "IR validation error" in result.diagnostics[0].message


def test_plane_strain_von_mises_includes_out_of_plane_stress():
    constitutive = ConstitutiveTensor.from_properties(
        E=210e9, nu=0.3, assumption="plane_strain"
    )
    post = PostProcessor(constitutive)
    sx = np.array([100.0])
    sy = np.array([40.0])
    txy = np.array([10.0])

    sigma_zz = 0.3 * (sx + sy)
    expected = np.sqrt(
        0.5 * ((sx - sy) ** 2 + (sy - sigma_zz) ** 2 + (sigma_zz - sx) ** 2)
        + 3.0 * txy**2
    )

    np.testing.assert_allclose(post._von_mises(sx, sy, txy), expected)


def test_plane_stress_von_mises_uses_zero_out_of_plane_stress():
    constitutive = ConstitutiveTensor.from_properties(
        E=210e9, nu=0.3, assumption="plane_stress"
    )
    post = PostProcessor(constitutive)
    sx = np.array([100.0])
    sy = np.array([40.0])
    txy = np.array([10.0])

    expected = np.sqrt(sx**2 - sx * sy + sy**2 + 3.0 * txy**2)
    np.testing.assert_allclose(post._von_mises(sx, sy, txy), expected)
