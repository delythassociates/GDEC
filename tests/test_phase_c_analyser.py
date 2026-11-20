"""
Unit and Integration Tests for Phase C Problem Analyser and Accuracy Contracts.
Verifies:
1. Valid spatial discretisation uncertainty estimation (GCI) and contract issuance.
2. Conservative order cap p_cap = 2.0 for higher observed orders.
3. Deterministic refusal of ill-posed singular point stress.
4. Deterministic refusal of unsupported point displacement.
5. Deterministic refusal of poor-quality meshes (< 10 deg min angle).
6. Deterministic refusal of unconverged solver residuals (> 1e-10).
7. Deterministic refusal of differences below numerical floor (< 1e-13).
8. Deterministic refusal of non-monotonic or diverging sequences (q <= 1.0).
9. Deterministic refusal of out-of-window observed orders (p_obs < 0.5 or > 3.5).
10. Deterministic refusal priority enforcement.
11. Four-grid M3 asymptotic stability validation.
"""

import pytest
import numpy as np
import skfem as fem
from gdec.core.analyser import ProblemAnalyser, AccuracyTarget, RefusalCode


def test_contract_issuance_valid_asymptotic_convergence():
    analyser = ProblemAnalyser()
    # J0, J1, J2 exhibiting quadratic convergence (p_obs = 2.0)
    # J(h) = 1.0 + 0.04 * h^2
    # J0 = 1.04, J1 = 1.01, J2 = 1.0025
    # d01 = 0.03, d12 = 0.0075 -> q = 4.0 -> p_obs = 2.0
    J0 = 1.04
    J1 = 1.01
    J2 = 1.0025
    target = AccuracyTarget(target_type="relative", tolerance=0.10, qoi_scale=1.0)

    res = analyser.evaluate_contract(J0, J1, J2, target=target)

    assert res.issued is True
    assert res.status == "verified_contract_issued"
    assert res.uncertainty is not None
    assert np.isclose(res.uncertainty["observed_order"], 2.0, atol=1e-6)
    assert np.isclose(res.uncertainty["order_used"], 2.0, atol=1e-6)
    # U0 = Fs * |d01| * (4/3) = 1.25 * 0.03 * (4/3) = 0.05
    assert np.isclose(res.uncertainty["value"], 0.05, atol=1e-6)
    assert res.accuracy is not None
    assert res.accuracy["estimated_target_met"] is True
    assert res.accuracy["status"] == "estimated_target_met"


def test_order_cap_enforcement():
    analyser = ProblemAnalyser(order_cap_p_cap=2.0)
    # d01 = 0.08, d12 = 0.01 -> q = 8.0 -> p_obs = 3.0
    J0 = 1.09
    J1 = 1.01
    J2 = 1.00
    res = analyser.evaluate_contract(J0, J1, J2)

    assert res.issued is True
    assert np.isclose(res.uncertainty["observed_order"], 3.0, atol=1e-6)
    # Must be capped at 2.0
    assert np.isclose(res.uncertainty["order_used"], 2.0, atol=1e-6)
    # Factor uses p_used = 2.0: factor = 4/3
    expected_u0 = 1.25 * 0.08 * (4.0 / 3.0)
    assert np.isclose(res.uncertainty["value"], expected_u0, atol=1e-6)


def test_refusal_singular_point_stress():
    analyser = ProblemAnalyser()
    qoi_spec = {"type": "point_stress", "location": [0.0, 0.0], "is_singular_point": True}
    res = analyser.evaluate_contract(100.0, 110.0, 115.0, qoi_spec=qoi_spec)

    assert res.issued is False
    assert res.status == RefusalCode.ILL_POSED_QOI.value
    assert res.refusal["code"] == RefusalCode.ILL_POSED_QOI.value
    assert res.uncertainty is None


def test_refusal_unsupported_point_displacement():
    analyser = ProblemAnalyser()
    qoi_spec = {"type": "point_displacement", "location": [0.5, 0.5]}
    res = analyser.evaluate_contract(0.01, 0.008, 0.007, qoi_spec=qoi_spec)

    assert res.issued is False
    assert res.status == RefusalCode.UNSUPPORTED_QOI.value
    assert res.refusal["code"] == RefusalCode.UNSUPPORTED_QOI.value


def test_refusal_mesh_quality_failure():
    analyser = ProblemAnalyser(min_angle_threshold_deg=10.0)
    # Degenerate angle = 5.0 deg
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, mesh_min_angle_deg=5.0)

    assert res.issued is False
    assert res.status == RefusalCode.MESH_QUALITY_FAILURE.value
    assert res.refusal["code"] == RefusalCode.MESH_QUALITY_FAILURE.value


