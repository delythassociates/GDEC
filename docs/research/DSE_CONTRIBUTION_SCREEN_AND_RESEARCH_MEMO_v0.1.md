# GDEC Research Track — Candidate Contribution Screen and DSE Memo v0.1

**Date:** 2026-11-22  
**Status:** Preliminary research hypothesis; not a novelty claim  
**Scope:** Software-only engineering computation planning. No hardware/GPU implementation or performance claims.  
**Repository baseline:** `research/phase-5.2.1b-expression-input-integrity`

## Executive result

A useful GDEC research direction is not a new mesh estimator, DWR variant, reduced-order model, or floating-point error tracker in isolation. Those areas already have substantial prior art.

The strongest candidate is a **Decision-Sufficiency Engine (DSE)**: a sequential planner that selects the next engineering computation or evidence action—where to refine, which solver tolerance to tighten, which model fidelity to use, whether to run an independent check, and when to stop—according to the expected reduction in *engineering decision risk per unit cost*, subject to explicit evidence and assurance constraints.

This is a **novelty hypothesis**, not a verified original contribution. Existing work covers important components: guaranteed goal-error bounds with inexact algebraic solves; goal-oriented adaptivity; online DWR-controlled reduced-order enrichment; per-operation finite-element-kernel rounding-error analysis; formal compiler-correctness proofs; and value-of-information stopping theory. GDEC's potential contribution is the explicit integration of heterogeneous numerical and verification actions around a declared engineering decision, with honest separation of certified, probabilistic, and heuristic evidence.

## 1. Prior-art reading notes

### 1.1 Running error bounds in finite-element kernels (2026 preprint)

Habera, Kühner, Croci and Zilian, *Running error bounds in finite element kernels*, arXiv:2609.37844 (29 September 2026), https://arxiv.org/abs/2609.37844.

**Read:** abstract, introduction, running-error analysis, implementation, examples and limitations.

The paper propagates local floating-point rounding error alongside computed values in generated FEniCSx finite-element assembly kernels. It distinguishes approximate worst-case bounds from signed error estimates, demonstrates catastrophic cancellation in a Neo-Hooke strain-energy expression and sensitivity on near-degenerate meshes, and reports roughly 2–3.5× overhead in tested cases. It explicitly notes limitations in subnormal/underflow handling, math-library error assumptions, and the inability of the current FFCx path to assign precision independently to sub-operations. Dynamic per-operation precision selection is identified as future work.

**Implication for GDEC:** kernel-level arithmetic error tracking is not a new contribution for GDEC. It is a possible evidence provider/action model inside a larger planner. A planner must not mistake a first-order approximate REA bound for a rigorous global QoI bound.

### 1.2 Goal-oriented guaranteed bounds with inexact solvers (2020)

*Goal-oriented a posteriori error estimation for conforming and nonconforming approximations with inexact solvers*, Journal of Computational and Applied Mathematics 366 (2020), 112367, https://doi.org/10.1016/j.cam.2019.112367.

**Read:** abstract and available article description.

The work combines H(div)-conforming flux reconstruction and H1-conforming potential reconstruction to obtain a guaranteed upper bound on goal error for a model elliptic problem. It explicitly splits primal/dual discretisation and algebraic errors and derives stopping criteria for iterative algebraic solvers. The numerical study reports reduced unnecessary algebraic iterations.

**Implication:** “stop the solver when the QoI error is small enough” is already established. GDEC cannot claim novelty for a solver stopping rule alone. The candidate must select among heterogeneous actions and address the engineering decision, not only the error in one functional.

### 1.3 DWR plus equilibrated flux/potential reconstruction (2023)

Creusé, Nicaise and Tang, *Goal-oriented error estimation based on equilibrated flux and potential reconstruction for the approximation of elliptic and parabolic problems*, Computers & Mathematics with Applications 146 (2023), 323–338, https://doi.org/10.1016/j.camwa.2023.07.008.

