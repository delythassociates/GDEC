# GDEC v0.2.3 Known Limitations & Review Notes

In compliance with scientific audit standards, this document lists all known limitations of the current codebase:

1. **Hardware & Accelerator Execution**:
   - GDEC v0.2.3 executes entirely on the CPU.
   - Although physical NVIDIA GPUs are detected for hardware telemetry, no GPU/CUDA computation backend is implemented in v0.2.3.
   - Any attempt to specify `backend = cuda` is rejected by the semantic validator with an informative explanation.

2. **Finite Element Formulation**:
   - 2D linear static elasticity with 3-node triangular elements (P1) is implemented for plane stress and plane strain.
   - Point displacement QoIs $u_i(x_0, y_0)$ are supported via P1 barycentric interpolation adjoint assembly.
   - High-order elements (P2, Q1, Q2) and 3D elasticity are planned for future versions.
   - Linear triangles exhibit bending-stiffness bias on coarse meshes before refinement.

3. **Error Estimator Theoretical Status**:
   - The goal-aware indicator `goal_heuristic_v1` is an adjoint-informed ranking heuristic, not a certified Dual-Weighted Residual (DWR) bound.
   - The rank correlation with true error reduction is strong (Spearman $\rho = 0.81$), but rigorous mathematical upper bounds require full residual jump integration.
   - Zienkiewicz-Zhu (ZZ) recovery uses exact degree-2 Dunavant/Hammer 3-point midpoint triangle quadrature for the energy norm.

4. **Net Wall-Clock Time on Small Meshes**:
   - Goal-Aware adaptivity reduces degrees of freedom by $1.12\times$ to $2.34\times$ at matched accuracy thresholds.
   - However, net wall-clock time on small meshes (< 10,000 DOFs) is comparable to or slightly higher than uniform refinement due to Python overhead in element marking and dual solve setup.
   - Factorization reuse achieves a $1.96\times - 2.00\times$ speedup on the isolated linear solve, translating to $1.42\times - 1.65\times$ overall pipeline speedup.
   - The research hypothesis is therefore classified as `PARTIALLY_SUPPORTED` (spatial DOF efficiency confirmed; wall-clock superiority equivocal on small meshes).
