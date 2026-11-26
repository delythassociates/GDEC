# DSCA v0.1 — Action-Selection Mathematics and Adversarial Test Design

**Status:** RESEARCH DESIGN — NOT IMPLEMENTED, NOT VALIDATED, NOT APPROVED FOR PRODUCTION  
**Parent specification:** `research/DSCA_DECISION_SUFFICIENCY_ALGORITHM_SPEC_v0.1.md`  
**Workstream:** `research/decision-sufficiency-algorithm`  
**Purpose:** Make the proposed controller mathematically explicit enough to falsify before any implementation is authorised.

---

## 1. Scope and non-claims

This note sharpens two parts of DSCA:

1. how the controller determines whether the engineering decision is already sufficiently supported; and
2. how it chooses a next computational action without confusing a useful ranking heuristic with a safety guarantee.

It does **not** propose a new FEM/CFD discretisation, a new a posteriori estimator, a new probability theory, or a theorem establishing optimality. It does not change GDEC production code, the current WP2 campaign, solver mathematics, estimator mathematics, GPU backends or WP3.

The current state of prior art is important. Goal-oriented adaptive FEM already combines mesh refinement and iterative-solver steering, and has theoretical results relating convergence to total computational cost for specific problem classes. Active-learning methods also exist for reliability-based design optimisation with multiple simulation models and differing evaluation costs. Sequential allocation of simulation effort among competing alternatives is also an established research area. DSCA must be tested against these methods rather than claiming those ideas as new.

References and the precise novelty boundary are in Section 10.

## 2. Separate the evidence channels before planning

Represent accumulated evidence as typed channels, not one undifferentiated confidence score:

\[
E = (E_{\mathrm{alg}}, E_{\mathrm{disc}}, E_{\mathrm{input}},
E_{\mathrm{model}}, E_{\mathrm{validation}}, E_{\mathrm{provenance}}).
\]

| Channel | What it describes | Examples of actions that may affect it |
|---|---|---|
| Algebraic/numerical | Error from incomplete solution of the discrete equations, floating-point or numerical execution | additional solver work, tighter admissible tolerance, independent residual check |
| Discretisation/representation | Error from mesh, polynomial order, quadrature or approximation spaces | mesh refinement, order increase, applicable estimator/reconstruction |
| Input/parameter | Uncertainty in loads, geometry, material parameters and boundary data | parameter study, sampling, measurement, sensitivity analysis |
| Model-form | Missing physics, constitutive inadequacy, idealised contacts, geometry simplification, discrepancy | model comparison, higher-fidelity physics, targeted experiment; not ordinary mesh refinement alone |
| Validation | Whether the model's predictions agree with relevant physical observations over a declared domain | experiment, benchmark data, independent physical comparison |
| Provenance/integrity | Whether evidence belongs to the stated input, executable, configuration and run | hashing, signature/authenticity check, reproducibility or independent audit |

An action must declare which channels it can legitimately affect and which assumptions permit that effect. A finer mesh does not, by itself, reduce uncertain material data or model-form discrepancy. A second solver using the same governing equations and boundary conditions is not independent physical validation. A verifier can check a numerical claim without proving that the physical model represents reality.

**Required design rule:** no scalar “total uncertainty” is allowed unless the aggregation law, dependence assumptions, coverage of each component and assurance meaning are all explicit.

## 3. Decision sufficiency: the terminal gate

Let \(\mathcal D\) be the allowed decision set, \(\mathcal Q(E)\) the admissible joint set of QoI values supported by valid bounded evidence, and \(L(d,q)\) a declared decision-loss function.

### 3.1 General bounded-decision criterion

Define worst-case regret over the admissible QoI set:

\[
\mathcal R(d;\mathcal Q)
=
\sup_{q\in\mathcal Q}
\left[
L(d,q)-\min_{d'\in\mathcal D}L(d',q)
\right].
\]

The minimum achievable worst-case regret is

\[
\mathcal R^*(\mathcal Q)
=
\min_{d\in\mathcal D}\mathcal R(d;\mathcal Q).
\]

A bounded-mode decision is sufficient only if:

- \(\mathcal R^*(\mathcal Q)\leq\tau\), for a decision-regret tolerance \(\tau\) declared before the run;
- every mandatory evidence obligation for the requested assurance class is satisfied;
- all evidence used in \(\mathcal Q\) is applicable, traceable and internally consistent.

The controller may return a minimax-regret decision and its regret bound. It must not silently equate a small regret tolerance with a statutory or safety acceptance criterion; the decision owner must define that relationship.

For a single deterministic constraint \(g(q)\leq0\), retain the more transparent three-way test:

- **Robustly acceptable:** \(\sup_{q\in\mathcal Q}g(q)\leq0\).
- **Robustly unacceptable:** \(\inf_{q\in\mathcal Q}g(q)>0\).
- **Inconclusive:** otherwise.

A point estimate on the acceptable side is not enough when its valid interval crosses the constraint boundary.

### 3.2 Probabilistic-decision criterion

For a documented probability model, define posterior decision risk:

\[
R^*(E)=\min_{d\in\mathcal D}
\mathbb E[L(d,Q)\mid E].
\]

For a constraint with violation event \(V\), an acceptance rule may require

\[
P(V\mid E)\leq\epsilon,
\]

where \(\epsilon\), the probability model, calibration domain and loss of false acceptance are declared in advance.

A minimum-expected-loss decision is not automatically an acceptable engineering decision. It must also pass all explicit risk constraints and mandatory assurance gates. If calibration, dependence structure, tail behaviour or applicability is unsupported, probabilistic assurance is unavailable; DSCA must not substitute a heuristic score.

### 3.3 Decision status is not solver status

The controller must preserve separate fields for:

- algebraic status;
- discretisation/QoI status;
- input/model uncertainty status;
- validation status;
- decision status;
- assurance mode;
- terminal reason.

Valid terminal outcomes include:

- `ACCEPT`: the declared acceptance decision passes the required decision gate and mandatory obligations;
- `REJECT`: the admissible evidence robustly violates a declared requirement;
- `INCONCLUSIVE`: the evidence does not determine the decision, or the available budget/capabilities cannot resolve it;
- `REFUSE`: the requested assurance cannot be attempted because the specification, method applicability, physical assumptions, evidence integrity or required capability is invalid or unsupported.

“Not enough budget” is not “pass”. “No action has positive estimated value” is not “pass”. “Solver converged” is not “accept”.

## 4. Action eligibility contract

A candidate action \(a\) is eligible only if all of the following are true:

1. The relevant backend/method is actually available for this problem and device.
2. Its mathematical and engineering applicability preconditions are satisfied.
3. It targets at least one currently unresolved evidence channel.
4. Its result can be incorporated into the current evidence state without violating the evidence-dependence rules.
5. Its required inputs, output semantics and provenance are specified.
6. Its resource upper bound fits the remaining hard budget, or the action is an explicitly mandatory obligation with an approved budget allocation.
7. It is permitted by the selected assurance mode.

Each action descriptor should include:

| Field | Required meaning |
|---|---|
| `action_id` | Stable action identifier and version |
| `targets` | Evidence channels the action can affect |
| `preconditions` | Mesh/physics/solver/data/device applicability requirements |
| `evidence_contract` | Exact evidence type and assurance class the action can produce |
| `outcome_model` | Bounded outcome set or calibrated probabilistic outcome model |
| `cost_upper` | Conservative upper bound on resource consumption |
| `cost_actual` | Measured cost recorded after execution |
| `dependencies` | Evidence and artifacts consumed; shared assumptions or residuals |
| `failure_semantics` | What counts as failure, conflict, timeout or unsupported execution |

An unavailable GPU kernel is an ineligible GPU action; it must not be represented as a successful GPU execution after CPU fallback. A separately declared CPU action may be selected if it is supported and within budget. Backend substitution must be visible in the action trace.

## 5. Bounded-mode action policy

### 5.1 Sound evidence update

Let \(\mathcal Y_a(E)\) be the set of possible outcomes of action \(a\), and let

\[
\mathcal Q_{a,y}=\mathcal Q(E\oplus(a,y))
\]

be the admissible QoI set after outcome \(y\).

