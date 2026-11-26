# WP2 Residual Closure — P1 Linear-Elasticity Manufactured-Solution Convergence

**Test Module:** `tests/verification/test_elasticity_mms_convergence.py`  
**Production Solver Exercised:** `gdec.fem.elasticity.LinearElasticitySolver.solve()` (Element: `ElementVector(ElementTriP1())`)  
**Command:** `.venv\Scripts\python.exe -m pytest -v tests/verification/test_elasticity_mms_convergence.py`  
**Status:** **NUMERICALLY VERIFIED** (2 passed in 0.87s)  

---

## 1. Manufactured Solution Formulation

On domain $\Omega = [0, 1] \times [0, 1]$ with homogeneous Dirichlet boundary conditions $u = (0, 0)$ on all four boundaries (`left`, `right`, `bottom`, `top`), $E = 100\text{ GPa}$, $\nu = 0.3$, thickness $t = 0.02\text{ m}$, $A = 1.0 \times 10^{-3}\text{ m}$, $B = 0.7 \times 10^{-3}\text{ m}$:

$$u_x(x, y) = A \sin(\pi x)\sin(\pi y), \qquad u_y(x, y) = B \sin(\pi x)\sin(\pi y)$$

Applying $-\nabla \cdot \sigma(u) = f = (b_x, b_y)$ with constitutive matrix $(c_{11}, c_{12}, c_{33})$:

$$b_x(x, y) = \pi^2 \left[ (c_{11} + c_{33}) A \sin(\pi x)\sin(\pi y) - (c_{12} + c_{33}) B \cos(\pi x)\cos(\pi y) \right]$$
$$b_y(x, y) = \pi^2 \left[ (c_{11} + c_{33}) B \sin(\pi x)\sin(\pi y) - (c_{12} + c_{33}) A \cos(\pi x)\cos(\pi y) \right]$$

---

## 2. Measured Refinement Sequence & Fitted Convergence Orders

### Plane Stress (`assumption="plane_stress"`)

| Mesh $N \times N$ | $h = 1/N$ | DOFs | $\|u - u_h\|_{L^2(\Omega)}$ | $|u - u_h|_{H^1(\Omega)}$ |
|---|---|---|---|---|
| $4 \times 4$ | $0.25000$ | $50$ | $7.141296 \times 10^{-5}$ | $1.033308 \times 10^{-3}$ |
| $8 \times 8$ | $0.12500$ | $162$ | $1.868857 \times 10^{-5}$ | $5.284650 \times 10^{-4}$ |
| $16 \times 16$ | $0.06250$ | $578$ | $4.732324 \times 10^{-6}$ | $2.657180 \times 10^{-4}$ |
| $32 \times 32$ | $0.03125$ | $2178$ | $1.187098 \times 10^{-6}$ | $1.330444 \times 10^{-4}$ |

- **Observed $L^2$ convergence order:** $p_{L^2} = \mathbf{1.9714}$ (acceptance range $[1.85, 2.15]$, theoretical $2.0$), $R^2 = \mathbf{0.99995}$
- **Observed $H^1$-seminorm convergence order:** $p_{H^1} = \mathbf{0.9864}$ (acceptance range $[0.85, 1.15]$, theoretical $1.0$), $R^2 = \mathbf{0.99995}$

### Plane Strain (`assumption="plane_strain"`)

| Mesh $N \times N$ | $h = 1/N$ | DOFs | $\|u - u_h\|_{L^2(\Omega)}$ | $|u - u_h|_{H^1(\Omega)}$ |
|---|---|---|---|---|
| $4 \times 4$ | $0.25000$ | $50$ | $6.824542 \times 10^{-5}$ | $1.036092 \times 10^{-3}$ |
| $8 \times 8$ | $0.12500$ | $162$ | $1.786355 \times 10^{-5}$ | $5.288377 \times 10^{-4}$ |
| $16 \times 16$ | $0.06250$ | $578$ | $4.527847 \times 10^{-6}$ | $2.657664 \times 10^{-4}$ |
| $32 \times 32$ | $0.03125$ | $2178$ | $1.136263 \times 10^{-6}$ | $1.330505 \times 10^{-4}$ |

- **Observed $L^2$ convergence order:** $p_{L^2} = \mathbf{1.9705}$ (acceptance range $[1.85, 2.15]$, theoretical $2.0$), $R^2 = \mathbf{0.99995}$
- **Observed $H^1$-seminorm convergence order:** $p_{H^1} = \mathbf{0.9876}$ (acceptance range $[0.85, 1.15]$, theoretical $1.0$), $R^2 = \mathbf{0.99996}$
