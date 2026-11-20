"""
Unit and Adversarial Tests for GDEC Phase C Amendment 3.
Verifies:
1. AM3-01: Dynamic M3 construction and multi-order quadrature geometric tail bounding (<= 1.0%).
2. AM3-02: Family 4 exact analytical QoI formulas, sign reconciliation (ux vs uy), and quadrature concordance.
3. AM3-03: Typed mesh hierarchy validation (MeshLevelEvidence), parent-child hash continuity, uniform doubling.
4. AM3-03: Deterministic rejection of invalid verification modes (three_grid / four_grid enforcement).
5. AM3-03: Scale-aware dimensionless geometry validation across s in {1e-6, 1.0, 1e6}.
6. Adversarial suite: Falsified refinement ratios, non-monotonic h, broken parent hashes, duplicated levels,
   insufficient levels, and degenerate geometries across scales.
"""

import math
import numpy as np
import pytest
import scipy.integrate as integrate
import skfem as fem

from gdec.core.analyser import ProblemAnalyser, RefusalCode, MeshLevelEvidence, AccuracyTarget
from gdec.runtime.mesh_evidence import (
    compute_mesh_hash,
    compute_characteristic_h,
    build_mesh_hierarchy_evidence,
)
from verification.phase_c.amendment_3.quadrature_study import (
    solve_case_b_with_quadrature,
)


# ============================================================================
# AM3-01: Quadrature Reproducibility and Dynamic M3 Convergence
# ============================================================================

def test_dynamic_m3_quadrature_convergence_am3_01():
    """AM3-01: Dynamic construction of M3 and verification of geometric convergence without hardcoding."""
    m0 = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 6), np.linspace(0.0, 1.0, 6)).oriented()
    m1 = m0.refined()
    m2 = m1.refined()
    m3 = m2.refined()

    assert m3.t.shape[1] == 3200
    assert m3.p.shape[1] == 1681

    alpha = 1.40
    j_exact = float((0.6 ** 2.4 - 0.2 ** 2.4) / (2.4 * 0.4))
    j_m3_26 = solve_case_b_with_quadrature(m3, alpha=alpha, n_1d=13)
    e_smallest_m3 = abs(j_m3_26 - j_exact)

    # Dynamic error must be finite and positive
    assert 5.0e-5 < e_smallest_m3 < 5.5e-5

    # Check M2 geometric sensitivities
    j14 = solve_case_b_with_quadrature(m2, alpha=alpha, n_1d=7)
    j18 = solve_case_b_with_quadrature(m2, alpha=alpha, n_1d=9)
    j22 = solve_case_b_with_quadrature(m2, alpha=alpha, n_1d=11)
    j26 = solve_case_b_with_quadrature(m2, alpha=alpha, n_1d=13)

    d14_18 = abs(j14 - j18)
    d18_22 = abs(j18 - j22)
    d22_26 = abs(j22 - j26)

    assert d14_18 > d18_22 > d22_26 > 0.0

    rho = d22_26 / d18_22
    assert 0.0 < rho < 1.0, f"Geometric convergence violated: rho={rho}"

    e_tail = d22_26 / (1.0 - rho)
    ratio_to_e_m3 = e_tail / e_smallest_m3

    # Frozen threshold: residual quadrature error <= 1.0% of M3 spatial discretisation error
    assert ratio_to_e_m3 <= 0.010, f"Residual quadrature tail exceeds 1.0%: {ratio_to_e_m3:.4e}"


# ============================================================================
# AM3-02: Family 4 Exact QoI Sign and Formula Reconciliation
# ============================================================================

def test_family4_qoi_sign_reconciliation_am3_02():
    """AM3-02: Rigorous verification of Family 4 displacement patch averages for ux vs uy."""
    kx, ky = 0.006, 0.0024

    # Displacement fields:
    # ux = kx * x * y + ky * y^2
    # uy = -ky * x^2 + kx * x * y

    # Patch averages on [0.25, 0.75]^2:
    # ux_patch = 0.25 * kx + (13/48) * ky  (positive ky term)
    # uy_patch = 0.25 * kx - (13/48) * ky  (negative ky term)
    ux_patch_analytical = 0.25 * kx + (13.0 / 48.0) * ky
    uy_patch_analytical = 0.25 * kx - (13.0 / 48.0) * ky

    # Independent high-precision SciPy quadrature
    ux_patch_quad, _ = integrate.dblquad(
        lambda y, x: kx * x * y + ky * y**2,
        0.25, 0.75, lambda x: 0.25, lambda x: 0.75
    )
    ux_patch_quad /= 0.25

    uy_patch_quad, _ = integrate.dblquad(
        lambda y, x: -ky * x**2 + kx * x * y,
        0.25, 0.75, lambda x: 0.25, lambda x: 0.75
    )
    uy_patch_quad /= 0.25

    assert np.isclose(ux_patch_analytical, ux_patch_quad, atol=1e-15)
    assert np.isclose(uy_patch_analytical, uy_patch_quad, atol=1e-15)

    # Prove sign distinction between ux and uy
    diff_sign = ux_patch_analytical - uy_patch_analytical
    expected_diff = 2.0 * (13.0 / 48.0) * ky
    assert np.isclose(diff_sign, expected_diff, atol=1e-15)


