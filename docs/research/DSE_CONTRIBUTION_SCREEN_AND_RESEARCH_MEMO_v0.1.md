# GDEC Research Track — Candidate Contribution Screen and DSE Memo v0.1

**Date:** 2026-11-22  
**Status:** Preliminary research hypothesis; not a novelty claim  
**Scope:** Software-only engineering computation planning. No hardware/GPU implementation or performance claims.  
**Repository baseline:** `research/phase-5.2.1b-expression-input-integrity`

## Executive result

A useful GDEC research direction is not a new mesh estimator, DWR variant, reduced-order model, floating-point error tracker, or generic value-of-information planner in isolation. Those areas already have substantial prior art—including work directly on deciding how much to refine a simulation model and optimally allocating computation among discretisation, uncertainty quantification and model reduction.

The **Decision-Sufficiency Engine (DSE)** remains a working research hypothesis, but its broad form is not novel. The possible gap is narrower: a planner that treats engineering assurance obligations and heterogeneous evidence types as hard constraints on computation selection, tracks dependence between evidence sources, distinguishes certified bounds from empirical/probabilistic estimates, and refuses a decision when those obligations remain unmet. This is a research question, not a demonstrated contribution.

The novelty burden is high. A combination of existing VOI, goal-oriented adaptivity, resource allocation and evidence tracking is not automatically publishable novelty. A defensible contribution would need a precise algorithm, a nontrivial property or guarantee, and benchmark evidence showing an advantage over the closest existing engineering model-refinement and resource-allocation methods.

## 1. Prior-art reading notes

### 1.1 Running error bounds in finite-element kernels (2026 preprint)

Habera, Kühner, Croci and Zilian, *Running error bounds in finite element kernels*, arXiv:2609.37844 (29 September 2026), https://arxiv.org/abs/2609.37844.

**Read:** abstract, introduction, running-error analysis, implementation, examples and limitations.

The paper propagates local floating-point rounding error alongside computed values in generated FEniCSx finite-element assembly kernels. It distinguishes approximate worst-case bounds from signed error estimates, demonstrates catastrophic cancellation in a Neo-Hooke strain-energy expression and sensitivity on near-degenerate meshes, and reports roughly 2–3.5× overhead in tested cases. It notes limitations in subnormal/underflow handling, math-library error assumptions, and the inability of the current FFCx path to assign precision independently to sub-operations. Dynamic per-operation precision selection is identified as future work.

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

**Implication:** multi-goal DWR, guaranteed QoI estimates under stated assumptions, and balancing some numerical error sources are prior art. GDEC's potential differentiation must be broader and decision-level, while respecting each estimator's assumptions.

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
| 1 | Assurance-constrained decision-sufficiency planner over heterogeneous computation/evidence actions | 6.0 | Strong direct overlap with VOI model refinement and optimal compute-budget allocation; only assurance/dependency constraints remain a possible gap. |
| 2 | Cross-layer error/evidence ledger with dependency-aware aggregation | 8.0 | Error decomposition exists; general dependency and assurance ledger needs focused search. |
| 3 | Joint allocation of mesh, algebraic-solve, and arithmetic effort by decision-risk reduction | 5.5 | Direct overlap with optimal allocation across discretisation/UQ/model reduction; narrower cross-assurance extension required. |
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

**Advance to focused research (with novelty risk):** candidates 1, 2, 4, 7, 8 and 19. Candidates 1 and 3 are downgraded after finding direct resource-allocation prior art.  
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

## 6. Novelty-threat addendum — direct engineering decision/resource-allocation prior art

A second literature search found three works that materially narrow the DSE novelty hypothesis. These are not peripheral analogies; they address the same high-level question of deciding whether/how to refine a simulation model or allocate limited computation to improve an engineering decision.

### 6.1 Panchal et al. (2008): value of information for simulation-model refinement

Panchal, Paredis, Allen and Mistree, *A value-of-information based approach to simulation model refinement*, Engineering Optimization 40(3) (2008), 223–251, https://doi.org/10.1080/03052150701690764.

