"""
Phase C Amendment 3.2 — Reproduction and Remediation Verification Tests for Audit Defects AM32-01 to AM32-04.

This test module verifies the reproduction of the 4 major audit findings identified in the
Phase C Amendment 3.1 review and verifies that Amendment 3.2 remediates each defect:
- Defect 1 (AM32-01): Mesh topology false positives (fabricated metadata rejection).
- Defect 2 (AM32-02): Mathematical BVP audit false positives (manifest c33, body force, boundary audit).
- Defect 3 (AM32-03): Shallow immutability allowing post-construction mutation of nested evidence dictionaries.
- Defect 4 (AM32-04): Unjustified zero-difference quadrature convergence.
"""

import copy
import dataclasses
import json
from pathlib import Path
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
# Reproduction 1 (AM32-01): Fabricated Metadata Rejection
# ============================================================================
def test_reproduce_am32_01_metadata_trust_rejected_in_amendment_3_2():
    """
    AM32-01 Verification:
    In Amendment 3.1, validate_mesh_hierarchy() accepted fabricated metadata without mesh proof.
    In Amendment 3.2, validate_mesh_hierarchy() strictly rejects unvalidated claims when
    meshes are omitted and refinement_evidence lacks topological proof.
    """
    analyser = ProblemAnalyser()
    ev0 = MeshLevelEvidence("M0", "hash0", 8, 9, 0.7)
    ev1 = MeshLevelEvidence(
        "M1",
        "hash1",
        32,
        25,
        0.35,
        parent_mesh_hash="hash0",
        refinement_ratio=2.0,
        refinement_method="uniform_midpoint",
        nestedness_verified=True,  # Fabricated flag
        topology_verified=True,    # Fabricated flag
        refinement_evidence={"fabricated": True},  # Missing true topological proof
    )
    ev2 = MeshLevelEvidence(
        "M2",
        "hash2",
        128,
        81,
        0.175,
        parent_mesh_hash="hash1",
        refinement_ratio=2.0,
        refinement_method="uniform_midpoint",
        nestedness_verified=True,  # Fabricated flag
        topology_verified=True,    # Fabricated flag
        refinement_evidence={"fabricated": True},  # Missing true topological proof
    )

    # In Amendment 3.2, this must be rejected with RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    ok, code, msg = analyser.validate_mesh_hierarchy([ev0, ev1, ev2])
    assert ok is False, "Amendment 3.2 must reject fabricated mesh metadata without proof"
    assert code == RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS
    assert "lacks independent topological verification evidence" in msg


# ============================================================================
# Reproduction 2 (AM32-02): Manifest BVP Field Audit
# ============================================================================
def test_reproduce_am32_02_bvp_verification_rejects_corrupted_manifest_fields():
    """
    AM32-02 Verification:
    In Amendment 3.1, verify_bvp_single() bypassed the actual manifest c33 and body force.
    In Amendment 3.2, verify_tier1_bvp_manifest() audits manifest c33 against isotropy
    and compares derived body forces against manifest body forces.
    """
    corrupted_bvp = {
        "config_id": "T1_CORRUPTED",
        "family": "family_1_polynomial",
        "family_index": 1,
        "item_index": 0,
        "bvp_specification": {
            "displacement_field": {"ux": "0.001*x^2", "uy": "0.001*x*y"},
            "body_force": {
                "fx": "0.0",  # Inconsistent with displacement field
                "fy": "0.0",
            },
            "boundary_conditions": {
                "dirichlet_boundaries": ["b", "t", "l", "r"],
                "prescription": "exact_displacement_trace",
            },
        },
        "parameters": {"a": 0.001, "b": -0.0004},
        "material": {"E": 1e11, "nu": 0.22},
        "constitutive_assumption": "plane_stress",
        "elasticity_tensor": {
            "c11": 1.05086e11,
            "c12": 2.31189e10,
            "c33": 999999.0,  # Corrupted c33: violates isotropy C11 - C12 - 2*C33 != 0!
        },
        "qoi": {
            "type": "boundary_average_displacement",
            "component": "y",
            "exact_analytical_value": 0.0005,
        },
    }

    record = verify_tier1_bvp_manifest(corrupted_bvp)
    assert record.status == BVPVerificationStatus.INVALID_SPECIFICATION
    assert record.isotropy_verified is False
    assert len(record.discrepancies) >= 1


# ============================================================================
# Reproduction 3 (AM32-03): Mutation Prevention on Nested Evidence
# ============================================================================
def test_reproduce_am32_03_deep_immutability_enforced():
    """
    AM32-03 Verification:
    In Amendment 3.1, refinement_evidence could be mutated post-construction.
    In Amendment 3.2, MeshLevelEvidence defensively freezes all nested dictionaries
    and lists via MappingProxyType and tuple. Post-construction mutation raises TypeError.
    """
    evidence_dict = {"nestedness_proven": False, "method": "uniform_midpoint"}
    ev = MeshLevelEvidence(
        level_id="M1",
        mesh_hash="h1",
        element_count=32,
        node_count=25,
        characteristic_h=0.35,
        refinement_evidence=evidence_dict,
    )

    # In Amendment 3.2, in-place modification must raise TypeError
    with pytest.raises(TypeError):
        ev.refinement_evidence["nestedness_proven"] = True

    # Mutating caller reference after construction must not affect the instance
    evidence_dict["nestedness_proven"] = True
    assert ev.refinement_evidence["nestedness_proven"] is False


# ============================================================================
# Reproduction 4 (AM32-04): Rejection of Unjustified Zero Differences
# ============================================================================
def test_reproduce_am32_04_zero_difference_rejected_without_precision_floor():
    """
    AM32-04 Verification:
    In Amendment 3.1, assess_quadrature_convergence() accepted delta_18_22 == 0 and
    delta_22_26 == 0 even if delta_14_18 was large.
    In Amendment 3.2, this is flagged as INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.
    """
    res = assess_quadrature_convergence(
        j14=2.0,
        j18=1.0,  # delta_14_18 = 1.0 > 1e-12
        j22=1.0,  # delta_18_22 = 0.0
        j26=1.0,  # delta_22_26 = 0.0
        e_smallest_spatial=1e-4,
    )
    assert res["passes_verification"] is False
    assert res["status"] == QuadratureConvergenceStatus.INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.value
