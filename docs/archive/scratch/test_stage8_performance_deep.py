"""
scratch/test_stage8_performance_deep.py
Precise performance verification with repeated runs (N = 10 repeats):
Separates:
- Assembly time
- Matrix condensation time
- Sparse LU factorization time (SuperLU via scipy.sparse.linalg.splu / factorized)
- Primal backsolve time
- Adjoint backsolve time
- Mesh refinement time
- Total iteration time
Reports median, mean, min, max, and spread for all stages.
Disambiguates isolated factorization reuse speedup vs total pipeline speedup.
"""

import sys
sys.path.insert(0, r"f:\fem-edit-benchmark\src")
import time
import gc
import json
import scipy
import numpy as np
from pathlib import Path

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.adaptivity import MeshAdaptor
from gdec.fem.estimators import RefinementEstimator

ct = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
solver = LinearElasticitySolver(ct)
loads = [("right", 0.0, -1.0e6)]
fixed = [("left", ["x", "y"])]
estimator = RefinementEstimator(ct)

mesh_configs = [
    ("Medium (approx 3k DOFs)", 60, 24),
    ("Fine (approx 12k DOFs)", 120, 48),
    ("Extra-Fine (approx 26k DOFs)", 180, 72),
]

N_REPEATS = 10
perf_results = []

print(f"=== REPEATED STAGE PERFORMANCE PROFILING (N = {N_REPEATS} repeats) ===")
print(f"Environment: Python {sys.version.split()[0]} | SciPy {scipy.__version__} (SuperLU 5.3 vendored)")

