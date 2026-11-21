"""
GDEC Phase 5.1.2 Dedicated DSE Adversarial Test Suite.
Validates the complete 20-scenario evidence integrity matrix:
1. Rejected required evidence
2. Unvalidated required evidence
3. Missing provenance
4. Wrong model reference
5. Wrong domain
6. Missing DWR indicator when required
7. DWR evidence above threshold
8. Assessment status conflicts with record status
9. Duplicate evidence categories
10. Conflicting evidence records
11. Missing assumptions
12. Unit mismatch
13. NaN/Inf metric
14. Invalid probability / distribution parameters
15. Zero variance
16. Exact risk tie
17. Missing required category
18. Extra irrelevant evidence
19. Incompatible evidence mixed with valid evidence
20. Attempt to bypass a mandatory gate
"""

import math
import pytest
import numpy as np

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
    ValidationStatus,
    EvidenceRecord,
    EvidenceAssessment,
    EvidenceEligibility,
    RecordEvaluationReport,
)


@pytest.fixture
def contract():
    """Standard baseline contract for adversarial testing."""
    return DecisionContract(
        identity=DecisionIdentity(
            id="DEC-ADV-512",
            schema_version="1.0.0",
            title="Adversarial Validation Contract",
            question="Is the structural margin sufficient for release?",
        ),
        qoi=QuantityOfInterest(
            qoi_id="tip_disp",
            name="Tip Displacement",
            unit="mm",
            expected_sign="positive",
            model_reference="BeamModel-2D",
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
            std=0.4,
            unit="mm",
            provenance="Verified FEM solver with UQ",
        ),
        loss=DecisionLoss(
            cost_false_acceptance=1000.0,
            cost_false_rejection=100.0,
            cost_unit="USD",
        ),
        evidence=EvidenceRequirements(
            required_categories=["mesh_convergence", "boundary_conditions"],
            model_assumptions=["linear_elasticity", "small_strain"],
            applicable_domain="cantilever_aspect_ratio_ge_5",
            numerical_quality_threshold=0.05,
            validation_status="verified",
        ),
        budget=ComputationalBudget(max_evaluations=10, max_wall_clock_seconds=30.0),
    )


@pytest.fixture
def valid_assessment():
    """Fully compliant baseline EvidenceAssessment matching contract."""
    return EvidenceAssessment(
        assessment_id="ASSESS-VALID-01",
        evidence_records=[
            EvidenceRecord(
                id="EV-MESH-01",
                category="mesh_convergence",
                provenance="Richardson extrapolation tool",
                model_reference="BeamModel-2D",
                applicable_domain="cantilever_aspect_ratio_ge_5",
                validation_status=ValidationStatus.VERIFIED,
                numerical_metric=0.01,
            ),
            EvidenceRecord(
                id="EV-BC-01",
                category="boundary_conditions",
                provenance="Clamping fixture stiffness audit",
                model_reference="BeamModel-2D",
                applicable_domain="cantilever_aspect_ratio_ge_5",
                validation_status=ValidationStatus.VERIFIED,
            ),
        ],
        validated_assumptions=["linear_elasticity", "small_strain"],
        model_reference="BeamModel-2D",
        applicable_domain="cantilever_aspect_ratio_ge_5",
        validation_status=ValidationStatus.VERIFIED,
        reference_scale=10.0,
        provenance="Lead Integrity Auditor",
    )


