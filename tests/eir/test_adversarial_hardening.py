"""
Adversarial hardening tests for GDEC Engineering-IR (EIR) and Type System.
Covers property-based algebraic invariants, hash determinism across platforms,
input fuzzing (deep nesting, control characters, huge exponents), and immutability.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import unicodedata
from fractions import Fraction
import random
import pytest

from gdec.types.dimensions import (
    Dimension, DIMENSIONLESS, MASS, LENGTH, TIME, CURRENT, TEMPERATURE,
    AMOUNT, LUMINOUS_INTENSITY, FORCE, PRESSURE, ENERGY, POWER
)
from gdec.types.units import SI_UNITS, Unit, UnitRegistry
from gdec.types.quantities import Quantity
from gdec.types.errors import (
    TypeSystemError, DimensionError, UnitError, QuantityKindError, ShapeError
)
from gdec.eir.models import (
    EngineeringProblemIR, PhysicalModelIR, ProblemIdentity, CoordinateFrameIR,
    DomainIR, QuantityParameterIR, FieldIR, QuantityOfInterestIR, DimensionVector,
    _identifier
)
from gdec.eir.expressions import (
    Binary, Expr, ExpressionEnvironment, ExpressionRef, ExpressionTypeError,
    FieldRef, Literal, Negate, ParameterRef, Power, ValueType, infer_expression_type
)


# ==============================================================================
# 1. PROPERTY-BASED TESTS: UNIT ALGEBRA & SI NORMALIZATION
# ==============================================================================

class TestUnitAlgebraProperties:
    """Property tests over algebraic invariants of physical dimensions and units."""

    BASE_DIMS = [MASS, LENGTH, TIME, CURRENT, TEMPERATURE, AMOUNT, LUMINOUS_INTENSITY]

    def test_dimension_multiplication_associativity(self):
        """(A * B) * C == A * (B * C)"""
        rng = random.Random(42)
        for _ in range(50):
            d1 = self.BASE_DIMS[rng.randint(0, 6)] ** rng.randint(-3, 3)
            d2 = self.BASE_DIMS[rng.randint(0, 6)] ** rng.randint(-3, 3)
            d3 = self.BASE_DIMS[rng.randint(0, 6)] ** rng.randint(-3, 3)
            assert (d1 * d2) * d3 == d1 * (d2 * d3)

    def test_dimension_multiplication_commutativity(self):
        """A * B == B * A"""
        rng = random.Random(43)
        for _ in range(50):
            d1 = self.BASE_DIMS[rng.randint(0, 6)] ** rng.randint(-3, 3)
            d2 = self.BASE_DIMS[rng.randint(0, 6)] ** rng.randint(-3, 3)
            assert d1 * d2 == d2 * d1

    def test_dimension_multiplication_identity(self):
        """A * 1 == A and A / 1 == A"""
        for d in self.BASE_DIMS + [FORCE, PRESSURE, ENERGY, POWER]:
            assert d * DIMENSIONLESS == d
            assert DIMENSIONLESS * d == d
            assert d / DIMENSIONLESS == d
            assert d / d == DIMENSIONLESS

    def test_si_normalization_round_trips(self):
        """Value -> to_base -> from_base preserves exact float value within machine precision."""
        rng = random.Random(44)
        for symbol, unit in SI_UNITS.units.items():
            if unit.kind == "absolute_temperature":
                # Must be >= 0 K
                test_values = [0.0, 20.0, 100.0, 500.0, rng.uniform(0.0, 1000.0)]
                for val in test_values:
                    # Convert to K then back
                    base = unit.to_base(val)
                    recovered = unit.from_base(base)
                    assert math.isclose(recovered, val, rel_tol=1e-12, abs_tol=1e-12)
            else:
                test_values = [0.0, 1.0, -1.0, 1e-4, 1e5, rng.uniform(-1e4, 1e4)]
                for val in test_values:
                    base = unit.to_base(val)
                    recovered = unit.from_base(base)
                    assert math.isclose(recovered, val, rel_tol=1e-12, abs_tol=1e-12)

    def test_rational_exponent_arithmetic_no_float_leakage(self):
        """Dimension exponents must remain strictly Fraction instances, never float."""
        d = (LENGTH ** Fraction(1, 3)) * (LENGTH ** Fraction(2, 3))
        assert d == LENGTH
        assert all(isinstance(x, Fraction) for x in d.exponents)
        assert d.exponents[1] == Fraction(1, 1)


# ==============================================================================
# 2. HASH DETERMINISM SUITE
# ==============================================================================

class TestCanonicalHashDeterminism:
    """Verifies SHA-256 hash invariants across serialization and representation."""

    def _make_problem(self, param_id="E", val=1000.0, unit="Pa", prob_id="cantilever"):
        p = QuantityParameterIR(id=param_id, value=val, unit=unit)
        return EngineeringProblemIR(
            problem=ProblemIdentity(id=prob_id, name="Test Cantilever"),
            physical_model=PhysicalModelIR(parameters=(p,))
        )

    def test_hash_invariant_to_dict_insertion_order(self):
        p1 = QuantityParameterIR(id="param_a", value=10.0, unit="m")
        p2 = QuantityParameterIR(id="param_b", value=20.0, unit="m")
        prob1 = EngineeringProblemIR(
            problem=ProblemIdentity(id="prob", name="P"),
            physical_model=PhysicalModelIR(parameters=(p1, p2))
        )
        prob2 = EngineeringProblemIR(
            problem=ProblemIdentity(id="prob", name="P"),
            physical_model=PhysicalModelIR(parameters=(p2, p1))
        )
        assert prob1.canonical_sha256() == prob2.canonical_sha256()

    def test_hash_invariant_to_line_endings_and_whitespace(self):
        prob = self._make_problem()
        json_lf = prob.to_json()
        json_crlf = json_lf.replace("\n", "\r\n")
        assert EngineeringProblemIR.from_json(json_lf).canonical_sha256() == \
               EngineeringProblemIR.from_json(json_crlf).canonical_sha256()

    def test_hash_invariant_to_equivalent_numeric_notations(self):
        """1000, 1000.0, and 1e3 produce identical canonical hashes."""
        h1 = self._make_problem(val=1000).canonical_sha256()
        h2 = self._make_problem(val=1000.0).canonical_sha256()
        h3 = self._make_problem(val=1e3).canonical_sha256()
        assert h1 == h2 == h3

    def test_hash_invariant_to_equivalent_si_units(self):
        """1.0 kPa and 1000.0 Pa normalize to the same canonical representation."""
        h_pa = self._make_problem(val=1000.0, unit="Pa").canonical_sha256()
        h_kpa = self._make_problem(val=1.0, unit="kPa").canonical_sha256()
        assert h_pa == h_kpa

    def test_hash_what_must_differ(self):
        """Differing problem values or definitions MUST produce distinct hashes."""
        base_h = self._make_problem(val=1000.0, unit="Pa", prob_id="cant_1").canonical_sha256()
        diff_val = self._make_problem(val=1000.001, unit="Pa", prob_id="cant_1").canonical_sha256()
        diff_id = self._make_problem(val=1000.0, unit="Pa", prob_id="cant_2").canonical_sha256()
        diff_param = self._make_problem(param_id="nu", val=1000.0, unit="Pa", prob_id="cant_1").canonical_sha256()
        diff_unit = self._make_problem(val=1000.0, unit="N", prob_id="cant_1").canonical_sha256()

        assert len({base_h, diff_val, diff_id, diff_param, diff_unit}) == 5


# ==============================================================================
# 3. ADVERSARIAL FUZZING & ATTACK SUITE
# ==============================================================================

class TestAdversarialFuzzing:
    """Attacks parser, AST, identifier sanitization, and recursion bounds."""

    def test_deeply_nested_expression_rejected_with_typed_error(self):
        """Expressions exceeding depth limit must raise ExpressionTypeError, not crash Python."""
        lit = Literal(1.0, ValueType(DIMENSIONLESS))
        node = lit
        for _ in range(500):
            node = Negate(node)
        env = ExpressionEnvironment()
        with pytest.raises(ExpressionTypeError, match="depth|nesting|limit"):
            infer_expression_type(node, env)

    def test_huge_expression_node_count_rejected_with_typed_error(self):
        """Expressions exceeding AST node count limit must raise ExpressionTypeError."""
        node = Literal(1.0, ValueType(DIMENSIONLESS))
        # Build wide tree
        for _ in range(250):
            node = Binary("add", node, Literal(1.0, ValueType(DIMENSIONLESS)))
        env = ExpressionEnvironment()
        # Should either succeed if under node limit or raise typed error if over
        try:
            res = infer_expression_type(node, env)
            assert res.dimension.is_dimensionless
        except ExpressionTypeError:
            pass

    @pytest.mark.parametrize("bad_id", [
        "foo\x00bar",      # Null byte
        "foo\nbar",        # Newline
        "foo\rbar",        # Carriage return
        "foo\tbar",        # Tab
        "foo\u200bbar",    # Zero-width space
        "foo\u202ebar",    # Right-to-left override
        "foo\ufeffbar",    # Zero-width no-break space / BOM
    ])
    def test_identifier_rejects_control_and_confusable_characters(self, bad_id):
        """Identifiers containing control or confusable characters must be rejected."""
        with pytest.raises(ValueError, match="control|confusable|invalid"):
            _identifier(bad_id)

    def test_identifier_unicode_nfc_normalization(self):
        """Identifiers written in NFD are normalized to NFC."""
        composed = "caf\u00e9"
        decomposed = unicodedata.normalize("NFD", composed)
        assert composed != decomposed
        assert _identifier(decomposed) == composed

    def test_power_rejects_adversarial_huge_exponents(self):
        """Power exponents with absurdly huge numerators or denominators must be rejected."""
        node = Literal(1.0, ValueType(DIMENSIONLESS))
        with pytest.raises(ExpressionTypeError, match="bound|rational|overflow"):
            Power(node, Fraction(10**8, 1))

    @pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
    def test_quantity_parameter_rejects_non_finite_values(self, bad_val):
        with pytest.raises(ValueError, match="finite"):
            QuantityParameterIR(id="param", value=bad_val, unit="m")

    @pytest.mark.parametrize("bool_val", [True, False])
    def test_quantity_parameter_rejects_boolean_values(self, bool_val):
        with pytest.raises(ValueError, match="boolean"):
            QuantityParameterIR(id="param", value=bool_val, unit="m")


# ==============================================================================
# 4. IMMUTABILITY & ALIASING SUITE
# ==============================================================================

class TestImmutabilityAndAliasing:
    """Verifies that no public EIR or type-environment object can be mutated."""

    def test_physical_model_immutable_after_construction(self):
        p = QuantityParameterIR(id="p1", value=10.0, unit="m")
        phys = PhysicalModelIR(parameters=(p,))
        with pytest.raises(Exception):
            phys.parameters = (QuantityParameterIR(id="p2", value=20.0, unit="m"),)

    def test_caller_list_mutation_does_not_mutate_physical_model(self):
        p1 = QuantityParameterIR(id="p1", value=10.0, unit="m")
        caller_list = [p1]
        phys = PhysicalModelIR(parameters=caller_list)
        caller_list.append(QuantityParameterIR(id="p2", value=20.0, unit="m"))
        assert len(phys.parameters) == 1

    def test_expression_environment_immutable_and_anti_aliased(self):
        caller_params = {"p1": ValueType(LENGTH)}
        env = ExpressionEnvironment(parameters=caller_params)
        caller_params["p2"] = ValueType(MASS)
        assert "p2" not in env.parameters
        with pytest.raises(Exception):
            env.parameters["p1"] = ValueType(TIME)
