"""
Phase 4 Experimental Suite: Rigorous Solver, Matrix Conditioning, and Performance Benchmarking.
Collects actual empirical measurements without fabrication.
"""

import time
import os
import psutil
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem as fem

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver, FEMSolution
from gdec.fem.matrix_diagnostics import analyze_stiffness_matrix, compute_symmetry_defect
from gdec.fem.solvers import (
    ConjugateGradientSolver,
    IdentityPreconditioner,
    JacobiPreconditioner,
    IncompleteCholeskyPreconditioner,
    AMGPreconditioner,
    ILUPreconditioner,
)
from gdec.fem.postprocess import PostProcessor


def get_process_memory_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024.0 * 1024.0)


def compute_mesh_quality(mesh: GDECMesh) -> tuple[float, float]:
    """Compute minimum angle (degrees) and maximum aspect ratio."""
    p = mesh.mesh.p
    t = mesh.mesh.t
    v0 = p[:, t[0]]
    v1 = p[:, t[1]]
    v2 = p[:, t[2]]
    a = np.linalg.norm(v1 - v0, axis=0)
    b = np.linalg.norm(v2 - v1, axis=0)
    c = np.linalg.norm(v0 - v2, axis=0)
    
    # Law of cosines
    cos_A = np.clip((b**2 + c**2 - a**2) / (2.0 * b * c + 1e-15), -1.0, 1.0)
    cos_B = np.clip((a**2 + c**2 - b**2) / (2.0 * a * c + 1e-15), -1.0, 1.0)
    cos_C = np.clip((a**2 + b**2 - c**2) / (2.0 * a * b + 1e-15), -1.0, 1.0)
    angles = np.rad2deg(np.vstack([np.arccos(cos_A), np.arccos(cos_B), np.arccos(cos_C)]))
    min_angle = float(np.min(angles))
    
    # Aspect ratio: max_side / (2 * inradius) = max_side * (a+b+c) / (4 * area)
    areas = mesh.element_areas
    s = 0.5 * (a + b + c)
    r_in = areas / (s + 1e-15)
    max_side = np.maximum(np.maximum(a, b), c)
    aspect_ratios = max_side / (2.0 * r_in + 1e-15)
    max_ar = float(np.max(aspect_ratios))
    return min_angle, max_ar


def run_matrix_verification_study():
    print("=" * 80)
    print("PHASE 4.1: MATRIX SYMMETRY AND SPD VERIFICATION")
    print("=" * 80)

    configs = [
        ("Cantilever Coarse (4x2)", 4, 2, "plane_stress", 70e9, 0.33, [("left", ["x", "y"])]),
        ("Cantilever Medium (12x6)", 12, 6, "plane_stress", 70e9, 0.33, [("left", ["x", "y"])]),
        ("Cantilever Fine (24x12)", 24, 12, "plane_stress", 70e9, 0.33, [("left", ["x", "y"])]),
        ("Cantilever Plane Strain", 12, 6, "plane_strain", 70e9, 0.33, [("left", ["x", "y"])]),
        ("Distorted Mesh (12x6)", 12, 6, "plane_stress", 70e9, 0.33, [("left", ["x", "y"])]),
        ("Steel Material (E=210GPa, nu=0.3)", 12, 6, "plane_stress", 210e9, 0.30, [("left", ["x", "y"])]),
        ("Rubber-like (nu=0.49)", 12, 6, "plane_stress", 10e6, 0.49, [("left", ["x", "y"])]),
        ("Unconstrained (No BCs)", 12, 6, "plane_stress", 70e9, 0.33, []),
        ("Roller Boundary (Only Ux)", 12, 6, "plane_stress", 70e9, 0.33, [("left", ["x"])]),
    ]

    for name, nx, ny, assumption, E, nu, bcs in configs:
        c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption=assumption, thickness=0.02)
        solver = LinearElasticitySolver(c)
        mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=nx, ny=ny)

        if "Distorted" in name:
            p = mesh.mesh.p.copy()
            is_interior = (p[0] > 0.1) & (p[0] < 1.9) & (p[1] > 0.05) & (p[1] < 0.45)
            np.random.seed(42)
            p[:, is_interior] += (np.random.rand(2, np.sum(is_interior)) - 0.5) * 0.04
            mesh = GDECMesh(fem.MeshTri(p, mesh.mesh.t), 2.0, 0.5)

        basis = solver.create_basis(mesh)
        K = solver.assemble_stiffness(basis)
        f = np.zeros(basis.N)

        dofs_fixed_list = []
        for bnd, comps in bcs:
            dofs_fixed_list.append(solver.find_dirichlet_dofs(basis, mesh, bnd, comps))
        dofs_fixed = np.unique(np.concatenate(dofs_fixed_list)) if dofs_fixed_list else np.array([], dtype=int)

        if len(dofs_fixed) > 0:
            K_eval, _, _, _ = fem.condense(K, f, D=dofs_fixed)
        else:
            K_eval = K

        diag = analyze_stiffness_matrix(K_eval, compute_spectrum=True, dense_threshold=400)
        cond_str = f"{diag.condition_number:.2e}" if diag.condition_number is not None else "N/A"
        lmin_str = f"{diag.lambda_min:.2e}" if diag.lambda_min is not None else "N/A"
        lmax_str = f"{diag.lambda_max:.2e}" if diag.lambda_max is not None else "N/A"

        print(f"Case: {name}")
        print(f"  Shape: {diag.n_rows}x{diag.n_cols}, NNZ: {diag.nnz}, delta_sym: {diag.symmetry_defect:.2e}")
        print(f"  lambda_min: {lmin_str}, lambda_max: {lmax_str}, kappa_2: {cond_str}")
        print(f"  SPD: {diag.is_positive_definite}, CG Eligible: {diag.is_cg_eligible}, Null Modes: {diag.null_modes_count}")
        if diag.warnings:
            print(f"  Warnings: {diag.warnings[0]}")
        print()


