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
- \(C_a\): a resource record containing, for each declared resource \(r\), a lower/upper cost descriptor and its aggregation semantics. Cost lower bounds are used only by a compatible admissible search relaxation; cost upper bounds are used for hard-budget planning. If a defensible lower bound is unavailable, use zero or disable that resource-specific pruning rule;
- \(Y_a\): conservative cover of possible action outcomes;
- \(K_a\): evidence/certificate contract;
- \(D_a\): dependencies and shared assumptions;
- \(F_a\): failure, conflict, invalidation and timeout semantics.

Resource lower/upper bounds must follow the resource-specific contract in Section 5.6. They are not universally additive. Peak-memory descriptors additionally identify retained outputs, releasable temporaries and simultaneously live buffers.

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

### 5.2 Verified Witness-Exclusion Certificates (VWEC)

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

### 5.3 Witness/action/obligation effect map

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
- action can produce evidence relevant to a blocker;
- action may close or partition a blocker under a specified outcome cell, subject to post-run checking;
- action has a guaranteed proof effect for each specified outcome cell;
- action can only provide heuristic guidance;
- action is inapplicable.

An action need not close the same blocker in every outcome. It may partition the state, after which each child branch has its own witness and obligation set. A contingent plan is guaranteed only when **every** outcome cell has a sound checked transition and every child branch is itself decision-complete. The pre-run effect map is used for optimistic candidate filtering and lower bounds; the actual branch effect is established only by the checked output artefact.

### 5.4 Typed witness and decision effects

For each covered action outcome cell \(y\), the transition contract should declare one or more typed effects:

- \`EXCLUDE_REGION(R)\`: a checked set-transition certificate proves a region \(R\) is incompatible with the observed outcome/model and removes it from the sound admissible set.
- \`PARTITION(\{R_i\})\`: a checked outcome partition covers the prior admissible set; each \(R_i\) becomes a separate child state. The partition must be exhaustive and non-overlapping where required by its semantics.
- \`CONFIRM_VIOLATION(q^*)\`: a checked feasible point shows that a candidate acceptance claim is false. It does not alone prove robust rejection.
- \`ESTABLISH_REJECTION\`: a checked global result proves that every admissible QoI state violates at least one required constraint, i.e. \(\mathcal Q\cap\mathcal F=\varnothing\).
- \`DISCHARGE_OBLIGATION(o_i)\`: an artefact satisfies the exact predicate for a named mandatory assurance obligation.
- \`INVALIDATE_ASSUMPTION(m_i)\`: evidence shows a model assumption is unsupported or false; the model scope and admissible set must be rebuilt or the claim refused.
- \`HEURISTIC_GUIDANCE\`: may reprioritise future actions but cannot remove a witness or discharge a bounded assurance obligation.

These effects are not interchangeable. In particular, \`CONFIRM_VIOLATION\` refutes robust acceptance, while \`ESTABLISH_REJECTION\` is the stronger proof needed for a robust rejection verdict. A \`PARTITION\` effect creates multiple obligations for the planner: every child outcome branch must be handled.

### 5.5 Decision-Assurance Plan Certificate (DAPC)

A VWEC checks one numerical witness-exclusion or set-transition claim. DWAOP additionally needs a certificate for the **entire contingent computation plan**. The proposed plan-level artefact is a **Decision-Assurance Plan Certificate (DAPC)**.

A DAPC is a finite rooted tree (or a DAG only where shared subplans are represented without losing branch identity). Each node records:

- canonical state identity and model/specification hash;
- the joint admissible QoI set representation;
- unresolved decision-witness regions;
- open, satisfied, blocked and conflicted assurance obligations;
- accumulated and remaining resource vectors;
- evidence-dependence/provenance graph reference.

Each action node records:

- action contract identifier/version and checked preconditions;
- action execution artefact and measured resource consumption;
- the complete outcome-cell cover used by the planner;
- for every outcome edge, the child-state identity and transition certificate;
- VWEC, partition, violation, rejection, assumption-invalidation or obligation-discharge certificates as applicable.

Every leaf must contain one of:
- a checked \`ACCEPT\` proof satisfying all mandatory acceptance constraints/regret requirements and obligations;
- a checked \`REJECT\` proof establishing the declared rejection condition and obligations;
- a safe non-acceptance leaf (\`INCONCLUSIVE\` or \`REFUSE\`) in an exploratory/partial plan, which means the DAPC is **not** a decision-complete acceptance plan.

The independent DAPC checker must verify:

1. the root state matches the exact requested specification and provenance;
2. every action's preconditions and evidence contract apply to its parent state;
3. outcome cells cover all possibilities claimed by the action contract; if disjointness is part of the semantics, that is checked too;
4. each edge's child-state set is a sound outer representation of the parent state conditioned on that outcome;
5. every witness exclusion and obligation discharge is backed by a valid scoped certificate;
6. evidence conflicts and model invalidations are not silently discarded;
7. every terminal leaf satisfies its own decision and assurance predicates;
8. worst-case resource upper bounds for every branch fit the declared budget, using the exact aggregation operator and live-set/schedule semantics declared for each resource;
9. peak-memory accounting includes all simultaneously live retained artefacts, workspaces, temporary buffers and release events;
10. unsupported parallel execution or undefined resource aggregation is rejected rather than approximated.

The DAPC does not certify the physical truth of the declared model. Its top-level proposition is conditional: all covered executions of the plan reach the stated terminal outcomes with evidence valid under the declared model, assumptions and assurance scope.

A tree containing only a producer's asserted statuses is not a DAPC. A proof checker must validate the underlying artefacts and transition relations. Plan completeness is distinct from plan optimality: DWAOP may return a sound, decision-complete plan without proving it is globally minimum-cost. A Pareto-optimality claim requires its own search-completeness and optimality certificate; otherwise report only the nondominated frontier found within the declared search limits.

### 5.6 Resource semantics and action-cost contract

A resource vector is not a vector of values that can always be summed componentwise. Each resource dimension must declare its path-aggregation semantics before planning.

| Resource class | Examples | Sequential path aggregation | Notes |
|---|---|---|---|
| Additive consumption | CPU time, accelerator execution time, energy, monetary cost, operation count | Sum of action consumption | Valid when all costs are measured consistently and each action's consumption is charged once |
| Sequential elapsed time | Wall-clock duration in the first prototype | Sum of action upper durations | Requires an explicit no-overlap/sequential execution policy |
| Peak/live-set resource | Peak RAM, peak device memory | Maximum live footprint over the execution timeline | Must account for retained evidence, action workspace, temporary buffers and releases; not the sum of every action's peak |
| Parallel scheduled latency | Wall time with concurrent actions | Schedule makespan / critical-path and contention model | Unsupported in the first prototype; never approximate by summing or taking the maximum of action durations without a schedule model |

Each resource declaration must contain:

- stable resource identifier and physical unit;
- aggregation class and composition operator;
- upper-bound measurement/model method;
- lower-bound method, if one is justified;
- whether actions may overlap;
- whether the resource is cumulative, instantaneous, or a high-water mark;
- the accounting treatment of persistent outputs, caches and released temporaries.

**First-prototype restriction:** actions execute sequentially. CPU time, device execution time, energy and monetary cost are additive. Wall elapsed time is additive because no actions overlap. Peak memory is tracked from a live-artifact state and a per-action workspace model. Parallel execution is out of scope until a schedule-aware resource algebra is defined and tested.

For peak memory, the state must include the retained artefact set \(A_{\mathrm{live}}(S)\) and a conservative resident-memory bound \(M_{\mathrm{resident}}^\uparrow(S)\). For sequential action \(a\), define a peak upper bound:

\[
M_{\mathrm{during}}^\uparrow(a,S)
=
M_{\mathrm{resident}}^\uparrow(S)
+
M_{\mathrm{workspace}}^\uparrow(a,S)
+
M_{\mathrm{overlap}}^\uparrow(a,S),
\]

where \(M_{\mathrm{overlap}}^\uparrow\) bounds temporary output/buffer allocations that coexist with the resident set and workspace. The action transition specifies which output artefacts remain live and which temporary allocations are released. The upper bound may be conservative, but it must never omit simultaneously live allocations.

For a sequential path \(\omega\):

\[
M_{\mathrm{peak}}^\uparrow(\omega)
=
\max\left(
M_{\mathrm{resident}}^\uparrow(S_0),
\max_{a_t\in\omega}M_{\mathrm{during}}^\uparrow(a_t,S_t),
\max_t M_{\mathrm{resident}}^\uparrow(S_{t+1})
\right),
\]

where \(S_t\) carries the current retained artefacts and resident-memory bound. This is a high-water mark, not a cumulative sum of all action memory costs.

A memory lower bound must also respect live-set semantics. A defensible per-action unavoidable peak lower bound \(m^\downarrow(a,S)\) must include the minimum resident input/live-artifact footprint that cannot be released plus the minimum workspace/output footprint that must coexist. It can be used only when the action contract proves that amount must be simultaneously resident. If lifetime/overlap information is absent, use zero for the lower-bound calculation. Never sum per-action peak-memory lower bounds merely because the actions occur sequentially.

The plan's resource envelope is computed per resource using its declared aggregation function. Componentwise comparison against a budget is allowed only after each component has been computed with the correct semantics.

Worked numeric checks of additive, peak/live-set and branch resource aggregation are recorded in [DWAOP Resource Algebra Sanity Check v0.2](DSCA_DWAOP_RESOURCE_ALGEBRA_SANITY_CHECK_v0.2.md). This note is a hand-calculated specification check, not an implementation test.


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

A policy \(\pi\) maps each reachable evidence state/history to an action and branches on the observed outcomes. Let \(\Omega(\pi)\) be the set of all outcome paths covered by the action contracts.

For each path \(\omega\), compute resource use by the semantics declared for that resource:

- for additive resources \(r\in\mathcal R_\Sigma\):
  \[
  C_r^\uparrow(\pi,\omega)
  =
  \sum_{a_t\in\omega}c_{a_t,r}^\uparrow;
  \]
- for peak/live-set resources \(r\in\mathcal R_{\max}\):
  \[
  C_r^\uparrow(\pi,\omega)
  =
  \max_{a_t\in\omega} C_{a_t,r,\mathrm{during}}^\uparrow(S_t),
  \]
  with \(S_t\) carrying the live retained-artifact set and the bound on resident memory;
- for scheduled/parallel resources \(r\in\mathcal R_{\mathrm{sched}}\), use an explicit schedule makespan/critical-path and contention model. These resources are unsupported in the first sequential prototype.

The componentwise worst-case upper envelope across all covered branches is:

\[
\overline{\mathbf C}^\uparrow(\pi)
=
\left(
\sup_{\omega\in\Omega(\pi)}C_r^\uparrow(\pi,\omega)
\right)_{r=1}^{R}.
\]

This envelope may combine maxima attained on different paths. It is a conservative per-resource summary, not necessarily the resource vector of one physically realised path.

A policy is **decision-complete** only if every outcome branch covered by its contracts reaches a valid terminal decision (\`ACCEPT\` or \`REJECT\`) with all mandatory obligations satisfied and valid evidence integrity. Branches ending \`INCONCLUSIVE\` or \`REFUSE\` are safe non-acceptance outcomes, but they do not count as a completed decision plan.

The planner returns the nondominated worst-case upper resource envelopes:

\[
\Pi^*(S)=\operatorname{ParetoMin}
\left\{
\overline{\mathbf C}^\uparrow(\pi):
\pi\text{ is decision-complete from }S
\right\}.
\]

A plan fits hard budget \(\mathbf B\) only if \(\overline{\mathbf C}^\uparrow(\pi)\preceq\mathbf B\), where each component has first been computed using its declared aggregation semantics. The algorithm must not invent exchange rates between unlike resources.

### 7.2 AND-OR recursion with resource-specific composition

For a finite, sound abstraction of the evidence state and action outcomes, define \(\mathcal J(S)\) as the Pareto frontier of worst-case upper resource states for robust decision-completing policies from state \(S\). A resource state includes both cumulative consumption and retained/live resources; it is not always a simple numeric cost vector.

For a terminal state with a satisfied decision gate and no open obligations, the additional continuation cost is zero and the retained artefact state is the terminal retained set.

For a non-terminal state and eligible action \(a\), every covered outcome \(y\in\mathcal Y_a(S)\) must have a feasible continuation \(\mathbf j_y\). Compose action and child-plan costs separately for each resource class:

- Additive sequential resource:
  \[
  v_r(a,S,\{\mathbf j_y\})
  =
  c_{a,r}^\uparrow+
  \max_{y\in\mathcal Y_a(S)}j_{y,r}.
  \]
- Peak/live-set resource:
  \[
  v_r(a,S,\{\mathbf j_y\})
  =
  \max\left(
  C_{a,r,\mathrm{during}}^\uparrow(S),
  \max_{y\in\mathcal Y_a(S)}j_{y,r}
  \right).
  \]
  The child state \(T(S,a,y)\) carries the artefacts retained after action \(a\); therefore the child continuation's peak already accounts for those live outputs. The action's during-peak accounts for parent-resident objects, workspace and temporary overlaps.
- Scheduled/parallel resource: no recursion is defined for the first prototype. A future implementation must carry an explicit schedule/resource-occupancy state and a validated composition operator.

Write the resource composition as \(\otimes_r\). The plan-cost frontier is:

\[
\mathcal J(S)=
\operatorname{ParetoMin}
\left\{
\left(
c_{a,r}^\uparrow\otimes_r
\operatorname{cmax}_{y\in\mathcal Y_a(S)}j_{y,r}
\right)_{r=1}^{R}
:
a\in\mathcal A(S),\
\mathbf j_y\in\mathcal J(T(S,a,y))\;\forall y
\right\},
\]

where \(c_{a,r}^\uparrow\) is interpreted as additive consumption for \(r\in\mathcal R_\Sigma\) and as an action-during peak together with live-set state for \(r\in\mathcal R_{\max}\). This notation does not license addition for every resource.

If an outcome branch has no feasible continuation, that action cannot be part of a guaranteed decision-completing policy. If no action yields a feasible vector/state, \(\mathcal J(S)=\varnothing\). A budget admits a plan only when its worst-case resource envelope satisfies every hard componentwise limit.

### 7.3 Proof-preserving search accelerators

The AND-OR search can be expensive. Two pruning mechanisms are proposed. Neither may remove a state or plan unless its lower-bound or dominance preconditions are checked.

#### 7.3.1 Resource-specific blocker-distance lower bounds

Let \(B(S)\) be the current unresolved blockers. Construct a relaxed action graph that over-approximates every potentially valid route for discharging or partition-resolving each blocker. It may relax prerequisites and choose favourable outcomes, but it must not omit any valid route. Uncertain routes are included with zero lower-bound cost or the affected pruning rule is disabled.

**Additive resource \(r\in\mathcal R_\Sigma\).** Let \(d_r^\Sigma(b\mid S)\) be the shortest relaxed-path sum of defensible action lower bounds \(c_{a,r}^\downarrow\). Then:

\[
LB_r^\Sigma(S)=\max_{b\in B(S)}d_r^\Sigma(b\mid S).
\]

This is a lower bound on worst-case additive resource consumption, provided every complete outcome path necessarily resolves each blocker and the relaxed graph is a supergraph of all valid discharge routes.

**Peak/live-set resource \(m\in\mathcal R_{\max}\).** Do not sum per-action peak-memory bounds. Let \(m^\downarrow(a,S)\) be a defensible lower bound on the unavoidable live-memory peak while action \(a\) executes from state \(S\), including retained inputs that must remain resident. For blocker \(b\), define the minimax path lower bound:

\[
d_m^{\max}(b\mid S)
=
\min_{p\in\mathcal P_b^{\mathrm{relaxed}}(S)}
\max_{(a,S')\in p}m^\downarrow(a,S').
\]

Then:

\[
LB_m^{\max}(S)=\max_{b\in B(S)}d_m^{\max}(b\mid S).
\]

This is admissible only if every complete branch must follow a route represented in the relaxed graph and each \(m^\downarrow\) is a genuine lower bound on simultaneously live memory. If retained-artifact lifetimes or necessary residency cannot be established, use zero for the affected lower bound and do not prune on that component.

**Lower-bound argument:** on every complete outcome path, the actions that resolve blocker \(b\) form a path in the relaxed graph. The actual peak live memory on that path is at least the maximum of the unavoidable per-action live-memory lower bounds along it, which is at least the minimum such maximum over all relaxed paths. Taking the maximum over blockers therefore remains a lower bound on the policy's worst-case peak memory. This argument depends on the relaxed graph containing every valid blocker-resolution route and on each per-action memory lower bound being sound.

**Safe pruning rule.** For additive resources, compare spent cumulative consumption plus the admissible remaining lower bound to the hard total budget. For peak memory, compare the maximum already observed/committed high-water mark and the admissible lower bound for future unavoidable peaks to the peak-memory limit. Never add action peak-memory estimates as if memory were cumulative.

#### 7.3.2 Blocker-cover LP relaxation — deterministic paths only

The blocker-cover LP is an optional relaxation for **additive resource dimensions only** and for a deterministic, non-branching action path (or a subproblem whose selected actions are all executed on the same path). It is not part of the core contingent-plan pruning rule.

Let \(\bar M_{ba}=1\) when action \(a\) has any potentially valid route to blocker \(b\); the relation must over-approximate all valid routes. For additive resource \(r\in\mathcal R_\Sigma\), solve:

\[
LB_r^{\mathrm{cover}}(S)=
\min_{x_a\ge0}
\sum_{a\in\mathcal A(S)}c_{a,r}^{\downarrow}x_a
\quad\text{subject to}\quad
\sum_{a\in\mathcal A(S)}\bar M_{ba}x_a\ge1
\quad\forall b\in B(S).
\]

The variables are continuous and unbounded above, giving an optimistic fractional relaxation of action multiplicities. This is admissible only if every blocker must be addressed by actions on the same deterministic path, the action-effect relation includes every potentially valid discharge route, and costs are defensible additive lower bounds.

**Important contingent-plan restriction:** do not apply this LP to the union of actions from mutually exclusive policy branches. Summing action counts across branches can exceed the maximum cost of any realised path, so the LP objective can overestimate the worst-case contingent cost and is not an admissible lower bound. A scenario-tree or max-path relaxation would be required before using an LP for branched plans. Until such a formulation is derived and proved, disable this LP whenever the plan branches.

For an eligible deterministic path only, combine it with the additive blocker-distance lower bound:

\[
LB_r^{\mathrm{combined}}(S)=
\max\left\{
LB_r^\Sigma(S),LB_r^{\mathrm{cover}}(S)
\right\}.
\]

Do not apply this LP to peak memory: summing action-memory lower bounds can overestimate the minimum peak live set and could prune a feasible plan. Peak memory uses the minimax-path bound in Section 7.3.1 or zero if a sound live-set lower bound is unavailable. Parallel latency requires a schedule-aware relaxation and is out of scope.

If a blocker can be discharged by deterministic inference over already available evidence without resource-consuming computation, represent that inference as an explicit zero-cost action so the relaxation remains complete.

#### 7.3.3 Proof-preserving state dominance

A search state \(S_1\) may dominate \(S_2\) only when all of the following are established:

1. both states refer to the identical canonical specification, model scope and assurance mode;
2. \(\mathcal Q_1\subseteq\mathcal Q_2\), with both sets sound under the same model assumptions;
3. \(S_1\) has no more open, blocked or conflicted obligations than \(S_2\), and all evidence used by \(S_1\) has valid provenance;
4. cumulative additive consumption in \(S_1\) is componentwise no greater than in \(S_2\), and its peak resources already committed are no greater; its retained/live-artifact set and release semantics are no harder for every continuation;
5. every continuation action/policy available from \(S_2\) has a corresponding valid continuation from \(S_1\), with outcome coverage and proof obligations no harder.

Condition 5 is essential. A smaller QoI set alone does not guarantee that a solver, estimator or verifier remains applicable.

For a finite state abstraction, make the simulation relation explicit. For every action \(a_2\) enabled at \(S_2\), there must be a matching action \(a_1\) enabled at \(S_1\), with no greater upper resource use under the declared resource semantics (and no worse live-set state), such that for every outcome \(y_1\in\mathcal Y_{a_1}(S_1)\), there is a matching outcome \(y_2\in\mathcal Y_{a_2}(S_2)\) whose successor states satisfy \(T(S_1,a_1,y_1)\preceq T(S_2,a_2,y_2)\). The relation must preserve terminal decision predicates, outcome coverage and certificate scope/validity. It need not preserve a verdict branch that is impossible under the stronger state's sound QoI subset: a tighter admissible set may legitimately eliminate an ACCEPT or REJECT branch that remains possible in the weaker state. Every outcome still possible in the stronger state must map to a semantically valid successor of the weaker-state action.

**Conditional dominance proposition:** if \(S_1\preceq S_2\) satisfies these conditions, every decision-complete continuation from \(S_2\) can be simulated from \(S_1\) with no greater worst-case upper resource vector and no weaker terminal assurance. Therefore \(S_2\) may be pruned when searching for Pareto-minimal complete policies. If the simulation relation cannot be checked, retain both states.

This is a conditional dominance argument, not a proof that a generic QoI-set subset test is safe.

**Finite-state simulation prototype (research-only):** the reference harness represents the proposed relation as a finite greatest-simulation fixed point. A candidate action match requires the same action semantic key, preconditions, evidence contract and failure semantics, with no greater upper RU or during-peak memory. Every outcome of the stronger/left action must map to at least one outcome of the weaker/right action whose successor pair remains in the relation. Outcome labels are not treated as proof of semantic equivalence; the mapping is established from the successor-state relation. The harness also enumerates complete contingent policy summaries on a small constructed graph and compares the frontier before and after removing a strictly dominated candidate.

This is not yet integrated into the AND-OR search recursion. It has not been checked on generated graph families, and the finite test does not establish generic correctness for arbitrary numerical action contracts. The report is in [DWAOP finite-state reference harness test report](DSCA_DWAOP_REFERENCE_HARNESS_TEST_REPORT_v0.1.md).


**Finite-state reference implementation (research-only):** the standalone harness now contains a greatest-simulation-relation routine. It begins with pairs satisfying local scope, QoI-set, obligation, capability, live-artifact and resource-order conditions, then repeatedly removes pairs for which an action offered by the weaker state has no semantically compatible, no-more-expensive action in the stronger state, or for which an outcome successor cannot be mapped to a related successor. Outcome labels are not used as a substitute for successor-state semantics. A candidate-frontier reducer removes only strict dominance; equivalent states are retained.

This routine is currently an isolated finite-state prototype. It is **not yet called by the AND-OR planner's search recursion**, and its correctness has not yet been tested by comparing dominance-pruned search against exhaustive unpruned search on generated contingent graphs. The current tests establish the specified relation's behaviour on a hand-constructed graph, including cycles and adversarial contract mismatches; they do not prove the relation sound for arbitrary engineering action contracts.


#### 7.3.4 Action-equivalence reduction

Actions may be merged or one removed only if a checked equivalence relation establishes identical:
- applicability/preconditions;
- possible outcome coverage;
- witness and obligation effects;
- evidence dependencies and checker semantics;
- failure/invalidation behaviour.

If these are equivalent and one action has no greater upper resource cost in every component (and is strictly cheaper in at least one), the more expensive action is dominated. Otherwise retain both. General action-equivalence reduction is established in AI planning; the research task is to test whether numerical proof-effect signatures provide a useful, sound abstraction for GDEC's computation portfolio.

### 7.4 Receding-horizon controller

The planner constructs a bounded contingent plan, executes only its first action, verifies the result, and then replans from the updated evidence and resource state. It does not blindly execute a long predicted plan after its assumptions have changed.

~~~text
DWAOP(spec, resource_budget):
    validate_specification_and_decision_rules(spec)
    obligations = compile_mandatory_obligations(spec)
    state = establish_initial_sound_QoI_set_and_provenance(spec)

    ledger = {
        additive_consumed_upper: zero_vector(),
        peak_committed_upper: initial_live_set_high_water(state),
        live_artifacts: state.retained_artifacts,
        schedule_state: SEQUENTIAL_ONLY
    }

    if specification_invalid_or_claim_inapplicable:
        return REFUSE(reason, state, ledger)

    repeat:
        verify_state_integrity_model_identity_and_live_set(state, ledger)

        blockers = construct_tagged_witness_and_obligation_blockers(state)
        witnesses = generate_decision_reversing_witnesses(state.Q)
        decision = evaluate_robust_decision(state.Q, witnesses)

        if decision.robust and state.obligations.all_satisfied:
            return TERMINAL_DECISION(
                decision,
                independently_checked_certificate_bundle,
                resource_ledger = ledger
            )

        actions = enumerate_supported_actions(state)
        contracts = validate_action_preconditions_and_effect_contracts(
            actions,
            blockers,
            resource_semantics
        )

        apply_only_admissible_resource_specific_lower_bound_pruning(
            state,
            contracts,
            ledger,
            resource_budget
        )
        apply_proof_preserving_state_dominance_including_live_set()

        plan_frontier = bounded_vector_cost_AND_OR_search(
            state,
            eligible_contracts,
            hard_resource_budget = resource_budget,
            current_resource_ledger = ledger,
            mandatory_obligations = obligations,
            terminal_decision_gate = decision_gate
        )

        if no_complete_plan_fits(plan_frontier):
            if required_claim_is_invalid_or_unsupported:
                return REFUSE(reason, blockers, ledger)
            return INCONCLUSIVE(
                blockers,
                remaining_additive_budget,
                remaining_peak_limits,
                rejected_action_and_pruning_reasons,
                ledger
            )

        if plan_frontier_has_multiple_incomparable_options and no_predeclared_operator_preference:
            return PLAN_SELECTION_REQUIRED(plan_frontier)

        action = first_action(select_declared_preference_from_Pareto_frontier(plan_frontier))
        prior_ledger = ledger
        result = execute_sequentially_and_record_resource_observations(action)
        ledger = update_resource_ledger_by_declared_semantics(
            prior_ledger,
            action,
            result,
            resource_semantics
        )

        if result.failed_or_timed_out:
            preserve_failure_artifacts_and_update_state(state, result)
            if any_hard_resource_limit_exceeded(ledger, resource_budget):
                return INCONCLUSIVE("ACTUAL_RESOURCE_LIMIT_EXCEEDED", blockers, ledger)
            continue

        proposed_state = apply_typed_evidence_transition(state, result)
        checker_result = independent_checker.verify_transition_certificates_and_live_set(
            old_state = state,
            action = action,
            result = result,
            proposed_state = proposed_state,
            old_resource_ledger = prior_ledger,
            new_resource_ledger = ledger
        )

        if checker_result != VERIFIED:
            preserve_all_artifacts()
            state = mark_conflicted_or_incomplete(state, proposed_state, checker_result)
        else:
            state = proposed_state

        if any_hard_resource_limit_exceeded(ledger, resource_budget):
            return INCONCLUSIVE("ACTUAL_RESOURCE_LIMIT_OVERRUN", state, ledger)

~~~

The resource ledger keeps additive consumption, peak high-water marks, and live retained artefacts as separate fields. For additive resources, remaining budget is the hard limit minus cumulative upper consumption. For peak/live-set resources, the planner retains the original peak limit and checks whether the maximum of the already committed high-water mark and the predicted future peak fits that limit; it does not subtract previous peak memory and then add action memory again. The first prototype prohibits overlapping actions, so elapsed wall time is additive. Parallel execution requires a schedule-aware ledger and is unsupported.


The transition checker receives both the pre-action and post-action ledgers. It must independently recompute or validate the resource update from the action's declared aggregation semantics and measured resource observations; it must not trust the planner's post-action ledger as an asserted status.

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
- Goal-oriented adaptive modelling of stochastic heterogeneous media and model-based multilevel Monte Carlo.
- Running error propagation through generated finite-element kernels.
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
| Vexler & Wollner (2008), adaptive FEM for elliptic optimisation with control constraints | A posteriori estimates for both cost functionals and QoIs with pointwise inequality constraints; adaptive mesh refinement | Do not claim novelty for QoI-driven mesh adaptation in constrained optimisation |
| Becker et al. (2023), goal-oriented AFEM | Joint mesh-refinement and iterative-solver steering, with convergence and optimal rates in total computational cost under assumptions | Do not claim novelty for solver/mesh co-steering |
| NASA Nemec & Aftosmis (2014/2015), automatic verification of goal-oriented flow simulations | Adjoint-weighted error estimates and automatic control of discretisation error in practical Euler simulations | Do not claim novelty for automated goal-oriented verification and mesh control |
| Bespalov et al. (2019), goal-oriented stochastic Galerkin FEM | Joint spatial and parametric adaptive refinement for QoIs under uncertain inputs, with a reliable and efficient two-level a posteriori estimate | Do not claim novelty for spatial/parametric goal-oriented adaptivity or reliable QoI error estimation |
| Mohite & Upadhyay (2012), adaptive FEM for laminated plates | Goal-based discretisation adaptivity plus a modelling-error indicator and automatic selection of local plate-model fidelity | Do not claim novelty for coupled model/discretisation adaptivity |
| Bespalov, Praetorius & Ruggeri (2026), nonlinear goal-oriented stochastic Galerkin FEM | Goal-oriented adaptivity for continuously Gâteaux-differentiable nonlinear QoIs under countably many uncertain parameters | Do not claim novelty for extending goal-oriented adaptivity to nonlinear QoIs under parametric uncertainty |
| Kerfriden, Kundu & Claus (2019), Bayesian inverse FEM adaptivity | Simultaneous control of goal-oriented FEM discretisation error and statistical sampling error in Bayesian parameter identification, with stopping and mesh-refinement decisions | Do not claim novelty for coupling sampling sufficiency and FEM discretisation-error control |
| Bonilla-Villalba et al. (2020), stochastic elastodynamics model adaptivity | Joint control of spatial discretisation, surrogate-model and Monte Carlo sampling errors for QoI statistics at minimum cost | Do not claim novelty for coordinating these numerical approximation and sampling errors |
| Goal-oriented adaptive modelling of random heterogeneous media / model-based MLMC (2019) | QoI-driven adaptive surrogate/model resolution and multilevel Monte Carlo for stochastic heat conduction and elastostatics | Do not claim novelty for QoI-driven model-resolution plus sampling-cost control |
| Yang et al. (2024), active learning for RBDO under multiple simulation models | Active constraints, model selection and differing simulation costs in reliability-based design optimisation | Do not claim novelty for cost-aware fidelity/action selection in reliability optimisation |
| Ma et al. (2023), adaptive Kriging RBDO | Active-constraint-focused local/global enrichment in augmented reliability space for single- and double-loop reliability-based design optimisation | Do not claim novelty for targeted sampling near active probabilistic constraints |
| Liu et al. (2026), interval-uncertainty RBDO | Ensemble surrogate modelling and global learning for non-probabilistic reliability under interval uncertainty | Do not claim novelty for interval-uncertainty RBDO with adaptive surrogate enrichment |
| Buchheim, Grütering & Meyer (2025), PDE branch-and-bound with adaptive refinement | Global branch-and-bound with a posteriori safe dual bounds and adaptive temporal-grid refinement for parabolic optimal control | Do not claim novelty for branch-and-bound coupled to safe numerical bounds and discretisation refinement |
| Vayanos et al. (2023), robust optimisation with decision-dependent information discovery | Decisions control when uncertain information is revealed through costly exploratory investments; develops multistage robust formulations and a solution method | Do not claim novelty for planning costly queries that reveal information before a decision |
| Ley et al. (2026), optimisation under elementwise controllable uncertainty | Decision maker can pay to shrink bounded uncertainty intervals element by element and optimise under the remaining uncertainty | Do not claim novelty for paid computation/measurement reducing an uncertainty set |
| Solak et al. (2026), MF-CAS preprint | Joint sample-location and fidelity selection using decomposed uncertainty intervals and model cost | Do not claim novelty for cost-aware interval-based sampling/fidelity selection |
| Zhao et al. (2026), MF-PBALC | Posterior-mean failure-probability bounds, a stopping rule, and cost-aware joint evaluation-point/fidelity selection for structural reliability | Do not claim novelty for bounded stopping or cost-aware joint fidelity selection |
| Habera et al. (2026), running error analysis in FE kernels | Automatically propagates running round-off/error estimates through generated FE kernels; the paper explicitly states its estimates are not certified bounds | Do not claim novelty for running kernel-error estimates; do not treat REA estimates as VWECs without a separate certification argument |
| Ning & You (2018), adaptive robust optimisation with minimax regret | Minimax-regret objectives and algorithms in adaptive robust optimisation | Do not claim novelty for the regret objective or worst-case regret formulation |
| Mugdan, Christen & Eriksson (2023), optimality certificates for classical planning | Computer-verifiable certificates for plan correctness and optimality, with sound/complete certification methods in the studied setting | Do not claim novelty for plan certificates or optimality certificates in generic planning |
| Hill, Komendantskaya & Petrick (2020), Proof-Carrying Plans | Resource logic and typed pre/postconditions for checking AI plans, with formal soundness proof and Agda formalisation | Do not claim novelty for resource-aware plans carrying machine-checkable proofs |
| Gardiol & Kaelbling, action equivalence for planning | Runtime partitioning of actions into approximate equivalence classes to reduce planning search | Do not claim novelty for action-signature compression in generic planning |
| CEGAR literature | Counterexample generation, abstraction refinement and validation loops | Do not claim novelty for counterexample-guided refinement alone |
| ACCESS (2024), assurance-case-centric engineering | Model-based assurance-case/artifact traceability, automated formal-method evidence invocation, logical checking and change-impact analysis | Do not claim novelty for assurance graphs or automated evidence integration in isolation |
| NASA (2023), formal verification in assurance cases | Tool preconditions, postconditions and assurance constraints integrated into machine-supported assurance arguments | Do not claim novelty for verifier applicability contracts alone |
| Automated assurance-case pattern selection for CPS (2022) | Coverage and optimisation of assurance-case patterns | Do not claim novelty for obligation coverage or evidence-pattern selection alone |
| Yang et al. (2023), RL for adaptive mesh refinement | AMR formulated as sequential decision-making under a computational budget; policy compared with greedy ZZ refinement | Do not claim novelty for framing refinement as sequential budgeted decisions |
| US20240348663A1, AI-enhanced simulation and modeling experimentation and control | Published claims describe simulation goals/constraints, uncertainty reduction, active-learning scenario selection, and look-ahead/branching adapted to resources | Material adjacent patent disclosure; requires patent-professional claim analysis. This is not a legal opinion |

### 11.1 What this does to the novelty hypothesis

The research must now treat all the following as established ingredients: QoI-focused error control; constrained optimisation with adaptive FEM; joint spatial, parametric, surrogate, sampling and model-error control; adaptive reliability-based design optimisation under probabilistic and interval uncertainty; branch-and-bound with safe numerical bounds and adaptive discretisation; robust regret; paid information discovery; cost-aware multi-fidelity selection; resource-aware proof-carrying plans; action equivalence; counterexample-guided refinement; and assurance-case obligation management.

The remaining candidate is narrower:

**A numerical-engineering-specific, certificate-first computation planner in which (i) each action emits a scoped, independently checkable set-transition or witness-exclusion artefact, (ii) action contracts explicitly describe the numerical assumptions and QoI regions to which that artefact applies, and (iii) a contingent planner uses those contracts to construct a complete decision-and-assurance proof path, with proof-preserving pruning and explicit fail-closed outcomes.**

The specific algorithmic mechanism proposed for evaluation is the pairing of:
- **Verified Witness-Effect Certificates (VWEC):** proof objects for excluding a defined decision-reversing QoI region under an identified model/action outcome; and
- **Blocker-distance lower bounds plus proof-preserving state dominance:** search accelerators that prune only when their admissibility conditions are checked.

This is not yet a demonstrated gap. It may still be obvious to a skilled reader as an application-specific combination of proof-carrying planning, robust optimisation, certified numerical analysis and assurance cases. The novelty claim is therefore **OPEN / UNPROVEN**. A full literature, dissertation, standards and patent-family search is needed before public claims or an invention disclosure.

### 11.2 Primary links

- Vexler & Wollner (2008), adaptive FEM for elliptic optimisation with control constraints: https://doi.org/10.1137/070683416
- Bespalov et al. (2019), goal-oriented stochastic Galerkin FEM: https://doi.org/10.1016/j.cma.2018.10.041
- Mohite & Upadhyay (2012), adaptive FEM for laminated plates: https://doi.org/10.1016/j.compstruc.2012.08.002
- Bespalov, Praetorius & Ruggeri (2026), nonlinear goal-oriented stochastic Galerkin FEM: https://doi.org/10.1137/23M1597678
- Ma et al. (2023), adaptive Kriging RBDO: https://doi.org/10.1016/j.ress.2023.109386
- Liu et al. (2026), interval-uncertainty RBDO: https://doi.org/10.1016/j.apm.2026.117029
- Buchheim, Grütering & Meyer (2025), PDE branch-and-bound with adaptive refinement: https://doi.org/10.1007/s10589-025-00654-3
- Oden & Prudhomme (2001), goal-oriented FEM: https://doi.org/10.1016/S0898-1221(00)00317-5
- Becker et al. (2023), GOAFEM: https://doi.org/10.1007/s00211-022-01334-8
- NASA Nemec & Aftosmis, automatic goal-oriented flow verification: https://ntrs.nasa.gov/citations/20150000864
- Kerfriden, Kundu & Claus (2019), Bayesian inverse-FEM adaptivity: https://pmc.ncbi.nlm.nih.gov/articles/PMC6416561/
- Bonilla-Villalba et al. (2020), stochastic elastodynamics model adaptivity: https://doi.org/10.1615/Int.J.UncertaintyQuantification.2020031735
- Adaptive modelling of random heterogeneous media / model-based MLMC (2019): https://doi.org/10.1016/j.camwa.2019.04.014
- Yang et al. (2024), multi-model active learning for RBDO: https://doi.org/10.1016/j.strusafe.2023.102426
- Vayanos et al., decision-dependent information discovery: https://doi.org/10.1287/mnsc.2021.00160
- Ley et al. (2026), elementwise controllable uncertainty: https://doi.org/10.1007/s00291-026-00856-z
- Solak et al. (2026), MF-CAS: https://arxiv.org/abs/2610.38582
- Zhao et al. (2026), MF-PBALC: https://doi.org/10.1016/j.ress.2026.113871
- Habera et al. (2026), running error analysis in FE kernels: https://arxiv.org/abs/2609.37844
- Ning & You (2018), adaptive robust optimisation with minimax regret: https://doi.org/10.1016/j.compchemeng.2017.09.026
- Mugdan, Christen & Eriksson (2023), optimality certificates for classical planning: https://ai.dmi.unibas.ch/papers/mugdan-et-al-icaps2023.pdf
- Hill et al. (2020), Proof-Carrying Plans: https://doi.org/10.1145/3414080.3414094
- Gardiol & Kaelbling, computing action equivalences for planning: https://people.csail.mit.edu/nhg/papers/gardiol_icaps_consortium.pdf
- Clarke et al. (2000), CEGAR: https://doi.org/10.1007/10722167_15
- ACCESS (2024): https://doi.org/10.1016/j.jss.2024.112034
- NASA, formal verification in assurance cases: https://ntrs.nasa.gov/citations/20230007599
- Automated assurance-case pattern selection for CPS (2022): https://doi.org/10.1007/978-3-031-14835-4_6
- Yang et al. (2023), RL for AMR: https://proceedings.mlr.press/v206/yang23e.html
- Patent publication: https://patents.google.com/patent/US20240348663A1/en

The patent publication is listed as pending by Google Patents, which explicitly warns that its legal-status display is not a legal conclusion. The publication has a long priority/family chain. Its published claims include uncertainty reduction and active-learning scenario selection, and look-ahead/branching depth adapted to objectives and resources. It is an adjacent disclosure requiring professional review; it does not establish anticipation, obviousness, infringement or freedom to operate for DWAOP.

## 12. Required novelty experiments

The central experiment is not merely “does DWAOP use fewer DOFs?” It is whether proof-obligation-aware planning gives a better cost/assurance frontier than a strong combination of existing methods.

### Baselines

1. uniform refinement / fixed solver tolerances;
2. conventional goal-oriented AFEM;
3. GOAFEM-like joint mesh/solver steering where applicable;
4. goal-oriented spatial/parametric or stochastic model-adaptivity baselines for uncertain-input cases;
5. adaptive Kriging / multi-fidelity reliability-learning baselines for probabilistic or interval reliability cases;
6. branch-and-bound with safe numerical bounds and adaptive discretisation for finite decision abstractions where applicable;
7. a greedy action selector using the same action contracts but no look-ahead;
8. an obligation-aware prerequisite planner without numerical witness certificates;
9. DWAOP with witness/obligation planning and DAPC;
10. offline oracle policy for retrospective lower-bound comparison only.

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
- two resource dimensions: sequential wall time (additive) and peak memory (live-set high-water mark); execute actions sequentially and explicitly prohibit concurrency;
- finite sound action outcome abstractions;
- bounded AND-OR search depth of at most three actions;
- an independent checker for state transitions and terminal decision;
- adversarial tests for wrong-QoI bound, near-boundary decision, conflicting evidence, action timeout and budget exhaustion.

No GPU, probabilistic reliability or full multi-physics scope in the first prototype. It should be compared against a greedy selector and conventional adaptive FEM. If the prototype does not show an advantage or reliable new assurance behaviour, stop.

## 14. Research status and next gate

- **RESEARCHED:** constrained goal-oriented AFEM, goal-oriented flow verification, stochastic/parametric and nonlinear QoI adaptivity, model/discretisation/sampling error control, Bayesian inverse-FEM, adaptive RBDO under probability and interval uncertainty, PDE branch-and-bound with safe numerical bounds, multi-fidelity/active learning, decision-dependent information discovery, controllable uncertainty, running FE-kernel error analysis, minimax regret, proof-carrying plans, action equivalence, CEGAR, assurance cases, sequential AMR and one adjacent patent publication.
- **FORMULATED:** decision-witness state, obligation state, typed branch-conditional action effects, VWEC and DAPC certificate layers, robust AND-OR planning objective, resource-specific aggregation semantics, additive-only blocker-cover LP, peak-memory live-set accounting, blocker-distance lower bounds and proof-preserving state dominance.
- **REFERENCE HARNESS IMPLEMENTED (RESEARCH ONLY):** standalone finite-state planner/oracle, greatest-simulation relation, strict candidate-frontier reducer and complete-policy summary enumerator in [`research/prototypes/dwaop_reference_harness.py`](prototypes/dwaop_reference_harness.py). It is not imported by GDEC and does not change production/runtime behaviour.
- **EXECUTED:** 26 Python unittest cases passed on Python 3.13.5 against the exact committed harness blob `0ac15407371d241678d62459340067b57fcb1d64`. Tests cover the contingent finite fixture, 25 additive-budget points, 2,401 small action-cover families, resource aggregation, dominance relation direction, missing action, excess cost, unmatched successor, model-scope mismatch, evidence/failure-contract mismatch, outcome-label independence, cyclic action graph handling, transitivity, policy-frontier preservation, elimination of an impossible verdict branch, seven candidate-cost values and 168 parameterised dominance cases across QoI shape, prior RU, peak memory and outcome labels. `py_compile` also passed.
- **HAND-CHECKED:** sequential additive totals, peak/live-set memory and contingent branch aggregation in the separate resource-algebra note.
- **CONDITIONALLY JUSTIFIED:** terminal soundness proposition under explicit enclosure, transition and checker assumptions.
- **NOT INTEGRATED:** dominance and frontier reduction are not yet called within the general finite planner's AND-OR search recursion; generated-graph pruned/unpruned search comparison has not been run.
- **NOT IMPLEMENTED:** no GDEC DWAOP controller, VWEC generator, production resource ledger, independent DAPC checker, or blocker-cover LP pruning. The harness includes only a test-specific plan-tree validator and finite policy-summary enumerator.
- **NOT TESTED:** no FEM/CFD solve, no GDEC runtime integration, no numerical certificate generation, no dominance-pruned search comparison across different graph topologies, no large/cyclic generated contingent graph families, and no measured performance advantage.
- **NOT PROVEN:** global optimality, tractability at scale, novelty, patentability or freedom to operate. The tested lower bound is the weak max-of-cheapest-resolver bound, not the optional blocker-cover LP.
- **NOT INDEPENDENTLY VERIFIED:** no external numerical-analysis, formal-methods or planning review.
- **NOT APPROVED:** no production implementation authorisation.

**Next gate:** generate different contingent graph topologies (including multi-level branches and cycles), compare dominance-pruned and unpruned Pareto frontiers against exhaustive enumeration, and add mutations for invalid state/action simulation assumptions. Only after those checks and an independent review should the relation be wired into the offline finite-state planner. Obtain independent review of action contracts and proof obligations before proposing any GDEC runtime integration. Main, WP2 and WP3 remain outside this research task.