class TestDSEAdversarialMatrix20:
    """Systematic validation of all 20 adversarial evidence conditions."""

    # 1. Rejected required evidence
    def test_01_rejected_required_evidence(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-REJ-01",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-REJ",
                    category="mesh_convergence",
                    provenance="Audit report",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.REJECTED,
                    numerical_metric=0.02,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "rejected/discredited" in res.refusal_reason

    # 2. Unvalidated required evidence
    def test_02_unvalidated_required_evidence(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-UNVAL-02",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-UNVAL",
                    category="mesh_convergence",
                    provenance="Draft",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.UNVALIDATED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "no acceptable evidence records" in res.refusal_reason

    # 3. Missing provenance
    def test_03_missing_provenance(self, contract):
        # Empty provenance is rejected at model creation
        with pytest.raises(Exception):
            EvidenceRecord(
                id="EV-MESH-EMPTYPROV",
                category="mesh_convergence",
                provenance="",
                model_reference="BeamModel-2D",
                applicable_domain="cantilever_aspect_ratio_ge_5",
                validation_status=ValidationStatus.VERIFIED,
            )

        # Whitespace-only provenance passes Pydantic min_length=1 but is rejected by eligibility auditor
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-NOPROV-03",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="   ",  # Whitespace-only provenance!
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "lacks explicit provenance" in res.refusal_reason

    # 4. Wrong model reference
    def test_04_wrong_model_reference(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-DIFFMODEL-04",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="Audit",
                    model_reference="PlateModel-3D",  # Model mismatch!
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "does not match contract target model" in res.refusal_reason

    # 5. Wrong domain
    def test_05_wrong_domain(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-DIFFDOM-05",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="deep_beam_ratio_le_2",  # Domain mismatch!
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "does not match contract envelope" in res.refusal_reason

    # 6. Missing DWR indicator when required
    def test_06_missing_dwr_indicator_when_required(self):
        contract_dwr = DecisionContract(
            identity=DecisionIdentity(id="DEC-DWR", title="T", question="Q"),
            qoi=QuantityOfInterest(qoi_id="u", name="U", unit="mm", model_reference="M"),
            criterion=AcceptanceCriterion(operator="<=", limit=10.0, unit="mm"),
            predictive_distribution=PredictiveDistribution(family="normal", mean=5.0, std=0.5, unit="mm", provenance="FEM"),
            loss=DecisionLoss(cost_false_acceptance=1000.0, cost_false_rejection=100.0),
            evidence=EvidenceRequirements(
                required_categories=["discretization_error"],
                model_assumptions=["elastic"],
                applicable_domain="dom",
                numerical_quality_threshold=0.05,
            ),
        )
        # Assessment without numerical_metric on discretization_error
        ev_nodwr = EvidenceAssessment(
            assessment_id="ASSESS-NODWR",
            evidence_records=[
                EvidenceRecord(
                    id="EV-1",
                    category="discretization_error",
                    provenance="Audit",
                    model_reference="M",
                    applicable_domain="dom",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=None,  # No metric!
                )
            ],
            validated_assumptions=["elastic"],
            model_reference="M",
            applicable_domain="dom",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract_dwr).evaluate(evidence_assessment=ev_nodwr, dwr_indicator=None)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Mandatory Discretization Quality Evidence Missing" in res.refusal_reason

    # 7. DWR evidence above threshold
    def test_07_dwr_above_threshold_forces_refine(self, contract, valid_assessment):
        # Threshold is 5%. With indicator 1.0 on scale 10.0 -> 10% error -> REFINE
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=valid_assessment, dwr_indicator=1.0)
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Mandatory Quality Breach" in res.refusal_reason

    # 8. Assessment status conflicts with record status
    def test_08_assessment_status_conflicts_with_record_status(self, contract):
        # Assessment declares VERIFIED, but record has REJECTED
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-CONFLICT-08",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-REJ",
                    category="mesh_convergence",
                    provenance="Auditor",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.REJECTED,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Auditor",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,  # Overall says VERIFIED!
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "rejected/discredited" in res.refusal_reason

    # 9. Duplicate evidence categories (both valid)
    def test_09_duplicate_evidence_categories_both_valid(self, contract):
        # Two valid records for mesh_convergence (e.g. h-refinement and p-refinement)
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-DUP-09",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-H",
                    category="mesh_convergence",
                    provenance="h-refinement study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-MESH-P",
                    category="mesh_convergence",
                    provenance="p-refinement study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.008,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment, dwr_indicator=0.1)
        assert res.recommendation == DecisionRecommendation.RELEASE

    # 10. Conflicting evidence records (one valid, one rejected)
    def test_10_conflicting_evidence_records(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-CONFLICT-10",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-GOOD",
                    category="mesh_convergence",
                    provenance="Author",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-MESH-BAD",
                    category="mesh_convergence",
                    provenance="Reviewer Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.REJECTED,
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "rejected/discredited" in res.refusal_reason

    # 11. Missing assumptions
    def test_11_missing_assumptions(self, contract, valid_assessment):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-NOASM-11",
            evidence_records=valid_assessment.evidence_records,
            validated_assumptions=["linear_elasticity"],  # "small_strain" missing!
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Unattested model assumptions" in res.refusal_reason

    # 12. Unit mismatch
    def test_12_unit_mismatch(self, contract, valid_assessment):
        dist_m = PredictiveDistribution(
            family="normal", mean=0.008, std=0.0004, unit="m", provenance="SI metric"
        )
        res = SingleQoIEvaluator(contract).evaluate(
            predictive_distribution=dist_m, evidence_assessment=valid_assessment
        )
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "does not match contract QoI unit" in res.refusal_reason

    # 13. NaN/Inf metric
    def test_13_nan_metric(self, contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-NAN-13",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-NAN",
                    category="mesh_convergence",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=float("nan"),  # NaN!
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "invalid non-finite" in res.refusal_reason

    # 14. Invalid distribution parameters (negative std)
    def test_14_invalid_distribution_parameters(self, contract, valid_assessment):
        with pytest.raises(Exception):
            PredictiveDistribution(family="normal", mean=8.0, std=-1.0, unit="mm", provenance="Bad")

    # 15. Zero variance deterministic safe design
    def test_15_zero_variance_deterministic(self, contract, valid_assessment):
        dist_det = PredictiveDistribution(
            family="normal", mean=8.0, std=0.0, unit="mm", provenance="Deterministic"
        )
        res = SingleQoIEvaluator(contract).evaluate(
            predictive_distribution=dist_det, evidence_assessment=valid_assessment, dwr_indicator=0.05
        )
        assert res.recommendation == DecisionRecommendation.RELEASE
        assert res.probability_safe == 1.0
        assert res.probability_fail == 0.0

    # 16. Exact risk tie
    def test_16_exact_risk_tie(self):
        c_tie = DecisionContract(
            identity=DecisionIdentity(id="DEC-TIE", title="T", question="Q"),
            qoi=QuantityOfInterest(qoi_id="x", name="X", unit="mm", model_reference="M"),
            criterion=AcceptanceCriterion(operator="<=", limit=10.0, unit="mm", safety_margin=0.0),
            predictive_distribution=PredictiveDistribution(family="normal", mean=10.0, std=1.0, unit="mm", provenance="sym"),
            loss=DecisionLoss(cost_false_acceptance=500.0, cost_false_rejection=500.0),
            evidence=EvidenceRequirements(
                required_categories=["cat"],
                model_assumptions=["elastic"],
                applicable_domain="dom",
                numerical_quality_threshold=0.05,
            ),
        )
        ev_tie = EvidenceAssessment(
            assessment_id="ASSESS-TIE",
            evidence_records=[
                EvidenceRecord(
                    id="EV-1",
                    category="cat",
                    provenance="Audit",
                    model_reference="M",
                    applicable_domain="dom",
                    validation_status=ValidationStatus.VERIFIED,
                )
            ],
            validated_assumptions=["elastic"],
            model_reference="M",
            applicable_domain="dom",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(c_tie).evaluate(evidence_assessment=ev_tie)
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Exact Risk Tie" in res.refusal_reason

    # 17. Missing required category
    def test_17_missing_required_category(self, contract):
        ev_missing = EvidenceAssessment(
            assessment_id="ASSESS-MISSING-17",
            evidence_records=[
                EvidenceRecord(
                    id="EV-1",
                    category="mesh_convergence",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                )
                # boundary_conditions is missing!
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=ev_missing)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Missing required evidence categories" in res.refusal_reason

    # 18. Extra irrelevant evidence
    def test_18_extra_irrelevant_evidence(self, contract, valid_assessment):
        # Adding an extra irrelevant category (e.g. thermal_expansion) does not invalidate required categories
        records = list(valid_assessment.evidence_records) + [
            EvidenceRecord(
                id="EV-EXTRA",
                category="thermal_expansion",
                provenance="Thermal audit",
                model_reference="BeamModel-2D",
                applicable_domain="cantilever_aspect_ratio_ge_5",
                validation_status=ValidationStatus.VERIFIED,
            )
        ]
        ev_extra = EvidenceAssessment(
            assessment_id="ASSESS-EXTRA-18",
            evidence_records=records,
            validated_assumptions=valid_assessment.validated_assumptions,
            model_reference=valid_assessment.model_reference,
            applicable_domain=valid_assessment.applicable_domain,
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=ev_extra, dwr_indicator=0.05)
        assert res.recommendation == DecisionRecommendation.RELEASE

    # 19. Incompatible evidence mixed with valid evidence
    def test_19_incompatible_evidence_mixed(self, contract):
        # mesh_convergence is valid, but boundary_conditions belongs to a different model
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-MIXED-19",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="Audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                ),
                EvidenceRecord(
                    id="EV-BC-BAD",
                    category="boundary_conditions",
                    provenance="Audit",
                    model_reference="DifferentModel-3D",  # Model mismatch!
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "does not match contract target model" in res.refusal_reason

    # 20. Attempt to bypass mandatory gate
    def test_20_attempt_to_bypass_mandatory_gate(self, contract, valid_assessment):
        # Even if probability of failure is nearly zero, a DWR breach MUST force REFINE
        safe_dist = PredictiveDistribution(
            family="normal", mean=2.0, std=0.1, unit="mm", provenance="Safe"
        )
        # Relative DWR = 2.0 / 10.0 = 20% > 5% threshold
        res = SingleQoIEvaluator(contract).evaluate(
            predictive_distribution=safe_dist,
            evidence_assessment=valid_assessment,
            dwr_indicator=2.0,
        )
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Mandatory Quality Breach" in res.refusal_reason
