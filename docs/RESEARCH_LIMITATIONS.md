# Research Limitations & Future Roadmap (v0.1)

In compliance with GDEC scientific integrity standards, this document explicitly records the current limitations and open research challenges in Version 0.1.

## 1. What Is and Is Not Proven in v0.1

### Adjoint Sensitivity Heuristic vs Certified DWR
- **Status**: The element indicator $\eta_e = h_e^2 A_e |\boldsymbol{\epsilon}_e(\mathbf{u}) : \mathbf{C} : \boldsymbol{\epsilon}_e(\mathbf{z})|$ is an adjoint-informed sensitivity heuristic.
- **Limitation**: It is **not** a mathematically certified Dual-Weighted Residual (DWR) upper error bound. In true DWR (Becker & Rannacher), the primal and adjoint residuals are evaluated with higher-order interpolation or patch recovery ($\mathbf{z} - \Pi_h \mathbf{z}$).
- **Roadmap**: Implement certified primal-dual bilinear residual evaluation with higher-order representation in v0.2.

### Linear Triangular Elements (P1)
- **Status**: Version 0.1 employs linear 3-node triangular elements.
- **Limitation**: Linear triangles suffer from shear-locking under pure bending when aspect ratios are large. Coarse meshes predict artificially stiff behavior.
- **Roadmap**: Add 6-node quadratic triangles (P2) and bilinear/biquadratic quad elements.

### Wall-Clock Time vs DOF Trade-off
- **Observation**: While Goal-Aware adaptivity achieves comparable QoI accuracy with fewer degrees of freedom than uniform refinement (typically $\approx 1.2\times$ DOF reduction on the cantilever), its total wall-clock time in v0.1 is slightly higher due to the dual adjoint solve and Python element sorting overhead on small problems.
- **Mitigation in Future Versions**: Adjoint matrix factorization reuse (since $\mathbf{K} = \mathbf{K}^T$, the LU factors are identical and the adjoint requires only an instantaneous back-solve) and compiled C++/Rust/CUDA marking kernels.

### Execution Backends
- **Status**: Only the CPU sparse direct backend is operational in v0.1.
- **Policy**: GDEC explicitly rejects requests for `cuda` or GPU backends until custom GPU kernels are written and verified.

---

## 2. Prior-Art Investigation Checklist

- [ ] Becker & Rannacher (2001), *An Optimal Control Approach to Error Estimation and Mesh Adaptation in Finite Element Methods*.
- [ ] Oden & Prudhomme (2001), *Goal-oriented error estimation and adaptivity for the finite element method*.
- [ ] Zienkiewicz & Zhu (1987), *A simple error estimator and adaptivity for the finite element method*.
- [ ] Ainsworth & Oden (2000), *A Posteriori Error Estimation in Finite Element Analysis*.
- [ ] Dörfler (1996), *A convergent adaptive algorithm for Poisson's equation*.
- [ ] Bangerth & Rannacher (2003), *Adaptive Finite Element Methods for Differential Equations*.
