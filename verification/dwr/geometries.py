"""
Phase B Benchmark Geometries and Regularised QoI Definitions.
Defines four engineering benchmark problems:
1. Cantilever Beam (smooth baseline, boundary average vertical displacement)
2. Plate with Circular Hole (stress concentration, ligament patch horizontal displacement)
3. Notched Tensile Bar (localised response, notch-root patch vertical displacement)
4. L-Shaped Elastic Domain (re-entrant corner singularity, arm patch vertical displacement)

Each problem provides three independent conforming initial mesh configurations.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import numpy as np
import scipy.spatial as spatial
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1, FacetBasis

from gdec.fem.elasticity import ConstitutiveTensor
from verification.mesh_utils import create_perturbed_mesh


@dataclass
class ProblemDefinition:
    id: str
    name: str
    material: ConstitutiveTensor
    qoi_scale: float
    patch_info: Dict[str, any]
    mesh_variants: List[str]

    def get_mesh(self, variant_idx: int = 0) -> fem.MeshTri:
        raise NotImplementedError

    def get_dirichlet_dofs(self, basis: Basis) -> np.ndarray:
        raise NotImplementedError

    def assemble_traction(self, basis: Basis) -> np.ndarray:
        raise NotImplementedError

    def assemble_qoi_vector(self, basis: Basis) -> np.ndarray:
        raise NotImplementedError

    def evaluate_qoi(self, u: np.ndarray, basis: Basis) -> float:
        g = self.assemble_qoi_vector(basis)
        return float(g @ u)


class CantileverProblem(ProblemDefinition):
    def __init__(self):
        mat = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
        super().__init__(
            id="cantilever",
            name="Cantilever Beam",
            material=mat,
            qoi_scale=1e-3,
            patch_info={"type": "boundary_average", "boundary": "right", "component": "y", "length": 0.5},
            mesh_variants=["structured_10x5", "perturbed_10x5_seed12345", "structured_16x8"],
        )

    def get_mesh(self, variant_idx: int = 0) -> fem.MeshTri:
        if variant_idx == 0:
            return fem.MeshTri.init_tensor(np.linspace(0.0, 2.0, 11), np.linspace(0.0, 0.5, 6)).oriented()
        elif variant_idx == 1:
            m_base, _ = create_perturbed_mesh(n=5, seed=12345)
            # Scale unit square to 2.0 x 0.5
            p_scaled = m_base.p.copy()
            p_scaled[0] *= 2.0
            p_scaled[1] *= 0.5
            return fem.MeshTri(p_scaled, m_base.t).oriented()
        elif variant_idx == 2:
            return fem.MeshTri.init_tensor(np.linspace(0.0, 2.0, 17), np.linspace(0.0, 0.5, 9)).oriented()
        else:
            raise ValueError(f"Invalid variant index {variant_idx}")

    def get_dirichlet_dofs(self, basis: Basis) -> np.ndarray:
        # Clamped at left boundary x = 0
        nodes = np.where(np.isclose(basis.doflocs[0], 0.0))[0]
        return np.unique(nodes)

    def assemble_traction(self, basis: Basis) -> np.ndarray:
        # Right boundary traction ty = -1e6 N/m (thickness = 0.02)
        m = basis.mesh
        right_facets = np.where(np.isclose(m.p[0, m.facets[0]], 2.0) & np.isclose(m.p[0, m.facets[1]], 2.0))[0]
        if len(right_facets) == 0:
            return np.zeros(basis.N)
        fbasis = FacetBasis(m, basis.elem, facets=right_facets)
        t_thick = self.material.thickness

        @fem.LinearForm
        def tr(v, w):
            return t_thick * (-1e6 * v[1])

        return fem.asm(tr, fbasis)

    def assemble_qoi_vector(self, basis: Basis) -> np.ndarray:
        # Boundary average vertical displacement on right boundary (H = 0.5)
        m = basis.mesh
        right_facets = np.where(np.isclose(m.p[0, m.facets[0]], 2.0) & np.isclose(m.p[0, m.facets[1]], 2.0))[0]
        if len(right_facets) == 0:
            return np.zeros(basis.N)
        fbasis = FacetBasis(m, basis.elem, facets=right_facets)

        @fem.LinearForm
        def qoi(v, w):
            return (1.0 / 0.5) * v[1]

        return fem.asm(qoi, fbasis)


class PlateWithHoleProblem(ProblemDefinition):
    def __init__(self):
        mat = ConstitutiveTensor.from_properties(E=200e9, nu=0.30, assumption="plane_stress", thickness=0.01)
        # Patch: x in [0.95, 1.05], y in [0.75, 0.95], area = 0.10 * 0.20 = 0.020
        super().__init__(
            id="plate_with_hole",
            name="Rectangular Plate with Circular Hole",
            material=mat,
            qoi_scale=1e-4,
            patch_info={
                "type": "patch_average",
                "component": "x",
                "xmin": 0.95,
                "xmax": 1.05,
                "ymin": 0.75,
                "ymax": 0.95,
                "area": 0.020,
            },
            mesh_variants=["conforming_h014", "conforming_h011", "conforming_h009"],
        )

    def _generate_mesh(self, h_target: float, n_circ: int) -> fem.MeshTri:
        width, height, r_hole, xc, yc = 2.0, 1.0, 0.25, 1.0, 0.5
        nx = int(np.ceil(width / h_target))
        ny = int(np.ceil(height / h_target))

        pts = []
        for x in np.linspace(0, width, nx + 1):
            pts.append([x, 0.0])
            pts.append([x, height])
        for y in np.linspace(0, height, ny + 1):
            pts.append([0.0, y])
            pts.append([width, y])

        thetas = np.linspace(0, 2 * np.pi, n_circ, endpoint=False)
        for th in thetas:
            pts.append([xc + r_hole * np.cos(th), yc + r_hole * np.sin(th)])

        for x in np.linspace(h_target / 2, width - h_target / 2, nx):
            for y in np.linspace(h_target / 2, height - h_target / 2, ny):
                if np.hypot(x - xc, y - yc) > r_hole + 0.45 * h_target:
                    pts.append([x, y])

        pts = np.unique(np.array(pts), axis=0)
        tri = spatial.Delaunay(pts)
        tris = [
            s
            for s in tri.simplices
            if np.hypot(pts[s].mean(axis=0)[0] - xc, pts[s].mean(axis=0)[1] - yc) > r_hole * 0.999
        ]
        m = fem.MeshTri(pts.T, np.array(tris).T).remove_unused_nodes()
        for e in range(m.t.shape[1]):
            v = m.p[:, m.t[:, e]]
            if 0.5 * ((v[0, 1] - v[0, 0]) * (v[1, 2] - v[1, 0]) - (v[0, 2] - v[0, 0]) * (v[1, 1] - v[1, 0])) < 0:
                m.t[[1, 2], e] = m.t[[2, 1], e]
        return m

    def get_mesh(self, variant_idx: int = 0) -> fem.MeshTri:
        if variant_idx == 0:
            return self._generate_mesh(h_target=0.14, n_circ=24)
        elif variant_idx == 1:
            return self._generate_mesh(h_target=0.11, n_circ=28)
        elif variant_idx == 2:
            return self._generate_mesh(h_target=0.09, n_circ=32)
        else:
            raise ValueError(f"Invalid variant index {variant_idx}")

    def get_dirichlet_dofs(self, basis: Basis) -> np.ndarray:
        # Left boundary: ux = 0 (roller constraint)
        # Rigid body y-fix: bottom-left corner uy = 0 at (0, 0)
        dofs = []
        locs = basis.doflocs
        # x-dofs on left edge
        left_mask = np.isclose(locs[0], 0.0)
        # Even dofs are x-displacement
        ux_dofs = np.where(left_mask & (np.arange(basis.N) % 2 == 0))[0]
        dofs.extend(ux_dofs)

        # Fix uy at bottom-left corner
        bl_mask = np.isclose(locs[0], 0.0) & np.isclose(locs[1], 0.0)
        uy_bl = np.where(bl_mask & (np.arange(basis.N) % 2 == 1))[0]
        dofs.extend(uy_bl)
        return np.unique(np.array(dofs, dtype=int))

    def assemble_traction(self, basis: Basis) -> np.ndarray:
        # Right boundary tension tx = 1e7 N/m
        m = basis.mesh
        right_facets = np.where(np.isclose(m.p[0, m.facets[0]], 2.0) & np.isclose(m.p[0, m.facets[1]], 2.0))[0]
        if len(right_facets) == 0:
            return np.zeros(basis.N)
        fbasis = FacetBasis(m, basis.elem, facets=right_facets)
        t_thick = self.material.thickness

        @fem.LinearForm
        def tr(v, w):
            return t_thick * (1e7 * v[0])

        return fem.asm(tr, fbasis)

    def assemble_qoi_vector(self, basis: Basis) -> np.ndarray:
        # Patch average ux in [0.95, 1.05] x [0.75, 0.95]
        area = self.patch_info["area"]
        xmin, xmax = self.patch_info["xmin"], self.patch_info["xmax"]
        ymin, ymax = self.patch_info["ymin"], self.patch_info["ymax"]

        @fem.LinearForm
        def qoi(v, w):
            in_patch = (w.x[0] >= xmin) & (w.x[0] <= xmax) & (w.x[1] >= ymin) & (w.x[1] <= ymax)
            return (1.0 / area) * in_patch.astype(float) * v[0]

        return fem.asm(qoi, basis)


class NotchedBarProblem(ProblemDefinition):
    def __init__(self):
        mat = ConstitutiveTensor.from_properties(E=210e9, nu=0.28, assumption="plane_stress", thickness=0.015)
        # Patch: x in [0.90, 1.10], y in [0.35, 0.45], area = 0.20 * 0.10 = 0.020
        super().__init__(
            id="notched_bar",
            name="Notched Tensile Bar",
            material=mat,
            qoi_scale=1e-4,
            patch_info={
                "type": "patch_average",
                "component": "y",
                "xmin": 0.90,
                "xmax": 1.10,
                "ymin": 0.35,
                "ymax": 0.45,
                "area": 0.020,
            },
            mesh_variants=["notched_h014", "notched_h011", "notched_h009"],
        )

    def _generate_mesh(self, h_target: float) -> fem.MeshTri:
        width, height, notch_x, notch_r = 2.0, 0.8, 1.0, 0.15
        ny = int(np.ceil(height / h_target))
        nx_seg = int(np.ceil((notch_x - notch_r) / h_target))

        pts = []
        for y in np.linspace(0, height, ny + 1):
            pts.append([0.0, y])
            pts.append([width, y])

        for x in np.linspace(0, notch_x - notch_r, nx_seg + 1):
            pts.append([x, 0.0])
            pts.append([x, height])
        for x in np.linspace(notch_x + notch_r, width, nx_seg + 1):
            pts.append([x, 0.0])
            pts.append([x, height])

        thetas = np.linspace(0, np.pi, 16)
        for th in thetas:
            pts.append([notch_x - notch_r * np.cos(th), 0.0 + notch_r * np.sin(th)])
            pts.append([notch_x - notch_r * np.cos(th), height - notch_r * np.sin(th)])

        grid_x = np.linspace(h_target / 2, width - h_target / 2, int(width / h_target))
        grid_y = np.linspace(h_target / 2, height - h_target / 2, int(height / h_target))
        for x in grid_x:
            for y in grid_y:
                d_bot = np.hypot(x - notch_x, y - 0.0)
                d_top = np.hypot(x - notch_x, y - height)
                if d_bot > notch_r + 0.35 * h_target and d_top > notch_r + 0.35 * h_target:
                    pts.append([x, y])

        pts = np.unique(np.array(pts), axis=0)
        tri = spatial.Delaunay(pts)
        tris = []
        for s in tri.simplices:
            c = pts[s].mean(axis=0)
            d_bot = np.hypot(c[0] - notch_x, c[1] - 0.0)
            d_top = np.hypot(c[0] - notch_x, c[1] - height)
            if d_bot > notch_r * 0.999 and d_top > notch_r * 0.999:
                tris.append(s)

        m = fem.MeshTri(pts.T, np.array(tris).T).remove_unused_nodes()
        for e in range(m.t.shape[1]):
            v = m.p[:, m.t[:, e]]
            if 0.5 * ((v[0, 1] - v[0, 0]) * (v[1, 2] - v[1, 0]) - (v[0, 2] - v[0, 0]) * (v[1, 1] - v[1, 0])) < 0:
                m.t[[1, 2], e] = m.t[[2, 1], e]
        return m

    def get_mesh(self, variant_idx: int = 0) -> fem.MeshTri:
        if variant_idx == 0:
            return self._generate_mesh(h_target=0.14)
        elif variant_idx == 1:
            return self._generate_mesh(h_target=0.11)
        elif variant_idx == 2:
            return self._generate_mesh(h_target=0.09)
        else:
            raise ValueError(f"Invalid variant index {variant_idx}")

    def get_dirichlet_dofs(self, basis: Basis) -> np.ndarray:
        # Bottom clamped: ux = 0, uy = 0 on y = 0
        nodes = np.where(np.isclose(basis.doflocs[1], 0.0))[0]
        return np.unique(nodes)

    def assemble_traction(self, basis: Basis) -> np.ndarray:
        # Top boundary tension: ty = 1.5e7 N/m on y = 0.8
        m = basis.mesh
        top_facets = np.where(np.isclose(m.p[1, m.facets[0]], 0.8) & np.isclose(m.p[1, m.facets[1]], 0.8))[0]
        if len(top_facets) == 0:
            return np.zeros(basis.N)
        fbasis = FacetBasis(m, basis.elem, facets=top_facets)
        t_thick = self.material.thickness

        @fem.LinearForm
        def tr(v, w):
            return t_thick * (1.5e7 * v[1])

        return fem.asm(tr, fbasis)

    def assemble_qoi_vector(self, basis: Basis) -> np.ndarray:
        # Patch average uy in [0.90, 1.10] x [0.35, 0.45]
        area = self.patch_info["area"]
        xmin, xmax = self.patch_info["xmin"], self.patch_info["xmax"]
        ymin, ymax = self.patch_info["ymin"], self.patch_info["ymax"]

        @fem.LinearForm
        def qoi(v, w):
            in_patch = (w.x[0] >= xmin) & (w.x[0] <= xmax) & (w.x[1] >= ymin) & (w.x[1] <= ymax)
            return (1.0 / area) * in_patch.astype(float) * v[1]

        return fem.asm(qoi, basis)


class LShapedProblem(ProblemDefinition):
    def __init__(self):
        mat = ConstitutiveTensor.from_properties(E=100e9, nu=0.25, assumption="plane_strain", thickness=1.0)
        # Domain: [0, 1]x[0, 1] \ [0.5, 1.0]x[0.5, 1.0]
        # Re-entrant corner at (0.5, 0.5)
        # Patch: x in [0.10, 0.40], y in [0.60, 0.90], area = 0.30 * 0.30 = 0.090 (away from singularity)
        super().__init__(
            id="l_shaped",
            name="L-Shaped Elastic Domain",
            material=mat,
            qoi_scale=1e-5,
            patch_info={
                "type": "patch_average",
                "component": "y",
                "xmin": 0.10,
                "xmax": 0.40,
                "ymin": 0.60,
                "ymax": 0.90,
                "area": 0.090,
            },
            mesh_variants=["l_shaped_coarse_n4", "l_shaped_medium_n6", "l_shaped_fine_n8"],
        )

    def _generate_mesh(self, n: int) -> fem.MeshTri:
        m1 = fem.MeshTri.init_tensor(np.linspace(0, 0.5, n + 1), np.linspace(0, 0.5, n + 1))
        m2 = fem.MeshTri.init_tensor(np.linspace(0.5, 1.0, n + 1), np.linspace(0, 0.5, n + 1))
        m3 = fem.MeshTri.init_tensor(np.linspace(0, 0.5, n + 1), np.linspace(0.5, 1.0, n + 1))
        m = (m1 + m2 + m3).remove_duplicate_nodes().oriented()
        return m

    def get_mesh(self, variant_idx: int = 0) -> fem.MeshTri:
        if variant_idx == 0:
            return self._generate_mesh(n=4)
        elif variant_idx == 1:
            return self._generate_mesh(n=6)
        elif variant_idx == 2:
            return self._generate_mesh(n=8)
        else:
            raise ValueError(f"Invalid variant index {variant_idx}")

    def get_dirichlet_dofs(self, basis: Basis) -> np.ndarray:
        # Bottom boundary clamped: ux = 0, uy = 0 on y = 0
        nodes = np.where(np.isclose(basis.doflocs[1], 0.0))[0]
        return np.unique(nodes)

    def assemble_traction(self, basis: Basis) -> np.ndarray:
        # Right edge of bottom leg (x = 1.0, y in [0, 0.5]): shear ty = -5e6 N/m
        m = basis.mesh
        right_facets = np.where(
            np.isclose(m.p[0, m.facets[0]], 1.0)
            & np.isclose(m.p[0, m.facets[1]], 1.0)
            & (m.p[1, m.facets[0]] <= 0.5 + 1e-6)
            & (m.p[1, m.facets[1]] <= 0.5 + 1e-6)
        )[0]
        if len(right_facets) == 0:
            return np.zeros(basis.N)
        fbasis = FacetBasis(m, basis.elem, facets=right_facets)
        t_thick = self.material.thickness

        @fem.LinearForm
        def tr(v, w):
            return t_thick * (-5e6 * v[1])

        return fem.asm(tr, fbasis)

    def assemble_qoi_vector(self, basis: Basis) -> np.ndarray:
        # Patch average uy in [0.10, 0.40] x [0.60, 0.90] in upper arm
        area = self.patch_info["area"]
        xmin, xmax = self.patch_info["xmin"], self.patch_info["xmax"]
        ymin, ymax = self.patch_info["ymin"], self.patch_info["ymax"]

        @fem.LinearForm
        def qoi(v, w):
            in_patch = (w.x[0] >= xmin) & (w.x[0] <= xmax) & (w.x[1] >= ymin) & (w.x[1] <= ymax)
            return (1.0 / area) * in_patch.astype(float) * v[1]

        return fem.asm(qoi, basis)


BENCHMARK_PROBLEMS = {
    "cantilever": CantileverProblem(),
    "plate_with_hole": PlateWithHoleProblem(),
    "notched_bar": NotchedBarProblem(),
    "l_shaped": LShapedProblem(),
}
