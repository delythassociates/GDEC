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
from skfem.models.elasticity import linear_elasticity, plane_stress
from skfem.helpers import dot

from gdec.verification.reference_problems import get_reference_problem, list_reference_problems


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

    def test_ref_05_lame_thick_cylinder(self):
        """REF-05: Lame pressurized thick cylinder quadrant under internal pressure."""
        spec = get_reference_problem("REF-05-LAME-CYLINDER")
        a, b = 1.0, 2.0
        P_int = 10.0e6
        E, nu = 200.0e9, 0.3

        # Analytical Lame formula for radial displacement at outer radius r = b in plane stress:
        # u_r(b) = (2 * P_int * a^2 * b) / (E * (b^2 - a^2))
        expected_ur_b = (2.0 * P_int * a**2 * b) / (E * (b**2 - a**2))

        # Discretize quadrant in polar coordinates (r, theta) mapped to (x, y)
        nr, ntheta = 16, 24
        r_vals = np.linspace(a, b, nr + 1)
        theta_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
        grid_mesh = skfem.MeshTri.init_tensor(r_vals, theta_vals)

        # Map to Cartesian coordinates
        r_coords = grid_mesh.p[0]
        th_coords = grid_mesh.p[1]
        x_coords = r_coords * np.cos(th_coords)
        y_coords = r_coords * np.sin(th_coords)
        cyl_mesh = skfem.MeshTri(np.vstack([x_coords, y_coords]), grid_mesh.t)

        basis = skfem.Basis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

        # Symmetry boundaries: bottom (y=0 -> v=0), left (x=0 -> u=0)
        bottom_nodes = np.where(np.isclose(cyl_mesh.p[1], 0.0))[0]
        left_nodes = np.where(np.isclose(cyl_mesh.p[0], 0.0))[0]
        D_bottom = basis.nodal_dofs[1, bottom_nodes]
        D_left = basis.nodal_dofs[0, left_nodes]
        D = np.unique(np.concatenate([D_bottom, D_left]))

        # Internal pressure on inner radius r = a: normal force P_int directed outward from cavity
        inner_facets = cyl_mesh.facets_satisfying(lambda x: np.isclose(np.sqrt(x[0]**2 + x[1]**2), a, atol=0.01))
        fb_inner = skfem.FacetBasis(cyl_mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=inner_facets)

        @skfem.LinearForm
        def pressure_form(v, w):
            # w.n is unit outward normal to the domain (points toward origin)
            # Internal pressure acts outward from cavity into domain (-w.n)
            return -P_int * dot(v, w.n)

        f = skfem.asm(pressure_form, fb_inner)
        u_sol = skfem.solve(*skfem.condense(K, f, D=D))

        # Check radial displacement at outer radius
        outer_nodes = np.where(np.isclose(np.sqrt(cyl_mesh.p[0]**2 + cyl_mesh.p[1]**2), b, atol=0.01))[0]
        ur_outer = np.sqrt(u_sol[basis.nodal_dofs[0, outer_nodes]]**2 + u_sol[basis.nodal_dofs[1, outer_nodes]]**2)
        mean_ur_outer = np.mean(ur_outer)

        # Relative agreement within 1.5% on moderate mesh (as documented in spec)
        rel_err = abs(mean_ur_outer - expected_ur_b) / expected_ur_b
        assert rel_err < 0.015, f"REF-05 outer radial displacement discrepancy: {rel_err:.2%}"

    def test_ref_06_plate_with_hole_stress_concentration(self):
        """REF-06: Numerical Kirsch plate-with-hole stress concentration benchmark (Kt ~ 3.0)."""
        spec = get_reference_problem("REF-06-PLATE-HOLE-KIRSCH")
        assert "3.0" in spec.expected_qoi_formula
        assert spec.category == "physical_validation"

        # Solve 2D elasticity on quarter-annulus with circular hole
        a = 1.0  # hole radius
        b = 5.0  # far-field boundary radius (b >> a)
        nr, ntheta = 24, 32
        E, nu = 200.0e9, 0.3
        sigma_inf = 10.0e6

        r_vals = np.geomspace(a, b, nr + 1)
        th_vals = np.linspace(0, np.pi / 2.0, ntheta + 1)
        grid = skfem.MeshTri.init_tensor(r_vals, th_vals)
        x = grid.p[0] * np.cos(grid.p[1])
        y = grid.p[0] * np.sin(grid.p[1])
        mesh = skfem.MeshTri(np.vstack([x, y]), grid.t)

        basis = skfem.Basis(mesh, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
        K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

        # Symmetry: bottom y=0 (v=0), left x=0 (u=0)
        bottom_nodes = np.where(np.isclose(mesh.p[1], 0.0))[0]
        left_nodes = np.where(np.isclose(mesh.p[0], 0.0))[0]
        D_bottom = basis.nodal_dofs[1, bottom_nodes]
        D_left = basis.nodal_dofs[0, left_nodes]
        D = np.unique(np.concatenate([D_bottom, D_left]))

        # Far-field boundary r = b: apply Kirsch analytical tractions
        outer_facets = mesh.facets_satisfying(lambda p: np.isclose(np.sqrt(p[0]**2 + p[1]**2), b, atol=0.05))
        fb_outer = skfem.FacetBasis(mesh, skfem.ElementVector(skfem.ElementTriP1()), facets=outer_facets)

        @skfem.LinearForm
        def outer_traction(v, w):
            x_c, y_c = w.x[0], w.x[1]
            th = np.arctan2(y_c, x_c)
            r = b
            s_r = (sigma_inf / 2.0) * (1.0 - a**2 / r**2) + (sigma_inf / 2.0) * (1.0 - 4.0 * a**2 / r**2 + 3.0 * a**4 / r**4) * np.cos(2.0 * th)
            t_rth = -(sigma_inf / 2.0) * (1.0 + 2.0 * a**2 / r**2 - 3.0 * a**4 / r**4) * np.sin(2.0 * th)
            T_x = s_r * np.cos(th) - t_rth * np.sin(th)
            T_y = s_r * np.sin(th) + t_rth * np.cos(th)
            return T_x * v[0] + T_y * v[1]

        f = skfem.asm(outer_traction, fb_outer)
        u_sol = skfem.solve(*skfem.condense(K, f, D=D))

        # Evaluate peak hoop stress at top of hole (0, a) where theta = pi/2:
        top_hole_node = left_nodes[np.argmin(np.abs(mesh.p[1, left_nodes] - a))]
        dofs_u = u_sol[basis.nodal_dofs[0]]
        dofs_v = u_sol[basis.nodal_dofs[1]]

        elem_idx = np.where(np.any(mesh.t == top_hole_node, axis=0))[0]
        scalar_basis = skfem.Basis(mesh, skfem.ElementTriP1())
        grad_u = scalar_basis.interpolate(dofs_u).grad
        grad_v = scalar_basis.interpolate(dofs_v).grad

        eps_xx = grad_u[0]
        eps_yy = grad_v[1]
        sigma_xx = (E / (1.0 - nu**2)) * (eps_xx + nu * eps_yy)
        peak_sigma = float(np.mean(sigma_xx[elem_idx, :]))
        kt_num = peak_sigma / sigma_inf

        # Stress concentration factor must be in [2.85, 3.15] (within 5% of theoretical 3.0)
        assert 2.85 <= kt_num <= 3.15, f"REF-06 calculated Kt {kt_num:.3f} outside [2.85, 3.15] (expected ~3.0)"

    def test_ref_07_l_shaped_domain_singular(self):
        """REF-07: Linear elasticity re-entrant corner singularity benchmark on L-shaped domain."""
        spec = get_reference_problem("REF-07-L-SHAPED-DOMAIN-SINGULAR")
        assert spec.expected_order_h == pytest.approx(0.544, abs=0.01)
        assert spec.category == "numerical_verification"

        # Solve 2D linear elasticity on sequence of uniform L-shaped meshes
        E, nu = 100.0e9, 0.3
        P_traction = 1000.0

        energies = []
        for k in [1, 2, 3]:
            m = skfem.MeshTri.init_lshaped().refined(k)
            basis = skfem.Basis(m, skfem.ElementVector(skfem.ElementTriP1()), intorder=2)
            K = skfem.asm(linear_elasticity(*plane_stress(E, nu)), basis)

            # Clamped on top boundary y = 1: x in [-1, 0]
            top_nodes = np.where(np.isclose(m.p[1], 1.0))[0]
            D = np.concatenate([basis.nodal_dofs[0, top_nodes], basis.nodal_dofs[1, top_nodes]])

            # Shear traction on right boundary x = 1: y in [-1, 0]
            right_facets = m.facets_satisfying(lambda p: np.isclose(p[0], 1.0))
            fb = skfem.FacetBasis(m, skfem.ElementVector(skfem.ElementTriP1()), facets=right_facets)

            @skfem.LinearForm
            def tr(v, w):
                return P_traction * v[1]

            f = skfem.asm(tr, fb)
            u = skfem.solve(*skfem.condense(K, f, D=D))
            # Conforming strain energy U_h = 1/2 * u^T * K * u
            strain_energy = float(0.5 * np.dot(u, K @ u))
            energies.append(strain_energy)

        # 1. Monotonic strain energy convergence from below (Rayleigh-Ritz minimum potential energy)
        assert energies[1] > energies[0], f"Energy level 1 {energies[1]} <= level 0 {energies[0]}"
        assert energies[2] > energies[1], f"Energy level 2 {energies[2]} <= level 1 {energies[1]}"

        # 2. Ratio of energy increments reflects corner singularity convergence exponent 2*lambda ~ 1.089
        delta_01 = energies[1] - energies[0]
        delta_12 = energies[2] - energies[1]
        ratio = delta_01 / delta_12
        assert 1.50 <= ratio <= 2.50, f"Singular energy increment ratio {ratio:.3f} outside [1.50, 2.50]"

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