**Read:** abstract and introduction, including scope and stated estimator/remainder decomposition.

The paper combines DWR with equilibrated flux and potential reconstruction for elliptic and parabolic problems and multiple discretisation families. It decomposes QoI error into a computable estimator and a remainder bounded using primal and dual energy-error estimators. It discusses multi-goal control and balancing discretisation and nonlinear-iteration errors.

**Implication:** multi-goal DWR, certified/guaranteed QoI estimates under stated assumptions, and balancing some numerical error sources are prior art. GDEC's potential differentiation must be broader and decision-level, while respecting each estimator's assumptions.

### 1.4 Online goal-oriented reduced-order model adaptation (2024)

Fischer et al., *MORe DWR: Space-time goal-oriented error control for incremental POD-based ROM for time-averaged goal functionals*, Journal of Computational Physics 504 (2024), 112863, https://doi.org/10.1016/j.jcp.2024.112863.

**Read:** abstract, highlights and available article description.

The method estimates error in a time-averaged goal functional during a simulation and enriches an incremental POD basis with high-fidelity snapshots when the estimated error exceeds a threshold. It reduces the number of full-order solves and adapts to unforeseen solution behaviour.

**Implication:** online selection of additional high-fidelity computation from a QoI error indicator is already established in ROM workflows. GDEC cannot claim that general idea alone.

### 1.5 Mechanically verified compiler transformations (2021)

Herklotz, Pollard, Ramanathan and Wickerson, *Formal Verification of High-Level Synthesis*, Proceedings of the ACM on Programming Languages 5 (OOPSLA), Article 117 (2021), https://doi.org/10.1145/3485494. Open author copy: https://yannherklotz.com/papers/oopsla21_fvhls.pdf.

**Read:** abstract and repository/publisher description.

Vericert extends CompCert with a hardware-oriented intermediate language and Verilog backend, with a Coq proof that generated hardware preserves input-program behaviour. This is a compiler-semantic correctness result, not a proof that the input program represents the correct physics or that a numerical solution is accurate.

**Implication:** compiler correctness and numerical/physical correctness must be separate assurance layers. GDEC's independent checker must not treat a verified lowering as a verified engineering result.

### 1.6 Value of information in stopping problems (2024)

Lehrer and Wang, *The value of information in stopping problems*, Economic Theory 78 (2024), 619–648, https://doi.org/10.1007/s00199-023-01543-8; preprint https://arxiv.org/abs/2205.06583.

**Read:** abstract and repository record.

The work formalises sequential decisions to stop and act irreversibly or pay to acquire additional information. It analyses how information quality and acquisition cost affect optimal stopping.

**Implication:** sequential value-of-information stopping is not novel in general. GDEC's research question is how to operationalise it for engineering computations whose actions produce heterogeneous, dependent and differently assured numerical evidence.

## 2. Candidate contribution screen (20 candidates)

Scores are preliminary research-priority scores (1–10), not novelty probabilities. “Prior art” indicates the strongest overlap found in this first screen.

