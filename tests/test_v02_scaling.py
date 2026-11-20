"""
Tests for Discretization Scalability Runner (v0.2).
"""

from gdec.compiler import GDECCompiler
from gdec.benchmark.scaling import ScalabilityRunner


def test_scalability_runner_moderate_scales():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    assert comp.success is True

    # Test small to moderate scale points
    res = ScalabilityRunner.run_scaling(comp.ir, scale_targets=[1000, 3000])

    assert len(res.points) == 2
    assert all(p.completed for p in res.points)
    assert res.points[0].actual_dofs < res.points[1].actual_dofs
    assert res.points[0].total_time_sec > 0.0
    assert res.max_dofs_achieved > 0
