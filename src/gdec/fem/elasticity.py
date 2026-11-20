"""
2D Linear Elasticity FEM formulation for small strains.
Supports isotropic materials under plane stress and plane strain assumptions.
Includes single-factorization reuse for symmetric primal and adjoint solves,
and discrete high-resolution stage profiling.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem as fem
from skfem.helpers import sym_grad

from gdec.fem.mesh import GDECMesh


@dataclass
class ConstitutiveTensor:
    E: float
    nu: float
    assumption: str
    thickness: float
    c11: float
    c12: float
    c33: float  # G

    @classmethod
    def from_properties(
        cls, E: float, nu: float, assumption: str = "plane_stress", thickness: float = 1.0
    ) -> ConstitutiveTensor:
        if assumption == "plane_stress":
            c11 = E / (1.0 - nu**2)
            c12 = nu * c11
            c33 = E / (2.0 * (1.0 + nu))
        elif assumption == "plane_strain":
            lam = (E * nu) / ((1.0 + nu) * (1.0 - 2.0 * nu))
            mu = E / (2.0 * (1.0 + nu))
            c11 = lam + 2.0 * mu
            c12 = lam
            c33 = mu
        else:
            raise ValueError(f"Unknown assumption: '{assumption}'")
        return cls(E=E, nu=nu, assumption=assumption, thickness=thickness, c11=c11, c12=c12, c33=c33)

    @property
    def matrix_3x3(self) -> np.ndarray:
        return np.array([
            [self.c11, self.c12, 0.0],
            [self.c12, self.c11, 0.0],
            [0.0, 0.0, self.c33],
        ])

    @property
    def compliance_3x3(self) -> np.ndarray:
        return np.linalg.inv(self.matrix_3x3)


@dataclass
class FEMSolution:
    u: np.ndarray             # primal displacement vector (N_dofs,)
    z: Optional[np.ndarray]   # adjoint displacement vector (N_dofs,)
    K: sp.csr_matrix          # global assembled stiffness matrix
    f: np.ndarray             # global external load vector
    g: np.ndarray             # adjoint load vector (QoI representation)
    dofs_fixed: np.ndarray    # constrained Dirichlet DOF indices
    basis: fem.Basis          # primal finite element basis
    qoi: float                # quantity of interest J(u) in meters
    qoi_mm: float             # quantity of interest in millimeters
    # Discrete profiling timings
    assembly_time_sec: float = 0.0
    condensation_time_sec: float = 0.0
    factorization_time_sec: float = 0.0
    primal_solve_time_sec: float = 0.0
    adjoint_solve_time_sec: float = 0.0
    total_solver_time_sec: float = 0.0
    factorization_reused: bool = True


class LinearElasticitySolver:
    def __init__(self, constitutive: ConstitutiveTensor):
        self.c = constitutive
        self.element = fem.ElementVector(fem.ElementTriP1())

    def create_basis(self, gdec_mesh: GDECMesh) -> fem.Basis:
        return fem.Basis(gdec_mesh.mesh, self.element)

    def assemble_stiffness(self, basis: fem.Basis) -> sp.csr_matrix:
        c11 = self.c.c11
        c12 = self.c.c12
        c33 = self.c.c33
        thickness = self.c.thickness

        @fem.BilinearForm
        def stiffness_form(u, v, w):
            eps_u = sym_grad(u)
            eps_v = sym_grad(v)
            sig_11 = c11 * eps_u[0, 0] + c12 * eps_u[1, 1]
            sig_22 = c12 * eps_u[0, 0] + c11 * eps_u[1, 1]
            sig_12 = 2.0 * c33 * eps_u[0, 1]
            return thickness * (
                sig_11 * eps_v[0, 0] + sig_22 * eps_v[1, 1] + 2.0 * sig_12 * eps_v[0, 1]
            )

        return fem.asm(stiffness_form, basis).tocsr()

    def assemble_traction(
        self, gdec_mesh: GDECMesh, boundary_name: str, tx: float, ty: float
    ) -> np.ndarray:
        facets = gdec_mesh.get_boundary_facets(boundary_name)
        if len(facets) == 0:
            return np.zeros(gdec_mesh.nnodes * 2)

        fbasis = fem.FacetBasis(gdec_mesh.mesh, self.element, facets=facets)
        thickness = self.c.thickness

        @fem.LinearForm
        def traction_form(v, w):
            return thickness * (tx * v[0] + ty * v[1])

        return fem.asm(traction_form, fbasis)

    def assemble_qoi_adjoint_vector(
        self, gdec_mesh: GDECMesh, boundary_name: str = "right", component: str = "y"
    ) -> np.ndarray:
        r"""
        Assemble the discrete representation g of the linear QoI functional:
        J(v) = 1/L_b \int_{Gamma_b} v_component dGamma.
        """
        facets = gdec_mesh.get_boundary_facets(boundary_name)
        if len(facets) == 0:
            return np.zeros(gdec_mesh.nnodes * 2)

        fbasis = fem.FacetBasis(gdec_mesh.mesh, self.element, facets=facets)
        if boundary_name in ["left", "right"]:
            lb = gdec_mesh.height
        else:
            lb = gdec_mesh.width

        comp_idx = 0 if component.lower() == "x" else 1

        @fem.LinearForm
        def qoi_form(v, w):
            return (1.0 / lb) * v[comp_idx]

        return fem.asm(qoi_form, fbasis)

    def assemble_point_qoi_adjoint_vector(
        self, gdec_mesh: GDECMesh, px: float, py: float, component: str = "y"
    ) -> np.ndarray:
        r"""
        Assemble the discrete representation g of the point displacement functional:
        J(v) = v_component(px, py).
        Evaluated via P1 triangular finite element shape functions.
        """
        basis = self.create_basis(gdec_mesh)
        p = gdec_mesh.mesh.p
        t = gdec_mesh.mesh.t
        comp_idx = 0 if component.lower() == "x" else 1

        v0, v1, v2 = t[0, :], t[1, :], t[2, :]
        x1, y1 = p[0, v0], p[1, v0]
        x2, y2 = p[0, v1], p[1, v1]
        x3, y3 = p[0, v2], p[1, v2]

        detT = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        l1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / detT
        l2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / detT
        l3 = 1.0 - l1 - l2

        inside = np.where((l1 >= -1e-10) & (l2 >= -1e-10) & (l3 >= -1e-10))[0]
        if len(inside) == 0:
            raise ValueError(f"Point ({px}, {py}) is outside computational mesh boundaries.")
        elem = inside[0]
        weights = np.maximum(np.array([l1[elem], l2[elem], l3[elem]]), 0.0)
        weights /= np.sum(weights)
        elem_nodes = t[:, elem]

        g = np.zeros(basis.N)
        for i in range(3):
            dof = basis.nodal_dofs[comp_idx, elem_nodes[i]]
            g[dof] += weights[i]
        return g

    def find_dirichlet_dofs(
        self, basis: fem.Basis, gdec_mesh: GDECMesh, boundary_name: str, components: List[str]
    ) -> np.ndarray:
        bnd = boundary_name.lower().strip()
        if bnd == "left":
            pred = lambda x: np.isclose(x[0], 0.0)
        elif bnd == "right":
            pred = lambda x: np.isclose(x[0], gdec_mesh.width)
        elif bnd == "bottom":
            pred = lambda x: np.isclose(x[1], 0.0)
        elif bnd == "top":
            pred = lambda x: np.isclose(x[1], gdec_mesh.height)
        else:
            raise ValueError(f"Unknown boundary: '{boundary_name}'")

        dofs_view = basis.get_dofs(pred)
        res = []
        if "x" in components:
            res.append(dofs_view.nodal["u^1"])
        if "y" in components:
            res.append(dofs_view.nodal["u^2"])
        if not res:
            return np.array([], dtype=int)
        return np.unique(np.concatenate(res))

    def solve(
        self,
        gdec_mesh: GDECMesh,
        loads: List[Tuple[str, float, float]],
        fixed_boundaries: List[Tuple[str, List[str]]],
        objective: Optional[Any] = None,
        qoi_boundary: str = "right",
        qoi_component: str = "y",
        solve_adjoint: bool = True,
        reuse_factorization: bool = True,
    ) -> FEMSolution:
        """
        Solve primal and adjoint systems with discrete stage timings and optional factorization reuse.
        """
        t_total_start = time.perf_counter()

        # Step 1: Assembly
        t0 = time.perf_counter()
        basis = self.create_basis(gdec_mesh)
        K = self.assemble_stiffness(basis)

        # External loads
        f = np.zeros(basis.N)
        for bnd, tx, ty in loads:
            f += self.assemble_traction(gdec_mesh, bnd, tx, ty)

        # QoI adjoint load vector
        obj_type = getattr(objective, "type", None) or getattr(objective, "kind", None)
        if objective is not None and obj_type == "point_displacement":
            if objective.point_x is None or objective.point_y is None:
                raise ValueError("Point displacement objective requires point_x and point_y coordinates.")
            g = self.assemble_point_qoi_adjoint_vector(
                gdec_mesh, objective.point_x, objective.point_y, objective.component
            )
        else:
            bnd = getattr(objective, "boundary", None) or qoi_boundary
            comp = getattr(objective, "component", None) or qoi_component
            g = self.assemble_qoi_adjoint_vector(gdec_mesh, bnd, comp)

        # Dirichlet boundary condition DOFs
        dofs_fixed_list = []
        for bnd, comps in fixed_boundaries:
            dofs = self.find_dirichlet_dofs(basis, gdec_mesh, bnd, comps)
            dofs_fixed_list.append(dofs)
        dofs_fixed = np.unique(np.concatenate(dofs_fixed_list)) if dofs_fixed_list else np.array([], dtype=int)
        t_assembly = time.perf_counter() - t0

        # Step 2: Condensation
        t0 = time.perf_counter()
        K_free, f_free, u_full, I = fem.condense(K, f, D=dofs_fixed)
        t_condensation = time.perf_counter() - t0

        if reuse_factorization:
            # Step 3: Factorize once for symmetric K_free
            t0 = time.perf_counter()
            solve_fac = spla.factorized(K_free.tocsc())
            t_factor = time.perf_counter() - t0

            # Step 4: Primal solve (fast triangular back-solve)
            t0 = time.perf_counter()
            u_free = solve_fac(f_free)
            u = u_full.copy()
            u[I] = u_free
            t_primal = time.perf_counter() - t0

            # Step 5: Adjoint solve (reuses same factor)
            z = None
            t_adjoint = 0.0
            if solve_adjoint:
                t0 = time.perf_counter()
                g_free = g[I]
                z_free = solve_fac(g_free)
                z = np.zeros(basis.N)
                z[I] = z_free
                t_adjoint = time.perf_counter() - t0
        else:
            # Separate solves without factorization reuse
            t0 = time.perf_counter()
            u = fem.solve(K_free, f_free, u_full, I)
            t_primal = time.perf_counter() - t0
            t_factor = 0.0

            z = None
            t_adjoint = 0.0
            if solve_adjoint:
                t0 = time.perf_counter()
                z = fem.solve(*fem.condense(K, g, D=dofs_fixed))
                t_adjoint = time.perf_counter() - t0

        qoi = float(g @ u)
        qoi_mm = qoi * 1000.0
        t_total = time.perf_counter() - t_total_start

        return FEMSolution(
            u=u,
            z=z,
            K=K,
            f=f,
            g=g,
            dofs_fixed=dofs_fixed,
            basis=basis,
            qoi=qoi,
            qoi_mm=qoi_mm,
            assembly_time_sec=t_assembly,
            condensation_time_sec=t_condensation,
            factorization_time_sec=t_factor,
            primal_solve_time_sec=t_primal,
            adjoint_solve_time_sec=t_adjoint,
            total_solver_time_sec=t_total,
            factorization_reused=reuse_factorization,
        )

    def check_reactions_equilibrium(
        self, sol: FEMSolution
    ) -> Tuple[np.ndarray, float, float]:
        """
        Calculate reaction forces R = K u - f on fixed DOFs and check static equilibrium:
        Returns: (R_total_vector, sum_Rx, sum_Ry + applied_Fy)
        """
        R = sol.K @ sol.u - sol.f
        Rx_total = np.sum(R[0::2])
        Ry_total = np.sum(R[1::2])
        Fx_applied = np.sum(sol.f[0::2])
        Fy_applied = np.sum(sol.f[1::2])
        bal_x = Rx_total + Fx_applied
        bal_y = Ry_total + Fy_applied
        return R, float(bal_x), float(bal_y)
