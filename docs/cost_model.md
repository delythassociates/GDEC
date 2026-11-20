# GDEC Computational Cost Model

## 1. Purpose
The refinement cost model predicts the degrees of freedom resulting from a proposed marking set $\mathcal{M}$ before committing to refinement:
$$\hat{N}_{k+1} = N_k + \alpha \cdot |\mathcal{M}|$$
where:
- $N_k$: Current mesh DOFs.
- $|\mathcal{M}|$: Number of elements marked for refinement.
- $\alpha$: Effective DOF expansion factor per marked element.

## 2. Empirical Model Parameters
- **Linear Triangles (P1)**: Each bisected element introduces new interior nodes and edge splits. Conforming green closure propagates splits to adjacent elements.
- **Empirical Factor**: $\alpha \approx 1.8 - 2.4$ DOFs per marked element under red-green bisection.
- **Observed Accuracy in v0.2.2**:
  - Mean Absolute Percentage Error: $18.30\%$.
  - Median Error: $19.19\%$.
  - Mean Signed Bias: $+541.2\text{ DOFs}$ (conservative over-prediction).
  - Under-prediction Frequency: $10.0\%$ (maximum observed under-prediction: 35 DOFs).
  - Safety Guarantee: Transactional rollback ensures that any under-prediction is trapped before committing mesh over budget.