# ============================================================================
# AM3-03: Mesh Hierarchy Evidence, Mode Enforcement & Scale Invariance
# ============================================================================

def test_mesh_hierarchy_evidence_construction_and_validation():
    """AM3-03: Verifies build_mesh_hierarchy_evidence and validate_mesh_hierarchy."""
    m0 = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 4), np.linspace(0.0, 1.0, 4)).oriented()
    m1 = m0.refined()
    m2 = m1.refined()
    m3 = m2.refined()

    evidence = build_mesh_hierarchy_evidence([m0, m1, m2, m3], ["M0", "M1", "M2", "M3"])
    assert len(evidence) == 4

    # Check parent hashes
    assert evidence[0].parent_mesh_hash is None
    assert evidence[1].parent_mesh_hash == evidence[0].mesh_hash
    assert evidence[2].parent_mesh_hash == evidence[1].mesh_hash
    assert evidence[3].parent_mesh_hash == evidence[2].mesh_hash

    # Check refinement ratios
    for ev in evidence[1:]:
        assert np.isclose(ev.refinement_ratio, 2.0, rtol=0.05)

    analyser = ProblemAnalyser()

    # Three-grid validation on M0..M2
    ok3, code3, reason3 = analyser.validate_mesh_hierarchy(evidence[:3], verification_mode="three_grid")
    assert ok3 is True
    assert code3 is None

    # Four-grid validation on M0..M3
    ok4, code4, reason4 = analyser.validate_mesh_hierarchy(evidence, verification_mode="four_grid")
    assert ok4 is True
    assert code4 is None

    # Three levels in four-grid mode must fail closed
    ok_fail, code_fail, _ = analyser.validate_mesh_hierarchy(evidence[:3], verification_mode="four_grid")
    assert ok_fail is False
    assert code_fail == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS


def test_verification_mode_rejection_of_invalid_mode():
    """AM3-03: Invalid verification_mode strings must be deterministically rejected with ValueError."""
    analyser = ProblemAnalyser()
    m = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 3), np.linspace(0.0, 1.0, 3))
    ev = build_mesh_hierarchy_evidence([m, m.refined(), m.refined().refined()])

    with pytest.raises(ValueError, match="Invalid verification mode"):
        analyser.validate_mesh_hierarchy(ev, verification_mode="two_grid")

    with pytest.raises(ValueError, match="Invalid verification mode"):
        analyser.evaluate_contract(1.04, 1.01, 1.0025, verification_mode="adaptive")


def test_scale_aware_geometry_validation():
    """AM3-03 & AM3-AC-07: Dimensionless scale invariance across s in {1e-6, 1.0, 1e6}."""
    analyser = ProblemAnalyser(min_angle_threshold_deg=10.0)

    # Base unit mesh (oriented)
    m_base = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, 4), np.linspace(0.0, 1.0, 4)).oriented()

    for scale in [1e-6, 1.0, 1e6]:
        p_scaled = m_base.p * scale
        m_scaled = fem.MeshTri(p_scaled, m_base.t).oriented()

        # Check mesh quality: angles and scale-aware areas/edges must be valid
        is_valid_q, min_angle = analyser.check_mesh_quality(m_scaled)
        assert is_valid_q is True, f"Failed at scale {scale}"
        assert min_angle >= 10.0, f"Angle failed at scale {scale}"

        # Validate geometry: must accept scaled valid mesh
        is_valid_g, refusal_code, _ = analyser.validate_geometry(m_scaled)
        assert is_valid_g is True, f"Geometry validation failed at scale {scale}"
        assert refusal_code is None


# ============================================================================
# Adversarial Hierarchy & Contract Refusal Tests
# ============================================================================