| # | Candidate | Preliminary score | Prior-art overlap / initial disposition |
|---:|---|---:|---|
| 1 | Decision-sufficiency planner over heterogeneous computation/evidence actions | 9.0 | Components exist; integrated engineering decision-level planner is the leading hypothesis. |
| 2 | Cross-layer error/evidence ledger with dependency-aware aggregation | 8.0 | Error decomposition exists; general dependency and assurance ledger needs focused search. |
| 3 | Joint allocation of mesh, algebraic-solve, and arithmetic effort by decision-risk reduction | 8.0 | Each axis has prior art separately; integrated action allocation is promising. |
| 4 | Robust decision-margin stopping using certified QoI intervals | 8.0 | Interval methods and guaranteed QoI bounds exist; decision-specific orchestration may be useful. |
| 5 | Model-fidelity escalation selected by expected decision-risk reduction | 7.5 | Multifidelity optimisation is broad prior art; engineering verification coupling needs screening. |
| 6 | Adaptive experiment acquisition when simulation uncertainty dominates | 7.5 | Value-of-information and optimal experimental design are mature; domain integration needed. |
| 7 | Evidence-dependency graph preventing double-counting correlated checks | 7.5 | Bayesian networks and uncertainty propagation are prior art; engineering evidence semantics are the question. |
| 8 | Assurance-aware action planner that refuses unsupported claims | 7.0 | Formal verification and assurance cases exist; numerical evidence/action integration may differentiate. |
| 9 | Multi-QoI compute-budget allocation by consequence-weighted risk | 7.0 | Multi-goal DWR exists; consequence-weighted resource allocation is not yet screened deeply. |
| 10 | Automatic independent-solver selection as an evidence action | 6.5 | Code verification and cross-code validation are established; selection policy needs evidence. |
| 11 | Mesh-refinement scheduling based on decision-boundary sensitivity | 6.5 | Goal-oriented adaptivity exists; robust decision boundary objective is a possible variant. |
| 12 | Precision escalation based on local-to-global error propagation | 6.0 | REA and mixed-precision methods overlap strongly; integration only, not standalone novelty. |
| 13 | Solver tolerance selection from certified QoI budget | 5.5 | Strong prior art in guaranteed estimators with inexact solves. |
| 14 | Online ROM enrichment based on QoI error | 4.5 | MORe DWR and related work already cover this. |
| 15 | DWR/equilibrated-flux estimator for another standard PDE | 3.5 | Mature and crowded literature. |
| 16 | Unit/type-system-aware numerical planner | 6.0 | Typed engineering IR is valuable infrastructure; novelty needs a specific decision-theoretic claim. |
| 17 | Proof-obligation scheduling for numerical certificates | 6.5 | Formal methods and proof-carrying approaches exist; compute-aware ordering may be distinct. |
| 18 | Cost-aware independent verification sampling | 6.0 | Statistical verification/testing is broad; must avoid unsupported probability claims. |
| 19 | Adaptive physical-model validation versus numerical refinement | 7.0 | Potentially strong: distinguish numerical error from model-form uncertainty and choose validation action. |
| 20 | Reproducibility-risk-aware computation planning | 5.5 | Provenance and reproducibility are established; decision relevance needs demonstration. |

### First-pass ranking

**Advance to focused research:** candidates 1, 2, 3, 4, 5, 7, 8 and 19.  
**Use as enabling mechanisms, not headline claims:** 10, 12, 16 and 17.  
**Do not claim as novel without a substantially different theorem or scope:** 11, 13, 14 and 15.

The top two research tracks should be:
- **Track A — Decision-Sufficiency Engine:** action selection, cost/risk trade-offs, and stop/refuse criteria.
- **Track B — Evidence Dependency and Assurance Ledger:** typed representation of error/evidence sources, assumptions, dependencies, and assurance strength, so Track A cannot combine incompatible or correlated evidence incorrectly.

## 3. Core research memo — Decision-Sufficiency Engine

### 3.1 Problem statement

A conventional adaptive solver asks: “How do I reduce this numerical error indicator?” An engineering decision workflow needs to ask: “What is the cheapest next computation or evidence action that can establish whether the requested decision is safe and sufficiently supported?”

Examples of possible actions include:
- refine a selected mesh region;
- enrich polynomial order or a reduced basis;
- tighten primal or adjoint algebraic tolerances;
- improve quadrature or stabilise a constitutive evaluation;
- increase arithmetic precision;
- evaluate an alternative model fidelity;
- run an independent solver/checker;
- sample an uncertain parameter or acquire an experiment;
- stop and issue a supported decision, or refuse as inconclusive.

The action scope and intensity matter: `a = (action_type, spatial_or_model_scope, effort_level)`.

### 3.2 Proposed formal objective

