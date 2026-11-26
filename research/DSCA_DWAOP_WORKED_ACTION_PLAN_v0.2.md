# DWAOP v0.2 — Worked Contingent Action-Planning Example

**Status:** HAND-CONSTRUCTED PLANNING TRACE — NOT A NUMERICAL SOLVER RESULT  
**Algorithm:** Decision-Witness and Assurance-Obligation Planning (DWAOP)  
**Parent:** `research/DSCA_DWAOP_ALGORITHM_REDESIGN_v0.2.md`

---

## 1. Purpose

This example checks whether the v0.2 planner actually needs both:

1. a decision-resolving evidence action; and
2. a separate mandatory assurance action.

It is designed to distinguish contingent action planning from a greedy one-step uncertainty-reduction score.

The values and action contracts are synthetic. They are not measured GDEC results and do not describe the behaviour of an existing GDEC solver.

## 2. Decision state

The engineering requirement is:

\[
T_{\max}\leq T_{\mathrm{lim}},\qquad
T_{\mathrm{lim}}=300.10\;\mathrm K.
\]

The joint admissible set is a disconnected one-dimensional set:

\[
\mathcal Q_0=
[300.04,300.08]\;\mathrm K
\;\cup\;
[300.12,300.14]\;\mathrm K.
\]

The two components represent two admissible operating/material scenarios that have not yet been distinguished. This is an illustrative set representation only.

There are two decision-reversing regions:

- \(\mathcal Q_{\mathrm{pass}}=[300.04,300.08]\;\mathrm K\);
- \(\mathcal Q_{\mathrm{fail}}=[300.12,300.14]\;\mathrm K\).

Because \(\mathcal Q_0\) intersects both sides of the threshold, the decision is unresolved.

Mandatory obligation:

\[
\mathcal O_0=\{o_{\mathrm{independent\_check}}\}.
\]

The final interval and its provenance must be independently checked before either terminal decision can be issued.

## 3. Candidate action contracts

### Action A — resolve the operating/material scenario

`A_RESOLVE_SCENARIO`

- Preconditions: both scenarios and their admissible QoI ranges are explicitly represented; a validated discriminating calculation/measurement is available.
- Effect: partitions the current admissible set into one of two outcome cells.
- Outcome cover: exactly the two cells below; in this idealised example there are no action failures or unmodelled outcomes.
- It does **not** discharge the independent-check obligation.
- Upper resource cost:

\[
\mathbf c_A^\uparrow=(4.0\;\mathrm{min},\;0.8\;\mathrm{GB}).
\]

Possible outcomes:

\[
y_L:\quad \mathcal Q_1=[300.04,300.08]\;\mathrm K,
\]

\[
y_H:\quad \mathcal Q_1=[300.12,300.14]\;\mathrm K.
\]

The two outcome cells cover \(\mathcal Q_0\) exactly:

\[
\mathcal Q_0=\mathcal Q(y_L)\cup\mathcal Q(y_H).
\]

### Action B — independently check the decision certificate

`A_INDEPENDENT_CHECK`

- Preconditions: Action A has produced a branch-specific interval, input identity and evidence artefact.
- Effect: independently checks the interval derivation, configuration binding and provenance; discharges \(o_{\mathrm{independent\_check}}\) only on a valid `VERIFIED` result.
- Outcome: `VERIFIED` in this idealised example. A real checker must have explicit failure and inapplicability outcomes.
- Upper resource cost:

\[
\mathbf c_B^\uparrow=(1.0\;\mathrm{min},\;0.2\;\mathrm{GB}).
\]

The checker verifies a computational claim under the stated model. It does not validate the physical model against reality.

### Deliberately ineligible action

`A_SOLVE_TIGHTER` has no declared effect on the unresolved scenario identity or the missing independent-check obligation. It may reduce algebraic error if such error exists, but this example contains no such blocker. It is therefore ineligible as a decision-resolving action in the current state.

## 4. Resource budget

\[
\mathbf B=(6.0\;\mathrm{min},\;1.5\;\mathrm{GB}).
\]

The total upper-bound cost of the contingent plan is:

\[
\mathbf c_A^\uparrow+\mathbf c_B^\uparrow
=(5.0\;\mathrm{min},\;1.0\;\mathrm{GB})
\preceq
(6.0\;\mathrm{min},\;1.5\;\mathrm{GB}).
\]

The plan fits both resource dimensions. No scalar exchange rate between time and memory is required.

## 5. AND-OR plan

The first node is an OR choice: the planner selects Action A. Its outcomes form AND branches: both outcome cells must be handled.

