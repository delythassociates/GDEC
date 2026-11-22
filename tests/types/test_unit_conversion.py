import pytest
from gdec.types import SI_UNITS, Unit, UnitRegistry, LENGTH, UnitError

def test_length_conversion():
    assert SI_UNITS.convert(1000, "mm", "m") == pytest.approx(1.0)
    assert SI_UNITS.convert(1, "km", "m") == pytest.approx(1000.0)

def test_pressure_conversion():
    assert SI_UNITS.convert(2, "MPa", "Pa") == pytest.approx(2_000_000)

def test_affine_temperature_conversion():
    assert SI_UNITS.convert(0, "degC", "K") == pytest.approx(273.15)
    assert SI_UNITS.convert(32, "degF", "degC") == pytest.approx(0.0)

def test_incompatible_dimensions_rejected():
    with pytest.raises(UnitError):
        SI_UNITS.convert(1, "m", "s")

def test_absolute_and_interval_units_not_interchangeable():
    with pytest.raises(UnitError):
        SI_UNITS.convert(10, "degC", "delta_degC")

def test_duplicate_unit_registration_rejected():
    registry = UnitRegistry()
    registry.register(Unit("m", LENGTH))
    with pytest.raises(UnitError):
        registry.register(Unit("m", LENGTH))

def test_absolute_temperature_below_zero_kelvin_rejected_by_registry():
    with pytest.raises(UnitError):
        SI_UNITS.convert(-300, "degC", "K")

def test_nonfinite_and_boolean_conversion_inputs_rejected():
    with pytest.raises(UnitError):
        SI_UNITS.convert(float("nan"), "m", "cm")
    with pytest.raises(UnitError):
        SI_UNITS.convert(True, "m", "cm")

def test_invalid_unit_scale_and_non_atomic_alias_registration():
    with pytest.raises(UnitError):
        Unit("bad", LENGTH, scale=-1)
    registry = UnitRegistry()
    unit = Unit("m", LENGTH)
    registry.register(unit)
    with pytest.raises(UnitError):
        registry.register(Unit("cm", LENGTH), aliases=("m",))
    assert "cm" not in registry.units


def test_unit_conversion_rejects_integer_too_large_for_finite_float():
    with pytest.raises(UnitError, match="finite real number"):
        SI_UNITS.convert(10**10000, "m", "cm")
