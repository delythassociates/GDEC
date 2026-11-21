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
class FacetResidualData:
    """Detailed geometric and mechanical residual data for mesh facets."""
    facet_indices: np.ndarray
    is_interior: np.ndarray
    lengths: np.ndarray
    normals: np.ndarray
    tangents: np.ndarray
    element_0: np.ndarray
    element_1: np.ndarray
    traction_jumps: np.ndarray
    boundary_residuals: np.ndarray
    dual_weights: np.ndarray
    signed_dwr_contributions: np.ndarray
    abs_dwr_contributions: np.ndarray


class FacetTractionJumpEvaluator:
    """Evaluates inter-element normal traction jumps and boundary traction residuals."""

    def __init__(self, constitutive: ConstitutiveTensor):
        self.c = constitutive

    def evaluate(
        self,
        gdec_mesh: GDECMesh,
        stresses: np.ndarray,
        loads: Optional[List[Tuple[str, float, float]]] = None,
    ) -> FacetResidualData:
        """
        Compute outward unit normals, traction jumps [[sigma_h * n]] across interior facets,
        and boundary traction residuals t_applied - sigma_h * n on Neumann boundaries.
        """
        skm = gdec_mesh.mesh
        p = skm.p
        t = skm.t
        f2t = skm.f2t
        facets = skm.facets
        nfacets = facets.shape[1]
        is_interior = f2t[1] >= 0

        v0 = facets[0]
        v1 = facets[1]
        dx = p[0, v1] - p[0, v0]
        dy = p[1, v1] - p[1, v0]
        lengths = np.sqrt(dx**2 + dy**2)
        tangents = np.vstack([dx, dy]) / np.maximum(lengths, 1e-14)

        # Initial normals [dy, -dx] / length
        normals = np.vstack([dy, -dx]) / np.maximum(lengths, 1e-14)

        # Orient normals outward from element e0 = f2t[0]
        centroids = np.mean(p[:, t], axis=1)  # (2, nelements)
        midpoints = 0.5 * (p[:, v0] + p[:, v1])
        e0 = f2t[0]
        e1 = f2t[1]

        v_c2m = midpoints - centroids[:, e0]
        dots = np.sum(v_c2m * normals, axis=0)
        flip = dots < 0
        normals[:, flip] = -normals[:, flip]

        # Extract stresses on e0
        s_xx_0 = stresses[0, e0]
        s_yy_0 = stresses[1, e0]
        s_xy_0 = stresses[2, e0]

        # Traction on e0: T_0 = sigma_0 * n_0
        t0_x = s_xx_0 * normals[0] + s_xy_0 * normals[1]
        t0_y = s_xy_0 * normals[0] + s_yy_0 * normals[1]

        # Compute traction jumps on interior facets: [[sigma_h * n]] = T_0 - T_1
        traction_jumps = np.zeros((2, nfacets), dtype=float)
        int_idx = np.where(is_interior)[0]
        e1_int = e1[int_idx]
        s_xx_1 = stresses[0, e1_int]
        s_yy_1 = stresses[1, e1_int]
        s_xy_1 = stresses[2, e1_int]

        t1_x = s_xx_1 * normals[0, int_idx] + s_xy_1 * normals[1, int_idx]
        t1_y = s_xy_1 * normals[0, int_idx] + s_yy_1 * normals[1, int_idx]

        traction_jumps[0, int_idx] = t0_x[int_idx] - t1_x
        traction_jumps[1, int_idx] = t0_y[int_idx] - t1_y

        # Boundary residuals on external facets: R_bnd = t_applied - T_0
        boundary_residuals = np.zeros((2, nfacets), dtype=float)
        load_map: Dict[str, Tuple[float, float]] = {}
        if loads:
            for bnd, tx, ty in loads:
                load_map[bnd.lower().strip()] = (tx, ty)

        bnd_idx = np.where(~is_interior)[0]
        for f in bnd_idx:
            mx, my = midpoints[0, f], midpoints[1, f]
            # Identify boundary name from coordinates
            bnd_name = None
            if np.isclose(mx, 0.0, atol=1e-5):
                bnd_name = "left"
            elif np.isclose(mx, gdec_mesh.width, atol=1e-5):
                bnd_name = "right"
            elif np.isclose(my, 0.0, atol=1e-5):
                bnd_name = "bottom"
            elif np.isclose(my, gdec_mesh.height, atol=1e-5):
                bnd_name = "top"

            if bnd_name and bnd_name in load_map:
                applied_tx, applied_ty = load_map[bnd_name]
            else:
                applied_tx, applied_ty = 0.0, 0.0

            boundary_residuals[0, f] = applied_tx - t0_x[f]
            boundary_residuals[1, f] = applied_ty - t0_y[f]

        return FacetResidualData(
            facet_indices=np.arange(nfacets),
            is_interior=is_interior,
            lengths=lengths,
            normals=normals,
            tangents=tangents,
            element_0=e0,
            element_1=e1,
            traction_jumps=traction_jumps,
            boundary_residuals=boundary_residuals,
            dual_weights=np.zeros((2, nfacets), dtype=float),
            signed_dwr_contributions=np.zeros(nfacets, dtype=float),
            abs_dwr_contributions=np.zeros(nfacets, dtype=float),
        )


