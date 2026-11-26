# Decision-Sufficiency Computation Algorithm (DSCA)
## Research specification v0.1

**Status:** RESEARCH PROPOSAL — NOT IMPLEMENTED, NOT VALIDATED, NOT APPROVED FOR PRODUCTION  
**Workstream:** GDEC research, separate from WP2 residual-gate closure  
**Scope:** Decision-aware selection and stopping of engineering computations. No solver, estimator, GPU or WP3 implementation is included.

---

## 1. Executive statement

GDEC should investigate an algorithm that selects the next computation by asking:

> Which admissible computation is expected to reduce uncertainty in the engineering decision enough to justify its incremental cost?

This is stronger than asking only whether a PDE solver has converged or whether a global error is below a tolerance. Engineering decisions are commonly based on quantities of interest (QoIs), constraints, margins, operating conditions and model assumptions. Improving a field solution in regions irrelevant to the decision may waste resources; a small global residual may still leave a decision-critical QoI unresolved.

The proposed **Decision-Sufficiency Computation Algorithm (DSCA)** is a controller over a portfolio of computational actions. It is not a new FEM/CFD discretisation, a new error estimator, or a claim that GDEC can infer physical truth from simulation data. It combines established ingredients—goal-oriented error estimation, adaptive FEM, uncertainty quantification, value-of-information reasoning and explicit assurance gates—into one decision-oriented control problem.

The research question is whether this integration can produce a reproducible and defensible policy for selecting what to compute next, how much to compute, and when to stop or refuse.

## 2. Problem definition

Let:
- \(m\) denote the declared engineering model and assumptions;
- \(x\) denote uncertain inputs (loads, material parameters, geometry, boundary data);
- \(u(m,x)\) denote the model solution;
- \(q(u,x)\in\mathbb{R}^k\) denote decision-relevant QoIs;
- \(d\in\mathcal D\) denote an engineering decision;
- \(L(d,q,x)\) denote decision loss;
- \(B\) denote the available computational budget;
- \(a\in\mathcal A\) denote a permissible computational action.

Actions may include another solver iteration, tighter algebraic tolerance within the numerical contract, local mesh refinement, polynomial-order increase, another applicable estimator, independent verification, higher-fidelity physics, additional uncertainty samples, a targeted parameter study, or an experimental/reference comparison. The action set is problem- and capability-dependent. The controller cannot invent unavailable capabilities or relax declared requirements.

The desired output is not necessarily a fully converged field. It is a decision accompanied by evidence sufficient to justify it under declared assumptions—or an explicit inconclusive/refusal result.

## 3. Three distinct stopping concepts

1. **Algebraic convergence:** the discrete system has been solved to a stated numerical criterion.
2. **Discretisation/QoI adequacy:** the numerical approximation of the target QoI is sufficiently accurate, based on an applicable estimator or bound.
3. **Decision sufficiency:** remaining uncertainty in the QoIs cannot change the decision under the declared decision rule and assurance obligations.

A small algebraic residual does not establish discretisation accuracy. A stable QoI over successive refinements is not, by itself, a certified error bound. A small QoI error may still be decision-insufficient when a design lies close to a constraint boundary. Conversely, a relatively large QoI uncertainty may be decision-sufficient when all plausible values lead to the same decision.

The controller must never merge these statuses into a single “converged” flag.

## 4. Formal decision criterion

### 4.1 Certified/interval path

Where an applicable mathematical bound is available, represent each QoI by an interval:

\[
q_i \in [\underline q_i,\overline q_i].
\]

The interval must include all error components required by the stated assurance claim, such as discretisation, algebraic solve, quadrature, data approximation and relevant input uncertainty. If a component is not covered, the interval must not be presented as a total guaranteed interval.

For a deterministic constraint \(g(q)\leq 0\):
- **Robustly acceptable:** \(\sup_{q\in\mathcal Q}g(q)\leq 0\).
- **Robustly unacceptable:** \(\inf_{q\in\mathcal Q}g(q)>0\).
- **Decision-inconclusive:** the admissible set crosses the decision boundary.

