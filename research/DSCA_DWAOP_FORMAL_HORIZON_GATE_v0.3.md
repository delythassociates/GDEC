# DWAOP v0.3 — Finite-Horizon Formal and Deep-Tree Gate

Status: RESEARCH PROTOTYPE — FORMAL PROOF NOT MACHINE-CHECKED — NOT A NUMERICAL CERTIFICATE.
Branch: research/dwaop-horizon-six-formal-gate-v0.3
Base: 402592a8af185706dbe8af3981838f3c065419c8

## 1. v0.3 changes

The v0.2 planner and exhaustive policy simulator are carried forward as isolated research code. Proof-relevant hardening changes:

1. Hard resource-budget comparisons use exact comparisons by default; the previous 1e-12 slack could admit a value slightly above a declared hard budget.
2. Proof-relevant state identity and Pareto deduplication use exact stored resource tuples rather than a 12-decimal rounded key.
3. The exhaustive oracle has its own Pareto dominance and reduction implementation. The previous oracle imported the planner's pareto_reduce, causing a common-mode error in final frontier comparison.

The oracle still shares typed contract/data classes and finite-oracle validation with the planner. It independently enumerates contingent trees, simulates policies world-by-world, accumulates resources, and computes its own Pareto frontier. This is stronger independence, not total independence.

## 2. Finite-horizon simulation relation

Let an evidence state be S=(X,O,K,A,r,v,s,c,m), where X is possible worlds, O open obligations, K capabilities, A remaining actions, r retry budget, v model validity, s evidence staleness, c accumulated resource vector, and m resident memory.

Define S_f <= S_c when:
- specification, model and assurance scope are equal;
- X_f is a subset of X_c;
- O_f is a subset of O_c;
- K_c is a subset of K_f;
- r_f >= r_c;
- model validity and evidence freshness are no worse in the fine state;
- each exact resource component in c_f is no greater than c_c, and resident memory is no greater;
- terminal verdicts are preserved or improved.

For each action enabled in S_c, local simulation requires a matching action in S_f with compatible semantics, preconditions and failure handling, and no greater resource upper bounds. Every fine outcome must map to exactly one coarse outcome containing its world subset; successor states must again satisfy the relation.

## 3. Proposed finite-horizon policy-preservation theorem

Assume a finite deterministic observable-world universe, finite action set, horizon H, exhaustive non-overlapping outcome partitions, exact resource comparisons, sound provenance, monotone obligation/capability and validity invariants, and the local-simulation condition for every pruned complete sibling cover.

Then each complete policy removed by complete-cover pruning has a retained complete policy with no worse per-world terminal verdicts and component-wise no-greater worst-case resource vector. Therefore complete-cover pruning preserves the finite-horizon Pareto frontier.

### Induction outline

Base h=0: only terminal policies are complete. Terminal-preservation plus resource dominance gives a no-worse retained leaf.

Step h>0: take a complete coarse policy with root action a_c. By local simulation choose a matching fine action a_f. Each fine outcome maps to exactly one coarse outcome with containing worlds. By the induction hypothesis, replace each mapped coarse child continuation with a no-worse fine continuation. The fine outcomes are exhaustive and disjoint, so the continuations combine into a complete contingent policy. Exact component-wise resource dominance and branch aggregation preserve the resource bound.

Pareto consequence: every removed coarse policy is dominated or matched by a retained policy, so pruning cannot remove a Pareto-optimal policy.

This is a proof sketch, not a machine-checked theorem. The implementation and tests do not prove local simulation for all possible oracles or all finite horizons. The theorem depends on the resource algebra, failure semantics and relation being correctly implemented.

## 4. H6/H8 benchmark design

A structured refinement ladder begins with one fine observation that splits possible worlds into two groups and a coarse observation that merges them. Later stages are one-cell continuations. Each stage has a fine/coarse action pair with the same semantic key and compatible preconditions; the fine action has no greater resource claims. A final observable action emits ACCEPT/REJECT leaves.

The executable compares pruned planner, unpruned planner, and world-by-world exhaustive contingent-policy enumeration using an independent Pareto reducer. It reports expanded states, actions, complete policies, dominance checks, successful and rejected prunes, dominance-check time, total runtime, peak memory and frontier size.

Fewer states alone are insufficient: the dominance-check cost and total wall time must be compared too.

## 5. Execution and acceptance

A branch-specific workflow runs the existing v0.2 regression, adversarial and mutation suites plus the H6/H8 gate on Python 3.10–3.13. It then generates a machine-readable benchmark artifact.

Do not mark the gate PASS until the workflow run is successful on the exact branch HEAD. If pruning does not reduce states, frontiers diverge, or runtime cost outweighs the benefit, preserve and report that result.

## 6. Scope limits

- Finite deterministic possible-world semantics only.
- No cyclic or stochastic policies.
- No continuous world sets or interval quantifiers.
- No PDE/FEM execution or numerical certificate.
- No formal proof assistant run in this patch.
- No production integration, main changes, or WP2/WP3 modifications.
- DWAOP novelty remains unestablished.