def test_mesh_quality_calculator():
    analyser = ProblemAnalyser()
    # Good equilateral triangle mesh
    m_good = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    valid, min_angle = analyser.check_mesh_quality(m_good)
    assert valid is True
    assert min_angle >= 40.0

    # Create degenerate stretched triangle (y coordinates very small)
    p_bad = np.array([[0.0, 1.0, 0.5], [0.0, 0.0, 0.001]])
    t_bad = np.array([[0], [1], [2]])
    m_bad = fem.MeshTri(p_bad, t_bad)
    valid_bad, min_angle_bad = analyser.check_mesh_quality(m_bad)
    assert valid_bad is False
    assert min_angle_bad < 5.0


def test_refusal_solver_not_converged():
    analyser = ProblemAnalyser(solver_residual_tol=1e-10)
    # Relative residual = 1e-6 (unconverged)
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, solver_relative_residual=1e-6)

    assert res.issued is False
    assert res.status == RefusalCode.SOLVER_NOT_CONVERGED.value


def test_refusal_numerical_difference_floor():
    analyser = ProblemAnalyser(numerical_floor=1e-13)
    # d01 and d12 are at 1e-15 (below floor)
    J0 = 1.000000000000001
    J1 = 1.000000000000000
    J2 = 1.000000000000000
    res = analyser.evaluate_contract(J0, J1, J2)

    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR.value


def test_refusal_non_asymptotic_oscillating():
    analyser = ProblemAnalyser()
    # Oscillating: d01 = 0.02, d12 = -0.01 (d01 * d12 < 0)
    J0 = 1.02
    J1 = 1.00
    J2 = 1.01
    res = analyser.evaluate_contract(J0, J1, J2)

    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value


def test_refusal_diverging_mesh():
    analyser = ProblemAnalyser()
    # Diverging: d01 = 0.01, d12 = 0.02 (q = 0.5 < 1)
    J0 = 1.01
    J1 = 1.00
    J2 = 0.98
    res = analyser.evaluate_contract(J0, J1, J2)

    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value


def test_refusal_implausible_observed_order():
    analyser = ProblemAnalyser(order_window=(0.5, 3.5))
    # Super-asymptotic order: d01 = 0.16, d12 = 0.001 -> q = 160 -> p_obs = 7.32 > 3.5
    J0 = 1.161
    J1 = 1.001
    J2 = 1.000
    res = analyser.evaluate_contract(J0, J1, J2)

    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_ORDER.value


def test_deterministic_priority_order():
    analyser = ProblemAnalyser()
    # Both ill-posed QoI (priority 1) AND bad mesh angle (priority 4) present
    qoi_spec = {"type": "point_stress", "is_singular_point": True}
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, qoi_spec=qoi_spec, mesh_min_angle_deg=2.0)

    # Ill-posed QoI must take precedence over mesh quality
    assert res.status == RefusalCode.ILL_POSED_QOI.value
    assert res.refusal["priority"] == 1


def test_four_grid_m3_stability_validation():
    analyser = ProblemAnalyser()
    # J0, J1, J2, J3 with consistent p_obs = 2.0
    J0 = 1.04
    J1 = 1.01
    J2 = 1.0025
    J3 = 1.000625
    res = analyser.evaluate_contract(J0, J1, J2, J3=J3)

    assert res.issued is True
    assert res.verification["m3_stability"] is True
    assert np.isclose(res.verification["p_obs_123"], 2.0, atol=1e-6)


def test_refusal_patch_average_stress_unsupported():
    """AM1-09: patch_average_stress must be strictly refused with UNSUPPORTED_QOI."""
    analyser = ProblemAnalyser()
    qoi_spec = {"type": "patch_average_stress", "patch": [0.4, 0.6, 0.4, 0.6]}
    res = analyser.evaluate_contract(10.0, 9.0, 8.5, qoi_spec=qoi_spec)

    assert res.issued is False
    assert res.status == RefusalCode.UNSUPPORTED_QOI.value
    assert res.refusal["code"] == RefusalCode.UNSUPPORTED_QOI.value


def test_refusal_invalid_geometry():
    """AM1-14: invalid geometry flag or non-finite coords must refuse with INVALID_GEOMETRY."""
    analyser = ProblemAnalyser()
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, geometry_valid=False)

    assert res.issued is False
    assert res.status == RefusalCode.INVALID_GEOMETRY.value
    assert res.refusal["priority"] == 3


