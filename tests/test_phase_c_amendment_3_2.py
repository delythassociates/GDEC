"""
Phase C Amendment 3.2 — Comprehensive Adversarial Verification Test Suite.

Covers all required adversarial cases across:
1. Mesh Topology Verification (Section 4.5 & AM32-01)
2. Mathematical BVP Verification (Section 5.4 & AM32-02)
3. Deep Immutability & Canonical Serialization (Section 6.3 & AM32-03)
4. Quadrature Consistency & Precision-Floor Semantics (Section 7.3 & AM32-04)
"""

import copy
import dataclasses
import json
from pathlib import Path
import numpy as np
import pytest
import skfem as fem

from gdec.core.analyser import (
    MeshHierarchyStatus,
    MeshLevelEvidence,
    ProblemAnalyser,
    RefusalCode,
)
from gdec.runtime.mesh_evidence import (
    build_mesh_hierarchy_evidence,
    validate_mesh_pair_topology,
    verify_mesh_refinement_topology,
)
from verification.phase_c.amendment_3_2.quadrature_study import (
    QuadratureConvergenceStatus,
    assess_quadrature_convergence,
)
from verification.phase_c.amendment_3_2.verify_tier1_bvps import (
    BVPVerificationStatus,
    verify_tier1_bvp_manifest,
)


# ============================================================================
# Section 1: Mesh Topology Adversarial Cases (AM32-01)
# ============================================================================

def test_topology_vertex_outside_parent_even_if_centroid_inside():
    """
    Adversarial Case 1.1:
    Child element has centroid inside parent triangle, but one vertex extends outside.
    Must fail child-in-parent containment.
    """
    p_parent = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    t_parent = np.array([[0], [1], [2]])
    parent = fem.MeshTri(p_parent, t_parent)

    p_child = np.array([
        [0.0, 1.0, 0.0, 0.5, 0.5, 0.0, 0.2],
        [0.0, 0.0, 1.0, 0.0, 0.5, 0.5, -0.1],
    ])
    t_child = np.array([
        [0, 3, 6],
        [3, 1, 4],
        [5, 4, 2],
        [5, 3, 4],
    ]).T
    child = fem.MeshTri(p_child, t_child)

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID


def test_topology_missing_region_in_child_mesh():
    """
    Adversarial Case 1.2:
    Child mesh misses a triangle (covers only part of parent area).
    Must fail area partition and domain identity.
    """
    parent = fem.MeshTri.init_symmetric()
    child_full = parent.refined()
    p_child = child_full.p.copy()
    t_child = child_full.t[:, :-1].copy()
    child = fem.MeshTri(p_child, t_child)

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "area" in reason.lower() or "ratio" in reason.lower()


def test_topology_duplicated_child_elements():
    """
    Adversarial Case 1.3:
    Child mesh has duplicate identical triangles.
    Must fail element uniqueness.
    """
    parent = fem.MeshTri.init_symmetric()
    child_full = parent.refined()
    p_child = child_full.p.copy()
    t_child = np.hstack([child_full.t, child_full.t[:, :1]])
    child = fem.MeshTri(p_child, t_child)

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "duplicate" in reason.lower()


def test_topology_overlapping_child_elements_with_correct_area():
    """
    Adversarial Case 1.4:
    Overlapping child elements where some elements overlap.
    """
    parent = fem.MeshTri.init_symmetric()
    child_full = parent.refined()
    p_child = child_full.p.copy()
    p_child[:, 8] = [0.45, 0.45]
    child = fem.MeshTri(p_child, child_full.t)

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID


def test_topology_inverted_degenerate_child_triangle():
    """
    Adversarial Case 1.5:
    Child triangle with zero area (collinear points).
    """
    p_child = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 0.0]])  # Collinear points -> area 0
    t_child = np.array([[0], [1], [2]])
    child = fem.MeshTri(p_child, t_child)

    parent = fem.MeshTri.init_symmetric()
    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "zero area" in reason.lower() or "degenerate" in reason.lower()


def test_topology_hanging_nodes_on_interior_edges():
    """
    Adversarial Case 1.6:
    Mesh with hanging nodes on shared interior edge.
    """
    p = np.array([
        [0.0, 1.0, 1.0, 0.0, 0.5],
        [0.0, 0.0, 1.0, 1.0, 0.5],
    ])
    t = np.array([
        [0, 1, 4],  # T0a
        [1, 2, 4],  # T0b
        [0, 2, 3],  # T1 (unrefined: edge 0-2 has hanging node 4!)
    ]).T
    child = fem.MeshTri(p, t)
    parent = fem.MeshTri.init_symmetric()

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "hanging node" in reason.lower() or "ratio" in reason.lower()


