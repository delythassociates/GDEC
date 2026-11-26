# DWAOP v0.2 — Integrated Refinement-Cover Pruning and Exhaustive Verification

**Research memo:** v0.2  
**Status:** RESEARCH PROTOTYPE — NOT A NUMERICAL CERTIFICATE, NOT FORMALLY PROVED, NOT APPROVED FOR PRODUCTION  
**Branch:** `research/dwaop-integrated-pruning-oracle`  
**Starting branch & commit:** `research/dwaop-outcome-refinement-cover` @ `c86e2b057e98c3b4046fc3473395cc6a0e77e0cb`  
**Prototypes:**
- [`research/prototypes/dwaop_integrated_planner.py`](prototypes/dwaop_integrated_planner.py)
- [`research/prototypes/dwaop_exhaustive_policy_oracle.py`](prototypes/dwaop_exhaustive_policy_oracle.py)
- [`research/prototypes/dwaop_outcome_refinement_oracle.py`](prototypes/dwaop_outcome_refinement_oracle.py) (v0.1 baseline, preserved unmodified)

---

## 1. Executive Result

DWAOP v0.2 integrates certificate-backed complete sibling refinement-cover pruning directly into an AND-OR contingent finite planner (`plan_policies`) and evaluates it against an independent brute-force exhaustive policy oracle (`enumerate_exact_pareto_frontier`).

1. **Exact Pareto Frontier Equivalence:** Across all **240** generated campaign fixtures (200 exhaustive 3-world partition pairs + 40 seeded 4- and 5-world graphs), **35** additional Strategy B seeded graphs, **17** hand-constructed adversarial counterexamples, and **4** multi-resource/failure integration benchmarks, the pruned planner, unpruned planner, and independent exhaustive oracle produced **identical** normalized complete-policy Pareto frontiers ($\mathcal{P}_{\text{pruned}} = \mathcal{P}_{\text{unpruned}} = \mathcal{P}_{\text{oracle}}$).
2. **Independent Formal Audit Catch & Fix:** Independent review (Agent C) identified a real soundness edge case in the initial draft of `is_local_refinement`: short-circuiting on `terminal_verdict == "REFUSE"` without checking enabled recovery actions in `coarse_state`, plus non-sticky `UNRECOVERABLE_REFUSAL` and `_TOL` slack in multi-step resource comparisons. All three were fixed, and two new regression tests (`test_c16_refuse_with_recovery_does_not_unsoundly_prune`, `test_c17_unrecoverable_refusal_is_sticky`) were added.
3. **Deliberate Mutation Campaign:** **14 / 14** targeted mutations (16 pytest cases) were killed (**0** survivors).
4. **Honest Search-Reduction Measurement:** Across the 240-fixture generated campaign, pruning reduced expanded states from **4,481** (unpruned) to **4,464** (pruned) with **17** successful prunes (**0.38%** state reduction). Because the 12 fail-closed conditions are strict and random small-depth graphs rarely exhibit exact single-cell coarse domination without differing capabilities/obligations, search reduction on small random graphs is modest.

---

## 2. Design and Semantics

### 2.1 Finite-World & Observation-Based Semantics
- **Universe:** $\Omega = \{\omega_1, \dots, \omega_n\}$ with reference per-world verdicts in `{"ACCEPT", "REJECT"}`.
- **Evidence State (`EvidenceState`):** Carries `specification_id`, `model_id`, `assurance_scope`, `worlds`, `open_obligations`, `capabilities`, `remaining_actions`, `remaining_retries`, `model_valid`, `evidence_stale`, `resource_spent`, `resident_memory_gb`, `parent_state_snapshot`, `last_action_id`, `last_outcome_label`, `last_outcome_kind`, and `provenance_depth`.
- **Deterministic Observable Partition:** Every action's `OutcomeCell`s partition `applicable_worlds` by `observable_label_by_world` ($\bigcup_i C_i = X_{\text{app}}$, $C_i \cap C_j = \varnothing$). `validate_oracle` rejects `allow_clairvoyant_world_branching=True`; policies branch strictly on observable `outcome_label`.

### 2.2 Explicit Result & Failure Semantics (`OutcomeKind`)
Ten explicit outcome kinds are modeled: `SUCCESS`, `INCONCLUSIVE`, `NUMERICAL_BREAKDOWN`, `TIMEOUT`, `RESOURCE_EXHAUSTION`, `BACKEND_FAILURE`, `MODEL_INVALIDATED`, `STALE_EVIDENCE`, `BOUNDED_RETRY`, and `UNRECOVERABLE_REFUSAL`.
- `MODEL_INVALIDATED`, `STALE_EVIDENCE`, and `UNRECOVERABLE_REFUSAL` are **sticky**: they permanently force `terminal_verdict == "REFUSE"` and halt further action expansion.
- Non-sticky failure/inconclusive outcomes (`INCONCLUSIVE`, `TIMEOUT`, `NUMERICAL_BREAKDOWN`, `RESOURCE_EXHAUSTION`, `BACKEND_FAILURE`) force `"REFUSE"` at the leaf if no recovery action is taken (never defaulting to `"ACCEPT"`), and may only reach `"ACCEPT"` if an enabled recovery action succeeds and discharges all obligations.
- `BOUNDED_RETRY` decrements `remaining_retries` by `max(1, retry_cost)` and disables the action when `remaining_retries == 0`.

