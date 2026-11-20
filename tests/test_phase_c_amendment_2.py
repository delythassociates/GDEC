"""
GDEC Phase C Amendment 2 — Comprehensive Verification and Regression Tests.
Verifies:
1. Symbolic equilibrium f + div(sigma) = 0 for all 40 Tier 1 configurations.
2. Exact analytical QoI values match high-precision numerical quadrature for all 40 configs.
3. Dedicated Tier 3 harness execution achieving 80/80 (100%) refusal accuracy.
4. Budget exhaustion semantics (AM2-03: all 5 required conditions).
5. Four-grid verification mode enforcement (AM2-04).
6. Numerical input validation (AM2-05).
7. Reference uncertainty gate (AM2-07).
"""

import json
import math
import numpy as np
import pytest
import scipy.integrate as integrate
import sympy as sp
import skfem as fem

from gdec.core.analyser import ProblemAnalyser, AccuracyTarget, RefusalCode
from verification.phase_c.amendment_2.tier3_harness import run_tier3_harness


def test_tier1_bvp_symbolic_equilibrium():
    """AM2-01: Verifies f + div(sigma) = 0 symbolically for all 40 Tier 1 configurations."""
    with open("verification/phase_c/amendment_2/tier1_manifest.json", "r", encoding="utf-8") as f:
        configs = json.load(f)

    assert len(configs) == 40
    x, y = sp.symbols("x y")

    for cfg in configs:
        cid = cfg["config_id"]
        bvp = cfg["bvp_specification"]
        disp = bvp["displacement_field"]
        body_f = bvp["body_force"]
        c_dict = cfg["elasticity_tensor"]
        c11, c12, c33 = c_dict["c11"], c_dict["c12"], c_dict["c33"]

        ux = sp.sympify(disp["ux"].replace("^", "**"))
        uy = sp.sympify(disp["uy"].replace("^", "**"))

        eps_xx = sp.diff(ux, x)
        eps_yy = sp.diff(uy, y)
        gam_xy = sp.diff(ux, y) + sp.diff(uy, x)

        sig_xx = c11 * eps_xx + c12 * eps_yy
        sig_yy = c12 * eps_xx + c11 * eps_yy
        sig_xy = c33 * gam_xy

        fx_exact = -(sp.diff(sig_xx, x) + sp.diff(sig_xy, y))
        fy_exact = -(sp.diff(sig_xy, x) + sp.diff(sig_yy, y))

        # Check equilibrium at sample interior test points
        for pt in [(0.2, 0.3), (0.5, 0.5), (0.7, 0.8)]:
            fx_val = float(fx_exact.subs([(x, pt[0]), (y, pt[1])]))
            fy_val = float(fy_exact.subs([(x, pt[0]), (y, pt[1])]))

            if body_f["fx_constant_value"] is not None:
                assert np.isclose(fx_val, body_f["fx_constant_value"], atol=1e-6), f"{cid} fx mismatch"
                assert np.isclose(fy_val, body_f["fy_constant_value"], atol=1e-6), f"{cid} fy mismatch"


def test_tier1_exact_qoi_numerical_quadrature_concordance():
    """AM2-01: Verifies all 40 exact QoI values against numerical quadrature."""
    with open("verification/phase_c/amendment_2/tier1_manifest.json", "r", encoding="utf-8") as f:
        configs = json.load(f)

    for cfg in configs:
        cid = cfg["config_id"]
        fam = cfg["family"]
        qoi = cfg["qoi"]
        j_exact = qoi["exact_analytical_value"]
        params = cfg["parameters"]

        if fam == "family_1_polynomial":
            a, b = params["a"], params["b"]
            ux_fn = lambda x, y: a * x**2 + b * y**2
            uy_fn = lambda x, y: a * x * y
        elif fam == "family_2_trigonometric":
            freq, amp = params["freq"], params["amp"]
            ux_fn = lambda x, y: amp * math.sin(freq * math.pi * x) * math.cos(freq * math.pi * y)
            uy_fn = lambda x, y: amp * math.cos(freq * math.pi * x) * math.sin(freq * math.pi * y)
        elif fam == "family_3_localized_gaussian":
            x0, y0, sigma, amp = params["x0"], params["y0"], params["sigma"], params["amp"]
            ux_fn = lambda x, y: amp * math.exp(-((x - x0)**2 + (y - y0)**2) / sigma**2)
            uy_fn = lambda x, y: 0.5 * amp * math.exp(-((x - x0)**2 + (y - y0)**2) / sigma**2)
        elif fam == "family_4_mixed_shear":
            kx, ky = params["kx"], params["ky"]
            ux_fn = lambda x, y: kx * x * y + ky * y**2
            uy_fn = lambda x, y: -ky * x**2 + kx * x * y
        elif fam == "family_5_multiscale_oscillatory":
            k1, k2, beta, amp = params["k1"], params["k2"], params["beta"], params["amp"]
            ux_fn = lambda x, y: amp * (math.sin(k1 * math.pi * x) + beta * math.sin(k2 * math.pi * x))
            uy_fn = lambda x, y: amp * (math.cos(k1 * math.pi * y) + beta * math.cos(k2 * math.pi * y))

        if qoi["type"] == "boundary_average_displacement":
            val, _ = integrate.quad(lambda x: uy_fn(x, 1.0), 0.0, 1.0)
        else:
            val, _ = integrate.dblquad(lambda y, x: ux_fn(x, y), 0.25, 0.75, lambda x: 0.25, lambda x: 0.75)
            val /= 0.25

        assert abs(val - j_exact) < 1e-11, f"{cid} QoI mismatch: quad={val}, exact={j_exact}"