def test_adversarial_hierarchy_missing_parent():
    """Adversarial: Mesh level with corrupted/missing parent hash must fail closed."""
    analyser = ProblemAnalyser()
    m0 = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    evidence = build_mesh_hierarchy_evidence([m0, m0.refined(), m0.refined().refined()])

    # Corrupt parent hash on level 2
    bad_evidence = list(evidence)
    bad_evidence[2] = MeshLevelEvidence(
        level_id="M2",
        mesh_hash=bad_evidence[2].mesh_hash,
        element_count=bad_evidence[2].element_count,
        node_count=bad_evidence[2].node_count,
        characteristic_h=bad_evidence[2].characteristic_h,
        parent_mesh_hash="deadbeef12345678",  # Wrong parent hash
        refinement_ratio=2.0,
        nestedness_verified=True,
    )

    ok, code, reason = analyser.validate_mesh_hierarchy(bad_evidence, verification_mode="three_grid")
    assert ok is False
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    assert "does not match previous level" in reason

    # Test via evaluate_contract
    res = analyser.evaluate_contract(1.04, 1.01, 1.0025, mesh_hierarchy=bad_evidence)
    assert res.issued is False
    assert res.status == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value


def test_adversarial_hierarchy_falsified_refinement_ratio():
    """Adversarial: Falsely claimed refinement ratio contradicting actual h must be caught."""
    analyser = ProblemAnalyser()
    m0 = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    evidence = build_mesh_hierarchy_evidence([m0, m0.refined(), m0.refined().refined()])

    bad_evidence = list(evidence)
    # Level 1 claimed ratio 3.5 when actual is 2.0
    bad_evidence[1] = MeshLevelEvidence(
        level_id="M1",
        mesh_hash=bad_evidence[1].mesh_hash,
        element_count=bad_evidence[1].element_count,
        node_count=bad_evidence[1].node_count,
        characteristic_h=bad_evidence[1].characteristic_h,
        parent_mesh_hash=bad_evidence[1].parent_mesh_hash,
        refinement_ratio=3.50,  # Falsified ratio!
        nestedness_verified=True,
    )

    ok, code, reason = analyser.validate_mesh_hierarchy(bad_evidence)
    assert ok is False
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    assert "contradicts independently calculated ratio" in reason


def test_adversarial_hierarchy_non_monotonic_h():
    """Adversarial: Non-monotonic or coarsening characteristic h must be rejected."""
    analyser = ProblemAnalyser()
    m0 = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    evidence = build_mesh_hierarchy_evidence([m0, m0.refined(), m0.refined().refined()])

    bad_evidence = list(evidence)
    # Level 2 h is larger than Level 1 (coarsened instead of refined)
    bad_evidence[2] = MeshLevelEvidence(
        level_id="M2",
        mesh_hash="hash_m2",
        element_count=8,
        node_count=9,
        characteristic_h=bad_evidence[1].characteristic_h * 1.5,
        parent_mesh_hash=bad_evidence[1].mesh_hash,
        refinement_ratio=0.67,
        nestedness_verified=True,
    )

    ok, code, reason = analyser.validate_mesh_hierarchy(bad_evidence)
    assert ok is False
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    assert "not strictly decreasing" in reason


def test_adversarial_hierarchy_duplicate_levels():
    """Adversarial: Duplicated levels with identical mesh hashes must be rejected."""
    analyser = ProblemAnalyser()
    m0 = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    evidence = build_mesh_hierarchy_evidence([m0, m0.refined(), m0.refined().refined()])

    bad_evidence = [evidence[0], evidence[1], evidence[1]]  # M1 duplicated

    ok, code, reason = analyser.validate_mesh_hierarchy(bad_evidence)
    assert ok is False
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    assert "duplicate mesh hash" in reason


def test_adversarial_degenerate_mesh_at_all_scales():
    """Adversarial: Collinear zero-area triangles must be caught at scales s in {1e-6, 1.0, 1e6}."""
    analyser = ProblemAnalyser()
    p_zero = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 0.0]])
    t_zero = np.array([[0], [1], [2]])

    for scale in [1e-6, 1.0, 1e6]:
        m_degen = fem.MeshTri(p_zero * scale, t_zero)
        is_valid, _ = analyser.check_mesh_quality(m_degen)
        assert is_valid is False, f"Zero area element escaped check at scale {scale}"

        is_valid_g, code, _ = analyser.validate_geometry(m_degen)
        assert is_valid_g is False, f"Degenerate geometry escaped check at scale {scale}"
        assert code == RefusalCode.INVALID_GEOMETRY
