"""
Restricted analytical parameter propagation for linear-elastic scaling.
Exploits the exact scaling invariant: J(E, P) = (P / P_0) * (E_0 / E) * J_0
for compatible displacement functionals, requiring zero additional FEM solves.
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
    Mandatory physical and numerical assumptions required for exact linear-elastic scaling.
    All flags must be explicitly verified and certified.
    """
    uniform_material_scaling: bool = True     # Homogeneous Young's modulus throughout domain
    fixed_geometry: bool = True               # Domain mesh does not deform or change shape
    fixed_poisson_ratio: bool = True          # Poisson's ratio nu is constant (not varied)
    linear_elastic_regime: bool = True        # Infinitesimal strains, Hookean constitutive law
    proportional_loading: bool = True         # Spatial load distribution shape is fixed; magnitude scales by P
    compatible_displacement_qoi: bool = True  # QoI is a linear functional of displacement (deflection, compliance)

    def validate(self) -> None:
        """Validate that all physical preconditions for exact scaling hold."""
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


@dataclass(frozen=True)
class ReferenceBaseline:
    """Certified reference baseline computed from an initial high-fidelity FEM solve."""
    E_0: float               # Reference Young's modulus
    P_0: float               # Reference load factor
    J_0: float               # Reference Quantity of Interest value
    poisson_ratio: float     # Fixed Poisson's ratio
    dof_count: int           # Degrees of freedom of the reference solve
    qoi_name: str            # Name of the QoI

    def __post_init__(self) -> None:
        if self.E_0 <= 0.0:
            raise ScalingAssumptionError(f"Reference Young's modulus E_0 must be positive, got {self.E_0}")
        if self.P_0 == 0.0:
            raise ScalingAssumptionError("Reference load factor P_0 cannot be zero.")
        if not math.isfinite(self.J_0):
            raise ScalingAssumptionError(f"Reference QoI J_0 must be a finite number, got {self.J_0}")
        if not (0.0 <= self.poisson_ratio < 0.5):
            raise ScalingAssumptionError(f"Poisson's ratio must be in [0, 0.5), got {self.poisson_ratio}")


class RestrictedLinearElasticScaling:
    """
    Evaluator for the restricted linear-elastic scaling case.
    Computes exact predictions for arbitrary (E, P) combinations with zero additional FEM solves.
    """

    def __init__(
        self,
        baseline: ReferenceBaseline,
        assumptions: Optional[ScalingAssumptions] = None,
    ) -> None:
        self.baseline = baseline
        self.assumptions = assumptions or ScalingAssumptions()
        self.assumptions.validate()

    def evaluate_scalar(self, E: float, P: float) -> float:
        """
        Evaluate scaled QoI for a single (E, P) parameter pair:
            J(E, P) = (P / P_0) * (E_0 / E) * J_0
        """
        if E <= 0.0:
            raise ScalingAssumptionError(f"Young's modulus E must be strictly positive, got {E}")
        if not math.isfinite(P):
            raise ScalingAssumptionError(f"Load factor P must be finite, got {P}")

        return (P / self.baseline.P_0) * (self.baseline.E_0 / E) * self.baseline.J_0

    def evaluate_batch(
        self,
        E_samples: np.ndarray,
        P_samples: np.ndarray,
    ) -> np.ndarray:
        """
        Evaluate scaled QoI for arrays of (E, P) samples via CPU vectorized NumPy.
        Requires ZERO additional FEM solves.
        """
        E_arr = np.asarray(E_samples, dtype=np.float64)
        P_arr = np.asarray(P_samples, dtype=np.float64)

        if E_arr.shape != P_arr.shape:
            raise ValueError(f"Sample array shapes must match: E {E_arr.shape} != P {P_arr.shape}")
        if np.any(E_arr <= 0.0):
            raise ScalingAssumptionError("All sampled Young's moduli E must be strictly positive.")

        return (P_arr / self.baseline.P_0) * (self.baseline.E_0 / E_arr) * self.baseline.J_0

    def evaluate_moments(
        self,
        E_samples: np.ndarray,
        P_samples: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Compute sample mean and standard deviation of scaled QoI over sample arrays.
        """
        J_samples = self.evaluate_batch(E_samples, P_samples)
        return float(np.mean(J_samples)), float(np.std(J_samples, ddof=1 if len(J_samples) > 1 else 0))
