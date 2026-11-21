# GDEC Phase 5.1 Single-QoI Decision Evaluator Report

**Document ID:** `GDEC-DSE-EVAL-001`
**Date:** 2026-11-22
**Workstream:** D — Single-QoI Decision Evaluator
**Author:** Lead Engineering Research Orchestrator
**Status:** Implemented, Tested, Mathematically Certified

---

## 1. Mathematical Formulation & Implementation

The `SingleQoIEvaluator` in `src/gdec/dse/evaluator.py` implements Bayesian decision theory for one Quantity of Interest (QoI), one performance threshold, and asymmetric decision loss.

### 1.1 Predictive Model
The QoI predictive distribution represents epistemic and aleatory uncertainty:
$$Q \sim \mathcal{N}(\mu, \sigma^2)$$

For an engineering acceptance criterion with operator $\le$ and effective limit $L_{\text{eff}} = L - \text{margin}$:
$$z = \frac{L_{\text{eff}} - \mu}{\sigma}$$
$$P_{\text{safe}} = \Phi(z) = \frac{1}{2} \left[1 + \text{erf}\left(\frac{z}{\sqrt{2}}\right)\right]$$
$$P_{\text{fail}} = 1 - P_{\text{safe}} = \Phi(-z)$$

### 1.2 Asymmetric Bayesian Expected Loss
Let:
- $C_{\text{FA}}$: Cost of falsely releasing an unsafe design (false acceptance).
- $C_{\text{FR}}$: Cost of falsely rejecting a safe design (false rejection).

The expected losses associated with each decision action are:
$$\mathcal{R}(\text{RELEASE}) = C_{\text{FA}} \cdot P_{\text{fail}}$$
$$\mathcal{R}(\text{REJECT}) = C_{\text{FR}} \cdot P_{\text{safe}}$$

The preliminary recommendation selects the action minimizing expected loss:
$$\text{Action}^* = \arg\min \{\mathcal{R}(\text{RELEASE}), \mathcal{R}(\text{REJECT})\}$$

---

## 2. Decision Recommendations & Quality Gates

The evaluator produces one of four explicit recommendation verdicts:
- **`RELEASE`**: Expected loss of release is lower than rejection, and all numerical quality gates pass.
- **`REJECT`**: Expected loss of rejection is lower than release, and evidence is conclusive.
- **`REFINE`**: Either:
  1. High decision ambiguity ($|\mathcal{R}_{\text{release}} - \mathcal{R}_{\text{reject}}| / \max(\mathcal{R}) < 0.05$).
  2. Discretization error indicator breaches quality threshold ($\eta_{\text{rel}} > \text{threshold}$).
- **`INSUFFICIENT_EVIDENCE`**: Missing uncertainty distributions, unvalidated assumptions, or non-finite inputs.

---

## 3. Strict DWR Guardrails

In strict conformance with Phase 5.1 governance:
1. **Asymptotic Indicator, Not a Certified Bound:** The DWR error indicator is explicitly labeled as `dwr_asymptotic_indicator` in all outputs.
2. **Separation from Physical Uncertainty:** The DWR indicator is **NEVER** converted into a standard deviation or added into $\sigma$.
3. **Automated Refinement Trigger:** If $\frac{|\eta_{\text{DWR}}|}{|\mu|} > \text{numerical\_quality\_threshold}$ (e.g. $5\%$), the evaluator automatically refuses to release and recommends `REFINE` with actionable diagnostics:
   > *"Numerical discretization error indicator (10.0000%) exceeds contract quality threshold (5.0000%). Additional mesh refinement required."*

---

## 4. Verification Evidence

The mathematical accuracy of the evaluator was verified against analytical Gaussian integrals in `tests/test_dse.py`:
- Known Case ($\mu = 8.0, \sigma = 0.5, L = 9.5$): Verified $z = 3.0, P_{\text{fail}} = 0.00135, R_{\text{release}} = 1.35, R_{\text{reject}} = 99.87 \implies$ `RELEASE`.
- Unsafe Case ($\mu = 10.5, \sigma = 0.5, L = 9.5$): Verified $P_{\text{fail}} = 0.9772 \implies$ `REJECT`.
- Deterministic Case ($\sigma = 0$): Handled without division-by-zero, yielding exact step-function probabilities ($P = 1.0$ or $0.0$).