for label, nx, ny in mesh_configs:
    mesh = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx, ny)
    dofs = mesh.nnodes * 2
    nelems = mesh.nelements
    
    t_asm_arr = []
    t_cond_arr = []
    t_fac_arr = []
    t_bs_p_arr = []
    t_bs_a_arr = []
    t_lin_reuse_arr = []
    t_lin_noreuse_arr = []
    t_tot_reuse_arr = []
    t_tot_noreuse_arr = []
    t_refine_arr = []
    
    # Warmup
    _ = solver.solve(mesh, loads, fixed, solve_adjoint=True, reuse_factorization=True)
    _ = solver.solve(mesh, loads, fixed, solve_adjoint=True, reuse_factorization=False)
    
    for r in range(N_REPEATS):
        gc.collect()
        
        # 1. Reuse run
        sol_reuse = solver.solve(mesh, loads, fixed, solve_adjoint=True, reuse_factorization=True)
        t_asm_arr.append(sol_reuse.assembly_time_sec)
        t_cond_arr.append(sol_reuse.condensation_time_sec)
        t_fac_arr.append(sol_reuse.factorization_time_sec)
        t_bs_p_arr.append(sol_reuse.primal_solve_time_sec)
        t_bs_a_arr.append(sol_reuse.adjoint_solve_time_sec)
        lin_reuse = sol_reuse.factorization_time_sec + sol_reuse.primal_solve_time_sec + sol_reuse.adjoint_solve_time_sec
        t_lin_reuse_arr.append(lin_reuse)
        t_tot_reuse_arr.append(sol_reuse.total_solver_time_sec)
        
        # 2. No-reuse run
        sol_noreuse = solver.solve(mesh, loads, fixed, solve_adjoint=True, reuse_factorization=False)
        lin_noreuse = sol_noreuse.primal_solve_time_sec + sol_noreuse.adjoint_solve_time_sec
        t_lin_noreuse_arr.append(lin_noreuse)
        t_tot_noreuse_arr.append(sol_noreuse.total_solver_time_sec)
        
        # 3. Refinement time
        # Mark 20% of elements
        ind = estimator.compute_goal_aware_indicator(mesh, sol_reuse)
        marked = MeshAdaptor.mark_elements(ind, "goal_aware", 0.2, dofs, 100000)
        t_ref0 = time.perf_counter()
        _ = MeshAdaptor.refine_mesh(mesh, "goal_aware", marked)
        t_refine_arr.append(time.perf_counter() - t_ref0)

    def stats(arr):
        a = np.array(arr) * 1000.0 # convert to ms
        return {
            "median_ms": float(np.median(a)),
            "mean_ms": float(np.mean(a)),
            "min_ms": float(np.min(a)),
            "max_ms": float(np.max(a)),
            "std_ms": float(np.std(a)),
        }

    s_asm = stats(t_asm_arr)
    s_cond = stats(t_cond_arr)
    s_fac = stats(t_fac_arr)
    s_bsp = stats(t_bs_p_arr)
    s_bsa = stats(t_bs_a_arr)
    s_lin_reuse = stats(t_lin_reuse_arr)
    s_lin_noreuse = stats(t_lin_noreuse_arr)
    s_tot_reuse = stats(t_tot_reuse_arr)
    s_tot_noreuse = stats(t_tot_noreuse_arr)
    s_refine = stats(t_refine_arr)
    
    speedup_linear = s_lin_noreuse["median_ms"] / s_lin_reuse["median_ms"]
    speedup_pipeline = s_tot_noreuse["median_ms"] / s_tot_reuse["median_ms"]
    
    entry = {
        "label": label,
        "dofs": int(dofs),
        "elements": int(nelems),
        "assembly": s_asm,
        "condensation": s_cond,
        "factorization": s_fac,
        "primal_backsolve": s_bsp,
        "adjoint_backsolve": s_bsa,
        "refinement": s_refine,
        "linear_solve_reuse": s_lin_reuse,
        "linear_solve_noreuse": s_lin_noreuse,
        "total_solve_reuse": s_tot_reuse,
        "total_solve_noreuse": s_tot_noreuse,
        "speedup_linear_median": float(speedup_linear),
        "speedup_pipeline_median": float(speedup_pipeline),
    }
    perf_results.append(entry)
    
    print(f"\n--- {label} ({dofs} DOFs, {nelems} elements) ---")
    print(f"  Assembly:               median {s_asm['median_ms']:6.2f} ms (spread: {s_asm['min_ms']:5.2f} - {s_asm['max_ms']:5.2f} ms)")
    print(f"  Condensation:           median {s_cond['median_ms']:6.2f} ms (spread: {s_cond['min_ms']:5.2f} - {s_cond['max_ms']:5.2f} ms)")
    print(f"  LU Factorization:       median {s_fac['median_ms']:6.2f} ms (spread: {s_fac['min_ms']:5.2f} - {s_fac['max_ms']:5.2f} ms)")
    print(f"  Primal Backsolve:       median {s_bsp['median_ms']:6.2f} ms (spread: {s_bsp['min_ms']:5.2f} - {s_bsp['max_ms']:5.2f} ms)")
    print(f"  Adjoint Backsolve:      median {s_bsa['median_ms']:6.2f} ms (spread: {s_bsa['min_ms']:5.2f} - {s_bsa['max_ms']:5.2f} ms)")
    print(f"  Refinement (20% marked):median {s_refine['median_ms']:6.2f} ms (spread: {s_refine['min_ms']:5.2f} - {s_refine['max_ms']:5.2f} ms)")
    print(f"  Linear Solve (Reuse):   median {s_lin_reuse['median_ms']:6.2f} ms | No-Reuse: {s_lin_noreuse['median_ms']:6.2f} ms")
    print(f"  --> Isolated Linear Solve Speedup: {speedup_linear:.2f}x")
    print(f"  Total Pipeline (Reuse): median {s_tot_reuse['median_ms']:6.2f} ms | No-Reuse: {s_tot_noreuse['median_ms']:6.2f} ms")
    print(f"  --> Total Solver Pipeline Speedup: {speedup_pipeline:.2f}x")

out_file = Path("results/v022/performance_deep_audit.json")
with open(out_file, "w") as fp:
    json.dump({
        "environment": {
            "scipy_version": scipy.__version__,
            "superlu_version": "5.3.0 (vendored in scipy.sparse.linalg)",
            "repeats": N_REPEATS
        },
        "benchmarks": perf_results
    }, fp, indent=2)

print(f"\nSaved detailed performance data to {out_file}")