def test_refusal_insufficient_levels():
    """AM1-14: insufficient mesh levels (< 3) must refuse with UNVERIFIED_INSUFFICIENT_LEVELS."""
    analyser = ProblemAnalyser()
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, mesh_levels=2)

    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value
    assert res.refusal["priority"] == 6


def test_mesh_quality_zero_area_degenerate():
    """AM1-13: zero-area collinear triangle must return (False, 0.0) without division error."""
    analyser = ProblemAnalyser()
    # Vertices on a straight line: (0,0), (1,0), (2,0) -> zero area
    p_zero = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 0.0]])
    t_zero = np.array([[0], [1], [2]])
    m_zero = fem.MeshTri(p_zero, t_zero)

    is_valid, min_angle = analyser.check_mesh_quality(m_zero)
    assert is_valid is False
    assert min_angle == 0.0


def test_accuracy_target_requires_explicit_positive_scale():
    """AM1-11: AccuracyTarget must raise ValueError if relative target has missing/non-positive scale."""
    with pytest.raises(ValueError, match="Explicit positive finite qoi_scale is strictly required"):
        AccuracyTarget(target_type="relative", tolerance=0.01, qoi_scale=0.0)

    with pytest.raises(ValueError, match="Explicit positive finite qoi_scale is strictly required"):
        AccuracyTarget(target_type="relative", tolerance=0.01, qoi_scale=-1.0)


def test_budget_exhaustion_semantics_am2_03():
    """AM2-03: Budget exhaustion must not overturn an achieved accuracy target."""
    analyser = ProblemAnalyser()
    # U0 = 0.05, tolerance = 0.10 -> U0 <= tolerance
    target_met_spec = AccuracyTarget(target_type="relative", tolerance=0.10, qoi_scale=1.0)
    # U0 = 0.05, tolerance = 0.02 -> U0 > tolerance
    target_unmet_spec = AccuracyTarget(target_type="relative", tolerance=0.02, qoi_scale=1.0)

    # 1. Budget exhausted before target attainment (target unmet)
    res1 = analyser.evaluate_contract(1.04, 1.01, 1.0025, target=target_unmet_spec, budget_exhausted=True)
    assert res1.issued is True
    assert res1.accuracy["estimated_target_met"] is False
    assert res1.accuracy["status"] == "estimated_target_not_met"
    assert res1.accuracy["budget_exhausted"] is True

    # 2. Budget exhausted after target attainment (target met)
    res2 = analyser.evaluate_contract(1.04, 1.01, 1.0025, target=target_met_spec, budget_exhausted=True)
    assert res2.issued is True
    assert res2.accuracy["estimated_target_met"] is True
    assert res2.accuracy["status"] == "estimated_target_met"
    assert res2.accuracy["budget_exhausted"] is True

    # 3. Budget not exhausted and target met
    res3 = analyser.evaluate_contract(1.04, 1.01, 1.0025, target=target_met_spec, budget_exhausted=False)
    assert res3.issued is True
    assert res3.accuracy["estimated_target_met"] is True
    assert res3.accuracy["status"] == "estimated_target_met"
    assert res3.accuracy["budget_exhausted"] is False

    # 4. Budget not exhausted and target not met
    res4 = analyser.evaluate_contract(1.04, 1.01, 1.0025, target=target_unmet_spec, budget_exhausted=False)
    assert res4.issued is True
    assert res4.accuracy["estimated_target_met"] is False
    assert res4.accuracy["status"] == "estimated_target_not_met"
    assert res4.accuracy["budget_exhausted"] is False

    # 5. Valid uncertainty available but target unmet
    assert res4.uncertainty is not None
    assert np.isclose(res4.uncertainty["value"], 0.05, atol=1e-6)
    assert np.isclose(res4.accuracy["evaluated_uncertainty_metric"], 0.05, atol=1e-6)


