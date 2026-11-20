"""
GDEC Problem Analyser and Numerical Verification Contract Engine.
Implements:
1. Problem analysis, geometry inspection, and QoI suitability validation.
2. Deterministic refusal mechanics for ill-posed or unsupported engineering requests.
3. Nested uniform refinement (r = 2) spatial discretisation uncertainty estimation (GCI).
4. Four-grid observed order stability validation (M0, M1, M2, M3) with strict mode enforcement.
5. Structured accuracy contract output schema conforming to Phase C specifications.
"""

from dataclasses import dataclass, field
from enum import Enum
import copy
import hashlib
import json
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import skfem as fem


class MeshHierarchyStatus(str, Enum):
    """Refinement method classification and topological verification status (AM32-01)."""
    NESTED_VERIFIED = "NESTED_VERIFIED"
    CONFORMING_NON_NESTED_VERIFIED = "CONFORMING_NON_NESTED_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


def _deep_freeze(obj: Any) -> Any:
    """Recursively converts mutable collections (dict, list, set, ndarray) into immutable equivalents."""
    if obj is None:
        return None
    if isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, (dict, MappingProxyType)):
        frozen_dict = {str(k): _deep_freeze(v) for k, v in obj.items()}
        return MappingProxyType(frozen_dict)
    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return frozenset(_deep_freeze(v) for v in obj)
    if isinstance(obj, np.ndarray):
        arr_copy = obj.copy()
        arr_copy.flags.writeable = False
        return arr_copy
    return obj