**Read:** full abstract and detailed publication record.

This work explicitly asks how much a simulation model should be refined for a particular engineering design problem. It accounts for both variability (probabilistic) and imprecision (interval) in simplified models, introduces an “improvement potential” metric for the value of information gained by model refinement, and gradually refines models until further improvement in design decisions becomes small. The examples include pressure-vessel design and refinement of a complex finite-element model.

**Consequence:** the broad DSE proposition “decide how much computation/model refinement is needed to make a trustworthy engineering decision” is already directly anticipated. GDEC cannot present that as its novel claim.

### 6.2 Zinkhahn, Leube, Nowak and de Barros (2013): optimal allocation across computation dimensions

*Towards optimal allocation of computer resources: Trade-offs between uncertainty quantification, discretization and model reduction*, Environmental Modelling & Software 50 (2013), 97–107, https://doi.org/10.1016/j.envsoft.2013.08.008.

**Read:** abstract, highlights, introduction and methodology description available from the article record.

This work explicitly allocates a finite CPU budget among physical-space, temporal and parameter-space/stochastic resolutions, jointly considering discretisation error and statistical uncertainty. It constructs a cost-to-error surface, recommends cost-efficient pre-investigations to fit error/complexity models, and selects a task-dependent resource allocation to maximise prediction accuracy for a given budget. It reports 5–100× speedups in its application examples.

**Consequence:** joint allocation across mesh/discretisation and uncertainty-quantification effort is not novel. Any GDEC algorithm must compare against this class of cost-to-error resource allocation, not just fixed mesh refinement.

### 6.3 Shallcross et al. (2021): multiobjective VOI for set-based engineering design

Shallcross, Parnell, Pohl and Goerger, *A value of information methodology for multiobjective decisions in quantitative set-based design*, Systems Engineering 24 (2021), 409–424, https://doi.org/10.1002/sys.21593.

**Read:** full accessible article page, abstract and references.

The work integrates Bayesian decision models and value of information into multiobjective set-based design, evaluates whether higher-resolution models can reduce uncertainty, and compares high-resolution model choices by usage cost and information value. The article explicitly cites Panchal et al. (2008) as a prior simulation-refinement VOI method.

**Consequence:** VOI-driven selection among model fidelities for multiobjective engineering decisions is also prior art.

### 6.4 Updated novelty verdict

The broad DSE formulation in Sections 3.1–3.2 is **not sufficiently differentiated** from existing work. In particular, the objective “minimise computation cost while reducing decision risk” and the action “refine the simulation model only while the value of further refinement is material” are already established ideas.

The only plausible gap worth investigating is the **assurance-constrained orchestration of heterogeneous evidence**:
- each action is typed by what it can establish (e.g. discretisation estimate, guaranteed QoI bound, algebraic residual, floating-point bound, independent code comparison, parameter uncertainty reduction, experimental validation);
- evidence items carry assurance level, assumptions, scope and provenance;
- dependence between evidence items is represented explicitly so correlated checks cannot be counted as independent;
- decision sufficiency is constrained by mandatory verification obligations, not only expected decision utility;
- a planner can choose a computation that closes a specific assurance gap, or return INCONCLUSIVE if no available action can do so.

This proposed gap may itself have prior art in assurance cases, safety verification, uncertainty management and value-of-information research. It is **not yet established as novel**. The next research gate is a targeted review of evidence theory/dependence, assurance-case reasoning, certified numerical computation and decision-theoretic metareasoning applied to engineering simulations.

**Revised recommendation:** do not proceed to implementation. First define the evidence/action ontology and identify a formal property that existing model-refinement and resource-allocation frameworks do not provide. If no such property survives prior-art review, retain DSE as a useful product architecture but do not claim it as a novel algorithm.

## 7. Second novelty-threat addendum — metareasoning and assurance-case prior art

This targeted search found direct prior art for two additional building blocks in the proposed gap: (i) selecting computations by expected utility, and (ii) representing claims, arguments, assumptions and evidence with explicit dependencies. These findings further reduce the novelty space.

