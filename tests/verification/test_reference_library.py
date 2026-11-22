"""
Comprehensive verification tests for the eight traceable reference problems in GDEC.
Tests each reference problem against exact analytical closed-form solutions,
manufactured solutions, or peer-reviewed asymptotic benchmarks.
"""
from __future__ import annotations

import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.spatial import Delaunay
import pytest
import skfem
from skfem.models.elasticity import linear_elasticity, plane_stress, lame_parameters
from skfem.helpers import dot

from gdec.verification.reference_problems import (
    get_reference_problem,
    list_reference_problems,
    lame_cylinder_analytical_plane_stress,
    lame_cylinder_analytical_plane_strain,
    kirsch_plate_hole_analytical,
)


class TestReferenceProblemLibrary:
    """Automated numerical verification of GDEC's 8 traceable reference problems."""

    def test_reference_catalog_integrity(self):
        """Verify all 8 reference problems exist and have complete documentation."""
        problems = list_reference_problems()
        assert len(problems) == 8
        for p in problems:
            assert p.problem_id.startswith("REF-")
            assert len(p.name) > 0
            assert len(p.source_reference) > 0
            assert len(p.governing_equations) > 0
            assert len(p.boundary_conditions) > 0
            assert len(p.expected_tolerance) > 0

    def test_ref_01_constant_strain_patch_test(self):
        """REF-01: Constant-strain patch test on intentionally distorted mesh."""
        spec = get_reference_problem("REF-01-PATCH-TEST")
        # Intentionally distorted patch on [0, 1]^2 with interior nodes
        p = np.array([
            [0.0, 1.0, 1.0, 0.0, 0.45, 0.70],
            [0.0, 0.0, 1.0, 1.0, 0.35, 0.65],
        ])
        delaunay = Delaunay(p.T)
        t = delaunay.simplices.T

        mesh = skfem.MeshTri(p, t)
        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)

        E, nu = 210.0e9, 0.3
        c1, c2, c0 = 0.001, 0.002, 0.0005
        d1, d2, d0 = -0.0015, 0.0008, -0.0002

        def exact_u(x, y):
            return c1 * x + c2 * y + c0

        def exact_v(x, y):
            return d1 * x + d2 * y + d0

        # Boundary nodes (all nodes on outer boundary)
        boundary_nodes = mesh.boundary_nodes()
        D_dofs = np.concatenate([basis.nodal_dofs[0, boundary_nodes], basis.nodal_dofs[1, boundary_nodes]])

        # Prescribe exact displacement on all boundary nodes
        u_exact_all = np.zeros(basis.N)
        u_exact_all[basis.nodal_dofs[0]] = exact_u(mesh.p[0], mesh.p[1])
        u_exact_all[basis.nodal_dofs[1]] = exact_v(mesh.p[0], mesh.p[1])

        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)
        f = np.zeros(basis.N)

        u_sol = skfem.solve(*skfem.condense(K, f, x=u_exact_all, D=D_dofs))

        interior_nodes = np.setdiff1d(np.arange(mesh.nvertices), boundary_nodes)
        for node in interior_nodes:
            x, y = mesh.p[0, node], mesh.p[1, node]
            u_num = u_sol[basis.nodal_dofs[0, node]]
            v_num = u_sol[basis.nodal_dofs[1, node]]
            u_ex = exact_u(x, y)
            v_ex = exact_v(x, y)
            assert abs(u_num - u_ex) < 1e-11, f"REF-01 u error on node {node}: {abs(u_num - u_ex)}"
            assert abs(v_num - v_ex) < 1e-11, f"REF-01 v error on node {node}: {abs(v_num - v_ex)}"

    def test_ref_02_uniaxial_tension_bar(self):
        """REF-02: Uniform uniaxial tension bar with Poisson lateral contraction."""
        spec = get_reference_problem("REF-02-UNIAXIAL-TENSION")
        L, H = 4.0, 1.0
        nx, ny = 16, 4
        mesh = skfem.MeshTri.init_tensor(np.linspace(0, L, nx + 1), np.linspace(0, H, ny + 1))
        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)

        E, nu, sigma_0 = 100.0e9, 0.25, 10.0e6
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

        # Left boundary (x = 0): roller u = 0; pin center node (v = 0)
        left_nodes = np.where(np.isclose(mesh.p[0], 0.0))[0]
        center_left_node = left_nodes[np.argmin(np.abs(mesh.p[1, left_nodes] - H / 2.0))]
        D_dofs = np.concatenate([basis.nodal_dofs[0, left_nodes], [basis.nodal_dofs[1, center_left_node]]])

        # Right boundary (x = L): apply traction sigma_0
        right_facets = mesh.facets_satisfying(lambda x: np.isclose(x[0], L))
        facet_basis = skfem.FacetBasis(mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=right_facets)

        @skfem.LinearForm
        def traction_form(v, w):
            return sigma_0 * v[0]

        f = skfem.asm(traction_form, facet_basis)
        u_sol = skfem.solve(*skfem.condense(K, f, D=D_dofs))

        # Analytical check: u(L) = sigma_0 * L / E
        expected_u_tip = sigma_0 * L / E
        right_nodes = np.where(np.isclose(mesh.p[0], L))[0]
        actual_u_tip = np.mean(u_sol[basis.nodal_dofs[0, right_nodes]])
        rel_diff = abs(actual_u_tip - expected_u_tip) / expected_u_tip
        assert rel_diff < 1e-10, f"REF-02 u_tip discrepancy: {rel_diff}"

        # Analytical check: v(top) - v(bottom) = -nu * sigma_0 * H / E
        top_nodes = np.where(np.isclose(mesh.p[1], H))[0]
        bottom_nodes = np.where(np.isclose(mesh.p[1], 0.0))[0]
        expected_delta_v = -nu * sigma_0 * H / E
        actual_delta_v = np.mean(u_sol[basis.nodal_dofs[1, top_nodes]]) - np.mean(u_sol[basis.nodal_dofs[1, bottom_nodes]])
        assert abs(actual_delta_v - expected_delta_v) / abs(expected_delta_v) < 1e-10

    def test_ref_03_timoshenko_cantilever(self):
        """REF-03: Timoshenko slender cantilever beam deflection comparison."""
        spec = get_reference_problem("REF-03-TIMOSHENKO-CANTILEVER")
        L, c = 4.0, 0.5  # depth D = 2c = 1.0 m
        E, nu, P = 70.0e9, 0.33, 1000.0
        I = (2 * c) ** 3 / 12.0
        A_area = 2 * c * 1.0

        # Exact Timoshenko tip deflection formula
        bending_part = -(P * L**3) / (3.0 * E * I)
        shear_part = -(P * L * (4.0 + 5.0 * nu)) / (2.0 * E * A_area * (1.0 + nu))
        v_timoshenko = bending_part + shear_part

        # Numerical solve on coarse and fine meshes
        def solve_beam(nx, ny):
            m = skfem.MeshTri.init_tensor(np.linspace(0, L, nx + 1), np.linspace(-c, c, ny + 1))
            b = skfem.Basis(m, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            K_mat = skfem.asm(linear_elasticity(*plane_stress(E, nu)), b)

            # Left boundary (x = 0): clamped kinematic root
            left_nodes = np.where(np.isclose(m.p[0], 0.0))[0]
            D = np.concatenate([b.nodal_dofs[0, left_nodes], b.nodal_dofs[1, left_nodes]])

            # Right boundary (x = L): parabolic shear load
            right_facets = m.facets_satisfying(lambda x: np.isclose(x[0], L))
            fb = skfem.FacetBasis(m, skfem.ElementVector(skfem.ElementTriP1()), facets=right_facets)

            @skfem.LinearForm
            def shear_form(v, w):
                y = w.x[1]
                tau = -(3.0 * P / (4.0 * c)) * (1.0 - (y / c)**2)
                return tau * v[1]

            f_vec = skfem.asm(shear_form, fb)
            u = skfem.solve(*skfem.condense(K_mat, f_vec, D=D))
            right_nodes = np.where(np.isclose(m.p[0], L))[0]
            center_tip = right_nodes[np.argmin(np.abs(m.p[1, right_nodes]))]
            return u[b.nodal_dofs[1, center_tip]]

        v_coarse = solve_beam(16, 4)
        v_fine = solve_beam(32, 8)

        # Monotonic convergence from below (for displacement-based P1 FEM)
        assert abs(v_fine) > abs(v_coarse)
        # Discrepancy vs Timoshenko within 10% on 32x8 mesh (asymptotically converging to beam theory)
        assert abs(v_fine - v_timoshenko) / abs(v_timoshenko) < 0.10

    def test_ref_04_manufactured_pure_bending(self):
        """REF-04: Manufactured solution for pure bending with exact displacement representation."""
        spec = get_reference_problem("REF-04-PURE-BENDING-MANUFACTURED")
        L, H = 2.0, 1.0
        E, nu, M = 100.0e9, 0.25, 5000.0
        I = (H**3) / 12.0

        def u_exact(x, y):
            return -(M / (E * I)) * x * y

        def v_exact(x, y):
            return (M / (2.0 * E * I)) * (x**2 + nu * y**2)

        mesh = skfem.MeshTri.init_tensor(np.linspace(0, L, 9), np.linspace(-H/2, H/2, 5))
        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

        # Prescribe exact Dirichlet values on all boundary nodes
        boundary_nodes = mesh.boundary_nodes()
        D = np.concatenate([basis.nodal_dofs[0, boundary_nodes], basis.nodal_dofs[1, boundary_nodes]])

        u_dir = np.zeros(basis.N)
        u_dir[basis.nodal_dofs[0]] = u_exact(mesh.p[0], mesh.p[1])
        u_dir[basis.nodal_dofs[1]] = v_exact(mesh.p[0], mesh.p[1])

        f = np.zeros(basis.N)
        u_sol = skfem.solve(*skfem.condense(K, f, x=u_dir, D=D))

        # Verify max nodal error is tightly bounded to machine precision
        diff_u = u_sol[basis.nodal_dofs[0]] - u_exact(mesh.p[0], mesh.p[1])
        diff_v = u_sol[basis.nodal_dofs[1]] - v_exact(mesh.p[0], mesh.p[1])
        max_err = max(np.max(np.abs(diff_u)), np.max(np.abs(diff_v)))
        assert max_err < 1e-10, f"REF-04 max error: {max_err}"

    def test_ref_05_lame_cylinder_plane_stress(self):
        """REF-05: Lame thick cylinder quadrant under plane stress with full displacement and stress profiles."""
        spec = get_reference_problem("REF-05-LAME-CYLINDER")
        a, b = 1.0, 2.0
        P_int = 10.0e6
        E, nu = 200.0e9, 0.3

        errors_u = []
        errors_srr = []
        errors_stt = []
        hs = []
        for nr, ntheta in [(8, 12), (16, 24), (32, 48)]:
            h = (b - a) / nr
            r_vals = np.linspace(a, b, nr + 1)
            th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
            grid_mesh = skfem.MeshTri.init_tensor(r_vals, th_vals)
            x_coords = grid_mesh.p[0] * np.cos(grid_mesh.p[1])
            y_coords = grid_mesh.p[0] * np.sin(grid_mesh.p[1])
            cyl_mesh = skfem.MeshTri(np.vstack([x_coords, y_coords]), grid_mesh.t)

            basis = skfem.Basis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

            bottom_nodes = np.where(np.isclose(cyl_mesh.p[1], 0.0))[0]
            left_nodes = np.where(np.isclose(cyl_mesh.p[0], 0.0))[0]
            D = np.unique(np.concatenate([basis.nodal_dofs[1, bottom_nodes], basis.nodal_dofs[0, left_nodes]]))

            inner_facets = cyl_mesh.facets_satisfying(lambda x: np.isclose(np.sqrt(x[0]**2 + x[1]**2), a, atol=0.01))
            fb_inner = skfem.FacetBasis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=inner_facets)

            @skfem.LinearForm
            def pressure_form(v, w):
                return -P_int * (v[0] * w.n[0] + v[1] * w.n[1])

            f = skfem.asm(pressure_form, fb_inner)
            u_sol = skfem.solve(*skfem.condense(K, f, D=D))

            # Displacements at element centroids
            pts = cyl_mesh.p[:, cyl_mesh.t]
            elem_areas = 0.5 * np.abs((pts[0, 1] - pts[0, 0]) * (pts[1, 2] - pts[1, 0]) - (pts[0, 2] - pts[0, 0]) * (pts[1, 1] - pts[1, 0]))
            xc = np.mean(pts[0], axis=0)
            yc = np.mean(pts[1], axis=0)
            rc = np.sqrt(xc**2 + yc**2)
            thc = np.arctan2(yc, xc)

            scalar_basis = skfem.Basis(cyl_mesh, skfem.ElementTriP1())
            dofs_u = u_sol[basis.nodal_dofs[0]]
            dofs_v = u_sol[basis.nodal_dofs[1]]
            u_c = np.mean(dofs_u[cyl_mesh.t], axis=0)
            v_c = np.mean(dofs_v[cyl_mesh.t], axis=0)
            ur_c = u_c * np.cos(thc) + v_c * np.sin(thc)

            # Element Cauchy stresses
            grad_u = scalar_basis.interpolate(dofs_u).grad
            grad_v = scalar_basis.interpolate(dofs_v).grad
            eps_xx = grad_u[0, :, 0]
            eps_yy = grad_v[1, :, 0]
            gamma_xy = grad_u[1, :, 0] + grad_v[0, :, 0]

            s_xx = (E / (1.0 - nu**2)) * (eps_xx + nu * eps_yy)
            s_yy = (E / (1.0 - nu**2)) * (eps_yy + nu * eps_xx)
            t_xy = (E / (2.0 * (1.0 + nu))) * gamma_xy

            # Polar stress transformation at element centroids
            cos_t = np.cos(thc)
            sin_t = np.sin(thc)
            s_rr = s_xx * cos_t**2 + s_yy * sin_t**2 + 2.0 * t_xy * sin_t * cos_t
            s_tt = s_xx * sin_t**2 + s_yy * cos_t**2 - 2.0 * t_xy * sin_t * cos_t

            # Full radial profile comparison against authoritative closed form
            exact = lame_cylinder_analytical_plane_stress(rc, a, b, P_int, E, nu)
            w = elem_areas / np.sum(elem_areas)
            ur_err = float(np.sqrt(np.sum(w * (ur_c - exact["u_r"])**2)) / np.sqrt(np.sum(w * exact["u_r"]**2)))
            srr_err = float(np.sqrt(np.sum(w * (s_rr - exact["sigma_rr"])**2)) / np.sqrt(np.sum(w * exact["sigma_rr"]**2)))
            stt_err = float(np.sqrt(np.sum(w * (s_tt - exact["sigma_tt"])**2)) / np.sqrt(np.sum(w * exact["sigma_tt"]**2)))

            errors_u.append(ur_err)
            errors_srr.append(srr_err)
            errors_stt.append(stt_err)
            hs.append(h)

        # Nodal max relative error on fine mesh
        r_nodes = np.sqrt(cyl_mesh.p[0]**2 + cyl_mesh.p[1]**2)
        ur_nodes = np.sqrt(u_sol[basis.nodal_dofs[0]]**2 + u_sol[basis.nodal_dofs[1]]**2)
        exact_nodes = lame_cylinder_analytical_plane_stress(r_nodes, a, b, P_int, E, nu)
        max_rel_nodal_err = float(np.max(np.abs(ur_nodes - exact_nodes["u_r"]) / exact_nodes["u_r"]))

        # 1. Monotonic error reduction for displacements and stresses under uniform refinement
        assert errors_u[1] < errors_u[0] and errors_u[2] < errors_u[1], f"Displacement error not strictly decreasing: {errors_u}"
        assert errors_srr[1] < errors_srr[0] and errors_srr[2] < errors_srr[1], f"Radial stress error not strictly decreasing: {errors_srr}"
        assert errors_stt[1] < errors_stt[0] and errors_stt[2] < errors_stt[1], f"Hoop stress error not strictly decreasing: {errors_stt}"

        # 2. Observed convergence orders (p_u ~ 2.0 in L2, p_sigma ~ 1.0 in L2)
        p_u = float(np.polyfit(np.log(hs), np.log(errors_u), 1)[0])
        p_srr = float(np.polyfit(np.log(hs), np.log(errors_srr), 1)[0])
        p_stt = float(np.polyfit(np.log(hs), np.log(errors_stt), 1)[0])
        assert 1.85 <= p_u <= 2.15, f"Observed displacement order {p_u:.3f} outside [1.85, 2.15]"
        assert 0.85 <= p_srr <= 1.15, f"Observed radial stress order {p_srr:.3f} outside [0.85, 1.15]"
        assert 0.85 <= p_stt <= 1.15, f"Observed hoop stress order {p_stt:.3f} outside [0.85, 1.15]"

        # 3. Fine mesh tolerances
        assert errors_u[-1] < 0.0010, f"Fine mesh displacement L2 error {errors_u[-1]:.4%} exceeds 0.10%"
        assert max_rel_nodal_err < 0.0035, f"Max nodal error {max_rel_nodal_err:.4%} exceeds 0.35%"
        assert errors_srr[-1] < 0.040, f"Fine mesh radial stress error {errors_srr[-1]:.4%} exceeds 4.0%"
        assert errors_stt[-1] < 0.020, f"Fine mesh hoop stress error {errors_stt[-1]:.4%} exceeds 2.0%"

    def test_ref_05_lame_cylinder_plane_strain(self):
        """REF-05: Lame thick cylinder quadrant under plane strain with full displacement and 3D stress profiles."""
        spec = get_reference_problem("REF-05-LAME-CYLINDER")
        a, b = 1.0, 2.0
        P_int = 10.0e6
        E, nu = 200.0e9, 0.3

        errors_u = []
        errors_srr = []
        errors_stt = []
        errors_szz = []
        hs = []
        for nr, ntheta in [(8, 12), (16, 24), (32, 48)]:
            h = (b - a) / nr
            r_vals = np.linspace(a, b, nr + 1)
            th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
            grid_mesh = skfem.MeshTri.init_tensor(r_vals, th_vals)
            x_coords = grid_mesh.p[0] * np.cos(grid_mesh.p[1])
            y_coords = grid_mesh.p[0] * np.sin(grid_mesh.p[1])
            cyl_mesh = skfem.MeshTri(np.vstack([x_coords, y_coords]), grid_mesh.t)

            basis = skfem.Basis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            # In plane strain, use standard lame_parameters(E, nu)
            K = skfem.asm(linear_elasticity(*lame_parameters(E, nu)), basis)

            bottom_nodes = np.where(np.isclose(cyl_mesh.p[1], 0.0))[0]
            left_nodes = np.where(np.isclose(cyl_mesh.p[0], 0.0))[0]
            D = np.unique(np.concatenate([basis.nodal_dofs[1, bottom_nodes], basis.nodal_dofs[0, left_nodes]]))

            inner_facets = cyl_mesh.facets_satisfying(lambda x: np.isclose(np.sqrt(x[0]**2 + x[1]**2), a, atol=0.01))
            fb_inner = skfem.FacetBasis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=inner_facets)

            @skfem.LinearForm
            def pressure_form(v, w):
                return -P_int * (v[0] * w.n[0] + v[1] * w.n[1])

            f = skfem.asm(pressure_form, fb_inner)
            u_sol = skfem.solve(*skfem.condense(K, f, D=D))

            # Displacements at element centroids
            pts = cyl_mesh.p[:, cyl_mesh.t]
            elem_areas = 0.5 * np.abs((pts[0, 1] - pts[0, 0]) * (pts[1, 2] - pts[1, 0]) - (pts[0, 2] - pts[0, 0]) * (pts[1, 1] - pts[1, 0]))
            xc = np.mean(pts[0], axis=0)
            yc = np.mean(pts[1], axis=0)
            rc = np.sqrt(xc**2 + yc**2)
            thc = np.arctan2(yc, xc)

            scalar_basis = skfem.Basis(cyl_mesh, skfem.ElementTriP1())
            dofs_u = u_sol[basis.nodal_dofs[0]]
            dofs_v = u_sol[basis.nodal_dofs[1]]
            u_c = np.mean(dofs_u[cyl_mesh.t], axis=0)
            v_c = np.mean(dofs_v[cyl_mesh.t], axis=0)
            ur_c = u_c * np.cos(thc) + v_c * np.sin(thc)

            # Element Cauchy stresses in plane strain
            grad_u = scalar_basis.interpolate(dofs_u).grad
            grad_v = scalar_basis.interpolate(dofs_v).grad
            eps_xx = grad_u[0, :, 0]
            eps_yy = grad_v[1, :, 0]
            gamma_xy = grad_u[1, :, 0] + grad_v[0, :, 0]

            lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
            mu = E / (2.0 * (1.0 + nu))
            s_xx = (lam + 2.0 * mu) * eps_xx + lam * eps_yy
            s_yy = (lam + 2.0 * mu) * eps_yy + lam * eps_xx
            t_xy = mu * gamma_xy
            s_zz = nu * (s_xx + s_yy)

            # Polar stress transformation at element centroids
            cos_t = np.cos(thc)
            sin_t = np.sin(thc)
            s_rr = s_xx * cos_t**2 + s_yy * sin_t**2 + 2.0 * t_xy * sin_t * cos_t
            s_tt = s_xx * sin_t**2 + s_yy * cos_t**2 - 2.0 * t_xy * sin_t * cos_t

            # Full radial profile comparison against authoritative plane strain closed form
            exact = lame_cylinder_analytical_plane_strain(rc, a, b, P_int, E, nu)
            w = elem_areas / np.sum(elem_areas)
            ur_err = float(np.sqrt(np.sum(w * (ur_c - exact["u_r"])**2)) / np.sqrt(np.sum(w * exact["u_r"]**2)))
            srr_err = float(np.sqrt(np.sum(w * (s_rr - exact["sigma_rr"])**2)) / np.sqrt(np.sum(w * exact["sigma_rr"]**2)))
            stt_err = float(np.sqrt(np.sum(w * (s_tt - exact["sigma_tt"])**2)) / np.sqrt(np.sum(w * exact["sigma_tt"]**2)))
            szz_err = float(np.sqrt(np.sum(w * (s_zz - exact["sigma_zz"])**2)) / np.sqrt(np.sum(w * exact["sigma_zz"]**2)))

            errors_u.append(ur_err)
            errors_srr.append(srr_err)
            errors_stt.append(stt_err)
            errors_szz.append(szz_err)
            hs.append(h)

        # Nodal max relative error on fine mesh
        r_nodes = np.sqrt(cyl_mesh.p[0]**2 + cyl_mesh.p[1]**2)
        ur_nodes = np.sqrt(u_sol[basis.nodal_dofs[0]]**2 + u_sol[basis.nodal_dofs[1]]**2)
        exact_nodes = lame_cylinder_analytical_plane_strain(r_nodes, a, b, P_int, E, nu)
        max_rel_nodal_err = float(np.max(np.abs(ur_nodes - exact_nodes["u_r"]) / exact_nodes["u_r"]))

        # 1. Monotonic error reduction across all components under uniform refinement
        assert errors_u[1] < errors_u[0] and errors_u[2] < errors_u[1], f"Displacement error not strictly decreasing: {errors_u}"
        assert errors_srr[1] < errors_srr[0] and errors_srr[2] < errors_srr[1], f"Radial stress error not strictly decreasing: {errors_srr}"
        assert errors_stt[1] < errors_stt[0] and errors_stt[2] < errors_stt[1], f"Hoop stress error not strictly decreasing: {errors_stt}"
        assert errors_szz[1] < errors_szz[0] and errors_szz[2] < errors_szz[1], f"Axial stress error not strictly decreasing: {errors_szz}"

        # 2. Observed convergence orders (p_u ~ 2.0 in L2, p_sigma ~ 1.0 in L2)
        p_u = float(np.polyfit(np.log(hs), np.log(errors_u), 1)[0])
        p_srr = float(np.polyfit(np.log(hs), np.log(errors_srr), 1)[0])
        p_stt = float(np.polyfit(np.log(hs), np.log(errors_stt), 1)[0])
        p_szz = float(np.polyfit(np.log(hs), np.log(errors_szz), 1)[0])
        assert 1.85 <= p_u <= 2.15, f"Observed displacement order {p_u:.3f} outside [1.85, 2.15]"
        assert 0.85 <= p_srr <= 1.15, f"Observed radial stress order {p_srr:.3f} outside [0.85, 1.15]"
        assert 0.85 <= p_stt <= 1.15, f"Observed hoop stress order {p_stt:.3f} outside [0.85, 1.15]"
        assert 0.85 <= p_szz <= 1.15, f"Observed axial stress order {p_szz:.3f} outside [0.85, 1.15]"

        # 3. Fine mesh tolerances
        assert errors_u[-1] < 0.0010, f"Fine mesh displacement L2 error {errors_u[-1]:.4%} exceeds 0.10%"
        assert max_rel_nodal_err < 0.0035, f"Max nodal error {max_rel_nodal_err:.4%} exceeds 0.35%"
        assert errors_srr[-1] < 0.050, f"Fine mesh radial stress error {errors_srr[-1]:.4%} exceeds 5.0%"
        assert errors_stt[-1] < 0.030, f"Fine mesh hoop stress error {errors_stt[-1]:.4%} exceeds 3.0%"
        assert errors_szz[-1] < 0.070, f"Fine mesh axial stress error {errors_szz[-1]:.4%} exceeds 7.0%"

    def test_ref_06_plate_with_hole_stress_concentration(self):
        """REF-06: Numerical Kirsch plate-with-hole stress concentration benchmark (Kt -> 3.000)."""
        spec = get_reference_problem("REF-06-PLATE-HOLE-KIRSCH")
        a = 1.0  # hole radius
        b = 5.0  # far-field boundary radius
        E, nu = 200.0e9, 0.3
        sigma_inf = 10.0e6

        mesh_levels = [(12, 16), (24, 32), (48, 64)]
        kt_values = []
        rel_errors = []

        for nr, ntheta in mesh_levels:
            r_vals = np.geomspace(a, b, nr + 1)
            th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
            grid = skfem.MeshTri.init_tensor(r_vals, th_vals)
            x = grid.p[0] * np.cos(grid.p[1])
            y = grid.p[0] * np.sin(grid.p[1])
            mesh = skfem.MeshTri(np.vstack([x, y]), grid.t)

            basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

            bottom_nodes = np.where(np.isclose(mesh.p[1], 0.0))[0]
            left_nodes = np.where(np.isclose(mesh.p[0], 0.0))[0]
            D = np.unique(np.concatenate([basis.nodal_dofs[1, bottom_nodes], basis.nodal_dofs[0, left_nodes]]))

            outer_facets = mesh.facets_satisfying(lambda p: np.isclose(np.sqrt(p[0]**2 + p[1]**2), b, atol=0.05))
            fb_outer = skfem.FacetBasis(mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=outer_facets)

            @skfem.LinearForm
            def outer_traction(v, w):
                th = np.arctan2(w.x[1], w.x[0])
                tr_data = kirsch_plate_hole_analytical(b, th, a, sigma_inf)
                s_r = tr_data["sigma_rr"]
                t_rth = tr_data["sigma_rth"]
                T_x = s_r * np.cos(th) - t_rth * np.sin(th)
                T_y = s_r * np.sin(th) + t_rth * np.cos(th)
                return T_x * v[0] + T_y * v[1]

            f = skfem.asm(outer_traction, fb_outer)
            u_sol = skfem.solve(*skfem.condense(K, f, D=D))

            # Area-weighted patch stress recovery at hole boundary (0, a)
            # Physical justification: At (0, a), theta = pi/2.
            # Circumferential stress sigma_theta is tangential to the circular cavity.
            # Since the boundary at (0, a) is horizontal (parallel to x-axis),
            # sigma_theta(a, pi/2) == sigma_xx(0, a).
            top_hole_node = left_nodes[np.argmin(np.abs(mesh.p[1, left_nodes] - a))]
            elem_idx = np.where(np.any(mesh.t == top_hole_node, axis=0))[0]

            pts = mesh.p[:, mesh.t[:, elem_idx]]
            patch_areas = 0.5 * np.abs((pts[0, 1] - pts[0, 0]) * (pts[1, 2] - pts[1, 0]) - (pts[0, 2] - pts[0, 0]) * (pts[1, 1] - pts[1, 0]))

            scalar_basis = skfem.Basis(mesh, skfem.ElementTriP1())
            dofs_u = u_sol[basis.nodal_dofs[0]]
            dofs_v = u_sol[basis.nodal_dofs[1]]
            grad_u = scalar_basis.interpolate(dofs_u).grad
            grad_v = scalar_basis.interpolate(dofs_v).grad

            eps_xx = grad_u[0, elem_idx, 0]
            eps_yy = grad_v[1, elem_idx, 0]
            sigma_xx = (E / (1.0 - nu**2)) * (eps_xx + nu * eps_yy)

            # Area-weighted patch average: \bar{\sigma} = \sum(A_i * \sigma_i) / \sum(A_i)
            peak_sigma = float(np.sum(patch_areas * sigma_xx) / np.sum(patch_areas))
            kt = peak_sigma / sigma_inf
            kt_values.append(kt)
            rel_errors.append(abs(kt - 3.0) / 3.0)

        # 1. Monotonic error reduction across refinement series
        assert rel_errors[1] < rel_errors[0] and rel_errors[2] < rel_errors[1], f"Refinement series not monotonically reducing error: {rel_errors}"

        # 2. Fine mesh achieves tight agreement with analytical Kt = 3.000 (relative error <= 0.10%)
        assert rel_errors[-1] <= 0.0010, f"Fine mesh relative error {rel_errors[-1]:.4%} exceeds 0.10% (Kt={kt_values[-1]:.4f})"
        assert 2.98 <= kt_values[-1] <= 3.02, f"Fine mesh Kt {kt_values[-1]:.4f} outside [2.98, 3.02]"

    def test_ref_06_kirsch_input_traction_sensitivity(self):
        """REF-06: Input boundary condition / traction perturbation sensitivity."""
        a, b = 1.0, 5.0
        E, nu = 200.0e9, 0.3
        sigma_inf = 10.0e6
        nr, ntheta = 24, 32

        r_vals = np.geomspace(a, b, nr + 1)
        th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
        grid = skfem.MeshTri.init_tensor(r_vals, th_vals)
        mesh = skfem.MeshTri(np.vstack([grid.p[0] * np.cos(grid.p[1]), grid.p[0] * np.sin(grid.p[1])]), grid.t)

        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)
        bottom_nodes = np.where(np.isclose(mesh.p[1], 0.0))[0]
        left_nodes = np.where(np.isclose(mesh.p[0], 0.0))[0]
        D = np.unique(np.concatenate([basis.nodal_dofs[1, bottom_nodes], basis.nodal_dofs[0, left_nodes]]))

        outer_facets = mesh.facets_satisfying(lambda p: np.isclose(np.sqrt(p[0]**2 + p[1]**2), b, atol=0.05))
        fb_outer = skfem.FacetBasis(mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=outer_facets)

        # Perturb traction by +15%
        @skfem.LinearForm
        def perturbed_traction(v, w):
            th = np.arctan2(w.x[1], w.x[0])
            tr_data = kirsch_plate_hole_analytical(b, th, a, sigma_inf)
            s_r = 1.15 * tr_data["sigma_rr"]
            t_rth = 1.15 * tr_data["sigma_rth"]
            T_x = s_r * np.cos(th) - t_rth * np.sin(th)
            T_y = s_r * np.sin(th) + t_rth * np.cos(th)
            return T_x * v[0] + T_y * v[1]

        f_pert = skfem.asm(perturbed_traction, fb_outer)
        u_sol = skfem.solve(*skfem.condense(K, f_pert, D=D))

        top_hole_node = left_nodes[np.argmin(np.abs(mesh.p[1, left_nodes] - a))]
        elem_idx = np.where(np.any(mesh.t == top_hole_node, axis=0))[0]
        pts = mesh.p[:, mesh.t[:, elem_idx]]
        patch_areas = 0.5 * np.abs((pts[0, 1] - pts[0, 0]) * (pts[1, 2] - pts[1, 0]) - (pts[0, 2] - pts[0, 0]) * (pts[1, 1] - pts[1, 0]))

        scalar_basis = skfem.Basis(mesh, skfem.ElementTriP1())
        grad_u = scalar_basis.interpolate(u_sol[basis.nodal_dofs[0]]).grad
        grad_v = scalar_basis.interpolate(u_sol[basis.nodal_dofs[1]]).grad
        sigma_xx = (E / (1.0 - nu**2)) * (grad_u[0, elem_idx, 0] + nu * grad_v[1, elem_idx, 0])
        peak_sigma = float(np.sum(patch_areas * sigma_xx) / np.sum(patch_areas))
        kt_pert = peak_sigma / sigma_inf

        # Perturbed solve MUST fall outside valid acceptance interval [2.95, 3.05]
        assert not (2.95 <= kt_pert <= 3.05), f"Benchmark failed to detect perturbation: Kt={kt_pert:.4f}"

    def test_ref_06_kirsch_production_defect_sensitivity(self):
        """REF-06: Production solver defect sensitivity (plane-strain constitutive tensor applied to plate fails gate)."""
        a, b = 1.0, 5.0
        E, nu = 200.0e9, 0.3
        sigma_inf = 10.0e6
        nr, ntheta = 24, 32

        r_vals = np.geomspace(a, b, nr + 1)
        th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
        grid = skfem.MeshTri.init_tensor(r_vals, th_vals)
        mesh = skfem.MeshTri(np.vstack([grid.p[0] * np.cos(grid.p[1]), grid.p[0] * np.sin(grid.p[1])]), grid.t)

        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        # Deliberate production solver defect: assembling plane-strain stiffness on a plane-stress plate
        K_defective = skfem.asm(linear_elasticity(*lame_parameters(E, nu)), basis)
        bottom_nodes = np.where(np.isclose(mesh.p[1], 0.0))[0]
        left_nodes = np.where(np.isclose(mesh.p[0], 0.0))[0]
        D = np.unique(np.concatenate([basis.nodal_dofs[1, bottom_nodes], basis.nodal_dofs[0, left_nodes]]))

        outer_facets = mesh.facets_satisfying(lambda p: np.isclose(np.sqrt(p[0]**2 + p[1]**2), b, atol=0.05))
        fb_outer = skfem.FacetBasis(mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=outer_facets)

        @skfem.LinearForm
        def outer_traction(v, w):
            th = np.arctan2(w.x[1], w.x[0])
            tr_data = kirsch_plate_hole_analytical(b, th, a, sigma_inf)
            return (tr_data["sigma_rr"] * np.cos(th) - tr_data["sigma_rth"] * np.sin(th)) * v[0] + (tr_data["sigma_rr"] * np.sin(th) + tr_data["sigma_rth"] * np.cos(th)) * v[1]

        f = skfem.asm(outer_traction, fb_outer)
        u_sol = skfem.solve(*skfem.condense(K_defective, f, D=D))

        top_hole_node = left_nodes[np.argmin(np.abs(mesh.p[1, left_nodes] - a))]
        elem_idx = np.where(np.any(mesh.t == top_hole_node, axis=0))[0]
        pts = mesh.p[:, mesh.t[:, elem_idx]]
        patch_areas = 0.5 * np.abs((pts[0, 1] - pts[0, 0]) * (pts[1, 2] - pts[1, 0]) - (pts[0, 2] - pts[0, 0]) * (pts[1, 1] - pts[1, 0]))

        scalar_basis = skfem.Basis(mesh, skfem.ElementTriP1())
        grad_u = scalar_basis.interpolate(u_sol[basis.nodal_dofs[0]]).grad
        grad_v = scalar_basis.interpolate(u_sol[basis.nodal_dofs[1]]).grad

        sigma_xx = (E / (1.0 - nu**2)) * (grad_u[0, elem_idx, 0] + nu * grad_v[1, elem_idx, 0])
        peak_sigma_defective = float(np.sum(patch_areas * sigma_xx) / np.sum(patch_areas))
        kt_defective = peak_sigma_defective / sigma_inf

        # Defective solve yields Kt ~ 2.62, decisively failing the acceptance gate [2.95, 3.05]
        assert not (2.95 <= kt_defective <= 3.05), f"Defective solver went undetected: Kt={kt_defective:.4f}"
        assert abs(kt_defective - 3.0) / 3.0 > 0.10, f"Defect error {abs(kt_defective - 3.0) / 3.0:.2%} not large enough"

    def test_ref_07_l_shaped_domain_singular(self):
        """REF-07: Linear elasticity re-entrant corner singularity benchmark on L-shaped domain."""
        spec = get_reference_problem("REF-07-L-SHAPED-DOMAIN-SINGULAR")
        E, nu = 200.0e9, 0.3
        P_traction = 1.0e6

        energies = []
        for k in [1, 2, 3, 4]:
            m = skfem.MeshTri.init_lshaped().refined(k)
            basis = skfem.Basis(m, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

            top_nodes = np.where(np.isclose(m.p[1], 1.0))[0]
            D = np.concatenate([basis.nodal_dofs[0, top_nodes], basis.nodal_dofs[1, top_nodes]])

            right_facets = m.facets_satisfying(lambda p: np.isclose(p[0], 1.0))
            fb = skfem.FacetBasis(m, skfem.ElementVector(skfem.ElementTriP1()), facets=right_facets)

            @skfem.LinearForm
            def tr(v, w):
                return P_traction * v[1]

            f = skfem.asm(tr, fb)
            u = skfem.solve(*skfem.condense(K, f, D=D))
            strain_energy = float(0.5 * np.dot(u, K @ u))
            energies.append(strain_energy)

        # 1. Monotonic strain energy convergence from below (Rayleigh-Ritz minimum potential energy)
        for i in range(len(energies) - 1):
            assert energies[i+1] > energies[i], f"Level {i+1} energy ({energies[i+1]}) <= Level {i} energy ({energies[i]})"

        # 2. Monotonic energy increment reduction: Delta U_k decreases as mesh refines
        deltas = [energies[i+1] - energies[i] for i in range(len(energies) - 1)]
        for i in range(len(deltas) - 1):
            assert deltas[i+1] < deltas[i], f"Energy increment not decreasing: Delta_{i+1}={deltas[i+1]} >= Delta_{i}={deltas[i]}"

        # 3. Observed singularity convergence exponent lambda_obs = log2(ratio) / 2
        # For re-entrant corner (3*pi/2), theoretical Mode I root is lambda ~ 0.54448.
        # Observed uniform pre-asymptotic rate is bounded in [0.45, 0.75], strictly < 1.0 (smooth rate).
        ratios = [deltas[i] / deltas[i+1] for i in range(len(deltas) - 1)]
        for r in ratios:
            lam_obs = float(np.log2(r) / 2.0)
            assert 0.45 <= lam_obs <= 0.75, f"Observed lambda {lam_obs:.4f} outside expected range [0.45, 0.75]"

    def test_ref_08_rigid_body_nullspace(self):
        """REF-08: Exactly 3 rigid-body zero modes in unconstrained 2D elasticity stiffness."""
        spec = get_reference_problem("REF-08-RIGID-BODY-NULLSPACE")
        mesh = skfem.MeshTri.init_tensor(np.linspace(0, 1, 4), np.linspace(0, 1, 4))
        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        E, nu = 100.0e9, 0.3
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

        K_dense = K.toarray()
        eigenvalues = np.sort(np.linalg.eigvalsh(K_dense))

        # First 3 eigenvalues must be machine-precision zero
        lambda_max = eigenvalues[-1]
        assert abs(eigenvalues[0]) / lambda_max < 1e-12
        assert abs(eigenvalues[1]) / lambda_max < 1e-12
        assert abs(eigenvalues[2]) / lambda_max < 1e-12

        # 4th eigenvalue must be strictly positive (elastic deformation mode)
        assert eigenvalues[3] / lambda_max > 1e-4