Here \(\mathcal Q\) is the joint admissible QoI set. Correlations must be retained where known; independent scalar intervals can be unnecessarily conservative and must not be treated as a joint probability distribution.

For design selection, define the admissible decision set as all decisions optimal for at least one \(q\in\mathcal Q\). If exactly one decision remains possible, the decision is robust to the bounded uncertainty. If multiple decisions remain possible, more evidence may be valuable.

### 4.2 Probabilistic path

Where uncertainty is represented probabilistically, define:

\[
R(d\mid E)=\mathbb E[L(d,q,x)\mid E],
\qquad
d^*=\arg\min_{d\in\mathcal D}R(d\mid E),
\]

where \(E\) is accumulated evidence. A risk-constrained decision may additionally require:

\[
P(\text{constraint violation}\mid E)\leq\epsilon.
\]

This path is only as defensible as the probability model, likelihood, prior, dependence structure and calibration evidence. A Gaussian approximation, an unvalidated surrogate, or an estimator relabelled as a standard deviation is not sufficient. The system must expose distributional assumptions and refuse probabilistic assurance if calibration or applicability requirements are unmet.

### 4.3 Assurance modes must not be blended

DSCA must declare which mode it is using:
- **Bounded mode:** decision based on mathematically justified intervals/bounds.
- **Probabilistic mode:** decision based on a documented, calibrated probabilistic model.
- **Heuristic mode:** guidance only; no assurance claim.
- **Incomplete mode:** evidence is insufficient or an obligatory check is absent.

A heuristic DWR indicator must not be inserted into a probability distribution as if it were a standard deviation. A status string such as “INDEPENDENTLY_VALIDATED” is not proof of validation.

## 5. Computational action selection

### 5.1 Value of computation

For each candidate action \(a\), estimate:
- incremental cost \(C(a\mid E)\), including setup, solve, transfer and verification costs;
- possible evidence outcomes \(Y_a\);
- expected reduction in decision risk or decision ambiguity;
- action applicability and resource constraints;
- whether the action can resolve the current dominant uncertainty.

A probabilistic value-of-computation score can be written:

\[
\operatorname{VOC}(a\mid E)=
R(d^*\mid E)-
\mathbb E_{Y_a\mid E}\left[
\min_d R(d\mid E,Y_a)
\right]
-\lambda C(a\mid E).
\]

Here \(\lambda\) converts computational cost into the chosen utility scale. It is not a universal physical constant. The risk model and cost units must be declared.

Select the admissible action with the greatest positive VOC. If all actions have non-positive estimated VOC, the controller must not automatically declare success: it must either stop with a justified decision, return inconclusive, or refuse because a mandatory evidence obligation remains unmet.

The expected-value calculation can be unreliable when outcome models are poorly calibrated. The initial research should also evaluate deterministic interval-based action selection and conservative lower-confidence estimates of VOC.

### 5.2 Bounded-information alternative

For bounded mode, use a conservative action-ranking proxy:

\[
S(a)=\frac{\Delta W_{\mathrm{decision}}^{\mathrm{lower}}(a)}
{C^{\mathrm{upper}}(a)},
\]

where the numerator is a conservative lower estimate of reduction in the width or ambiguity of the decision-relevant set and the denominator is a conservative upper cost estimate. This ratio is only a prioritisation heuristic unless its bounds are mathematically established. It must not be called an optimal policy.

### 5.3 Avoid double counting

Evidence sources are often dependent: DWR and residual estimators may use the same residual; two solvers may share a discretisation and constitutive model; repeated refinements may share model-form error; multiple samples may use the same uncertain input distribution. DSCA must maintain an evidence-dependence graph. It must not combine confidence statements as if evidence were independent unless independence is justified.

## 6. Proposed control loop

The controller operates over explicit states:

