from fractions import Fraction
import pytest
from gdec.types import DIMENSIONLESS, LENGTH, TIME, MASS, VELOCITY, FORCE, PRESSURE, Dimension

def test_base_and_derived_dimensions():
    assert VELOCITY == LENGTH / TIME
    assert FORCE == MASS * LENGTH / (TIME ** 2)
    assert PRESSURE == FORCE / (LENGTH ** 2)

def test_rational_exponents_are_exact():
    root_length = LENGTH ** Fraction(1, 2)
    assert root_length.exponents[1] == Fraction(1, 2)
    assert root_length ** 2 == LENGTH

def test_dimensionless_and_string_representation():
    assert DIMENSIONLESS.is_dimensionless
    assert not LENGTH.is_dimensionless
    assert str(DIMENSIONLESS) == "1"

def test_wrong_number_of_base_exponents_rejected():
    with pytest.raises(ValueError):
        Dimension.from_exponents((1, 2))
