import pytest

from gdec.eir.expressions import (
    Binary,
    ExpressionEnvironment,
    ExpressionRef,
    ExpressionTypeError,
    FieldRef,
    Literal,
    Negate,
    ParameterRef,
    Power,
    ValueType,
    environment_from_eir,
    infer_expression_type,
)
from gdec.types.dimensions import (
    DIMENSIONLESS, LENGTH, MASS, TEMPERATURE, TIME, VELOCITY, FORCE,
)
from gdec.types.errors import DimensionError, QuantityKindError, ShapeError


def scalar(dimension, kind="linear"):
    return ValueType(dimension, kind)


def test_parameter_reference_resolves_type():
    env = ExpressionEnvironment(parameters={"load": scalar(FORCE)})
    assert infer_expression_type(ParameterRef("load"), env) == scalar(FORCE)


def test_unknown_parameter_and_field_references_fail_closed():
    env = ExpressionEnvironment()
    with pytest.raises(ExpressionTypeError, match="Unknown parameter"):
        infer_expression_type(ParameterRef("missing"), env)
    with pytest.raises(ExpressionTypeError, match="Unknown field"):
        infer_expression_type(FieldRef("missing"), env)


def test_addition_requires_equal_dimensions():
    expr = Binary("add", Literal(1, scalar(LENGTH)), Literal(1, scalar(TIME)))
    with pytest.raises(DimensionError):
        infer_expression_type(expr, ExpressionEnvironment())


def test_addition_preserves_linear_dimension():
    expr = Binary("add", Literal(1, scalar(LENGTH)), Literal(2, scalar(LENGTH)))
    assert infer_expression_type(expr, ExpressionEnvironment()) == scalar(LENGTH)


def test_absolute_temperature_plus_interval_is_absolute():
    absolute = Literal(293.15, scalar(TEMPERATURE, "absolute_temperature"))
    interval = Literal(10, scalar(TEMPERATURE, "temperature_interval"))
    assert infer_expression_type(
        Binary("add", absolute, interval), ExpressionEnvironment()
    ) == scalar(TEMPERATURE, "absolute_temperature")
    assert infer_expression_type(
        Binary("add", interval, absolute), ExpressionEnvironment()
    ) == scalar(TEMPERATURE, "absolute_temperature")


def test_absolute_temperature_plus_absolute_temperature_is_rejected():
    a = Literal(293.15, scalar(TEMPERATURE, "absolute_temperature"))
    b = Literal(300, scalar(TEMPERATURE, "absolute_temperature"))
    with pytest.raises(QuantityKindError):
        infer_expression_type(Binary("add", a, b), ExpressionEnvironment())


def test_absolute_temperature_minus_absolute_temperature_is_interval():
    a = Literal(300, scalar(TEMPERATURE, "absolute_temperature"))
    b = Literal(293.15, scalar(TEMPERATURE, "absolute_temperature"))
    assert infer_expression_type(
        Binary("subtract", a, b), ExpressionEnvironment()
    ) == scalar(TEMPERATURE, "temperature_interval")


def test_absolute_temperature_minus_interval_remains_absolute():
    a = Literal(300, scalar(TEMPERATURE, "absolute_temperature"))
    b = Literal(10, scalar(TEMPERATURE, "temperature_interval"))
    assert infer_expression_type(
        Binary("subtract", a, b), ExpressionEnvironment()
    ) == scalar(TEMPERATURE, "absolute_temperature")


def test_interval_minus_absolute_temperature_is_rejected():
    a = Literal(10, scalar(TEMPERATURE, "temperature_interval"))
    b = Literal(300, scalar(TEMPERATURE, "absolute_temperature"))
    with pytest.raises(QuantityKindError):
        infer_expression_type(Binary("subtract", a, b), ExpressionEnvironment())


def test_absolute_temperature_cannot_be_negated_or_multiplied():
    t = Literal(300, scalar(TEMPERATURE, "absolute_temperature"))
    with pytest.raises(QuantityKindError):
        infer_expression_type(Negate(t), ExpressionEnvironment())
    with pytest.raises(QuantityKindError):
        infer_expression_type(Binary("multiply", t, Literal(2, scalar(DIMENSIONLESS))), ExpressionEnvironment())


def test_multiplication_and_division_compose_dimensions():
    env = ExpressionEnvironment()
    velocity = Binary(
        "divide",
        Literal(10, scalar(LENGTH)),
        Literal(2, scalar(TIME)),
    )
    assert infer_expression_type(velocity, env) == scalar(VELOCITY)
    force = Binary(
        "multiply",
        Literal(2, scalar(MASS)),
        Literal(3, scalar(LENGTH / (TIME ** 2))),
    )
    assert infer_expression_type(force, env) == scalar(FORCE)


