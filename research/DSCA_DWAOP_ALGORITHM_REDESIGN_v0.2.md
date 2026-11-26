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

Let the joint admissible QoI set be \(\mathcal Q\), and let the complete feasible decision region be:

\[
\mathcal F=\{q:g_j(q)\le0\;\forall j=1,\ldots,p\}.
\]

The three-way robust decision is:

- **Robustly acceptable:** \(\mathcal Q\subseteq\mathcal F\), equivalently \(\sup_{q\in\mathcal Q}g_j(q)\le0\) for every mandatory constraint \(j\).
- **Robustly rejectable:** \(\mathcal Q\cap\mathcal F=\varnothing\), equivalently every admissible QoI state violates at least one mandatory constraint.
- **Inconclusive:** \(\mathcal Q\cap\mathcal F\ne\varnothing\) and \(\mathcal Q\setminus\mathcal F\ne\varnothing\).

For a single constraint, robust rejection reduces to \(\inf_{q\in\mathcal Q}g(q)>0\). For multiple constraints, it is not sufficient to show that each constraint can be violated somewhere; those violations might occur at different admissible states while another state satisfies all constraints.

A verified point \(q^*\in\mathcal Q\setminus\mathcal F\) is a **violation witness**. It disproves robust acceptance, but does not by itself establish robust rejection. Robust rejection requires proving \(\mathcal Q\cap\mathcal F=\varnothing\).

Absence of a violation witness is not established by a local optimiser failing to find one. Robust acceptance requires a valid global upper bound, exhaustive method or sound outer approximation for every mandatory constraint.

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
- \(C_a=(\mathbf c_a^\downarrow,\mathbf c_a^\uparrow)\): defensible lower/upper resource-cost vectors. The upper vector is used for hard-budget planning; the lower vector is used only for admissible search lower bounds. If a defensible lower bound is unavailable for a resource, use zero for that component;
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

### 5.1 Evidence assurance type and checker status

Evidence type and verification status are orthogonal fields. Do not flatten them into a single confidence score.

| Evidence class | Permitted use | Not sufficient by itself for |
|---|---|---|
| Point estimate | Nominal reporting and exploratory guidance | A bounded acceptance claim or calibrated probability |
| Heuristic indicator | Action targeting and prioritisation | A deterministic bound or calibrated probability |
| Statistical estimate/bound | Probability statement within a declared model, sampling and calibration scope | Deterministic enclosure or out-of-domain guarantee |
| Deterministic mathematical bound | Bounded claim under explicit theorem assumptions | Physical model validity or omitted uncertainty |
| Formal proof/certificate | The proposition actually encoded and checked | Claims outside its formal scope |
| Experimental validation evidence | Agreement/disagreement with measurements over a declared domain | Universal proof outside tested conditions |
| Provenance/integrity evidence | Identity/integrity of inputs, executable, configuration and outputs | Numerical accuracy by itself |

