import pytest
from gdec.types import TensorShape, CoordinateFrame, ValueShape, FieldType, ShapeError

def test_tensor_shape_metadata():
    shape = TensorShape((3, 3))
    assert shape.rank == 2
    assert shape.size == 9

def test_invalid_tensor_extent_rejected():
    with pytest.raises(ShapeError):
        TensorShape((3, 0))

def test_frame_mismatch_requires_explicit_transform():
    world = CoordinateFrame("world", 3)
    local = CoordinateFrame("part_local", 3, parent_id="world")
    with pytest.raises(ShapeError):
        ValueShape(TensorShape((3,)), world).require_compatible(ValueShape(TensorShape((3,)), local))

def test_field_requires_domain_and_function_space():
    with pytest.raises(ShapeError):
        FieldType(ValueShape(TensorShape((1,))), "", "H1")