### 7.1 Russell and Wefald (1991): rational metareasoning

Russell and Wefald, *Principles of metareasoning*, Artificial Intelligence 49(1–3) (1991), 361–395, https://doi.org/10.1016/0004-3702(91)90015-C.

**Read:** publisher abstract and author research summary.

The paper develops a general framework for selecting and justifying computational actions under resource limits. It treats computation as an action whose utility derives from its expected effect on the agent's subsequent external decision, using probability and decision theory to evaluate computational strategies.

**Consequence:** selecting the next computation according to expected decision improvement minus computational cost is not a new principle. GDEC's proposed VOI action-selection equation is an engineering-domain adaptation of established rational metareasoning, not a novelty claim by itself.

### 7.2 Assurance cases already model claims, arguments, assumptions and evidence

Relevant sources:
- UK Information Commissioner's Office, *Annexe 5: Argument-based assurance cases*, https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/explaining-decisions-made-with-artificial-intelligence/annexe-5-argument-based-assurance-cases.
- NIST SP 800-160 Vol. 1 Rev. 1 (2022), *Engineering Trustworthy Secure Systems*, https://doi.org/10.6028/NIST.SP.800-160v1r1.
- Rushby, *The Interpretation and Evaluation of Assurance Cases*, SRI-CSL-15-01 (2015), https://www.csl.sri.com/~rushby/papers/sri-csl-15-1-assurance-cases.pdf.
- Nešić, Nyberg and Gallina, *A probabilistic model of belief in safety cases*, Safety Science 138 (2021), 105187, https://doi.org/10.1016/j.ssci.2021.105187.

**Read:** ICO guidance sections on GSN context, arguments, assumptions and evidence; NIST assurance-case description and evidence-quality criteria; Rushby's discussion of evidence dependence; and the abstract/highlights of the probabilistic safety-case model.

These sources establish that assurance cases already structure claims supported by arguments, assumptions, context and evidence. GSN/SACM and related notations provide established representations. Probabilistic safety-case research already models confidence in structured claims. Rushby explicitly discusses the problem that multiple evidence items may not be independent and describes representing dependencies with Bayesian belief networks. Thus, neither an evidence graph nor dependence-aware confidence reasoning is novel in the abstract.

**Consequence:** GDEC cannot claim to invent an assurance ledger, structured claim/evidence graph, or dependency-aware confidence calculation. A possible differentiator would have to be a machine-executable connection between *numerical computation actions* and *typed engineering assurance obligations*, with sound rules governing what a result is allowed to establish. Even this needs a broader standards and literature review.

### 7.3 Multi-fidelity optimization is a mature adjacent field (2026 survey)

Li and Li, *Multi-Fidelity Methods for Optimization: A Survey*, ACM Computing Surveys 58(12), Article 298 (published 15 May 2026), https://doi.org/10.1145/3801959.

**Read:** abstract and available sections on surrogate modelling, fidelity management and open challenges.

The survey synthesises more than 1,000 papers and reviews multi-fidelity surrogate construction, optimization methods and fidelity-management strategies. It describes adaptive selection of low- and high-fidelity evaluations, often using information gain and evaluation cost, and discusses unresolved issues in fidelity relationships, resource trade-offs and benchmark design.

**Consequence:** selecting fidelity levels based on information gain and cost is a mature, actively surveyed area. GDEC's differentiation cannot be “choose the right fidelity”; it would need to demonstrate how assurance obligations and numerical verification constraints change the action space and admissibility rules.

### 7.4 Evidence-grounding and computational verification are also established

Additional relevant sources:
- Oberkampf and Roy, *Verification and Validation in Scientific Computing*, chapter “Code verification” (2010), https://doi.org/10.1017/CBO9780511760396.008.
- *Trusting computations: A mechanized proof from partial differential equations to actual program*, Computers & Mathematics with Applications 68(3) (2014), 325–352, https://doi.org/10.1016/j.camwa.2014.06.004.
- CODECHECK, *An Open Science initiative for the independent execution of computations underlying research articles during peer review*, https://pmc.ncbi.nlm.nih.gov/articles/PMC8311796/.

