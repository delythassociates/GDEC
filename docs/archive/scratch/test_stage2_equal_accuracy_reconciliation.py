"""
scratch/test_stage2_equal_accuracy_reconciliation.py
Runs the 3 refinement strategies under identical conditions:
- Uniform refinement
- Area-weighted nodal stress recovery (Recovery_ZZ)
- goal_heuristic_v1 (Goal-Aware)

Evaluates errors relative to:
- Ref A: Level 3 discrete (-1.90729549 mm)
- Ref B: Level 4 discrete (-1.90802421 mm)
- Ref C1: Richardson extrapolated mean-r (-1.90923950 mm)
- Ref C2: Richardson extrapolated Celik exact (-1.90952476 mm)

Finds the first iteration reaching each error threshold:
- 2.0%
- 1.0%
- 0.5%
- 0.25%
"""

import sys
sys.path.insert(0, r"f:\fem-edit-benchmark\src")
import time
import json
import pandas as pd
import numpy as np
from pathlib import Path

from gdec.compiler import GDECCompiler
from gdec.core.planner import ExecutionPlanner
from gdec.core.runtime import GDECRuntime
from gdec.fem.mesh import GDECMesh

compiler = GDECCompiler()
ir = compiler.compile_source(open("f:/fem-edit-benchmark/examples/cantilever.gdc").read()).ir

# 3 References
refs = {
    "Level 3 Discrete (29.8k DOFs)": -1.90729549,
    "Level 4 Discrete (45.0k DOFs)": -1.90802421,
    "Richardson Extrapolated (mean-r)": -1.90923950,
    "Richardson Extrapolated (Celik)": -1.90952476,
}

planner = ExecutionPlanner()
strategies = ["uniform", "recovery", "goal_aware"]
traces = {}

print("=== RUNNING 3 STRATEGIES ===")
for strat in strategies:
    plan = planner.create_plan(ir, override_strategy=strat)
    # Ensure sufficient budget to see full convergence
    plan.max_dofs_budget = 30000
    plan.max_iterations = 15
    plan.accuracy_target_pct = 0.001 # don't stop prematurely on successive change
    
    runtime = GDECRuntime(plan, ir)
    t0 = time.perf_counter()
    trace = runtime.execute()
    t_tot = time.perf_counter() - t0
    traces[strat] = trace
    print(f"Strategy {strat:<12}: {len(trace.iterations)} iterations | Final DOFs: {trace.final_dofs:5d} | Final QoI: {trace.final_qoi_mm:.6f} mm | Time: {t_tot:.2f}s")

# Analyze each reference
thresholds = [2.0, 1.0, 0.5, 0.25]
eval_results = {}

for ref_name, ref_val in refs.items():
    print(f"\n=======================================================")
    print(f"EVALUATION AGAINST: {ref_name} (J_ref = {ref_val:.6f} mm)")
    print(f"=======================================================")
    
    rows = []
    strat_threshold_reach = {strat: {} for strat in strategies}
    
    for strat in strategies:
        trace = traces[strat]
        cum_time = 0.0
        for r in trace.iterations:
            cum_time += r.total_iteration_time_sec
            err = abs(r.qoi_mm - ref_val) / abs(ref_val) * 100.0
            
            # Check thresholds
            for th in thresholds:
                if th not in strat_threshold_reach[strat] and err <= th:
                    strat_threshold_reach[strat][th] = {
                        "iteration": r.iteration,
                        "dofs": int(r.dofs),
                        "err_pct": float(err),
                        "time_sec": float(cum_time),
                        "qoi_mm": float(r.qoi_mm)
                    }
                    
    # Construct comparative table
    for th in thresholds:
        print(f"\n--- Target Threshold: <= {th}% ---")
        g_data = strat_threshold_reach["goal_aware"].get(th)
        u_data = strat_threshold_reach["uniform"].get(th)
        r_data = strat_threshold_reach["recovery"].get(th)
        
        for s_name, data in [("Uniform", u_data), ("Recovery (ZZ)", r_data), ("Goal Aware", g_data)]:
            if data:
                print(f"  {s_name:<15}: Iter {data['iteration']} | DOFs: {data['dofs']:5d} | Actual Error: {data['err_pct']:.4f}% | Time: {data['time_sec']:.3f}s")
            else:
                print(f"  {s_name:<15}: NOT REACHED within budget")
                
        # DOF ratios relative to goal-aware
        if g_data and u_data:
            print(f"  --> DOF Reduction (Uniform / Goal-Aware): {u_data['dofs'] / g_data['dofs']:.2f}x")
        if g_data and r_data:
            print(f"  --> DOF Reduction (Recovery / Goal-Aware): {r_data['dofs'] / g_data['dofs']:.2f}x")

    eval_results[ref_name] = strat_threshold_reach

# Export all iterations and raw data
out_dir = Path("results/v022")
out_dir.mkdir(parents=True, exist_ok=True)
with open(out_dir / "benchmark_reference_comparison.json", "w") as fp:
    json.dump(eval_results, fp, indent=2)

print("\nSaved multi-reference comparison to results/v022/benchmark_reference_comparison.json")
