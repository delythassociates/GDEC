# GDEC v0.2.2 Known Limitations & Review Notes

In compliance with scientific audit standards, this document lists all known limitations of the current codebase:

1. **Hardware & Accelerator Execution**:
   - GDEC v0.2.2 executes entirely on the CPU.
   - Although physical NVIDIA GPUs are detected for hardware telemetry, no GPU/CUDA computation backend is implemented in v0.2.2.
   - Any attempt to specify `backend = cuda` is rejected by the semantic validator.

2. **Finite Element Formulation**:
   - Only 2D linear static elasticity with 3-node triangular elements (P1) is implemented.
   - High-order elements (P2, Q1, Q2) and 3D elasticity are not yet supported.
   - Linear triangles exhibit bending-stiffness bias on coarse meshes before refinement.

3. **Error Estimator Theoretical Status**:
   - The goal-aware indicator `goal_heuristic_v1` is an adjoint-informed ranking heuristic, not a certified Dual-Weighted Residual (DWR) bound.
   - The rank correlation with true error reduction is strong (Spearman $\rho = 0.81$), but rigorous mathematical upper bounds require full residual jump integration.

4. **Net Wall-Clock Time on Small Meshes**:
   - While Goal-Aware adaptivity reduces degrees of freedom by $1.37\times$ to $2.50\times$, net wall-clock time on very small meshes (< 5,000 DOFs) is comparable to or slightly higher than uniform refinement due to Python overhead in element marking and dual solve setup.
   - Factorization reuse achieves a $1.96\times - 2.00\times$ speedup on the isolated linear solve, translating to $1.42\times - 1.65\times$ overall pipeline speedup.
