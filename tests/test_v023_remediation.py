"""
Unit and integration tests for GDEC v0.2.3 remediation release.
Validates:
- Point displacement QoI and adjoint duality
- Strict compiler and semantic validation (duplicate args, invalid numbers, non-physical values, top-level checks)
- ZZ recovery with degree-2 (3-point) Gauss/Hammer quadrature
- Topological element refinement cost model
- Rigorous multi-dimensional hypothesis evaluator
"""

import pytest
import numpy as np

from gdec.compiler import GDECCompiler
from gdec.language.parser import GDECParser, GDECParseError
from gdec.language.semantic import SemanticAnalyzer, GDECSemanticError
from gdec.language.ir import ObjectiveIR
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.estimators import (
    RefinementEstimator,
)
from gdec.benchmark.evaluator import (
    EqualAccuracyEvaluator,
    EqualAccuracyComparison,
    ThresholdEvaluationResult,
)


def test_point_qoi_adjoint_duality():
    """Verify that the adjoint formulation for a point QoI satisfies g^T u = z^T f to high precision."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=20, ny=5)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    px, py = 2.0, 0.0
    obj = ObjectiveIR(kind="point_displacement", boundary=None, component="y", point_x=px, point_y=py)
    res = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, objective=obj, solve_adjoint=True)

    # Duality check: res.g^T u == res.z^T f
    u_dot_g = float(res.g.T @ res.u)
    z_dot_f = float(res.z.T @ res.f)

    rel_diff = abs(u_dot_g - z_dot_f) / max(abs(u_dot_g), 1e-12)
    assert rel_diff < 1e-10
    assert abs(res.qoi - u_dot_g) < 1e-14


def test_point_qoi_compiler_end_to_end():
    """Verify compiling and planning a .gdc program with point_displacement objective."""
    source = """
    problem PointTest {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5, thickness=0.02)
        material = isotropic(E=70e9, nu=0.33, assumption=plane_stress)
        fix = boundary(left)
        load = traction(boundary=right, tx=0.0, ty=-1.0e6)
        objective = point_displacement(x=2.0, y=0.0, component=y)
        accuracy = successive_qoi_change(percent=1.0)
        budget = max_dofs(value=5000)
    }
    """
    res = GDECCompiler().compile_source(source)
    assert res.success is True
    assert res.ir.objective.kind == "point_displacement"
    assert res.ir.objective.point_x == 2.0
    assert res.ir.objective.point_y == 0.0
    assert res.ir.objective.component == "y"


def test_point_qoi_validation_errors():
    """Verify point_displacement validates bounding box and rejects missing/invalid parameters."""
    compiler = GDECCompiler()

    # Out of bounds x
    bad_x = """
    problem BadX {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5, thickness=0.02)
        material = isotropic(E=70e9, nu=0.33)
        fix = boundary(left)
        load = traction(boundary=right, tx=0.0, ty=-1.0e6)
        objective = point_displacement(x=2.5, y=0.0, component=y)
        accuracy = successive_qoi_change(percent=1.0)
        budget = max_dofs(value=5000)
    }
    """
    res = compiler.compile_source(bad_x)
    assert res.success is False
    assert any("outside domain bounds" in d.message for d in res.diagnostics)

    # Disallow boundary parameter in point_displacement
    bad_arg = """
    problem BadArg {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5, thickness=0.02)
        material = isotropic(E=70e9, nu=0.33)
        fix = boundary(left)
        load = traction(boundary=right, tx=0.0, ty=-1.0e6)
        objective = point_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=1.0)
        budget = max_dofs(value=5000)
    }
    """
    res = compiler.compile_source(bad_arg)
    assert res.success is False


def test_parser_duplicate_named_args():
    """Verify parser rejects duplicate named arguments in calls."""
    source = """
    problem DupArg {
        geometry = rectangle(width=2.0, width=3.0, height=0.5)
    }
    """
    with pytest.raises(GDECParseError) as exc_info:
        GDECParser().parse(source)
    assert "Duplicate named argument" in str(exc_info.value)


def test_semantic_unknown_top_level_rejected():
    """Verify semantic analyzer rejects unrecognized top-level declarations."""
    source = """
    problem UnknownTopLevel {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5)
        material = isotropic(E=70e9, nu=0.33)
        optimizer = gradient_descent
    }
    """
    res = GDECCompiler().compile_source(source)
    assert res.success is False
    assert any("Unknown top-level declaration 'optimizer'" in d.message for d in res.diagnostics)


def test_semantic_duplicate_declaration_rejected():
    """Verify semantic analyzer rejects multiple declarations of single-instance blocks."""
    source = """
    problem DupBlock {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5)
        material = isotropic(E=70e9, nu=0.33)
        material = isotropic(E=80e9, nu=0.30)
    }
    """
    res = GDECCompiler().compile_source(source)
    assert res.success is False
    assert any("Duplicate declaration of 'material'" in d.message for d in res.diagnostics)


def test_semantic_nan_inf_rejected():
    """Verify semantic analyzer rejects NaN and infinity."""
    source = """
    problem NanVal {
        physics = linear_elasticity
        geometry = rectangle(width=NaN, height=0.5)
        material = isotropic(E=70e9, nu=0.33)
    }
    """
    res = GDECCompiler().compile_source(source)
    assert res.success is False
    assert any("must be a numeric value" in d.message for d in res.diagnostics)


def test_semantic_non_physical_properties():
    """Verify semantic analyzer rejects unphysical materials and geometries."""
    # Negative Young's modulus
    res1 = GDECCompiler().compile_source("""
    problem NegE {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5)
        material = isotropic(E=-70e9, nu=0.33)
    }
    """)
    assert res1.success is False
    assert any("strictly positive number" in d.message for d in res1.diagnostics)

    # Poisson's ratio >= 0.5
    res2 = GDECCompiler().compile_source("""
    problem BadNu {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5)
        material = isotropic(E=70e9, nu=0.55)
    }
    """)
    assert res2.success is False
    assert any("Poisson's ratio" in d.message for d in res2.diagnostics)


def test_unsupported_device_rejected():
    """Verify device backend validation rejects unsupported GPU backends with clear message."""
    source = """
    problem CudaTest {
        physics = linear_elasticity
        geometry = rectangle(width=2.0, height=0.5)
        material = isotropic(E=70e9, nu=0.33)
        fix = boundary(left)
        load = traction(boundary=right, tx=0.0, ty=-1e6)
        objective = average_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=1.0)
        budget = max_dofs(value=5000)
        backend = cuda
    }
    """
    res = GDECCompiler().compile_source(source)
    assert res.success is False
    assert any("no GPU accelerator hardware or CUDA backend is available in GDEC v0.2.3" in d.message for d in res.diagnostics)


def test_element_refinement_costs():
    """Verify topological element refinement cost model produces valid cost factors."""
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=10, ny=4)
    costs = RefinementEstimator.estimate_element_refinement_costs(mesh)
    assert len(costs) == mesh.mesh.t.shape[1]
    # Costs must be strictly positive and bounded
    assert np.all(costs >= 2.0)
    assert np.all(costs <= 6.0)
    # Boundary elements should have higher cost than pure interior elements
    assert np.max(costs) > np.min(costs)


def test_zz_recovery_quadrature_exactness():
    """Verify ZZ recovery integration accurately computes positive energy seminorm."""
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=8, ny=3)
    loads = [("right", 0.0, -1e6)]
    bcs = [("left", ["x", "y"])]

    sol = solver.solve(mesh, loads=loads, fixed_boundaries=bcs)
    estimator = RefinementEstimator(c)
    res = estimator.compute_zz_recovery_indicator(mesh, sol)

    assert len(res.indicators) == mesh.mesh.t.shape[1]
    assert np.all(res.indicators >= 0.0)
    assert np.sum(res.indicators) > 0.0
    assert len(res.priorities) == mesh.mesh.t.shape[1]


def test_hypothesis_evaluator_rigorous():
    """Verify hypothesis evaluator cleanly distinguishes between DOF efficiency and runtime efficiency."""
    c1 = EqualAccuracyComparison(
        threshold_pct=1.0,
        results={
            "goal_aware": ThresholdEvaluationResult(
                strategy="goal_aware", threshold_pct=1.0, achieved=True,
                iteration_reached=2, dofs_at_target=1000, elements_at_target=500, time_to_target_sec=0.25,
                peak_memory_mb=50.0, qoi_at_target_mm=-1.90,
                actual_ref_error_pct=0.8, runtime_convergence_pct=0.9,
                status_note="Target met",
            ),
            "uniform": ThresholdEvaluationResult(
                strategy="uniform", threshold_pct=1.0, achieved=True,
                iteration_reached=3, dofs_at_target=2500, elements_at_target=1200, time_to_target_sec=0.20,
                peak_memory_mb=60.0, qoi_at_target_mm=-1.90,
                actual_ref_error_pct=0.7, runtime_convergence_pct=0.8,
                status_note="Target met",
            ),
        },
        dof_ratio_unif_over_goal=2.5,
        time_ratio_unif_over_goal=0.8,
    )

    hyp = EqualAccuracyEvaluator.evaluate_hypothesis_rigorous([c1])
    assert hyp.dof_efficiency_vs_uniform == "SUPPORTED"
    assert hyp.runtime_efficiency_vs_uniform == "NOT_SUPPORTED"
    assert hyp.combined_computational_cost_superiority == "PARTIALLY_SUPPORTED"
    assert hyp.overall_verdict == "PARTIALLY_SUPPORTED"
