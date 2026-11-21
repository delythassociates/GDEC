"""
Unit and verification tests for GDEC Decision Sufficiency Engine (DSE).
Covers Decision Contract schema, Single-QoI Evaluator, Deterministic Refusal,
and Analytical Linear-Elastic Parameter Propagation.
"""

import math
import pytest
import numpy as np
from scipy.special import ndtr

from gdec.dse import (
    DecisionContract,
    DecisionIdentity,
    QuantityOfInterest,
    AcceptanceCriterion,
    PredictiveDistribution,
    DecisionLoss,
    EvidenceRequirements,
    ComputationalBudget,
    SingleQoIEvaluator,
    DecisionRecommendation,
    DecisionRefusalError,
    ContractValidationError,
    RestrictedLinearElasticScaling,
    ReferenceBaseline,
    ScalingAssumptions,
    ScalingAssumptionError,
)


@pytest.fixture
def valid_contract():
    """Create a fully valid canonical Decision Contract."""
    return DecisionContract(
        identity=DecisionIdentity(
            id="DEC-CANTILEVER-001",
            schema_version="1.0.0",
            title="Cantilever Tip Deflection Release",
            question="Does the cantilever beam tip deflection remain below allowable threshold?",
            description="Verification of 2D linear-elastic cantilever tip displacement under end shear load.",
        ),
        qoi=QuantityOfInterest(
            qoi_id="tip_deflection",
            name="Vertical Tip Displacement",
            unit="mm",
            expected_sign="positive",
            model_reference="LinearElasticity-Cantilever",
        ),
        criterion=AcceptanceCriterion(
            operator="<=",
            limit=10.0,
            unit="mm",
            safety_margin=0.5,  # Effective limit: 9.5 mm
        ),
        predictive_distribution=PredictiveDistribution(
            family="normal",
            mean=8.0,
            std=0.5,
            unit="mm",
            provenance="FEM Simulation with DWR and Material UQ",
        ),
        loss=DecisionLoss(
            cost_false_acceptance=1000.0,
            cost_false_rejection=100.0,
            cost_unit="USD",
        ),
        evidence=EvidenceRequirements(
            required_categories=["discretization_error", "boundary_conditions"],
            model_assumptions=["linear_elasticity", "small_strain", "isotropic"],
            applicable_domain="cantilever_length_to_height_ratio_ge_5",
            numerical_quality_threshold=0.05,
            validation_status="verified_against_analytical",
            known_limitations=["not_valid_for_geometric_nonlinearities"],
        ),
        budget=ComputationalBudget(
            max_evaluations=10,
            max_wall_clock_seconds=60.0,
            enforced=False,
        ),
    )


# ==============================================================================
# WORKSTREAM C TESTS: DECISION CONTRACT & SCHEMA VALIDATION
# ==============================================================================

def test_contract_valid_json_roundtrip(valid_contract):
    """Test that a valid contract serializes to JSON and round-trips identically."""
    json_str = valid_contract.to_json()
    assert isinstance(json_str, str)
    assert "DEC-CANTILEVER-001" in json_str

    reconstructed = DecisionContract.from_json(json_str)
    assert reconstructed.identity.id == valid_contract.identity.id
    assert reconstructed.criterion.limit == 10.0
    assert reconstructed.criterion.safety_margin == 0.5
    assert reconstructed.predictive_distribution.mean == 8.0
    assert reconstructed.loss.cost_false_acceptance == 1000.0


def test_contract_json_schema_export():
    """Verify JSON Schema export conforms to Pydantic schema structure."""
    schema = DecisionContract.get_json_schema()
    assert "properties" in schema
    assert "identity" in schema["properties"]
    assert "criterion" in schema["properties"]
    assert "loss" in schema["properties"]


