# DSCA v0.2 — Decision-Witness and Assurance-Obligation Planning

**Working algorithm name:** DWAOP — Decision-Witness and Assurance-Obligation Planning  
**Parent concept:** Decision-Sufficiency Computation Algorithm (DSCA)  
**Status:** RESEARCH PROPOSAL — NOT IMPLEMENTED, NOT VALIDATED, NOT APPROVED FOR PRODUCTION  
**Branch:** `research/decision-sufficiency-algorithm`  
**Supersedes as the active algorithm proposal:** DSCA specification v0.1. The v0.1 documents remain as historical baseline and comparison material.

---

## 0. Executive decision

The v0.1 formulation was too close to a broad collection of established ideas: goal-oriented adaptivity, value of information, multi-fidelity action selection, uncertainty reduction and evidence gating. A cost ratio over a wider set of actions is not a novel algorithm.

The v0.2 proposal changes the core computational problem.

**DWAOP does not simply choose the next computation with the highest expected uncertainty reduction. It constructs and attempts to eliminate explicit decision-reversing counterexamples while simultaneously satisfying non-tradeable assurance obligations. It plans over sequences of proof-producing computational actions under hard, multi-resource budgets.**

The proposed core is a bounded-mode controller. Probabilistic active learning is kept as a separate extension, not mixed into the first algorithm.

The possible contribution is the combination of:

1. decision-witness generation from a joint admissible QoI set;
2. typed evidence/action contracts describing which witnesses an action can legitimately exclude and which assurance obligations it can discharge;
3. an AND-OR planner that searches action sequences, not only one-step greedy scores;
4. robust terminal conditions requiring both elimination of decision-reversing witnesses and completion of all mandatory obligations;
5. vector resource budgets with worst-case path accounting;
6. independent checking of every proof-producing update.

This is a **candidate research contribution**, not an established novelty, proof of patentability or performance result. Closely related work and a preliminary patent landscape are summarised in Section 11.

## 1. What is being changed from v0.1

| v0.1 element | Problem identified | v0.2 change |
|---|---|---|
| General value-of-computation score | Broadly established; model calibration is difficult | Not the core of the bounded algorithm |
| Uncertainty-width reduction per cost | Can spend work reducing irrelevant uncertainty | Generate decision-reversing witnesses and plan to eliminate them |
| One-step greedy action selection | Can miss complementary action sequences | Robust AND-OR action-sequence planning |
| Evidence obligations as a final gate | Does not tell the planner how to close several linked obligations | Obligations become explicit planning state and action effects |
| Single scalar cost | Hides time/memory/energy/budget conflicts | Hard resource vector and Pareto plan costs |
| Monotone shrinking of the QoI set | New evidence can expose inconsistency or model invalidity | Sound state updates may narrow, invalidate or enlarge the model set; conflicts trigger fail-closed handling |
| Mixed bounded and probabilistic ambition | Too large and risks treating incompatible claims as one score | First algorithm is bounded/set-based; probability mode is a separate future method |

The v0.1 worked heat example remains useful, but it is a hand-traced toy case, not validation of v0.2.

## 2. Formal problem

Let:

- (m): declared mathematical/physical model and its assumptions;
- (q\in\mathbb R^k): vector of decision-relevant quantities of interest (QoIs);
- \(\mathcal Q(E)\): joint admissible QoI set implied by valid evidence \(E\);
- \(\mathcal D\): allowed engineering decisions;
- \(L(d,q)\): declared decision loss;
- \(\tau\): decision-regret tolerance fixed before computation;
- \(\mathcal O\): mandatory assurance obligations;
- \(\mathbf B\): remaining hard resource budget vector;
- \(\mathcal A\): available computational actions.

The evidence state is:

\[
S=(\mathcal Q,\mathcal O,\mathcal G,\mathbf B,\mathcal M),
\]

where:

- \(\mathcal Q\) is the joint QoI admissible set;
- \(\mathcal O\) is the set of open/satisfied/blocked obligations;
- \(\mathcal G\) is a typed evidence-dependence and provenance graph;
- \(\mathbf B\) is the remaining resource vector;
- \(\mathcal M\) records model identity, applicability assumptions and invalidation state.

No independence is assumed merely because two uncertainty components are stored separately. Correlation and shared derivation are represented in \(\mathcal G\).

### 2.1 The admissible QoI set

\(\mathcal Q(E)\) must be a sound outer set for the QoIs under the declared model and included uncertainty assumptions. It may be represented by intervals, polytopes, ellipsoids, zonotopes, constrained parameter sets or another mathematically defined set representation.

A vector of independent scalar intervals is not a valid substitute for a joint set when correlations or shared parameters matter.

The set covers only declared and modelled uncertainty. It does not silently include unknown model-form error, physical reality, omitted physics or unmeasured operating conditions. Uncovered uncertainty remains an open obligation or explicit limitation.

## 3. Decision witnesses: the central mechanism

### 3.1 General decision problem

For a candidate decision \(d\), define pointwise regret:

\[
r(d,q)=L(d,q)-\min_{d'\in\mathcal D}L(d',q).
\]

The worst-case regret over the admissible set is:

\[
\rho(d\mid\mathcal Q)=\sup_{q\in\mathcal Q}r(d,q).
\]

Select a robust incumbent:

\[
\hat d\in\arg\min_{d\in\mathcal D}\rho(d\mid\mathcal Q).
\]

The bounded decision is sufficient only when:

\[
\rho(\hat d\mid\mathcal Q)\le\tau
\]

and all mandatory obligations are satisfied.

A **decision witness** is an admissible QoI configuration under which the incumbent decision exceeds its permitted regret:

\[
\mathcal W_\tau(\hat d,\mathcal Q)
=
\{q\in\mathcal Q:r(\hat d,q)>\tau\}.
\]

The decision is regret-sufficient exactly when this witness set is empty, subject to the accuracy of the set and optimisation calculations.

For multiple alternatives, the witness set may be partitioned by the alternative decision that beats the incumbent. This exposes which decision reversal remains possible.

### 3.2 Constraint decision as a special case

For a pass/fail requirement:

\[
g_j(q)\le0,\qquad j=1,\ldots,p,
\]

the violation witness set for constraint \(j\) is:

\[
\mathcal W_j^+(\mathcal Q)
=
\{q\in\mathcal Q:g_j(q)>0\}.
\]

Robust acceptance requires:

\[
\sup_{q\in\mathcal Q}g_j(q)\le0
\quad\text{for every mandatory constraint }j.
\]

Robust rejection of a particular constraint requires:

\[
\inf_{q\in\mathcal Q}g_j(q)>0.
\]

Otherwise the constraint remains unresolved. A feasible violating witness is sufficient to refute robust acceptance; absence of a witness is not established by a local optimiser failing to find one. It requires a valid global upper bound, exhaustive method or sound outer approximation.

### 3.3 Witness certificates

For each unresolved witness or decision-reversing region, the controller records:

- the affected decision or constraint;
- a witness point or sound outer representation of the witness region;
- the QoI components and model assumptions involved;
- the optimisation/interval method and its assurance class;
- the evidence dependencies used to construct it;
- whether the witness is confirmed, merely suspected, or globally excluded.

A heuristic optimiser can propose a witness candidate. It cannot prove that no witness exists. The independent checker must distinguish a verified feasible counterexample from an unverified candidate.

## 4. Assurance obligations are first-class planning state

An obligation is not a soft objective and cannot be traded against a larger reduction in QoI uncertainty.

Each obligation \(o_i\) contains:

| Field | Meaning |
|---|---|
| `obligation_id` | Stable identifier |
| `claim` | Exact claim that must be supported |
| `scope` | Model, QoI, operating envelope and configuration to which it applies |
| `required_evidence_type` | Mathematical bound, independent check, validation result, provenance proof, etc. |
| `acceptance_rule` | Machine-checkable condition for discharging it |
| `dependencies` | Other evidence and assumptions needed |
| `status` | OPEN, SATISFIED, BLOCKED, CONFLICTED, INAPPLICABLE |
| `owner` | Authority responsible for approving the obligation and assurance level |

