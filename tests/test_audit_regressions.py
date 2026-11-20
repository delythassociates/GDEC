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


def test_combined_efficiency_claim_requires_dof_and_time_advantage_vs_both_baselines():
    from types import SimpleNamespace

    from gdec.benchmark.runner import BenchmarkRunner

    def strategy():
        return SimpleNamespace(
            target_achieved=True,
            final_dofs=1000,
            total_execution_time_sec=1.0,
            final_reference_error_pct=0.5,
        )

    results = {
        "goal_aware": strategy(),
        "uniform": strategy(),
        "recovery": strategy(),
    }
    comparison = SimpleNamespace(
        threshold_pct=1.0,
        results={
            "goal_aware": SimpleNamespace(achieved=True, dofs_at_target=1000),
            "uniform": SimpleNamespace(achieved=True, dofs_at_target=2000),
            "recovery": SimpleNamespace(achieved=True, dofs_at_target=1500),
        },
        dof_ratio_unif_over_goal=2.0,
        time_ratio_unif_over_goal=0.8,  # Fewer DOFs, but slower wall-clock time.
        dof_ratio_rec_over_goal=1.5,
        time_ratio_rec_over_goal=1.2,
    )

    evaluation = BenchmarkRunner.__new__(BenchmarkRunner)._evaluate_hypothesis(
        results, None, [comparison]
    )

    assert evaluation["dof_efficiency_supported"] is True
    assert evaluation["wall_clock_efficiency_supported"] is False
    assert evaluation["hypothesis_supported"] is False