def test_contract_rejects_unit_mismatch():
    """Reject contract when QoI and Criterion units differ."""
    with pytest.raises(ValueError, match="Unit mismatch"):
        DecisionContract(
            identity=DecisionIdentity(id="DEC-01", title="T", question="Q"),
            qoi=QuantityOfInterest(qoi_id="deflection", name="D", unit="mm"),
            criterion=AcceptanceCriterion(operator="<=", limit=10.0, unit="m"),  # Mismatch: m != mm
            loss=DecisionLoss(cost_false_acceptance=100.0, cost_false_rejection=10.0),
            evidence=EvidenceRequirements(model_assumptions=["linear_elasticity"], applicable_domain="beam"),
        )


def test_contract_rejects_negative_std():
    """Reject predictive distribution with negative standard deviation."""
    with pytest.raises(ValueError):
        PredictiveDistribution(
            family="normal",
            mean=5.0,
            std=-1.0,
            unit="mm",
            provenance="test",
        )


def test_contract_rejects_zero_or_negative_loss():
    """Reject zero or negative loss costs."""
    with pytest.raises(ValueError):
        DecisionLoss(cost_false_acceptance=-50.0, cost_false_rejection=10.0)

    with pytest.raises(ValueError):
        DecisionLoss(cost_false_acceptance=50.0, cost_false_rejection=0.0)


def test_contract_rejects_invalid_operator():
    """Reject unsupported comparison operator."""
    with pytest.raises(ValueError):
        AcceptanceCriterion(operator="==", limit=10.0, unit="mm")


def test_contract_rejects_empty_assumptions():
    """Reject empty model assumptions list."""
    with pytest.raises(ValueError):
        EvidenceRequirements(model_assumptions=[], applicable_domain="test")


def test_contract_rejects_unsupported_schema_version():
    """Reject unsupported schema versions."""
    with pytest.raises(ValueError, match="Unsupported schema version"):
        DecisionIdentity(id="DEC-01", schema_version="2.0.0", title="T", question="Q")


# ==============================================================================
# WORKSTREAM D TESTS: SINGLE-QOI DECISION EVALUATOR & MATHEMATICS
# ==============================================================================

def test_evaluator_known_gaussian_calculation(valid_contract):
    """
    Test exact expected-loss calculation on a known Gaussian problem.
    Contract effective limit: limit (10.0) - margin (0.5) = 9.5 mm
    mu = 8.0 mm, sigma = 0.5 mm
    z = (9.5 - 8.0) / 0.5 = 3.0
    P_safe = Phi(3.0) approx 0.9986501
    P_fail = Phi(-3.0) approx 0.0013499
    C_FA = 1000, C_FR = 100
    R_release = 1000 * 0.0013499 = 1.3499
    R_reject = 100 * 0.9986501 = 99.865
    R_release << R_reject -> Decision: RELEASE
    """
    evaluator = SingleQoIEvaluator(valid_contract)
    res = evaluator.evaluate()

    assert res.recommendation == DecisionRecommendation.RELEASE
    assert pytest.approx(res.threshold_value, abs=1e-8) == 9.5
    assert pytest.approx(res.probability_fail, abs=1e-5) == float(ndtr(-3.0))
    assert pytest.approx(res.probability_safe, abs=1e-5) == float(ndtr(3.0))
    assert pytest.approx(res.expected_loss_release, abs=1e-4) == 1000.0 * float(ndtr(-3.0))
    assert pytest.approx(res.expected_loss_reject, abs=1e-4) == 100.0 * float(ndtr(3.0))
    assert res.decision_margin == pytest.approx(3.0, abs=1e-6)
    assert res.is_conclusive() is True


def test_evaluator_selects_reject_when_risk_exceeds(valid_contract):
    """
    Test that REJECT is selected when the design is likely unsafe.
    mu = 10.5 mm (effective limit = 9.5 mm)
    z = (9.5 - 10.5) / 0.5 = -2.0
    P_fail = Phi(2.0) approx 0.9772
    R_release = 1000 * 0.9772 = 977.2
    R_reject = 100 * 0.0228 = 2.28 -> REJECT
    """
    evaluator = SingleQoIEvaluator(valid_contract)
    res = evaluator.evaluate(mean=10.5, std=0.5)

    assert res.recommendation == DecisionRecommendation.REJECT
    assert res.expected_loss_release > res.expected_loss_reject
    assert res.probability_fail > 0.95


