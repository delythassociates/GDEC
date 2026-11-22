"""
Phase 5.1.3 Adversarial Test Suite for DSE Numerical Evidence Integrity.
Validates record-level DWR binding, metric semantics, unit checking,
reference scale validation, conflicting metric refusal, and duplicate provenance audit.
"""

import math
import pytest
from gdec.dse.contract import (
    DecisionContract,
    DecisionIdentity,
    QuantityOfInterest,
    AcceptanceCriterion,
    PredictiveDistribution,
    DecisionLoss,
    EvidenceRequirements,
    ComputationalBudget,
)
from gdec.dse.evidence import (
    EvidenceRecord,
    EvidenceAssessment,
    ValidationStatus,
    EvidenceEligibility,
)
from gdec.dse.evaluator import (
    SingleQoIEvaluator,
    DecisionRecommendation,
    DecisionEvaluationResult,
    DecisionRefusalError,
)


@pytest.fixture
def base_contract():
    return DecisionContract(
        identity=DecisionIdentity(
            id="DEC-ADV-513",
            title="Adversarial Validation Contract Phase 5.1.3",
            question="Is the deflection safe under strict evidence integrity?",
        ),
        qoi=QuantityOfInterest(
            qoi_id="tip_deflection",
            name="Vertical Tip Displacement",
            unit="mm",
            model_reference="BeamModel-2D",
        ),
        criterion=AcceptanceCriterion(
            operator="<=",
            limit=10.0,
            unit="mm",
            safety_margin=0.5,
        ),
        predictive_distribution=PredictiveDistribution(
            family="normal",
            mean=8.0,
            std=0.5,
            unit="mm",
            provenance="FEM Simulation with DWR UQ",
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
            known_limitations=[],
        ),
        budget=ComputationalBudget(
            max_evaluations=10,
            max_wall_clock_seconds=30.0,
            enforced=False,
        ),
    )


