# DWAOP v0.2 — Resource Algebra Sanity Check

**Status:** HAND-CHECKED SPECIFICATION EXAMPLE — NOT A GDEC BENCHMARK  
**Related algorithm:** \`research/DSCA_DWAOP_ALGORITHM_REDESIGN_v0.2.md\`  
**Purpose:** Check the resource aggregation rules used by contingent planning before any implementation.

---

## 1. The error this note is intended to prevent

A planner must not add every resource dimension across actions. CPU time and energy are usually cumulative. Peak memory is a maximum over simultaneously live allocations. Parallel elapsed time is a schedule property.

Using a sum for peak memory can make a feasible plan appear to exceed its memory limit. Using a sum for parallel wall time can make the predicted duration wrong. Using a maximum for cumulative CPU time can undercount work.

The first DWAOP prototype therefore uses sequential actions only and explicitly separates additive consumption from peak/live-set resources.

## 2. Sequential-path example

Assume an initial state with 0.50 GB resident memory. Three actions run sequentially:

| Action | CPU-time upper | Wall-time upper | Workspace upper | Temporary overlap upper | Retained output after action |
|---|---:|---:|---:|---:|---:|
| \(a_1\) | 2 s | 2 s | 2.00 GB | 0.20 GB | 0.40 GB |
| \(a_2\) | 3 s | 2 s | 1.50 GB | 0.30 GB | 0.20 GB |
| \(a_3\) | 4 s | 4 s | 3.00 GB | 0.10 GB | 0.10 GB |

The illustrative upper bounds assume retained outputs from previous actions remain resident. The workspace and overlap columns are additional to resident memory during that action.

### 2.1 Additive resources

CPU time:

\[
C_{\mathrm{CPU}}^\uparrow=2+3+4=9\ \mathrm{s}.
\]

Sequential wall time:

\[
C_{\mathrm{wall}}^\uparrow=2+2+4=8\ \mathrm{s}.
\]

These sums are valid because all actions execute sequentially and the costs are measured on compatible bases.

### 2.2 Peak memory

Start resident memory:

\[
M_0=0.50\ \mathrm{GB}.
\]

During action \(a_1\):

\[
M_1^\uparrow=0.50+2.00+0.20=2.70\ \mathrm{GB}.
\]

After \(a_1\), its retained output raises resident memory to:

\[
M_{1,\mathrm{resident}}=0.50+0.40=0.90\ \mathrm{GB}.
\]

During action \(a_2\):

\[
M_2^\uparrow=0.90+1.50+0.30=2.70\ \mathrm{GB}.
\]

After \(a_2\):

\[
M_{2,\mathrm{resident}}=0.90+0.20=1.10\ \mathrm{GB}.
\]

During action \(a_3\):

\[
M_3^\uparrow=1.10+3.00+0.10=4.20\ \mathrm{GB}.
\]

After \(a_3\):

\[
M_{3,\mathrm{resident}}=1.10+0.10=1.20\ \mathrm{GB}.
\]

The path peak is therefore:

\[
M_{\mathrm{peak}}^\uparrow
=\max(0.50,2.70,2.70,4.20,1.20)
=4.20\ \mathrm{GB}.
\]

It is **not** \(2.00+1.50+3.00=6.50\) GB. Nor is it just the largest workspace (3 GB), because retained objects and overlapping temporary outputs contribute to the live footprint.

This example assumes the stated memory categories do not overlap each other except as explicitly represented. A real backend must provide a sound live-set accounting model or use a more conservative bound.

## 3. Contingent-branch example

A root action \(a_0\) costs 2 CPU-seconds and has a 3 GB during-peak. It produces one of two mutually exclusive outcomes:

| Branch | Continuation CPU cost | Continuation peak memory |
|---|---:|---:|
| \(y_1\) | 2 s | 4 GB |
| \(y_2\) | 5 s | 2 GB |

For additive CPU time, the worst-case contingent policy cost is:

\[
C_{\mathrm{CPU}}^\uparrow
=2+\max(2,5)=7\ \mathrm{s}.
\]

For peak memory, the worst-case policy peak is:

\[
M_{\mathrm{peak}}^\uparrow
=\max(3,\max(4,2))=4\ \mathrm{GB}.
\]

The two branch continuations are not both executed in one run. Adding their CPU costs would give \(2+2+5=9\) s and would overstate the worst-case realised path cost. The same per-branch rule applies to the peak-memory high-water mark.

## 4. Why the flat blocker-cover LP is restricted

A blocker-cover LP that sums action lower costs is naturally defined over a single deterministic path. A contingent policy is a tree, and different branches can execute mutually exclusive actions.

If a flat LP treats branch-specific child blockers as though they are simultaneous obligations at the same state, it may force selection of actions from several mutually exclusive branches and sum their costs. That total may exceed the maximum cost of any realised branch. Such an LP objective is not automatically a lower bound on worst-case contingent cost.

DWAOP therefore:

- allows the blocker-cover LP only for a deterministic, non-branching path/subproblem where all selected actions execute on the same path;
- disables it for a branching contingent plan until a scenario-tree or max-path relaxation is derived and proved;
- retains blocker-distance lower bounds only when every complete branch must resolve the blocker, the relaxed graph includes every valid route, and all lower resource bounds are admissible.

For peak memory, even on a deterministic path, summing per-action memory lower bounds is invalid. The proposed peak-memory lower bound is a minimum-bottleneck path over unavoidable per-action live-memory lower bounds, and is disabled when live-set semantics cannot be justified.

## 5. Required independent checks

Before prototype implementation, an offline resource-algebra harness should verify:

1. additive path accumulation against explicit action sums;
2. peak-memory path calculation against enumerated live allocations and release events;
3. branch aggregation against exhaustive enumeration of all outcome paths;
4. budget feasibility against the exact path-specific aggregation;
5. blocker-distance pruning never removes a plan that fits the budget in exhaustive small graphs;
6. LP pruning is disabled whenever the policy branches;
7. no memory lower bound is summed across sequential actions;
8. unsupported parallel schedules are rejected, not approximated.

For finite graphs, the pruned and unpruned search results must agree on the feasibility and Pareto frontier. This test is stronger than checking only that the returned plan itself fits the budget.

## 6. Classification

- **HAND-CALCULATED:** additive totals, live-set memory peaks and branch maxima.
- **SPECIFICATION CHECK:** the examples exercise the intended resource aggregation operators.
- **NOT IMPLEMENTED:** no resource ledger, planner or backend memory tracker exists yet.
- **NOT EXECUTED:** no automated finite-graph oracle comparison was run.
- **NOT INDEPENDENTLY VERIFIED:** no second implementation/reviewer checked the resource model.
- **NOT A PERFORMANCE CLAIM:** all values are illustrative.
