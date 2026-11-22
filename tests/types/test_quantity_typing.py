import pytest
from gdec.types import Quantity, LENGTH, VELOCITY, DimensionError, QuantityKindError

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
