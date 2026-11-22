"""
Comprehensive compiler and DSL validation test suite for GDEC.
Verifies that the compiler and semantic analyzer strictly reject invalid
engineering specifications with clear, source-located diagnostics.
"""

import math
import pytest
from pathlib import Path
from pydantic import ValidationError

from gdec.compiler import GDECCompiler
from gdec.language.parser import GDECParser, GDECParseError
from gdec.language.semantic import SemanticAnalyzer, GDECSemanticError
from gdec.language.ir import (
    ProblemIR,
    GeometryIR,
    MaterialIR,
    BoundaryConditionIR,
    TractionLoadIR,
    ObjectiveIR,
    AccuracyTargetIR,
    BudgetIR,
    AdaptivityIR,
    BackendIR,
)


def _base_cantilever_source() -> str:
    return Path("examples/cantilever.gdc").read_text(encoding="utf-8")


# 1. Unknown Top-Level Declarations
def test_unknown_top_level_declaration():
    source = _base_cantilever_source().replace(
        "physics = linear_elasticity", "thermodynamics = conduction"
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Unknown declaration 'thermodynamics'" in result.diagnostics[0].message


# 2. Duplicate Singleton Declarations
@pytest.mark.parametrize("declaration", [
    "physics = linear_elasticity",
    "geometry = rectangle(width=1.0, height=1.0)",
    "material = isotropic(E=1e9, nu=0.3)",
    "objective = average_displacement(boundary=right, component=y)",
    "accuracy = successive_qoi_change(percent=1.0)",
    "budget = max_dofs(value=10000)",
    "adaptivity = goal_aware",
    "backend = cpu",
])
def test_duplicate_singleton_declarations(declaration):
    source = _base_cantilever_source()
    key = declaration.split("=")[0].strip()
    # Append a duplicate declaration at the end of the problem block
    source_dup = source.replace("backend = cpu", f"backend = cpu\n    {declaration}")
    result = GDECCompiler().compile_source(source_dup)
    assert result.success is False
    assert f"Duplicate declaration '{key}'" in result.diagnostics[0].message


# 3. Unknown Named Arguments
def test_unknown_named_argument_geometry():
    source = _base_cantilever_source().replace("width = 2.0,", "width = 2.0,\n        depth = 0.5,")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Unknown argument(s) for 'rectangle'" in result.diagnostics[0].message
    assert "depth" in result.diagnostics[0].message


def test_unknown_named_argument_material():
    source = _base_cantilever_source().replace("E = 70e9,", "E = 70e9,\n        yield_stress = 250e6,")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Unknown argument(s) for 'isotropic'" in result.diagnostics[0].message


def test_unknown_named_argument_load():
    source = _base_cantilever_source().replace("tx = 0.0,", "tx = 0.0,\n        tz = 100.0,")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Unknown argument(s) for 'traction'" in result.diagnostics[0].message


# 4. Duplicate Named Arguments
def test_duplicate_named_argument_rejected_by_parser():
    source = _base_cantilever_source().replace("width = 2.0,", "width = 2.0,\n        width = 3.0,")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Duplicate named argument 'width'" in result.diagnostics[0].message


# 5. Invalid Positional Arguments (Function Arity)
def test_invalid_positional_arguments_in_geometry():
    source = _base_cantilever_source().replace("geometry = rectangle(", "geometry = rectangle(2.0, ")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "takes only named arguments" in result.diagnostics[0].message


def test_invalid_positional_arguments_in_material():
    source = _base_cantilever_source().replace("material = isotropic(", "material = isotropic(70e9, ")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "takes only named arguments" in result.diagnostics[0].message


def test_invalid_positional_arguments_in_traction():
    source = _base_cantilever_source().replace("load = traction(", "load = traction(right, ")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "takes only named arguments" in result.diagnostics[0].message


def test_duplicate_positional_and_named_boundary():
    source = _base_cantilever_source().replace("fix = boundary(left)", "fix = boundary(left, boundary=left)")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "boundary accepts exactly one boundary name" in result.diagnostics[0].message


# 6. Boolean Parsing and Type Confusion
def test_boolean_passed_to_float_geometry_rejected():
    source = _base_cantilever_source().replace("width = 2.0", "width = true")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "must be a finite number" in result.diagnostics[0].message


def test_cost_aware_requires_literal_boolean():
    source = _base_cantilever_source().replace("adaptivity = goal_aware", "adaptivity = goal_aware(cost_aware=1)")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "'cost_aware' must be the literal true or false" in result.diagnostics[0].message


# 7. Integer vs Floating-Point Semantics
def test_fractional_dof_budget_rejected():
    source = _base_cantilever_source().replace("value = 25000", "value = 25000.7")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "positive whole number" in result.diagnostics[0].message


def test_fractional_max_iterations_rejected():
    source = _base_cantilever_source().replace("value = 25000", "value = 25000, max_iterations = 12.3")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "positive whole number" in result.diagnostics[0].message


# 8. Non-Finite Values (NaN and Infinity)
@pytest.mark.parametrize("bad_val", ["nan", "inf", "1e999", "-1e999"])
def test_nonfinite_numeric_values_rejected(bad_val):
    source = _base_cantilever_source().replace("width = 2.0,", f"width = {bad_val},")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "finite number" in result.diagnostics[0].message


# 9. Negative and Zero Physical Parameters
@pytest.mark.parametrize("target,replacement", [
    ("width = 2.0,", "width = 0.0,"),
    ("width = 2.0,", "width = -2.0,"),
    ("height = 0.5,", "height = 0.0,"),
    ("height = 0.5,", "height = -0.5,"),
    ("thickness = 0.02", "thickness = 0.0"),
    ("thickness = 0.02", "thickness = -0.01"),
    ("E = 70e9,", "E = 0.0,"),
    ("E = 70e9,", "E = -70e9,"),
])
def test_negative_or_zero_physical_parameters(target, replacement):
    source = _base_cantilever_source().replace(target, replacement)
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert ("strictly positive" in result.diagnostics[0].message or "positive number" in result.diagnostics[0].message)


# 10. Invalid Material Constants (Poisson's Ratio Bounds)
@pytest.mark.parametrize("bad_nu", ["-1.0", "-1.5", "0.5", "0.6"])
def test_invalid_poisson_ratio_bounds(bad_nu):
    source = _base_cantilever_source().replace("nu = 0.33", f"nu = {bad_nu}")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Poisson's ratio 'nu' must satisfy -1.0 < nu < 0.5" in result.diagnostics[0].message


# 11. Invalid Boundary References
@pytest.mark.parametrize("invalid_bnd", ["center", "middle", "north", "face_1"])
def test_invalid_boundary_references(invalid_bnd):
    source = _base_cantilever_source().replace("boundary = right", f"boundary = {invalid_bnd}")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert f"Invalid load boundary '{invalid_bnd}'" in result.diagnostics[0].message


# 12. Conflicting Boundary Conditions
def test_conflicting_dirichlet_and_traction_load():
    # Attempt to apply a traction load to the fixed boundary 'left'
    source = _base_cantilever_source().replace(
        "boundary = right,\n        tx = 0.0,\n        ty = -1.0e6",
        "boundary = left,\n        tx = 0.0,\n        ty = -1.0e6",
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Conflicting boundary condition on 'left'" in result.diagnostics[0].message
    assert "cannot apply traction load to fixed Dirichlet boundary" in result.diagnostics[0].message


def test_duplicate_boundary_fix():
    # Attempt to declare fix on 'left' twice
    source = _base_cantilever_source().replace(
        "fix = boundary(left)",
        "fix = boundary(left)\n    fix = boundary(left)",
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Duplicate boundary condition on boundary 'left'" in result.diagnostics[0].message


# 13. Conflicting Objective Boundary
def test_objective_on_fixed_boundary_rejected():
    # Attempt to evaluate average displacement on the clamped boundary 'left' where displacement is 0
    source = _base_cantilever_source().replace(
        "objective = average_displacement(\n        boundary = right,",
        "objective = average_displacement(\n        boundary = left,",
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Conflicting objective boundary 'left'" in result.diagnostics[0].message
    assert "cannot evaluate displacement objective on a fixed Dirichlet boundary" in result.diagnostics[0].message


# 14. Invalid Objectives
def test_point_displacement_rejected_until_implemented():
    source = _base_cantilever_source().replace(
        "average_displacement(", "point_displacement("
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "point_displacement is rejected" in result.diagnostics[0].message


def test_invalid_objective_component():
    source = _base_cantilever_source().replace("component = y", "component = z")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Objective component 'z' must be 'x' or 'y'" in result.diagnostics[0].message


# 15. Invalid Adaptivity Parameters
@pytest.mark.parametrize("bad_fraction", ["0.0", "-0.1", "1.1", "2.0"])
def test_invalid_adaptivity_fraction(bad_fraction):
    source = _base_cantilever_source().replace(
        "adaptivity = goal_aware", f"adaptivity = goal_aware(fraction={bad_fraction})"
    )
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Adaptivity fraction must satisfy 0 < fraction <= 1" in result.diagnostics[0].message


# 16. Invalid Accuracy Target
@pytest.mark.parametrize("bad_pct", ["0.0", "-1.0"])
def test_invalid_accuracy_percent(bad_pct):
    source = _base_cantilever_source().replace("percent = 1.0", f"percent = {bad_pct}")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "must be strictly positive" in result.diagnostics[0].message


# 17. Invalid Backend Requests
def test_unknown_backend_device():
    source = _base_cantilever_source().replace("backend = cpu", "backend = quantum_qpu")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert "Unknown backend device 'quantum_qpu'" in result.diagnostics[0].message


@pytest.mark.parametrize("accel_backend", ["cuda", "hip", "sycl", "tpu"])
def test_unsupported_accelerator_backend_strictly_rejected(accel_backend):
    source = _base_cantilever_source().replace("backend = cpu", f"backend = {accel_backend}")
    result = GDECCompiler().compile_source(source)
    assert result.success is False
    assert f"Backend '{accel_backend}' was requested" in result.diagnostics[0].message
    assert "no accelerator backend is implemented" in result.diagnostics[0].message


# 18. Typed IR Contract Tests (Direct Pydantic Gate)
def test_typed_ir_direct_instantiation_rejects_conflicting_bc_and_load():
    geo = GeometryIR(width=2.0, height=0.5, thickness=0.02)
    mat = MaterialIR(E=70e9, nu=0.33, assumption="plane_stress")
    bcs = [BoundaryConditionIR(boundary="left", constrained_components=["x", "y"])]
    # Conflict: load applied to fixed boundary "left"
    loads = [TractionLoadIR(boundary="left", tx=0.0, ty=-1.0e6)]
    obj = ObjectiveIR(kind="average_displacement", boundary="right", component="y")
    acc = AccuracyTargetIR(kind="successive_qoi_change", percent=1.0)
    bud = BudgetIR(kind="max_dofs", value=25000, max_iterations=15)
    adp = AdaptivityIR(strategy="goal_aware", marking_fraction=0.3, cost_aware=True)
    dev = BackendIR(device="cpu")

    with pytest.raises(ValidationError, match="cannot apply traction to fixed Dirichlet boundary"):
        ProblemIR(
            name="ConflictingProblem",
            physics="linear_elasticity",
            geometry=geo,
            material=mat,
            boundary_conditions=bcs,
            loads=loads,
            objective=obj,
            accuracy=acc,
            budget=bud,
            adaptivity=adp,
            backend=dev,
        )


def test_typed_ir_direct_instantiation_rejects_objective_on_fixed_boundary():
    geo = GeometryIR(width=2.0, height=0.5, thickness=0.02)
    mat = MaterialIR(E=70e9, nu=0.33, assumption="plane_stress")
    bcs = [BoundaryConditionIR(boundary="left", constrained_components=["x", "y"])]
    loads = [TractionLoadIR(boundary="right", tx=0.0, ty=-1.0e6)]
    # Conflict: objective on fixed boundary "left"
    obj = ObjectiveIR(kind="average_displacement", boundary="left", component="y")
    acc = AccuracyTargetIR(kind="successive_qoi_change", percent=1.0)
    bud = BudgetIR(kind="max_dofs", value=25000, max_iterations=15)
    adp = AdaptivityIR(strategy="goal_aware", marking_fraction=0.3, cost_aware=True)
    dev = BackendIR(device="cpu")

    with pytest.raises(ValidationError, match="cannot evaluate displacement objective on a fixed Dirichlet boundary"):
        ProblemIR(
            name="ConflictingObjectiveProblem",
            physics="linear_elasticity",
            geometry=geo,
            material=mat,
            boundary_conditions=bcs,
            loads=loads,
            objective=obj,
            accuracy=acc,
            budget=bud,
            adaptivity=adp,
            backend=dev,
        )