class DualWeightEvaluator:
    """
    Evaluates dual weighting int_F (z - Pi_h z) dGamma along mesh facets using
    higher-order adjoint gradient recovery.
    """

    @staticmethod
    def evaluate(
        gdec_mesh: GDECMesh,
        sol: FEMSolution,
        facet_data: FacetResidualData,
        fixed_boundary_names: Optional[List[str]] = None,
    ) -> np.ndarray:
        """
        Compute edge-integrated dual weights along each facet:
        w_F = int_F (z - Pi_h z) ds ~ (h_F^2 / 12) * [ (grad_z(v0) - grad_z(v1)) * t_F ]
        """
        if sol.z is None:
            raise ValueError("Adjoint solution z is required for dual weighting.")

        skm = gdec_mesh.mesh
        p = skm.p
        t = skm.t
        nnodes = gdec_mesh.nnodes
        areas = gdec_mesh.element_areas

        # Compute element gradients of adjoint solution z
        # basis.interpolate(sol.z).grad has shape (2, 2, nelements, nquad)
        grad_z = sol.basis.interpolate(sol.z).grad[:, :, :, 0]  # (2, 2, nelements)

        # Recover nodal gradients by area-weighted patch averaging
        nodal_grad_z = np.zeros((2, 2, nnodes), dtype=float)
        nodal_weights = np.zeros(nnodes, dtype=float)
        for v in range(3):
            nodes = t[v, :]
            for comp in range(2):
                for coord in range(2):
                    np.add.at(nodal_grad_z[comp, coord], nodes, areas * grad_z[comp, coord])
            np.add.at(nodal_weights, nodes, areas)
        nodal_grad_z /= np.maximum(nodal_weights, 1e-14)

        # For each facet, compute edge bubble integral
        v0 = skm.facets[0]
        v1 = skm.facets[1]
        h_F = facet_data.lengths
        t_F = facet_data.tangents

        # w_F_comp = (h_F^2 / 12.0) * sum_coord (grad_z(v0)[comp, coord] - grad_z(v1)[comp, coord]) * t_F[coord]
        dual_weights = np.zeros((2, len(h_F)), dtype=float)
        for comp in range(2):
            diff_0 = nodal_grad_z[comp, 0, v0] - nodal_grad_z[comp, 0, v1]
            diff_1 = nodal_grad_z[comp, 1, v0] - nodal_grad_z[comp, 1, v1]
            directional_diff = diff_0 * t_F[0] + diff_1 * t_F[1]
            dual_weights[comp] = (h_F**2 / 12.0) * directional_diff

        # On Dirichlet boundaries where z is constrained to zero, dual error vanishes
        fixed_names = set(fixed_boundary_names or ["left"])
        bnd_idx = np.where(~facet_data.is_interior)[0]
        midpoints = 0.5 * (p[:, v0] + p[:, v1])
        for f in bnd_idx:
            mx, my = midpoints[0, f], midpoints[1, f]
            is_fixed = False
            if "left" in fixed_names and np.isclose(mx, 0.0, atol=1e-5):
                is_fixed = True
            elif "right" in fixed_names and np.isclose(mx, gdec_mesh.width, atol=1e-5):
                is_fixed = True
            elif "bottom" in fixed_names and np.isclose(my, 0.0, atol=1e-5):
                is_fixed = True
            elif "top" in fixed_names and np.isclose(my, gdec_mesh.height, atol=1e-5):
                is_fixed = True

            if is_fixed:
                dual_weights[:, f] = 0.0

        return dual_weights