For a sound, applicable evidence update, the new set should satisfy

\[
\mathcal Q_{a,y}\subseteq\mathcal Q(E).
\]

A reported empty intersection must be treated as **conflicting/inconsistent evidence**, not as zero uncertainty or a perfect result. The controller must preserve the conflicting artifacts and return `INCONCLUSIVE` or `REFUSE` according to the cause; it must not silently discard the inconvenient source.

### 5.2 Conservative guaranteed reduction

Use the minimax-regret ambiguity measure \(A(\mathcal Q)=\mathcal R^*(\mathcal Q)\). For an eligible action define:

\[
G_a =
A(\mathcal Q(E))
-
\sup_{y\in\mathcal Y_a(E)}
A(\mathcal Q_{a,y}).
\]

\(G_a\) is the worst-case guaranteed reduction in the declared ambiguity measure, provided the outcome set and all resulting admissible sets are sound. It is not an expected reduction.

For a vector resource cost \(c_a\) (for example wall time, CPU time, peak memory, energy), apply the hard componentwise budget gate first:

\[
\overline c_{a,r}\leq B_{r,\mathrm{remaining}}
\quad\text{for every controlled resource }r.
\]

If actions must be ranked, define a cost scalarisation \(C_w(a)=w^T\overline c_a\) using weights \(w\) declared before execution. A candidate ranking score is:

\[
S_a=\frac{G_a}{C_w(a)}.
\]

This ratio is a **policy heuristic**, not a proof of globally optimal computation. It can rank only eligible actions with positive conservative gain and a valid positive cost bound. If cost is multi-objective and no defensible weights exist, preserve the Pareto set rather than inventing a single scalar.

### 5.3 Mandatory evidence is a separate gate

Some actions are mandatory because of the requested assurance class, regardless of their predicted decision-risk reduction. Examples include a required independent checker or a required experimental comparison. Such an action is not removed merely because its estimated \(G_a\) is zero. It must still pass capability and budget checks.

If a mandatory obligation cannot be met, the controller returns `INCONCLUSIVE` or `REFUSE`; it does not lower the assurance class without explicit owner authorisation.

### 5.4 Bounded-mode selection procedure

Candidate deterministic policy:

1. Test decision sufficiency using Section 3.
2. If sufficient and mandatory obligations are complete, terminate with the supported decision.
3. Enumerate supported actions and apply the eligibility contract.
4. Execute mandatory eligible actions according to the declared obligation order.
5. For remaining actions, construct sound outcome sets and compute \(G_a\).
6. Rank positive-gain actions by \(S_a\), subject to hard resource budgets.
7. If no action has defensible positive worst-case gain and the decision is unresolved, return `INCONCLUSIVE`; do not force a pass.
8. If action effects are complementary, use bounded look-ahead over action sequences rather than assuming a greedy one-step policy is sufficient.

This policy is deliberately conservative. It may return inconclusive even when an action would probably help. That is an efficiency limitation to measure, not a reason to weaken the assurance gate.

## 6. Probabilistic-mode action policy

For a calibrated probabilistic model, define the expected value of sample information / computation for action \(a\):

\[
\operatorname{EVSI}(a\mid E)
=
R^*(E)
-
\mathbb E_{Y_a\mid E}
\left[
R^*(E,Y_a)
\right].
\]

Under a coherent model where the action produces information and the same decision/loss model is used before and after observing it, this expected reduction in optimal Bayes risk is non-negative. That property does **not** establish that the model is calibrated or that the estimated EVSI is accurate.

A cost-adjusted score is

\[
\operatorname{NetVOC}(a\mid E)
=
\operatorname{EVSI}(a\mid E)
-
\lambda\,\mathbb E[C_a\mid E].
\]

Requirements:

- \(\lambda\) and the cost units are declared before the run;
- hard resource limits are applied separately, not hidden inside \(\lambda\);
- probabilities for future outcomes are calibrated for the relevant action and problem domain;
- dependent evidence is modelled jointly;
- where the outcome/cost model is estimated, use conservative uncertainty bounds or lower-confidence estimates for action ranking;
- do not use a DWR indicator as a standard deviation or likelihood;
- no positive NetVOC can waive mandatory evidence obligations.

