# GDEC Adaptive Refinement & Error Estimators

## 1. Implemented Error Indicators

GDEC implements two adaptive indicators alongside uniform mesh refinement:

### A. Zienkiewicz-Zhu (ZZ) Recovery Estimator
Computes energy-norm error by comparing element stresses $\boldsymbol{\sigma}_h$ with a recovered continuous stress field $\boldsymbol{\sigma}^*$:
$$\eta_{ZZ,e}^2 = \int_{\Omega_e} (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h) : \mathbf{C}^{-1} : (\boldsymbol{\sigma}^* - \boldsymbol{\sigma}_h) \, d\Omega$$
In GDEC, $\boldsymbol{\sigma}^*$ is constructed via area-weighted patch averaging of element centroid stresses to mesh vertices.

### B. Adjoint-Informed Goal Heuristic (`goal_heuristic_v1`)
To prioritize elements that directly influence the target QoI, GDEC computes an adjoint energy contraction weighted by element geometry:
$$\eta_{G,e} = h_e^2 A_e \left| \boldsymbol{\sigma}_e(\mathbf{u}) : \boldsymbol{\epsilon}_e(\mathbf{z}) \right|$$
where:
- $h_e$: Element characteristic diameter $\sqrt{A_e}$.
- $A_e$: Element area.
- $\boldsymbol{\sigma}_e(\mathbf{u})$: Primal stress tensor in element $e$.
- $\boldsymbol{\epsilon}_e(\mathbf{z})$: Adjoint strain tensor in element $e$.

> [!IMPORTANT]
> Mathematical Classification: $\eta_{G,e}$ is an **adjoint-informed refinement ranking heuristic**. It is **not** a certified Dual-Weighted Residual (DWR) error estimator, because it omits higher-order dual interpolation patch residuals $(\mathbf{z} - \Pi_h \mathbf{z})$ and boundary traction jump residuals.

## 2. Marking & Mesh Refinement
- **Dörfler Marking**: Sorts element indicators descending and marks top elements until cumulative indicator reaches fraction $\theta = 0.3$:
  $$\sum_{e \in \mathcal{M}} \eta_e \ge \theta \sum_{e \in \mathcal{T}} \eta_e$$
- **Conforming Bisection**: Refines marked elements using longest-edge red-green bisection (`scikit-fem`). Conforming closure ensures zero hanging nodes.
