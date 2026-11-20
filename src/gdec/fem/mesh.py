"""
Mesh generation and boundary tagging for GDEC.
Provides conforming triangular 2D meshes with persistent boundary definitions.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional
import numpy as np
import skfem as fem


class GDECMesh:
    def __init__(self, skfem_mesh: fem.MeshTri, width: float, height: float):
        self.mesh = skfem_mesh
        self.width = float(width)
        self.height = float(height)

    @classmethod
    def create_cantilever_mesh(
        cls, width: float = 2.0, height: float = 0.5, nx: int = 9, ny: int = 5
    ) -> GDECMesh:
        """Create an initial conforming Delaunay triangular mesh for the cantilever plate."""
        x = np.linspace(0.0, width, nx)
        y = np.linspace(0.0, height, ny)
        skm = fem.MeshTri.init_tensor(x, y)
        return cls(skm, width, height)

    @property
    def nelements(self) -> int:
        return self.mesh.t.shape[1]

    @property
    def nnodes(self) -> int:
        return self.mesh.p.shape[1]

    @property
    def element_areas(self) -> np.ndarray:
        p = self.mesh.p
        t = self.mesh.t
        v0 = p[:, t[0]]
        v1 = p[:, t[1]]
        v2 = p[:, t[2]]
        return 0.5 * np.abs((v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1]))

    @property
    def element_diameters(self) -> np.ndarray:
        return np.sqrt(2.0 * self.element_areas)

    @property
    def element_centroids(self) -> np.ndarray:
        p = self.mesh.p
        t = self.mesh.t
        return np.mean(p[:, t], axis=1)

    def get_boundary_facets(self, boundary_name: str, tol: float = 1e-6) -> np.ndarray:
        """Return facet indices for named boundaries: 'left', 'right', 'top', 'bottom'."""
        bnd = boundary_name.lower().strip()
        if bnd == "left":
            return self.mesh.facets_satisfying(lambda x: np.isclose(x[0], 0.0, atol=tol))
        elif bnd == "right":
            return self.mesh.facets_satisfying(lambda x: np.isclose(x[0], self.width, atol=tol))
        elif bnd == "bottom":
            return self.mesh.facets_satisfying(lambda x: np.isclose(x[1], 0.0, atol=tol))
        elif bnd == "top":
            return self.mesh.facets_satisfying(lambda x: np.isclose(x[1], self.height, atol=tol))
        else:
            raise ValueError(f"Unknown boundary name: '{boundary_name}'")

    def refine_uniform(self) -> GDECMesh:
        """Uniform refinement: splits every triangle into 4 conforming triangles."""
        refined_skm = self.mesh.refined()
        return GDECMesh(refined_skm, self.width, self.height)

    def refine_elements(self, marked_elements: np.ndarray) -> GDECMesh:
        """Local adaptive refinement using red-green conforming refinement."""
        if len(marked_elements) == 0:
            return self
        refined_skm = self.mesh.refined(marked_elements)
        return GDECMesh(refined_skm, self.width, self.height)
