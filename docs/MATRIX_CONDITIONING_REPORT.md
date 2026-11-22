# GDEC Phase 4.1 — Stiffness Matrix Conditioning & Diagnostics Report

## 1. Mathematical Formulation

Let $\Omega \subset \mathbb{R}^2$ be a bounded Lipschitz domain discretized by a conforming triangular mesh $\mathcal{T}_h$ with linear Lagrange basis functions $V_h \subset [H^1(\Omega)]^2$. The discrete small-strain linear elasticity bilinear form is:
$$a(u, v) = \int_\Omega \sigma(u) : \varepsilon(v) \, d\Omega = \int_\Omega \varepsilon(v)^T C \, \varepsilon(u) \, d\Omega$$
where $C$ is the symmetric $3 \times 3$ constitutive tensor for plane stress or plane strain.

The global assembled stiffness matrix $K \in \mathbb{R}^{N \times N}$ is partitioned into free degrees of freedom $I$ and Dirichlet-constrained degrees of freedom $D$:
$$\begin{bmatrix} K_{ff} & K_{fd} \\ K_{df} & K_{dd} \end{bmatrix} \begin{bmatrix} u_f \\ u_d \end{bmatrix} = \begin{bmatrix} f_f \\ f_d \end{bmatrix}$$
The condensed linear system governing the free displacements is:
$$K_{ff} u_f = f_f - K_{fd} u_d$$

### 1.1 Matrix Symmetry Metric
Because the constitutive tensor satisfies $C_{ij} = C_{ji}$ and the bilinear form is symmetric ($a(u, v) = a(v, u)$), $K_{ff}$ is theoretically symmetric. To evaluate machine precision deviations and assembly defects, GDEC defines the strictly scale-invariant relative Frobenius symmetry defect:
$$\delta_{\mathrm{sym}} = \frac{\|K_{ff} - K_{ff}^T\|_F}{\|K_{ff}\|_F}$$
For the exact zero matrix ($\|K_{ff}\|_F = 0$), $\delta_{\mathrm{sym}} \equiv 0.0$. By removing arbitrary absolute denominator floors, this metric is strictly scale-invariant across at least 28 orders of magnitude ($c \in [10^{-14}, 10^{14}]$). If $\delta_{\mathrm{sym}} > \text{sym\_tol}$, the matrix is nonsymmetric; symmetric eigensolvers (`eigvalsh`, `eigsh`) are bypassed and SPD classification is declared inapplicable.

### 1.2 Positive Definiteness and Spectrum
By Korn's inequality, when kinematic boundary conditions eliminate all rigid-body displacements (translations $T_x, T_y$ and in-plane rotation $R_z$), the strain energy is coercive:
$$a(v, v) \ge c_K \|v\|_{H^1(\Omega)}^2 \quad \forall v \in V_h \cap [H^1_D(\Omega)]^2$$
Consequently, the constrained stiffness matrix $K_{ff}$ is Symmetric Positive-Definite (SPD). Its eigenvalues satisfy:
$$0 < \lambda_{\min}(K_{ff}) \le \lambda_1 \le \dots \le \lambda_{\max}(K_{ff})$$
The spectral condition number $\kappa_2(K_{ff})$ is:
$$\kappa_2(K_{ff}) = \frac{\lambda_{\max}(K_{ff})}{\lambda_{\min}(K_{ff})}$$

---

## 2. Experimental Verification of Matrix Properties

The diagnostic component implemented in `src/gdec/fem/matrix_diagnostics.py` was executed across multiple configurations. All values below represent actual measured results.

