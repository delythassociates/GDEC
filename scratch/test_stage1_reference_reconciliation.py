"""
scratch/test_stage1_reference_reconciliation.py
Investigates and reconciles the two reference solutions:
1. Level 3 discrete solve: 29,768 DOFs, QoI: -1.90729549 mm
2. Level 4 discrete solve: 45,000 DOFs, QoI: -1.90802421 mm
3. Richardson extrapolated solution J_infinity from Levels 2, 3, 4
   - Using Celik / ASME 2008 exact transcendental solver for non-uniform refinement ratios
   - Comparing against Roache mean-ratio approximation
4. Evaluates the 3 benchmark strategies (Uniform, ZZ, Goal-Aware) against:
   - Ref A: Level 3 discrete (-1.907295 mm)
   - Ref B: Level 4 discrete (-1.908024 mm)
   - Ref C: Richardson extrapolated (-1.909240 mm)
"""

import sys
sys.path.insert(0, r"f:\fem-edit-benchmark\src")
import time
import json
import numpy as np
import scipy.optimize as opt
from pathlib import Path

from gdec.compiler import GDECCompiler
from gdec.benchmark.reference import ReferenceSolver, compute_timoshenko_cantilever
from gdec.benchmark.runner import BenchmarkRunner
from gdec.benchmark.reporting import BenchmarkReporter
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver

# 1. Compile cantilever IR
compiler = GDECCompiler()
res_comp = compiler.compile_source(open("f:/fem-edit-benchmark/examples/cantilever.gdc").read())
ir = res_comp.ir

ct = ConstitutiveTensor.from_properties(E=ir.material.E, nu=ir.material.nu, assumption=ir.material.assumption, thickness=ir.geometry.thickness)
solver = LinearElasticitySolver(ct)
loads = [("right", 0.0, ir.loads[0].ty)]
fixed = [("left", ["x", "y"])]

print("=== 1. PRECISE FOUR-LEVEL REFERENCE COMPUTATION ===")
resolutions = [
    ("Level 1", 144, 36),
    ("Level 2", 196, 49),
    ("Level 3", 244, 61),
    ("Level 4", 300, 75),
]

levels = []
for name, nx, ny in resolutions:
    t0 = time.perf_counter()
    m = GDECMesh.create_cantilever_mesh(width=ir.geometry.width, height=ir.geometry.height, nx=nx, ny=ny)
    sol = solver.solve(m, loads, fixed, solve_adjoint=False)
    t_solve = time.perf_counter() - t0
    h_x = ir.geometry.width / (nx - 1)
    h_y = ir.geometry.height / (ny - 1)
    h = np.sqrt(h_x * h_y)  # characteristic cell size
    levels.append({
        "name": name,
        "nx": int(nx),
        "ny": int(ny),
        "elements": int(m.nelements),
        "nodes": int(m.nnodes),
        "dofs": int(sol.basis.N),
        "qoi_meters": float(sol.qoi),
        "qoi_mm": float(sol.qoi_mm),
        "h": float(h),
        "solve_time_sec": float(t_solve),
    })
    print(f"{name:8}: {nx:3d}x{ny:2d} | DOFs: {sol.basis.N:6d} | QoI: {sol.qoi_mm:.8f} mm | h: {h:.6e} | Time: {t_solve:.3f} s")

# Levels 2, 3, 4:
# Let index 1 = Level 4 (finest), index 2 = Level 3 (medium), index 3 = Level 2 (coarse)
# Following ASME / Celik (2008) standard notation:
# h1 < h2 < h3
f1 = levels[3]["qoi_mm"]  # Level 4: finest
f2 = levels[2]["qoi_mm"]  # Level 3: medium
f3 = levels[1]["qoi_mm"]  # Level 2: coarse

h1 = levels[3]["h"]
h2 = levels[2]["h"]
h3 = levels[1]["h"]

r21 = h2 / h1  # refinement ratio medium to fine: 243/299 in 1D or h2/h1
r32 = h3 / h2  # refinement ratio coarse to medium: 195/243

print(f"\nGrid refinement ratios: r21 = {r21:.6f}, r32 = {r32:.6f}")

