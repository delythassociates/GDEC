# DWAOP Hydrogen Stage 1 — Exhaustive Oracle & Pareto Reducer Audit

**Repository:** `f:/gdec-dwaop-v03`  
**Audited Commit:** `2812b000ea0241a3aee2b5580444a7e1767c3417`  
**Python Environment:** `f:/fem-edit-benchmark/.venv/Scripts/python.exe` (`Python 3.13.14`)  
**Scope:** Read-only code audit and bounded exhaustive generation (no code or test modifications).

---

## 1. Executive Summary

This report audits `_policy_dominates`, `_canonical_dedup`, and `pareto_reduce` in [dwaop_integrated_planner.py](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py) alongside `_oracle_dominates` and `_oracle_pareto_reduce` in [dwaop_exhaustive_policy_oracle.py](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py), and compares four evaluators across **972** bounded exhaustive and targeted deterministic action graphs (including **573** multi-entry Pareto frontier instances with `> 1` policy):

1. **Pruned planner:** `plan_policies(..., prune=True)`
2. **Unpruned planner:** `plan_policies(..., prune=False)`
3. **Exhaustive oracle:** `enumerate_exact_pareto_frontier(...)`
4. **Explicit independent reference frontier:** from-scratch brute-force tree enumerator, world simulator, and Pareto reducer (evaluated both under the implemented tie-break specification and under an alternative 5-objective specification treating `max_actions_on_path` as a Pareto objective).

### Key Findings

- **Syntactic Independence, Semantic Identity of the Reducers:** `_oracle_dominates` and `_oracle_pareto_reduce` do not call the planner's reducer, but they encode the **exact same mathematical dominance and tie-breaking specification** as `_policy_dominates`, `_canonical_dedup`, and `pareto_reduce` (`0` mismatches across `8,100` pairwise dominance checks and `50` randomized subset/permutation trials).
- **Answer to Q6:** The exhaustive oracle **reproduces the same potentially incomplete objective specification** regarding `max_actions_on_path` (omitting path length from Pareto dominance and tie-breaking exact `(world_verdict_map, resource_vector)` ties by minimum `max_actions_on_path`). If `max_actions_on_path` were intended as a primary Pareto objective, the oracle would fail to catch that omission (`134 / 972` graphs across C1–C7 differ when `max_actions_on_path` is a 5th Pareto objective). **However**, under the implemented specification itself, the oracle is **not** a vacuous tautology: because `enumerate_exact_pareto_frontier` enumerates all trees and reduces **only at the root** (`972 / 972` match with the independent explicit reference frontier, `0` divergences), it exposes **three distinct planner failure modes** relative to the implemented spec:
  1. **Internal `pareto_reduce` Bellman Violation (`pruned == unpruned != oracle`, `8 / 244` in C4 and `12 / 32` in C7):** Calling `pareto_reduce` at internal OR-nodes in `_search` drops a slightly costlier, shorter-path sub-policy whose extra resource cost is masked at a parent AND-node by a heavier sibling via `ResourceVector.max_across`. Both `pruned` and `unpruned` return `max_actions_on_path = 3`, while `oracle` and `ref` return `max_actions_on_path = 2`.
  2. **`SUCCESS`-Only Pruning + Bellman Interaction (`pruned != unpruned == oracle`, `12 / 32` in C7):** When `fine_split` prunes `coarse_step` via `is_complete_refinement_cover` and internal `pareto_reduce` drops the fine child's short-path witness while `coarse_step` (which cannot take the fine-only 2-step sub-branch) would have preserved it, `pruned` returns `max_actions_on_path = 3` while `unpruned`, `oracle`, and `ref` return `max_actions_on_path = 2`.
  3. **Sticky-Refusal Pruning Soundness Bug (`pruned != unpruned == oracle`, `1 / 120` in C6):** In `c6_106_unrec_unrec_c_to_c1_rec_all`, `is_local_refinement` allows a sticky `UNRECOVERABLE_REFUSAL` fine state to spuriously simulate a recoverable `TIMEOUT` coarse state because `_enabled` does not block transitions out of `UNRECOVERABLE_REFUSAL`. `pruned` drops the `(('w0', 'ACCEPT'), ('w1', 'REJECT'))` frontier entry that `unpruned`, `oracle`, and `ref` all preserve.