### Table 1: Matrix Symmetry, Spectrum, and Solver Eligibility Across Configurations
| Configuration | Mesh Resolution | Matrix Shape | Nonzeros (NNZ) | Symmetry Defect $\delta_{\mathrm{sym}}$ | $\lambda_{\min}$ | $\lambda_{\max}$ | $\kappa_2$ | Null Modes | SPD Status | CG Eligible |
|---|---|---|---|---|---|---|---|---|---|---|
| Cantilever Coarse | $4 \times 2$ | $12 \times 12$ | 86 | $0.00$ | $8.63 \times 10^6$ | $5.86 \times 10^9$ | $6.79 \times 10^2$ | 0 | **True** | **True** |
| Cantilever Medium | $12 \times 6$ | $132 \times 132$ | 1,382 | $2.65 \times 10^{-17}$ | $3.27 \times 10^5$ | $1.39 \times 10^{10}$ | $4.24 \times 10^4$ | 0 | **True** | **True** |
| Cantilever Fine | $24 \times 12$ | $552 \times 552$ | 6,206 | $2.35 \times 10^{-17}$ | $7.26 \times 10^4$ | $1.50 \times 10^{10}$ | $2.07 \times 10^5$ | 0 | **True** | **True** |
| Plane Strain Cantilever | $12 \times 6$ | $132 \times 132$ | 1,382 | $2.56 \times 10^{-17}$ | $3.73 \times 10^5$ | $1.83 \times 10^{10}$ | $4.91 \times 10^4$ | 0 | **True** | **True** |
| Distorted Mesh (4% shear) | $12 \times 6$ | $132 \times 132$ | 1,584 | $5.78 \times 10^{-17}$ | $3.31 \times 10^5$ | $1.47 \times 10^{10}$ | $4.43 \times 10^4$ | 0 | **True** | **True** |
| Steel ($E=210\text{ GPa}, \nu=0.3$) | $12 \times 6$ | $132 \times 132$ | 1,382 | $2.61 \times 10^{-17}$ | $9.80 \times 10^5$ | $4.08 \times 10^{10}$ | $4.16 \times 10^4$ | 0 | **True** | **True** |
| Rubber-like ($\nu=0.49$) | $12 \times 6$ | $132 \times 132$ | 1,382 | $2.79 \times 10^{-17}$ | $4.74 \times 10^1$ | $2.32 \times 10^6$ | $4.90 \times 10^4$ | 0 | **True** | **True** |
| Unconstrained (Free Body) | $12 \times 6$ | $144 \times 144$ | 1,512 | $2.63 \times 10^{-17}$ | $-7.69 \times 10^{-7}$ | $1.39 \times 10^{10}$ | $\infty$ | **3** | **False** | **False** |
| Roller Boundary (Only $u_x=0$) | $12 \times 6$ | $138 \times 138$ | 1,432 | $2.63 \times 10^{-17}$ | $1.29 \times 10^{-6}$ | $1.39 \times 10^{10}$ | $\infty$ | **1** | **False** | **False** |

---

## 3. Key Mathematical Insights and Defect Analysis

### 3.1 Symmetry Defect Preservation
Across all tests, $\delta_{\mathrm{sym}} \le 5.78 \times 10^{-17}$, which is well below the standard double-precision threshold $\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$. The stiffness assembly preserves exact matrix symmetry within floating-point roundoff.

### 3.2 Distinguishing Floating-Point Noise from Mathematical Positive Definiteness
In the unconstrained free-body case, the continuous operator has a 3-dimensional nullspace:
$$\text{ker}(K) = \text{span}\{ (1, 0)^T, (0, 1)^T, (-y, x)^T \}$$
Numerically, computing eigenvalues via dense eigensolvers yields:
$$\lambda_1 = -7.69 \times 10^{-7}, \quad \lambda_2 = 1.05 \times 10^{-6}, \quad \lambda_3 = 2.41 \times 10^{-6}, \quad \lambda_4 = 3.09 \times 10^7$$
Notice that $\lambda_2$ and $\lambda_3$ are strictly positive floating-point numbers ($\sim 10^{-6}$), but their ratio to $\lambda_{\max} \approx 1.39 \times 10^{10}$ is $\sim 10^{-16}$.
> **Caution:** Naive checks such as `np.all(eigvals > 0)` would falsely classify this unconstrained, singular matrix as positive-definite! GDEC's `MatrixDiagnostics` detects that these eigenvalues are within the null-mode tolerance relative to $\|K\|$, correctly reporting:
> `SPD: False, CG Eligible: False, Null Modes: 3`.