def test_temperature_interval_times_dimensionless_preserves_interval():
    interval = Literal(5, scalar(TEMPERATURE, "temperature_interval"))
    factor = Literal(2, scalar(DIMENSIONLESS))
    assert infer_expression_type(
        Binary("multiply", interval, factor), ExpressionEnvironment()
    ) == scalar(TEMPERATURE, "temperature_interval")


def test_fractional_power_uses_exact_dimension_exponents():
    expr = Power(Literal(9, scalar(LENGTH ** 2)), exponent=1 / 2)
    assert infer_expression_type(expr, ExpressionEnvironment()) == scalar(LENGTH)


def test_tensor_addition_requires_same_shape_and_frame():
    env = ExpressionEnvironment(fields={
        "u": ValueType(LENGTH, shape=(2,), frame_id="global"),
        "v": ValueType(LENGTH, shape=(2,), frame_id="global"),
        "w": ValueType(LENGTH, shape=(3,), frame_id="global"),
        "q": ValueType(LENGTH, shape=(2,), frame_id="local"),
    })
    assert infer_expression_type(Binary("add", FieldRef("u"), FieldRef("v")), env) == ValueType(
        LENGTH, shape=(2,), frame_id="global"
    )
    with pytest.raises(ShapeError, match="shape mismatch"):
        infer_expression_type(Binary("add", FieldRef("u"), FieldRef("w")), env)
    with pytest.raises(ShapeError, match="frame mismatch"):
        infer_expression_type(Binary("add", FieldRef("u"), FieldRef("q")), env)


def test_implicit_tensor_broadcasting_and_tensor_products_are_rejected():
    env = ExpressionEnvironment(fields={
        "u": ValueType(LENGTH, shape=(3,), frame_id="world"),
        "scalar_field": ValueType(LENGTH),
    })
    with pytest.raises(ShapeError, match="broadcasting"):
        infer_expression_type(Binary("add", FieldRef("u"), FieldRef("scalar_field")), env)
    with pytest.raises(ShapeError, match="contraction"):
        infer_expression_type(
            Binary("multiply", FieldRef("u"), FieldRef("u")), env
        )


def test_power_of_temperature_interval_is_rejected():
    expr = Power(Literal(5, scalar(TEMPERATURE, "temperature_interval")), 2)
    with pytest.raises(QuantityKindError):
        infer_expression_type(expr, ExpressionEnvironment())


def test_expression_references_are_memoized_and_cycles_are_rejected():
    env = ExpressionEnvironment(expressions={
        "length": Literal(2, scalar(LENGTH)),
        "area": Binary("multiply", ExpressionRef("length"), ExpressionRef("length")),
    })
    assert infer_expression_type(ExpressionRef("area"), env) == scalar(LENGTH ** 2)

    cyclic = ExpressionEnvironment(expressions={
        "a": ExpressionRef("b"),
        "b": ExpressionRef("a"),
    })
    with pytest.raises(ExpressionTypeError, match="cycle"):
        infer_expression_type(ExpressionRef("a"), cyclic)


def test_unknown_expression_reference_is_rejected():
    with pytest.raises(ExpressionTypeError, match="Unknown expression"):
        infer_expression_type(ExpressionRef("missing"), ExpressionEnvironment())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_literal_rejects_nonfinite_and_boolean_values(value):
    expr = Literal(value, scalar(DIMENSIONLESS))
    with pytest.raises(ExpressionTypeError):
        infer_expression_type(expr, ExpressionEnvironment())


def test_unsupported_operator_is_rejected():
    expr = Binary("matmul", Literal(1, scalar(DIMENSIONLESS)), Literal(2, scalar(DIMENSIONLESS)))
    with pytest.raises(ExpressionTypeError, match="Unsupported binary operator"):
        infer_expression_type(expr, ExpressionEnvironment())


def test_environment_is_derived_from_validated_eir():
    from gdec.eir import DimensionVector, EngineeringProblemIR

    document = EngineeringProblemIR.model_validate({
        "problem": {"id": "p", "name": "test"},
        "physical_model": {
            "coordinate_frames": [{"id": "world", "dimension": 2}],
            "domains": [{"id": "plate", "spatial_dimension": 2, "coordinate_frame_id": "world"}],
            "parameters": [{"id": "youngs_modulus", "value": 210, "unit": "GPa"}],
            "fields": [{
                "id": "displacement", "domain_id": "plate",
                "dimension": DimensionVector.from_dimension(LENGTH).model_dump(),
                "unit": "m", "shape": [2], "coordinate_frame_id": "world",
                "function_space": "H1",
            }],
        },
    })
    env = environment_from_eir(document)
    assert env.parameters["youngs_modulus"].dimension == FORCE / (LENGTH ** 2)
    assert env.fields["displacement"] == ValueType(LENGTH, shape=(2,), frame_id="world")
