import json

import pytest
from pydantic import ValidationError

from gdec.eir import (
    CoordinateFrameIR,
    DimensionVector,
    DomainIR,
    EngineeringProblemIR,
    FieldIR,
    PhysicalModelIR,
    ProblemIdentity,
    QuantityOfInterestIR,
    QuantityParameterIR,
)
from gdec.types.dimensions import LENGTH, PRESSURE


def make_problem(**overrides):
    payload = {
        "problem": {"id": "problem.cantilever", "name": "Cantilever plate"},
        "physical_model": {
            "coordinate_frames": [
                {"id": "frame.world", "dimension": 2}
            ],
            "domains": [
                {
                    "id": "domain.plate",
                    "spatial_dimension": 2,
                    "coordinate_frame_id": "frame.world",
                }
            ],
            "parameters": [
                {
                    "id": "parameter.youngs_modulus",
                    "value": 210,
                    "unit": "GPa",
                }
            ],
            "fields": [
                {
                    "id": "field.displacement",
                    "domain_id": "domain.plate",
                    "dimension": DimensionVector.from_dimension(LENGTH).model_dump(),
                    "unit": "m",
                    "shape": [2],
                    "coordinate_frame_id": "frame.world",
                    "function_space": "H1",
                }
            ],
        },
        "quantities_of_interest": [
            {
                "id": "qoi.tip_displacement",
                "field_id": "field.displacement",
                "unit": "mm",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_eir_round_trip_and_pinned_schema_identity():
    model = EngineeringProblemIR.model_validate(make_problem())
    assert model.kind == "gdec.engineering_problem"
    assert model.schema_version == "0.1.0"
    restored = EngineeringProblemIR.from_json(model.to_json())
    assert restored == model
    assert restored.quantities_of_interest[0].unit == "mm"


def test_dimension_vector_uses_exact_canonical_rational_exponents():
    vector = DimensionVector(exponents=["0", "0.5", "-1", 0, 0, 0, 0])
    assert vector.exponents == ("0", "1/2", "-1", "0", "0", "0", "0")
    assert vector.to_dimension().exponents[1] == 1 / 2


def test_dimension_vector_rejects_wrong_length_and_zero_denominator():
    with pytest.raises(ValidationError):
        DimensionVector(exponents=["0", "1"])
    with pytest.raises(ValidationError):
        DimensionVector(exponents=["0", "1/0", "0", "0", "0", "0", "0"])


def test_parameter_units_are_checked_against_quantity_kind_and_absolute_zero():
    data = make_problem()
    data["physical_model"]["parameters"] = [
        {"id": "temperature", "value": -300, "unit": "degC",
         "quantity_kind": "absolute_temperature"}
    ]
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_unknown_units_are_rejected_even_if_general_registry_might_be_extended():
    data = make_problem()
    data["physical_model"]["parameters"] = [
        {"id": "custom", "value": 1, "unit": "invented_unit"}
    ]
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_field_declared_dimension_must_match_unit_dimension():
    data = make_problem()
    data["physical_model"]["fields"][0]["unit"] = "Pa"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_dangling_domain_frame_field_and_qoi_references_are_rejected():
    data = make_problem()
    data["physical_model"]["domains"][0]["coordinate_frame_id"] = "missing.frame"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)

    data = make_problem()
    data["physical_model"]["fields"][0]["domain_id"] = "missing.domain"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)

    data = make_problem()
    data["quantities_of_interest"][0]["field_id"] = "missing.field"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_coordinate_frame_parent_cycle_is_rejected():
    data = make_problem()
    data["physical_model"]["coordinate_frames"] = [
        {"id": "frame.a", "dimension": 2, "parent_id": "frame.b"},
        {"id": "frame.b", "dimension": 2, "parent_id": "frame.a"},
    ]
    data["physical_model"]["domains"][0]["coordinate_frame_id"] = "frame.a"
    data["physical_model"]["fields"][0]["coordinate_frame_id"] = "frame.a"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_duplicate_entity_ids_are_rejected_globally():
    data = make_problem()
    data["physical_model"]["fields"][0]["id"] = "domain.plate"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_field_frame_and_vector_shape_must_match_domain():
    data = make_problem()
    data["physical_model"]["fields"][0]["shape"] = [3]
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_qoi_unit_must_match_field_dimension_and_quantity_kind():
    data = make_problem()
    data["quantities_of_interest"][0]["unit"] = "s"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)


def test_canonical_json_and_hash_ignore_entity_list_order():
    data_a = make_problem()
    data_b = make_problem()
    data_a["physical_model"]["parameters"].append(
        {"id": "parameter.poisson", "value": 0.3, "unit": "1"}
    )
    data_b["physical_model"]["parameters"] = list(reversed(data_a["physical_model"]["parameters"]))
    model_a = EngineeringProblemIR.model_validate(data_a)
    model_b = EngineeringProblemIR.model_validate(data_b)
    assert model_a.canonical_json() == model_b.canonical_json()
    assert model_a.canonical_sha256() == model_b.canonical_sha256()


def test_canonical_hash_changes_when_engineering_value_changes():
    data = make_problem()
    first = EngineeringProblemIR.model_validate(data)
    data["physical_model"]["parameters"][0]["value"] = 205
    second = EngineeringProblemIR.model_validate(data)
    assert first.canonical_sha256() != second.canonical_sha256()


def test_unsupported_schema_version_is_rejected():
    data = make_problem()
    data["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        EngineeringProblemIR.model_validate(data)
