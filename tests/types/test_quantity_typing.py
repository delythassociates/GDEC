import pytest
from gdec.types import Quantity, LENGTH, VELOCITY, TEMPERATURE, DimensionError, QuantityKindError, UnitError

def test_quantity_unit_round_trip():
    q = Quantity.from_unit(250, "cm")
    assert q.dimension == LENGTH
    assert q.value == pytest.approx(2.5)
    assert q.to("m") == pytest.approx(2.5)
    assert q.to("mm") == pytest.approx(2500)

def test_dimension_checked_arithmetic():
    distance = Quantity.from_unit(10, "m")
    duration = Quantity.from_unit(2, "s")
    speed = distance / duration
    assert speed.dimension == VELOCITY
    assert speed.value == pytest.approx(5)
    with pytest.raises(DimensionError):
        _ = distance + duration

def test_temperature_semantics():
    t1 = Quantity.from_unit(20, "degC")
    t2 = Quantity.from_unit(10, "degC")
    delta = t1 - t2
    assert delta.kind == "temperature_interval"
    assert delta.to("delta_degC") == pytest.approx(10)
    assert (t2 + delta).to("degC") == pytest.approx(20)
    with pytest.raises(QuantityKindError):
        _ = t1 + t2

def test_absolute_temperature_cannot_be_multiplied_or_negated():
    temp = Quantity.from_unit(20, "degC")
    with pytest.raises(QuantityKindError):
        _ = temp * 2
    with pytest.raises(QuantityKindError):
        _ = -temp

def test_quantity_rejects_dimension_mismatch_in_required_context():
    with pytest.raises(DimensionError):
        Quantity.from_unit(1, "s").require_dimension(LENGTH, context="geometry length")

def test_temperature_interval_can_participate_in_dimensional_products():
    delta = Quantity.from_unit(5, "delta_degC")
    length = Quantity.from_unit(2, "m")
    product = delta * length
    assert product.dimension.exponents[1] == 1
    assert product.dimension.exponents[4] == 1
    assert product.value == pytest.approx(10)

def test_nonfinite_and_below_absolute_zero_rejected():
    with pytest.raises(ValueError):
        Quantity(float("nan"), LENGTH)
    with pytest.raises(UnitError):
        Quantity.from_unit(-300, "degC")
    with pytest.raises(QuantityKindError):
        Quantity(-1, TEMPERATURE, "absolute_temperature")

def test_temperature_interval_product_loses_affine_kind_when_dimension_changes():
    interval = Quantity.from_unit(5, "delta_degC")
    length = Quantity.from_unit(2, "m")
    product = interval * length
    assert product.kind == "linear"
    assert product.dimension.exponents[1] == 1
    assert product.dimension.exponents[4] == 1

def test_temperature_interval_scalar_and_dimensionless_operations_preserve_interval_kind():
    interval = Quantity.from_unit(5, "delta_degC")
    assert (interval * 2).kind == "temperature_interval"
    assert (interval / 2).kind == "temperature_interval"
    dimensionless = Quantity.from_unit(2, "1")
    assert (interval * dimensionless).kind == "temperature_interval"

def test_quantity_zero_division_and_nonfinite_scalar_fail_closed():
    distance = Quantity.from_unit(3, "m")
    zero = Quantity.from_unit(0, "s")
    with pytest.raises(ZeroDivisionError):
        _ = distance / zero
    with pytest.raises(ZeroDivisionError):
        _ = distance / 0
    with pytest.raises(ValueError):
        _ = distance * float("inf")

def test_temperature_interval_cannot_be_subtracted_from_absolute_temperature_in_reverse_order():
    absolute = Quantity.from_unit(20, "degC")
    interval = Quantity.from_unit(5, "delta_degC")
    with pytest.raises(QuantityKindError):
        _ = interval - absolute