def run_conditioning_scaling_study():
    print("=" * 80)
    print("PHASE 4.2: CONDITIONING UNDER MESH REFINEMENT AND PARAMETER VARIATION")
    print("=" * 80)

    # 1. Mesh Refinement Scaling
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)

    grids = [(4, 2), (8, 4), (16, 8), (32, 16), (64, 32)]
    print("--- Mesh Refinement Scaling (Cantilever 2.0m x 0.5m) ---")
    print(f"{'Grid':<10} | {'DOFs':<7} | {'Elements':<8} | {'Min Angle':<10} | {'NNZ':<8} | {'lambda_min':<11} | {'lambda_max':<11} | {'kappa_2':<10} | {'Asm Time (s)':<12}")
    print("-" * 105)

    for nx, ny in grids:
        t0 = time.perf_counter()
        mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=nx, ny=ny)
        basis = solver.create_basis(mesh)
        K = solver.assemble_stiffness(basis)
        t_asm = time.perf_counter() - t0

        f = np.zeros(basis.N)
        dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])
        K_free, _, _, _ = fem.condense(K, f, D=dofs_fixed)

        diag = analyze_stiffness_matrix(K_free, compute_spectrum=True, dense_threshold=200)

        # Min angle and aspect ratio
        min_angle, max_ar = compute_mesh_quality(mesh)

        print(f"{nx}x{ny:<7} | {diag.n_rows:<7} | {mesh.nelements:<8} | {min_angle:<10.2f} | {diag.nnz:<8} | {diag.lambda_min:<11.2e} | {diag.lambda_max:<11.2e} | {diag.condition_number:<10.2e} | {t_asm:<12.4f}")

    print()

    # 2. Poisson's Ratio Scaling: Plane Stress vs Plane Strain
    print("--- Poisson's Ratio Scaling (Grid 16x8, E=70GPa): Plane Stress vs Plane Strain ---")
    nus = [0.20, 0.30, 0.40, 0.45, 0.49, 0.499]
    print(f"{'nu':<7} | {'Stress lambda_min':<18} | {'Stress kappa_2':<15} | {'Strain lambda_min':<18} | {'Strain kappa_2':<15}")
    print("-" * 85)

    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=16, ny=8)
    for nu in nus:
        # Plane stress
        c_stress = ConstitutiveTensor.from_properties(E=70e9, nu=nu, assumption="plane_stress")
        s_stress = LinearElasticitySolver(c_stress)
        basis = s_stress.create_basis(mesh)
        K_str = s_stress.assemble_stiffness(basis)
        dofs = s_stress.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])
        Kf_str, _, _, _ = fem.condense(K_str, np.zeros(basis.N), D=dofs)
        diag_str = analyze_stiffness_matrix(Kf_str, compute_spectrum=True, dense_threshold=200)

        # Plane strain
        c_strain = ConstitutiveTensor.from_properties(E=70e9, nu=nu, assumption="plane_strain")
        s_strain = LinearElasticitySolver(c_strain)
        K_stra = s_strain.assemble_stiffness(basis)
        Kf_stra, _, _, _ = fem.condense(K_stra, np.zeros(basis.N), D=dofs)
        diag_stra = analyze_stiffness_matrix(Kf_stra, compute_spectrum=True, dense_threshold=200)

        print(f"{nu:<7.3f} | {diag_str.lambda_min:<18.2e} | {diag_str.condition_number:<15.2e} | {diag_stra.lambda_min:<18.2e} | {diag_stra.condition_number:<15.2e}")

    print()

    # 3. Geometric Aspect Ratio Distortion
    print("--- Geometric Aspect Ratio Distortion (Fixed mesh 10x10, Length=1.0m, Width varying) ---")
    aspect_ratios = [1.0, 2.0, 5.0, 10.0, 20.0]
    print(f"{'AR (L/H)':<10} | {'Height (m)':<12} | {'Min Angle (deg)':<16} | {'kappa_2':<12}")
    print("-" * 55)

    for ar in aspect_ratios:
        h = 1.0 / ar
        m = GDECMesh.create_cantilever_mesh(width=1.0, height=h, nx=10, ny=10)
        c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress")
        s = LinearElasticitySolver(c)
        basis = s.create_basis(m)
        K = s.assemble_stiffness(basis)
        dofs = s.find_dirichlet_dofs(basis, m, "left", ["x", "y"])
        Kf, _, _, _ = fem.condense(K, np.zeros(basis.N), D=dofs)
        diag = analyze_stiffness_matrix(Kf, compute_spectrum=True, dense_threshold=200)
        min_ang, _ = compute_mesh_quality(m)
        print(f"{ar:<10.1f} | {h:<12.4f} | {min_ang:<16.2f} | {diag.condition_number:<12.2e}")

    print()