def test_evaluator_zero_variance_deterministic():
    """Test deterministic edge case where sigma = 0."""
    contract = DecisionContract(
        identity=DecisionIdentity(id="DEC-DET", title="Det", question="Q"),
        qoi=QuantityOfInterest(qoi_id="disp", name="Displacement", unit="mm"),
        criterion=AcceptanceCriterion(operator="<=", limit=10.0, unit="mm", safety_margin=0.0),
        predictive_distribution=PredictiveDistribution(family="normal", mean=9.0, std=0.0, unit="mm", provenance="det"),
        loss=DecisionLoss(cost_false_acceptance=500.0, cost_false_rejection=50.0),
        evidence=EvidenceRequirements(model_assumptions=["beam"], applicable_domain="linear"),
    )
    evaluator = SingleQoIEvaluator(contract)

    # mu = 9.0 <= 10.0 -> Safe with probability 1.0
    res = evaluator.evaluate()
    assert res.recommendation == DecisionRecommendation.RELEASE
    assert res.probability_safe == 1.0
    assert res.probability_fail == 0.0
    assert res.expected_loss_release == 0.0
    assert res.expected_loss_reject == 50.0


def test_evaluator_refusal_on_missing_uncertainty():
    """Evaluator refuses when predictive distribution is missing and not supplied."""
    contract = DecisionContract(
        identity=DecisionIdentity(id="DEC-NO-UQ", title="T", question="Q"),
        qoi=QuantityOfInterest(qoi_id="d", name="D", unit="mm"),
        criterion=AcceptanceCriterion(operator="<=", limit=5.0, unit="mm"),
        predictive_distribution=None,  # No predictive distribution
        loss=DecisionLoss(cost_false_acceptance=100.0, cost_false_rejection=10.0),
        evidence=EvidenceRequirements(model_assumptions=["linear"], applicable_domain="test"),
    )
    evaluator = SingleQoIEvaluator(contract)

    # Returns INSUFFICIENT_EVIDENCE when raise_on_refusal=False
    res = evaluator.evaluate(raise_on_refusal=False)
    assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
    assert "Missing predictive uncertainty distribution" in res.refusal_reason

    # Raises DecisionRefusalError when raise_on_refusal=True
    with pytest.raises(DecisionRefusalError, match="Missing predictive uncertainty distribution"):
        evaluator.evaluate(raise_on_refusal=True)


def test_evaluator_refusal_on_non_finite_inputs(valid_contract):
    """Evaluator refuses when mean, std, or limit are NaN or Inf."""
    evaluator = SingleQoIEvaluator(valid_contract)

    with pytest.raises(DecisionRefusalError, match="Non-finite input values"):
        evaluator.evaluate(mean=float("nan"), std=0.5, raise_on_refusal=True)

    with pytest.raises(DecisionRefusalError, match="Non-finite input values"):
        evaluator.evaluate(mean=8.0, std=float("inf"), raise_on_refusal=True)


def test_evaluator_dwr_quality_gate(valid_contract):
    """
    CRITICAL GUARDRAIL TEST:
    Verify that DWR error indicator is treated as an asymptotic indicator
    and triggers REFINE when relative error exceeds quality threshold (0.05 = 5%).
    It must NOT be converted to standard deviation or merged into predictive std.
    """
    evaluator = SingleQoIEvaluator(valid_contract)

    # Case 1: DWR indicator = 0.1 mm on mean = 8.0 mm -> 0.1 / 8.0 = 1.25% <= 5% -> Passes quality gate
    res_pass = evaluator.evaluate(mean=8.0, std=0.5, dwr_indicator=0.1)
    assert res_pass.recommendation == DecisionRecommendation.RELEASE
    assert res_pass.dwr_asymptotic_indicator == 0.1
    # Check that std remained exactly 0.5 (DWR was NOT combined into sigma!)
    assert res_pass.qoi_std == 0.5

    # Case 2: DWR indicator = 0.8 mm on mean = 8.0 mm -> 0.8 / 8.0 = 10% > 5% -> Triggers REFINE
    res_refine = evaluator.evaluate(mean=8.0, std=0.5, dwr_indicator=0.8)
    assert res_refine.recommendation == DecisionRecommendation.REFINE
    assert "Numerical discretization error indicator (10.0000%) exceeds contract quality threshold" in res_refine.refusal_reason
    assert res_refine.diagnostics["dwr_gate_breached"] is True