class ElementResidualEvaluator:
    """Evaluates element interior equilibrium residuals R_K = b + div(sigma_h)."""

    @staticmethod
    def evaluate(
        gdec_mesh: GDECMesh,
        sol: FEMSolution,
        body_force_fn: Optional[Any] = None,
    ) -> np.ndarray:
        """
        In linear P1 triangles, element stresses are constant, so div(sigma_h) is identically zero.
        Returns element-wise body force residuals if applicable.
        """
        ne = gdec_mesh.nelements
        if body_force_fn is None:
            return np.zeros((2, ne), dtype=float)
        centroids = gdec_mesh.element_centroids
        b_val = body_force_fn(centroids)  # shape (2, ne)
        return np.asarray(b_val, dtype=float)


class DWREstimator(GoalOrientedEstimator):
    """
    Goal-Oriented Dual-Weighted Residual (DWR) a posteriori error estimator.
    Evaluates:
      J(u) - J(u_h) = sum_{F in F_I} int_F -[[sigma_h n]] . (z - Pi_h z) dGamma
                    + sum_{F in F_N} int_F (t - sigma_h n) . (z - Pi_h z) dGamma
                    + sum_{K} int_K (b + div(sigma_h)) . (z - Pi_h z) dOmega
    """

    def __init__(self, constitutive: ConstitutiveTensor):
        self.c = constitutive
        self.jump_evaluator = FacetTractionJumpEvaluator(constitutive)
        self.dual_evaluator = DualWeightEvaluator()
        self.elem_evaluator = ElementResidualEvaluator()

    def estimate(
        self,
        gdec_mesh: GDECMesh,
        sol: FEMSolution,
        loads: Optional[List[Tuple[str, float, float]]] = None,
        cost_aware: bool = True,
    ) -> IndicatorResult:
        if sol.z is None:
            raise ValueError("Adjoint solution z is required for DWR error estimation.")

        # 1. Compute element strains and stresses
        grad_u = sol.basis.interpolate(sol.u).grad[:, :, :, 0]
        eps_11 = grad_u[0, 0, :]
        eps_22 = grad_u[1, 1, :]
        gamma_12 = grad_u[0, 1, :] + grad_u[1, 0, :]

        c11, c12, c33 = self.c.c11, self.c.c12, self.c.c33
        sig_11 = c11 * eps_11 + c12 * eps_22
        sig_22 = c12 * eps_11 + c11 * eps_22
        sig_12 = c33 * gamma_12
        stresses = np.vstack([sig_11, sig_22, sig_12])

        # 2. Evaluate facet traction jumps and boundary residuals
        facet_data = self.jump_evaluator.evaluate(gdec_mesh, stresses, loads=loads)

        # 3. Evaluate dual weights along facets
        dual_weights = self.dual_evaluator.evaluate(gdec_mesh, sol, facet_data)
        facet_data.dual_weights = dual_weights

        # 4. Integrate facet DWR contributions
        # On interior facets: -[[sigma_h n]] . (z - Pi_h z)
        # On boundary facets: (t_applied - sigma_h n) . (z - Pi_h z)
        thickness = self.c.thickness
        signed_facet_dwr = np.zeros(len(facet_data.lengths), dtype=float)
        abs_facet_dwr = np.zeros(len(facet_data.lengths), dtype=float)

        int_idx = np.where(facet_data.is_interior)[0]
        signed_facet_dwr[int_idx] = thickness * (
            facet_data.traction_jumps[0, int_idx] * dual_weights[0, int_idx]
            + facet_data.traction_jumps[1, int_idx] * dual_weights[1, int_idx]
        )
        abs_facet_dwr[int_idx] = np.abs(signed_facet_dwr[int_idx])

        bnd_idx = np.where(~facet_data.is_interior)[0]
        signed_facet_dwr[bnd_idx] = thickness * (
            facet_data.boundary_residuals[0, bnd_idx] * dual_weights[0, bnd_idx]
            + facet_data.boundary_residuals[1, bnd_idx] * dual_weights[1, bnd_idx]
        )
        abs_facet_dwr[bnd_idx] = np.abs(signed_facet_dwr[bnd_idx])

        facet_data.signed_dwr_contributions = signed_facet_dwr
        facet_data.abs_dwr_contributions = abs_facet_dwr

        # 5. Distribute facet indicators to elements
        ne = gdec_mesh.nelements
        elem_indicators = np.zeros(ne, dtype=float)
        e0 = facet_data.element_0
        e1 = facet_data.element_1

        # Interior facets split 50/50 between e0 and e1
        np.add.at(elem_indicators, e0[int_idx], 0.5 * abs_facet_dwr[int_idx])
        np.add.at(elem_indicators, e1[int_idx], 0.5 * abs_facet_dwr[int_idx])

        # Boundary facets assigned 100% to e0
        np.add.at(elem_indicators, e0[bnd_idx], abs_facet_dwr[bnd_idx])

        # 6. Global error estimates
        signed_qoi_error = float(np.sum(signed_facet_dwr))
        abs_indicator_sum = float(np.sum(elem_indicators))

        # 7. Cost-aware priority
        est_dofs = np.full(ne, 4.0)
        if cost_aware:
            priorities = elem_indicators / np.maximum(est_dofs, 1.0)
        else:
            priorities = elem_indicators.copy()

        return IndicatorResult(
            name="Goal_Oriented_DWR",
            indicators=elem_indicators,
            priorities=priorities,
            estimated_dofs_increase=est_dofs,
            details={
                "method": "dual_weighted_residual",
                "classification": "goal_oriented_dwr_estimator",
                "is_certified_dwr_bound": False,
                "signed_qoi_error_estimate": signed_qoi_error,
                "signed_qoi_error_estimate_mm": signed_qoi_error * 1000.0,
                "absolute_error_indicator_sum": abs_indicator_sum,
                "interior_jump_contribution": float(np.sum(signed_facet_dwr[int_idx])),
                "boundary_residual_contribution": float(np.sum(signed_facet_dwr[bnd_idx])),
                "max_traction_jump": float(np.max(np.sqrt(facet_data.traction_jumps[0]**2 + facet_data.traction_jumps[1]**2))),
                "cost_aware": cost_aware,
                "max_indicator": float(np.max(elem_indicators)),
            },
        )


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
        self.dwr_estimator = DWREstimator(constitutive)

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

        # 2. Recover element centroid stress: average of 3 vertices
        v0 = triangles[0, :]
        v1 = triangles[1, :]
        v2 = triangles[2, :]
        recovered_elem_stresses = (
            nodal_recovered_stresses[:, v0]
            + nodal_recovered_stresses[:, v1]
            + nodal_recovered_stresses[:, v2]
        ) / 3.0

        # 3. Stress difference Delta sigma = sigma* - sigma
        delta_sig = recovered_elem_stresses - stresses

        # 4. Energy norm indicator: sqrt( A_e * thickness * (delta_sig^T * C^{-1} * delta_sig) )
        C_inv = self.c.compliance_3x3
        # delta_sig has shape (3, ne)
        # Compute quadratic form for each column
        # q = sum_i sum_j delta_sig[i] * C_inv[i,j] * delta_sig[j]
        C_inv_delta = C_inv @ delta_sig  # shape (3, ne)
        quad = np.sum(delta_sig * C_inv_delta, axis=0)  # shape (ne,)
        quad = np.maximum(quad, 0.0)

        eta_zz = np.sqrt(areas * thickness * quad)

        # Estimate additional DOFs per element (local bisection adds ~2-4 DOFs per marked element)
        est_dofs = np.full(ne, 4.0)

        return IndicatorResult(
            name="Recovery_ZZ_NodalAveraging",
            indicators=eta_zz,
            priorities=eta_zz,
            estimated_dofs_increase=est_dofs,
            details={
                "method": "Zienkiewicz-Zhu stress recovery (area-weighted nodal averaging)",
                "classification": "area_weighted_nodal_stress_averaging",
                "max_indicator": float(np.max(eta_zz)),
                "total_energy_error": float(np.sqrt(np.sum(eta_zz**2))),
            },
        )

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
        # In engineering Voigt notation:
        # sig_11 * eps_z_11 + sig_22 * eps_z_22 + sig_12 * (2 * eps_z_12)
        inner_prod = (
            sig_u[0, :] * eps_z[0, :]
            + sig_u[1, :] * eps_z[1, :]
            + sig_u[2, :] * eps_z[2, :]
        )

        # Sensitivity heuristic: eta_e = h_e^2 * A_e * | inner_prod |
        eta_goal = (he**2) * areas * np.abs(inner_prod)

        # Cost model: estimate additional DOFs if element e is refined
        # Elements in high-aspect-ratio regions or boundaries trigger green closures.
        # Baseline predicted cost: ~4 DOFs per marked element
        est_dofs = np.full(ne, 4.0)

        if cost_aware:
            # P_e = eta_e / est_dofs
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

    def compute_dwr_indicator(
        self,
        gdec_mesh: GDECMesh,
        sol: FEMSolution,
        loads: Optional[List[Tuple[str, float, float]]] = None,
        cost_aware: bool = True,
    ) -> IndicatorResult:
        """
        Compute mathematically consistent goal-oriented Dual-Weighted Residual (DWR)
        indicators and signed QoI error estimates.
        """
        return self.dwr_estimator.estimate(
            gdec_mesh=gdec_mesh, sol=sol, loads=loads, cost_aware=cost_aware
        )

    def compute_residual_energy_indicator(
        self,
        gdec_mesh: GDECMesh,
        sol: FEMSolution,
        loads: Optional[List[Tuple[str, float, float]]] = None,
    ) -> IndicatorResult:
        """
        Standard residual-based energy norm indicator (Ainsworth-Oden):
        eta_K^2 = h_K * sum_{F in del K} || [[sigma_h n]] ||^2
        """
        grad_u = sol.basis.interpolate(sol.u).grad[:, :, :, 0]
        c11, c12, c33 = self.c.c11, self.c.c12, self.c.c33
        eps_11 = grad_u[0, 0, :]
        eps_22 = grad_u[1, 1, :]
        gamma_12 = grad_u[0, 1, :] + grad_u[1, 0, :]

        sig_11 = c11 * eps_11 + c12 * eps_22
        sig_22 = c12 * eps_11 + c11 * eps_22
        sig_12 = c33 * gamma_12
        stresses = np.vstack([sig_11, sig_22, sig_12])

        evaluator = FacetTractionJumpEvaluator(self.c)
        facet_data = evaluator.evaluate(gdec_mesh, stresses, loads=loads)

        jump_sq = (
            facet_data.traction_jumps[0] ** 2 + facet_data.traction_jumps[1] ** 2
        )
        int_idx = np.where(facet_data.is_interior)[0]

        ne = gdec_mesh.nelements
        h_K = gdec_mesh.element_diameters
        eta_sq = np.zeros(ne, dtype=float)

        e0 = facet_data.element_0
        e1 = facet_data.element_1
        h_F = facet_data.lengths

        np.add.at(eta_sq, e0[int_idx], 0.5 * h_F[int_idx] * jump_sq[int_idx])
        np.add.at(eta_sq, e1[int_idx], 0.5 * h_F[int_idx] * jump_sq[int_idx])

        # Multiply by element diameter h_K
        eta = np.sqrt(np.maximum(h_K * eta_sq, 0.0))

        est_dofs = np.full(ne, 4.0)
        return IndicatorResult(
            name="Residual_Energy_Norm",
            indicators=eta,
            priorities=eta,
            estimated_dofs_increase=est_dofs,
            details={
                "method": "residual_energy_norm",
                "classification": "residual_energy_norm_indicator",
                "is_certified_dwr_bound": False,
                "max_indicator": float(np.max(eta)),
                "total_energy_indicator": float(np.sqrt(np.sum(eta**2))),
            },
        )
