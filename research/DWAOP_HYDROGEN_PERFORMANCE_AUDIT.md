# DWAOP v0.3 — Performance & Algorithmic Complexity Audit (`DWAOP_HYDROGEN_PERFORMANCE_AUDIT`)

**Repository:** `f:/gdec-dwaop-v03`  
**Audited Commit:** `2812b000ea0241a3aee2b5580444a7e1767c3417`  
**Python Runtime:** `f:/fem-edit-benchmark/.venv/Scripts/python.exe` (Python `3.13.14`)  
**Scope:** Read-only code and performance audit of [`is_local_refinement`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L826-L930), [`is_complete_refinement_cover`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L983-L1079), and the [`plan_policies`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1161-L1362) pruning loop in [`dwaop_integrated_planner.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py). No code or test files were modified.

---

## 1. Executive Summary

On the structured refinement ladder ([`dwaop_horizon_ladder.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_horizon_ladder.py)), complete-cover pruning reduces `states_expanded` by **92.11%** at **H6** (`15` vs `190`) and **97.52%** at **H8** (`19` vs `766`), yet increases wall-clock runtime by **7.41×** at H6 (`22.257s` vs `3.005s`) and **7.56×** at H8 (`155.244s` vs `20.539s`), with `dominance_check_time_sec` accounting for **98.2%** (`21.858s`) and **99.2%** (`153.956s`) of pruned runtime ([`DWAOP_HORIZON_CAMPAIGN_v0.3.json`](file:///f:/gdec-dwaop-v03/research/results/DWAOP_HORIZON_CAMPAIGN_v0.3.json)).

Empirical instrumentation and `cProfile` measurements across H3–H8 establish **four compounding causes**:

1. **Exponential simulation branching inside `is_local_refinement` on the refinement ladder ($2^{S+3}-2S-8$ calls):** At every stage $i \ge 1$, both `fine_stage_i` and `coarse_stage_i` remain enabled in `coarse_state`. `is_local_refinement` therefore checks **both** choices at every remaining stage, visiting `238` state pairs at H6 and `1,002` (closed-form) at H8—exceeding the total number of states expanded by unpruned `_search` (`190` at H6, `766` at H8).
2. **Repeated full-chain provenance re-verification (`verify_state_provenance`):** Every recursive call to `is_local_refinement` re-walks both `fine_state` and `coarse_state` back to the root (`depth 0`), calling `apply_action_outcome` $\to$ `_enabled` $\to$ `verify_action_contract` $\to$ `validate_oracle` at every ancestor (`3,014` provenance calls at H6 for only `9` dominance checks).
3. **Un-cached oracle/contract re-validation inside every `_enabled` and `apply_action_outcome` call:** `validate_oracle` runs `4,670` times and `verify_action_contract` runs `4,657` times at H6—constituting **80.6%** and **93.5%** of cumulative pruned runtime at H5 (`cProfile`).
4. **Repeated decimal-string-to-`Fraction` parsing (`_nonnegative`):** Because `ActionSemantics` stores resource bounds as raw `float`s (`dwaop_integrated_planner.py:206-219`), every `validate_oracle` and `verify_action_contract` call re-parses `Fraction(str(value))` via regex matching and `math.gcd` (`494,256` calls to `_nonnegative` at H6; `Fraction.__new__` + regex takes **>75%** of H5 CPU time).

Crucially, **memoizing `is_local_refinement` alone does not help H6/H8**: on the refinement ladder, `100%` of `(fine_state, coarse_state, depth_left)` pairs (`112/112` at H5) are distinct because `remaining_actions` tracks the exact subset of `{fine_stage_i, coarse_stage_i}` consumed along each branch. By contrast, **pre-validating the oracle/contracts + inductive provenance caching (in-memory counterfactual `V2`) cuts H6 runtime by 97.6× (`28.34s` $\to$ `0.290s`, **15.7× faster than unpruned**) and H8 runtime from `155.24s` to `1.326s` (**117.1× speedup vs pruned, 15.5× faster than unpruned**)** with identical Pareto frontiers. On general DAGs with commutative actions, unmemoized `is_local_refinement` also suffers factorial blowup ($O(k!)$ vs $O(2^k)$), where safe memoization yields an additional **4.71×** speedup at $k=4$.

---

## 2. Line-by-Line Audit of the Three Target Functions

### 2.1 `plan_policies()` Pruning Loop (`dwaop_integrated_planner.py:1161-1362`)

1. **Contract Construction & Pre-Loop Work (`1178`, `1238-1262`):**
   - `plan_policies` validates `oracle` and `budget` once (`1169-1170`), builds `contracts = {aid: build_action_contract(oracle, aid) ...}` (`1178`, which itself calls `validate_oracle` $|A|$ times), and starts `_search(root, max_horizon)` (`1191`).
   - At every non-terminal state (`1239-1248`), `_search` iterates `sorted(state.remaining_actions)` and calls `apply_action_outcome(state, contract, oracle)` $\to$ `_enabled(...)` $\to$ `verify_action_contract(...)` $\to$ `validate_oracle(...)` for every remaining action.
   - When `prune=True` (`1250-1262`), `candidate_groups` is sorted by `(-len(transitions), ru_upper, cpu_ticks, energy_ticks, workspace_gb_upper, action_id)` so finer-grained and cheaper actions expand first and populate `expanded_covers` (`1264`, `1336`).
2. **Pruning Gate (`1269-1295`):**
   - For each subsequent `(contract, transitions)` in `candidate_groups`, the loop scans `expanded_covers` for matching `fine_contract.semantic_key == contract.semantic_key` (`1271-1273`).
   - For each match, it increments `dominance_checks` and evaluates:
     ```python
     covers_all = all(
         is_complete_refinement_cover(
             fine_children, t.state, contracts, oracle, budget, depth_left - 1
         )
         for t in transitions
     )
     ```
     (`1276-1286`).
   - **Per-transition redundancy:** If a coarse action splits worlds into $k \ge 2$ transitions (`len(transitions) >= 2`), the generator invokes `is_complete_refinement_cover` once per `t.state`, repeating `validate_resource_budget`, `_state_key(parent)`, and parent checks until line `1007` (`parent.worlds != coarse_state.worlds`) fails on the first splitting transition. (When a coarse action is non-splitting, `len(transitions) == 1` and `t.state.worlds == parent.worlds`.)
   - **Eager recursion before pruning:** An action is only appended to `expanded_covers` if `action_policies` is non-empty (`1333-1336`). Because `expanded_covers` stores `(contract, tuple(t.state for t in transitions))` unconditionally once a single non-empty policy exists, later coarse actions check against all earlier same-key actions that yielded $\ge 1$ policy.
3. **Combination & Frontier Reduction (`1304-1338`):**
   - `product(*branch_policies)` (`1304`) enumerates the Cartesian product of branch Pareto frontiers, whose size is $\prod_{j=1}^{B} |\mathcal{P}(t_j)|$.
   - `pareto_reduce` (`1124-1134`, called at `1236`, `1338`, `1341`) deduplicates via `_canonical_dedup` and performs an $O(|\text{unique}|^2)$ pairwise dominance loop (`1128-1133`).

### 2.2 `is_complete_refinement_cover()` (`dwaop_integrated_planner.py:983-1079`)

For one call `is_complete_refinement_cover(candidate_children, coarse_state, contracts, oracle, budget, depth_left)`:

| Lines | Operation | Work Performed |
|---|---|---|
| `992` | `validate_resource_budget(budget)` | 4 `_nonnegative` calls (`Fraction` conversion/check). |
| `1005, 1040` | `_state_key(parent)` & `_state_key(child.parent_state_snapshot)` | Re-sorts 4 sets (`worlds`, `open_obligations`, `capabilities`, `remaining_actions`) for `parent`, `coarse_state.parent`, and every `child` in `candidate_children`. |
| `1007` | `parent.worlds != coarse_state.worlds` | Early exit for any world-splitting coarse transition. |
| `1019` | `verify_state_provenance(coarse_state, contracts, oracle)` | **Full recursive ancestry walk** (`provenance_depth` steps to root); each step invokes `apply_action_outcome` $\to$ `_enabled` $\to$ `verify_action_contract` $\to$ `validate_oracle`. |
| `1026-1027` | `verify_action_contract` ($\times 2$) | Validates `fine_contract`, `coarse_contract`, and runs `validate_oracle(oracle)` twice over all actions/labels in `oracle`. |
| `1050-1056` | `apply_action_outcome(parent, fine_contract, oracle)` | Recomputes all fine transitions from `parent` (calling `_enabled` $\to$ `verify_action_contract` $\to$ `validate_oracle`), then compares full `EvidenceState` equality (`set(candidate_children) != expected_states`, which compares `parent_state_snapshot` recursively!). |
| `1062-1069` | Per-child loop (`m = len(candidate_children)`) | For **every** fine child: (a) calls `verify_state_provenance(child, ...)` (another full root walk), and (b) calls `is_local_refinement(child, coarse_state, contracts, oracle, depth_left)` (recursive finite-horizon simulation). |
| `1075-1077` | Budget feasibility loop | For **every** fine child: calls `_has_complete_policy_within_budget(child, contracts, oracle, budget, depth_left)` (unmemoized DFS until first budget-feasible policy). |

### 2.3 `is_local_refinement()` (`dwaop_integrated_planner.py:826-930`)

Inside **every recursive invocation** of `is_local_refinement(fine_state, coarse_state, contracts, oracle, depth_left)`:

| Lines | Operation | Cost / Amplifying Behavior |
|---|---|---|
| `836-839` | `verify_state_provenance(fine_state)` & `verify_state_provenance(coarse_state)` | **2 full root-to-node provenance walks** executed at *every* depth of the recursion tree (not only at the top-level cover check!). |
| `840-853` | 11 structural/resource inequalities | Cheap `Fraction` and `frozenset` comparisons (`dominates_or_equal` calls `_nonnegative(0.0)`). |
| `855-888` | `terminal_verdict` ($\times 2$) & non-sticky `REFUSE` guard (`878-882`) | If `coarse_term == "REFUSE"` and non-sticky (`depth_left > 0`), checks `_enabled` for all `coarse_state.remaining_actions`—**then lines `890-894` recompute the exact same `coarse_enabled` list a second time!** |
| `890-894` | Build `coarse_enabled` | Loops `sorted(coarse_state.remaining_actions)`, calling `_enabled` $\to$ `verify_action_contract` $\to$ `validate_oracle` for every remaining action. |
| `899-929` | Universal/existential simulation loop | For **every** `right_action` in `coarse_enabled`: loops `left_action_id` in `sorted(fine_state.remaining_actions)` calling `_enabled` (`903`, `validate_oracle` again!) until `_action_matches_no_worse` (`905`) passes; then calls `apply_action_outcome` for both `fine_state` (`908`) and `coarse_state` (`909`) (`2` more `validate_oracle` calls), and recurses (`919`) on **every** `lt` in `left_transitions`! |

**Critical structural finding:** `is_local_refinement` checks `for right_action in coarse_enabled:` universally ($\forall a_c \in \text{enabled}(S_c)$). Whenever multiple actions are enabled in `coarse_state`, `is_local_refinement` **branches across all of them**, even if `fine_state` already has a strictly cheaper dominant action at that stage.

---

## 3. Why H6/H8 Pruning Cuts States >92% Yet Increases Runtime ~7.5×

### 3.1 Measured Scaling Across H3–H8

Data for H3–H5 comes from our `cProfile` and wrapper instrumentation ([`profile_dwaop.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/profile_dwaop.py)); H6 call counts from lightweight wrapper instrumentation ([`h8_and_worstcase.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/h8_and_worstcase.py)); H6/H8 clean baseline timings from [`DWAOP_HORIZON_CAMPAIGN_v0.3.json`](file:///f:/gdec-dwaop-v03/research/results/DWAOP_HORIZON_CAMPAIGN_v0.3.json).

| Metric | H3 (`S=2`, 8w) | H4 (`S=3`, 16w) | H5 (`S=4`, 32w) | H6 (`S=5`, 64w) | H8 (`S=7`, 256w) |
|---|---:|---:|---:|---:|---:|
| Actions (`2S+1`) | 5 | 7 | 9 | 11 | 15 |
| Unpruned `states_expanded` | 22 | 46 | 94 | 190 | 766 |
| Pruned `states_expanded` | 9 | 11 | 13 | 15 | 19 |
| State reduction | 59.09% | 76.09% | 86.17% | 92.11% | 97.52% |
| Unpruned runtime (clean) | 0.083s | 0.290s | 1.415s | 3.005s | 20.539s |
| Pruned runtime (clean) | 0.725s | 3.342s | 8.797s | 22.257s | 155.244s |
| Ratio (Pruned / Unpruned) | 8.69× | 11.52× | 6.22× | 7.41× | 7.56× |
| `dominance_checks` (= `successful_prunes`) | 3 | 5 | 7 | 9 | 13 |
| `is_complete_refinement_cover` calls | 3 | 5 | 7 | 9 | 13 |
| **`is_local_refinement` calls** | **20** | **50** | **112** | **238** | **1,002** *(formula)* |
| `verify_state_provenance` calls | 158 | 470 | 1,230 | 3,014 | — |
| `_enabled` calls | 221 | 697 | 1,873 | 4,639 | — |
| `verify_action_contract` calls | 227 | 707 | 1,887 | 4,657 | — |
| `validate_oracle` calls | 234 | 716 | 1,898 | 4,670 | — |
| `_nonnegative` calls | 15,778 | 56,994 | 175,602 | 494,256 | — |

### 3.2 Closed-Form Explanation of `is_local_refinement` Call Count

In `build_refinement_ladder(S)` (`horizon = S + 1`):
- Stage `0` has `fine_stage_0` (2 outcomes: `group_0`, `group_1`) and `coarse_stage_0` (1 outcome: `coarse_cell`). Both gain `cap_1`.
- Stages `i = 1 .. S-1` each have `fine_stage_i` (1 outcome: `same_cell`) and `coarse_stage_i` (1 outcome: `coarse_cell`).
- `final_decision` splits into 2 outcomes (`accept`, `reject`) at depth `0`.

In `plan_policies(prune=True)`:
- At Stage `0` (`depth_left = S`), `fine_stage_0` expands 2 children (`child_0`, `child_1`) and prunes `coarse_stage_0` (`1` dominance check $\to$ `2` calls to `is_local_refinement` at `depth_left = S`).
- Along each of `child_0` and `child_1`, at Stage `i` ($1 \le i \le S-1$, `depth_left = S - i`), `fine_stage_i` expands 1 child and prunes `coarse_stage_i` (`2` dominance checks per stage $\implies$ `2S - 1` total dominance checks = `3, 5, 7, 9, 13` for $S = 2, 3, 4, 5, 7$).
- Inside `is_local_refinement` at `depth_left = k >= 1`, `coarse_enabled` contains **both** `coarse_stage_i` and `fine_stage_i` (branching factor **2** at every remaining stage!). Therefore, the number of `is_local_refinement` calls at each depth $k \in \{1, \dots, S\}$ satisfies $N(S) = 2$ and $N(k) = 2 N(k+1) + 2 = 2^{S - k + 2} - 2$, and `final_decision` splits 2 ways into depth `0` ($N(0) = 2 N(1) = 2^{S+2} - 4$). Summing over $k = 0 \dots S$:

$$C_{\text{local}}(S) = \sum_{k=1}^{S} (2^{S-k+2} - 2) + (2^{S+2} - 4) = 2^{S+3} - 2S - 8.$$

This matches every measured count (`20` at $S=2$, `50` at $S=3$, `112` at $S=4$, `238` at $S=5$) and yields **`1,002`** calls at H8 ($S=7$).

Compare this directly against **unpruned** `_search`:
- On the ladder, `unpruned` expands $N_{\text{unpruned}}(S) = 3 \cdot 2^{S+1} - 2$ states? Wait—let's check the exact sequence `22, 46, 94, 190, 766`: $3 \cdot 2^{S+1} - 2$ gives $3 \cdot 8 - 2 = 22$ ($S=2$), $3 \cdot 16 - 2 = 46$ ($S=3$), $3 \cdot 32 - 2 = 94$ ($S=4$), $3 \cdot 64 - 2 = 190$ ($S=5$), $3 \cdot 256 - 2 = 766$ ($S=7$).
- Thus, on H6/H8, **`is_local_refinement` alone visits MORE recursion nodes (`238` at H6, `1,002` at H8) than unpruned `_search` expands states (`190` at H6, `766` at H8)**! Because each stage has `|P| = 1` Pareto policy and no world splitting after Stage 0, unpruned search has zero `product(*branch_policies)` blowup (`236` policies at H6, `956` at H8), whereas `is_local_refinement` performs ~**20×** more `validate_oracle` calls per node than unpruned `_search` (`4,670` vs `~560` extrapolated; at H5, `validate_oracle` is called `1,898` times in pruned vs `278` times in unpruned = `6.83×` more `validate_oracle` calls overall, even with `86%` fewer states!).

### 3.3 `cProfile` CPU Hotspot Breakdown (H5 / `S=4`, `44.037s` pruned vs `6.252s` unpruned)

From `cprofile_pruned_cumtime` and `cprofile_pruned_tottime` in `profile_results_2_3_4.json`:

| Function | Calls (Pruned H5) | CumTime (s) | % of Total | SelfTime (s) | Role |
|---|---:|---:|---:|---:|---|
| `plan_policies` / `_search` | `1` / `13` | `44.037` | `100.0%` | `0.009` | Search driver |
| `is_complete_refinement_cover` | `7` | `42.441` | `96.4%` | `0.002` | Top-level cover checks |
| `verify_action_contract` | `1,887` | `41.186` | `93.5%` | `1.285` | Called inside every `_enabled` & cover check |
| `_enabled` | `1,873` | `40.943` | `93.0%` | `0.051` | Called per remaining action in `is_local_refinement` & `apply` |
| `is_local_refinement` | `112` | `39.528` | `89.8%` | `0.030` | Recursive simulation tree (`238` at H6) |
| `validate_oracle` | `1,898` | `35.503` | `80.6%` | `6.568` | Loops over all `2S+1` actions & all labels in `oracle` |
| `_nonnegative` | `175,602` | `33.777` | `76.7%` | `3.968` | Parses raw floats in `ActionSemantics` on every check |
| `apply_action_outcome` | `1,267` | `29.949` | `68.0%` | `0.395` | Re-runs `_enabled` + constructs `ResourceVector`s |
| `Fraction.__new__` | `152,493` | `27.228` | `61.8%` | `14.534` | Regex match (`re.Match.group` `5.914s`, `re.Pattern.match` `2.506s`) + `gcd` (`0.899s`) |
| `verify_state_provenance` | `1,230` (`239` top) | `23.827` | `54.1%` | `0.081` | Walks `parent_state_snapshot` recursively to depth `0` |
| `_has_complete_policy_within_budget` | `36` (`8` top) | `1.525` | `3.5%` | `0.002` | Feasibility DFS on fine children |

---

## 4. Cost Per Dominance Check

A single `dominance_checks += 1` iteration in `plan_policies()` (`1275-1287`) invokes `is_complete_refinement_cover` $m_c$ times (where $m_c = |\text{transitions}(a_c)|$; $m_c = 1$ for non-splitting coarse actions, and for $m_c \ge 2$ it short-circuits on the first transition at `1007` because `parent.worlds != coarse_state.worlds`).

Let:
- $m_f = |\text{candidate\_children}|$ (fine sibling count),
- $p = \text{provenance\_depth}(\text{coarse\_state})$,
- $d = \text{depth\_left}$,
- $|A|$ = total actions in `oracle`, $b_A$ = average enabled actions in `coarse_state`,
- $L_{\text{tot}} = \sum_{a \in A} |\text{labels}(a)|$ (number of `validate_oracle` label checks; each `validate_oracle` executes $\Theta(|A| + L_{\text{tot}})$ `Fraction(str(...))` constructions),
- $N_{\text{sim}}(d)$ = number of recursive `is_local_refinement` calls triggered per fine child (worst-case up to $O((b_A \cdot \bar{m}_f)^d)$).

Then the cost of **one successful dominance check** is:
$$C_{\text{cover}} \approx \underbrace{m_f \cdot N_{\text{sim}}(d)}_{\text{simulation nodes}} \cdot \Big[ \underbrace{2 \bar{p} \cdot C_{\text{apply}}}_{\text{provenance walks}} + \underbrace{(|A_{\text{rem}}| + 3 b_A) \cdot C_{\text{contract+oracle}}}_{\text{\_enabled + apply}} \Big] + \underbrace{m_f \cdot C_{\text{budget}}(d)}_{\text{\_has\_complete\_policy}},$$
where $C_{\text{contract+oracle}} = \Theta(|A| + L_{\text{tot}})$ `_nonnegative`/`Fraction(str(...))` calls!

Empirically on the refinement ladder:
- **Baseline H6:** `21.858s / 9 = 2.429s` per dominance check (`~519` `validate_oracle` calls and `~54,900` `_nonnegative` calls per check on average; Stage 0 check is much heavier than Stage 4 checks).
- **Baseline H8:** `153.956s / 13 = 11.843s` per dominance check.
- **After contract/oracle pre-validation (`V1`):** `1.369s / 9 = 0.152s` per check at H6; `8.517s / 13 = 0.655s` per check at H8.
- **After + provenance caching (`V2`):** `0.260s / 9 = 0.029s` per check at H6 (**84× cheaper per check**); `1.288s / 13 = 0.099s` per check at H8 (**120× cheaper per check**).

---

## 5. Repeated Recursive Subproblems

### 5.1 What Repeats on H6/H8 vs. What Does Not

Measured uniqueness ratios on H3–H5 (`dedup_stats` in `profile_results_2_3_4.json`):

| Function | H3 (`S=2`) Total / Unique | H4 (`S=3`) Total / Unique | H5 (`S=4`) Total / Unique | Redundancy Factor (H5) |
|---|---:|---:|---:|---:|
| `validate_oracle` | `234 / 1` | `716 / 1` | `1,898 / 1` | **1,898×** |
| `verify_action_contract` | `227 / 5` | `707 / 7` | `1,887 / 9` | **209.7×** |
| `verify_state_provenance` | `158 / 22` keys (`39` objs) | `470 / 46` keys (`92` objs) | `1,230 / 94` keys (`205` objs) | **13.1×** (by key), **6.0×** (by obj) |
| `is_local_refinement` | `20 / 20` | `50 / 50` | `112 / 112` | **1.00× (0% cache hits!)** |
| `_has_complete_policy_within_budget` | `14 / 14` | `24 / 24` | `36 / 36` | **1.00× (0% cache hits!)** |

**Why `is_local_refinement` has 0% subproblem repetition on H6/H8:** Even though `fine_stage_i` and `coarse_stage_i` discharge the exact same obligation `stage_i` and gain the exact same `cap_{i+1}`, `EvidenceState.remaining_actions` removes only the specific `action_id` executed (`fine_stage_i` vs `coarse_stage_i`). Thus every distinct sequence of fine/coarse choices across stages $1 \dots i$ yields a distinct `(fine.remaining_actions, coarse.remaining_actions)` pair, producing **zero** duplicate `(fine_state, coarse_state, depth_left)` calls on the ladder.

### 5.2 Factorial Repetition on Commutative / Diamond Action Graphs

On general graphs where $k$ obligations `{ob_0, ..., ob_{k-1}}` can be discharged in **any order** (independent / commutative actions), any two permutations of the same action subset reach the identical `(worlds, open_obligations, capabilities, remaining_actions, resource_spent, ...)` state. Unmemoized `is_local_refinement` traverses all $k!$ action interleavings instead of the $2^k$ subset pairs.

Measured in [`worstcase_and_breakeven.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/worstcase_and_breakeven.py) (`test_commutative_diamond_blowup`, one cover check at root):

| Commutative pairs $k$ | Unmemoized `is_local_refinement` calls | Unique `(sim_key_f, sim_key_c, depth)` | Duplication Factor | Unmemoized Runtime | Memoized `is_local_refinement` Calls / Hits / Runtime |
|---:|---:|---:|---:|---:|---|
| 2 | 16 | 12 | 1.33× | 0.079s | 16 / 4 hits / 0.065s |
| 3 | 92 | 36 | 2.56× | 0.671s | 68 / 32 hits / 0.350s (1.92× faster) |
| 4 | 712 | 108 | 6.59× | 11.562s | 272 / 164 hits / 2.454s (**4.71× faster**) |

*(Note: `test_commutative_diamond_blowup` memoized only `is_local_refinement` without contract/provenance caching; combining both eliminates the remaining provenance/oracle overhead.)*

### 5.3 Repeated Subproblems in `_search` and `_has_complete_policy_within_budget`

Both `_search` (`1191-1338`) and `_has_complete_policy_within_budget` (`951-980`) are unmemoized recursive tree searches. Whenever two different action orderings reach the same state (same `worlds`, `open_obligations`, `capabilities`, `remaining_actions`, `remaining_retries`, `model_valid`, `evidence_stale`, `resource_spent`, `resident_memory_gb`, `last_outcome_kind`) at the same `depth_left`, both functions re-expand the full remaining subtree from scratch.

---

## 6. Safe Memoization Keys & Precomputation Analysis

### 6.1 Soundness Traps in Naive Keys

Audit of [`dwaop_integrated_planner.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py) identifies **four critical soundness constraints** that restrict what keys and caches are safe:

1. **`_state_key()` (`932-948`) is UNSAFE as a memoization key for ANY of the three functions:**
   - `_state_key` **omits `last_outcome_kind`**, which is read by `terminal_verdict` (`797`) and `is_local_refinement` (`870`, `coarse_sticky`). Two states with identical `_state_key`—one after `OutcomeKind.TIMEOUT` (recoverable `REFUSE`) and one after `OutcomeKind.UNRECOVERABLE_REFUSAL` (sticky `REFUSE`) or `OutcomeKind.SUCCESS`—have different simulation and termination behavior.
   - `_state_key` **omits `parent_state_snapshot`, `last_action_id`, and `last_outcome_label`**, so it cannot validate `verify_state_provenance` across untrusted/forged states.
   - `_state_key` **includes `provenance_depth`**, which causes unnecessary cache misses in `is_local_refinement`, `_has_complete_policy_within_budget`, and `_search` when states reconverge via different-length prefixes (unless `last_outcome_kind` is also included and provenance is separately verified).
2. **`depth_left` CANNOT be omitted or treated monotonically in `is_local_refinement`:**
   - Look at `dwaop_integrated_planner.py:874-875`: when `coarse_term == "REFUSE"` and `coarse_state` is non-sticky with enabled recovery actions, `is_local_refinement` returns **`True`** at `depth_left == 0` (`875`), whereas at `depth_left == 1` it falls through to `890-929` and can return **`False`**.
   - Conversely, when `coarse_term is None`, `depth_left == 0` returns **`False`** (`888`), whereas `depth_left >= 1` can return **`True`**.
   - Therefore, `is_local_refinement` is **non-monotone in `depth_left`**; `depth_left` MUST be included as an exact component of the memoization key.
3. **`resource_spent` and `resident_memory_gb` CANNOT be omitted from `_search` or `_has_complete_policy_within_budget` keys:**
   - Even though `_search` constructs incremental `additional_vec` (`1306-1311`), line `1318` filters by `budget.allows(total_vec)` (which depends on `state.resource_spent`), and `apply_action_outcome` (`686-700`) computes `during_peak = resident_before + workspace + overlap` and `resident_after = max(0, resident_before + retained - released)` nonlinearly from `state.resident_memory_gb` and `state.resource_spent.peak_memory_gb`.
4. **Cross-call `id(oracle)` caching is UNSAFE on public functions:**
   - `WorldOracle` and `ActionSemantics` are `@dataclass(frozen=True)` containers holding mutable `Mapping` fields (`dict`s at `201, 211-219, 230-231`), and `plan_policies` accepts external `initial_state` (`1166`). Global cross-call caching keyed by `id(oracle)` risks stale hits if a caller mutates a `dict` inside `WorldOracle`/`ActionSemantics` or reuses an object address after GC. **Within a single `plan_policies` call** (where `oracle` and `contracts` are fixed and `initial_state` provenance is checked once), per-invocation precomputation and caching are 100% safe.

### 6.2 Exact Safe Memoization Keys & Precomputation Design

| Component | Safe Precomputation / Key (Scoped to Single `plan_policies` Run) | Why It Is Sound |
|---|---|---|
| **Oracle & Contracts** | Validate `oracle` once (`validate_oracle`), pre-normalize `ActionSemantics` floats to `Fraction` once, build & verify `contracts` once (`1178`), and use trusted internal `_enabled_verified` / `_apply_verified` skipping re-validation. | `contracts` is freshly built at `1178` from validated `oracle` and never mutated during `_search`. (Keep public `verify_action_contract` / `apply_action_outcome` validating when called externally.) |
| **`verify_state_provenance`** | Verify `root` (`initial_state`) once at `plan_policies` entry, then pass an internal `_verify_provenance: bool = False` flag inside `plan_policies()` / `is_local_refinement()` (relying on the inductive invariant that every child produced by `_apply_verified(verified_parent, verified_contract)` is provenance-valid by construction). **Avoid** a global or unretained `id(state)` cache (risks GC address reuse, or inflates `tracemalloc` peak memory if strong refs are retained). Keep `_verify_provenance=True` by default on public entry points so external callers remain fail-closed. | By `753-787`, provenance is inductive: `parent` valid + `child in apply_action_outcome(parent, contract, oracle)` $\iff$ `child` valid. |
| **`is_local_refinement`** | After verifying provenance of top-level `(fine_state, coarse_state)`, memoize recursive calls on:<br>`(sim_key(fine_state), sim_key(coarse_state), depth_left)`<br>where `sim_key(s) = (s.specification_id, s.model_id, s.assurance_scope, s.worlds, s.open_obligations, s.capabilities, s.remaining_actions, s.remaining_retries, s.model_valid, s.evidence_stale, s.resource_spent.exact_key(), s.resident_memory_gb, s.last_outcome_kind)`. | Exhaustive inspection of `834-929` confirms these are the exact and only fields of `EvidenceState` (plus provenance validity and `depth_left`) that `is_local_refinement` and `terminal_verdict` read. |
| **`_has_complete_policy_within_budget`** | Memoize on `(state_exec_key(state), depth_left)`, where `state_exec_key` equals `sim_key(state)` (excluding `provenance_depth` and `parent_state_snapshot`). | All transitions, terminal checks, and `budget.allows` depend solely on `state_exec_key(state)` and `depth_left` for fixed `(contracts, oracle, budget)`. |
| **`_search`** | Memoize on `(state_exec_key(state), depth_left)` (storing returned `Tuple[NormalizedPolicy, ...]`, careful to charge `states_expanded` / `complete_policies_enumerated` metrics consistently if metrics matter). | `_search` outputs depend only on `state_exec_key(state)` and `depth_left` for fixed `(oracle, budget, prune)`. |
| **Precomputing `coarse_enabled`** | Cache `enabled_actions(state)` per `(worlds, open_obligations, capabilities, remaining_actions, remaining_retries)` and avoid calling `_enabled` twice for non-sticky `REFUSE` (`878-882` + `890-894`). | `_enabled` depends only on those 5 `EvidenceState` fields once contracts are verified. |

### 6.3 Measured Counterfactual Ablations (No Repo Code Modified)

Executed via in-memory wrapper ablations ([`profile_counterfactuals.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/profile_counterfactuals.py) and [`h8_and_worstcase.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/h8_and_worstcase.py)); every variant asserted exact `pareto_frontier` equality with baseline pruned search:

- **V1:** Cache `validate_oracle` + `verify_action_contract`
- **V2:** V1 + cache `verify_state_provenance`
- **V3:** V2 + memoize `is_local_refinement` by `(sim_key_f, sim_key_c, depth_left)`
- **V4:** V3 + memoize `_has_complete_policy_within_budget`

| Benchmark | Unpruned | Baseline Pruned | V1 (Contracts) | V2 (+Provenance) | V3 (+Local Memo) | V4 (+Budget Memo) |
|---|---:|---:|---:|---:|---:|---:|
| **H3** (`S=2`, 8w) | 0.110s | 0.643s (`5.85×`) | 0.074s (`0.67×`) | **0.033s (`0.30×`)** | 0.042s (`0.38×`) | 0.043s (`0.39×`) |
| **H4** (`S=3`, 16w) | 0.278s | 2.110s (`7.59×`) | 0.261s (`0.94×`) | **0.109s (`0.39×`)** | 0.159s (`0.57×`) | 0.118s (`0.43×`) |
| **H5** (`S=4`, 32w) | 1.573s | 11.709s (`7.45×`) | 0.680s (`0.43×`) | **0.152s (`0.096×`)** | 0.254s (`0.16×`) | 0.266s (`0.17×`) |
| **H6** (`S=5`, 64w) | 4.560s | 28.338s (`6.21×`) | 1.395s (`0.31×`) | **0.290s (`0.064×`)** | 0.529s (`0.12×`) | 0.452s (`0.099×`) |
| **H8** (`S=7`, 256w) | 20.539s* | 155.244s* (`7.56×`) | 8.551s (`0.42×`) | **1.326s (`0.065×`)** | — | — |

*\*H8 baseline numbers from `DWAOP_HORIZON_CAMPAIGN_v0.3.json`; V1/V2 measured directly on this machine with `frontier_size = 1`, `states_expanded = 19`, `dominance_checks = 13`, `successful_prunes = 13`.*

Direct H8 exact-match and `tracemalloc` verification ([`verify_h8_memory.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/verify_h8_memory.py)) confirmed exact `pareto_frontier` equality (including `world_verdict_map`, `terminal_verdicts`, `resource_vector.exact_key()`, and `max_actions_on_path`) against `plan_policies(..., prune=False)`:
- `unpruned`: `29.055s`, `peak_planner_memory_bytes = 530,308 B`
- `V1` (`cache_contracts`): `9.383s`, `peak_planner_memory_bytes = 442,392 B`
- `V2_id_cache` (`id`-keyed provenance cache): `1.304s`, `peak_planner_memory_bytes = 473,616 B` (`+31 KB` cache overhead over `V1`)
- `V2_skip_prov` (internal `_verify_provenance=False` after root check): **`1.071s`**, **`peak_planner_memory_bytes = 414,376 B`** (**27.1×** faster than unpruned on the same run and **21.9%** lower peak memory).

**Key takeaway:** Eliminating repeated contract/oracle re-validation and provenance walks (`V2`) alone turns H6 from **6.21×–7.41× slower** to **15.7× faster** than unpruned (**97.6×** speedup vs baseline pruned), and H8 from **7.56× slower** to **15.5× faster** than unpruned (**117.1×** speedup vs baseline pruned). Adding `is_local_refinement` memoization (`V3`) adds slight key-hashing overhead on tree-shaped ladders with 0% hit rate (`0.290s` $\to$ `0.529s` at H6), while preventing $k!$ blowup on commutative DAGs.

---

## 7. Worst-Case Growth & Break-Even Conditions

### 7.1 Worst-Case Complexity

1. **Unoptimized `is_local_refinement`:**
   - On $k$ commutative action pairs: $\Omega(k! \cdot 2^k)$ calls (`712` calls for $k=4$, vs `108` unique subproblems).
   - **Residual $2^S$ scaling even after `V2`:** Even with contract pre-validation and inductive provenance, `is_local_refinement` still makes $2^{S+3}-2S-8$ calls on the refinement ladder (e.g., at $S=15$, `262,106` calls) because `coarse_enabled` contains both `coarse_stage_i` and `fine_stage_i` at every stage $i \ge 1$. Moreover, pruning unused dead actions from `remaining_actions` (actions whose `required_obligations` are permanently absent from `open_obligations`) still leaves distinct `resource_spent` tuples along `coarse_stage_i` vs `fine_stage_i` branches (`0.20` vs `0.10`), so naive `sim_key` memoization does not collapse the $2^S$ ladder tree unless either (a) `is_local_refinement` omits `right_action`s already proven cover-dominated within `coarse_state` (valid by transitivity of local simulation, provided that intra-`coarse_state` cover dominance has actually been verified), or (b) additive resource totals are normalized/canonicalized to `(coarse_res - fine_res)` gaps when `resident_memory_gb` and `peak_memory_gb` gaps permit.
   - On general graphs of horizon $d$ with $b_A$ enabled coarse actions per step, $m_f$ fine outcomes per matched action, provenance depth $p$, and $|A|$ actions / $L_{\text{tot}}$ labels:
     $$T_{\text{local}} = O\!\Big((b_A \cdot m_f)^d \cdot (p + |A|) \cdot (|A| + L_{\text{tot}})\Big).$$
2. **Failed / Rejected Prune Attempts (`rejected_prune_attempts`):**
   - When `k_coarse` coarse actions share `semantic_key` with an already-expanded `fine` action but fail simulation near the leaves (e.g., at `depth_left == 0` or because coarse gains an extra capability deep in the tree), `plan_policies` pays up to $k_{\text{coarse}} \cdot C_{\text{cover}}$ **and still expands all `k_coarse` subtrees**, giving `0%` state reduction with strictly higher runtime.
   - Measured in `worstcase_and_breakeven.py` (`test_rejected_prune_overhead`, depth 4, 2 worlds): `k_coarse = 1` gives `0/1` prunes (`14` vs `14` states) at `1.19×` runtime; `k_coarse = 4` (with `coarse_0_0` failing and `3` worse copies pruned) hits `7` dominance checks (`4` rejected) and `2.75×` runtime (`1.353s` vs `0.492s`).
3. **Cartesian `product(*branch_policies)` & `pareto_reduce` (`1304-1338`, `1124-1134`):**
   - At any state with $B$ outcome branches each having frontier size $P$, unpruned `_search` enumerates $\prod_{i=1}^B P_i = O(P^B)$ policies and passes them to $O(|\text{unique}|^2)$ `pareto_reduce`. If internal `pareto_reduce` is relaxed to retain distinct `(V, R, L)` tuples (as recommended in dominance specification audits), $|\mathcal{P}(t_i)|$ grows by at most a factor of $H$, making `product(*branch_policies)` even more sensitive to pruning coarse branching subtrees!

### 7.2 Break-Even Conditions

Let $S_c$ be a coarse outcome state pruned against `fine_children`. Pruning yields a net wall-clock speedup ($T_{\text{pruned}} < T_{\text{unpruned}}$) iff:

$$\sum_{\text{all checks}} C_{\text{cover}}(S_f, S_c, d) \;<\; \sum_{\text{pruned } S_c} \Big( W_{\text{search}}(S_c) + C_{\text{product}}(S_c) \Big),$$

where:
- $W_{\text{search}}(S_c)$ is the unpruned state-expansion work saved inside $S_c$'s subtree, and
- $C_{\text{product}}(S_c) \propto \prod_{j=1}^B |\mathcal{P}(t_j)|$ is the Cartesian policy combination + `pareto_reduce` cost saved under $S_c$.

**Two regimes govern break-even:**

1. **Current Unoptimized Planner (high $C_{\text{cover}}$):**
   - When $|\mathcal{P}| = 1$ and post-split branching is $1$ (as in H6/H8), $C_{\text{product}} \approx 0$ and $W_{\text{search}}(S_c) \propto 2^S$, while $C_{\text{cover}}$ also visits $\Theta(2^S)$ simulation nodes at ~20× higher per-node cost $\implies$ **pruning never breaks even** (`7.41×–7.56×` slower).
   - **Crossover when `product(*branch_policies)` dominates:** Because `is_local_refinement` checks simulation **per branch** (additive in $B$, zero Cartesian product) while unpruned `_search` pays $P^B$, break-even occurs once $P^B$ exceeds the dominance-check overhead.
   - Measured in [`crossover8.py`](file:///C:/Users/Nevan/.gemini/antigravity/brain/338c9913-c1d5-430e-bf78-3463c83b3747/scratch/crossover8.py) (8 worlds, Stage 0 fine 2-way vs coarse 1-way, Stage 1 8-way split, $P$ incomparable leaf policies):

     | Leaf Frontier Size $P$ | Unpruned States / Policies | Pruned States / Policies | Unpruned Runtime | Pruned Runtime | Ratio (`Pruned / Unpruned`) |
     |---:|---:|---:|---:|---:|---:|
     | `2` | `52` / `358` | `27` / `68` | `0.277s` | `0.972s` | `3.51×` (pruned slower) |
     | `3` | `68` / `6,831` | `35` / `219` | `3.297s` | `2.701s` | **`0.82×` (break-even crossed: 1.22× faster)** |
     | `4` | `84` / `66,196` | `43` / `592` | `31.133s` | `3.400s` | **`0.11×` (9.16× faster)** |

2. **Pre-Validated & Inductive-Provenance Planner (`V2`):**
   - Once `validate_oracle`, `verify_action_contract`, and `verify_state_provenance` are hoisted/inductively cached, $C_{\text{cover}}$ drops by **~84×–120×**, shifting break-even down to small trees where even a 2×–3× state reduction (`H3` at `0.30×`, `H6` at `0.064×`, `H8` at `0.065×`) already beats unpruned search by **3×–16×**.

---

## 8. Prioritized Optimization Recommendations (For Stage 2)

1. **Pre-normalize `ActionSemantics` & hoist `validate_oracle` / `verify_action_contract` inside `plan_policies()` (`V1`):** Eliminates `494k` `_nonnegative`/`Fraction(str(...))` regex calls at H6; single-handedly gives **18×–20×** speedup on H6/H8 (`28.34s` $\to$ `1.39s` at H6; `155.24s` $\to$ `8.55s` at H8).
2. **Inductive provenance path (`_verify_provenance=False` internally) inside `plan_policies()` (`V2_skip_prov`):** Verify `initial_state` once at entry and use an internal `_verify_provenance=False` path in `is_complete_refinement_cover` / `is_local_refinement` (keeping `_verify_provenance=True` fail-closed for external callers, and avoiding `id(state)` dicts). Brings H8 to `1.071s` and `414,376 B` peak memory (**27.1×** faster and **21.9%** less peak memory than unpruned's `29.055s` / `530,308 B` on the same run).
3. **Deduplicate `coarse_enabled` computation in `is_local_refinement()` (`878-882` vs `890-894`) and check `parent.worlds == coarse_state.worlds` before `_state_key` / provenance walks in `is_complete_refinement_cover()` (`1007` before `1005`/`1019`)** to fast-reject splitting coarse transitions at near-zero cost.
4. **Safe memoization of `is_local_refinement` (using full `sim_key` *with* `last_outcome_kind` and *exact* `depth_left`) and `_has_complete_policy_within_budget`:** Protects against factorial $O(k!)$ blowup on commutative DAGs (`4.71×` at $k=4$).
5. **Fast-path syntactic dominance precheck before full recursive simulation (optional heuristic):** Before launching a depth-$d$ `is_local_refinement` check, verify cheap necessary local inequalities (`840-853`, `fine_contract` bounds $\le$ `coarse_contract` bounds, and compatible `coarse_enabled` action coverage) so unprunable pairs fail in $O(1)$ rather than $O((b_A m_f)^d)$.