# ==============================================================================
# WORKSTREAM D TESTS: ANALYTICAL PARAMETER SCALING
# ==============================================================================

def test_analytical_scaling_exactness():
    """
    Verify exact analytical scaling formula:
    J(E, P) = (P / P_0) * (E_0 / E) * J_0
    """
    baseline = ReferenceBaseline(
        E_0=210e3,
        P_0=1000.0,
        J_0=4.5,
        poisson_ratio=0.3,
        dof_count=1200,
        qoi_name="tip_deflection",
    )
    scaler = RestrictedLinearElasticScaling(baseline)

    # Exact scaling tests
    # Double load P -> 2 * J_0 = 9.0
    assert scaler.evaluate_scalar(E=210e3, P=2000.0) == pytest.approx(9.0, abs=1e-12)

    # Half Young's modulus E -> 2 * J_0 = 9.0
    assert scaler.evaluate_scalar(E=105e3, P=1000.0) == pytest.approx(9.0, abs=1e-12)

    # Double both P and E -> 1.0 * J_0 = 4.5
    assert scaler.evaluate_scalar(E=420e3, P=2000.0) == pytest.approx(4.5, abs=1e-12)


def test_analytical_scaling_batch_evaluation():
    """Verify batch evaluation over sampled parameter distributions."""
    baseline = ReferenceBaseline(
        E_0=200e3,
        P_0=10.0,
        J_0=1.0,
        poisson_ratio=0.3,
        dof_count=500,
        qoi_name="tip_deflection",
    )
    scaler = RestrictedLinearElasticScaling(baseline)

    E_samples = np.array([200e3, 100e3, 400e3])
    P_samples = np.array([10.0, 10.0, 20.0])

    expected = np.array([1.0, 2.0, 1.0])
    J_results = scaler.evaluate_batch(E_samples, P_samples)
    np.testing.assert_allclose(J_results, expected, rtol=1e-12)

    mean_J, std_J = scaler.evaluate_moments(E_samples, P_samples)
    assert mean_J == pytest.approx(np.mean(expected), abs=1e-12)
    assert std_J == pytest.approx(np.std(expected, ddof=1), abs=1e-12)


def test_analytical_scaling_assumption_rejection():
    """Verify that scaler rejects invalid assumptions and non-positive parameters."""
    baseline = ReferenceBaseline(
        E_0=200e3,
        P_0=10.0,
        J_0=1.0,
        poisson_ratio=0.3,
        dof_count=500,
        qoi_name="tip_deflection",
    )

    # Rejection of negative Young's modulus in baseline
    with pytest.raises(ScalingAssumptionError, match="must be positive"):
        ReferenceBaseline(E_0=-100.0, P_0=10.0, J_0=1.0, poisson_ratio=0.3, dof_count=10, qoi_name="tip")

    # Rejection of zero load in baseline
    with pytest.raises(ScalingAssumptionError, match="cannot be zero"):
        ReferenceBaseline(E_0=100.0, P_0=0.0, J_0=1.0, poisson_ratio=0.3, dof_count=10, qoi_name="tip")

    # Rejection when non-uniform material scaling is flagged
    invalid_assumptions = ScalingAssumptions(uniform_material_scaling=False)
    with pytest.raises(ScalingAssumptionError, match="Multi-material or spatially heterogeneous"):
        RestrictedLinearElasticScaling(baseline, assumptions=invalid_assumptions)

    # Rejection when stress QoI is flagged
    stress_assumptions = ScalingAssumptions(compatible_displacement_qoi=False)
    with pytest.raises(ScalingAssumptionError, match="Stress QoIs or non-linear functionals"):
        RestrictedLinearElasticScaling(baseline, assumptions=stress_assumptions)