Let:
- `d` be an engineering decision (accept/reject, select design, choose operating point);
- `theta` represent unknown physical/model parameters and other unresolved states;
- `E` be the current evidence;
- `A(E)` be the admissible next computation/evidence actions;
- `c(a)` be the resource cost of action `a`;
- `Y_a` be the possible result of action `a`;
- `L(d, theta)` be the engineering loss or consequence of taking decision `d` when the state is `theta`.

For a calibrated probabilistic model, define current decision risk:

`R_prob(E) = min_d E[L(d, theta) | E]`.

For a robust ambiguity set `Theta(E)`, define:

`R_rob(E) = min_d sup_{theta in Theta(E)} L(d, theta)`.

The planner chooses an action by expected risk reduction relative to cost:

`VOI(a | E) = R(E) - E_{Y_a}[R(E union Y_a)]`

`a* = argmax_{a in A(E)} [LCB(VOI(a | E)) / c(a)]`

where `LCB` is a conservative lower confidence bound on predicted value of information, used to avoid selecting actions on optimistic cost/error forecasts. This is a proposed policy, not yet a proven optimal rule.

Stop only when:
1. the decision risk is below a declared threshold `epsilon` (or a robust interval establishes the same acceptable decision for every admissible state);
2. all mandatory verification/evidence obligations for the requested assurance level pass;
3. no unresolved model applicability or unsupported-assumption gate remains.

If the resource budget is exhausted first, return **INCONCLUSIVE / REFUSED**, not a low-confidence engineering answer.

### 3.3 Critical safeguards

- **Do not collapse unlike errors.** Discretisation, algebraic, floating-point, parameter, model-form and measurement uncertainty are different quantities. They can be combined only through a justified bound or joint uncertainty model.
- **Do not assume independence.** Two checks derived from the same solver output are not independent evidence. The ledger must record evidence lineage and dependencies.
- **Do not call an estimator a certificate.** DWR indicators, empirical effectivity, residual norms, approximate REA bounds and certified upper bounds must carry distinct evidence types.
- **Do not manufacture probabilities.** If calibration data or a defensible probabilistic model is absent, use robust intervals/sets or mark the risk estimate heuristic.
- **Keep decision and QoI separate.** A small QoI error may still change a threshold decision; a large field error may be irrelevant to a particular decision. The decision boundary and consequence matter.
- **Keep physical validation separate from numerical verification.** Refining a mesh cannot resolve an invalid constitutive model or unvalidated boundary conditions.
- **Make failure a first-class outcome.** Missing action models, unsupported physics, absent bounds, invalid provenance, or budget exhaustion must lead to explicit refusal/inconclusive status.

### 3.4 Falsifiable claim and baseline

**Hypothesis H1:** On a benchmark suite of engineering decision tasks with independently known reference outcomes, the proposed DSE will achieve a lower total computation cost than fixed-fidelity and single-indicator stopping baselines while keeping the false-safe decision rate below a predeclared limit.

This claim is falsified if:
- the DSE's false-safe rate exceeds the limit;
- cost savings disappear when action-model calibration and independent checks are included;
- a simple DWR/solver-tolerance policy achieves equal or better risk-cost performance;
- the planner's predicted action value is poorly calibrated or systematically overoptimistic;
- it cannot distinguish numerical uncertainty from model-form uncertainty in benchmark cases.

**Initial software-only benchmark:** start with supported 2D linear elasticity and analytically or independently referenceable cases. Include smooth solutions, stress concentration/singularity cases, near-incompressible parameter regimes within supported assumptions, and decision thresholds deliberately placed near the reference QoI. Use the same CPU/double-precision environment for all baselines. Do not claim general multiphysics validity from this first slice.

**Baselines:**
1. Fixed mesh and fixed solver tolerance.
2. Uniform mesh refinement until successive QoI change meets a threshold.
3. Existing GDEC goal-oriented/DWR adaptive path.
4. A posteriori goal-error control with algebraic stopping where a suitable guaranteed estimator is available.
5. Exhaustive high-fidelity reference computation as the cost/accuracy ceiling.