~~~text
                         Initial state S0
                 Q0 spans pass and fail regions
                 O0 = {independent check open}
                              |
                       OR: choose action
                              |
                    A_RESOLVE_SCENARIO
                              |
                    AND: cover all outcomes
                      /               \
                   yL                   yH
                    |                    |
          Q1=[300.04,300.08]   Q1=[300.12,300.14]
             pass region             fail region
                    |                    |
             A_INDEPENDENT_CHECK  A_INDEPENDENT_CHECK
                    |                    |
                 VERIFIED             VERIFIED
                    |                    |
                  ACCEPT               REJECT
~~~

### Branch L — pass-side result

After (y_L):

\[
\sup \mathcal Q(y_L)=300.08\;\mathrm K
<300.10\;\mathrm K.
\]

The decision witness for violation is empty. The independent-check obligation is still open, so the state is **not yet terminal**.

After Action B returns `VERIFIED`, the obligation is satisfied and the terminal decision is:

`ACCEPT`, conditional on the declared model and evidence scope.

### Branch H — fail-side result

After (y_H):

\[
\inf \mathcal Q(y_H)=300.12\;\mathrm K
>300.10\;\mathrm K.
\]

The admissible set lies wholly on the violating side. The independent-check obligation is still open, so the state is **not yet terminal**.

After Action B returns `VERIFIED`, the terminal decision is:

`REJECT`, conditional on the declared model and evidence scope.

## 6. Why the action sequence matters

A one-step selector that only measures decision-set contraction could choose Action A and then stop as soon as the temperature interval lies on one side of the threshold. That would leave the mandatory independent-check obligation unsatisfied.

A selector that only prioritises mandatory obligations might run the checker before a branch-specific certificate exists; Action B is not eligible at the initial state.

DWAOP plans the dependency:

\[
A_{\mathrm{resolve\_scenario}}
\prec
A_{\mathrm{independent\_check}}.
\]

It recognises that both actions are required, and that the second action's precondition depends on the first action's output. The plan is contingent because the terminal decision differs by the first action's outcome.

This is the specific behaviour the prototype must compare against a greedy selector.

## 7. Budget-exhausted variant

Change only the resource budget:

\[
\mathbf B'=(4.5\;\mathrm{min},\;1.5\;\mathrm{GB}).
\]

Action A fits, but the complete plan does not:

\[
5.0\;\mathrm{min}>4.5\;\mathrm{min}.
\]

The planner must not execute Action A and then pretend that the decision is finished. Because the mandatory verifier cannot be budgeted after scenario resolution, there is no feasible complete plan.

Required result before execution:

`INCONCLUSIVE`

Reason: `NO_COMPLETE_ASSURANCE_PLAN_WITHIN_RESOURCE_BUDGET`.

The controller reports both blockers: the unresolved decision witness and the open independent-check obligation. It may provide the best available plan and its estimated shortfall, but must not claim acceptance.

## 8. Failure-outcome variant

Now add a possible `A_RESOLVE_SCENARIO` outcome `INCONSISTENT_EVIDENCE`, representing contradictory or invalid evidence.

This branch does not identify a pass or fail interval. It transitions the evidence state to `CONFLICTED`, preserves the artifacts, and cannot discharge the obligation.

The original plan is no longer a guaranteed decision-completing plan across all outcomes. The correct controller behaviour is:

- retain the successful branches as valid conditional paths;
- add an explicit conflict branch;
- replan only if a supported conflict-resolution action exists;
- otherwise terminate that branch as `INCONCLUSIVE` or `REFUSE`;
- never report a robust all-outcomes decision guarantee.

This demonstrates why the outcome cover must include failures and evidence conflicts when they are genuinely possible. The idealised two-outcome plan above is not permitted to omit a known failure mode.

## 9. What this example establishes

It demonstrates, by construction:

1. decision resolution and assurance completion are different state variables;
2. an action can resolve a decision witness without satisfying the verifier obligation;
3. another action can discharge an obligation but is ineligible until a prerequisite artifact exists;
4. an AND-OR plan captures the dependency and the branch-specific terminal verdict;
5. a resource vector can reject a plan even when its first action fits;
6. an adverse outcome invalidates a claimed all-branches guarantee.

It does **not** establish that this planner is more efficient than existing algorithms, that the proposed action contracts are implementable for real solvers, or that the combination is novel.

## 10. Classification

- **HAND-CONSTRUCTED:** state, action contracts, branch transitions and resource arithmetic.
- **NOT NUMERICALLY SIMULATED:** no FEM or CFD solver execution.
- **NOT IMPLEMENTED:** no DWAOP code or search engine.
- **NOT TESTED:** no automated comparison with greedy or adaptive baselines.
- **NOT INDEPENDENTLY REVIEWED:** no external reviewer has checked this planning trace.
- **NOT A GDEC CAPABILITY CLAIM:** the example is a research artefact only.
