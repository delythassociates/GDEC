"""
Refinement error indicators and sensitivity estimators for GDEC.
Provides:
  1. Uniform indicator (all elements equal)
  2. Zienkiewicz-Zhu (ZZ) recovery-based energy norm indicator (area-weighted nodal averaging)
  3. Adjoint-informed Goal-Aware QoI sensitivity heuristic (goal_heuristic_v1) with cost awareness
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import skfem as fem
from skfem.helpers import sym_grad

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, FEMSolution


class GoalOrientedEstimator(ABC):
    """Abstract base class for goal-oriented error estimators and indicators."""

    @abstractmethod
    def estimate(
        self, gdec_mesh: GDECMesh, sol: FEMSolution, cost_aware: bool = True
    ) -> IndicatorResult:
        """Compute goal-oriented element-wise refinement indicators and priorities."""
        pass


@dataclass
class IndicatorResult:
    name: str
    indicators: np.ndarray       # per-element raw indicator values
    priorities: np.ndarray       # per-element selection priority (cost-weighed if applicable)
    estimated_dofs_increase: np.ndarray  # predicted additional DOFs if element is refined
    details: Dict[str, any]      # auxiliary diagnostic data


class RefinementEstimator:
    """Computes element-wise indicators and marking priorities."""

    def __init__(self, constitutive: ConstitutiveTensor):
        self.c = constitutive

    def compute_element_strains_and_stresses(
        self, gdec_mesh: GDECMesh, sol: FEMSolution, field_vec: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute constant strain and stress tensors on each triangular element.
        Returns:
          strains: shape (3, nelements) [eps_11, eps_22, 2*eps_12]
          stresses: shape (3, nelements) [sig_11, sig_22, sig_12]
        """
        # In P1 triangle, gradient is uniform across each element.
        # basis.interpolate(field_vec).grad has shape (2, 2, nelements, nquad)
        grad = sol.basis.interpolate(field_vec).grad
        # Take values at quadrature point 0 (constant across P1 triangle)
        grad0 = grad[:, :, :, 0]  # shape (2, 2, nelements)

        eps_11 = grad0[0, 0, :]
        eps_22 = grad0[1, 1, :]
        eps_12 = 0.5 * (grad0[0, 1, :] + grad0[1, 0, :])
        gamma_12 = 2.0 * eps_12

        strains = np.vstack([eps_11, eps_22, gamma_12])

        # Stress via constitutive matrix
        c11 = self.c.c11
        c12 = self.c.c12
        c33 = self.c.c33

        sig_11 = c11 * eps_11 + c12 * eps_22
        sig_22 = c12 * eps_11 + c11 * eps_22
        sig_12 = c33 * gamma_12

        stresses = np.vstack([sig_11, sig_22, sig_12])
        return strains, stresses

    def compute_uniform_indicator(self, gdec_mesh: GDECMesh) -> IndicatorResult:
        """Uniform refinement: marks all elements."""
        ne = gdec_mesh.nelements
        indicators = np.ones(ne, dtype=float)
        # Uniform refinement replaces 1 triangle with 4 triangles, adding ~1.5 new nodes per element
        est_dofs = np.full(ne, 3.0)
        return IndicatorResult(
            name="Uniform",
            indicators=indicators,
            priorities=indicators,
            estimated_dofs_increase=est_dofs,
            details={"method": "uniform"},
        )

    def compute_zz_recovery_indicator(
        self, gdec_mesh: GDECMesh, sol: FEMSolution
    ) -> IndicatorResult:
        """
        Zienkiewicz-Zhu (ZZ) recovery-based energy norm indicator.
        Averages element stresses to nodes, interpolates recovered nodal stresses back
        to element centroids, and integrates compliance-weighted stress jump.
        """
        ne = gdec_mesh.nelements
        nn = gdec_mesh.nnodes
        areas = gdec_mesh.element_areas
        thickness = self.c.thickness
        triangles = gdec_mesh.mesh.t  # shape (3, ne)

        _, stresses = self.compute_element_strains_and_stresses(gdec_mesh, sol, sol.u)

        # 1. Recover nodal stresses by area-weighted averaging
        nodal_stresses_sum = np.zeros((3, nn), dtype=float)
        nodal_weights_sum = np.zeros(nn, dtype=float)

        for local_v in range(3):
            nodes = triangles[local_v, :]
            for comp in range(3):
                np.add.at(nodal_stresses_sum[comp], nodes, areas * stresses[comp])
            np.add.at(nodal_weights_sum, nodes, areas)

        # Avoid division by zero
        nodal_weights_sum = np.maximum(nodal_weights_sum, 1e-14)
        nodal_recovered_stresses = nodal_stresses_sum / nodal_weights_sum[None, :]

        # 2. Quadrature-based exact integration for degree-2 energy norm of linearly recovered stress
        # Using Hammer/Dunavant 3-point midpoint rule (exact for quadratic polynomials on triangles):
        v0 = triangles[0, :]
        v1 = triangles[1, :]
        v2 = triangles[2, :]

        s0 = nodal_recovered_stresses[:, v0]
        s1 = nodal_recovered_stresses[:, v1]
        s2 = nodal_recovered_stresses[:, v2]

        # Midpoint stresses for the linearly interpolated recovered stress field sigma*
        s_m01 = 0.5 * (s0 + s1)
        s_m12 = 0.5 * (s1 + s2)
        s_m20 = 0.5 * (s2 + s0)

        # Stress difference Delta sigma = sigma* - sigma_h at each midpoint
        ds01 = s_m01 - stresses
        ds12 = s_m12 - stresses
        ds20 = s_m20 - stresses

        # 3. Energy norm integration: sqrt( integral_Omega_e (Delta sigma^T * C^{-1} * Delta sigma) dOmega )
        C_inv = self.c.compliance_3x3
        q01 = np.sum(ds01 * (C_inv @ ds01), axis=0)
        q12 = np.sum(ds12 * (C_inv @ ds12), axis=0)
        q20 = np.sum(ds20 * (C_inv @ ds20), axis=0)

        # Exact degree-2 quadrature: Area * (q01 + q12 + q20) / 3.0
        quad_exact = (q01 + q12 + q20) / 3.0
        quad_exact = np.maximum(quad_exact, 0.0)

        eta_zz = np.sqrt(areas * thickness * quad_exact)

        # Estimate additional DOFs per element via local topology
        est_dofs = self.estimate_element_refinement_costs(gdec_mesh)

        return IndicatorResult(
            name="Recovery_ZZ_NodalAveraging",
            indicators=eta_zz,
            priorities=eta_zz,
            estimated_dofs_increase=est_dofs,
            details={
                "method": "Zienkiewicz-Zhu stress recovery (area-weighted nodal averaging with degree-2 triangle quadrature)",
                "classification": "area_weighted_nodal_stress_averaging",
                "quadrature": "degree_2_hammer_dunavant_3_point",
                "max_indicator": float(np.max(eta_zz)),
                "total_energy_error": float(np.sqrt(np.sum(eta_zz**2))),
            },
        )

    @staticmethod
    def estimate_element_refinement_costs(gdec_mesh: GDECMesh) -> np.ndarray:
        """
        Estimate element-dependent incremental refinement cost (in degrees of freedom).
        Uses local mesh topology:
        - Boundary facet count per element (boundary elements trigger fewer neighbor splits).
        - Element aspect ratio (higher aspect ratio triggers longer green closure chains).
        """
        ne = gdec_mesh.nelements
        mesh = gdec_mesh.mesh
        p = mesh.p
        t = mesh.t

        # Boundary facet detection via f2t and t2f
        if hasattr(mesh, "f2t") and hasattr(mesh, "t2f"):
            f2t = mesh.f2t
            t2f = mesh.t2f
            is_bnd_facet = (f2t[0] == f2t[1]) | (f2t[1] == -1)
            bnd_facets_per_elem = np.sum(is_bnd_facet[t2f], axis=0)
        else:
            bnd_facets_per_elem = np.zeros(ne, dtype=int)

        # Aspect ratio of triangle edges
        e0 = np.linalg.norm(p[:, t[1]] - p[:, t[0]], axis=0)
        e1 = np.linalg.norm(p[:, t[2]] - p[:, t[1]], axis=0)
        e2 = np.linalg.norm(p[:, t[0]] - p[:, t[2]], axis=0)
        longest = np.maximum(e0, np.maximum(e1, e2))
        shortest = np.minimum(e0, np.minimum(e1, e2))
        aspect = longest / np.maximum(shortest, 1e-12)

        # Base cost: 2.0 DOFs (1 new vertex).
        # Neighbor propagation: +1.0 DOF per interior facet.
        # Aspect penalty: +0.5 * (aspect - 1.0) for non-equilateral elements.
        propagation_dofs = 2.0 - bnd_facets_per_elem.astype(float)
        aspect_penalty = 0.5 * np.maximum(aspect - 1.0, 0.0)
        costs = 2.0 + 1.0 * propagation_dofs + aspect_penalty
        return costs

    def compute_goal_aware_indicator(
        self, gdec_mesh: GDECMesh, sol: FEMSolution, cost_aware: bool = True
    ) -> IndicatorResult:
        """
        Adjoint-informed Goal-Aware QoI sensitivity heuristic (goal_heuristic_v1):
        eta_e = h_e^2 * A_e * | eps_e(u) : C : eps_e(z) |
        where u is primal solution and z is adjoint solution.
        Cost-aware priority: P_e = eta_e / Delta_Cost_e
        
        NOTE: This indicator provides element marking priority; it is a heuristic sensitivity
        indicator and not a certified dual-weighted residual (DWR) a posteriori error bound.
        """
        if sol.z is None:
            raise ValueError("Adjoint solution z is required for goal-aware indicator.")

        ne = gdec_mesh.nelements
        areas = gdec_mesh.element_areas
        he = gdec_mesh.element_diameters
        thickness = self.c.thickness

        # Primal strain and stress
        eps_u, sig_u = self.compute_element_strains_and_stresses(gdec_mesh, sol, sol.u)
        # Adjoint strain
        eps_z, _ = self.compute_element_strains_and_stresses(gdec_mesh, sol, sol.z)

        # Inner product: eps(u) : C : eps(z) = sig(u) : eps(z)
        inner_prod = (
            sig_u[0, :] * eps_z[0, :]
            + sig_u[1, :] * eps_z[1, :]
            + sig_u[2, :] * eps_z[2, :]
        )

        # Sensitivity heuristic: eta_e = h_e^2 * A_e * | inner_prod |
        eta_goal = (he**2) * areas * np.abs(inner_prod)

        # Cost model: calculate element-dependent estimated refinement cost based on mesh topology
        est_dofs = self.estimate_element_refinement_costs(gdec_mesh)

        if cost_aware:
            priorities = eta_goal / np.maximum(est_dofs, 1.0)
        else:
            priorities = eta_goal.copy()

        return IndicatorResult(
            name="Goal_Aware_Adjoint",
            indicators=eta_goal,
            priorities=priorities,
            estimated_dofs_increase=est_dofs,
            details={
                "method": "goal_heuristic_v1",
                "classification": "heuristic_priority_indicator",
                "is_certified_dwr_bound": False,
                "cost_aware": cost_aware,
                "max_sensitivity": float(np.max(eta_goal)),
                "sum_sensitivity": float(np.sum(eta_goal)),
            },
        )

    def compute_goal_heuristic_v1_indicator(
        self, gdec_mesh: GDECMesh, sol: FEMSolution, cost_aware: bool = True
    ) -> IndicatorResult:
        """Explicit alias for goal_heuristic_v1 indicator."""
        return self.compute_goal_aware_indicator(gdec_mesh, sol, cost_aware=cost_aware)