A probabilistic action policy is not available when these requirements are unmet. In that case bounded mode may be used if a valid bound exists; otherwise the outcome is heuristic or incomplete, with no assurance claim.

## 7. Non-myopic planning and action complementarity

A greedy action can be a poor choice when one computation enables another. For example, a sensitivity study may not itself resolve a constraint, but may identify which parameter measurement is valuable; the measurement may then resolve the decision.

The controller should therefore compare:

- one-step greedy selection;
- fixed-depth action-sequence look-ahead;
- mandatory-action-first selection;
- an oracle lower bound used only for offline benchmark analysis.

For a finite-horizon probabilistic policy, a conceptual Bellman recursion is:

\[
V_h(E,b)=
\min\left\{
R^*(E),\;
\min_{a\in\mathcal A(E,b)}
\left[
\lambda C(a)
+
\mathbb E_{Y_a\mid E}
V_{h-1}(E\oplus(a,Y_a),b-C(a))
\right]
\right\}.
\]

This expression is only a planning template. It requires a valid transition/outcome model, a well-defined terminal loss, resource-state updates and mandatory-obligation handling. It should not be implemented until the one-step deterministic bounded policy is understood.

For bounded mode, a conservative finite action tree can minimise the worst-case terminal ambiguity subject to an upper-bound resource budget. The tree must include all admissible outcomes and all branch costs; pruning a costly adverse branch is not allowed.

## 8. Cost accounting and stopping integrity

Total cost includes:

\[
C_{\mathrm{total}}=
C_{\mathrm{setup}}+
C_{\mathrm{solve}}+
C_{\mathrm{transfer}}+
C_{\mathrm{estimator}}+
C_{\mathrm{verification}}+
C_{\mathrm{failed}}+
C_{\mathrm{orchestration}}.
\]

At minimum, record wall-clock time, CPU time, peak memory, accelerator time and transfer time when relevant. Record energy or monetary cost only when measured with a documented method. Failed, timed-out and abandoned actions count against the actual consumed budget.

Predicted cost is used for pre-execution eligibility; actual cost is used for the cumulative budget. A budget overrun must be reported and must not be hidden by resetting the controller or excluding failed attempts.

## 9. Adversarial benchmark suite

These are future test specifications, not executed tests. Each case should have a known reference decision or a deliberately unresolvable reference state.

