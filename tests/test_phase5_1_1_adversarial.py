"""
Consolidated Adversarial Test Suite for GDEC Phase 5.1.1 Correctness Remediation.
Systematically validates fail-closed behavior across:
- Workstream A: CG Solver Eligibility, SPD Certification & Preconditioner Security
- Workstream B: DSE Evidence Enforcement, Domain Mismatch & Refusal Semantics
- Workstream C: Analytical Scaling Preconditions, Provenance & QoI Demarcation
- Workstream D: Matrix Discretisation & Numerical Quality Gates
"""

import math
import pytest
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from gdec.core.backend import (
    CPUBackend,
    CUDABackend,
    NumericalBackendError,
    UnsupportedCapabilityError,
    InputValidationError,
    detect_cuda_capability,
)
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
    RestrictedLinearElasticScaling,
    ReferenceBaseline,
    ScalingAssumptions,
    ScalingAssumptionError,
)

cuda_det = detect_cuda_capability()
CUDA_AVAILABLE = cuda_det.is_operational


# ==============================================================================
# WORKSTREAM A: CONJUGATE GRADIENT SOLVER SAFETY ADVERSARIAL TESTS
# ==============================================================================

class TestSolverSafetyAdversarial:
    """Adversarial stress tests for CPU and CUDA Conjugate Gradient eligibility."""

    def test_adv_cg_indefinite_with_positive_diagonal_cpu(self):
        """Matrix A = [[1, 2], [2, 1]] has diag > 0 but eigenvalues -1 and 3."""
        backend = CPUBackend()
        A = sp.csr_matrix([[1.0, 2.0], [2.0, 1.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(NumericalBackendError, match="Matrix A is indefinite"):
            backend.solve_cg(A, b, caller_certified_spd=False)

        # Allowed only when caller explicitly assumes liability
        x_cert, info = backend.solve_cg(A, b, caller_certified_spd=True)
        assert np.all(np.isfinite(x_cert))

    @pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA not operational")
    def test_adv_cg_indefinite_with_positive_diagonal_cuda(self):
        """CUDA backend must reject indefinite matrices identically to CPU."""
        backend = CUDABackend()
        A = sp.csr_matrix([[1.0, 2.0], [2.0, 1.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(NumericalBackendError, match="Matrix A is indefinite"):
            backend.solve_cg(A, b, caller_certified_spd=False)

    def test_adv_cg_asymmetric_matrix_rejection(self):
        """Asymmetric matrices must be rejected before any solve attempts."""
        backend = CPUBackend()
        A = sp.csr_matrix([[2.0, 5.0], [1.0, 2.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(NumericalBackendError, match="not symmetric"):
            backend.solve_cg(A, b, caller_certified_spd=False)

    def test_adv_cg_non_positive_diagonal_rejection(self):
        """Zero or negative diagonal entries must trigger immediate rejection."""
        backend = CPUBackend()
        A = sp.csr_matrix([[0.0, 1.0], [1.0, 4.0]])
        b = np.array([1.0, 1.0])

        with pytest.raises(NumericalBackendError, match="non-positive"):
            backend.solve_cg(A, b, caller_certified_spd=False)

    def test_adv_cg_untrusted_preconditioner_cpu(self):
        """CPU backend must reject preconditioner without is_spd=True."""
        backend = CPUBackend()
        A = sp.csr_matrix([[4.0, 1.0], [1.0, 4.0]])
        b = np.array([1.0, 1.0])

        untrusted_M = spla.LinearOperator(A.shape, matvec=lambda v: v)
        # untrusted_M does not have is_spd = True
        with pytest.raises(NumericalBackendError, match="SPD preconditioner"):
            backend.solve_cg(A, b, M=untrusted_M, caller_certified_spd=True)

    @pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA not operational")
    def test_adv_cg_cpu_preconditioner_passed_to_cuda(self):
        """CUDABackend must reject host CPU LinearOperator instances."""
        backend = CUDABackend()
        A = sp.csr_matrix([[4.0, 1.0], [1.0, 4.0]])
        b = np.array([1.0, 1.0])

        cpu_M = spla.LinearOperator(A.shape, matvec=lambda v: v)
        cpu_M.is_spd = True
        with pytest.raises(UnsupportedCapabilityError, match="CPU operator"):
            backend.solve_cg(A, b, M=cpu_M, caller_certified_spd=True)


# ==============================================================================
# WORKSTREAM B: DSE EVIDENCE ENFORCEMENT & REFUSAL ADVERSARIAL TESTS
# ==============================================================================

@pytest.fixture
def base_contract():
    return DecisionContract(
        identity=DecisionIdentity(
            id="DEC-TEST-ADV",
            schema_version="1.0.0",
            title="Adversarial Test Contract",
            question="Is the component safe for production release?",
        ),
        qoi=QuantityOfInterest(
            qoi_id="max_disp",
            name="Max Displacement",
            unit="mm",
            expected_sign="positive",
            model_reference="CantileverBeamModel-v1",
        ),
        criterion=AcceptanceCriterion(
            operator="<=",
            limit=5.0,
            unit="mm",
            safety_margin=0.5,  # Effective limit: 4.5 mm
        ),
        predictive_distribution=PredictiveDistribution(
            family="normal",
            mean=3.0,
            std=0.2,
            unit="mm",
            provenance="Verified FEM with UQ",
        ),
        loss=DecisionLoss(
            cost_false_acceptance=10000.0,
            cost_false_rejection=500.0,
            cost_unit="USD",
        ),
        evidence=EvidenceRequirements(
            required_categories=["mesh_convergence", "boundary_conditions"],
            model_assumptions=["linear_elasticity", "small_strain"],
            applicable_domain="aspect_ratio_le_10",
            numerical_quality_threshold=0.05,
            validation_status="verified",
        ),
        budget=ComputationalBudget(max_evaluations=10, max_wall_clock_seconds=30.0),
    )


@pytest.fixture
def base_evidence():
    return EvidenceAssessment(
        assessment_id="ASSESS-ADV-001",
        evidence_records=[
            EvidenceRecord(
                id="EV-MESH",
                category="mesh_convergence",
                provenance="Refined FEM Grid",
                model_reference="CantileverBeamModel-v1",
                applicable_domain="aspect_ratio_le_10",
                validation_status=ValidationStatus.VERIFIED,
                numerical_metric=0.005,
            ),
            EvidenceRecord(
                id="EV-BC",
                category="boundary_conditions",
                provenance="Clamped boundary certification",
                model_reference="CantileverBeamModel-v1",
                applicable_domain="aspect_ratio_le_10",
                validation_status=ValidationStatus.VERIFIED,
            ),
        ],
        validated_assumptions=["linear_elasticity", "small_strain"],
        model_reference="CantileverBeamModel-v1",
        applicable_domain="aspect_ratio_le_10",
        validation_status=ValidationStatus.VERIFIED,
        reference_scale=5.0,
        provenance="Quality Assurance Team",
    )


class TestDSEEvidenceEnforcementAdversarial:
    """Adversarial validation of DSE fail-closed refusal rules."""

    def test_adv_dse_missing_evidence_assessment(self, base_contract):
        """Evaluator must refuse to evaluate without an EvidenceAssessment."""
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=None)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Missing EvidenceAssessment" in res.refusal_reason

    def test_adv_dse_missing_required_category(self, base_contract):
        """Missing a declared required category must trigger INSUFFICIENT_EVIDENCE."""
        incomplete_evidence = EvidenceAssessment(
            assessment_id="ASSESS-INCOMPLETE",
            evidence_records=[
                EvidenceRecord(
                    id="EV-MESH",
                    category="mesh_convergence",
                    provenance="Refined Grid",
                    model_reference="CantileverBeamModel-v1",
                    applicable_domain="aspect_ratio_le_10",
                    validation_status=ValidationStatus.VERIFIED,
                )
                # "boundary_conditions" is missing!
            ],
            validated_assumptions=["linear_elasticity", "small_strain"],
            model_reference="CantileverBeamModel-v1",
            applicable_domain="aspect_ratio_le_10",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=5.0,
            provenance="QA",
        )
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=incomplete_evidence)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Missing required evidence categories" in res.refusal_reason

    def test_adv_dse_unattested_assumption(self, base_contract, base_evidence):
        """Unattested model assumption must trigger refusal."""
        bad_evidence = EvidenceAssessment(
            assessment_id="ASSESS-UNATTESTED",
            evidence_records=base_evidence.evidence_records,
            validated_assumptions=["linear_elasticity"],  # "small_strain" missing!
            model_reference="CantileverBeamModel-v1",
            applicable_domain="aspect_ratio_le_10",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=5.0,
            provenance="QA",
        )
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=bad_evidence)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Unattested model assumptions" in res.refusal_reason

    def test_adv_dse_domain_applicability_mismatch(self, base_contract, base_evidence):
        """Cross-domain spoofing must be caught and refused."""
        mismatched_domain = EvidenceAssessment(
            assessment_id="ASSESS-DIFF-DOMAIN",
            evidence_records=base_evidence.evidence_records,
            validated_assumptions=base_evidence.validated_assumptions,
            model_reference="CantileverBeamModel-v1",
            applicable_domain="aspect_ratio_gt_20",  # Mismatch!
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=5.0,
            provenance="QA",
        )
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=mismatched_domain)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Domain applicability mismatch" in res.refusal_reason

    def test_adv_dse_model_reference_mismatch(self, base_contract, base_evidence):
        """Mismatched model version must be rejected."""
        mismatched_model = EvidenceAssessment(
            assessment_id="ASSESS-DIFF-MODEL",
            evidence_records=base_evidence.evidence_records,
            validated_assumptions=base_evidence.validated_assumptions,
            model_reference="PlateModel-v2",  # Mismatch!
            applicable_domain="aspect_ratio_le_10",
            validation_status=ValidationStatus.VERIFIED,
            reference_scale=5.0,
            provenance="QA",
        )
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=mismatched_model)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Model reference mismatch" in res.refusal_reason

    def test_adv_dse_unit_mismatch(self, base_contract, base_evidence):
        """Mismatch between contract QoI unit and distribution unit must be rejected."""
        unit_mismatch_dist = PredictiveDistribution(
            family="normal",
            mean=0.003,
            std=0.0002,
            unit="m",  # Contract expects "mm"!
            provenance="SI converted",
        )
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(predictive_distribution=unit_mismatch_dist, evidence_assessment=base_evidence)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "unit 'm' does not match" in res.refusal_reason

    def test_adv_dse_dwr_breach_forces_refine(self, base_contract, base_evidence):
        """Discretization error breach must force REFINE even if design seems safe."""
        evaluator = SingleQoIEvaluator(base_contract)
        # Threshold is 0.05 (5%). DWR indicator = 0.5 on ref scale 5.0 -> 10% error!
        res = evaluator.evaluate(evidence_assessment=base_evidence, dwr_indicator=0.5)
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Mandatory Quality Breach" in res.refusal_reason
        assert res.diagnostics["dwr_gate_breached"] is True

    def test_adv_dse_negative_dwr_indicator(self, base_contract, base_evidence):
        """Negative DWR error indicator is mathematically invalid."""
        evaluator = SingleQoIEvaluator(base_contract)
        res = evaluator.evaluate(evidence_assessment=base_evidence, dwr_indicator=-0.1)
        assert res.recommendation == DecisionRecommendation.INSUFFICIENT_EVIDENCE
        assert "Invalid DWR indicator" in res.refusal_reason

    def test_adv_dse_exact_risk_tie_recommends_refine(self):
        """Exact risk tie must yield REFINE to prevent arbitrary release."""
        # Setup symmetric loss and symmetric 50% probability
        contract = DecisionContract(
            identity=DecisionIdentity(id="DEC-TIE", title="Tie", question="Q"),
            qoi=QuantityOfInterest(qoi_id="d", name="D", unit="mm"),
            criterion=AcceptanceCriterion(operator="<=", limit=10.0, unit="mm", safety_margin=0.0),
            predictive_distribution=PredictiveDistribution(family="normal", mean=10.0, std=1.0, unit="mm", provenance="sym"),
            loss=DecisionLoss(cost_false_acceptance=500.0, cost_false_rejection=500.0),
            evidence=EvidenceRequirements(required_categories=["cat"], model_assumptions=["beam"], applicable_domain="dom"),
        )
        ev = EvidenceAssessment(
            assessment_id="ASSESS-TIE",
            evidence_records=[
                EvidenceRecord(
                    id="EV-1",
                    category="cat",
                    provenance="test",
                    model_reference="m",
                    applicable_domain="dom",
                    validation_status=ValidationStatus.VERIFIED,
                )
            ],
            validated_assumptions=["beam"],
            model_reference="m",
            applicable_domain="dom",
            validation_status=ValidationStatus.VERIFIED,
            provenance="QA",
        )
        evaluator = SingleQoIEvaluator(contract)
        res = evaluator.evaluate(evidence_assessment=ev)
        assert res.recommendation == DecisionRecommendation.REFINE
        assert "Exact Risk Tie" in res.refusal_reason


# ==============================================================================
# WORKSTREAM C: ANALYTICAL SCALING PRECONDITIONS ADVERSARIAL TESTS
# ==============================================================================

class TestScalingAssumptionsAdversarial:
    """Adversarial testing of linear-elastic parameter scaling guardrails."""

    @pytest.fixture
    def baseline(self):
        return ReferenceBaseline(
            E_0=210e3,
            P_0=1000.0,
            J_0=2.5,
            poisson_ratio=0.3,
            dof_count=2000,
            qoi_name="tip_deflection",
        )

    def test_adv_scaling_rejects_compliance_qoi(self, baseline):
        """Compliance scales as P^2/E, not P/E; must be strictly rejected."""
        assumptions = ScalingAssumptions(
            uniform_material_scaling=True,
            fixed_geometry=True,
            fixed_poisson_ratio=True,
            linear_elastic_regime=True,
            proportional_loading=True,
            compatible_displacement_qoi=True,
            qoi_type="compliance",
            attested_by="analyst",
        )
        with pytest.raises(ScalingAssumptionError, match="scales quadratically"):
            RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

    def test_adv_scaling_rejects_stress_qoi(self, baseline):
        """Stress QoIs do not scale identically to tip displacement."""
        assumptions = ScalingAssumptions(
            uniform_material_scaling=True,
            fixed_geometry=True,
            fixed_poisson_ratio=True,
            linear_elastic_regime=True,
            proportional_loading=True,
            compatible_displacement_qoi=False,
            qoi_type="von_mises_stress",
            attested_by="analyst",
        )
        with pytest.raises(ScalingAssumptionError, match="Stress QoIs"):
            RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

    def test_adv_scaling_rejects_missing_attestation_provenance(self, baseline):
        """Assumptions without attested_by provenance must be rejected."""
        assumptions = ScalingAssumptions(
            uniform_material_scaling=True,
            fixed_geometry=True,
            fixed_poisson_ratio=True,
            linear_elastic_regime=True,
            proportional_loading=True,
            compatible_displacement_qoi=True,
            attested_by="",  # Unattested!
        )
        with pytest.raises(ScalingAssumptionError, match="explicit attestation provenance"):
            RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

    def test_adv_scaling_rejects_non_finite_batch_inputs(self, baseline):
        """Batch scaling must reject arrays containing NaN or Inf."""
        assumptions = ScalingAssumptions(
            uniform_material_scaling=True,
            fixed_geometry=True,
            fixed_poisson_ratio=True,
            linear_elastic_regime=True,
            proportional_loading=True,
            compatible_displacement_qoi=True,
            attested_by="analyst",
        )
        scaler = RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

        with pytest.raises(ScalingAssumptionError, match="non-finite"):
            scaler.evaluate_batch(np.array([210e3, float("nan")]), np.array([1000.0, 1000.0]))

        with pytest.raises(ScalingAssumptionError, match="non-finite"):
            scaler.evaluate_batch(np.array([210e3, 210e3]), np.array([1000.0, float("inf")]))

    def test_adv_scaling_rejects_empty_batch(self, baseline):
        """Empty batch arrays must be rejected."""
        assumptions = ScalingAssumptions(
            uniform_material_scaling=True,
            fixed_geometry=True,
            fixed_poisson_ratio=True,
            linear_elastic_regime=True,
            proportional_loading=True,
            compatible_displacement_qoi=True,
            attested_by="analyst",
        )
        scaler = RestrictedLinearElasticScaling(baseline, assumptions=assumptions)

        with pytest.raises(ScalingAssumptionError, match="empty"):
            scaler.evaluate_batch(np.array([]), np.array([]))
