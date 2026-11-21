"""
Restricted analytical parameter propagation for linear-elastic scaling.
Exploits the exact scaling invariant: J(E, P) = (P / P_0) * (E_0 / E) * J_0
for compatible fixed linear displacement functionals under verified physical assumptions.
Requires ZERO additional FEM solves.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

from gdec.dse.exceptions import ScalingAssumptionError


@dataclass(frozen=True)
class ScalingAssumptions:
    """
    Explicit physical and mathematical assumptions required for exact linear-elastic scaling.
    NO assumptions default to True. Every precondition must be positively attested by the caller.
    """
    uniform_material_scaling: bool       # Homogeneous Young's modulus throughout domain
    fixed_geometry: bool                 # Domain mesh does not deform or change shape
    fixed_poisson_ratio: bool            # Poisson's ratio nu is constant (not varied)
    linear_elastic_regime: bool          # Infinitesimal strains, Hookean constitutive law
    proportional_loading: bool           # Spatial load distribution shape is fixed; magnitude scales by P
    compatible_displacement_qoi: bool    # QoI is a fixed linear functional of displacement (e.g. tip deflection)
    qoi_type: str = "fixed_displacement" # Type of QoI: "fixed_displacement", "compliance", "stress"
    attested_by: str = ""                # Explicit provenance or engineer ID attesting these assumptions

    def validate(self) -> None:
        """Validate that all physical preconditions for exact linear scaling hold."""
        if not self.attested_by.strip():
            raise ScalingAssumptionError(
                "Scaling rejected: Assumptions must declare an explicit attestation provenance (attested_by)."
            )
        if not self.uniform_material_scaling:
            raise ScalingAssumptionError(
                "Scaling rejected: Multi-material or spatially heterogeneous Young's modulus requires separate solves."
            )
        if not self.fixed_geometry:
            raise ScalingAssumptionError("Scaling rejected: Varying geometry invalidates stiffness matrix scaling.")
        if not self.fixed_poisson_ratio:
            raise ScalingAssumptionError(
                "Scaling rejected: Varying Poisson's ratio nu changes the Lamé parameter ratio; requires re-assembly."
            )
        if not self.linear_elastic_regime:
            raise ScalingAssumptionError("Scaling rejected: Nonlinear kinematics or plasticity invalidates linear scaling.")
        if not self.proportional_loading:
            raise ScalingAssumptionError("Scaling rejected: Non-proportional load changes load direction/spatial distribution.")
        if not self.compatible_displacement_qoi:
            raise ScalingAssumptionError(
                "Scaling rejected: Stress QoIs or non-linear functionals do not scale identically by (P/P0)*(E0/E)."
            )

        q_type = self.qoi_type.lower().strip()
        if q_type in ("compliance", "energy", "strain_energy"):
            raise ScalingAssumptionError(
                f"Scaling rejected: Load-dependent compliance C(P, E) = f(P)^T u(P, E) scales quadratically with load "
                f"as C(P, E) = (P / P_0)^2 * (E_0 / E) * C_0, not linearly as (P / P_0) * (E_0 / E). "
                f"Use a verified compliance scaling formulation."
            )
        if q_type in ("stress", "von_mises", "tresca", "principal_stress"):
            raise ScalingAssumptionError(
                "Scaling rejected: Stress tensors sigma = C : eps(u) scale as P / P_0 (independent of E under fixed load). "
                "The displacement scaling formula (P / P_0) * (E_0 / E) cannot be applied to stress QoIs."
            )
        if q_type != "fixed_displacement":
            raise ScalingAssumptionError(
                f"Unsupported QoI type '{self.qoi_type}'. Only 'fixed_displacement' functionals are supported."
            )


@dataclass(frozen=True)
class ReferenceBaseline:
    """Certified reference baseline computed from an initial high-fidelity FEM solve."""
    E_0: float               # Reference Young's modulus (must be finite and > 0)
    P_0: float               # Reference load factor (must be finite and != 0)
    J_0: float               # Reference Quantity of Interest value (must be finite)
    poisson_ratio: float     # Fixed Poisson's ratio (must be in [0, 0.5))
    dof_count: int           # Degrees of freedom of the reference solve
    qoi_name: str            # Name of the QoI

    def __post_init__(self) -> None:
        if not math.isfinite(self.E_0) or self.E_0 <= 0.0:
            raise ScalingAssumptionError(f"Reference Young's modulus E_0 must be a positive finite number, got {self.E_0}")
        if not math.isfinite(self.P_0) or self.P_0 == 0.0:
            raise ScalingAssumptionError(f"Reference load factor P_0 must be a non-zero finite number, got {self.P_0}")
        if not math.isfinite(self.J_0):
            raise ScalingAssumptionError(f"Reference QoI J_0 must be a finite number, got {self.J_0}")
        if not math.isfinite(self.poisson_ratio) or not (0.0 <= self.poisson_ratio < 0.5):
            raise ScalingAssumptionError(f"Poisson's ratio must be a finite number in [0, 0.5), got {self.poisson_ratio}")
        if self.dof_count <= 0:
            raise ScalingAssumptionError(f"DOF count must be a positive integer, got {self.dof_count}")


class RestrictedLinearElasticScaling:
    """
    Evaluator for the restricted linear-elastic scaling case.
    Computes exact predictions for arbitrary (E, P) combinations with zero additional FEM solves:
        J(E, P) = (P / P_0) * (E_0 / E) * J_0
    """

    def __init__(
        self,
        baseline: ReferenceBaseline,
        assumptions: ScalingAssumptions,
    ) -> None:
        self.baseline = baseline
        self.assumptions = assumptions
        self.assumptions.validate()

    def evaluate_scalar(self, E: float, P: float) -> float:
        """
        Evaluate scaled QoI for a single (E, P) parameter pair:
            J(E, P) = (P / P_0) * (E_0 / E) * J_0
        """
        if not math.isfinite(E) or E <= 0.0:
            raise ScalingAssumptionError(f"Young's modulus E must be a positive finite number, got {E}")
        if not math.isfinite(P):
            raise ScalingAssumptionError(f"Load factor P must be a finite number, got {P}")

        try:
            val = (P / self.baseline.P_0) * (self.baseline.E_0 / E) * self.baseline.J_0
        except OverflowError as e:
            raise ScalingAssumptionError(f"Numerical overflow during analytical scaling: {e}") from e

        if not math.isfinite(val):
            raise ScalingAssumptionError("Analytical scaling produced a non-finite output value.")

        return float(val)

    def evaluate_batch(
        self,
        E_samples: np.ndarray | List[float],
        P_samples: np.ndarray | List[float],
    ) -> np.ndarray:
        """
        Evaluate scaled QoI for arrays of (E, P) samples via CPU vectorized NumPy.
        Requires ZERO additional FEM solves.
        """
        E_arr = np.asarray(E_samples, dtype=np.float64)
        P_arr = np.asarray(P_samples, dtype=np.float64)

        if E_arr.size == 0 or P_arr.size == 0:
            raise ScalingAssumptionError("Sample arrays cannot be empty.")
        if E_arr.shape != P_arr.shape:
            raise ScalingAssumptionError(f"Sample array shapes must match: E {E_arr.shape} != P {P_arr.shape}")
        if np.any(np.isnan(E_arr)) or np.any(np.isinf(E_arr)):
            raise ScalingAssumptionError("Sampled Young's modulus array contains non-finite values (NaN or Inf).")
        if np.any(np.isnan(P_arr)) or np.any(np.isinf(P_arr)):
            raise ScalingAssumptionError("Sampled load factor array contains non-finite values (NaN or Inf).")
        if np.any(E_arr <= 0.0):
            raise ScalingAssumptionError("All sampled Young's moduli E must be strictly positive.")

        res = (P_arr / self.baseline.P_0) * (self.baseline.E_0 / E_arr) * self.baseline.J_0
        if not np.all(np.isfinite(res)):
            raise ScalingAssumptionError("Analytical batch scaling produced non-finite values (overflow).")

        return res

    def evaluate_moments(
        self,
        E_samples: np.ndarray | List[float],
        P_samples: np.ndarray | List[float],
    ) -> Tuple[float, float]:
        """
        Compute sample mean and standard deviation of scaled QoI over sample arrays.
        """
        J_samples = self.evaluate_batch(E_samples, P_samples)
        ddof = 1 if len(J_samples) > 1 else 0
        return float(np.mean(J_samples)), float(np.std(J_samples, ddof=ddof))