def run_solver_benchmarking():
    print("=" * 80)
    print("PHASE 4.3 - 4.7: SOLVER PERFORMANCE AND NUMERICAL EQUIVALENCE BENCHMARKS")
    print("=" * 80)

    # Benchmark problem setup: Cantilever under end shear load
    # L = 2.0m, H = 0.5m, t = 0.02m, E = 70 GPa, nu = 0.33
    # Tip shear traction ty = -1.0 MPa on right boundary
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)

    bench_grids = [(8, 4), (16, 8), (32, 16), (64, 32), (96, 48)]
    cg = ConjugateGradientSolver(default_rtol=1e-8, default_atol=1e-12)

    for nx, ny in bench_grids:
        mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=nx, ny=ny)
        basis = solver.create_basis(mesh)
        t_asm_0 = time.perf_counter()
        K = solver.assemble_stiffness(basis)
        f = solver.assemble_traction(mesh, "right", 0.0, -1e6)
        g = solver.assemble_qoi_adjoint_vector(mesh, "right", "y")
        dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])
        t_asm = time.perf_counter() - t_asm_0

        t_cond_0 = time.perf_counter()
        K_free, f_free, u_full, I = fem.condense(K, f, D=dofs_fixed)
        g_free = g[I]
        t_cond = time.perf_counter() - t_cond_0

        n_dofs = K_free.shape[0]
        nnz = K_free.nnz

        print(f"\n=======================================================")
        print(f"BENCHMARK SYSTEM: Grid {nx}x{ny} | Free DOFs: {n_dofs:,} | NNZ: {nnz:,}")
        print(f"=======================================================")

        # 1. DIRECT SOLVER (SuperLU factorized)
        mem_before = get_process_memory_mb()
        t_fac_0 = time.perf_counter()
        solve_fac = spla.factorized(K_free.tocsc())
        t_fac = time.perf_counter() - t_fac_0

        # Primal solve
        t_sol_0 = time.perf_counter()
        u_free_dir = solve_fac(f_free)
        t_sol_dir = time.perf_counter() - t_sol_0

        # Adjoint solve (reusing factor)
        t_adj_0 = time.perf_counter()
        z_free_dir = solve_fac(g_free)
        t_adj_dir = time.perf_counter() - t_adj_0
        mem_dir = get_process_memory_mb() - mem_before

        res_dir = np.linalg.norm(f_free - K_free.dot(u_free_dir)) / max(np.linalg.norm(f_free), 1e-15)
        qoi_dir = float(np.dot(g_free, u_free_dir))

        print(f"Direct Solver (SuperLU via spla.factorized):")
        print(f"  Factorization: {t_fac*1000.0:.2f} ms | Primal: {t_sol_dir*1000.0:.2f} ms | Adjoint (Reuse): {t_adj_dir*1000.0:.2f} ms")
        print(f"  Total Time: {(t_fac + t_sol_dir + t_adj_dir)*1000.0:.2f} ms | Relative Residual: {res_dir:.2e} | QoI: {qoi_dir*1000.0:.5f} mm")

        # 2. CG UNPRECONDITIONED (Identity)
        t_cg_0 = time.perf_counter()
        res_cg_primal = cg.solve(K_free, f_free, preconditioner=IdentityPreconditioner())
        t_cg_primal = time.perf_counter() - t_cg_0

        t_cg_adj_0 = time.perf_counter()
        res_cg_adj = cg.solve(K_free, g_free, preconditioner=IdentityPreconditioner())
        t_cg_adj = time.perf_counter() - t_cg_adj_0

        qoi_cg = float(np.dot(g_free, res_cg_primal.x))
        e_rel_u_cg = np.linalg.norm(res_cg_primal.x - u_free_dir) / np.linalg.norm(u_free_dir)
        e_rel_j_cg = abs(qoi_cg - qoi_dir) / abs(qoi_dir)

        print(f"Unpreconditioned CG:")
        print(f"  Primal: {res_cg_primal.iterations} iters, {t_cg_primal*1000.0:.2f} ms | Adjoint: {res_cg_adj.iterations} iters, {t_cg_adj*1000.0:.2f} ms")
        print(f"  Total Time: {(t_cg_primal + t_cg_adj)*1000.0:.2f} ms | Rel Res: {res_cg_primal.relative_residual:.2e}")
        print(f"  e_rel_u: {e_rel_u_cg:.2e} | e_rel_J: {e_rel_j_cg:.2e}")

        # 3. JACOBI-PCG
        t_jac_setup_0 = time.perf_counter()
        jac_prec = JacobiPreconditioner(K_free)
        t_jac_setup = time.perf_counter() - t_jac_setup_0

        t_jac_primal_0 = time.perf_counter()
        res_jac_primal = cg.solve(K_free, f_free, preconditioner=jac_prec)
        t_jac_primal = time.perf_counter() - t_jac_primal_0

        t_jac_adj_0 = time.perf_counter()
        res_jac_adj = cg.solve(K_free, g_free, preconditioner=jac_prec)
        t_jac_adj = time.perf_counter() - t_jac_adj_0

        qoi_jac = float(np.dot(g_free, res_jac_primal.x))
        e_rel_u_jac = np.linalg.norm(res_jac_primal.x - u_free_dir) / np.linalg.norm(u_free_dir)
        e_rel_j_jac = abs(qoi_jac - qoi_dir) / abs(qoi_dir)

        print(f"Jacobi-PCG:")
        print(f"  Setup: {t_jac_setup*1000.0:.2f} ms | Primal: {res_jac_primal.iterations} iters, {t_jac_primal*1000.0:.2f} ms | Adjoint: {res_jac_adj.iterations} iters, {t_jac_adj*1000.0:.2f} ms")
        print(f"  Total Time: {(t_jac_setup + t_jac_primal + t_jac_adj)*1000.0:.2f} ms | Rel Res: {res_jac_primal.relative_residual:.2e}")
        print(f"  e_rel_u: {e_rel_u_jac:.2e} | e_rel_J: {e_rel_j_jac:.2e}")

        # 4. INCOMPLETE CHOLESKY IC(0)-PCG (for small to medium systems)
        if n_dofs <= 3000:
            try:
                t_ic_setup_0 = time.perf_counter()
                ic_prec = IncompleteCholeskyPreconditioner(K_free)
                t_ic_setup = time.perf_counter() - t_ic_setup_0

                t_ic_primal_0 = time.perf_counter()
                res_ic_primal = cg.solve(K_free, f_free, preconditioner=ic_prec)
                t_ic_primal = time.perf_counter() - t_ic_primal_0

                t_ic_adj_0 = time.perf_counter()
                res_ic_adj = cg.solve(K_free, g_free, preconditioner=ic_prec)
                t_ic_adj = time.perf_counter() - t_ic_adj_0

                qoi_ic = float(np.dot(g_free, res_ic_primal.x))
                e_rel_u_ic = np.linalg.norm(res_ic_primal.x - u_free_dir) / np.linalg.norm(u_free_dir)
                e_rel_j_ic = abs(qoi_ic - qoi_dir) / abs(qoi_dir)

                print(f"Incomplete Cholesky IC(0)-PCG:")
                print(f"  Setup: {t_ic_setup*1000.0:.2f} ms | Primal: {res_ic_primal.iterations} iters, {t_ic_primal*1000.0:.2f} ms | Adjoint: {res_ic_adj.iterations} iters, {t_ic_adj*1000.0:.2f} ms")
                print(f"  Total Time: {(t_ic_setup + t_ic_primal + t_ic_adj)*1000.0:.2f} ms | Rel Res: {res_ic_primal.relative_residual:.2e}")
                print(f"  e_rel_u: {e_rel_u_ic:.2e} | e_rel_J: {e_rel_j_ic:.2e}")
            except Exception as e:
                print(f"Incomplete Cholesky IC(0)-PCG: Failed with exception: {e}")
        else:
            print("Incomplete Cholesky IC(0)-PCG: Skipped for N > 3000 (Pure Python IC(0) setup complexity).")


