# GDEC v0.2.2 Benchmark Reproduction Suite

This directory contains reproduction configurations and scripts for the GDEC v0.2.2 benchmarks.

## 1. Benchmark Problem Description
- Model: 2D Cantilever Beam under tip shear traction.
- Source: `examples/cantilever.gdc`.
- Quantity of Interest: Average vertical tip displacement $J$.

## 2. Historical Reference Artifacts
Preserved in `results/v022/`:
- `CantileverDemo_benchmark.json`: Complete execution metrics and strategy comparison.
- `CantileverDemo_iterations.csv`: Per-iteration DOFs, QoI, error, and timings.
- `CantileverDemo_equal_accuracy.csv`: Equal-accuracy Pareto evaluation.
- `benchmark_reference_comparison.json`: Four-level Richardson convergence analysis.
- `performance_deep_audit.json`: SuperLU factorization reuse and solver timings.

## 3. Running the Benchmark
```powershell
python benchmarks/scripts/reproduce_benchmarks.py
```
Or via CLI:
```powershell
gdec benchmark examples/cantilever.gdc --ref-dofs 30000 --out-dir results/reproduced
```
