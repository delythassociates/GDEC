"""
Tests for GDEC Language lexer, parser, and syntax validation.
"""

import pytest
from gdec.language.parser import GDECParser, GDECParseError
from gdec.language.semantic import SemanticAnalyzer, GDECSemanticError


VALID_SRC = """
problem TestProblem {
    physics = linear_elasticity
    geometry = rectangle(width=2.0, height=0.5, thickness=0.02)
    material = isotropic(E=70e9, nu=0.33, assumption=plane_stress)
    fix = boundary(left)
    load = traction(boundary=right, tx=0.0, ty=-1.0e6)
    objective = average_displacement(boundary=right, component=y)
    accuracy = successive_qoi_change(percent=1.0)
    budget = max_dofs(value=25000)
    adaptivity = goal_aware
    backend = cpu
}
"""


def test_valid_source_parses():
    parser = GDECParser()
    ast = parser.parse(VALID_SRC)
    assert ast.name == "TestProblem"
    assert len(ast.statements) >= 9


def test_syntax_error_rejected():
    parser = GDECParser()
    bad_syntax = "problem Broken { physics = }"
    with pytest.raises(GDECParseError):
        parser.parse(bad_syntax)


def test_missing_physics_rejected():
    parser = GDECParser()
    analyzer = SemanticAnalyzer()
    src = """
    problem NoPhysics {
        geometry = rectangle(width=1.0, height=1.0)
        material = isotropic(E=1e9, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-100)
        objective = average_displacement(boundary=right, component=y)
    }
    """
    ast = parser.parse(src)
    with pytest.raises(GDECSemanticError, match="physics"):
        analyzer.analyze(ast)


def test_unsupported_physics_rejected():
    parser = GDECParser()
    analyzer = SemanticAnalyzer()
    src = """
    problem CFDProblem {
        physics = fluid_dynamics
        geometry = rectangle(width=1.0, height=1.0)
        material = isotropic(E=1e9, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-100)
        objective = average_displacement(boundary=right, component=y)
    }
    """
    ast = parser.parse(src)
    with pytest.raises(GDECSemanticError, match="Unsupported physics model"):
        analyzer.analyze(ast)


def test_negative_youngs_modulus_rejected():
    parser = GDECParser()
    analyzer = SemanticAnalyzer()
    src = """
    problem NegativeE {
        physics = linear_elasticity
        geometry = rectangle(width=1.0, height=1.0)
        material = isotropic(E=-50e9, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-100)
        objective = average_displacement(boundary=right, component=y)
    }
    """
    ast = parser.parse(src)
    with pytest.raises(GDECSemanticError, match="Young's modulus 'E' must be a strictly positive number"):
        analyzer.analyze(ast)


def test_invalid_poisson_ratio_rejected():
    parser = GDECParser()
    analyzer = SemanticAnalyzer()
    src = """
    problem BadNu {
        physics = linear_elasticity
        geometry = rectangle(width=1.0, height=1.0)
        material = isotropic(E=70e9, nu=0.6)
        fix = boundary(left)
        load = traction(boundary=right, ty=-100)
        objective = average_displacement(boundary=right, component=y)
    }
    """
    ast = parser.parse(src)
    with pytest.raises(GDECSemanticError, match="Poisson's ratio 'nu' must satisfy"):
        analyzer.analyze(ast)


def test_unsupported_backend_rejected():
    parser = GDECParser()
    analyzer = SemanticAnalyzer()
    src = """
    problem CudaBackend {
        physics = linear_elasticity
        geometry = rectangle(width=1.0, height=1.0)
        material = isotropic(E=70e9, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-100)
        objective = average_displacement(boundary=right, component=y)
        backend = cuda
    }
    """
    ast = parser.parse(src)
    with pytest.raises(GDECSemanticError, match="no GPU accelerator hardware or CUDA backend is available"):
        analyzer.analyze(ast)