def test_topology_midpoint_not_matching_parent_edge():
    """
    Adversarial Case 1.7:
    Midpoint refinement where a child vertex claims to be midpoint but is perturbed.
    """
    parent = fem.MeshTri.init_symmetric()
    child = parent.refined()
    p_perturbed = child.p.copy()
    p_perturbed[0, 4] += 0.05
    child_bad = fem.MeshTri(p_perturbed, child.t)

    status, reason, details = validate_mesh_pair_topology(parent, child_bad, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "node inheritance" in reason.lower() or "midpoint" in reason.lower() or "ratio" in reason.lower() or "containment" in reason.lower()


def test_topology_child_element_not_assigned_to_parent():
    """
    Adversarial Case 1.8:
    Child element located outside parent bounding box completely.
    """
    parent = fem.MeshTri.init_symmetric()
    p_child = np.array([[2.0, 3.0, 2.0], [2.0, 2.0, 3.0]])
    t_child = np.array([[0], [1], [2]])
    child = fem.MeshTri(p_child, t_child)

    status, reason, details = validate_mesh_pair_topology(parent, child, "uniform_midpoint")
    assert status == MeshHierarchyStatus.INVALID
    assert "bounding box" in reason.lower() or "domain" in reason.lower() or "ratio" in reason.lower()


def test_topology_bisection_with_provenance_and_without_provenance():
    """
    Adversarial Case 1.9 & 1.10:
    Bisection refinement with provenance passes as NESTED_VERIFIED;
    without provenance is marked UNVERIFIED.
    """
    parent = fem.MeshTri.init_symmetric()
    child = parent.refined()

    # Bisection with topological proof dict
    bisect_meta = {"longest_edge_bisection": True, "edge_split_record": {"split_count": 8}}
    status, reason, details = validate_mesh_pair_topology(
        parent, child, "bisection", method_metadata=bisect_meta
    )
    assert status == MeshHierarchyStatus.NESTED_VERIFIED
    assert details["nestedness_proven"] is True

    # Bisection without provenance metadata
    status_unv, reason_unv, details_unv = validate_mesh_pair_topology(
        parent, child, "bisection", method_metadata=None
    )
    assert status_unv == MeshHierarchyStatus.UNVERIFIED
    assert "provenance" in details_unv["reason"]


def test_topology_conforming_non_nested_mesh_pair():
    """
    Adversarial Case 1.11:
    Independent conforming triangulations of the same domain.
    Classified as CONFORMING_NON_NESTED_VERIFIED.
    """
    m_coarse = fem.MeshTri.init_tensor(np.linspace(0, 1, 3), np.linspace(0, 1, 3))
    m_fine = fem.MeshTri.init_tensor(np.linspace(0, 1, 5), np.linspace(0, 1, 5))

    status, reason, details = validate_mesh_pair_topology(
        m_coarse, m_fine, "independent_conforming"
    )
    assert status == MeshHierarchyStatus.CONFORMING_NON_NESTED_VERIFIED
    assert details["nestedness_proven"] is False
    assert details["conforming_proven"] is True


def test_topology_fabricated_metadata_rejected():
    """
    Adversarial Case 1.12:
    validate_mesh_hierarchy rejects fabricated metadata without mesh objects or proof.
    """
    analyser = ProblemAnalyser()
    ev0 = MeshLevelEvidence("M0", "h0", 8, 9, 0.7)
    ev1 = MeshLevelEvidence(
        "M1", "h1", 32, 25, 0.35,
        parent_mesh_hash="h0",
        refinement_ratio=2.0,
        nestedness_verified=True,  # Fabricated
        topology_verified=True,    # Fabricated
    )
    ok, code, msg = analyser.validate_mesh_hierarchy([ev0, ev1])
    assert ok is False
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS


# ============================================================================
# Section 2: Mathematical BVP Adversarial Cases (AM32-02)
# ============================================================================

@pytest.fixture
def base_valid_bvp():
    """Returns a valid Tier 1 BVP configuration loaded from tier1_manifest.json."""
    manifest_path = Path("verification/phase_c/amendment_2/tier1_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest[0]  # T1_01 is fully mathematically validated


def test_bvp_missing_body_force(base_valid_bvp):
    """Adversarial Case 2.1: Missing body force in specification."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["bvp_specification"]["body_force"]["fx"] = ""
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status == BVPVerificationStatus.INVALID_SPECIFICATION
    assert record.equilibrium_verified is False


def test_bvp_corrupted_c33_violating_isotropy(base_valid_bvp):
    """Adversarial Case 2.2: c33 does not satisfy (c11 - c12) / 2."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["elasticity_tensor"]["c33"] = 1.2345e11
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status == BVPVerificationStatus.INVALID_SPECIFICATION
    assert record.isotropy_verified is False
    assert any("Isotropy condition violated" in d for d in record.discrepancies)


def test_bvp_non_symmetric_elasticity_tensor(base_valid_bvp):
    """Adversarial Case 2.3: Non-symmetric elasticity tensor (c12 != c21)."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["elasticity_tensor"]["c21"] = 9.99e10
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status == BVPVerificationStatus.INVALID_SPECIFICATION
    assert any("Tensor symmetry violated" in d for d in record.discrepancies)


def test_bvp_wrong_plane_stress_vs_plane_strain(base_valid_bvp):
    """Adversarial Case 2.4: Tensor values computed with plane-strain formula when plane-stress is claimed."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["elasticity_tensor"]["c11"] = 1.144439e11
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status == BVPVerificationStatus.INVALID_SPECIFICATION
    assert record.constitutive_verified is False


def test_bvp_boundary_data_mismatch(base_valid_bvp):
    """Adversarial Case 2.5: Incomplete Dirichlet boundaries."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["bvp_specification"]["boundary_conditions"]["dirichlet_boundaries"] = ["bottom", "top"]
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status in (BVPVerificationStatus.PARTIALLY_VERIFIED, BVPVerificationStatus.INVALID_SPECIFICATION)
    assert record.boundary_verified is False


def test_bvp_corner_trace_mismatch(base_valid_bvp):
    """Adversarial Case 2.6: Boundary prescription not exact displacement trace."""
    bvp = copy.deepcopy(base_valid_bvp)
    bvp["bvp_specification"]["boundary_conditions"]["prescription"] = "zero_traction"
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status in (BVPVerificationStatus.PARTIALLY_VERIFIED, BVPVerificationStatus.INVALID_SPECIFICATION)
    assert record.boundary_verified is False


def test_bvp_matching_qoi_but_invalid_differential_equation(base_valid_bvp):
    """
    Adversarial Case 2.7:
    QoI matches analytical value, but differential equation (body force) is invalid.
    Must NOT be FULL_BVP_VERIFIED (should be QOI_ONLY_VERIFIED).
    """
    bvp = copy.deepcopy(base_valid_bvp)
    # Body force set to zero, violating equilibrium -div sigma = f
    bvp["bvp_specification"]["body_force"]["fx"] = "0.0"
    bvp["bvp_specification"]["body_force"]["fy"] = "0.0"
    record = verify_tier1_bvp_manifest(bvp)
    assert record.status != BVPVerificationStatus.FULL_BVP_VERIFIED
    assert record.qoi_verified is True
    assert record.equilibrium_verified is False
    assert record.status == BVPVerificationStatus.QOI_ONLY_VERIFIED


# ============================================================================
# Section 3: Immutability Adversarial Cases (AM32-03)
# ============================================================================

def test_immutability_attribute_mutation_raises():
    """Adversarial Case 3.1: Mutating top-level attribute raises FrozenInstanceError."""
    ev = MeshLevelEvidence("M0", "h0", 8, 9, 0.7)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.element_count = 16


def test_immutability_nested_dictionary_mutation_raises():
    """Adversarial Case 3.2: Mutating nested dictionary in refinement_evidence raises TypeError."""
    ev = MeshLevelEvidence(
        "M1", "h1", 32, 25, 0.35,
        refinement_evidence={"nested": {"field": 123}},
    )
    with pytest.raises(TypeError):
        ev.refinement_evidence["nested"]["field"] = 999


def test_immutability_nested_list_mutation_raises():
    """Adversarial Case 3.3: Mutating nested list in refinement_evidence raises AttributeError."""
    ev = MeshLevelEvidence(
        "M1", "h1", 32, 25, 0.35,
        refinement_evidence={"elements": [1, 2, 3]},
    )
    # Stored as tuple
    with pytest.raises(AttributeError):
        ev.refinement_evidence["elements"].append(4)


def test_immutability_caller_retained_reference_mutation_has_no_effect():
    """Adversarial Case 3.4: Mutating caller's dict after construction leaves evidence unchanged."""
    source_dict = {"mutable_key": "original_val", "inner_dict": {"x": 10}}
    ev = MeshLevelEvidence("M1", "h1", 32, 25, 0.35, refinement_evidence=source_dict)

    source_dict["mutable_key"] = "tampered_val"
    source_dict["inner_dict"]["x"] = 999

    assert ev.refinement_evidence["mutable_key"] == "original_val"
    assert ev.refinement_evidence["inner_dict"]["x"] == 10


def test_immutability_canonical_serialization_roundtrip_and_hash():
    """
    Adversarial Case 3.5, 3.6, 3.7:
    Canonical serialization round-trip: dict -> hash -> dict.
    Determinism across runs: identical byte sequence and hash stability.
    """
    ev1 = MeshLevelEvidence(
        level_id="M1",
        mesh_hash="sha1",
        element_count=32,
        node_count=25,
        characteristic_h=0.35,
        parent_mesh_hash="sha0",
        refinement_ratio=2.0,
        refinement_method="uniform_midpoint",
        nestedness_verified=True,
        topology_verified=True,
        refinement_evidence={"key_b": 2, "key_a": [1, 2, 3]},
    )

    ev2 = MeshLevelEvidence(
        level_id="M1",
        mesh_hash="sha1",
        element_count=32,
        node_count=25,
        characteristic_h=0.35,
        parent_mesh_hash="sha0",
        refinement_ratio=2.0,
        refinement_method="uniform_midpoint",
        nestedness_verified=True,
        topology_verified=True,
        refinement_evidence={"key_a": [1, 2, 3], "key_b": 2},  # Reordered keys
    )

    assert ev1.canonical_hash() == ev2.canonical_hash()

    c_dict = ev1.to_canonical_dict()
    ev_reconstructed = MeshLevelEvidence.from_canonical_dict(c_dict)
    assert ev_reconstructed.canonical_hash() == ev1.canonical_hash()
    assert ev_reconstructed.refinement_evidence["key_b"] == 2


# ============================================================================
# Section 4: Quadrature Consistency Adversarial Cases (AM32-04)
# ============================================================================

def test_quadrature_non_geometric_error_reduction():
    """Adversarial Case 4.1: Non-geometric error reduction classified as NON_GEOMETRIC_CONVERGENCE."""
    res = assess_quadrature_convergence(
        j14=1.0,
        j18=1.01,
        j22=1.03,
        j26=1.06,
        e_smallest_spatial=1e-4,
    )
    assert res["passes_verification"] is False
    assert res["status"] == QuadratureConvergenceStatus.NON_GEOMETRIC_CONVERGENCE.value


def test_quadrature_unjustified_zero_difference_rejected():
    """Adversarial Case 4.2: Zero differences with large prior difference rejected."""
    res = assess_quadrature_convergence(
        j14=10.0,
        j18=5.0,  # delta_14_18 = 5.0
        j22=5.0,  # delta_18_22 = 0.0
        j26=5.0,  # delta_22_26 = 0.0
        e_smallest_spatial=1e-4,
    )
    assert res["passes_verification"] is False
    assert res["status"] == QuadratureConvergenceStatus.INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.value


def test_quadrature_machine_precision_zero_difference_passed():
    """Adversarial Case 4.3: Valid zero difference at machine precision floor passed."""
    res = assess_quadrature_convergence(
        j14=1.0 + 1e-13,
        j18=1.0,
        j22=1.0,
        j26=1.0,
        e_smallest_spatial=1e-4,
    )
    assert res["passes_verification"] is True
    assert res["status"] == QuadratureConvergenceStatus.PASSED_MACHINE_PRECISION.value


def test_quadrature_json_report_consistency():
    """
    Adversarial Case 4.4:
    Direct validator checking that values in results JSON match exact expected Case B constants.
    """
    json_path = Path("results/phase_c_amendment_3_2/quadrature_study_results.json")
    assert json_path.exists(), "quadrature_study_results.json must exist"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    exact_qoi = data["exact_qoi"]
    m3_spatial_error = data["m3_reference"]["e_smallest_m3"]
    tail_ratio = data["mesh_levels"]["M3"]["convergence_assessment"]["ratio_to_spatial_error"] * 100.0

    # Verify against exact mathematical reference
    assert abs(exact_qoi - 0.2838096843988563) < 1e-12
    assert abs(m3_spatial_error - 5.279145e-5) < 1e-8
    assert tail_ratio <= 1.0  # Must be <= 1% of spatial error
    assert data["mesh_levels"]["M3"]["convergence_assessment"]["nature_of_estimate"] == "EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE"