### 2.3 Multi-Resource Algebra (`ResourceVector`)
Four separate dimensions are tracked without arbitrary exchange rates:
- Additive: `ru_upper`, `cpu_ticks`, `energy_ticks` (summed sequentially; component-wise `max` across mutually exclusive AND branches).
- Peak live memory: `peak_memory_gb` tracks $\max(\text{prior peak}, \text{resident} + \text{workspace} + \text{overlap}, \text{resident\_after})$, with explicit `released_memory_gb` and `retained_output_gb_upper`.
- `_nonnegative` rejects `bool`, `NaN`, `inf`, `-inf`, and negative values in all contracts, budgets, and vectors.

### 2.4 Twelve Fail-Closed Complete-Cover Pruning Conditions
`is_complete_refinement_cover` and `is_local_refinement` enforce:
1. Common canonical parent (`parent_state_snapshot`).
2. Identical `specification_id`, `model_id`, and `assurance_scope`.
3. Complete observable outcome set of the finer action.
4. Pairwise disjoint sibling world regions.
5. Exact union coverage ($\bigcup_i X(S_i^+) = X(S_-)$).
6. Checked parent/action/outcome provenance (`verify_state_provenance`).
7. Recursive local simulation $S_i^+ \preceq S_-$ over remaining horizon `depth_left - 1` (without short-circuiting non-sticky `REFUSE` when `coarse_state` has enabled recovery actions).
8. Compatible `semantic_key` and `failure_semantics`.
9. Monotonic obligations ($O_+ \subseteq O_-$) and capabilities ($K_- \subseteq K_+$).
10. Valid terminal predicates, `model_valid`, and `evidence_stale` compatibility.
11. Component-wise `ResourceVector` dominance with **zero tolerance** (`tol=0.0`) and `resident_memory_gb` dominance.
12. Budget-feasible complete continuations for every sibling child.

---

## 3. Generated Fixture Methodology & Exhaustive Oracle Results

- **Strategy A (Exhaustive 3-world):** 200 ordered pairs of deterministic 3-world observation partitions (`tests/research/test_dwaop_adversarial_graphs.py`, `DSCA_DWAOP_GENERATED_FIXTURE_RESULTS_v0.2.json`).
- **Strategy B (Deterministic seeded 4- and 5-world):** 40 campaign fixtures (25× 4-world, seeds 100–124; 15× 5-world, seeds 200–214) + 35 pytest-parametrized fixtures (20× 4-world, seeds 300–319; 15× 5-world, seeds 400–414) featuring mixed fan-out, reconvergence, failures, retries, model invalidation, and multi-resource trade-offs.
- **Strategy C (Adversarial counterexamples):** 17 hand-constructed tests (`test_c01`–`test_c17`) covering omitted outcomes, overlapping cells, empty/invalid worlds, duplicate siblings, incomplete covers, wrong provenance, hidden failures, stale certificates, forged obligation discharge, resource underestimation/`NaN`, incompatible failure contracts, coarse straddling, clairvoyant branching, horizon exhaustion, bounded-retry exhaustion, non-sticky `REFUSE`-with-recovery, and sticky `UNRECOVERABLE_REFUSAL`.
- **Oracle Comparison:** `plan_policies(..., prune=True)`, `plan_policies(..., prune=False)`, and `enumerate_exact_pareto_frontier` matched on **100% of fixtures (0 counterexamples)**.

---

## 4. Mutation Results (`tests/research/test_dwaop_mutations.py`)

**Targeted Mutation Score: 14 / 14 mutants killed (100.0%), 0 survivors** (executed via 16 pytest cases):
1. Remove one outcome (`ContractError`)
2. Merge incompatible outcome cells (`ContractError`)
3. Change successor world set (`verify_state_provenance == False`)
4. Alter certificate scope (`ContractError`)
5. Forge proof identifier (`ContractError`)
6. Understate additive costs (`ru_upper`, `cpu_ticks`, `energy_ticks` — 3 parametrized cases, `ContractError`)
7. Understate retained or peak memory (`ContractError`)
8. Omit failure branch (`ContractError`)
9. Bypass model invalidation (`ContractError` / refusal check)
10. Reverse containment comparison (rejected by cover check / oracle divergence)
11. Remove obligation precondition (`ContractError`)
12. Permit action reuse (caught by provenance / oracle divergence)
13. Corrupt retry limits (`ContractError`)
14. Allow clairvoyant world branching (`ContractError`)

*Scope disclosure:* Targeted mutation suite on DWAOP v0.2 contracts and planner; not whole-repository AST mutation.