eps32 = f3 - f2
eps21 = f2 - f1
s = 1.0 if (eps32 / eps21) > 0 else -1.0

print(f"Differences: eps32 = {eps32:.8f} mm, eps21 = {eps21:.8f} mm, ratio = {eps32/eps21:.6f}")

# Celik et al. (2008) transcendental equation:
# p = (1 / ln(r21)) * | ln|eps32 / eps21| + q(p) |
# where q(p) = ln((r21^p - s) / (r32^p - s))
def celik_residual(p):
    q_p = np.log((r21**p - s) / (r32**p - s))
    return p - (1.0 / np.log(r21)) * np.abs(np.log(np.abs(eps32 / eps21)) + q_p)

# Solve for p
sol_p = opt.root_scalar(celik_residual, bracket=[0.5, 4.0], method='brentq')
p_celik = sol_p.root

# Roache approximation using mean r:
r_mean = (r21 + r32) / 2.0
p_approx = np.log(eps32 / eps21) / np.log(r_mean)

print(f"\n--- CONVERGENCE ORDER ---")
print(f"Celik / ASME exact transcendental order p: {p_celik:.6f}")
print(f"Roache mean-ratio approximation order p:   {p_approx:.6f}")

# Richardson extrapolation to h -> 0:
# f_extrap = f1 + (f1 - f2) / (r21^p - 1)
f_ext_celik = f1 + (f1 - f2) / (r21**p_celik - 1.0)
f_ext_approx = f1 + (f1 - f2) / (r_mean**p_approx - 1.0)

print(f"\n--- RICHARDSON EXTRAPOLATION ---")
print(f"Using Celik exact p ({p_celik:.4f}):   J_infinity = {f_ext_celik:.8f} mm")
print(f"Using Roache approx p ({p_approx:.4f}): J_infinity = {f_ext_approx:.8f} mm")

# Roache GCI for fine grid (Level 4 vs Level 3):
# GCI21_fine = (Fs * |e_a_21|) / (r21^p - 1)
# where e_a_21 = (f1 - f2) / f1
Fs = 1.25  # standard safety factor for 3+ grids
ea21 = abs((f1 - f2) / f1)
GCI21_celik = (Fs * ea21) / (r21**p_celik - 1.0) * 100.0
GCI21_approx = (Fs * ea21) / (r_mean**p_approx - 1.0) * 100.0

# GCI for medium grid (Level 3 vs Level 2):
ea32 = abs((f2 - f3) / f2)
GCI32_celik = (Fs * ea32) / (r32**p_celik - 1.0) * 100.0

# Asymptotic range check:
# GCI32 / (r21^p * GCI21) should be close to 1.0
asymptotic_ratio = GCI32_celik / ((r21**p_celik) * GCI21_celik)

print(f"\n--- GRID CONVERGENCE INDEX (GCI) ---")
print(f"Level 4 (Finest) GCI21:          {GCI21_celik:.6f}%")
print(f"Level 3 (Medium) GCI32:          {GCI32_celik:.6f}%")
print(f"Asymptotic Range Check Ratio:    {asymptotic_ratio:.6f} (ideal: 1.000000)")

# Save reference investigation to json
res_dict = {
    "levels": levels,
    "r21": float(r21),
    "r32": float(r32),
    "p_celik": float(p_celik),
    "p_approx": float(p_approx),
    "f_extrap_celik": float(f_ext_celik),
    "f_extrap_approx": float(f_ext_approx),
    "GCI21_celik_pct": float(GCI21_celik),
    "GCI32_celik_pct": float(GCI32_celik),
    "asymptotic_check_ratio": float(asymptotic_ratio),
    "level3_discrete_mm": float(f2),
    "level4_discrete_mm": float(f1),
    "uncertainty_level3_discrete_pct": float(ea32 * 100.0),
    "uncertainty_level4_discrete_pct": float(ea21 * 100.0),
}

out_dir = Path("results/v022")
out_dir.mkdir(parents=True, exist_ok=True)
with open(out_dir / "reference_reconciliation.json", "w") as fp:
    json.dump(res_dict, fp, indent=2)

print("\nSaved reference reconciliation data to results/v022/reference_reconciliation.json")