These works reinforce that code verification, mechanized proofs spanning mathematical schemes and programs, and independent reproducibility checking already exist. Their scopes differ: for example, CODECHECK verifies that a workflow reproduces outputs, not that the implemented method is scientifically valid. GDEC must preserve these distinctions rather than collapsing “independent execution,” “code verification,” “numerical verification,” and “physical validation” into one assurance score.

### 7.5 Updated gap statement and kill criterion

The previous gap statement is now too broad if phrased as “typed evidence with dependencies and assurance levels.” Assurance-case standards and probabilistic safety-case research already cover much of that representation and reasoning space.

The remaining candidate is therefore narrower and more testable:

> **Can an engineering computation planner construct and execute a typed assurance-obligation graph in which each available numerical or physical investigation action has explicit, machine-checkable claim-production rules, and where action selection is constrained by unresolved obligations rather than only by expected information value?**

A credible contribution would need to establish all of the following:
1. A formal mapping from engineering decision claims and assumptions to specific verification/validation obligations.
2. Machine-checkable action contracts specifying which evidence claims an action can establish, under what assumptions, and with what assurance class.
3. A dependency-aware rule preventing evidence derived from shared solver state, mesh, model, data or oracle from being counted as independent.
4. A sound refusal rule: no top-level claim can be emitted unless every mandatory obligation is discharged by admissible evidence or explicitly accepted as an assumption by an authorised decision-maker.
5. A scheduling algorithm that chooses among admissible actions under a resource budget without weakening the soundness of the obligation rules.

**Kill criterion:** if existing assurance-case tooling plus standard numerical verification tools can express and execute these obligations without a new formal mechanism, then GDEC's contribution is integration/product engineering rather than a novel algorithm. That may still be useful, but it must be described accurately.

**Current verdict:** no novelty claim. Continue only with a formal requirements/specification exercise and a comparative prototype design; do not implement the DSE in the compiler/runtime yet. The next review should inspect SACM/GSN semantics, ISO/IEC/IEEE 15026, Bayesian-network assurance-case dependency models, and proof-carrying/verified numerical computation in greater depth before any paper claim.

## 8. Additional references

7. Russell, S., & Wefald, E. (1991). *Principles of metareasoning*. Artificial Intelligence, 49(1–3), 361–395. https://doi.org/10.1016/0004-3702(91)90015-C
8. Rushby, J. (2015). *The Interpretation and Evaluation of Assurance Cases*. SRI-CSL-15-01. https://www.csl.sri.com/~rushby/papers/sri-csl-15-1-assurance-cases.pdf
9. Nešić, D., Nyberg, M., & Gallina, B. (2021). *A probabilistic model of belief in safety cases*. Safety Science, 138, 105187. https://doi.org/10.1016/j.ssci.2021.105187
10. Li, K., & Li, F. (2026). *Multi-Fidelity Methods for Optimization: A Survey*. ACM Computing Surveys, 58(12), Article 298. https://doi.org/10.1145/3801959
11. Oberkampf, W. L., & Roy, C. J. (2010). *Verification and Validation in Scientific Computing*, Chapter 5: Code verification. https://doi.org/10.1017/CBO9780511760396.008
12. *Trusting computations: A mechanized proof from partial differential equations to actual program*. (2014). Computers & Mathematics with Applications, 68(3), 325–352. https://doi.org/10.1016/j.camwa.2014.06.004
13. *CODECHECK: an Open Science initiative for the independent execution of computations underlying research articles during peer review to improve reproducibility*. (2021). https://pmc.ncbi.nlm.nih.gov/articles/PMC8311796/
14. UK Information Commissioner's Office. *Annexe 5: Argument-based assurance cases*. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/explaining-decisions-made-with-artificial-intelligence/annexe-5-argument-based-assurance-cases
15. NIST. (2022). *Engineering Trustworthy Secure Systems* (SP 800-160 Vol. 1 Rev. 1). https://doi.org/10.6028/NIST.SP.800-160v1r1
