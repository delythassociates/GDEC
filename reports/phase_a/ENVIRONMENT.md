# Phase A: Environment & Discretization Manifest

## 1. Execution Platform & Hardware

| Parameter | Specification |
|:---|:---|
| **Operating System** | Windows 11 Enterprise (AMD64) |
| **Kernel / OS Build** | Windows NT 10.0.26100.0 |
| **Host Architecture** | x86_64 / AMD64 |
| **Logical Cores** | 16 |
| **Python Runtime** | CPython 3.13.14 (v3.13.14:a329d2a) |

---

## 2. Core Numerical & Scientific Dependencies

| Package | Version | Purpose |
|:---|:---|:---|
| `numpy` | 2.5.5 | Array operations, BLAS linear algebra, vectorized form evaluation |
| `scipy` | 1.18.1 | Sparse matrices (`csr_matrix`, `coo_matrix`), direct sparse solver SuperLU (`spla.spsolve`) |
| `scikit-fem` | 12.0.2 | Finite element bases, quadrature rules, red-green mesh refinement |
| `sympy` | 1.14.0 | Symbolic PDE derivation, exact manufactured solution stress divergence |
| `matplotlib` | 3.10.8 | Verification plot generation and convergence visualization |
| `pytest` | 9.2.0 | Automated verification harness |
| `mypy` | 2.4.1 | Static type checking (0 errors across 41 files) |
| `ruff` | 0.17.6 | Linting and code hygiene (0 errors) |

---

## 3. Discretization Specifications & Conventions

- **Finite Element Family:** Standard 2D Lagrange $P_1$ triangular elements (`ElementTriP1`).
- **Degree of Freedom Ordering:** Interleaved nodal displacement $[u_{x,0}, u_{y,0}, u_{x,1}, u_{y,1}, \dots, u_{x,N-1}, u_{y,N-1}]$.
- **Quadrature Order:**
  - Standard stiffness assembly: default element quadrature ($n_{quad} = 1$ interior point).
  - Body force assembly: high-precision Gaussian integration of order $\ge 6$ (`intorder=6`).
  - Error norm integration: high-precision Gaussian integration of order $\ge 8$ (`intorder=8`).
- **Domain Geometry:** Rectangular domains with width $L$, height $H$.
- **Boundary Conditions:** Strongly condensed Dirichlet DOFs via `skfem.condense`.
- **Refinement Method:** Conforming red-green local bisection (`MeshTri.refined`).
- **Pseudorandom Generation:** `numpy.random.default_rng(12345)` initialized explicitly per mesh generation.

---

## 4. Git Provenance

- **Repository:** `delythassociates/GDEC`
- **Branch:** `phase-a/v022-verification`
- **Root Release Commit:** `789f1f1f8fd43fc1fca65d098ca17bd5714158ea` (v0.2.2 baseline)
- **Preregistration Tag:** `prereg-thresholds` pointing to commit `8a5237d` (frozen verification criteria prior to test execution)