def run_tolerance_vs_qoi_study():
    print("=" * 80)
    print("PHASE 4.6: ENGINEERING QoI ERROR VS LINEAR SOLVER TOLERANCE")
    print("=" * 80)

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=24, ny=12)
    basis = solver.create_basis(mesh)
    K = solver.assemble_stiffness(basis)
    f = solver.assemble_traction(mesh, "right", 0.0, -1e6)
    g = solver.assemble_qoi_adjoint_vector(mesh, "right", "y")
    dofs_fixed = solver.find_dirichlet_dofs(basis, mesh, "left", ["x", "y"])

    K_free, f_free, _, I = fem.condense(K, f, D=dofs_fixed)
    g_free = g[I]

    solve_fac = spla.factorized(K_free.tocsc())
    u_ref = solve_fac(f_free)
    qoi_ref = float(np.dot(g_free, u_ref))

    tolerances = [1e-1, 1e-2, 1e-3, 1e-4, 1e-6, 1e-8, 1e-10, 1e-12]
    cg = ConjugateGradientSolver()
    prec = JacobiPreconditioner(K_free)

    print(f"Reference QoI: {qoi_ref*1000.0:.6f} mm (N_free = {K_free.shape[0]})")
    print(f"{'Tolerance (rtol)':<18} | {'Iterations':<11} | {'Final Rel Res':<16} | {'e_rel,u (Disp Error)':<22} | {'e_rel,J (QoI Error)':<22}")
    print("-" * 95)

    for tol in tolerances:
        res = cg.solve(K_free, f_free, preconditioner=prec, rtol=tol, atol=1e-15)
        qoi_val = float(np.dot(g_free, res.x))
        e_u = np.linalg.norm(res.x - u_ref) / np.linalg.norm(u_ref)
        e_j = abs(qoi_val - qoi_ref) / abs(qoi_ref)
        print(f"{tol:<18.1e} | {res.iterations:<11} | {res.relative_residual:<16.2e} | {e_u:<22.2e} | {e_j:<22.2e}")

    print()


if __name__ == "__main__":
    run_matrix_verification_study()
    run_conditioning_scaling_study()
    run_solver_benchmarking()
    run_tolerance_vs_qoi_study()
