# DWAOP v0.3 — H6/H8 Exhaustive-Oracle Verification & Closure Report

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/dwaop-horizon-six-formal-gate-v0.3`  
**Audited Baseline Commit:** `312dbf4c4439683257a0107ec6170d34ec465193` (CI Run [`45967617844`](https://github.com/delythassociates/GDEC/actions/runs/45967617844), 4/4 jobs succeeded)  
**Classification:** Research only. No production integration. No WP4 authorization.  

---

## 1. Executive Summary

This report presents an independent mathematical, algorithmic, adversarial, and CI verification of DWAOP v0.3 on `research/dwaop-horizon-six-formal-gate-v0.3`.

- **Frontier Equivalence:** For both **H6** (`horizon=6`, `64` worlds) and **H8** (`horizon=8`, `256` worlds), the pruned planner, unpruned planner, and independent exhaustive policy oracle produce **identical Pareto frontiers** under symmetric exact set equality (`left_only == 0`, `right_only == 0`, `left_size == right_size == 1`).
- **State Reduction vs. Runtime Trade-off:** Complete-cover pruning reduces expanded states by **92.11%** at H6 (`15` vs `190`) and **97.52%** at H8 (`19` vs `766`), **but total wall-clock runtime is 7.41× slower at H6 (`22.26s` vs `3.00s`) and 7.56× slower at H8 (`155.24s` vs `20.54s`)** because recursive `is_local_refinement` dominance checks consume >98% of pruned runtime.
- **Status Distinction:** DWAOP v0.3 is **IMPLEMENTED**, **EXECUTED**, **TESTED** (`94` passing tests locally after adversarial/mutation additions), and **ALGORITHMICALLY VERIFIED** on H6/H8 and finite adversarial suites; it is **NOT FORMALLY PROVED** in a machine-checked proof assistant.

**Recommendation:** **PASS WITH CONDITIONS** (exact frontier equivalence verified on H6/H8; runtime overhead of recursive dominance checking and unproved general-horizon optimality explicitly disclosed).

---

## 2. Exact Repository State & Commit Ancestry

- `39f2a7d3640c55dd50b922097654c8f2d8e3d050`: v0.2 baseline.
- `46b8b7cb0d4fa65906758a9271b0e82f62b1b7ee`: earlier full regression/oracle test evidence (failed in CI metrics step due to `ModuleNotFoundError: No module named 'research'`).
- `494b26646215e55b68be036397a5838a9271a8e8`: metrics-script `REPO_ROOT` `sys.path` fix (CI Run `45966924603`, `4/4` jobs succeeded).
- `312dbf4c4439683257a0107ec6170d34ec465193`: pre-audit HEAD (CI Run `45967617844`, `4/4` jobs succeeded).

---

## 3. Mathematical Definition & Audit Findings

- **Evidence State:** $S = (X, O, K, A, r, v, s, c, m, \text{provenance})$ in `dwaop_integrated_planner.py`.
- **Pareto Dominance (`_policy_dominates`):** Policy $P_1$ dominates $P_2$ iff for every world $w \in X$, $\text{verdict}_{P_1}(w) \preceq \text{verdict}_{P_2}(w)$ (`ACCEPT`/`REJECT` $\prec$ `REFUSE`), $c_1 \le c_2$ component-wise in exact `Fraction` arithmetic (`tol=0`), and either world-verdict maps differ or $c_1 < c_2$ strictly in at least one component.
- **Frontier Signature:** `(world_verdict_map, tuple(sorted(terminal_verdicts)), resource_vector.exact_key(), max_actions_on_path)`.
- **Audit Findings:**
  1. `is_complete_refinement_cover` requires `parent.worlds == coarse_state.worlds` (`dwaop_integrated_planner.py:1007`), so pruning is conservatively restricted to non-splitting coarse transitions.
  2. `_policy_dominates` does not compare `max_actions_on_path`, while `_canonical_dedup` keeps minimum `max_actions_on_path` only among policies with identical `(world_verdict_map, terminal_verdicts, resource_vector)`. In general graphs, if a fine continuation had identical `(world_verdict_map, resource_vector)` to a pruned coarse policy but a strictly larger `max_actions_on_path`, the frontier's `max_actions_on_path` field could differ; in H6/H8, fine actions have strictly smaller resource costs, so resource dominance holds strictly.
  3. `is_local_refinement` is finite-horizon-indexed (`depth_left`), so equivalence is bounded to the declared `max_horizon` and is not a general infinite-horizon theorem.

---

## 4. Oracle Independence Assessment

| Component | Shared vs. Independent | File / Symbol |
|---|---|---|
| Contract & Data Types | **Shared** | `ActionSemantics`, `WorldOracle`, `ResourceVector`, `ResourceBudget`, `NormalizedPolicy`, `OutcomeKind`, `validate_oracle` |
| Tree Enumeration | **Independent** | `dwaop_exhaustive_policy_oracle.py`: `_SimState`, `_enumerate_trees` |
| Transition & Eligibility | **Independent** | `_independent_enabled`, `_independent_terminal_verdict` |
| World-by-World Simulation & Budget | **Independent** | `_evaluate_tree_on_world` (`Fraction` accumulation) |
| Pareto Dominance & Reduction | **Independent** | `_oracle_verdict_no_worse`, `_oracle_dominates`, `_oracle_pareto_reduce` |

Verified by `test_exhaustive_oracle_does_not_call_planner_pareto_reducer` (monkeypatching `planner_module.pareto_reduce` to raise `AssertionError`).

---

## 5. Exact Resource Arithmetic Analysis

- `_nonnegative()` converts `int`, `float`, and `Fraction` via `Fraction(str(value))` (rejecting `bool`, `NaN`, `Inf`, and `< 0` with `ContractError`).
- `ResourceBudget.allows(..., tol=0.0)` and `ResourceVector.strictly_dominates(..., tol=0.0)` use exact `Fraction` comparisons with zero epsilon slack.
- `exact_key()` returns `(ru_upper, cpu_ticks, energy_ticks, peak_memory_gb)` as exact `Fraction` tuples (replacing v0.2's 12-decimal `rounded_key()`).
- Boundary tests verify exact accumulation (`0.1 * 10 == Fraction(1, 1)`), exact budget equality (`True`), `10^-50` rational excess (`False`), and strict dominance at `10^-400` scale.

---

## 6. H6 & H8 Benchmark Results and Symmetric Frontier Equality

Reproduced directly via `python research/prototypes/dwaop_horizon_ladder.py --stages 5 7 --output research/results/DWAOP_HORIZON_CAMPAIGN_v0.3.json`:

| Metric | H6 (`stages=5`, `horizon=6`, `64` worlds) | H8 (`stages=7`, `horizon=8`, `256` worlds) |
|---|---|---|
| Pruned `states_expanded` | `15` | `19` |
| Unpruned `states_expanded` | `190` | `766` |
| State reduction | `92.11%` | `97.52%` |
| Pruned `successful_prunes` / `dominance_checks` | `9` / `9` | `13` / `13` |
| Pruned `complete_policies_enumerated` | `15` | `19` |
| Unpruned `complete_policies_enumerated` | `236` | `956` |
| Frontier size (Pruned / Unpruned / Oracle) | `1` / `1` / `1` | `1` / `1` / `1` |
| Symmetric equality (all 6 directions) | **PASS (`true`)** | **PASS (`true`)** |
| Pruned runtime (`dominance_check_time_sec`) | `22.257s` (`21.858s`) | `155.244s` (`153.956s`) |
| Unpruned runtime | `3.005s` | `20.539s` |
| Runtime ratio (Pruned / Unpruned) | `7.41x` | `7.56x` |
| Peak memory (Pruned / Unpruned) | `155,928 B` / `151,336 B` | `436,788 B` / `425,400 B` |

---

## 7. Adversarial, Regression & Mutation Evidence

- **Baseline Suite at `312dbf4`:** `86 passed` in `1132.87s` (`0:18:52`) across `test_dwaop_integrated_pruning.py`, `test_dwaop_adversarial_graphs.py`, `test_dwaop_mutations.py`, and `test_dwaop_v03_horizon_ladder.py`.
- **Added Adversarial & Mutation Tests (`+8` tests):**
  - `test_adversarial_exact_arithmetic_budget_ties_and_horizon_cutoffs`: repeated fractional accumulation, `10^-50` budget excess, `ContractError` rejections, Pareto tie deduplication, empty budget frontier, and horizon cutoff (`H=2` empty vs `H=3` exact match).
  - `test_mutant_15`..`test_mutant_21` (`7` new targeted mutants in `test_dwaop_mutations.py`): dominance direction reversal, omitted `energy_ticks` dimension, permissive `ResourceBudget.allows`, missing `REJECT` terminal verdict, frontier identity omission in `_canonical_dedup`, dropped obligation discharge in `apply_action_outcome`, and off-by-one horizon cutoff.
  - **Targeted Mutation Result:** `23/23` targeted DWAOP mutation tests killed (`0` surviving; scoped to DWAOP prototype invariants, not whole-repository mutation coverage).

---

## 8. Explicit Limitations & Recommendation

- Finite deterministic observable-world semantics only; no cyclic, stochastic, continuous, or PDE/FEM execution.
- Proof sketch in `DSCA_DWAOP_FORMAL_HORIZON_GATE_v0.3.md` is **not** machine-checked.
- Recursive dominance checking currently incurs ~7.4×–7.6× wall-time overhead vs. unpruned search on H6/H8 despite >92% state reduction.
- **Recommendation:** **PASS WITH CONDITIONS** (exact frontier equivalence verified on H6/H8 and adversarial suites; wall-time overhead and proof-sketch-only status retained).