def test_verification_mode_four_grid_enforcement_am2_04():
    """AM2-04: verification_mode='four_grid' requires M3 and strictly enforces stability."""
    analyser = ProblemAnalyser()
    J0 = 1.04
    J1 = 1.01
    J2 = 1.0025

    # Missing J3 in four_grid mode must refuse with UNVERIFIED_INSUFFICIENT_LEVELS
    res_no_m3 = analyser.evaluate_contract(J0, J1, J2, verification_mode="four_grid")
    assert res_no_m3.issued is False
    assert res_no_m3.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value

    # J3 with stability failure in four_grid mode must refuse with UNVERIFIED_NON_ASYMPTOTIC
    J3_bad = 1.0025 - 0.00375  # delta_p = 1.0 > 0.50
    res_bad = analyser.evaluate_contract(J0, J1, J2, J3=J3_bad, verification_mode="four_grid")
    assert res_bad.issued is False
    assert res_bad.status == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value

    # J3 with passing stability in four_grid mode issues four_grid_verified_contract_issued
    J3_good = 1.000625  # p123 = 2.0 -> delta_p = 0.0
    res_good = analyser.evaluate_contract(J0, J1, J2, J3=J3_good, verification_mode="four_grid")
    assert res_good.issued is True
    assert res_good.status == "four_grid_verified_contract_issued"
    assert res_good.verification["four_grid_status"] == "four_grid_stability_passed"


def test_reference_uncertainty_refusal_gate_am2_05():
    """AM2-05 & AM2-07: Reference uncertainty exceeding frozen gate (0.05%) must be refused."""
    analyser = ProblemAnalyser(reference_uncertainty_gate=0.0005)
    # reference_uncertainty = 0.0012 (0.12% > 0.05%)
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, reference_uncertainty=0.0012)
    assert res.issued is False
    assert res.status == RefusalCode.REFERENCE_UNCERTAIN.value
    assert res.refusal["priority"] == 10

    # reference_uncertainty = 0.0003 (0.03% <= 0.05%)
    res_ok = analyser.evaluate_contract(1.04, 1.01, 1.0025, reference_uncertainty=0.0003)
    assert res_ok.issued is True


def test_numerical_input_validation_am2_05():
    """AM2-05: Non-finite values or negative residuals must raise ValueError."""
    analyser = ProblemAnalyser()
    with pytest.raises(ValueError, match="QoI value J0 must be finite"):
        analyser.evaluate_contract(np.nan, 1.01, 1.0025)

    with pytest.raises(ValueError, match="solver_relative_residual must be a non-negative finite float"):
        analyser.evaluate_contract(1.04, 1.01, 1.0025, solver_relative_residual=-1e-5)

    with pytest.raises(ValueError, match="solver_relative_residual must be a non-negative finite float"):
        analyser.evaluate_contract(1.04, 1.01, 1.0025, solver_relative_residual=np.nan)


def test_refinement_ratio_validation_am2_05():
    """AM2-05: Inconsistent refinement ratio (e.g. r=1.5 instead of 2.0) must refuse."""
    analyser = ProblemAnalyser()
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, refinement_ratio=1.5)
    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value
    assert "r=1.50" in res.refusal["reason"]


def test_m3_stability_refusal_when_required():
    """AM1-01: When require_m3_stability=True, M3 stability failure triggers refusal."""
    analyser = ProblemAnalyser()
    # J0, J1, J2 have p_012 = 2.0 (q = 4.0)
    # J3 has p_123 = 1.0 (d23 = 0.00375 -> q123 = 2.0 -> p_123 = 1.0)
    # |p_012 - p_123| = 1.0 > 0.50
    J0 = 1.04
    J1 = 1.01
    J2 = 1.0025
    J3 = 1.0025 - 0.00375  # d23 = 0.00375 -> d12/d23 = 0.0075 / 0.00375 = 2.0 -> p123 = 1.0

    # With require_m3_stability=True -> Refusal
    res_strict = analyser.evaluate_contract(J0, J1, J2, J3=J3, require_m3_stability=True)
    assert res_strict.issued is False
    assert res_strict.status == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value
    assert res_strict.refusal["code"] == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value

    # With require_m3_stability=False -> Issued with stability flag noted
    res_lax = analyser.evaluate_contract(J0, J1, J2, J3=J3, require_m3_stability=False)
    assert res_lax.issued is True
    assert res_lax.status == "verified_contract_issued"
    assert res_lax.verification["four_grid_status"] == "four_grid_stability_failed"
    assert res_lax.verification["m3_stability"] is False


def test_four_grid_verified_contract_status():
    """AM1-10: When M3 is stable, status is 'four_grid_verified_contract_issued'."""
    analyser = ProblemAnalyser()
    J0 = 1.04
    J1 = 1.01
    J2 = 1.0025
    J3 = 1.000625
    res = analyser.evaluate_contract(J0, J1, J2, J3=J3)

    assert res.issued is True
    assert res.status == "four_grid_verified_contract_issued"
    assert res.verification["four_grid_status"] == "four_grid_stability_passed"