---

## 5. Search Reduction Measurements

From [`DSCA_DWAOP_GENERATED_FIXTURE_RESULTS_v0.2.json`](DSCA_DWAOP_GENERATED_FIXTURE_RESULTS_v0.2.json) (240 fixtures):
- **Total states expanded (unpruned):** `4,481`
- **Total states expanded (pruned):** `4,464`
- **Total successful prunes:** `17`
- **Net state reduction ratio:** `0.38%` (`0.0038`)

**Honest assessment:** On shallow random 3–5 world graphs, complete sibling covers satisfying all 12 strict conditions occur infrequently (17 times across 240 graphs), so net search reduction is small. Larger savings require deeper multi-level contingent trees where a single coarse continuation has a large subtree below it.

---

## 6. Proposed Finite-Horizon Policy-Preservation Theorem & Unresolved Gaps

### Theorem (Proposed — Not Machine-Checked)
Under finite horizon $H \ge 0$, exact `<=` resource comparisons (`tol=0.0`), deterministic observable outcome partitions, monotonic state invariants (`open_obligations` shrinking, `capabilities` growing, `model_valid`/`evidence_stale`/`UNRECOVERABLE_REFUSAL` sticky), and complete sibling cover conditions (1–12, including full simulation of enabled recovery actions on non-sticky `REFUSE`),
$$\mathrm{pareto\_reduce}(\mathrm{plan\_policies}(\text{prune}=\text{True})) = \mathrm{pareto\_reduce}(\mathrm{plan\_policies}(\text{prune}=\text{False})).$$

### Proof Outline
By induction on remaining horizon $h \in \{0, \dots, H\}$, `is_local_refinement(s_f, s_c, h)` implies every complete policy tree $T_c$ from $s_c$ of depth $\le h$ is simulated by a complete policy tree $T_f$ from $s_f$ with at least as strong world verdicts ($V_f \succeq V_c$), component-wise $\le$ remaining/peak resources, and no greater depth when equal. Complete sibling coverage (1–12) partitions $X(S_-)$ across $\{S_i^+\}$ and supplies independent OR-branching per sibling, yielding a dominating or equivalent complete policy under `fine_contract`.

### Unresolved Gaps
1. **No machine-checked formal proof** (Lean/Coq/Isabelle verification has not been performed).
2. **Deterministic finite-world assumption:** Nondeterministic/stochastic observations and continuous parameter spaces are not modeled.
3. **Synthetic oracle certificates:** Certificates are validated against a finite trusted table, not a real PDE/FEM numerical enclosure checker.
4. **One-shot actions & finite retries:** General cyclic planning is out of scope.

---

## 7. Prior-Art Reassessment

DWAOP v0.2 combines five existing concepts: (1) simulation-based dominance pruning, (2) contingent/AND-OR planning, (3) belief/possible-world enclosures, (4) proof-carrying plans / assurance obligations, and (5) multi-resource Pareto search. While the engineering-specific combination (scoped model validity + non-exchangeable 4D resource bounds + complete sibling cover over observable partitions) is coherent for verification planning, **this research prototype and passing test suite do not establish algorithmic novelty or patentability** over prior simulation-dominance and contingent-planning literature.

---

## 8. Next Research Gate

Before connecting DWAOP to a numerical heat-conduction prototype:
1. Perform a lightweight formalization check (e.g., Lean/Z3/Alloy model of the transition & complete-cover lemma) on the finite-horizon theorem.
2. Benchmark deeper ($H \ge 6$) multi-level structured contingent planning trees to determine whether complete-cover pruning yields meaningful runtime savings once dominance-check overhead is accounted for.
3. Only then build a standalone numerical heat-conduction prototype with a genuinely guaranteed output-error enclosure (distinct from GDEC's empirical DWR indicator).

---

## 9. Status Summary

- **SPECIFIED:** Finite-world semantics, 10 `OutcomeKind`s, 4D `ResourceVector`, 12 complete-cover conditions, proposed finite-horizon theorem.
- **IMPLEMENTED:** `dwaop_integrated_planner.py`, `dwaop_exhaustive_policy_oracle.py`, adversarial & mutation suites.
- **EXECUTED & TESTED:** 74/74 v0.2 pytest cases + 26/26 v0.1 unittest cases + `py_compile`.
- **EXHAUSTIVELY CHECKED:** 200 3-world partition pairs + 40 campaign 4–5 world seeded graphs + 35 pytest seeded graphs + 17 adversarial counterexamples ($\mathcal{P}_{\text{pruned}} = \mathcal{P}_{\text{unpruned}} = \mathcal{P}_{\text{oracle}}$).
- **INDEPENDENTLY REVIEWED:** Agent C formal semantics audit (caught and resolved 3 edge cases).
- **NOT PROVEN:** Machine-checked formal proof; general cyclic/stochastic/continuous domains.
- **NOT NUMERICALLY VERIFIED / NOT APPROVED:** No PDE/FEM run; not approved for GDEC production integration.