Examples: a certified discretisation bound for a target QoI, independent verification of a numerical certificate, a declared material-property envelope, an experimental validation comparison, or exact run provenance.

The planner may not lower or delete an obligation. Only an authorised change to the problem specification can change the obligation set, and that change must create a new specification identity.

## 5. Proof-producing computational action contracts

An action is no longer described only by its expected cost and uncertainty reduction. Each action has a typed contract:

\[
a=(P_a,T_a,C_a,Y_a,K_a,D_a,F_a),
\]

where:

- \(P_a\): preconditions and applicability predicate;
- \(T_a\): affected evidence channels and witness types;
- \(C_a\): hard upper-bound resource vector;
- \(Y_a\): conservative cover of possible action outcomes;
- \(K_a\): evidence/certificate contract;
- \(D_a\): dependencies and shared assumptions;
- \(F_a\): failure, conflict, invalidation and timeout semantics.

A proof-producing action must return an artefact containing at least:

1. exact input/model/configuration identity;
2. method/backend/version and applicability conditions;
3. typed claim and its mathematical scope;
4. output data and error/bound information;
5. dependency references;
6. measured resource cost;
7. integrity/provenance data;
8. verifier result or explicit not-yet-verified status.

An action may only exclude points from \(\mathcal Q\) when the action's evidence contract and independent checker justify that exclusion. A solver run, an estimator status string or an LLM explanation is not automatically a proof-producing action.

Actions may target different evidence channels:

- algebraic/numerical error;
- discretisation and representation;
- input/parameter uncertainty;
- model-form uncertainty;
- experimental validation;
- provenance/integrity;
- an obligation that requires independent verification.

A mesh refinement cannot claim to resolve uncertain conductivity data. A second solver using the same equations cannot claim experimental validation. A GPU action that did not execute on the GPU cannot produce GPU performance evidence.

## 6. Evidence-state transition

For state \(S\), action \(a\) and an outcome cell \(y\in\mathcal Y_a(S)\), define:

\[
S'=T(S,a,y).
\]

A valid transition may:

- add a verified evidence artefact;
- remove a decision witness by soundly excluding an admissible QoI region;
- discharge one or more obligations;
- reveal a conflict between evidence sources;
- invalidate a previous model assumption and enlarge/rebuild the admissible set;
- consume resources and update the provenance/dependence graph.

**Important correction to v0.1:** valid new evidence is not required to monotonically shrink \(\mathcal Q\). For example, an experiment may reveal that the assumed material model is inadequate, requiring a larger model set or a different model. Soundness, configuration identity and explicit invalidation matter; monotone uncertainty reduction does not.

If new evidence produces an empty intersection between previously asserted sound sets, the planner must not interpret this as zero uncertainty. It must mark the evidence state CONFLICTED, preserve the source artefacts and refuse the affected assurance claim until the conflict is resolved.

Every possible outcome of an action must be represented by \(\mathcal Y_a(S)\). If the controller cannot provide a sound outcome cover, it cannot claim a worst-case guarantee for the plan. An exploratory action may still be run under a non-assured mode, but its uncertainty reduction must not be guaranteed in advance.

## 7. DWAOP: robust AND-OR planning algorithm

### 7.1 The planning objective

A policy \(\pi\) chooses an action at each reachable state and branches on the observed, conservatively covered outcomes.

The objective is to find a policy that resolves all mandatory decision witnesses and obligations at minimum worst-case cost:

For each policy, define its worst-case resource vector by taking the componentwise supremum over all covered outcome paths:

\[
\overline{\mathbf C}(\pi)
=
\sup_{\omega\in\Omega(\pi)}^{\mathrm{componentwise}}
\sum_{a\in\pi(\omega)}\mathbf c_a^\uparrow.
\]