- **Standalone Oracle Evaluator Defect:** Direct testing confirms `_evaluate_tree_on_world` ([dwaop_exhaustive_policy_oracle.py#L204-L270](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py#L204-L270)) shares the sticky-refusal eligibility gap: because `last_kind = kind` (`line 255`) overwrites `last_kind` on subsequent actions without checking `last_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`, calling `_evaluate_tree_on_world` standalone on a synthetic `UNRECOVERABLE_REFUSAL -> recover -> ACCEPT` tree falsely validates it (`('ACCEPT', ResourceVector(2, 2, 0, 0), 2)`). `enumerate_exact_pareto_frontier` avoids this in campaign runs only because `_enumerate_trees` (`lines 114–119`) stops expanding at sticky refusals.

---

## 2. Static & Unit Audit of the Five Target Functions

| Symbol | Location | Role in Implemented Spec | Key Observations & Edge Cases |
|---|---|---|---|
| `_policy_dominates` | [dwaop_integrated_planner.py#L1087-L1098](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1087-L1098) | Strict partial order on `(world_verdict_map, resource_vector)` | Uses `_verdict_no_worse` (`ACCEPT`, `REJECT` $\prec$ `REFUSE`; `ACCEPT` $\parallel$ `REJECT`) and exact `Fraction` 4-tuple comparison (`tol=0.0`). Ignores `max_actions_on_path` and `terminal_verdicts`. Compares `world_verdict_map` positionally via `zip()`; misaligned/unsorted maps return `False`. |
| `_canonical_dedup` | [dwaop_integrated_planner.py#L1101-L1121](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1101-L1121) | Tie-breaking deduplication & canonical sort | Groups by `(p.world_verdict_map, p.terminal_verdicts, p.resource_vector.exact_key())`, keeping minimum `p.max_actions_on_path`. Including `terminal_verdicts` in the key is redundant for valid policies (`frozenset(v for _, v in world_verdict_map)`), but retains malformed synthetic duplicates if `terminal_verdicts` differs. |
| `pareto_reduce` | [dwaop_integrated_planner.py#L1124-L1134](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1124-L1134) | Dedup + non-dominated filter | Calls `_canonical_dedup(policies)` then filters with `_policy_dominates`. Safe as a root filter on flat sets, **unsafe at internal OR-nodes** (`lines 1236, 1338`) because `max`-aggregation across AND-siblings breaks monotonicity of the `(V, R) + min L` lexicographic order. |
| `_oracle_dominates` | [dwaop_exhaustive_policy_oracle.py#L286-L296](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py#L286-L296) | Independent dominance predicate | Uses `_oracle_verdict_no_worse` and `_oracle_resource_tuple` (exact `Fraction` 4-tuple). Mathematically identical to `_policy_dominates` on all valid `NormalizedPolicy` inputs. |
| `_oracle_pareto_reduce` | [dwaop_exhaustive_policy_oracle.py#L299-L311](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py#L299-L311) | Independent dedup + filter + sort | Uses exact same dedup key `(world_verdict_map, terminal_verdicts, _oracle_resource_tuple)`, min `max_actions_on_path` tie-breaker, and sort key as `_canonical_dedup` + `pareto_reduce`. Called **only once at the root** (`line 366`). |

### Direct Unit Verification (`audit_five_functions()`)

Executed via `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/audit_exhaustive.py`:

- **Pairwise dominance grid:** `8,100` `(left, right)` pairs over `{"ACCEPT", "REJECT", "REFUSE"}^2` × `5` resource vectors × `2` path lengths -> **`0` mismatches** between `_policy_dominates` and `_oracle_dominates`.
- **Order axioms:** Irreflexive (`True`), asymmetric (`True`), and transitive (`True` on tested `60^3` triples).
- **Random subset & shuffle invariance (`50` trials, `25` policies each):** `pareto_reduce == _oracle_pareto_reduce == ref_pareto_frontier` on **`50 / 50`** trials, invariant under list permutation (`0` mismatches).
- **Boundary & tie-break checks:**
  - Equal `(world_verdict_map, resource_vector)` with `max_actions_on_path` in `{4, 1}` -> both `pareto_reduce` and `_oracle_pareto_reduce` retain only `max_actions_on_path = 1`.
  - Cheaper longer (`ru=1, L=5`) vs costlier shorter (`ru=2, L=1`) -> `_policy_dominates` and `_oracle_dominates` both return `True`, dropping `L=1` (`1`-entry frontier; vs `2`-entry frontier if `max_actions_on_path` were a Pareto objective).
  - Unsorted `world_verdict_map`: `(("w0","ACCEPT"),("w1","REJECT"))` vs `(("w1","REJECT"),("w0","ACCEPT"))` -> both predicates return `False`.
  - Manually malformed `terminal_verdicts` (`{"ACCEPT"}` vs `{"BOGUS"}`) with identical `(world_verdict_map, resource_vector)` -> both reducers keep `2` entries.

---

## 3. Bounded Exhaustive Generation & 4-Way Comparison

All experiments were executed from scratch scripts under `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/` comparing:
`(1) plan_policies(prune=True)` vs `(2) plan_policies(prune=False)` vs `(3) enumerate_exact_pareto_frontier` vs `(4) explicit_reference_frontier`.

### Summary Across All 7 Campaigns (`972` Graphs)

| Campaign | Graphs | Multi-Entry (`>1`) | Max Frontier Size | Graphs w/ Prunes (Total Prunes) | `oracle == ref` | `pruned == unpruned` | `unpruned == oracle` | `pruned == oracle` | Diff if `L` is Pareto Obj (`ref_depth`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C1: 2-world exhaustive (`H=3`) | 320 | — | — | — | 320/320 | 320/320 | 320/320 | 320/320 | — |
| C2: 3-world 5×5 partitions × 5 trade-offs (`H=3`) | 250 | — | — | — | 250/250 | 250/250 | 250/250 | 250/250 | — |
| C3: Targeted multi-branch / 4D `Fraction` / retry | 6 | 4/6 | 5 | 2 (3) | 6/6 | 6/6 | 6/6 | 6/6 | 0/6 |
| **Subtotal C1–C3** | **576** | **342/576** | **5** | **51 (78)** | **576/576** | **576/576** | **576/576** | **576/576** | **64/576** |
| C4–C5: 2-world variable-depth (`H=4`) + 3-world DAGs (`H=3`) | 244 | 183/244 | 5 | 0 (0) | 244/244 | 244/244 | **236/244** | **236/244** | 62/244 |
| C6: 2-world active pruning × `OutcomeKind` × recovery (`H=4`) | 120 | 48/120 | >1 | 24 (24) | 120/120 | **119/120** | 120/120 | **119/120** | 0/120 |
| C7: 2-world `SUCCESS`-only active pruning × `max`-masking (`H=4`) | 32 | 0/32 | 1 | 16 (16) | 32/32 | **20/32** | **20/32** | **8/32** | 8/32 |
| **Total C1–C7** | **972** | **573/972** | **5** | **91 (118)** | **972/972** | **959/972** | **952/972** | **939/972** | **134/972** |

*(C1–C3 frontier size histogram across the 576 graphs: `{0: 10, 1: 224, 2: 263, 3: 28, 4: 50, 5: 1}`.)*

### Observed Divergences (Exact Examples)

#### A. Bellman-Optimality Violation Under Sibling `max`-Masking (`8 / 244` in C4, `12 / 32` in C7)

In `c4_0_split_success_heavy_mask_coarse=False` and `c4_1_split_success_heavy_mask_coarse=True` (`H=4`, `w0 -> ACCEPT`, `w1 -> ACCEPT/REJECT`):
- `root_split` (cost `ru=1, cpu=1`) splits `w0` and `w1`.
- Under `w0`: `w0_fast` reaches `ACCEPT` in **1 step** at `(3, 1, 0, 0)`, while `w0_s1 -> w0_s2` reaches `ACCEPT` in **2 steps** at `(1, 1, 0, 0)`.
- Under `w1`: `w1_act` reaches `ACCEPT`/`REJECT` in **1 step** at `(10, 10, 0, 0)`.
- **What happens:** At the `w0` child state, `plan_policies` calls `pareto_reduce`, so `(1, 1, 0, 0), L=2` strictly dominates and **deletes** `(3, 1, 0, 0), L=1`. At the root, `w1_act`'s `(10, 10, 0, 0)` masks both `w0` costs under `ResourceVector.max_across`, yielding `(11, 11, 0, 0)` for both trees—but the deleted tree had `max_actions_on_path = 2`, whereas the surviving tree has `max_actions_on_path = 3`.
- **4-Way Output on `c4_1_split_success_heavy_mask_coarse=True` (3-entry frontier):**
  - `pruned` & `unpruned`: `(('w0','ACCEPT'),('w1','ACCEPT'))` with `(11, 11, 0, 0)` and **`max_actions_on_path = 3`** (plus `(ACCEPT, REFUSE)` at `(3,3,0,0), L=3` and `(REFUSE, REFUSE)` at `(2,2,0,0), L=1`).
  - `oracle` & `ref`: `(('w0','ACCEPT'),('w1','ACCEPT'))` with `(11, 11, 0, 0)` and **`max_actions_on_path = 2`** (plus the same `(ACCEPT, REFUSE)` and `(REFUSE, REFUSE)` entries).

#### B. `SUCCESS`-Only Active Pruning + Bellman Interaction (`12 / 32` in C7: `pruned != unpruned == oracle == ref`)

In `c7_0_cc1_bf3_s1_1_w1_5_ACCEPT` and `c7_1_cc1_bf3_s1_1_w1_5_REJECT` (`H=4`, `SUCCESS`-only actions):
- `fine_split` (`semantic_key="op"`, cost `(1, 1)`) splits `w0` and `w1`; `coarse_step` (`semantic_key="op"`, cost `(1, 1)`) keeps `{w0, w1}` merged.
- Under `w0` after `fine_split`, `w0_s1 -> w0_s2` (`(1, 1), L=2`) strictly dominates `both_fast` (`(3, 3), L=1`), so internal `pareto_reduce` drops `both_fast` on `w0`, and `w1_heavy` (`(5, 5), L=1`) masks `w0`'s cost, leaving `fine_split` with `(4, 4)`... wait: under `c7_0`, `fine_split (1,1) + max(w0_s1(1,1), both_fast_or_w1(3,3) -> (3,3))` gives `(4, 4)` with `L=3` (since `both_fast` can run on `w1` at `(3,3)`, masking `w0_s1`'s `(1,1)`!). Meanwhile `coarse_step (1,1)` keeps `{w0,w1}` merged so `w0_s1` is not enabled, forcing `both_fast` (`(3,3), L=1`) and giving `(4, 4)` with `L=2`.
- When `prune=True`, `is_complete_refinement_cover` prunes `coarse_step` (`prunes = 1`), so `pruned` loses the `L=2` witness that `unpruned`, `oracle`, and `ref` retain:
  - `pruned`: `(4, 4, 0, 0)`, **`max_actions_on_path = 3`**.
  - `unpruned`, `oracle`, `ref`: `(4, 4, 0, 0)`, **`max_actions_on_path = 2`**.

#### C. Sticky-Refusal Pruning Soundness Defect (`1 / 120` in C6: `pruned != unpruned == oracle == ref`)

In `c6_106_unrec_unrec_c_to_c1_rec_all` (`H=4`, `w0 -> ACCEPT`, `w1 -> REJECT`):
- `fine_act` (`semantic_key="op"`, cost `(1, 1)`) maps both `w0` and `w1` to `OutcomeKind.UNRECOVERABLE_REFUSAL` (gaining `c_done`).
- `coarse_act` (`semantic_key="op"`, cost `(1, 1)`) maps `{w0, w1}` to `OutcomeKind.TIMEOUT` (also gaining `c_done`).
- `rec_all` (cost `(2, 2)`, requires `c_done`) resolves both worlds to `ACCEPT`/`REJECT`.
- **What happens:** `is_local_refinement` ([dwaop_integrated_planner.py#L863-L886](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L863-L886)) sees `coarse_term == "REFUSE"` with `coarse_sticky == False`, checks whether `fine_state` can simulate `rec_all`, and calls `_enabled(fine_state, rec_all, oracle)` ([lines 642–664](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L642-L664))—which does **not** reject `UNRECOVERABLE_REFUSAL` (only `_search` lines 1227–1232 halts expansion). Thus `pruned` falsely prunes `coarse_act` (`successful_prunes = 1`).
- **4-Way Output on `c6_106_unrec_unrec_c_to_c1_rec_all`:**
  - `pruned`: **1 entry** — `(('w0','REFUSE'),('w1','REFUSE'))` at `(1, 1, 0, 0), L=1`.
  - `unpruned`, `oracle`, `ref`: **2 entries** — `(('w0','ACCEPT'),('w1','REJECT'))` at `(3, 3, 0, 0), L=2` **and** `(('w0','REFUSE'),('w1','REFUSE'))` at `(1, 1, 0, 0), L=1`.

---

## 4. Rigorous Answer to Q6

> **Q6.** Is the exhaustive oracle independently checking the same mathematical objective, or reproducing the same potentially incomplete objective definition?

1. **Common-mode objective definition (reproducing the same choice on `max_actions_on_path`):**  
   While `dwaop_exhaustive_policy_oracle.py` is syntactically independent of `pareto_reduce`, `_oracle_dominates` and `_oracle_pareto_reduce` encode the **identical mathematical specification** as `_policy_dominates` and `_canonical_dedup`:
   - Dominance checks only `(world_verdict_map, resource_vector)` in exact `Fraction` arithmetic.
   - `max_actions_on_path` is excluded from Pareto dominance and used solely as a minimum tie-breaker when `(world_verdict_map, terminal_verdicts, resource_vector)` are identical.
   - Consequently, if the intended specification treats `max_actions_on_path` as a 5th minimization objective (so a shorter-path, higher-resource policy is not dominated by a longer-path, lower-resource policy), **the exhaustive oracle does not detect that gap**—it reproduces the exact same omission (`134 / 972` graphs across C1–C7 differ under `ref_depth`, and `T1`/`C4`/`C7` show multi-entry vs single-entry sensitivity).
   - Both reducers also share the same minor quirk of including `terminal_verdicts` in the deduplication key while ignoring it in dominance.

2. **Genuine algorithmic independence at the search/reduction boundary:**  
   Under the implemented specification `(V, R) + min-L tie-break`, the exhaustive oracle **is** genuinely checking the planner independently rather than merely echoing planner behavior:
   - Across all `972` graphs, `enumerate_exact_pareto_frontier` agreed `972 / 972` with our independent from-scratch `explicit_reference_frontier`.
   - Because the oracle applies `_oracle_pareto_reduce` **only once at the root** over all enumerated trees, it caught **all three** planner failure modes under the implemented specification itself: the internal `pareto_reduce` Bellman violation (`8 / 244` in C4, `12 / 32` in C7), the `SUCCESS`-only pruning + Bellman interaction (`12 / 32` in C7), and the `UNRECOVERABLE_REFUSAL` vs `TIMEOUT` pruning soundness bug (`c6_106` in C6).
   - **Shared transition-eligibility gap:** Neither `_enabled` (planner) nor `_independent_enabled` / `_evaluate_tree_on_world` (oracle) rejects actions after sticky refusal states (`not model_valid`, `evidence_stale`, `UNRECOVERABLE_REFUSAL`). While `_enumerate_trees` (`lines 114–119`) and `_search` (`lines 1227–1232`) enforce stickiness during search, standalone `_evaluate_tree_on_world` (`lines 204–270`) falsely accepts an `UNRECOVERABLE_REFUSAL -> recover -> ACCEPT` tree because `last_kind` is overwritten on subsequent transitions.

---

## 5. Reproducibility

Scratch verification scripts (outside `f:/gdec-dwaop-v03`, zero repo code/test changes):
- `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/audit_exhaustive.py` (`88.316s`, exit `0`: 5-function audit + C1–C3, `576` graphs)
- `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/audit_exhaustive_deep.py` (`63.61s`, exit `0`: C4–C5, `244` graphs)
- `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/audit_exhaustive_prune_bugs.py` (`11.15s`, exit `0`: C6, `120` graphs)
- `C:/Users/Nevan/.gemini/antigravity/brain/7e75f540-602e-43b9-bf26-7524c7caee9a/scratch/audit_exhaustive_c7.py` (`20.24s`, exit `0`: standalone `_evaluate_tree_on_world` check + C7 `32` graphs + C6 `ref_depth` verification)
