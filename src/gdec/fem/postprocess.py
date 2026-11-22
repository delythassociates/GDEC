"""
Post-processing and field evaluation for GDEC FEM simulations.
Calculates engineering quantities: QoI, displacement magnitudes, Cauchy stresses,
and Von Mises stress for plane stress and plane strain.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np
import skfem as fem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, FEMSolution


@dataclass
class PostprocessResult:
    qoi_meters: float
    qoi_mm: float
    max_disp_magnitude: float
    u_x: np.ndarray             # nodal x displacements (nnodes,)
    u_y: np.ndarray             # nodal y displacements (nnodes,)
    sigma_xx: np.ndarray        # element-wise stress (nelements,)
    sigma_yy: np.ndarray        # element-wise stress (nelements,)
    tau_xy: np.ndarray          # element-wise shear stress (nelements,)
    von_mises: np.ndarray       # element-wise Von Mises stress (nelements,)
    nodal_von_mises: np.ndarray # nodal recovered Von Mises stress (nnodes,)


class PostProcessor:
    def __init__(self, constitutive: ConstitutiveTensor):
        self.c = constitutive

    def _von_mises(self, sigma_xx: np.ndarray, sigma_yy: np.ndarray, tau_xy: np.ndarray) -> np.ndarray:
        """Compute the 3D von Mises invariant for plane-stress or plane-strain fields."""
        if self.c.assumption == "plane_strain":
            sigma_zz = self.c.nu * (sigma_xx + sigma_yy)
        else:
            sigma_zz = np.zeros_like(sigma_xx)

        vm_sq = 0.5 * (
            (sigma_xx - sigma_yy) ** 2
            + (sigma_yy - sigma_zz) ** 2
            + (sigma_zz - sigma_xx) ** 2
        ) + 3.0 * (tau_xy ** 2)
        return np.sqrt(np.maximum(vm_sq, 0.0))

    def process(self, gdec_mesh: GDECMesh, sol: FEMSolution) -> PostprocessResult:
        nnodes = gdec_mesh.nnodes
        nelements = gdec_mesh.nelements

        # Nodal displacements
        u_x = sol.u[0::2]
        u_y = sol.u[1::2]
        disp_mag = np.sqrt(u_x**2 + u_y**2)
        max_disp = float(np.max(disp_mag))

        # Strains & stresses on elements
        grad = sol.basis.interpolate(sol.u).grad[:, :, :, 0]
        eps_11 = grad[0, 0, :]
        eps_22 = grad[1, 1, :]
        gamma_12 = grad[0, 1, :] + grad[1, 0, :]

        c11 = self.c.c11
        c12 = self.c.c12
        c33 = self.c.c33

        s_xx = c11 * eps_11 + c12 * eps_22
        s_yy = c12 * eps_11 + c11 * eps_22
        s_xy = c33 * gamma_12

        von_mises = self._von_mises(s_xx, s_yy, s_xy)

        # Recover nodal von Mises stress for smooth rendering
        areas = gdec_mesh.element_areas
        triangles = gdec_mesh.mesh.t
        nodal_vm_sum = np.zeros(nnodes, dtype=float)
        nodal_w_sum = np.zeros(nnodes, dtype=float)

        for v in range(3):
            nodes = triangles[v, :]
            np.add.at(nodal_vm_sum, nodes, areas * von_mises)
            np.add.at(nodal_w_sum, nodes, areas)

        nodal_von_mises = nodal_vm_sum / np.maximum(nodal_w_sum, 1e-14)

        return PostprocessResult(
            qoi_meters=sol.qoi,
            qoi_mm=sol.qoi_mm,
            max_disp_magnitude=max_disp,
            u_x=u_x,
            u_y=u_y,
            sigma_xx=s_xx,
            sigma_yy=s_yy,
            tau_xy=s_xy,
            von_mises=von_mises,
            nodal_von_mises=nodal_von_mises,
        )
