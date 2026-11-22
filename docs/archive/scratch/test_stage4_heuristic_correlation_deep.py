"""
scratch/test_stage4_heuristic_correlation_deep.py
Thorough verification of the goal-heuristic correlation:
Tests correlation between element refinement indicator and ACTUAL error reduction:
  error_before = abs(J_ref - J_initial)
  error_after = abs(J_ref - J_refined)
  error_reduction = error_before - error_after

Evaluates:
1. 8-group partition (reproducing original v0.2.1 test)
2. All individual elements (N = 64 individual element refinements)
3. Using Level 3 reference, Level 4 reference, and Richardson extrapolated J_infinity
4. Computes Spearman rho, p-value, Pearson r, p-value
"""

import sys
sys.path.insert(0, r"f:\fem-edit-benchmark\src")
import json
import numpy as np
import scipy.stats as stats
from pathlib import Path

from gdec.compiler import GDECCompiler
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.estimators import RefinementEstimator

# Setup problem
compiler = GDECCompiler()
ir = compiler.compile_source(open("f:/fem-edit-benchmark/examples/cantilever.gdc").read()).ir
ct = ConstitutiveTensor.from_properties(E=ir.material.E, nu=ir.material.nu, assumption=ir.material.assumption, thickness=ir.geometry.thickness)
solver = LinearElasticitySolver(ct)
loads = [("right", 0.0, ir.loads[0].ty)]
fixed = [("left", ["x", "y"])]

# Initial coarse mesh (9x5 grid = 64 elements, 90 DOFs)
mesh0 = GDECMesh.create_cantilever_mesh(width=ir.geometry.width, height=ir.geometry.height, nx=9, ny=5)
sol0 = solver.solve(mesh0, loads, fixed, solve_adjoint=True)
J0 = sol0.qoi_mm

# Estimator
estimator = RefinementEstimator(ct)
goal_res = estimator.compute_goal_heuristic_v1_indicator(mesh0, sol0, cost_aware=False)
eta_goal = goal_res.indicators  # (64,)

# References
ref_L3 = -1.90729549
ref_L4 = -1.90802421
ref_inf = -1.90923950

refs = {
    "Level 3 (29.8k DOFs)": ref_L3,
    "Level 4 (45.0k DOFs)": ref_L4,
    "Richardson J_inf": ref_inf
}

print(f"Initial mesh: {mesh0.nelements} elements, J0 = {J0:.6f} mm")

# --- EXPERIMENT 1: 8-GROUP PARTITION ---
print("\n=== EXPERIMENT 1: 8-GROUP PARTITION ===")
order = np.argsort(eta_goal)
groups = np.array_split(order, 8)

grp_results = {}
for r_name, j_ref in refs.items():
    e_before = abs(j_ref - J0)
    grp_etas = []
    grp_deltas = []
    
    for idx, grp in enumerate(groups):
        mean_eta = float(np.mean(eta_goal[grp]))
        m_ref = mesh0.refine_elements(grp)
        sol_ref = solver.solve(m_ref, loads, fixed, solve_adjoint=False)
        e_after = abs(j_ref - sol_ref.qoi_mm)
        delta_e = e_before - e_after
        grp_etas.append(mean_eta)
        grp_deltas.append(delta_e)
        
    rho_s, p_s = stats.spearmanr(grp_etas, grp_deltas)
    r_p, p_p = stats.pearsonr(grp_etas, grp_deltas)
    
    grp_results[r_name] = {
        "N": len(groups),
        "spearman_rho": float(rho_s),
        "spearman_p": float(p_s),
        "pearson_r": float(r_p),
        "pearson_p": float(p_p),
        "etas": grp_etas,
        "delta_e": grp_deltas,
    }
    print(f"Ref: {r_name:<24} | Spearman rho = {rho_s:.4f} (p={p_s:.4e}) | Pearson r = {r_p:.4f} (p={p_p:.4e})")

# --- EXPERIMENT 2: ELEMENT-BY-ELEMENT REFINEMENT (N = 64) ---
print("\n=== EXPERIMENT 2: ALL 64 INDIVIDUAL ELEMENTS ===")
elem_results = {}
for r_name, j_ref in refs.items():
    e_before = abs(j_ref - J0)
    elem_etas = []
    elem_deltas = []
    
    for e_idx in range(mesh0.nelements):
        val_eta = float(eta_goal[e_idx])
        m_ref = mesh0.refine_elements([e_idx])
        sol_ref = solver.solve(m_ref, loads, fixed, solve_adjoint=False)
        e_after = abs(j_ref - sol_ref.qoi_mm)
        delta_e = e_before - e_after
        elem_etas.append(val_eta)
        elem_deltas.append(delta_e)
        
    rho_s, p_s = stats.spearmanr(elem_etas, elem_deltas)
    r_p, p_p = stats.pearsonr(elem_etas, elem_deltas)
    
    elem_results[r_name] = {
        "N": mesh0.nelements,
        "spearman_rho": float(rho_s),
        "spearman_p": float(p_s),
        "pearson_r": float(r_p),
        "pearson_p": float(p_p),
    }
    print(f"Ref: {r_name:<24} | Spearman rho = {rho_s:.4f} (p={p_s:.4e}) | Pearson r = {r_p:.4f} (p={p_p:.4e})")

out_file = Path("results/v022/goal_heuristic_correlation.json")
with open(out_file, "w") as fp:
    json.dump({"group_8": grp_results, "individual_64": elem_results}, fp, indent=2)

print(f"\nSaved correlation verification to {out_file}")