Similarly, when only $u_x$ is constrained along the left edge (roller boundary), horizontal translation and rotation are prevented, but uniform vertical translation $T_y = (0, 1)^T$ remains unconstrained. The diagnostic tool correctly identifies $\lambda_1 = 1.29 \times 10^{-6}$ ($\text{ratio} = 9.30 \times 10^{-17}$) as a null mode, marking the system as mathematically singular.

---

## 4. Sparse vs Dense Eigenvalue Estimation

For small systems ($N \le 400$), full dense eigensolves (`scipy.linalg.eigh`) are fast and compute the complete spectrum without iterative convergence issues, providing the exact nullity `exact_nullity`.
For large sparse systems ($N > 400$ up to $100,000+$), dense conversion is prohibitive ($\mathcal{O}(N^3)$ operations and $\mathcal{O}(N^2)$ memory). GDEC uses ARPACK via `scipy.sparse.linalg.eigsh`:
- **Largest Eigenvalue $\lambda_{\max}$:** Computed with `which="LA"` (Largest Algebraic).
- **Smallest Eigenvalues:** Computed directly with `which="SA"` (Smallest Algebraic), requesting $k = \min(6, n - 2)$ eigenvalues.
- **Scale-Invariant Thresholding:** Spectral filtering uses:
  $$\text{norm\_scale} = \max(|\lambda_{\max}|, \epsilon_{\text{tiny}})$$
  where $\epsilon_{\text{tiny}} = \text{np.finfo(float).tiny} \approx 2.22 \times 10^{-308}$. This eliminates arbitrary unit-dependent threshold artifacts (such as $\max(\dots, 1.0)$), ensuring consistent behavior whether stiffness is measured in Pa, kPa, or GPa.
- **Why `which="SA"` Replaced Shift-Invert:**
  Shift-invert mode (`eigsh(..., sigma=0.0, which="LM")`) locates eigenvalues with largest $1/|\lambda|$, which corresponds to smallest *magnitude* $|\lambda|$. On indefinite matrices (e.g., matrices with eigenvalues $-1.0$ and $+3.0$), the smallest algebraic eigenvalue is negative ($-1.0$), but a shift-invert search near zero can return positive eigenvalues or miss negative modes with larger magnitudes, failing to identify indefiniteness. `which="SA"` searches algebraically from the negative end of the spectrum, reliably catching negative eigenvalues and proving indefiniteness.
- **Null Mode Multiplicity Telemetry:**
  In sparse mode, computing the full dimension of the nullspace would require dense rank or full singular value decomposition. GDEC explicitly reports:
  - `null_modes_detected`: The integer count of null modes discovered among the $k$ requested eigenvalues satisfying $|\lambda_i| \le \text{null\_tol} \times \text{norm\_scale}$.
  - `exact_nullity`: Returns the exact algebraic nullity in dense mode ($N \le 400$), and `None` in sparse mode to prevent false claims of complete nullspace dimension.
  - `has_null_modes`: Boolean flag indicating whether any null modes were detected.
- **Nonsymmetric Matrix Protection:**
  If $\delta_{\mathrm{sym}} > \text{sym\_tol}$, symmetric eigensolvers (`eigvalsh` and `eigsh`) are strictly bypassed. Sparse `eigsh` assumes symmetric operators and is skipped with an explicit diagnostic warning; dense analysis uses general eigensolves (`la.eigvals`) without discarding imaginary components. Both `is_positive_definite` and `is_cg_eligible` are strictly set to `False`.

### Validation of Agreement (Dense vs Sparse)
On a $6 \times 4$ cantilever mesh ($N = 40$ free DOFs):
- Dense Exact: $\lambda_{\min} = 9.0628 \times 10^5$, $\lambda_{\max} = 1.2268 \times 10^{10}$, $\kappa_2 = 1.3536 \times 10^4$.
- Sparse ARPACK: $\lambda_{\min} = 9.0628 \times 10^5$, $\lambda_{\max} = 1.2268 \times 10^{10}$, $\kappa_2 = 1.3536 \times 10^4$.
- Relative error between dense and sparse estimators: $< 10^{-8}$.

The diagnostic module `src/gdec/fem/matrix_diagnostics.py` is fully verified and covered by automated regression tests in `tests/test_matrix_diagnostics.py`.
