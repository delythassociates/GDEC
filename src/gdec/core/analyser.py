"""
GDEC Problem Analyser and Numerical Verification Contract Engine.
Implements:
1. Problem analysis, geometry inspection, and QoI suitability validation.
2. Deterministic refusal mechanics for ill-posed or unsupported engineering requests.
3. Nested uniform refinement (r = 2) spatial discretisation uncertainty estimation (GCI).
4. Four-grid observed order stability validation (M0, M1, M2, M3).
5. Structured accuracy contract output schema conforming to Phase C specifications.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import skfem as fem


class RefusalCode(str, Enum):
    ILL_POSED_QOI = "ill_posed_qoi"
    UNSUPPORTED_QOI = "unsupported_qoi"
    UNVERIFIED_INSUFFICIENT_LEVELS = "unverified_insufficient_levels"
    UNVERIFIED_ORDER = "unverified_order"
    UNVERIFIED_NON_ASYMPTOTIC = "unverified_non_asymptotic"
    UNVERIFIED_DIFFERENCE_BELOW_NUMERICAL_FLOOR = "unverified_difference_below_numerical_floor"
    MESH_QUALITY_FAILURE = "mesh_quality_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"
    SOLVER_NOT_CONVERGED = "solver_not_converged"
    REFERENCE_UNCERTAIN = "reference_uncertain"


@dataclass
class AccuracyTarget:
    target_type: str  # "relative" or "absolute"
    tolerance: float  # e.g. 0.01 (1.0%)
    qoi_scale: float = 1.0  # Scale S_J for relative comparison


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
    ):
        self.Fs = safety_factor_Fs
        self.p_cap = order_cap_p_cap
        self.order_window = order_window
        self.numerical_floor = numerical_floor
        self.min_angle_threshold_deg = min_angle_threshold_deg
        self.solver_residual_tol = solver_residual_tol

    def check_mesh_quality(self, mesh: fem.MeshTri) -> Tuple[bool, float]:
        """
        Calculates the minimum interior angle across all triangles in the mesh.
        Returns (is_valid, min_angle_degrees).
        """
        p = mesh.p
        t = mesh.t
        v0 = p[:, t[0]]
        v1 = p[:, t[1]]
        v2 = p[:, t[2]]

        # Edge lengths
        a = np.linalg.norm(v1 - v2, axis=0)
        b = np.linalg.norm(v2 - v0, axis=0)
        c = np.linalg.norm(v0 - v1, axis=0)

        # Law of cosines for all three interior angles
        # Clamp arguments to [-1, 1] to avoid float precision domain errors
        cos_alpha = np.clip((b**2 + c**2 - a**2) / (2.0 * np.maximum(b * c, 1e-14)), -1.0, 1.0)
        cos_beta = np.clip((a**2 + c**2 - b**2) / (2.0 * np.maximum(a * c, 1e-14)), -1.0, 1.0)
        cos_gamma = np.clip((a**2 + b**2 - c**2) / (2.0 * np.maximum(a * b, 1e-14)), -1.0, 1.0)

        min_angles_rad = np.minimum(np.arccos(cos_alpha), np.minimum(np.arccos(cos_beta), np.arccos(cos_gamma)))
        min_angle_deg = float(np.min(np.degrees(min_angles_rad)))

        is_valid = bool(min_angle_deg >= self.min_angle_threshold_deg)
        return is_valid, min_angle_deg

    def check_qoi_support(self, qoi_spec: Dict[str, Any]) -> Tuple[bool, Optional[RefusalCode], str]:
        """
        Validates whether the requested QoI is mathematically supported in the current H^1 setting.
        """
        qtype = qoi_spec.get("type", "").lower()
        location = qoi_spec.get("location")
        is_singular_point = qoi_spec.get("is_singular_point", False)

        if qtype == "point_stress":
            if is_singular_point or (location is not None and np.allclose(location, [0.0, 0.0])):
                return (
                    False,
                    RefusalCode.ILL_POSED_QOI,
                    "Point stress at re-entrant corner or notch singularity is mathematically divergent in H^1 elasticity.",
                )
            return (
                False,
                RefusalCode.UNSUPPORTED_QOI,
                "Point stress evaluation is currently unsupported. Use a regularized patch average.",
            )

        if qtype == "point_displacement":
            return (
                False,
                RefusalCode.UNSUPPORTED_QOI,
                "Unregularized point displacement is unsupported in 2D H^1 setting. Use a boundary or patch average.",
            )

        if qtype in ["boundary_average_displacement", "patch_average_displacement", "boundary_average", "patch_average"]:
            return True, None, "Supported displacement functional."

        if qtype in ["patch_average_stress", "patch_stress"]:
            # Exploratory support only
            return True, None, "Exploratory patch stress functional."

        return False, RefusalCode.UNSUPPORTED_QOI, f"Functional type '{qtype}' is not supported by GDEC."

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
    ) -> ContractResult:
        """
        Evaluates the verification contract for computed QoIs on nested levels M0, M1, M2.
        Enforces deterministic refusal priority.
        """
        qoi_meta = qoi_spec or {"type": "displacement", "units": "m"}
        base_qoi = {"kind": qoi_meta.get("type", "displacement"), "value": float(J0), "units": qoi_meta.get("units", "m")}
        limitations = [
            "Estimated spatial discretisation uncertainty only (Grid Convergence Index)",
            "Model-form uncertainty is not included",
            "Material-property and boundary-condition uncertainties are not included",
        ]

        # Priority 1 & 2: QoI suitability and well-posedness
        if qoi_spec is not None:
            supported, refusal_code, reason = self.check_qoi_support(qoi_spec)
            if not supported and refusal_code is not None:
                return ContractResult(
                    issued=False,
                    status=refusal_code.value,
                    qoi=base_qoi,
                    refusal={"code": refusal_code.value, "reason": reason, "priority": 1},
                    limitations=limitations,
                )

        # Priority 4: Mesh quality
        if mesh_min_angle_deg is not None and mesh_min_angle_deg < self.min_angle_threshold_deg:
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
        if solver_relative_residual is not None and solver_relative_residual > self.solver_residual_tol:
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

        # Priority 8 & 9: Monotonicity and Asymptotic range plausibility
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

        # Check observed order plausibility window [0.5, 3.5]
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

        # Four-grid M3 asymptotic stability validation (if M3 available)
        m3_stable = None
        p_123 = None
        if J3 is not None:
            d23 = J2 - J3
            if (d12 * d23 > 0.0) and (abs(d12) > abs(d23)):
                q_123 = abs(d12) / abs(d23)
                p_123 = float(np.log(q_123) / np.log(2.0))
                # Stability criterion: |p_012 - p_123| <= 0.50
                m3_stable = bool(abs(p_obs - p_123) <= 0.50)

        # Order cap and coarse-grid uncertainty calculation
        p_used = float(min(p_obs, self.p_cap))
        factor = (2.0**p_used) / (2.0**p_used - 1.0)
        U0 = float(self.Fs * abs(d01) * factor)

        # Accuracy target check
        accuracy_meta = None
        if target is not None:
            if target.target_type == "absolute":
                target_met = bool(U0 <= target.tolerance)
                metric_val = U0
            else:  # relative
                scale = target.qoi_scale if target.qoi_scale > 0 else max(abs(J0), 1e-12)
                rel_u = U0 / scale
                target_met = bool(rel_u <= target.tolerance)
                metric_val = rel_u

            accuracy_meta = {
                "target_type": target.target_type,
                "requested_tolerance": target.tolerance,
                "evaluated_uncertainty_metric": float(metric_val),
                "estimated_target_met": target_met and not budget_exhausted,
                "status": "estimated_target_met" if target_met else "estimated_target_not_met",
            }
            if budget_exhausted and not target_met:
                accuracy_meta["budget_exhausted"] = True

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
            "m3_stability": m3_stable,
            "p_obs_123": p_123,
        }

        return ContractResult(
            issued=True,
            status="verified_contract_issued",
            qoi=base_qoi,
            uncertainty=uncertainty_meta,
            accuracy=accuracy_meta,
            verification=verification_meta,
            limitations=limitations,
        )
