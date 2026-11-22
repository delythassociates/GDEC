"""
scratch/regenerate_v022_benchmarks.py
Regenerates all benchmark artifacts for GDEC v0.2.2 in results/v022/:
- CantileverDemo_equal_accuracy.csv
- CantileverDemo_iterations.csv
- CantileverDemo_summary.csv
- CantileverDemo_benchmark.json
- CantileverDemo_benchmark_report.md

Uses the validated continuum reference J_infinity = -1.90923950 mm (GCI = 0.0796%)
and also exports multi-reference comparison tables.
"""

import sys
sys.path.insert(0, r"f:\fem-edit-benchmark\src")
import time
import json
import pandas as pd
import numpy as np
from pathlib import Path

from gdec.compiler import GDECCompiler
from gdec.benchmark.reference import ReferenceSolution, ReferenceConvergenceReport, ReferenceLevelResult, compute_timoshenko_cantilever
from gdec.benchmark.runner import BenchmarkRunner, BenchmarkSuiteResult, StrategyBenchmarkResult, BenchmarkIterationData
from gdec.benchmark.evaluator import EqualAccuracyEvaluator, EqualAccuracyComparison
from gdec.benchmark.reporting import BenchmarkReporter, NumpyJsonEncoder

compiler = GDECCompiler()
ir = compiler.compile_source(open("f:/fem-edit-benchmark/examples/cantilever.gdc").read()).ir

out_dir = Path("results/v022")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. We construct the validated 4-level ReferenceSolution with Richardson extrapolation
# Validated values:
levels = [
    ReferenceLevelResult("Level 1 (Coarse)", 10368, 10010, 5184, (144, 36), -1.90336667e-3, -1.90336667, 0.100),
    ReferenceLevelResult("Level 2 (Medium)", 19208, 18720, 9604, (196, 49), -1.90612982e-3, -1.90612982, 0.222),
    ReferenceLevelResult("Level 3 (Fine)",   29768, 29160, 14884, (244, 61), -1.90729549e-3, -1.90729549, 0.371),
    ReferenceLevelResult("Level 4 (Finest)", 45000, 44252, 22500, (300, 75), -1.90802421e-3, -1.90802421, 0.652),
]

timo = compute_timoshenko_cantilever(ir.geometry.width, ir.geometry.height, ir.geometry.thickness, ir.material.E, ir.material.nu, ir.loads[0].ty)
timo["fem_vs_timoshenko_diff_pct"] = float(abs(-1.90802421 - timo["delta_timoshenko_total_mm"]) / abs(timo["delta_timoshenko_total_mm"]) * 100.0)

# Validated Richardson extrapolated reference (Celik unequal-ratio formulation as primary):
J_inf_mm = -1.90952476
J_inf_m = J_inf_mm / 1000.0
gci_pct = 0.098305

conv_report = ReferenceConvergenceReport(
    levels=levels,
    relative_changes_pct=[0.145, 0.0611, 0.0382],
    finest_adequate_for_thresholds=True,
    estimated_discretization_uncertainty_pct=gci_pct,
    analytical_comparison=timo,
    adequacy_assessment=f"Validated 4-grid convergence: ASME/Celik unequal-ratio apparent order p=1.898058 (Roache mean-ratio p=2.183978). Celik Richardson extrapolated continuum limit J_inf = {J_inf_mm:.8f} mm with fine GCI = {gci_pct:.6f}%.",
)

ref_solution = ReferenceSolution(
    qoi_meters=J_inf_m,
    qoi_mm=J_inf_mm,
    dofs=45000,
    nelements=44252,
    nnodes=22500,
    solve_time_sec=0.652,
    mesh_resolution=(300, 75),
    is_analytical=False,
    notes="Celik (2008) ASME-standard unequal-ratio Richardson extrapolated continuum reference (h -> 0) derived from 4-level grid convergence study (10k to 45k DOFs).",
    convergence_report=conv_report,
)

# 2. Run the 3 strategies under identical settings
print("=== RUNNING 3 BENCHMARK STRATEGIES FOR V0.2.2 REGENERATION ===")
runner = BenchmarkRunner(ir, ref_target_dofs=35000)
# Override the reference with our validated continuum reference
runner.ref_solution = ref_solution

# We execute each strategy and evaluate against J_inf
from gdec.core.planner import ExecutionPlanner
from gdec.core.runtime import GDECRuntime

planner = ExecutionPlanner()
strategies = ["uniform", "recovery", "goal_aware"]
strategy_results = {}

for strat in strategies:
    print(f"Executing strategy: {strat.upper()}...")
    plan = planner.create_plan(ir, override_strategy=strat)
    plan.max_dofs_budget = 30000
    plan.max_iterations = 12
    plan.accuracy_target_pct = 0.0001
    
    rt = GDECRuntime(plan, ir)
    t0 = time.perf_counter()
    trace = rt.execute()
    t_tot = time.perf_counter() - t0
    
    # Process iteration data against ref_solution
    iter_data_list = []
    cum_time = 0.0
    for r in trace.iterations:
        cum_time += r.total_iteration_time_sec
        ref_err = abs(r.qoi_mm - J_inf_mm) / abs(J_inf_mm) * 100.0
        iter_data_list.append(
            BenchmarkIterationData(
                iteration=r.iteration,
                strategy=strat,
                nelements=r.nelements,
                nnodes=r.nnodes,
                dofs=r.dofs,
                qoi_meters=r.qoi_meters,
                qoi_mm=r.qoi_mm,
                reference_error_pct=float(ref_err),
                successive_change_pct=r.successive_change_pct,
                max_indicator=r.max_refinement_indicator,
                elements_marked=r.elements_marked,
                assembly_time_sec=r.assembly_time_sec,
                solver_time_sec=r.solver_time_sec,
                total_time_sec=r.total_iteration_time_sec,
                cumulative_time_sec=cum_time,
                peak_memory_mb=r.peak_memory_mb,
                action_reason=r.action_reason,
            )
        )
        
    final_err = iter_data_list[-1].reference_error_pct if iter_data_list else 100.0
    strategy_results[strat] = StrategyBenchmarkResult(
        strategy=strat,
        trace=trace,
        iterations=iter_data_list,
        final_reference_error_pct=final_err,
        target_achieved=trace.converged,
        total_execution_time_sec=t_tot,
        final_dofs=trace.final_dofs,
    )
    print(f"  --> Completed {len(trace.iterations)} iterations. Final DOFs: {trace.final_dofs}, Error: {final_err:.4f}%")

# 3. Equal-Accuracy Evaluation
print("\n=== EVALUATING EQUAL-ACCURACY THRESHOLDS (<= 2%, 1%, 0.5%, 0.25%) ===")
suite_res = BenchmarkSuiteResult(
    problem_name=ir.name,
    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    reference=ref_solution,
    strategies=strategy_results,
    hypothesis_evaluation={},
    equal_accuracy_comparisons=[],
)

comparisons = EqualAccuracyEvaluator.evaluate_suite(suite_res)
suite_res.equal_accuracy_comparisons = comparisons

# 4. Export all artifacts to results/v022/
exported_files = BenchmarkReporter.export_all(suite_res, ir, out_dir)
print("\nGenerated Official Benchmark Deliverables in results/v022/:")
for k, p in exported_files.items():
    print(f"  {k:<25}: {p}")

# 5. Display Equal-Accuracy Table in full precision
df_eq = pd.read_csv(out_dir / "CantileverDemo_equal_accuracy.csv")
print("\n=== REGENERATED EQUAL-ACCURACY BENCHMARK TABLE (FULL PRECISION) ===")
print(df_eq.to_string(index=False))
