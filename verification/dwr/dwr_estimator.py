"""
Experimental Enriched-Dual Weighted Residual (DWR) Estimator.
Implements mathematically consistent DWR error estimation for 2D linear elasticity:
- Enriched adjoint space: quadratic Lagrange elements P2 on the triangulation T_h
- Exact weak residual evaluation: R(u_h)(psi) = l(psi) - a(u_h, psi)
- Enriched adjoint fluctuation: psi = z^+ - I_h z^+ (with zero values at vertices)
- Element-level indicators eta_K for adaptive mesh marking
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1, ElementTriP2, FacetBasis

from verification.dwr.geometries import ProblemDefinition


@dataclass
class DWREstimateResult:
    eta_dwr: float                  # Global signed DWR error estimate
    abs_eta_dwr: float              # Absolute DWR error estimate |eta_dwr|
    element_indicators: np.ndarray  # Per-element local error indicators for marking
    qoi_h: float                    # Primal QoI value J(u_h)
    u_h: np.ndarray                 # P1 primal solution vector
    z_enriched: np.ndarray          # P2 enriched adjoint solution vector
    dofs_p1: int                    # Number of primal DOFs
    dofs_p2: int                    # Number of enriched adjoint DOFs
    timings: Dict[str, float]       # Fine-grained breakdown: assemble, solve_primal, solve_adjoint, estimator


class DWREstimator:
    def __init__(self, problem: ProblemDefinition):
        self.problem = problem
        self.c = problem.material

    def _build_prolongation(self, b1: Basis, b2: Basis, mesh: fem.MeshTri) -> sp.csr_matrix:
        """Construct prolongation operator P: V_P1 -> V_P2."""
        rows, cols, vals = [], [], []
        # Vertex DOFs are identical (1:1 mapping)
        for i in range(b1.N):
            rows.append(i)
            cols.append(i)
            vals.append(1.0)
        # Facet midpoint DOFs are linear average of endpoint vertices
        for k in range(mesh.facets.shape[1]):
            n1, n2 = mesh.facets[0, k], mesh.facets[1, k]
            rows.extend([b2.facet_dofs[0, k], b2.facet_dofs[0, k]])
            cols.extend([2 * n1, 2 * n2])
            vals.extend([0.5, 0.5])

            rows.extend([b2.facet_dofs[1, k], b2.facet_dofs[1, k]])
            cols.extend([2 * n1 + 1, 2 * n2 + 1])
            vals.extend([0.5, 0.5])

        return sp.csr_matrix((vals, (rows, cols)), shape=(b2.N, b1.N))

    def _assemble_stiffness(self, basis: Basis) -> sp.csr_matrix:
        c = self.c
        thickness = c.thickness

        @fem.BilinearForm
        def a_form(u, v, w):
            from skfem.helpers import sym_grad
            eps_u = sym_grad(u)
            eps_v = sym_grad(v)
            sig_11 = c.c11 * eps_u[0, 0] + c.c12 * eps_u[1, 1]
            sig_22 = c.c12 * eps_u[0, 0] + c.c11 * eps_u[1, 1]
            sig_12 = 2.0 * c.c33 * eps_u[0, 1]
            return thickness * (
                sig_11 * eps_v[0, 0] + sig_22 * eps_v[1, 1] + 2.0 * sig_12 * eps_v[0, 1]
            )

        return fem.asm(a_form, basis).tocsr()

    def _get_p2_dirichlet_dofs(self, mesh: fem.MeshTri, b1: Basis, b2: Basis, D1: np.ndarray) -> np.ndarray:
        """Find P2 Dirichlet DOFs by including facet midpoints on Dirichlet boundary segments."""
        dofs = list(D1)
        # Find which nodes in mesh are constrained
        # Nodal DOFs in P1: node n has DOFs 2*n, 2*n+1
        constrained_nodes_x = set(D1[D1 % 2 == 0] // 2)
        constrained_nodes_y = set(D1[D1 % 2 == 1] // 2)

        for k in range(mesh.facets.shape[1]):
            n1, n2 = mesh.facets[0, k], mesh.facets[1, k]
            if n1 in constrained_nodes_x and n2 in constrained_nodes_x:
                dofs.append(b2.facet_dofs[0, k])
            if n1 in constrained_nodes_y and n2 in constrained_nodes_y:
                dofs.append(b2.facet_dofs[1, k])

        return np.unique(np.array(dofs, dtype=int))

    def estimate(self, mesh: fem.MeshTri) -> DWREstimateResult:
        timings: Dict[str, float] = {}

        t0 = time.perf_counter()
        b1 = Basis(mesh, ElementVector(ElementTriP1()))
        b2 = Basis(mesh, ElementVector(ElementTriP2()))

        K1 = self._assemble_stiffness(b1)
        K2 = self._assemble_stiffness(b2)
        f1 = self.problem.assemble_traction(b1)
        f2 = self.problem.assemble_traction(b2)
        g1 = self.problem.assemble_qoi_vector(b1)
        g2 = self.problem.assemble_qoi_vector(b2)

        P = self._build_prolongation(b1, b2, mesh)
        D1 = self.problem.get_dirichlet_dofs(b1)
        I1 = np.setdiff1d(np.arange(b1.N), D1)
        D2 = self._get_p2_dirichlet_dofs(mesh, b1, b2, D1)
        I2 = np.setdiff1d(np.arange(b2.N), D2)
        timings["assemble"] = time.perf_counter() - t0

        # Solve primal P1
        t1 = time.perf_counter()
        K1_c, f1_c, u1_full, _ = fem.condense(K1, f1, D=D1)
        u1 = u1_full.copy()
        u1[I1] = spla.spsolve(K1_c.tocsc(), f1_c)
        timings["solve_primal"] = time.perf_counter() - t1

        # Solve enriched adjoint on P2
        t2 = time.perf_counter()
        K2_adj, g2_c, z2_full, _ = fem.condense(K2, g2, D=D2)
        z2 = z2_full.copy()
        z2[I2] = spla.spsolve(K2_adj.tocsc(), g2_c)
        timings["solve_adjoint"] = time.perf_counter() - t2

        # Compute DWR residual and indicators
        t3 = time.perf_counter()
        u1_p2 = P @ u1
        res2 = f2 - K2 @ u1_p2

        # Adjoint fluctuation: psi = z2 - I_h z2
        z1_interp = z2[:b1.N]
        psi = z2 - P @ z1_interp

        # Global DWR estimate
        eta_dwr = float(psi @ res2)

        # Elemental DWR indicators
        c = self.c
        thickness = c.thickness

        @fem.Functional
        def energy_elem(w):
            from skfem.helpers import sym_grad
            eps_u = sym_grad(w["u"])
            eps_psi = sym_grad(w["psi"])
            sig_11 = c.c11 * eps_u[0, 0] + c.c12 * eps_u[1, 1]
            sig_22 = c.c12 * eps_u[0, 0] + c.c11 * eps_u[1, 1]
            sig_12 = 2.0 * c.c33 * eps_u[0, 1]
            return thickness * (
                sig_11 * eps_psi[0, 0] + sig_22 * eps_psi[1, 1] + 2.0 * sig_12 * eps_psi[0, 1]
            )

        u_eval = b2.interpolate(u1_p2)
        psi_eval = b2.interpolate(psi)
        a_elem = energy_elem.elemental(b2, u=u_eval, psi=psi_eval)

        # External traction elemental contribution
        tr_elem = np.zeros(mesh.nelements)
        # Check if right boundary has traction
        # Problem-specific traction facets
        if self.problem.id in ["cantilever", "plate_with_hole"]:
            tr_facets = np.where(
                np.isclose(mesh.p[0, mesh.facets[0]], 2.0) & np.isclose(mesh.p[0, mesh.facets[1]], 2.0)
            )[0]
            if len(tr_facets) > 0:
                fb = FacetBasis(mesh, b2.elem, facets=tr_facets)
                if self.problem.id == "cantilever":
                    @fem.Functional
                    def tr_fn(w):
                        return thickness * (-1e6 * w["psi"].value[1])
                else: # plate_with_hole
                    @fem.Functional
                    def tr_fn(w):
                        return thickness * (1e7 * w["psi"].value[0])
                tr_vals = tr_fn.elemental(fb, psi=fb.interpolate(psi))
                for e_idx, tr_val in zip(fb.tind, tr_vals):
                    tr_elem[e_idx] += tr_val

        elif self.problem.id == "notched_bar":
            tr_facets = np.where(
                np.isclose(mesh.p[1, mesh.facets[0]], 0.8) & np.isclose(mesh.p[1, mesh.facets[1]], 0.8)
            )[0]
            if len(tr_facets) > 0:
                fb = FacetBasis(mesh, b2.elem, facets=tr_facets)
                @fem.Functional
                def tr_fn(w):
                    return thickness * (1.5e7 * w["psi"].value[1])
                tr_vals = tr_fn.elemental(fb, psi=fb.interpolate(psi))
                for e_idx, tr_val in zip(fb.tind, tr_vals):
                    tr_elem[e_idx] += tr_val

        elif self.problem.id == "l_shaped":
            tr_facets = np.where(
                np.isclose(mesh.p[0, mesh.facets[0]], 1.0)
                & np.isclose(mesh.p[0, mesh.facets[1]], 1.0)
                & (mesh.p[1, mesh.facets[0]] <= 0.5 + 1e-6)
                & (mesh.p[1, mesh.facets[1]] <= 0.5 + 1e-6)
            )[0]
            if len(tr_facets) > 0:
                fb = FacetBasis(mesh, b2.elem, facets=tr_facets)
                @fem.Functional
                def tr_fn(w):
                    return thickness * (-5e6 * w["psi"].value[1])
                tr_vals = tr_fn.elemental(fb, psi=fb.interpolate(psi))
                for e_idx, tr_val in zip(fb.tind, tr_vals):
                    tr_elem[e_idx] += tr_val

        # Local element indicator: | l_K(psi) - a_K(u_h, psi) |
        element_indicators = np.abs(tr_elem - a_elem)
        timings["estimator"] = time.perf_counter() - t3

        qoi_val = float(g1 @ u1)

        return DWREstimateResult(
            eta_dwr=eta_dwr,
            abs_eta_dwr=abs(eta_dwr),
            element_indicators=element_indicators,
            qoi_h=qoi_val,
            u_h=u1,
            z_enriched=z2,
            dofs_p1=b1.N,
            dofs_p2=b2.N,
            timings=timings,
        )