**Metrics:** decision error and false-safe rate; total wall time and DOF/linear-solve count; number and cost of each action type; stopping regret; calibration of predicted versus observed risk reduction; fraction of cases returned as inconclusive; and performance under shifted parameters/mesh families.

### 3.5 Cheap kill tests

1. **Single-action dominance:** on simple elliptic problems, compare DSE against the strongest DWR + algebraic stopping baseline. If DSE adds overhead without reducing decision risk or cost, kill or narrow the claim.
2. **Decision-margin test:** construct cases where QoI error is small but crosses a design threshold, and cases where field error is large but does not affect the decision. If the planner cannot distinguish them, the central idea fails.
3. **Dependency test:** feed the planner two correlated checks derived from the same primal solve. If it treats them as independent and becomes more confident, the evidence ledger is unsafe.
4. **Model-form test:** introduce a deliberately wrong but numerically converged model. If the planner responds only by refining the mesh and reports confidence, the design is invalid.
5. **Budget-exhaustion test:** exhaust the budget before the risk threshold is met. The only acceptable outcome is inconclusive/refusal.
6. **Calibration test:** compare predicted risk reduction from each action with observed reduction over held-out cases. If the lower confidence bound is not conservative, action selection is unsafe.

### 3.6 Research gaps that remain

- A rigorous state representation for mixed certified intervals, calibrated distributions, empirical indicators and unknowns.
- A tractable action-value model for mesh/solver/model/experiment/checker actions.
- Guarantees or approximation bounds for sequential action selection; greedy VOI is not automatically optimal.
- How to estimate the cost of an action before performing it.
- How to represent and propagate dependence among evidence sources.
- How to incorporate consequence class and decision reversibility without arbitrary risk weights.
- How to validate the planner under distribution shift and unmodelled failure modes.

## 4. Recommendation

Proceed with Track A and Track B as research hypotheses only. Do not add a DSE implementation to the compiler or runtime yet. First produce a formal state/action/evidence model, a small synthetic decision benchmark, and a baseline comparison against the existing GDEC adaptive FEM path and published goal-oriented stopping methods.

The current evidence does **not** justify a claim that DSE is the first, optimal, or generally reliable engineering computation planner. The defensible claim to investigate is narrower: **a typed, assurance-aware planner that allocates heterogeneous engineering computation and verification actions to establish a declared decision at minimum measured cost, with explicit refusal when evidence is insufficient.**

## 5. References

1. Habera, M., Kühner, P. T., Croci, M., & Zilian, A. (2026). *Running error bounds in finite element kernels*. arXiv:2609.37844. https://arxiv.org/abs/2609.37844
2. *Goal-oriented a posteriori error estimation for conforming and nonconforming approximations with inexact solvers*. (2020). Journal of Computational and Applied Mathematics, 366, 112367. https://doi.org/10.1016/j.cam.2019.112367
3. Creusé, E., Nicaise, S., & Tang, Z. (2023). *Goal-oriented error estimation based on equilibrated flux and potential reconstruction for the approximation of elliptic and parabolic problems*. Computers & Mathematics with Applications, 146, 323–338. https://doi.org/10.1016/j.camwa.2023.07.008
4. Fischer, H., Roth, J., Wick, T., Chamoin, L., & Fau, A. (2024). *MORe DWR: Space-time goal-oriented error control for incremental POD-based ROM for time-averaged goal functionals*. Journal of Computational Physics, 504, 112863. https://doi.org/10.1016/j.jcp.2024.112863
5. Herklotz, Y., Pollard, J. D., Ramanathan, N., & Wickerson, J. (2021). *Formal Verification of High-Level Synthesis*. Proceedings of the ACM on Programming Languages, 5(OOPSLA), Article 117. https://doi.org/10.1145/3485494
6. Lehrer, E., & Wang, T. (2024). *The value of information in stopping problems*. Economic Theory, 78(2), 619–648. https://doi.org/10.1007/s00199-023-01543-8