The feasible-policy set contains only policies whose every covered branch reaches a terminal decision with all obligations satisfied and whose worst-case resource vector fits the hard budget. The planner returns the nondominated set:

\[
\Pi^*(S)=\operatorname{ParetoMin}
\left\{
\overline{\mathbf C}(\pi):
\pi\text{ is feasible from }S
\right\}.
\]

If an owner-specified preference is needed to select one plan from this Pareto set, the preference must be explicit. The algorithm does not invent weights for unlike resources.

subject to, for every reachable terminal branch \(\omega\):

\[
\begin{aligned}
&\text{DecisionGate}(S_\omega)=\text{true},\\
&\mathcal O_\omega=\varnothing,\\
&\text{EvidenceIntegrity}(S_\omega)=\text{valid},\\
&\mathbf C(\pi,\omega)\preceq\mathbf B.
\end{aligned}
\]

Here \(\Omega(\pi)\) is the set of all outcome branches covered by the policy. \(\preceq\) is componentwise resource comparison. Resource dimensions can include wall-clock time, CPU time, accelerator time, peak memory, energy and monetary cost.

No single scalarisation is imposed when the owner has not supplied defensible resource weights. The planner retains a Pareto set of feasible cost vectors.

A policy that satisfies the planning constraints must resolve every covered outcome branch to an allowed terminal decision with all obligations met. A branch that ends INCONCLUSIVE or REFUSE is not counted as a successful feasible plan; it is reported as a safe failure of the plan and the controller must not issue ACCEPT. The planner cannot omit adverse outcomes to make a plan look feasible.

### 7.2 AND-OR recursion with vector costs

For a finite, sound abstraction of the evidence state and action outcomes, define \(\mathcal J(S)\) as the Pareto frontier of worst-case resource vectors for robust decision-completing policies from state \(S\).

For a terminal state with a satisfied decision gate and no open obligations:

\[
\mathcal J(S)=\{\mathbf 0\}.
\]

For a non-terminal state, consider an eligible action \(a\). For **every** covered outcome \(y\in\mathcal Y_a(S)\), select a feasible continuation vector \(\mathbf j_y\in\mathcal J(T(S,a,y))\). The worst-case resource vector for that contingent plan is:

\[
\mathbf v(a,\{\mathbf j_y\})
=
\mathbf c_a^\uparrow
+
\operatorname{cmax}_{y\in\mathcal Y_a(S)}\mathbf j_y,
\]

where \(\operatorname{cmax}\) takes the componentwise maximum across all outcome branches. The state's plan-cost frontier is:

\[
\mathcal J(S)=
\operatorname{ParetoMin}
\left\{
\mathbf v(a,\{\mathbf j_y\}):
a\in\mathcal A(S),\mathbf j_y\in\mathcal J(T(S,a,y))\;\forall y
\right\}.
\]

If an outcome branch has no feasible continuation, that action cannot be part of a guaranteed decision-completing policy. If no action yields a feasible vector, \(\mathcal J(S)=\varnothing\). A resource budget \(\mathbf B\) admits a plan only when at least one frontier vector satisfies \(\mathbf j\preceq\mathbf B\).

This is the proposed multi-resource formulation. A scalarised version may be used for a separately declared single-objective experiment, but the core planner must not invent exchange rates between time, memory, energy or money.

The action choice is an OR node. Its conservatively covered outcomes are AND branches: every branch must be handled.

### 7.3 Receding-horizon controller

The first practical policy should use bounded look-ahead and recompute after each verified outcome:

~~~text
DWAOP(spec, resource_budget):
    validate_specification_and_decision_rules(spec)
    obligations = compile_mandatory_obligations(spec)
    state = establish_initial_sound_QoI_set_and_provenance(spec)

    if specification_invalid_or_claim_inapplicable:
        return REFUSE(reason, state)

    repeat:
        verify_state_integrity_and_model_identity(state)
        witnesses = generate_decision_reversing_witnesses(state.Q)
        decision = evaluate_robust_decision(state.Q, witnesses)

        if decision.robust and obligations.all_satisfied:
            return TERMINAL_DECISION(decision, certificate_bundle, cost_trace)

        blockers = witnesses + obligations.open_or_conflicted
        actions = enumerate_supported_actions(state)

        for action in actions:
            validate_preconditions_and_evidence_contract(action, blockers)
            derive_sound_outcome_cover(action)
            calculate_upper_resource_cost(action)

        plan = bounded_AND_OR_search(
            state,
            eligible_actions,
            hard_resource_budget,
            mandatory_obligations,
            terminal_decision_gate
        )

        if plan is absent:
            if specification_or_required_claim_is_invalid:
                return REFUSE(reason, state)
            return INCONCLUSIVE(blockers, budget, rejected_action_reasons)

        action = first_action(plan)
        result = execute_and_record_actual_cost(action)

        if result.failed_or_timed_out:
            charge_actual_cost(result)
            update_failure_state_and_replan()
            continue

        proposed_state = apply_typed_evidence_transition(state, result)
        checker_result = independently_check_transition(proposed_state)

        if checker_result != VERIFIED:
            preserve_artifacts_and_mark_conflict_or_incomplete()
            state = fail_closed_state()
        else:
            state = proposed_state
~~~ 

The pseudo-code intentionally does not specify executable APIs or a current GDEC runtime implementation.

### 7.4 Terminal outcomes

- `ACCEPT`: every required constraint/decision condition is robust over the sound admissible set; regret is within tolerance; all mandatory obligations are satisfied.
- `REJECT`: valid evidence robustly establishes violation or a decision rule selects rejection across the admissible set.
- `INCONCLUSIVE`: a decision witness remains and no robust plan fits the remaining resources/capabilities, or outcome coverage is insufficient.
- `REFUSE`: specification, model applicability, evidence integrity or required assurance request is invalid/unsupported; the system cannot honestly attempt the requested claim.

A budget-exhausted unresolved case is never `ACCEPT`. A non-positive estimated value of information is never sufficient to terminate successfully.

## 8. Correctness property to prove

### Proposition (conditional soundness of bounded terminal decisions)

Assume:

1. the initial admissible set \(\mathcal Q_0\) contains every QoI value permitted by the declared mathematical model and explicitly included uncertainty assumptions;
2. every action transition is sound: for every possible real outcome covered by the action contract, the resulting set and evidence state still contain all QoI values consistent with that outcome and the declared model;
3. evidence obligations are discharged only by artefacts that satisfy their stated predicates and have valid provenance;
4. the independent checker correctly verifies the soundness conditions of every transition and the terminal decision calculation;
5. the terminal acceptance condition establishes \(g_j(q)\le0\) for every \(q\in\mathcal Q\) and every required constraint (or establishes the declared minimax-regret condition).

Then a terminal `ACCEPT` is sound **with respect to the declared model and included uncertainty assumptions**.

**Proof sketch:** By assumption 1, the true model-consistent QoI lies in \(\mathcal Q_0\). By assumption 2, each verified transition preserves containment of all model-consistent QoIs. Induction over the finite action sequence therefore preserves containment at every reachable state. At a terminal `ACCEPT`, the checked predicate holds for every element of the terminal outer set; it therefore holds for the model-consistent QoI. Assumption 3 ensures required evidence claims have their stated support. This does not prove that the physical model is true, that omitted uncertainty is absent, or that the engineering system is safe outside the declared scope.

This proposition is conditional and straightforward. It is **not yet a complete proof of DWAOP**, because the soundness of action contracts, outcome covers, optimisation, evidence checking and the implementation remains to be established.

## 9. Computational tractability and limitations

The AND-OR search can grow exponentially with plan depth and action outcomes. The continuous QoI set and nonlinear decision rules can also make witness generation expensive.

First implementation research should therefore be restricted to:

1. linear deterministic QoI constraints over interval or polyhedral sets;
2. a small, finite action portfolio;
3. a finite set of sound outcome partitions;
4. one or two mandatory proof obligations;
5. short bounded plan depth;
6. deterministic action selection and auditable branch pruning.

Potential methods:

- linear programming for affine decision constraints over polytopes;
- interval branch-and-bound or validated global optimisation for nonlinear constraints;
- admissible lower bounds on remaining action cost;
- dominance pruning only when a plan state is no worse in every obligation, decision and resource dimension;
- memoisation by canonical state identity;
- bounded-horizon search with explicit `SEARCH_LIMIT_REACHED` outcome.

A heuristic search timeout is not evidence that no plan exists. It returns `INCONCLUSIVE` unless a formal lower-bound argument establishes infeasibility.

## 10. What may be new, and what is not

### Established ingredients — not novelty claims

- Goal-oriented error estimation and adaptive refinement.
- Joint steering of mesh refinement and iterative solver work.
- Multi-goal and coupled-physics error control.
- Multi-fidelity cost-aware active learning and reliability-based sampling.
- Expected value of information / optimal computing budget allocation.
- Counterexample-guided abstraction refinement.
- Assurance cases, evidence graphs, verification and provenance tracking.
- Resource-constrained AND-OR / contingent planning.

### Narrow candidate contribution

The research hypothesis is that the following integrated mechanism is not adequately covered by the closest identified engineering computation methods:

**A computation planner whose state is a sound joint QoI set plus explicit assurance obligations; whose action contracts can only eliminate decision witnesses or discharge obligations through independently checked evidence; and whose planner chooses robust action sequences under vector resource budgets, returning an explicit non-acceptance result whenever any outcome branch cannot satisfy the decision and assurance gates.**

A novelty claim would require showing that this is more than a straightforward engineering combination of robust optimisation, proof obligations, adaptive numerical methods and contingent planning.

### Explicit non-claims

Do not claim:
- first goal-oriented adaptive computation;
- first solver/mesh cost controller;
- first multi-fidelity cost-aware active learning;
- first use of counterexamples to guide refinement;
- first AI simulation decision platform;
- first evidence graph or assurance case;
- patentability or freedom to operate.

## 11. Prior-art and patent landscape (initial search, not exhaustive)

| Prior work | What it already covers | Consequence for DWAOP |
|---|---|---|
| Becker et al., 2023, goal-oriented AFEM | QoI-oriented mesh refinement and iterative-solver steering; convergence and optimal rates with respect to total computational cost under stated assumptions | Do not claim novelty for solver/mesh co-steering or total-cost-aware QoI adaptivity |
| Yang et al., 2024, active learning for RBDO under multiple simulation models | Active constraints, model selection and different simulation costs in reliability-based design optimisation | Do not claim novelty for cost-aware action/fidelity selection in reliability optimisation |
| Solak et al., arXiv:2610.38582, 28 Oct 2026, MF-CAS preprint | Joint sample-location and fidelity selection using decomposed uncertainty intervals and model cost | Do not claim novelty for decomposed interval uncertainty plus joint cost-aware sampling/fidelity selection |
| Zhao et al., Reliability Engineering & System Safety, online 20 Nov 2026, MF-PBALC | Posterior-mean failure-probability bounds, a stopping rule, a learning function and cost-aware joint evaluation-point/fidelity selection | Do not claim novelty for bound-based stopping or cost-aware joint fidelity selection in structural reliability |
| CEGAR literature | Counterexample generation, validation and guided abstraction refinement | Do not claim novelty for counterexample-guided refinement alone |
| ACCESS, *Assurance Case Centric Engineering of Safety-critical Systems* (2024) | Model-based assurance-case/artifact management, traceability, automatic invocation of formal verification evidence, machine-checking assurance logic and change-impact analysis | Do not claim novelty for machine-readable assurance obligations, evidence graphs, or automatic verification evidence integration in isolation |
| Automated assurance-case pattern selection for CPS (2022) | Formulates selection/coverage of assurance-case patterns with graph analytics and optimisation | Do not claim novelty for obligation coverage or minimising evidence-pattern sets alone |
| NASA, *Guided Integration of Formal Verification in Assurance Cases* (2023) | Captures formal verification method constraints and evidence in assurance cases | Do not claim novelty for connecting verification-tool applicability constraints to assurance evidence alone |
| US20240348663A1, “AI-enhanced simulation and modeling experimentation and control” | Broad published claims for an AI simulation/experimental-design decision platform with goals/constraints, targeted exploration, uncertainty reduction, model adjustment and planning/search features | Potential adjacent patent scope; requires patent-professional review. This document does not determine claim construction, infringement or freedom to operate |