1. **SPECIFIED:** objective, QoIs, constraints, assumptions, resource budget and assurance mode are explicit.
2. **ELIGIBILITY_CHECKED:** candidate actions and evidence methods satisfy capability/applicability contracts.
3. **BASELINE_COMPUTED:** a first admissible computation and provenance are available.
4. **EVIDENCE_ASSESSED:** algebraic, discretisation, input/model and validation evidence are classified separately.
5. **DECISION_TESTED:** robust interval or calibrated risk test is evaluated.
6. **ACTION_SELECTED:** next action and predicted value/cost rationale are recorded.
7. **BUDGET_CHECKED:** action fits the remaining resource budget.
8. **EXECUTED:** action runs and emits traceable output.
9. **UPDATED:** evidence, uncertainty and cost state are updated.
10. **STOPPED / INCONCLUSIVE / REFUSED:** terminal outcome with machine-readable reasons.

Pseudo-code:

~~~text
DSCA(specification, budget):
    validate_objective_QoIs_constraints_and_assurance_mode()
    obligations = derive_mandatory_evidence_obligations(specification)
    actions = enumerate_supported_actions(specification)

    if specification_is_ambiguous_or_physically_invalid:
        return REFUSED(reason, missing_or_invalid_fields)

    evidence = execute_minimum_admissible_baseline()
    cost = account_for_actual_cost(evidence)

    while true:
        classify_evidence_components(evidence)
        check_applicability_and_provenance(evidence, obligations)

        if mandatory_obligation_is_unmet_and_unresolvable:
            return REFUSED(reason, evidence)

        decision_state = evaluate_decision(evidence, assurance_mode)

        if decision_state.is_robust
           and all_mandatory_obligations_are_satisfied:
            return DECISION_WITH_EVIDENCE(decision_state, evidence, cost)

        candidates = filter_by_capability_and_contract(actions, evidence)
        candidates = remove_actions_exceeding_remaining_budget(candidates)

        if candidates is empty:
            return INCONCLUSIVE("budget_or_capability_exhausted", evidence, cost)

        action = select_action_by_conservative_value_of_computation(candidates)

        if action_has_no_defensible_expected_value:
            return INCONCLUSIVE("no_justified_next_computation", evidence, cost)

        result = execute(action)
        evidence = update_evidence_without_double_counting(evidence, result)
        cost = account_for_actual_cost(cost, result)
~~~

This state machine is a research design, not a description of the current GDEC runtime.

## 7. Safety and correctness invariants

1. **No weakening of requirements:** the controller cannot change user tolerances, safety factors, acceptance thresholds or assurance mode to force a decision.
2. **No false certification:** heuristic indicators remain indicators; certified bounds require a valid theorem, assumptions and checker.
3. **No hidden fallback:** unavailable methods produce explicit eligibility failures.
4. **No untracked computation:** every action records input identity, configuration, cost, software version and output hashes.
5. **No premature stop:** decision sufficiency requires decision robustness and completion of mandatory evidence obligations.
6. **No model-truth inference:** numerical verification does not establish that the physical model represents reality; validation and model-form uncertainty remain separate.
7. **No evidence double counting:** dependencies between evidence records are represented.
8. **Budget honesty:** actual consumed resources and failed attempts count against the budget.
9. **Reproducible control:** identical specification, evidence and policy version should produce the same action/decision unless a declared nondeterministic component is involved.
10. **Fail closed:** missing assumptions, invalid estimator applicability or unverifiable provenance cannot be converted into a pass.

## 8. Prior art and novelty boundary

The ingredients are established. DSCA must not be presented as the invention of goal-oriented adaptivity or computational value-of-information.

Closest work includes:

1. **Oden & Prudhomme (2001), “Goal-oriented error estimation and adaptivity for the finite element method.”** Develops QoI-focused a posteriori error estimation and goal-oriented adaptive procedures for elliptic problems. [Publisher record](https://doi.org/10.1016/S0898-1221(00)00317-5).
2. **Becker, Gantner, Innerberger & Praetorius (2023), “Goal-oriented adaptive finite element methods with optimal computational complexity.”** Analyses joint steering of mesh refinement and iterative solver work using computable a posteriori goal-error estimates; proves convergence and optimal rates under stated assumptions. [Open-access article](https://doi.org/10.1007/s00211-022-01334-8).
3. **Bespalov, Praetorius, Rocchi & Ruggeri (2019), goal-oriented error estimation and adaptivity for elliptic PDEs with parametric or uncertain inputs.** Combines spatial and parametric adaptivity for QoIs under uncertain inputs with reliable a posteriori estimates. [Publisher record](https://doi.org/10.1016/j.cma.2018.10.041).
4. **Endtmayer et al. (2024), “A posteriori single- and multi-goal error control and adaptivity for partial differential equations.”** Reviews single- and multi-goal error control, adaptivity and solver control, including coupled-field problems. [Publisher record](https://doi.org/10.1016/bs.aams.2024.08.003).
5. **Goal-oriented estimation with inexact solvers (2020).** Demonstrates decomposition of goal-error estimates into primal/dual discretisation and algebraic components, including stopping criteria for iterative solvers. [Publisher record](https://doi.org/10.1016/j.cam.2019.112367).

Potential contribution is the explicit coupling of:
- engineering decision semantics and multiple constraints/QoIs;
- typed action eligibility across solver, discretisation, fidelity, sampling and verification;
- bounded versus calibrated probabilistic versus heuristic assurance modes without conflation;
- evidence dependence and provenance tracking;
- resource-budgeted value-of-computation action selection;
- terminal outcomes ACCEPT, REJECT, INCONCLUSIVE or REFUSE rather than merely “solver converged”.

Adjacent work may already cover parts of this combination, especially Bayesian experimental design, active learning, reliability-based design optimisation, multi-fidelity optimisation and goal-oriented UQ. **No novelty claim is established by this memo.** A systematic literature and patent review is required before publication or marketing claims.

## 9. Falsifiable research hypotheses

### H1 — Decision-aware computation saves cost
On benchmark problems where the decision is insensitive to some regions or solution components, DSCA reaches the same defensible decision and assurance level at lower total cost than uniform refinement, conventional QoI-goal-oriented adaptivity and a fixed solver/refinement policy.

**Kill criterion:** no meaningful cost reduction across a predeclared benchmark set, or gains disappear when setup, estimator, verification and failed-run costs are included.

### H2 — Decision sufficiency avoids unnecessary over-solving
For cases with large decision margin, DSCA stops earlier than a fixed QoI-accuracy target while preserving the same decision under a valid bound or calibrated risk rule.

**Kill criterion:** early stopping changes the decision in adversarial near-boundary cases or relies on uncalibrated estimates.

### H3 — Multi-action planning beats single-axis adaptivity
Selecting among solver work, mesh/order refinement, additional uncertainty samples and higher-fidelity analysis improves cost to decision sufficiency compared with mesh-only adaptivity.

**Kill criterion:** action-selection overhead exceeds savings, or the policy cannot outperform a tuned baseline on held-out cases.

### H4 — Assurance-aware refusal improves trust
DSCA detects missing applicability, model, provenance or validation obligations and returns inconclusive/refusal instead of a false pass.

**Kill criterion:** adversarial cases produce unsupported acceptance, or refusal rates make the system unusable without measurable reduction in false acceptance.

### H5 — Policy generalises
A policy calibrated on one problem family transfers to held-out geometries, materials, loads and QoIs without unsafe degradation.

**Kill criterion:** reliability collapses under modest distribution shift and no reliable out-of-domain detector catches it.

## 10. Benchmark programme

Begin with small, interpretable problems before multiphysics.

| Benchmark family | Decision/QoI | Candidate actions | Main stress case |
|---|---|---|---|
| 2D linear elasticity | maximum displacement / stress constraint | algebraic solve, local refinement, QoI estimator | stress concentration and singularity |
| Steady heat conduction | maximum temperature / heat flux limit | refinement, flux reconstruction, material sampling | high conductivity contrast |
| Linear diffusion with uncertain coefficient | probability of threshold exceedance | spatial refinement, parameter sampling | correlated uncertain inputs |
| Thermal-mechanical coupling | displacement and temperature constraints | physics/fidelity escalation | coupled error and model discrepancy |
| Design comparison | choose A or B under constraints | targeted QoI computation, sampling, higher fidelity | near-tie and decision reversal |

For each case, record reference decision and how it was established; QoI error and assurance class; decision loss/risk where defined; action sequence and rejected actions; cumulative wall time, CPU time and peak memory; solver iterations, DOFs and samples; verification overhead; decision reversals and false acceptance/refusal counts; reproducibility across seeds and machines.

Comparisons must be matched by engineering decision, acceptance criteria and assurance class—not merely equal DOFs or solver residual.

## 11. Minimal prototype scope (future, after campaign approval)

Do not implement this now. Once current WP0–WP7 gates are complete and the owner authorises the work:

1. Define a small typed decision specification for one QoI and one deterministic constraint.
2. Support one physics family with a genuinely applicable QoI error bound.
3. Implement interval-based decision sufficiency first; defer Bayesian action-value optimisation.
4. Start with two actions: one additional algebraic solve step and one admissible mesh refinement.
5. Use a deterministic action policy and log every decision.
6. Validate against uniform refinement and conventional goal-oriented adaptivity.
7. Add uncertain inputs and multi-action planning only after the deterministic controller passes adversarial tests.

This isolates the central hypothesis without depending on an unvalidated probabilistic risk model.

## 12. Decisions required before implementation

- Which decision class is first: pass/fail constraint, design ranking, or multi-constraint acceptance?
- Which QoIs and assurance mode are supported in the first vertical slice?
- Which error components must be bounded before issuing a robust decision?
- What resource budget is controlled: wall time, CPU/GPU time, memory, energy, monetary cost, or a vector?
- How are model-form uncertainty and experimental validation represented?
- Which action families are eligible in the first implementation?
- What false-acceptance and refusal rates are acceptable for the intended research use?

These are owner/architecture decisions, not assumptions to hard-code.

## 13. Conclusion

DSCA is a plausible GDEC research direction, but its novelty and practical advantage are unproven. Its strongest defensible formulation is:

**A constrained, evidence-aware controller that selects computational actions to establish a declared engineering decision at minimum admissible cost, while preserving explicit mathematical assurance boundaries and refusing when evidence is insufficient.**

The first research milestone should test whether this decision-level objective yields measurable benefit over established goal-oriented adaptivity—not build a general autonomous simulation agent.

## References

- Oden, J. T. & Prudhomme, S. (2001). Goal-oriented error estimation and adaptivity for the finite element method. *Computers & Mathematics with Applications*, 41(5–6), 735–756. https://doi.org/10.1016/S0898-1221(00)00317-5
- Becker, R., Gantner, G., Innerberger, M. & Praetorius, D. (2023). Goal-oriented adaptive finite element methods with optimal computational complexity. *Numerische Mathematik*, 153, 111–140. https://doi.org/10.1007/s00211-022-01334-8
- Bespalov, A., Praetorius, D., Rocchi, L. & Ruggeri, M. (2019). Goal-oriented error estimation and adaptivity for elliptic PDEs with parametric or uncertain inputs. *Computer Methods in Applied Mechanics and Engineering*, 345, 951–982. https://doi.org/10.1016/j.cma.2018.10.041
- Endtmayer, B. et al. (2024). A posteriori single- and multi-goal error control and adaptivity for partial differential equations. *Advances in Applied Mechanics*, 59, 19–108. https://doi.org/10.1016/bs.aams.2024.08.003
- Goal-oriented a posteriori error estimation for conforming and nonconforming approximations with inexact solvers (2020). *Journal of Computational and Applied Mathematics*, 366, 112367. https://doi.org/10.1016/j.cam.2019.112367