class TestDSEPhase513EvidenceIntegrity:
    """Adversarial tests mandated by Phase 5.1.3 Workstream A."""

    # 1. Accepted record followed by rejected record in same category
    def test_01_accepted_followed_by_rejected_record_poisons_category(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-01",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-GOOD",
                    category="mesh_convergence",
                    provenance="Fine mesh",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-MESH-BAD",
                    category="mesh_convergence",
                    provenance="Discredited run",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.REJECTED,
                    numerical_metric=0.50,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "explicitly rejected/discredited" in res.refusal_reason

    # 2. Accepted record followed by incompatible-model record in DWR category
    def test_02_accepted_followed_by_incompatible_model_record(self, base_contract):
        # The incompatible model record must not be selected as the DWR metric source
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-02",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-VALID",
                    category="mesh_convergence",
                    provenance="Valid 2D model",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.02,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-MESH-OTHER-MODEL",
                    category="mesh_convergence",
                    provenance="3D plate model",
                    model_reference="PlateModel-3D",  # Mismatch!
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.50,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.RELEASE
        assert res.selected_dwr_record_id == "EV-MESH-VALID"
        assert res.diagnostics["selected_dwr_record_id"] == "EV-MESH-VALID"

    # 3. Accepted record followed by incompatible-domain record in DWR category
    def test_03_accepted_followed_by_incompatible_domain_record(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-03",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-DOM-VALID",
                    category="mesh_convergence",
                    provenance="Valid domain",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.015,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-MESH-DOM-OTHER",
                    category="mesh_convergence",
                    provenance="Short stubby beam",
                    model_reference="BeamModel-2D",
                    applicable_domain="deep_beam_aspect_ratio_le_2",  # Domain mismatch!
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.80,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.RELEASE
        assert res.selected_dwr_record_id == "EV-MESH-DOM-VALID"

    # 4. Accepted record followed by unassessed record in DWR category
    def test_04_accepted_followed_by_unassessed_record(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-04",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-CERTIFIED",
                    category="mesh_convergence",
                    provenance="Certified study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-MESH-UNASSESSED",
                    category="mesh_convergence",
                    provenance="Draft unreviewed run",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.UNASSESSED,  # Unassessed!
                    numerical_metric=0.99,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.RELEASE
        assert res.selected_dwr_record_id == "EV-MESH-CERTIFIED"

    # 5. Conflicting DWR values across eligible records forces refusal
    def test_05_conflicting_dwr_values_refusal(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-05",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-1",
                    category="mesh_convergence",
                    provenance="Study A",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-MESH-2",
                    category="mesh_convergence",
                    provenance="Study B",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.04,  # Conflicting metric!
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Conflicting DWR metrics detected" in res.refusal_reason
        assert "Explicit refusal policy enforced" in res.refusal_reason

    # 6. Incorrect units in DWR record
    def test_06_incorrect_units_refusal(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-06",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-UNIT-BAD",
                    category="mesh_convergence",
                    provenance="Stress study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="MPa",  # QoI is mm, record is MPa!
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Incompatible units" in res.refusal_reason
        assert "MPa" in res.refusal_reason

    # 7. Missing reference scale
    def test_07_missing_reference_scale_refusal(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-07",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="Mesh study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=None,  # Missing reference scale!
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Missing positive reference_scale" in res.refusal_reason

    # 8. Zero and near-zero reference scale
    def test_08_near_zero_reference_scale_refusal(self, base_contract):
        with pytest.raises(Exception):
            # Pydantic gt=0.0 rejects 0.0 at validation
            EvidenceAssessment(
                assessment_id="ASSESS-513-08",
                evidence_records=[],
                validated_assumptions=["linear_elasticity"],
                model_reference="BeamModel-2D",
                applicable_domain="cantilever_aspect_ratio_ge_5",
                reference_scale=0.0,
                provenance="Auditor",
            )

        # Near-zero scale (1e-15 > 0 passes Pydantic gt=0, but caught by evaluator)
        assessment_tiny = EvidenceAssessment(
            assessment_id="ASSESS-513-08B",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-01",
                    category="mesh_convergence",
                    provenance="Mesh study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=1e-15,  # Near-zero!
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment_tiny)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Non-positive or near-zero reference_scale" in res.refusal_reason

    # 9. Wrong category used as DWR evidence
    def test_09_wrong_category_used_as_dwr_evidence(self, base_contract):
        # boundary_conditions has a numerical metric, but mesh_convergence has none!
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-09",
            evidence_records=[
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.001,  # Metric in non-DWR category
                ),
                EvidenceRecord(
                    id="EV-MESH-NO-METRIC",
                    category="mesh_convergence",
                    provenance="Visual check",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    # numerical_metric is None!
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Mandatory Discretization Quality Evidence Missing" in res.refusal_reason

    # 10. DWR metric supplied by ineligible record (status EXPIRED)
    def test_10_dwr_metric_supplied_by_expired_record(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-10",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-EXPIRED",
                    category="mesh_convergence",
                    provenance="Old revision study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.EXPIRED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "explicitly rejected/discredited" in res.refusal_reason

    # 11. Duplicate records with conflicting provenance
    def test_11_duplicate_records_conflicting_provenance(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-11",
            evidence_records=[
                EvidenceRecord(
                    id="EV-RECORD-DUP",
                    category="mesh_convergence",
                    provenance="Original laboratory study",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-RECORD-DUP",  # Same ID!
                    category="mesh_convergence",
                    provenance="Contradictory third-party audit",  # Conflicting provenance!
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.01,
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "conflicting provenance" in res.refusal_reason

    # 12. Caller-supplied dwr_indicator cannot bypass missing eligible record
    def test_12_caller_dwr_cannot_bypass_missing_eligible_record(self, base_contract):
        # Assessment has NO mesh_convergence record, but caller provides dwr_indicator=0.01
        assessment_no_mesh = EvidenceAssessment(
            assessment_id="ASSESS-513-12",
            evidence_records=[
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(
            evidence_assessment=assessment_no_mesh,
            dwr_indicator=0.01,
        )
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "cannot bypass missing eligible evidence" in res.refusal_reason or "Missing required evidence categories" in res.refusal_reason

    # 13. Negative DWR metric is rejected
    def test_13_negative_dwr_metric_rejected(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-13",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-NEG",
                    category="mesh_convergence",
                    provenance="Faulty estimator",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=-0.05,  # Negative!
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "negative" in res.refusal_reason.lower()

    # 14. DWR above threshold forces REFINE
    def test_14_dwr_above_threshold_forces_refine(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-14",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-COARSE",
                    category="mesh_convergence",
                    provenance="Coarse mesh",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.VERIFIED,
                    numerical_metric=0.80,  # 0.80 / 10.0 = 8.0% > 5.0% threshold
                    units="mm",
                ),
                EvidenceRecord(
                    id="EV-BC-01",
                    category="boundary_conditions",
                    provenance="Wall fixture audit",
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
        res = SingleQoIEvaluator(base_contract).evaluate(evidence_assessment=assessment)
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Mandatory Quality Breach" in res.refusal_reason
        assert res.selected_dwr_record_id == "EV-MESH-COARSE"

    # 15. Raise on refusal contract conformance
    def test_15_raise_on_refusal_conformance(self, base_contract):
        assessment = EvidenceAssessment(
            assessment_id="ASSESS-513-15",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH-REJ",
                    category="mesh_convergence",
                    provenance="Bad run",
                    model_reference="BeamModel-2D",
                    applicable_domain="cantilever_aspect_ratio_ge_5",
                    validation_status=ValidationStatus.REJECTED,
                ),
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="BeamModel-2D",
            applicable_domain="cantilever_aspect_ratio_ge_5",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=10.0,
            provenance="Auditor",
        )
        with pytest.raises(DecisionRefusalError):
            SingleQoIEvaluator(base_contract).evaluate(
                evidence_assessment=assessment,
                raise_on_refusal=True,
            )