### 11.1 Revised novelty boundary

The following pieces are individually known or have close analogues: QoI adaptation, solver/mesh co-control, multi-fidelity cost-aware sampling, counterexample-guided refinement, assurance-case graphs, verification evidence integration, and resource-aware look-ahead planning.

The narrower candidate hypothesis is therefore not any one of those components. It is their **specific coupling in a bounded numerical-engineering computation controller**:

- the primary state is a sound joint QoI set, not a surrogate-only prediction;
- unresolved decision alternatives are represented as explicit decision witnesses;
- each computation action has a typed contract specifying the witnesses it can exclude, the assurance obligations it can discharge, the assumptions it shares and the exact evidence it emits;
- a robust AND-OR planner searches contingent action sequences, with every outcome branch represented;
- a vector-valued resource planner seeks a Pareto frontier of worst-case costs;
- only independently checked, scope-valid evidence can alter the admissible set or close an obligation;
- a terminal decision is permitted only when the witness set is empty (or minimax regret is within the declared tolerance) and every mandatory obligation is satisfied.

This combination may still be obvious or already disclosed when compared with assurance-case planning, formal verification, robust optimisation and contingent planning. The literature search has not established a gap. A targeted search must now examine those combinations and their patent claims, not merely search the phrase “decision sufficiency”.

### 11.2 Primary links

- Becker et al. (2023), *Numerische Mathematik*: https://doi.org/10.1007/s00211-022-01334-8
- Yang et al. (2024), *Structural Safety*: https://doi.org/10.1016/j.strusafe.2023.102426
- Solak et al. (2026), MF-CAS preprint: https://arxiv.org/abs/2610.38582
- Zhao et al. (2026), MF-PBALC: https://doi.org/10.1016/j.ress.2026.113871
- Clarke et al. (2000), CEGAR, CAV: https://doi.org/10.1007/10722167_15
- Clarke et al. (2003), CEGAR expanded journal treatment: https://doi.org/10.1145/876638.876643
- ACCESS (2024), *Journal of Systems and Software*: https://doi.org/10.1016/j.jss.2024.112034
- NASA, *Guided Integration of Formal Verification in Assurance Cases*: https://ntrs.nasa.gov/citations/20230007599
- Automated assurance-case pattern selection for CPS (2022): https://doi.org/10.1007/978-3-031-14835-4_6
- Patent publication: https://patents.google.com/patent/US20240348663A1/en

The patent was located through a preliminary search. Google Patents lists this publication as pending and shows a long priority/family chain; its own page warns that legal status is not a legal conclusion. Claims 1, 8 and 12 explicitly discuss goal/constraint-driven simulation and uncertainty reduction, active-learning/targeted exploration, and adaptive look-ahead/branching subject to resources. This is a material adjacent disclosure to review with a patent professional; it does not establish whether any specific DWAOP claim is anticipated, obvious, infringing or free to operate.

## 12. Required novelty experiments

The central experiment is not merely “does DWAOP use fewer DOFs?” It is whether proof-obligation-aware planning gives a better cost/assurance frontier than a strong combination of existing methods.

### Baselines

1. uniform refinement / fixed solver tolerances;
2. conventional goal-oriented AFEM;
3. GOAFEM-like joint mesh/solver steering where applicable;
4. cost-aware multi-fidelity active learning for problems with fidelity levels;
5. a greedy action selector using the same action contracts but no look-ahead;
6. DWAOP with witness/obligation planning;
7. offline oracle policy for retrospective lower-bound comparison only.