| ID | Adversarial construction | Incorrect behaviour being tested | Required DSCA response |
|---|---|---|---|
| A01 | Tiny algebraic residual with a coarse mesh and a QoI outside its target tolerance | Treating algebraic convergence as QoI accuracy | Keep algebraic status separate; consider a valid discretisation action |
| A02 | Point QoI estimate passes, but its valid error interval crosses the acceptance limit | Accepting from the point estimate | `INCONCLUSIVE`; no robust acceptance |
| A03 | QoI changes little over two or more refinements, but no applicable estimator/bound exists | Promoting apparent stability to certification | Heuristic only; no bounded acceptance |
| A04 | DWR asymptotic indicator is supplied as a Gaussian standard deviation | Converting an indicator into a probability model | Refuse probabilistic assurance; retain DWR as heuristic evidence |
| A05 | Two uncertain inputs are strongly correlated, but an action/model treats them as independent | Underestimating joint tail risk | Preserve joint dependence or refuse the claimed risk level |
| A06 | DWR and residual estimators reuse the same residual information | Counting correlated evidence twice | Record dependency; no unjustified confidence multiplication |
| A07 | Model-form discrepancy dominates while the proposed action is mesh refinement | Spending resources on an action that cannot address dominant uncertainty | Do not claim model uncertainty reduction; seek applicable model/experiment action or return inconclusive |
| A08 | Stress QoI is evaluated at a singular corner where the assumed estimator regularity does not hold | Issuing a bound outside estimator assumptions | Mark estimator inapplicable; no certified stress decision |
| A09 | Actual GPU execution is unavailable but a planner proposes a GPU action | Silent CPU fallback or invented accelerator evidence | GPU action ineligible; explicit CPU action may be selected separately |
| A10 | An action times out after consuming most of its budget | Ignoring failed-run cost | Account for actual cost; re-evaluate remaining budget |
| A11 | New independent evidence conflicts with a previous certified interval | Intersecting inconsistent intervals into an empty “perfect” set or discarding one source | Flag evidence conflict; preserve both artifacts; no acceptance |
| A12 | Evidence is stale, belongs to a different input hash or has a tampered output | Reusing evidence for the wrong engineering configuration | Provenance gate fails; refuse the affected assurance claim |
| A13 | A rare-event tail lies outside the calibration data or input distribution | Treating nominal calibration as valid out of domain | Refuse probabilistic risk assurance or return incomplete |
| A14 | Two designs have overlapping QoI intervals and their errors share common-mode input uncertainty | Declaring a winner from independent scalar intervals | Compare on the joint admissible set; remain inconclusive if ranking can reverse |
| A15 | Two individually low-value actions are valuable only as a sequence | Greedy one-step policy stops prematurely | Look-ahead finds the sequence, or policy records its myopic limitation and returns inconclusive |
| A16 | One action reduces one QoI uncertainty but worsens or does not address another mandatory QoI | Optimising an unweighted average and hiding a critical constraint | Enforce all mandatory QoI/constraint gates; no aggregate-score override |
| A17 | The solver gives a stable answer under a systematically wrong boundary condition | Treating numerical reproducibility as physical validity | Flag input/model specification and validation limitations; numerical stability is not model validation |
| A18 | An action's estimated setup/transfer cost is low but actual end-to-end cost is high | Selecting by kernel time while hiding orchestration cost | Use actual total cost; report estimate error and budget overrun |
| A19 | A required independent verifier is unavailable but a heuristic estimator looks favourable | Treating absence of verifier as optional after seeing the result | Mandatory-obligation gate fails; no claimed verified acceptance |
| A20 | Zero budget remains while the decision interval still straddles the constraint | Converting budget exhaustion into success | `INCONCLUSIVE` with exact remaining obligations and cost state |

### 9.1 Minimum adversarial acceptance criteria

Before implementation can be considered for approval, an offline reference harness should establish:

- zero false `ACCEPT` outcomes across all bounded-mode adversarial cases with valid reference data;
- zero conversion of heuristic indicators into probabilistic uncertainty;
- zero silent action/backend substitution;
- zero discarded failed-run cost;
- zero unsupported assurance claims when mandatory obligations are absent;
- all conflicts, inapplicability and out-of-domain conditions produce explicit non-acceptance states;
- results are deterministic for identical inputs, policy version and declared deterministic execution environment.

These are proposed test criteria, not results. A zero false-accept count on a finite test suite is not proof of zero real-world false-accept probability.

## 10. Prior art and novelty implications

### 10.1 Goal-oriented adaptive FEM already optimises computational effort

Becker, Gantner, Innerberger and Praetorius (2023) analyse a goal-oriented adaptive FEM method that steers both mesh refinement and iterative linear-solver work. Under stated assumptions for symmetric elliptic problems and linear goals, they prove convergence and optimal algebraic rates, including with respect to total computational cost. DSCA therefore cannot claim novelty for jointly choosing between solver work and mesh refinement, or for cost-aware QoI adaptivity in that problem class.

- Becker et al. (2023), *Goal-oriented adaptive finite element methods with optimal computational complexity*, **Numerische Mathematik**, 153, 111–140. https://doi.org/10.1007/s00211-022-01334-8
- Open text: https://pmc.ncbi.nlm.nih.gov/articles/PMC9829645/

### 10.2 Active learning already considers multiple simulation models and cost

Yang et al. (2024) propose an active-learning strategy for reliability-based design optimisation under multiple simulation models, including an activity function and differing model evaluation costs. DSCA cannot claim novelty merely for considering multiple fidelity levels, active sampling or differing computational cost.

- Yang et al. (2024), *An effective active learning strategy for reliability-based design optimization under multiple simulation models*, **Structural Safety**, 107, 102426. https://doi.org/10.1016/j.strusafe.2023.102426

