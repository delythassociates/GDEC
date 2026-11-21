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


class SolverConvergenceError(RuntimeError):
    """Raised when an iterative linear solver fails to converge to the required tolerance."""
    def __init__(self, message: str, result: Optional[Any] = None, system: str = "primal"):
        super().__init__(message)
        self.result = result
        self.system = system


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
    preconditioner_setup_time_sec: float = 0.0
    primal_solve_time_sec: float = 0.0
    adjoint_solve_time_sec: float = 0.0
    total_solver_time_sec: float = 0.0
    factorization_reused: bool = True
    solver_backend: str = "direct"
    converged: bool = True
    primal_converged: bool = True
    adjoint_converged: bool = True
    primal_iterations: int = 0
    adjoint_iterations: int = 0
    primal_relative_residual: float = 0.0
    adjoint_relative_residual: float = 0.0
    termination_reason: Optional[str] = None


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
        self, gdec_mesh: GDECMesh, boundary_name: str, tx: Any, ty: Any
    ) -> np.ndarray:
        facets = gdec_mesh.get_boundary_facets(boundary_name)
        if len(facets) == 0:
            return np.zeros(gdec_mesh.nnodes * 2)

        fbasis = fem.FacetBasis(gdec_mesh.mesh, self.element, facets=facets)
        thickness = self.c.thickness

        @fem.LinearForm
        def traction_form(v, w):
            if callable(tx):
                val_x = tx(w.x)
                val_y = ty(w.x)
            else:
                val_x = tx
                val_y = ty
            return thickness * (val_x * v[0] + val_y * v[1])

        return fem.asm(traction_form, fbasis)

    def assemble_body_force(
        self, basis: fem.Basis, body_force_fn: Any
    ) -> np.ndarray:
        r"""
        Assemble external body force vector:
          f_b = \int_\Omega t (b_x v_x + b_y v_y) d\Omega.
        Supports constant vectors (bx, by) or general callables for solver use.
        """
        thickness = self.c.thickness

        if isinstance(body_force_fn, (tuple, list, np.ndarray)) and not callable(body_force_fn):
            b_arr = np.asarray(body_force_fn, dtype=float)
            if b_arr.shape != (2,):
                raise ValueError(f"Body force must be a 2-component vector (bx, by), got shape {b_arr.shape}.")
            bx, by = float(b_arr[0]), float(b_arr[1])
            if not (np.isfinite(bx) and np.isfinite(by)):
                raise ValueError(f"Body force components must be finite numeric values, got ({bx}, {by}).")
            @fem.LinearForm
            def body_force_form(v, w):
                return thickness * (bx * v[0] + by * v[1])
        else:
            @fem.LinearForm
            def body_force_form(v, w):
                b_val = body_force_fn(w.x)
                bx, by = b_val[0], b_val[1]
                return thickness * (bx * v[0] + by * v[1])

        return fem.asm(body_force_form, basis)

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
        body_force_fn: Optional[Any] = None,
        qoi_boundary: str = "right",
        qoi_component: str = "y",
        solve_adjoint: bool = True,
        reuse_factorization: bool = True,
        solver_type: str = "direct",
        solver_rtol: float = 1e-8,
        solver_atol: float = 1e-12,
        solver_max_iter: Optional[int] = None,
        raise_on_nonconvergence: bool = True,
        caller_certified_spd: bool = True,
    ) -> FEMSolution:
        """
        Solve primal and adjoint systems with discrete stage timings and optional factorization reuse.
        Supports direct sparse solver (production default) and experimental Krylov solvers.
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
        if body_force_fn is not None:
            f += self.assemble_body_force(basis, body_force_fn)

        # QoI adjoint load vector
        g = self.assemble_qoi_adjoint_vector(gdec_mesh, qoi_boundary, qoi_component)

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

        primal_iters = 0
        adjoint_iters = 0
        primal_rel_res = 0.0
        adjoint_rel_res = 0.0
        primal_conv = True
        adjoint_conv = True
        term_reason: Optional[str] = None
        t_precond_setup = 0.0

        if solver_type == "direct":
            if reuse_factorization:
                # Step 3: Factorize once for symmetric K_free
                t0 = time.perf_counter()
                solve_fac = spla.factorized(K_free.tocsc())
                t_factor = time.perf_counter() - t0
                actual_fac_reused = True

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
                actual_fac_reused = False

                z = None
                t_adjoint = 0.0
                if solve_adjoint:
                    t0 = time.perf_counter()
                    z = fem.solve(*fem.condense(K, g, D=dofs_fixed))
                    t_adjoint = time.perf_counter() - t0

            term_reason = "direct_solve_success"
            # Compute direct relative residual
            f_norm = float(np.linalg.norm(f_free))
            res_dir = f_free - K_free.dot(u[I])
            primal_rel_res = float(np.linalg.norm(res_dir)) / max(f_norm, 1e-15)
            if solve_adjoint and z is not None:
                g_norm = float(np.linalg.norm(g[I]))
                res_adj_dir = g[I] - K_free.dot(z[I])
                adjoint_rel_res = float(np.linalg.norm(res_adj_dir)) / max(g_norm, 1e-15)
        else:
            # Experimental iterative Krylov solver
            from gdec.fem.solvers.iterative import (
                ConjugateGradientSolver,
                IdentityPreconditioner,
                JacobiPreconditioner,
                IncompleteCholeskyPreconditioner,
                AMGPreconditioner,
            )

            actual_fac_reused = False  # Iterative solvers never reuse direct factorization
            t_factor = 0.0

            t0 = time.perf_counter()
            if solver_type in ["cg", "identity"]:
                prec = IdentityPreconditioner()
            elif solver_type in ["pcg_jacobi", "jacobi"]:
                prec = JacobiPreconditioner(K_free)
            elif solver_type in ["pcg_ic0", "ic0"]:
                prec = IncompleteCholeskyPreconditioner(K_free)
            elif solver_type in ["pcg_amg", "amg"]:
                prec = AMGPreconditioner(K_free)
            else:
                raise ValueError(
                    f"Unknown solver_type: '{solver_type}'. "
                    "Supported: 'direct', 'cg', 'pcg_jacobi', 'pcg_ic0', 'pcg_amg'."
                )
            t_precond_setup = time.perf_counter() - t0

            cg = ConjugateGradientSolver(default_rtol=solver_rtol, default_atol=solver_atol)
            res_primal = cg.solve(
                K_free,
                f_free,
                preconditioner=prec,
                max_iter=solver_max_iter,
                caller_certified_spd=caller_certified_spd,
            )
            primal_conv = res_primal.converged
            primal_rel_res = res_primal.relative_residual
            primal_iters = res_primal.iterations
            t_primal = res_primal.time_sec

            if not primal_conv:
                term_reason = f"primal_failed: {res_primal.breakdown_reason or 'max_iter_exhausted'}"
                if raise_on_nonconvergence:
                    raise SolverConvergenceError(
                        f"Primal linear solve failed to converge: {res_primal.breakdown_reason or 'max iterations reached'}",
                        result=res_primal,
                        system="primal",
                    )
            else:
                term_reason = "primal_converged"

            u = u_full.copy()
            u[I] = res_primal.x

            z = None
            t_adjoint = 0.0
            if solve_adjoint:
                g_free = g[I]
                res_adj = cg.solve(
                    K_free,
                    g_free,
                    preconditioner=prec,
                    max_iter=solver_max_iter,
                    caller_certified_spd=caller_certified_spd,
                )
                adjoint_conv = res_adj.converged
                adjoint_rel_res = res_adj.relative_residual
                adjoint_iters = res_adj.iterations
                t_adjoint = res_adj.time_sec

                if not adjoint_conv:
                    term_reason = f"adjoint_failed: {res_adj.breakdown_reason or 'max_iter_exhausted'}"
                    if raise_on_nonconvergence:
                        raise SolverConvergenceError(
                            f"Adjoint linear solve failed to converge: {res_adj.breakdown_reason or 'max iterations reached'}",
                            result=res_adj,
                            system="adjoint",
                        )
                else:
                    if primal_conv:
                        term_reason = "primal_and_adjoint_converged"

                z = np.zeros(basis.N)
                z[I] = res_adj.x

        qoi = float(g @ u)
        qoi_mm = qoi * 1000.0
        t_total = time.perf_counter() - t_total_start
        overall_converged = primal_conv and (adjoint_conv if solve_adjoint else True)

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
            preconditioner_setup_time_sec=t_precond_setup,
            primal_solve_time_sec=t_primal,
            adjoint_solve_time_sec=t_adjoint,
            total_solver_time_sec=t_total,
            factorization_reused=actual_fac_reused,
            solver_backend=solver_type,
            converged=overall_converged,
            primal_converged=primal_conv,
            adjoint_converged=adjoint_conv,
            primal_iterations=primal_iters,
            adjoint_iterations=adjoint_iters,
            primal_relative_residual=primal_rel_res,
            adjoint_relative_residual=adjoint_rel_res,
            termination_reason=term_reason,
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