### Benchmark stages

**Stage A — deterministic bounded constraint**

- one QoI and one deterministic constraint;
- a mathematically valid QoI enclosure;
- actions: solver work, refinement, independent verification;
- one or two required obligations;
- linear or polyhedral decision set.

**Stage B — multiple constraints and QoIs**

- several constraints with different active margins;
- shared material/load/geometry uncertainty;
- evidence dependencies between estimators and solver outputs;
- action portfolios with complementary effects.

**Stage C — model and validation blockers**

- a mesh refinement cannot close model-form discrepancy;
- a higher-fidelity model or experiment may be required;
- planner must distinguish an unresolved but reducible blocker from an unsupported assurance claim.

**Stage D — resource conflicts**

- wall time, memory and compute budgets jointly limited;
- actions with setup/transfer/verification costs;
- failed actions and timeouts charged to actual resources.

### Primary metrics

- false acceptance count and rate (with confidence intervals where statistically applicable);
- decision correctness versus an independently established reference;
- proportion of runs reaching a supported terminal decision;
- proportion of mandatory obligations discharged;
- worst-case and actual resource consumption;
- total cost to supported decision;
- cost regret versus offline oracle;
- planner overhead and search nodes;
- unsafe pruning, unsupported action effects and evidence conflicts;
- rate of honest `INCONCLUSIVE`/`REFUSE` outcomes.

### Kill criteria

Stop or narrow the research if any of the following occurs:

1. a false `ACCEPT` occurs on the predeclared bounded adversarial suite;
2. DWAOP cannot outperform the greedy action planner or strong adaptive baselines after including all overheads;
3. the AND-OR planner's overhead exceeds the computation saved;
4. its sound action contracts cannot be authored or checked for realistic engineering actions;
5. it mostly returns `INCONCLUSIVE` without a measurable reduction in false acceptance;
6. prior-art review finds the full combination already disclosed in a technically equivalent method or claim set.

## 13. First proposed prototype (not authorised by this document)

Once the existing GDEC WP0–WP7 reliability campaign is formally closed and the owner authorises implementation:

- use one deterministic heat-conduction QoI and a genuinely valid bound;
- one pass/fail constraint;
- three actions: solver tightening, mesh refinement and independent certificate check;
- one non-tradeable verification obligation;
- two resource dimensions: wall time and peak memory;
- finite sound action outcome abstractions;
- bounded AND-OR search depth of at most three actions;
- an independent checker for state transitions and terminal decision;
- adversarial tests for wrong-QoI bound, near-boundary decision, conflicting evidence, action timeout and budget exhaustion.

No GPU, probabilistic reliability or full multi-physics scope in the first prototype. It should be compared against a greedy selector and conventional adaptive FEM. If the prototype does not show an advantage or reliable new assurance behaviour, stop.

## 14. Research status and next gate

- **RESEARCHED:** selected recent GOAFEM, active-learning, multi-fidelity reliability and CEGAR literature; one adjacent patent publication identified.
- **FORMULATED:** decision-witness state, obligation state, typed action contracts, robust AND-OR planning objective, vector budgets.
- **CONDITIONALLY JUSTIFIED:** terminal soundness proposition under explicit enclosure, transition and checker assumptions.
- **NOT PROVEN:** global optimality, tractability at scale, novelty, patentability or freedom to operate.
- **NOT IMPLEMENTED:** no production or research controller code.
- **NOT TESTED:** no controller benchmark or adversarial implementation test run.
- **NOT INDEPENDENTLY VERIFIED:** no external mathematical review.
- **NOT APPROVED:** no production implementation authorisation.

**Next gate:** independent review of the formal state/action model and soundness assumptions, then a hand-computed action-planning example with at least two complementary actions and a branching outcome. Only after that should the research prototype be proposed.