def _to_json_serializable(obj: Any) -> Any:
    """Recursively converts mappingproxy, tuples, sets back to standard dicts and lists for JSON serialization."""
    if obj is None:
        return None
    if isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, (dict, MappingProxyType)):
        return {str(k): _to_json_serializable(v) for k, v in sorted(obj.items(), key=lambda it: str(it[0]))}
    if isinstance(obj, (list, tuple)):
        return [_to_json_serializable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted([_to_json_serializable(v) for v in obj], key=str)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


class RefusalCode(str, Enum):
    ILL_POSED_QOI = "ill_posed_qoi"
    UNSUPPORTED_QOI = "unsupported_qoi"
    INVALID_GEOMETRY = "invalid_geometry"
    MESH_QUALITY_FAILURE = "mesh_quality_failure"
    SOLVER_NOT_CONVERGED = "solver_not_converged"
    UNVERIFIED_INSUFFICIENT_LEVELS = "unverified_insufficient_levels"
    UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR = "unverified_difference_below_numerical_floor"
    UNVERIFIED_ORDER = "unverified_order"
    UNVERIFIED_NON_ASYMPTOTIC = "unverified_non_asymptotic"
    REFERENCE_UNCERTAIN = "reference_uncertain"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass
class AccuracyTarget:
    target_type: str  # "relative" or "absolute"
    tolerance: float  # e.g. 0.01 (1.0%)
    qoi_scale: Optional[float] = None  # Scale S_J for relative comparison

    def __post_init__(self) -> None:
        if self.target_type not in ["relative", "absolute"]:
            raise ValueError(
                f"Invalid target_type '{self.target_type}'; must be 'relative' or 'absolute'."
            )
        if not np.isfinite(self.tolerance) or self.tolerance <= 0.0:
            raise ValueError(
                f"Tolerance must be a positive finite float (got {self.tolerance})."
            )
        if self.target_type == "relative":
            if self.qoi_scale is None or self.qoi_scale <= 0.0 or not np.isfinite(self.qoi_scale):
                raise ValueError(
                    f"Explicit positive finite qoi_scale is strictly required for relative accuracy targets (got {self.qoi_scale})."
                )
        elif self.target_type == "absolute":
            if self.qoi_scale is not None and (self.qoi_scale <= 0.0 or not np.isfinite(self.qoi_scale)):
                raise ValueError(
                    f"qoi_scale must be positive and finite if provided for absolute target (got {self.qoi_scale})."
                )


@dataclass(frozen=True)
class MeshLevelEvidence:
    """
    Typed, deeply immutable evidence representation for a single mesh level in a verification hierarchy.
    Captures verifiable topological, geometric, and provenance data.
    Enforces deep immutability via frozen=True and recursive MappingProxyType freezing (AM32-03).
    """
    level_id: str
    mesh_hash: str
    element_count: int
    node_count: int
    characteristic_h: float  # Maximum element diameter h_max = max_{K} diam(K) (AM31-02, AM32-05)
    characteristic_h_avg: Optional[float] = None  # Separate diagnostic area-average size
    parent_mesh_hash: Optional[str] = None
    refinement_ratio: Optional[float] = None
    nestedness_verified: bool = False  # NEVER True by default without proof (AM31-01, AM32-01)
    topology_verified: bool = False  # True only if genuine topological check executed
    refinement_method: str = "uniform_midpoint"
    provenance: Optional[Any] = None
    refinement_evidence: Optional[Any] = None

    def __post_init__(self):
        # Defensive deep copy and recursive deep freezing to prevent caller-side or post-hoc mutation (AM32-03)
        prov = _deep_freeze(copy.deepcopy(self.provenance)) if self.provenance is not None else None
        ref = _deep_freeze(copy.deepcopy(self.refinement_evidence)) if self.refinement_evidence is not None else None
        object.__setattr__(self, "provenance", prov)
        object.__setattr__(self, "refinement_evidence", ref)

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Deterministic canonical representation with recursively sorted keys and normalized primitives."""
        return {
            "characteristic_h": float(self.characteristic_h),
            "characteristic_h_avg": float(self.characteristic_h_avg) if self.characteristic_h_avg is not None else None,
            "element_count": int(self.element_count),
            "level_id": str(self.level_id),
            "mesh_hash": str(self.mesh_hash),
            "nestedness_verified": bool(self.nestedness_verified),
            "node_count": int(self.node_count),
            "parent_mesh_hash": str(self.parent_mesh_hash) if self.parent_mesh_hash is not None else None,
            "provenance": _to_json_serializable(self.provenance),
            "refinement_evidence": _to_json_serializable(self.refinement_evidence),
            "refinement_method": str(self.refinement_method),
            "refinement_ratio": float(self.refinement_ratio) if self.refinement_ratio is not None else None,
            "topology_verified": bool(self.topology_verified),
        }

    def canonical_hash(self) -> str:
        """Computes a deterministic SHA-256 hash of the canonical evidence representation."""
        data_str = json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return self.to_canonical_dict()

    @classmethod
    def from_canonical_dict(cls, d: Dict[str, Any]) -> "MeshLevelEvidence":
        """Reconstructs a deeply immutable MeshLevelEvidence instance from canonical dictionary."""
        return cls(
            level_id=str(d["level_id"]),
            mesh_hash=str(d["mesh_hash"]),
            element_count=int(d["element_count"]),
            node_count=int(d["node_count"]),
            characteristic_h=float(d["characteristic_h"]),
            characteristic_h_avg=float(d["characteristic_h_avg"]) if d.get("characteristic_h_avg") is not None else None,
            parent_mesh_hash=str(d["parent_mesh_hash"]) if d.get("parent_mesh_hash") is not None else None,
            refinement_ratio=float(d["refinement_ratio"]) if d.get("refinement_ratio") is not None else None,
            nestedness_verified=bool(d.get("nestedness_verified", False)),
            topology_verified=bool(d.get("topology_verified", False)),
            refinement_method=str(d.get("refinement_method", "uniform_midpoint")),
            provenance=d.get("provenance"),
            refinement_evidence=d.get("refinement_evidence"),
        )


@dataclass
class ContractResult:
    issued: bool
    status: str
    qoi: Dict[str, Any]
    uncertainty: Optional[Dict[str, Any]] = None
    accuracy: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    refusal: Optional[Dict[str, Any]] = None
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "issued": self.issued,
            "status": self.status,
            "qoi": self.qoi,
            "limitations": self.limitations,
        }
        if self.uncertainty is not None:
            res["uncertainty"] = self.uncertainty
        if self.accuracy is not None:
            res["accuracy"] = self.accuracy
        if self.verification is not None:
            res["verification"] = self.verification
        if self.refusal is not None:
            res["refusal"] = self.refusal
        return res


class ProblemAnalyser:
    """
    Intelligent Engineering Problem Analyser and Accuracy Contract Evaluator.
    Diagnoses suitability and verifies spatial discretisation accuracy without heuristics.
    """

    def __init__(
        self,
        safety_factor_Fs: float = 1.25,
        order_cap_p_cap: float = 2.0,
        order_window: Tuple[float, float] = (0.5, 3.5),
        numerical_floor: float = 1e-13,
        min_angle_threshold_deg: float = 10.0,
        solver_residual_tol: float = 1e-10,
        reference_uncertainty_gate: float = 0.0005,
    ):
        self.Fs = safety_factor_Fs
        self.p_cap = order_cap_p_cap
        self.order_window = order_window
        self.numerical_floor = numerical_floor
        self.min_angle_threshold_deg = min_angle_threshold_deg
        self.solver_residual_tol = solver_residual_tol
        self.reference_uncertainty_gate = reference_uncertainty_gate

    def check_mesh_quality(self, mesh: fem.MeshTri) -> Tuple[bool, float]:
        """
        Calculates the minimum interior angle across all triangles in the mesh.
        Strictly detects degenerate/zero-area elements before law-of-cosines evaluation.
        Returns (is_valid, min_angle_degrees).
        """
        p = mesh.p
        t = mesh.t
        v0 = p[:, t[0]]
        v1 = p[:, t[1]]
        v2 = p[:, t[2]]

        # Area check: det( [v1-v0, v2-v0] )
        det = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
        areas = 0.5 * np.abs(det)
        total_area = float(np.sum(areas))
        if total_area <= 0.0 or not np.isfinite(total_area):
            return False, 0.0

        # Relative dimensionless area check to prevent scale dependence
        if np.any(areas / total_area <= 1e-14):
            return False, 0.0

        # Scale-aware characteristic length L_ref
        L_ref = float(np.sqrt(total_area))
        if L_ref <= 0.0 or not np.isfinite(L_ref):
            return False, 0.0

        # Edge lengths (dimensionless against L_ref)
        a = np.linalg.norm(v1 - v2, axis=0)
        b = np.linalg.norm(v2 - v0, axis=0)
        c = np.linalg.norm(v0 - v1, axis=0)

        if np.any(a / L_ref <= 1e-14) or np.any(b / L_ref <= 1e-14) or np.any(c / L_ref <= 1e-14):
            return False, 0.0

        # Law of cosines for all three interior angles
        cos_alpha = np.clip((b**2 + c**2 - a**2) / (2.0 * b * c), -1.0, 1.0)
        cos_beta = np.clip((a**2 + c**2 - b**2) / (2.0 * a * c), -1.0, 1.0)
        cos_gamma = np.clip((a**2 + b**2 - c**2) / (2.0 * a * b), -1.0, 1.0)

        min_angles_rad = np.minimum(
            np.arccos(cos_alpha), np.minimum(np.arccos(cos_beta), np.arccos(cos_gamma))
        )
        min_angle_deg = float(np.min(np.degrees(min_angles_rad)))

        is_valid = bool(min_angle_deg >= self.min_angle_threshold_deg)
        return is_valid, min_angle_deg

    def validate_geometry(
        self, geometry: Any
    ) -> Tuple[bool, Optional[RefusalCode], str]:
        """
        Validates geometry definition and coordinates before meshing or execution.
        Distinguishes invalid geometry from poor-quality but geometrically valid meshes.
        """
        if isinstance(geometry, fem.MeshTri):
            if not np.all(np.isfinite(geometry.p)):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Geometry coordinates contain NaN or Inf values.",
                )
            if geometry.t.shape[0] != 3 or geometry.t.shape[1] == 0:
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh has invalid or empty element topology.",
                )
            if np.any(geometry.t < 0) or np.max(geometry.t) >= geometry.p.shape[1]:
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh topology references out-of-bounds vertex index.",
                )

            # Jacobian determinant / inverted element check
            p = geometry.p
            t = geometry.t
            v0 = p[:, t[0]]
            v1 = p[:, t[1]]
            v2 = p[:, t[2]]
            det = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
            if np.any(det < 0.0):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh contains inverted elements with negative Jacobian determinant.",
                )
            areas = 0.5 * np.abs(det)
            total_area = float(np.sum(areas))
            if total_area <= 0.0 or not np.isfinite(total_area) or np.any(areas / total_area <= 1e-14):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh contains degenerate zero-area elements.",
                )

            valid_angle, min_angle = self.check_mesh_quality(geometry)
            if not valid_angle:
                return (
                    False,
                    RefusalCode.MESH_QUALITY_FAILURE,
                    f"Mesh minimum angle ({min_angle:.1f} deg) violates threshold ({self.min_angle_threshold_deg:.1f} deg).",
                )
            return True, None, "Valid geometry and mesh quality."

        if isinstance(geometry, dict):
            if geometry.get("has_nan", False) or geometry.get("has_inf", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Geometry coordinates contain non-finite values (NaN or Inf).",
                )
            if geometry.get("zero_area", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Geometry definition produces degenerate zero-area domain.",
                )
            if geometry.get("inverted", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Element orientation is inverted (negative Jacobian determinant).",
                )
            if geometry.get("invalid_topology", False) or geometry.get("empty_topology", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh element topology table is invalid or empty.",
                )
            if geometry.get("self_intersecting", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Outer boundary polygon is self-intersecting.",
                )
            if geometry.get("disconnected_nodes", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Mesh contains unreferenced floating disconnected vertices.",
                )
            if geometry.get("degenerate_1d", False):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    "Domain has zero thickness (degenerate 1D line element in 2D space).",
                )
            if not geometry.get("valid", True):
                return (
                    False,
                    RefusalCode.INVALID_GEOMETRY,
                    geometry.get("reason", "Invalid geometric specification."),
                )
            return True, None, "Valid geometry."

        if isinstance(geometry, bool):
            if not geometry:
                return False, RefusalCode.INVALID_GEOMETRY, "Invalid geometric domain specification."
            return True, None, "Valid geometry."

        if geometry is None:
            return True, None, "Valid geometry (unspecified default)."

        return (
            False,
            RefusalCode.INVALID_GEOMETRY,
            f"Unsupported geometry specification type: {type(geometry).__name__}.",
        )

    def validate_sequence(
        self, levels: List[float], refinement_ratios: Optional[List[float]] = None
    ) -> Tuple[bool, Optional[RefusalCode], str]:
        """
        Validates whether sufficient mesh levels are provided and refinement ratios match r = 2.
        """
        if len(levels) < 3:
            return (
                False,
                RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                f"Grid sequence has {len(levels)} levels; at least 3 nested grid levels required for verification.",
            )
        if refinement_ratios is not None:
            for r in refinement_ratios:
                if not np.isclose(r, 2.0, atol=1e-3):
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Refinement ratio r={r:.2f} does not match required uniform doubling r=2.0.",
                    )
        return True, None, "Sufficient grid levels and valid refinement ratio available."

    def validate_mesh_hierarchy(
        self,
        evidence_list: List[MeshLevelEvidence],
        verification_mode: str = "three_grid",
        meshes: Optional[List[fem.MeshTri]] = None,
    ) -> Tuple[bool, Optional[RefusalCode], str]:
        """
        Validates typed mesh hierarchy evidence against verified parent-child links,
        monotonic characteristic h_max, actual refinement ratios, and protocol level counts (AM31-01, AM31-02).
        Rejects unproven assertions where nestedness is merely claimed without proof.
        Fail-closed on missing, corrupted, or contradictory evidence.
        """
        if verification_mode not in ("three_grid", "four_grid"):
            raise ValueError(
                f"Invalid verification mode: '{verification_mode}'. Supported modes are 'three_grid' and 'four_grid'."
            )

        min_levels = 4 if verification_mode == "four_grid" else 3
        if len(evidence_list) < min_levels:
            return (
                False,
                RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                f"Mesh hierarchy contains {len(evidence_list)} levels; at least {min_levels} required for mode '{verification_mode}'.",
            )

        # If actual meshes are supplied, verify them directly
        if meshes is not None:
            if len(meshes) != len(evidence_list):
                return (
                    False,
                    RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                    f"Supplied mesh count ({len(meshes)}) does not match evidence level count ({len(evidence_list)}).",
                )
            from gdec.runtime.mesh_evidence import verify_mesh_refinement_topology, compute_mesh_hash

            for i in range(1, len(meshes)):
                m_hash = compute_mesh_hash(meshes[i])
                if m_hash != evidence_list[i].mesh_hash:
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Mesh level '{evidence_list[i].level_id}' hash mismatch with supplied mesh.",
                    )
                ok_top, msg_top, _ = verify_mesh_refinement_topology(
                    meshes[i - 1], meshes[i], refinement_method=evidence_list[i].refinement_method
                )
                if not ok_top:
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Topological verification failed between level '{evidence_list[i-1].level_id}' and '{evidence_list[i].level_id}': {msg_top}",
                    )

        seen_hashes = set()
        for i, ev in enumerate(evidence_list):
            # Check finite metrics
            if (
                not np.isfinite(ev.characteristic_h)
                or ev.characteristic_h <= 0.0
                or ev.element_count <= 0
                or ev.node_count <= 0
            ):
                return (
                    False,
                    RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                    f"Mesh level '{ev.level_id}' has non-finite or invalid element/node metrics (h={ev.characteristic_h}, Ne={ev.element_count}, Nn={ev.node_count}).",
                )

            # Check duplicate levels
            if ev.mesh_hash in seen_hashes:
                return (
                    False,
                    RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                    f"Mesh level '{ev.level_id}' has duplicate mesh hash ({ev.mesh_hash[:8]}...); duplicate levels are forbidden.",
                )
            seen_hashes.add(ev.mesh_hash)

            if i > 0:
                prev = evidence_list[i - 1]
                # Check parent hash pointer
                if ev.parent_mesh_hash is None or ev.parent_mesh_hash != prev.mesh_hash:
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Mesh level '{ev.level_id}' parent hash ({str(ev.parent_mesh_hash)[:8]}...) does not match previous level '{prev.level_id}' hash ({prev.mesh_hash[:8]}...).",
                    )

                # Check strict monotonic decrease in characteristic h (h_max)
                if ev.characteristic_h >= prev.characteristic_h:
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Characteristic h is not strictly decreasing from '{prev.level_id}' ({prev.characteristic_h:.4e}) to '{ev.level_id}' ({ev.characteristic_h:.4e}).",
                    )

                # Independently calculated refinement ratio from characteristic h
                calc_ratio = prev.characteristic_h / ev.characteristic_h

                # Check claimed refinement ratio against actual evidence
                if ev.refinement_ratio is not None:
                    if not np.isclose(ev.refinement_ratio, calc_ratio, rtol=0.05):
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Level '{ev.level_id}' claimed refinement ratio ({ev.refinement_ratio:.2f}) contradicts independently calculated ratio ({calc_ratio:.2f}).",
                        )

                # Check refinement method support and genuine topological proof (AM31-01, AM32-01)
                ref_ev = ev.refinement_evidence
                if ev.refinement_method == "uniform_midpoint":
                    # Must have actual topological proof recorded with verified connectivity, not just unverified claimed Boolean
                    required_uniform_keys: Tuple[str, ...] = (
                        "subdivision_pattern_verified",
                        "element_mapping_verified",
                        "conforming_connectivity_verified",
                        "all_parent_nodes_inherited",
                        "edge_midpoint_provenance_verified",
                        "nestedness_proven",
                    )
                    valid_proof = (
                        ev.topology_verified
                        and ev.nestedness_verified
                        and ref_ev is not None
                        and all(ref_ev.get(k) is True for k in required_uniform_keys)
                        and ref_ev.get("parent_elements_covered") == prev.element_count
                        and ref_ev.get("child_elements_mapped") == ev.element_count
                        and ref_ev.get("topology_verification_hash") is not None
                    )
                    if not valid_proof:
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Mesh level '{ev.level_id}' lacks independent topological verification evidence under refinement method '{ev.refinement_method}'.",
                        )
                elif ev.refinement_method == "bisection":
                    required_bisection_keys: Tuple[str, ...] = (
                        "bisection_provenance_verified",
                        "element_mapping_verified",
                        "nestedness_proven",
                    )
                    valid_proof = (
                        ev.topology_verified
                        and ev.nestedness_verified
                        and ref_ev is not None
                        and all(ref_ev.get(k) is True for k in required_bisection_keys)
                        and ref_ev.get("topology_verification_hash") is not None
                    )
                    if not valid_proof:
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Mesh level '{ev.level_id}' lacks complete bisection provenance verification.",
                        )
                elif ev.refinement_method == "independent_conforming":
                    required_conforming_keys: Tuple[str, ...] = (
                        "conforming_hierarchy_verified",
                        "domain_equivalence_verified",
                    )
                    valid_proof = (
                        ev.topology_verified
                        and ref_ev is not None
                        and all(ref_ev.get(k) is True for k in required_conforming_keys)
                        and ref_ev.get("nestedness_proven") is False
                        and ref_ev.get("topology_verification_hash") is not None
                    )
                    if not valid_proof:
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Mesh level '{ev.level_id}' lacks hierarchy verification under non-nested method '{ev.refinement_method}'.",
                        )
                    if ev.nestedness_verified:
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Non-nested conforming mesh level '{ev.level_id}' cannot claim nestedness_verified=True.",
                        )
                else:
                    # Unknown/unsupported refinement method fails closed
                    return (
                        False,
                        RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                        f"Unsupported or unverified refinement method '{ev.refinement_method}' on level '{ev.level_id}'.",
                    )

                # Ratio tolerance check depending on refinement method
                if ev.refinement_method == "uniform_midpoint":
                    if not np.isclose(calc_ratio, 2.0, rtol=0.10):
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Independently calculated refinement ratio h_{prev.level_id}/h_{ev.level_id} = {calc_ratio:.2f} deviates from required uniform doubling r=2.0.",
                        )
                elif ev.refinement_method == "bisection":
                    if not np.isclose(calc_ratio, np.sqrt(2.0), rtol=0.15):
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Independently calculated refinement ratio h_{prev.level_id}/h_{ev.level_id} = {calc_ratio:.2f} deviates from bisection ratio sqrt(2).",
                        )
                elif ev.refinement_method == "independent_conforming":
                    if calc_ratio <= 1.0:
                        return (
                            False,
                            RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS,
                            f"Non-nested refinement ratio h_{prev.level_id}/h_{ev.level_id} = {calc_ratio:.2f} must be strictly > 1.0.",
                        )

        return (
            True,
            None,
            f"Mesh hierarchy ({len(evidence_list)} levels) verified for mode '{verification_mode}'.",
        )

    def check_qoi_support(
        self, qoi_spec: Dict[str, Any]
    ) -> Tuple[bool, Optional[RefusalCode], str]:
        """
        Validates whether the requested QoI is mathematically supported in the current H^1 setting.
        Strictly refuses point stresses, point displacements, and stress functionals.
        """
        qtype = qoi_spec.get("type", "").lower()
        location = qoi_spec.get("location")
        is_singular_point = bool(qoi_spec.get("is_singular_point", False))

        if qtype == "point_stress":
            if is_singular_point or (
                location is not None and np.allclose(location, [0.0, 0.0])
            ):
                return (
                    False,
                    RefusalCode.ILL_POSED_QOI,
                    "Point stress at re-entrant corner or notch singularity is mathematically divergent in H^1 elasticity.",
                )
            return (
                False,
                RefusalCode.UNSUPPORTED_QOI,
                "Point stress evaluation is currently unsupported. Use a regularized patch average displacement functional.",
            )

        if qtype == "point_displacement":
            return (
                False,
                RefusalCode.UNSUPPORTED_QOI,
                "Unregularized point displacement is unsupported in 2D H^1 setting. Use a boundary or patch average.",
            )

        if qtype in [
            "boundary_average_displacement",
            "patch_average_displacement",
            "boundary_average",
            "patch_average",
        ]:
            return True, None, "Supported displacement functional."

        if qtype in [
            "patch_average_stress",
            "patch_stress",
            "maximum_boundary_stress",
            "sif_k1",
            "j_integral_unregularized",
            "point_strain",
        ]:
            return (
                False,
                RefusalCode.UNSUPPORTED_QOI,
                f"Functional type '{qtype}' is currently unsupported in H^1 setting. Only displacement functionals are supported.",
            )

        return (
            False,
            RefusalCode.UNSUPPORTED_QOI,
            f"Functional type '{qtype}' is not supported by GDEC.",
        )

    def evaluate_contract(
        self,
        J0: float,
        J1: float,
        J2: float,
        target: Optional[AccuracyTarget] = None,
        J3: Optional[float] = None,
        mesh_min_angle_deg: Optional[float] = None,
        solver_relative_residual: Optional[float] = None,
        qoi_spec: Optional[Dict[str, Any]] = None,
        budget_exhausted: bool = False,
        verification_mode: str = "three_grid",
        require_m3_stability: bool = False,
        geometry: Any = True,
        geometry_valid: Optional[bool] = None,
        mesh_levels: Optional[int] = None,
        refinement_ratio: Optional[float] = None,
        reference_uncertainty: Optional[float] = None,
        mesh_hierarchy: Optional[List[MeshLevelEvidence]] = None,
        meshes: Optional[List[fem.MeshTri]] = None,
    ) -> ContractResult:
        """
        Evaluates the verification contract for computed QoIs on nested levels.
        Enforces deterministic refusal priority (Priority 1 through 10).
        """
        # Validate explicit verification mode
        if verification_mode not in ("three_grid", "four_grid"):
            raise ValueError(
                f"Invalid verification mode: '{verification_mode}'. Supported modes are 'three_grid' and 'four_grid'."
            )

        # Validate finite QoI inputs
        for val, name in [(J0, "J0"), (J1, "J1"), (J2, "J2")]:
            if not np.isfinite(val):
                raise ValueError(f"QoI value {name} must be finite (got {val}).")
        if J3 is not None and not np.isfinite(J3):
            raise ValueError(f"QoI value J3 must be finite (got {J3}).")

        # Validate solver residual parameter if provided
        if solver_relative_residual is not None:
            if not np.isfinite(solver_relative_residual) or solver_relative_residual < 0.0:
                raise ValueError(
                    f"solver_relative_residual must be a non-negative finite float (got {solver_relative_residual})."
                )

        # Reconcile geometry specification
        geom_input = geometry if geometry_valid is None else geometry_valid
        is_four_grid_mode = (verification_mode == "four_grid") or require_m3_stability

        qoi_meta = qoi_spec or {"type": "displacement", "units": "m"}
        base_qoi = {
            "kind": qoi_meta.get("type", "displacement"),
            "value": float(J0),
            "units": qoi_meta.get("units", "m"),
        }
        limitations = [
            "Estimated spatial discretisation uncertainty only (Grid Convergence Index)",
            "Model-form uncertainty is not included",
            "Material-property and boundary-condition uncertainties are not included",
        ]

        # Priority 1 & 2: QoI suitability and well-posedness
        if qoi_spec is not None:
            supported, refusal_code, reason = self.check_qoi_support(qoi_spec)
            if not supported and refusal_code is not None:
                priority = 1 if refusal_code == RefusalCode.ILL_POSED_QOI else 2
                return ContractResult(
                    issued=False,
                    status=refusal_code.value,
                    qoi=base_qoi,
                    refusal={"code": refusal_code.value, "reason": reason, "priority": priority},
                    limitations=limitations,
                )

        # Priority 3: Geometry validity
        geom_valid, geom_refusal, geom_reason = self.validate_geometry(geom_input)
        if not geom_valid and geom_refusal is not None:
            p_val = 3 if geom_refusal == RefusalCode.INVALID_GEOMETRY else 4
            return ContractResult(
                issued=False,
                status=geom_refusal.value,
                qoi=base_qoi,
                refusal={"code": geom_refusal.value, "reason": geom_reason, "priority": p_val},
                limitations=limitations,
            )

        # Priority 4: Mesh quality
        if (
            mesh_min_angle_deg is not None
            and mesh_min_angle_deg < self.min_angle_threshold_deg
        ):
            return ContractResult(
                issued=False,
                status=RefusalCode.MESH_QUALITY_FAILURE.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.MESH_QUALITY_FAILURE.value,
                    "reason": f"Minimum triangle angle ({mesh_min_angle_deg:.1f} deg) violates threshold ({self.min_angle_threshold_deg:.1f} deg).",
                    "priority": 4,
                },
                limitations=limitations,
            )

        # Priority 5: Solver convergence
        if (
            solver_relative_residual is not None
            and solver_relative_residual > self.solver_residual_tol
        ):
            return ContractResult(
                issued=False,
                status=RefusalCode.SOLVER_NOT_CONVERGED.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.SOLVER_NOT_CONVERGED.value,
                    "reason": f"Linear solver relative residual ({solver_relative_residual:.3e}) exceeds tolerance ({self.solver_residual_tol:.3e}).",
                    "priority": 5,
                },
                limitations=limitations,
            )

        # Priority 6: Sequence length and refinement ratio (minimum 3 levels, r = 2)
        if mesh_hierarchy is not None:
            hier_valid, hier_refusal, hier_reason = self.validate_mesh_hierarchy(
                mesh_hierarchy, verification_mode=verification_mode, meshes=meshes
            )
            if not hier_valid and hier_refusal is not None:
                return ContractResult(
                    issued=False,
                    status=hier_refusal.value,
                    qoi=base_qoi,
                    refusal={
                        "code": hier_refusal.value,
                        "reason": hier_reason,
                        "priority": 6,
                    },
                    limitations=limitations,
                )

        if mesh_levels is not None and mesh_levels < 3:
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                    "reason": f"Mesh levels ({mesh_levels}) insufficient for verification (minimum 3 required).",
                    "priority": 6,
                },
                limitations=limitations,
            )

        if refinement_ratio is not None and not np.isclose(refinement_ratio, 2.0, atol=1e-3):
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                    "reason": f"Refinement ratio r={refinement_ratio:.2f} does not match required uniform doubling r=2.0.",
                    "priority": 6,
                },
                limitations=limitations,
            )

        if is_four_grid_mode and J3 is None:
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS.value,
                    "reason": "Four-grid verification mode requires level M3 (J3) to be provided.",
                    "priority": 6,
                },
                limitations=limitations,
            )

        # Differences
        d01 = J0 - J1
        d12 = J1 - J2

        # Priority 7: Numerical difference floor
        if abs(d01) < self.numerical_floor or abs(d12) < self.numerical_floor:
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR.value,
                    "reason": f"Mesh differences (|d01|={abs(d01):.3e}, |d12|={abs(d12):.3e}) below numerical floor ({self.numerical_floor:.3e}).",
                    "priority": 7,
                },
                limitations=limitations,
            )

        # Priority 9: Monotonicity and Asymptotic range plausibility
        if (d01 * d12 <= 0.0) or (abs(d01) <= abs(d12)):
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value,
                    "reason": f"Differences are non-monotonic or non-convergent (d01={d01:.3e}, d12={d12:.3e}, q={abs(d01)/abs(d12):.3f} <= 1).",
                    "priority": 9,
                },
                limitations=limitations,
            )

        # Observed order
        q = abs(d01) / abs(d12)
        p_obs = float(np.log(q) / np.log(2.0))

        # Priority 8: Observed order plausibility window [0.5, 3.5]
        if not (self.order_window[0] <= p_obs <= self.order_window[1]):
            return ContractResult(
                issued=False,
                status=RefusalCode.UNVERIFIED_ORDER.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.UNVERIFIED_ORDER.value,
                    "reason": f"Observed order p_obs={p_obs:.2f} is outside the validated plausibility window [{self.order_window[0]}, {self.order_window[1]}].",
                    "priority": 8,
                },
                limitations=limitations,
            )

        # Four-grid M3 asymptotic stability validation (always calculate diagnostics if J3 provided)
        m3_stable: Optional[bool] = None
        p_123: Optional[float] = None
        delta_p: Optional[float] = None
        four_grid_status: str = "not_evaluated"

        if J3 is not None:
            d23 = J2 - J3
            if (d12 * d23 > 0.0) and (abs(d12) > abs(d23)):
                q_123 = abs(d12) / abs(d23)
                p_123 = float(np.log(q_123) / np.log(2.0))
                delta_p = float(abs(p_obs - p_123))
                # Stability criterion: |p_012 - p_123| <= 0.50
                m3_stable = bool(delta_p <= 0.50)
                four_grid_status = (
                    "four_grid_stability_passed"
                    if m3_stable
                    else "four_grid_stability_failed"
                )
            else:
                m3_stable = False
                four_grid_status = "four_grid_non_monotonic"

            # In four-grid mode, stability failure strictly refuses
            if is_four_grid_mode and not m3_stable:
                return ContractResult(
                    issued=False,
                    status=RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value,
                    qoi=base_qoi,
                    refusal={
                        "code": RefusalCode.UNVERIFIED_NON_ASYMPTOTIC.value,
                        "reason": f"Four-grid stability check failed (p_012={p_obs:.2f}, p_123={p_123 if p_123 is not None else 'N/A'}, delta_p={delta_p if delta_p is not None else 'N/A'}, status={four_grid_status}).",
                        "priority": 9,
                    },
                    limitations=limitations,
                )

        # Priority 10: Reference solution uncertainty gate
        if (
            reference_uncertainty is not None
            and reference_uncertainty > self.reference_uncertainty_gate
        ):
            return ContractResult(
                issued=False,
                status=RefusalCode.REFERENCE_UNCERTAIN.value,
                qoi=base_qoi,
                refusal={
                    "code": RefusalCode.REFERENCE_UNCERTAIN.value,
                    "reason": f"Reference solution numerical uncertainty ({reference_uncertainty:.3e}) exceeds frozen verification gate ({self.reference_uncertainty_gate:.3e}).",
                    "priority": 10,
                },
                limitations=limitations,
            )

        # Order cap and coarse-grid uncertainty calculation
        p_used = float(min(p_obs, self.p_cap))
        factor = (2.0**p_used) / (2.0**p_used - 1.0)
        U0 = float(self.Fs * abs(d01) * factor)

        # Accuracy target check (AM2-03: Budget exhaustion does NOT overturn an achieved target!)
        accuracy_meta = None
        if target is not None:
            if target.target_type == "absolute":
                metric_val = U0
            else:  # relative
                if (
                    target.qoi_scale is None
                    or target.qoi_scale <= 0.0
                    or not np.isfinite(target.qoi_scale)
                ):
                    raise ValueError(
                        f"Explicit positive finite qoi_scale is strictly required for relative accuracy targets (got {target.qoi_scale})."
                    )
                metric_val = U0 / target.qoi_scale

            target_met = bool(metric_val <= target.tolerance)
            # Budget exhaustion does not invalidate an achieved accuracy target
            estimated_target_met = target_met
            accuracy_status = (
                "estimated_target_met"
                if target_met
                else "estimated_target_not_met"
            )

            accuracy_meta = {
                "target_type": target.target_type,
                "requested_tolerance": target.tolerance,
                "evaluated_uncertainty_metric": float(metric_val),
                "estimated_target_met": estimated_target_met,
                "status": accuracy_status,
                "budget_exhausted": budget_exhausted,
            }

        uncertainty_meta = {
            "issued": True,
            "value": U0,
            "type": "estimated_spatial_discretization_gci",
            "safety_factor": self.Fs,
            "refinement_ratio": 2.0,
            "observed_order": p_obs,
            "order_cap": self.p_cap,
            "order_used": p_used,
            "mesh_levels": 4 if J3 is not None else 3,
        }

        verification_meta = {
            "status": "verified_within_tested_scope",
            "order_plausibility": "passed",
            "observed_order": p_obs,
            "order_window": list(self.order_window),
            "four_grid_status": four_grid_status,
            "m3_stability": m3_stable,
            "p_obs_123": p_123,
            "delta_p": delta_p,
            "verification_mode": "four_grid" if is_four_grid_mode else "three_grid",
        }

        # Contract status: distinguish 4-grid verified from standard 3-grid verified
        contract_status = (
            "four_grid_verified_contract_issued"
            if (J3 is not None and m3_stable is True)
            else "verified_contract_issued"
        )

        return ContractResult(
            issued=True,
            status=contract_status,
            qoi=base_qoi,
            uncertainty=uncertainty_meta,
            accuracy=accuracy_meta,
            verification=verification_meta,
            limitations=limitations,
        )