### 10.3 Sequential allocation of simulation effort is established

The NIST publication on allocating information-gathering resources to improve selection decisions reviews sequential simulation-allocation approaches, including indifference-zone procedures, value-of-information procedures and optimal computing budget allocation. DSCA must compare against relevant simulation-budget allocation baselines rather than presenting “choose which design to simulate next” as new.

- NIST publication: *Allocating Attribute-Specific Information-Gathering Resources to Improve Selection Decisions*. https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=913907

### 10.4 Narrower, testable contribution hypothesis

A potentially distinct GDEC contribution—still unproven—is an **engineering assurance-constrained computation controller** that:

1. represents decision requirements and mandatory evidence obligations explicitly;
2. uses typed eligibility contracts to prevent an action from claiming to reduce an uncertainty channel it cannot address;
3. distinguishes mathematically bounded, calibrated probabilistic, heuristic and incomplete evidence without converting between them implicitly;
4. maintains evidence dependence and provenance as first-class state;
5. selects from solver, discretisation, uncertainty, fidelity and verification actions under hard multi-resource budgets;
6. returns explicit `ACCEPT`, `REJECT`, `INCONCLUSIVE` or `REFUSE` outcomes.

Even this combination may overlap with assurance cases, reliability-based design optimisation, Bayesian experimental design, multi-fidelity active learning, adaptive verification and safety-critical decision frameworks. A systematic literature and patent review remains necessary. No patentability, novelty or publication claim is established here.

## 11. Benchmark protocol and comparison baselines

Each benchmark must be run against, at minimum:

1. fixed global refinement / fixed solver tolerance;
2. conventional QoI goal-oriented adaptive FEM;
3. a tuned solver/mesh co-control baseline where applicable;
4. an established sampling or active-learning baseline for probabilistic reliability cases;
5. DSCA bounded policy;
6. DSCA probabilistic policy only when its probability model is calibrated and applicable.

Compare matched engineering decisions, acceptance criteria and assurance classes. Report:

- false acceptance, false rejection, inconclusive and refusal counts;
- decision agreement with a high-quality reference and the method used to establish that reference;
- total end-to-end cost, including estimator, verification, transfers, orchestration and failed runs;
- QoI errors and the stated evidence class;
- number and type of actions, DOFs, solver iterations and uncertainty samples;
- predicted versus actual action cost;
- mandatory-obligation completion;
- evidence conflicts, out-of-domain detections and calibration failures;
- policy overhead and action-selection regret relative to an offline oracle.

An “oracle” may use reference solutions or known benchmark truth for retrospective scoring only. It must not feed future information to the live DSCA controller.

## 12. Research kill criteria and next gate

The research direction should be stopped or materially narrowed if:

1. DSCA cannot achieve zero false accepts on the predeclared bounded-mode adversarial suite without merely refusing every case;
2. its cost advantage disappears when all computation and verification costs are counted;
3. conventional goal-oriented adaptivity plus existing action-selection methods match its outcomes and costs without the proposed assurance controller;
4. typed uncertainty/action eligibility cannot be made operational and auditable;
5. the controller's policy overhead exceeds the computation it saves;
6. its probabilistic path cannot demonstrate calibration and out-of-domain detection on held-out cases.

**Next research gate (not implementation authorisation):** define one deterministic pass/fail benchmark with a trustworthy QoI bound, specify its action contracts and resource vector, and hand-calculate the policy trace for normal, near-boundary, estimator-inapplicable and budget-exhausted variants. Only after those traces are independently reviewed should an implementation proposal be considered.

---

## Classification

- **RESEARCHED:** prior work on GOAFEM cost steering, active learning for multi-model reliability design, and simulation budget allocation identified.
- **SPECIFIED:** bounded minimax-regret gate, probabilistic EVSI gate, action eligibility contract, resource accounting, adversarial test catalogue.
- **NOT IMPLEMENTED:** no executable DSCA controller or benchmark harness.
- **NOT TESTED:** no numerical tests or adversarial runs executed.
- **NOT VERIFIED:** no independent mathematical verification or formal proof of policy correctness.
- **NOT APPROVED:** no production or implementation authorisation.