Independently record checker status, for example: \`PRODUCER_ASSERTED\`, \`AUTOMATICALLY_CHECKED\`, \`INDEPENDENTLY_CHECKED\`, \`CONFLICTED\`, or \`STALE\`. These labels do not replace the underlying artefact or proof.

A statistical confidence interval is not a deterministic enclosure. A DWR asymptotic indicator is not a standard deviation. A running round-off estimate is not automatically a certified floating-point enclosure. A floating-point residual is not automatically a rigorous residual bound.

A VWEC used to exclude a witness in bounded mode must be backed by a deterministic mathematical bound or formal proof whose assumptions cover the entire claimed region and action outcome. Statistical or heuristic evidence can guide a separately declared probabilistic or exploratory path, but cannot discharge a deterministic-bound obligation.

### 5.1 Verified Witness-Exclusion Certificates (VWEC)

The key numerical evidence object proposed for DWAOP is a **Verified Witness-Exclusion Certificate (VWEC)**. This is a scoped proof artefact, not a confidence score.

For a current sound outer set \(\mathcal Q_t\), let \(W_t\subseteq\mathcal Q_t\) be a decision-reversing witness region. A VWEC claims that a specified part \(R\subseteq W_t\) is impossible under a declared action outcome and model scope.

A certificate must bind:

1. canonical problem/specification identity and all input/configuration hashes;
2. model, QoI, constraint and operating-envelope scope;
3. the exact witness region \(R\) and its representation;
4. the exact post-action admissible set \(\mathcal Q_{t+1}\);
5. the mathematical implication used to exclude the region;
6. all estimator, solver, quadrature, data and dependency assumptions;
7. the proof/checker artefact and independent checker version/result;
8. the consumed and measured resource record.

The checker must establish, as applicable:

- **scope identity:** the certificate refers to the active specification and model;
- **outer-set soundness:** every model-consistent QoI under the declared outcome remains in \(\mathcal Q_{t+1}\);
- **exclusion soundness:** \(\mathcal Q_{t+1}\cap R=\varnothing\);
- **obligation validity:** any assurance obligation marked satisfied meets its exact acceptance predicate;
- **dependency integrity:** evidence sources and shared assumptions are recorded and not counted as independent without justification.

There are two importantly different certificate directions:

- **Violation-witness certificate:** proves that at least one admissible point violates a requirement. This refutes robust acceptance, but does not prove that all admissible points fail.
- **Witness-exclusion certificate:** proves that an entire region of possible violations is excluded. This may contribute to robust acceptance only when every decision-reversing region has been soundly excluded.

A heuristic optimiser may propose a candidate violation point. A standard floating-point solver result or residual is not automatically a violation certificate. Likewise, a local search failing to find a violating point is not a witness-exclusion certificate.

An action's declared effect is only a candidate capability. The actual VWEC is checked after the action runs. No admissible region may be removed from \(\mathcal Q_t\) merely because an action was expected to reduce it.

The checker should be a separately specified, minimal verification component whose trusted computing base is substantially smaller than the solver/planner stack. It should validate proof artefacts and set relations, not re-run the same estimator through the same code path and then call that result independent. Independence is an architectural target that must itself be reviewed and tested; it is not established merely by using a different function or process.

### 5.2 Witness/action/obligation effect map

At each state, construct the blocker set:

\[
B(S)=\{(W_i,\mathrm{witness})\}_{i=1}^{n}
\;\cup\;
\{(O_j,\mathrm{obligation})\}_{j=1}^{m},
\]

where \(W_i\) are unresolved witness regions and \(O_j\) are open assurance obligations. The planner builds a typed effect map from action contracts to blockers:

\[
M_{ba}=
\begin{cases}
1,&\text{action }a\text{ has a potentially applicable, typed route to blocker }b,\\
0,&\text{otherwise.}
\end{cases}
\]

This map is used only for candidate filtering and lower-bound construction. It is not proof that an action will resolve a blocker. Conditional outcomes, prerequisites and certificate checking remain explicit in the AND-OR planner.

The map must distinguish:
- action can produce evidence relevant to blocker;
- action can guarantee blocker closure under every covered outcome;
- action can only provide heuristic guidance;
- action is inapplicable.

Only the second category can be used as a guaranteed effect in a terminal plan. The first may be included in an optimistic lower-bound relaxation but never in the terminal acceptance test.

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

A policy \(\pi\) maps each reachable evidence state/history to an action and branches on the observed outcomes. Let \(\Omega(\pi)\) be the set of all outcome paths covered by the action contracts. Let the upper-bound resource vector for path \(\omega\) be

\[
\mathbf C^\uparrow(\pi,\omega)
=
\sum_{a\in\pi(\omega)}\mathbf c_a^\uparrow.
\]

Define the componentwise worst-case upper resource envelope:

\[
\overline{\mathbf C}^\uparrow(\pi)
=
\left(
\sup_{\omega\in\Omega(\pi)}C_r^\uparrow(\pi,\omega)
\right)_{r=1}^{R}.
\]

This envelope may combine maxima attained on different paths. It is a conservative per-resource summary, not necessarily the cost vector of one physically realised path.

A policy is **decision-complete** only if every outcome branch covered by its contracts reaches a valid terminal decision (\`ACCEPT\` or \`REJECT\`) with all mandatory obligations satisfied and valid evidence integrity. Branches ending \`INCONCLUSIVE\` or \`REFUSE\` are safe non-acceptance outcomes, but they do not count as a completed decision plan.

The planner returns the nondominated worst-case resource envelopes:

\[
\Pi^*(S)=\operatorname{ParetoMin}
\left\{
\overline{\mathbf C}^\uparrow(\pi):
\pi\text{ is decision-complete from }S
\right\}.
\]

A plan fits hard budget \(\mathbf B\) only if \(\overline{\mathbf C}^\uparrow(\pi)\preceq\mathbf B\). If an owner preference is needed to select one plan from the Pareto frontier, it must be declared. The algorithm must not invent exchange rates between time, memory, energy or money.

The optimization is over complete contingent policies, not the cost of the first action. A policy that covers only favourable outcomes is invalid.

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

### 7.3 Proof-preserving search accelerators

The AND-OR search can be expensive. Two pruning mechanisms are proposed. Neither may remove a state or plan unless its lower-bound or dominance preconditions are checked.

#### 7.3.1 Blocker-distance lower bound

Let \(B(S)\) be the current unresolved blockers. For each blocker \(b\), construct an optimistic relaxed action graph that:

- over-approximates all actions that could possibly discharge \(b\) under their declared contracts; any uncertain or incompletely characterised route is included with zero lower-bound cost, or the pruning rule is disabled;
- relaxes action prerequisites;
- chooses the most favourable covered outcome;
- ignores conflicts with other blockers;
- ignores the need to satisfy other obligations.

Let \(d_r(b\mid S)\) be the shortest possible resource-\(r\) cost from \(b\) to a state where that blocker is discharged in this relaxed graph. To make this a valid lower bound, action descriptors must supply a defensible resource **lower bound** \(c_{a,r}^{\downarrow}\), distinct from the upper bound used for budget safety. If no positive lower bound is known, that action contributes zero to this lower-bound calculation.

Define:

\[
LB_r(S)=\max_{b\in B(S)}d_r(b\mid S).
\]

This is deliberately weak. For a fixed blocker \(b\), every path of a decision-complete policy must contain some action sequence that discharges \(b\). The relaxed graph permits at least all such sequences and additionally relaxes preconditions and outcome constraints; its minimum path cost, using resource lower bounds, therefore cannot exceed the cost of the actual sequence. Taking the maximum of these per-blocker minima remains a lower bound on the worst-case policy cost. The relaxed graph must be a supergraph of every potentially valid blocker-discharge route. It can underestimate the true cost because it ignores prerequisites, adverse outcomes, action interactions and other blockers. It must never overestimate it. If the effect map is incomplete, the computed bound is not admissible and must not be used to prune.

**Admissibility proof sketch:** Fix resource component \(r\) and blocker \(b\). For every outcome path \(\omega\) of a decision-complete policy, let \(P_{\omega,b}\) be the subsequence of actions on that path that causally discharges \(b\). By construction, this sequence is represented in the relaxed graph, whose edge costs are no greater than the corresponding actual action costs. Hence \(C_r^\uparrow(\pi,\omega)\ge C_r^\downarrow(P_{\omega,b})\ge d_r(b\mid S)\). Taking the supremum over \(\omega\) and then the maximum over \(b\) gives \(\overline C_r^\uparrow(\pi)\ge LB_r(S)\). This argument fails if the action-effect graph omits a valid discharge route or if a claimed cost lower bound exceeds actual cost; in either case the pruning rule must be disabled.

Safe pruning rule:

\[
C_{r,\mathrm{spent}}(S)+LB_r(S)>B_{r,\mathrm{total}}
\quad\Longrightarrow\quad
\text{no decision-complete policy fits the remaining budget}.
\]

Apply this test independently to each resource dimension. Do not sum individual blocker distances: one action may resolve multiple blockers, and different branches may use different actions. If the relaxed graph or resource lower bounds are not sound, disable this pruning rule.

#### 7.3.2 Proof-preserving state dominance

A search state \(S_1\) may dominate \(S_2\) only when all of the following are established:

1. both states refer to the identical canonical specification, model scope and assurance mode;
2. \(\mathcal Q_1\subseteq\mathcal Q_2\), with both sets sound under the same model assumptions;
3. \(S_1\) has no more open, blocked or conflicted obligations than \(S_2\), and all evidence used by \(S_1\) has valid provenance;
4. the resource vector already consumed in \(S_1\) is componentwise no greater than in \(S_2\);
5. every continuation action/policy available from \(S_2\) has a corresponding valid continuation from \(S_1\), with outcome coverage and proof obligations no harder.

Condition 5 is essential. A smaller QoI set alone does not guarantee that a solver, estimator or verifier remains applicable.

For a finite state abstraction, make the simulation relation explicit. For every action \(a_2\) enabled at \(S_2\), there must be a matching action \(a_1\) enabled at \(S_1\), with no greater upper resource cost, such that for every outcome \(y_1\in\mathcal Y_{a_1}(S_1)\), there is a matching outcome \(y_2\in\mathcal Y_{a_2}(S_2)\) whose successor states satisfy \(T(S_1,a_1,y_1)\preceq T(S_2,a_2,y_2)\). The relation must preserve terminal decision predicates, outcome coverage and certificate scope/validity.

**Conditional dominance proposition:** if \(S_1\preceq S_2\) satisfies these conditions, every decision-complete continuation from \(S_2\) can be simulated from \(S_1\) with no greater worst-case upper resource vector and no weaker terminal assurance. Therefore \(S_2\) may be pruned when searching for Pareto-minimal complete policies. If the simulation relation cannot be checked, retain both states.

This is a conditional dominance argument, not a proof that a generic QoI-set subset test is safe.

#### 7.3.3 Action-equivalence reduction

Actions may be merged or one removed only if a checked equivalence relation establishes identical:
- applicability/preconditions;
- possible outcome coverage;
- witness and obligation effects;
- evidence dependencies and checker semantics;
- failure/invalidation behaviour.

If these are equivalent and one action has no greater upper resource cost in every component (and is strictly cheaper in at least one), the more expensive action is dominated. Otherwise retain both. General action-equivalence reduction is established in AI planning; the research task is to test whether numerical proof-effect signatures provide a useful, sound abstraction for GDEC's computation portfolio.

### 7.4 Receding-horizon controller

The planner constructs a bounded contingent plan, executes only its first action, verifies the result, and then replans from the updated state. This prevents a long predicted plan from being executed blindly after its assumptions have changed.

~~~text
DWAOP(spec, resource_budget):
    validate_specification_and_decision_rules(spec)
    obligations = compile_mandatory_obligations(spec)
    state = establish_initial_sound_QoI_set_and_provenance(spec)
    actual_cost = zero_resource_vector()

    if specification_invalid_or_claim_inapplicable:
        return REFUSE(reason, state)

    repeat:
        verify_state_integrity_and_model_identity(state)

        blockers = construct_tagged_witness_and_obligation_blockers(state)
        witnesses = generate_decision_reversing_witnesses(state.Q)
        decision = evaluate_robust_decision(state.Q, witnesses)

        if decision.robust and state.obligations.all_satisfied:
            return TERMINAL_DECISION(
                decision,
                independently_checked_certificate_bundle,
                actual_cost
            )

        actions = enumerate_supported_actions(state)
        contracts = validate_action_preconditions_and_effect_contracts(
            actions,
            blockers
        )

        apply_blocker_distance_lower_bound_pruning(
            state,
            contracts,
            actual_cost,
            resource_budget
        )
        apply_proof_preserving_state_dominance()

        plan_frontier = bounded_vector_cost_AND_OR_search(
            state,
            eligible_contracts,
            hard_resource_budget = resource_budget - actual_cost,
            mandatory_obligations = obligations,
            terminal_decision_gate = decision_gate
        )

        if no_complete_plan_fits(plan_frontier):
            if required_claim_is_invalid_or_unsupported:
                return REFUSE(reason, blockers, actual_cost)
            return INCONCLUSIVE(
                blockers,
                remaining_budget,
                rejected_action_and_pruning_reasons,
                actual_cost
            )

        if plan_frontier_has_multiple_incomparable_options and no_predeclared_operator_preference:
            return PLAN_SELECTION_REQUIRED(plan_frontier)

        action = first_action(select_declared_preference_from_Pareto_frontier(plan_frontier))
        result = execute_and_record_actual_cost(action)
        actual_cost += result.measured_resource_cost

        if result.failed_or_timed_out:
            preserve_failure_artifacts_and_update_state(state, result)
            if actual_cost_exceeds_budget:
                return INCONCLUSIVE("ACTUAL_BUDGET_EXHAUSTED", blockers, actual_cost)
            continue

        proposed_state = apply_typed_evidence_transition(state, result)
        checker_result = independent_checker.verify_transition_and_certificates(
            old_state = state,
            action = action,
            result = result,
            proposed_state = proposed_state
        )

        if checker_result != VERIFIED:
            preserve_all_artifacts()
            state = mark_conflicted_or_incomplete(state, proposed_state, checker_result)
        else:
            state = proposed_state

        if actual_cost_exceeds_budget:
            return INCONCLUSIVE("ACTUAL_BUDGET_OVERRUN", state, actual_cost)

~~~

If the Pareto frontier contains multiple incomparable plans and no preference was declared, the system must expose the frontier for operator selection; it must not invent a trade-off between resource types. \`PLAN_SELECTION_REQUIRED\` is a planning interaction state, not an engineering acceptance result.

The controller may execute an exploratory action when no sound outcome cover exists only under an explicitly non-assured exploratory mode. Such an action cannot support a bounded terminal decision until its actual result has been converted into valid checked evidence. Search-depth exhaustion, state-space abstraction failure, or a heuristic witness-search timeout returns \`INCONCLUSIVE\`; it does not prove that no witness or plan exists.

### 7.5 Terminal outcomes

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
- Decision-dependent information discovery and controllable uncertainty sets.
- Minimax-regret robust optimisation and witness-style policy computation.
- Joint spatial, surrogate-model and sampling-error control in stochastic FEM.
- Bayesian inverse-FEM methods coupling discretisation-error and sampling-error control.
- Proof-carrying plans and resource logics for AI planning.
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

## 11. Prior-art and patent landscape (expanded, still not exhaustive)

| Prior work | What it already covers | Consequence for DWAOP |
|---|---|---|
| Oden & Prudhomme (2001), goal-oriented FEM | QoI-based a posteriori estimates and goal-oriented mesh adaptivity, including upper/lower bounds for classes of elliptic problems | Do not claim novelty for QoI-centric error estimation or mesh adaptation |
| Becker et al. (2023), goal-oriented AFEM | Joint mesh-refinement and iterative-solver steering, with convergence and optimal rates in total computational cost under assumptions | Do not claim novelty for solver/mesh co-steering |
| NASA Nemec & Aftosmis (2014/2015), automatic verification of goal-oriented flow simulations | Adjoint-weighted error estimates and automatic control of discretisation error in practical Euler simulations | Do not claim novelty for automated goal-oriented verification and mesh control |
| Yang et al. (2024), active learning for RBDO under multiple simulation models | Active constraints, model selection and differing simulation costs in reliability-based design optimisation | Do not claim novelty for cost-aware fidelity/action selection in reliability optimisation |
| Vayanos et al. (2023), robust optimisation with decision-dependent information discovery | Decisions control when uncertain information is revealed through costly exploratory investments; develops multistage robust formulations and a solution method | Do not claim novelty for planning costly queries that reveal information before a decision |
| Ley et al. (2026), optimisation under elementwise controllable uncertainty | Decision maker can pay to shrink bounded uncertainty intervals element by element and optimise under the remaining uncertainty | Do not claim novelty for paid computation/measurement reducing an uncertainty set |
| Bonilla-Villalba et al. (2020), goal-oriented model adaptivity in stochastic elastodynamics | Simultaneously controls spatial discretisation, surrogate-model and Monte Carlo sampling errors to compute QoI statistics at minimum cost | Do not claim novelty for jointly controlling multiple numerical approximation/sampling errors |
| Bayesian inverse FEM adaptive methodology (2019) | Simultaneous control of goal-oriented FEM discretisation error and statistical sampling error in Bayesian parameter identification, including stopping and mesh-refinement decisions | Do not claim novelty for coupling sampling sufficiency and FEM discretisation-error control |
| Goal-oriented adaptive modelling of random heterogeneous media and model-based MLMC (2019) | QoI-driven adaptive surrogate/model resolution and multilevel Monte Carlo for stochastic heat conduction and elastostatics | Do not claim novelty for QoI-driven model-resolution plus sampling-cost control |
| Habera et al. (2026), running error bounds in FE kernels | Propagates a posteriori running round-off/error estimates through generated FE kernels; authors distinguish these estimates from certified bounds | Do not claim novelty for running kernel-error estimates; do not treat these estimates as VWECs without a separate certification argument |
| Solak et al. (2026), MF-CAS preprint | Joint sample-location and fidelity selection using decomposed uncertainty intervals and model cost | Do not claim novelty for cost-aware interval-based sampling/fidelity selection |
| Zhao et al. (2026), MF-PBALC | Posterior-mean failure-probability bounds, a stopping rule, and cost-aware joint evaluation-point/fidelity selection for structural reliability | Do not claim novelty for bounded stopping or cost-aware joint fidelity selection |
| Minimax-regret robust optimisation (e.g. Ning & You, 2018) | Minimax-regret objectives and algorithms in adaptive robust optimisation | Do not claim novelty for the regret objective or worst-case regret formulation |
| Hill, Komendantskaya & Petrick (2020), Proof-Carrying Plans | Resource logic and typed pre/postconditions for checking AI plans, with formal soundness proof and Agda formalisation | Do not claim novelty for resource-aware plans carrying machine-checkable proofs |
| Gardiol & Kaelbling, action equivalence for planning | Runtime partitioning of actions into approximate equivalence classes to reduce planning search | Do not claim novelty for action-signature compression in generic planning |
| CEGAR literature | Counterexample generation, abstraction refinement and validation loops | Do not claim novelty for counterexample-guided refinement alone |
| ACCESS (2024), assurance-case-centric engineering | Model-based assurance-case/artifact traceability, automated formal-method evidence invocation, logical checking and change-impact analysis | Do not claim novelty for assurance graphs or automated evidence integration in isolation |
| NASA (2023), formal verification in assurance cases | Tool preconditions, postconditions and assurance constraints integrated into machine-supported assurance arguments | Do not claim novelty for verifier applicability contracts alone |
| Automated assurance-case pattern selection for CPS (2022) | Coverage and optimisation of assurance-case patterns | Do not claim novelty for obligation coverage or evidence-pattern selection alone |
| Yang et al. (2023), RL for adaptive mesh refinement | AMR formulated as sequential decision-making under a computational budget; policy compared with greedy ZZ refinement | Do not claim novelty for framing refinement as sequential budgeted decisions |
| US20240348663A1, AI-enhanced simulation and modeling experimentation and control | Published claims describe simulation goals/constraints, uncertainty reduction, active-learning scenario selection, and look-ahead/branching adapted to resources | Material adjacent patent disclosure; requires patent-professional claim analysis. This is not a legal opinion |

### 11.1 What this does to the novelty hypothesis

The research must now treat all the following as established ingredients: robust regret, paid information discovery, QoI adaptivity, cost-aware multi-fidelity selection, resource-aware proof-carrying plans, action equivalence, counterexample-guided refinement, assurance-case obligation management, and budgeted sequential mesh refinement.

The remaining candidate is narrower:

**A numerical-engineering-specific, certificate-first computation planner in which (i) each action emits a scoped, independently checkable set-transition or witness-exclusion artefact, (ii) action contracts explicitly describe the numerical assumptions and QoI regions to which that artefact applies, and (iii) a contingent planner uses those contracts to construct a complete decision-and-assurance proof path, with proof-preserving pruning and explicit fail-closed outcomes.**

The specific algorithmic mechanism proposed for evaluation is the pairing of:
- **Verified Witness-Effect Certificates (VWEC):** proof objects for excluding a defined decision-reversing QoI region under an identified model/action outcome; and
- **Blocker-distance lower bounds plus proof-preserving state dominance:** search accelerators that prune only when their admissibility conditions are checked.

This is not yet a demonstrated gap. It may still be obvious to a skilled reader as an application-specific combination of proof-carrying planning, robust optimisation, certified numerical analysis and assurance cases. The novelty claim is therefore **OPEN / UNPROVEN**. A full literature, dissertation, standards and patent-family search is needed before public claims or an invention disclosure.

### 11.2 Primary links

- Oden & Prudhomme (2001), goal-oriented FEM: https://doi.org/10.1016/S0898-1221(00)00317-5
- Becker et al. (2023), GOAFEM: https://doi.org/10.1007/s00211-022-01334-8
- NASA Nemec & Aftosmis, automatic goal-oriented flow verification: https://ntrs.nasa.gov/citations/20150000864
- Yang et al. (2024), multi-model active learning for RBDO: https://doi.org/10.1016/j.strusafe.2023.102426
- Vayanos et al., decision-dependent information discovery: https://doi.org/10.1287/mnsc.2021.00160
- Ley et al. (2026), elementwise controllable uncertainty: https://doi.org/10.1007/s00291-026-00856-z
- Bonilla-Villalba et al. (2020), stochastic elastodynamics model adaptivity: https://doi.org/10.1615/Int.J.UncertaintyQuantification.2020031735
- Bayesian inverse-FEM adaptive methodology (2019): https://pmc.ncbi.nlm.nih.gov/articles/PMC6416561/
- Adaptive modelling of random heterogeneous media / model-based MLMC (2019): https://doi.org/10.1016/j.camwa.2019.04.014
- Habera et al. (2026), running error estimates in FE kernels: https://arxiv.org/abs/2609.37844
- Solak et al. (2026), MF-CAS: https://arxiv.org/abs/2610.38582
- Zhao et al. (2026), MF-PBALC: https://doi.org/10.1016/j.ress.2026.113871
- Ning & You (2018), adaptive robust optimisation with minimax regret: https://doi.org/10.1016/j.compchemeng.2017.09.026
- Hill et al. (2020), Proof-Carrying Plans: https://doi.org/10.1145/3414080.3414094
- Gardiol & Kaelbling, computing action equivalences for planning: https://people.csail.mit.edu/nhg/papers/gardiol_icaps_consortium.pdf
- Clarke et al. (2000), CEGAR: https://doi.org/10.1007/10722167_15
- ACCESS (2024): https://doi.org/10.1016/j.jss.2024.112034
- NASA, formal verification in assurance cases: https://ntrs.nasa.gov/citations/20230007599
- Automated assurance-case pattern selection for CPS (2022): https://doi.org/10.1007/978-3-031-14835-4_6
- Yang et al. (2023), RL for AMR: https://proceedings.mlr.press/v206/yang23e.html
- Patent publication: https://patents.google.com/patent/US20240348663A1/en

The patent publication is listed as pending by Google Patents, which explicitly warns that its legal-status display is not a legal conclusion. The publication has a long priority/family chain. Its published claims include uncertainty reduction and active-learning scenario selection, and look-ahead/branching depth adapted to objectives and resources. It is an adjacent disclosure requiring professional review; it does not establish anticipation, obviousness, infringement or freedom to operate for DWAOP.

## 12. Required novelty experiments## 12. Required novelty experiments

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

- **RESEARCHED:** GOAFEM, multi-fidelity/active learning, decision-dependent information discovery, controllable uncertainty, minimax regret, proof-carrying plans, action equivalence, CEGAR, assurance cases, sequential AMR and one adjacent patent publication.
- **FORMULATED:** decision-witness state, obligation state, typed action contracts, verified witness-exclusion certificates, robust AND-OR planning objective, vector budgets, blocker-distance lower bound and proof-preserving state dominance.
- **CONDITIONALLY JUSTIFIED:** terminal soundness proposition under explicit enclosure, transition and checker assumptions.
- **NOT PROVEN:** global optimality, tractability at scale, novelty, patentability or freedom to operate.
- **NOT IMPLEMENTED:** no production or research controller code.
- **NOT TESTED:** no controller benchmark or adversarial implementation test run.
- **NOT INDEPENDENTLY VERIFIED:** no external mathematical review.
- **NOT APPROVED:** no production implementation authorisation.

**Next gate:** independent review of the formal state/action model and soundness assumptions, then a hand-computed action-planning example with at least two complementary actions and a branching outcome. Only after that should the research prototype be proposed.