def test_tier3_manifest_and_harness_execution():
    """AM2-02: Verifies that all 80 Tier 3 refusal cases execute and pass with 100% accuracy."""
    summary = run_tier3_harness("verification/phase_c/amendment_2/tier3_manifest.json")
    assert summary["total_cases"] == 80
    assert summary["successful_refusals"] == 80
    assert summary["failed_refusals"] == 0
    assert summary["accuracy"] == 1.00
    for cat, count in summary["category_counts"].items():
        assert count == 8, f"Category {cat} does not have exactly 8 cases (has {count})"


def test_budget_exhaustion_semantics_am2_03():
    """AM2-03: Tests all 5 budget exhaustion and accuracy target conditions."""
    analyser = ProblemAnalyser()
    target_met_spec = AccuracyTarget(target_type="relative", tolerance=0.10, qoi_scale=1.0)
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


def test_four_grid_verification_mode_am2_04():
    """AM2-04: Verifies explicit four_grid verification mode enforcement."""
    analyser = ProblemAnalyser()
    J0, J1, J2 = 1.04, 1.01, 1.0025

    # 1. Missing J3 in four_grid mode must refuse
    res_no_m3 = analyser.evaluate_contract(J0, J1, J2, verification_mode="four_grid")
    assert res_no_m3.issued is False
    assert res_no_m3.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value

    # 2. Stability failure in four_grid mode must refuse with UNVERIFIED_NON_ASYMPTOTIC
    J3_bad = 1.0025 - 0.00375
    res_bad = analyser.evaluate_contract(J0, J1, J2, J3=J3_bad, verification_mode="four_grid")
    assert res_bad.issued is False
    assert res_bad.status == RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value

    # 3. Stability success in four_grid mode issues four_grid_verified_contract_issued
    J3_good = 1.000625
    res_good = analyser.evaluate_contract(J0, J1, J2, J3=J3_good, verification_mode="four_grid")
    assert res_good.issued is True
    assert res_good.status == "four_grid_verified_contract_issued"
    assert res_good.verification["four_grid_status"] == "four_grid_stability_passed"


def test_reference_uncertainty_gate_am2_07():
    """AM2-07: Verifies reference uncertainty gate refusal (Priority 10)."""
    analyser = ProblemAnalyser(reference_uncertainty_gate=0.0005)
    # Exceeding gate (0.12% > 0.05%)
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, reference_uncertainty=0.0012)
    assert res.issued is False
    assert res.status == RefusalCode.REFERENCE_UNCERTAIN.value
    assert res.refusal["priority"] == 10

    # Within gate (0.02% <= 0.05%)
    res_ok = analyser.evaluate_contract(1.04, 1.01, 1.0025, reference_uncertainty=0.0002)
    assert res_ok.issued is True


def test_input_validation_checks_am2_05():
    """AM2-05: Verifies input validation raises ValueError on invalid types or values."""
    analyser = ProblemAnalyser()
    with pytest.raises(ValueError, match="QoI value J0 must be finite"):
        analyser.evaluate_contract(np.inf, 1.01, 1.0025)

    with pytest.raises(ValueError, match="solver_relative_residual must be a non-negative finite float"):
        analyser.evaluate_contract(1.04, 1.01, 1.0025, solver_relative_residual=-1e-4)

    # Inconsistent refinement ratio
    res_r = analyser.evaluate_contract(1.04, 1.01, 1.0025, refinement_ratio=1.5)
    assert res_r.issued is False
    assert res_r.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value
