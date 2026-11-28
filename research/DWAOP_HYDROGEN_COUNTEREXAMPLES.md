# DWAOP Hydrogen Counterexamples & Boundary Suite

**Target Repository:** `f:/gdec-dwaop-v03`  
**Commit:** `2812b000ea0241a3aee2b5580444a7e1767c3417`  
**Python Environment:** `f:/fem-edit-benchmark/.venv/Scripts/python.exe`  
**Scope:** Stage 1 read-only adversarial/counterexample synthesis against `_policy_dominates`, `_canonical_dedup`, `pareto_reduce`, `_oracle_dominates`, `_oracle_pareto_reduce`, `is_local_refinement`, `is_complete_refinement_cover`, `plan_policies`, and `enumerate_exact_pareto_frontier`.

---

## Executive Summary

| ID | Challenge Category | Target Functions | Key Observed Outcome |
|---|---|---|---|
| **CE-1** | Same verdicts + same resources + different `max_actions_on_path` | `_policy_dominates`, `_canonical_dedup`, `pareto_reduce`, `_oracle_dominates`, `_oracle_pareto_reduce`, `plan_policies`, `enumerate_exact_pareto_frontier` | `_policy_dominates` and `_oracle_dominates` return `False` in both directions; `_canonical_dedup` / `_oracle_pareto_reduce` silently drop the longer policy and keep `min(max_actions_on_path) = 1`. |
| **CE-2** | Lower resources + longer path vs. higher resources + shorter path | `_policy_dominates`, `pareto_reduce`, `_oracle_dominates`, `_oracle_pareto_reduce`, `plan_policies`, `enumerate_exact_pareto_frontier` | Lower resources + longer path (`ru=1, len=4`) **strictly dominates** higher resources + shorter path (`ru=2, len=1`) in both planner and oracle (`True`); shorter path is dropped unless another resource dimension creates an incomparable trade-off (`CE-2B`). |
| **CE-3** | Equal resources & equal `max_actions_on_path` | `_policy_dominates`, `_canonical_dedup`, `pareto_reduce`, `_oracle_dominates`, `_oracle_pareto_reduce` | Exact duplicates collapse to 1; incomparable verdict maps (`(ACCEPT, REFUSE)` vs. `(REFUSE, REJECT)`) both remain; synthetic mismatched `terminal_verdicts` bypass `_canonical_dedup` even with identical `world_verdict_map` and `resource_vector`. |
| **CE-4** | Different world verdicts | `_policy_dominates`, `_oracle_dominates`, `pareto_reduce`, `plan_policies`, `enumerate_exact_pareto_frontier` | `ACCEPT` and `REJECT` each dominate `REFUSE`, while `ACCEPT` vs. `REJECT` are mutually incomparable; a cheaper partial-`REFUSE` policy and a costlier full-decision policy both stay on the Pareto frontier. |
| **CE-5** | Multi-branch single-world-determined path lengths | `plan_policies`, `_enumerate_trees`, `_evaluate_tree_on_world`, `_canonical_dedup`, `_oracle_pareto_reduce` | **CE-5A:** Tree 0 (`w0`: 1/`ru=1`, `w1`: 3/`ru=2`, `max=3`) is collapsed to worst-case scalars and dropped in favor of Tree 1 (`(2, 2)`). **CE-5B (Bellman non-monotonicity):** Internal `pareto_reduce` at branch `w1` drops `(ru=2, L=1)` in favor of `(ru=1, L=3)`, causing **both** `plan_policies(prune=True)` and `plan_policies(prune=False)` to output `max_actions_on_path=4` while `enumerate_exact_pareto_frontier` outputs `max_actions_on_path=2` (`unpruned != oracle`). |
| **CE-6 (Q7)** | State-level pruning drops a frontier policy | `is_local_refinement`, `is_complete_refinement_cover`, `plan_policies`, `enumerate_exact_pareto_frontier` | **Two independent Q7 failure modes:** (1) **CE-6A/6B (`UNRECOVERABLE_REFUSAL`):** `is_local_refinement` checks `coarse_sticky` (`dwaop_integrated_planner.py:867-871`) but omits `fine_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`, so `prune=True` drops strictly dominating `ACCEPT` / `(ACCEPT, ACCEPT)` policies. (2) **CE-6C (`SUCCESS`-only, horizon 4):** Even with only `OutcomeKind.SUCCESS`, pruning `coarse_step` via `fine_split` combined with internal `pareto_reduce` dropping `(ru=2, L=1)` in `w1` causes `pruned` (`max_actions_on_path=4`) `!= unpruned == oracle` (`max_actions_on_path=2`). |

---

## CE-1: Same Verdicts + Same Resources + Different `max_actions_on_path`

### Mechanism Under Test
- `research/prototypes/dwaop_integrated_planner.py:1087-1121` (`_policy_dominates`, `_canonical_dedup`)
- `research/prototypes/dwaop_exhaustive_policy_oracle.py:286-311` (`_oracle_dominates`, `_oracle_pareto_reduce`)

Neither `_policy_dominates` nor `_oracle_dominates` inspects `max_actions_on_path`. However, both `_canonical_dedup` and `_oracle_pareto_reduce` group by `(world_verdict_map, terminal_verdicts, resource_vector)` and retain only the policy with the minimum `max_actions_on_path`.

### CE-1A: Direct `NormalizedPolicy` Comparison
- **Inputs:**
  - `rv = ResourceVector(ru_upper=1.0, cpu_ticks=2.0, energy_ticks=1.0, peak_memory_gb=0.5)`
  - `p_short = NormalizedPolicy((("w0", "ACCEPT"),), rv, frozenset({"ACCEPT"}), max_actions_on_path=1)`
  - `p_long  = NormalizedPolicy((("w0", "ACCEPT"),), rv, frozenset({"ACCEPT"}), max_actions_on_path=2)`
- **Expected behavior if `max_actions_on_path` were:**
  - *Strict tie-breaker (current design):* Dominance is `False` in both directions; deduplication keeps `(p_short,)` only.
  - *Pure descriptive metadata (no tie-break):* Both or insertion-order survivor could remain; `p_long` would not be systematically pruned.
- **Actual observed outputs:**
  - `_policy_dominates(p_short, p_long) == False`
  - `_policy_dominates(p_long, p_short) == False`
  - `_oracle_dominates(p_short, p_long) == False`
  - `_oracle_dominates(p_long, p_short) == False`
  - `_canonical_dedup([p_long, p_short])` -> `(p_short,)` (`max_actions_on_path=1`)
  - `pareto_reduce([p_long, p_short])` -> `(p_short,)` (`max_actions_on_path=1`)
  - `_oracle_pareto_reduce([p_long, p_short])` -> `(p_short,)` (`max_actions_on_path=1`)

**Reproducible command (run from `f:/gdec-dwaop-v03`):**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import NormalizedPolicy, ResourceVector, _policy_dominates, _canonical_dedup, pareto_reduce
from research.prototypes.dwaop_exhaustive_policy_oracle import _oracle_dominates, _oracle_pareto_reduce
rv = ResourceVector(ru_upper=1.0, cpu_ticks=2.0, energy_ticks=1.0, peak_memory_gb=0.5)
p_short = NormalizedPolicy((('w0', 'ACCEPT'),), rv, frozenset({'ACCEPT'}), 1)
p_long  = NormalizedPolicy((('w0', 'ACCEPT'),), rv, frozenset({'ACCEPT'}), 2)
print('policy_dom(short,long):', _policy_dominates(p_short, p_long))
print('policy_dom(long,short):', _policy_dominates(p_long, p_short))
print('oracle_dom(short,long):', _oracle_dominates(p_short, p_long))
print('oracle_dom(long,short):', _oracle_dominates(p_long, p_short))
print('canonical_dedup:', _canonical_dedup([p_long, p_short]))
print('pareto_reduce:', pareto_reduce([p_long, p_short]))
print('oracle_reduce:', _oracle_pareto_reduce([p_long, p_short]))
"
```

### CE-1B: End-to-End 1-World Graph (`fast` 1-step vs. `step1 -> step2` 2-step)
- **Inputs:** `universe={"w0"}`, `decision={"w0": "ACCEPT"}`, `initial_obligations={"ob"}`, `budget=(10, 10, 10, 10)`, `max_horizon=3`:
  - `fast`: `ru=2.0, cpu=2.0, energy=2.0, ws=0.5`, discharges `"ob"`.
  - `step1`: `ru=1.0, cpu=1.0, energy=1.0, ws=0.5`, gains `"c1"`.
  - `step2`: `ru=1.0, cpu=1.0, energy=1.0, ws=0.5`, requires `"c1"`, discharges `"ob"`.
- **Actual observed outputs:** Both policies produce `(("w0", "ACCEPT"),)` with `ResourceVector(2, 2, 2, 1/2)`. `plan_policies(..., prune=True)`, `plan_policies(..., prune=False)`, and `enumerate_exact_pareto_frontier` all return the single policy with `max_actions_on_path=1`.

---

## CE-2: Lower Resources + Longer Path vs. Higher Resources + Shorter Path

### CE-2A: Dominance of Lower-Resource / Longer-Path Policy
- **Inputs:**
  - `p_cheap_long   = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(1.0, 1.0, 1.0, 0.5), frozenset({"ACCEPT"}), max_actions_on_path=4)`
  - `p_costly_short = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(2.0, 1.0, 1.0, 0.5), frozenset({"ACCEPT"}), max_actions_on_path=1)`
- **Expected behavior if `max_actions_on_path` were a Pareto objective:** Neither policy dominates the other (trade-off between `ru_upper` and `max_actions_on_path`), so both remain on the frontier.
- **Actual observed outputs (confirming `max_actions_on_path` is NOT a Pareto objective):**
  - `_policy_dominates(p_cheap_long, p_costly_short) == True`
  - `_policy_dominates(p_costly_short, p_cheap_long) == False`
  - `_oracle_dominates(p_cheap_long, p_costly_short) == True`
  - `pareto_reduce([p_cheap_long, p_costly_short])` -> `(p_cheap_long,)` (`p_costly_short` is eliminated!)
  - `_oracle_pareto_reduce([p_cheap_long, p_costly_short])` -> `(p_cheap_long,)`
- **End-to-end graph confirmation:** Replacing `fast` (`ru=2.0`, 1 step) and `step1+step2` (`ru=0.5+0.5=1.0`, 2 steps) yields `plan_policies(prune=True) == plan_policies(prune=False) == enumerate_exact_pareto_frontier` containing only `(ru=1.0, max_actions_on_path=2)`.

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import NormalizedPolicy, ResourceVector, _policy_dominates, pareto_reduce
from research.prototypes.dwaop_exhaustive_policy_oracle import _oracle_dominates, _oracle_pareto_reduce
p_cheap_long   = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0, cpu_ticks=1.0, energy_ticks=1.0, peak_memory_gb=0.5), frozenset({'ACCEPT'}), 4)
p_costly_short = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=2.0, cpu_ticks=1.0, energy_ticks=1.0, peak_memory_gb=0.5), frozenset({'ACCEPT'}), 1)
print('policy_dom(cheap_long,costly_short):', _policy_dominates(p_cheap_long, p_costly_short))
print('policy_dom(costly_short,cheap_long):', _policy_dominates(p_costly_short, p_cheap_long))
print('oracle_dom(cheap_long,costly_short):', _oracle_dominates(p_cheap_long, p_costly_short))
print('pareto_reduce:', pareto_reduce([p_cheap_long, p_costly_short]))
print('oracle_reduce:', _oracle_pareto_reduce([p_cheap_long, p_costly_short]))
"
```

### CE-2B: Incomparable Multi-Resource Trade-Off with Different Path Lengths
- **Inputs:**
  - `p_a = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(ru_upper=1.0, cpu_ticks=5.0), frozenset({"ACCEPT"}), 3)`
  - `p_b = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(ru_upper=5.0, cpu_ticks=1.0), frozenset({"ACCEPT"}), 1)`
- **Actual observed outputs:** `_policy_dominates(p_a, p_b) == False`, `_policy_dominates(p_b, p_a) == False`, `len(pareto_reduce([p_a, p_b])) == 2`. Both stay on the frontier due to the `(ru_upper, cpu_ticks)` trade-off.

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import NormalizedPolicy, ResourceVector, _policy_dominates, pareto_reduce
p_a = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0, cpu_ticks=5.0), frozenset({'ACCEPT'}), 3)
p_b = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=5.0, cpu_ticks=1.0), frozenset({'ACCEPT'}), 1)
print('dom(a,b):', _policy_dominates(p_a, p_b), 'dom(b,a):', _policy_dominates(p_b, p_a))
print('frontier_len:', len(pareto_reduce([p_a, p_b])))
"
```

---

## CE-3: Equal Resources & Equal Action Count

- **Inputs (all sharing `rv = ResourceVector(1.0, 2.0, 1.0, 0.5)` and `max_actions_on_path=2`):**
  1. Exact duplicates: `p1` and `p1_dup` with `(("w0", "ACCEPT"), ("w1", "REJECT"))`.
  2. Strict verdict dominance: `p1` vs. `p_ar = (("w0", "ACCEPT"), ("w1", "REFUSE"))`.
  3. Incomparable partial verdicts: `p_ar` vs. `p_rr = (("w0", "REFUSE"), ("w1", "REJECT"))`.
  4. **Synthetic `terminal_verdicts` mismatch edge case:**
     - `ps_a = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(1.0), frozenset({"ACCEPT"}), 2)`
     - `ps_b = NormalizedPolicy((("w0", "ACCEPT"),), ResourceVector(1.0), frozenset({"ACCEPT", "REFUSE"}), 2)`
- **Actual observed outputs:**
  - `len(pareto_reduce([p1, p1_dup])) == 1` (exact duplicate collapsed).
  - `_policy_dominates(p1, p_ar) == True` and `_oracle_dominates(p1, p_ar) == True` (`REJECT` dominates `REFUSE` on `w1`).
  - `_policy_dominates(p_ar, p_rr) == False`, `_policy_dominates(p_rr, p_ar) == False`, `len(pareto_reduce([p_ar, p_rr])) == 2`.
  - **Latent dedup key asymmetry on `ps_a` vs. `ps_b`:** `_policy_dominates(ps_a, ps_b) == False` and `_policy_dominates(ps_b, ps_a) == False`, while both `_canonical_dedup` (`dwaop_integrated_planner.py:1106`) and `_oracle_pareto_reduce` (`dwaop_exhaustive_policy_oracle.py:302`) include `terminal_verdicts` in the deduplication key. Consequently `len(pareto_reduce([ps_a, ps_b])) == 2` and `len(_oracle_pareto_reduce([ps_a, ps_b])) == 2`. (In `plan_policies` and `enumerate_exact_pareto_frontier`, `terminal_verdicts` is always derived from `world_verdict_map`, so this only triggers on direct synthetic `NormalizedPolicy` inputs, revealing redundant/unvalidated key surface.)

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import NormalizedPolicy, ResourceVector, _policy_dominates, pareto_reduce
from research.prototypes.dwaop_exhaustive_policy_oracle import _oracle_dominates, _oracle_pareto_reduce
rv = ResourceVector(ru_upper=1.0, cpu_ticks=2.0, energy_ticks=1.0, peak_memory_gb=0.5)
p1     = NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'REJECT')), rv, frozenset({'ACCEPT', 'REJECT'}), 2)
p1_dup = NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'REJECT')), rv, frozenset({'ACCEPT', 'REJECT'}), 2)
p_ar   = NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'REFUSE')), rv, frozenset({'ACCEPT', 'REFUSE'}), 2)
p_rr   = NormalizedPolicy((('w0', 'REFUSE'), ('w1', 'REJECT')), rv, frozenset({'REFUSE', 'REJECT'}), 2)
print('dedup_len:', len(pareto_reduce([p1, p1_dup])))
print('p1_dom_ar:', _policy_dominates(p1, p_ar), 'oracle:', _oracle_dominates(p1, p_ar))
print('ar_vs_rr:', _policy_dominates(p_ar, p_rr), _policy_dominates(p_rr, p_ar), 'len:', len(pareto_reduce([p_ar, p_rr])))
ps_a = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT'}), 2)
ps_b = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT', 'REFUSE'}), 2)
print('synth_tv_mismatch_dom:', _policy_dominates(ps_a, ps_b), _policy_dominates(ps_b, ps_a))
print('synth_tv_mismatch_len_planner:', len(pareto_reduce([ps_a, ps_b])), 'oracle:', len(_oracle_pareto_reduce([ps_a, ps_b])))
"
```

---

## CE-4: Different World Verdicts (Lattice & Verdict-vs-Resource Trade-Offs)

- **Inputs:**
  - Single-world lattice at `ru=1.0`: `p_acc` (`ACCEPT`), `p_rej` (`REJECT`), `p_ref` (`REFUSE`).
  - Two-world verdict-vs-resource trade-off:
    - `p_trade_full = (("w0", "ACCEPT"), ("w1", "REJECT"))` at `ru=3.0, max_actions=2`
    - `p_trade_part = (("w0", "ACCEPT"), ("w1", "REFUSE"))` at `ru=1.0, max_actions=1`
- **Actual observed outputs:**
  - `_policy_dominates(p_acc, p_ref) == True`
  - `_policy_dominates(p_rej, p_ref) == True`
  - `_policy_dominates(p_acc, p_rej) == False` and `_policy_dominates(p_rej, p_acc) == False`
  - `_policy_dominates(p_trade_full, p_trade_part) == False` and `_oracle_dominates(p_trade_full, p_trade_part) == False` (`p_trade_full` has better verdict on `w1` but higher `ru=3.0`; `p_trade_part` has lower `ru=1.0` but `REFUSE` on `w1`), so `len(pareto_reduce([p_trade_full, p_trade_part])) == 2`.
  - Confirmed end-to-end on a 2-world action graph (`probe_partial` `ru=1.0` giving `(ok, fail/TIMEOUT)` vs. `recover_w1` `ru=2.0` recovering `w1`), where `plan_policies(prune=True) == enumerate_exact_pareto_frontier` returns both policies.

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import NormalizedPolicy, ResourceVector, _policy_dominates, pareto_reduce
from research.prototypes.dwaop_exhaustive_policy_oracle import _oracle_dominates
p_acc = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT'}), 1)
p_rej = NormalizedPolicy((('w0', 'REJECT'),), ResourceVector(ru_upper=1.0), frozenset({'REJECT'}), 1)
p_ref = NormalizedPolicy((('w0', 'REFUSE'),), ResourceVector(ru_upper=1.0), frozenset({'REFUSE'}), 1)
print('acc_dom_ref:', _policy_dominates(p_acc, p_ref), 'rej_dom_ref:', _policy_dominates(p_rej, p_ref))
print('acc_vs_rej:', _policy_dominates(p_acc, p_rej), _policy_dominates(p_rej, p_acc))
p_trade_full = NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'REJECT')), ResourceVector(ru_upper=3.0), frozenset({'ACCEPT', 'REJECT'}), 2)
p_trade_part = NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'REFUSE')), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT', 'REFUSE'}), 1)
print('trade_dom:', _policy_dominates(p_trade_full, p_trade_part), _oracle_dominates(p_trade_full, p_trade_part))
print('trade_frontier_len:', len(pareto_reduce([p_trade_full, p_trade_part])))
"
```

---

## CE-5: Multi-Branch Single-World-Determined Path Lengths

### Construction
A 2-world (`w0 -> ACCEPT`, `w1 -> REJECT`) contingent action graph with `initial_obligations = {"ob0", "ob1"}` admits two distinct complete branching trees (`max_horizon=4`, `budget=(10, 10, 10, 10)`):
- **Tree 0 (`root_asym`):** `root_asym` (`ru=1.0`) splits `w0` (`left`, discharges `{"ob0", "ob1"}`) and `w1` (`right`, discharges `{"ob0"}`, gains `"asym_mid1"`). Branch `w0` terminates immediately at depth `1` (`ru=1.0`), while branch `w1` executes `asym_w1_a` (`ru=0.5`) and `asym_w1_b` (`ru=0.5`) to finish at depth `3` (`ru=2.0`).
  - Per-world vector: `w0: (ACCEPT, ru=1.0, actions=1)`, `w1: (REJECT, ru=2.0, actions=3)`.
  - Collapsed `NormalizedPolicy`: `world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'REJECT'))`, `ru_upper=2.0`, `max_actions_on_path=3`.
- **Tree 1 (`root_even`):** `root_even` (`ru=1.0`) splits `w0`/`w1` (both discharge `{"ob0"}`, gain `"even_next"`), and both branches take `even_finish` (`ru=1.0`) to finish at depth `2` (`ru=2.0`).
  - Per-world vector: `w0: (ACCEPT, ru=2.0, actions=2)`, `w1: (REJECT, ru=2.0, actions=2)`.
  - Collapsed `NormalizedPolicy`: `world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'REJECT'))`, `ru_upper=2.0`, `max_actions_on_path=2`.

### Observed Behavior
Because `NormalizedPolicy` aggregates across worlds via `ResourceVector.max_across` and `max_actions_on_path = 1 + max(...)` (`dwaop_integrated_planner.py:1305,1328`; `dwaop_exhaustive_policy_oracle.py:350-354`), Tree 0's per-world advantage on `w0` (`1` action, `ru=1.0` vs. `2` actions, `ru=2.0`) is erased, and `_canonical_dedup` / `_oracle_pareto_reduce` drops Tree 0 (`max_actions_on_path=3`) in favor of Tree 1 (`max_actions_on_path=2`).

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import _SimState, _enumerate_trees, _evaluate_tree_on_world, enumerate_exact_pareto_frontier

def mk(aid, sk, obs, req_ob, req_cap, ru, disch, gain):
    lbls = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=frozenset({'w0', 'w1'}),
        observable_label_by_world=obs, required_capabilities=req_cap, required_obligations=req_ob,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'fail'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0, workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: OutcomeKind.SUCCESS for l in lbls},
        discharged_by_label=disch, capabilities_by_label=gain,
        retained_output_gb_by_label={l: 0.0 for l in lbls}, released_memory_gb_by_label={l: 0.0 for l in lbls},
        invalidates_model_by_label={l: False for l in lbls}, stale_evidence_by_label={l: False for l in lbls},
        retry_cost_by_label={l: 0 for l in lbls}, proof_id_by_label={l: f'p:{aid}:{l}' for l in lbls},
    )

u = frozenset({'w0', 'w1'})
oracle = WorldOracle(
    specification_id='ce5', model_id='m', assurance_scope='test', universe=u,
    decision_by_world={'w0': 'ACCEPT', 'w1': 'REJECT'}, initial_obligations=frozenset({'ob0', 'ob1'}),
    actions={
        'root_asym': mk('root_asym', 's1', {'w0': 'l', 'w1': 'r'}, frozenset({'ob0', 'ob1'}), frozenset(), 1.0,
                        {'l': frozenset({'ob0', 'ob1'}), 'r': frozenset({'ob0'})}, {'l': frozenset(), 'r': frozenset({'am1'})}),
        'asym_w1_a': mk('asym_w1_a', 's2', {'w0': 'ok', 'w1': 'ok'}, frozenset({'ob1'}), frozenset({'am1'}), 0.5,
                        {'ok': frozenset()}, {'ok': frozenset({'am2'})}),
        'asym_w1_b': mk('asym_w1_b', 's3', {'w0': 'ok', 'w1': 'ok'}, frozenset({'ob1'}), frozenset({'am2'}), 0.5,
                        {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
        'root_even': mk('root_even', 's4', {'w0': 'l', 'w1': 'r'}, frozenset({'ob0', 'ob1'}), frozenset(), 1.0,
                        {'l': frozenset({'ob0'}), 'r': frozenset({'ob0'})}, {'l': frozenset({'ev1'}), 'r': frozenset({'ev1'})}),
        'even_fin':  mk('even_fin', 's5', {'w0': 'ok', 'w1': 'ok'}, frozenset({'ob1'}), frozenset({'ev1'}), 1.0,
                        {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
    },
)
budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
root_s = _SimState(u, oracle.initial_obligations, frozenset(), frozenset(oracle.actions), 0, True, False, None)
trees = _enumerate_trees(root_s, oracle, 4)
print('trees:', len(trees))
for i, t in enumerate(trees):
    r0 = _evaluate_tree_on_world(t, 'w0', oracle, budget)
    r1 = _evaluate_tree_on_world(t, 'w1', oracle, budget)
    print(f'tree {i}: root={t.action_id} w0=(verdict={r0[0]}, ru={r0[1].ru_upper}, len={r0[2]}) w1=(verdict={r1[0]}, ru={r1[1].ru_upper}, len={r1[2]}) max_actions={max(r0[2], r1[2])}')
print('frontier:', enumerate_exact_pareto_frontier(oracle, budget, max_horizon=4))
"
```

---

### CE-5B: Internal `pareto_reduce` Breaks Bellman Optimality Under Sibling `max` (`unpruned != oracle`)

#### Construction
A 2-world (`w0 -> ACCEPT`, `w1 -> ACCEPT`) branching graph (`max_horizon=4`, `budget=(10, 10, 10, 10)`):
- `split` (`ru=0.0`) partitions `{"w0", "w1"}` into `w0` (`c0`) and `w1` (`c1`).
- On `w0`: only `w0_done` (`ru=2.0`, 1 step) is available (`L=1, ru=2.0`).
- On `w1`: two completions exist:
  - `w1_fast` (`ru=2.0`, 1 step -> `L=1, ru=2.0`)
  - `w1_s1 -> w1_s2 -> w1_s3` (`ru=0.5 + 0.5 + 0.0 = 1.0`, 3 steps -> `L=3, ru=1.0`).

#### Observed Divergence (`plan_policies(..., prune=False) != enumerate_exact_pareto_frontier`)
- Inside `plan_policies` (`dwaop_integrated_planner.py:1338`), `pareto_reduce` is applied at the internal `w1` OR-node: `(ru=1.0, L=3)` strictly dominates and **discards** `w1_fast` `(ru=2.0, L=1)`.
- When combined at `root` with `w0_done` `(ru=2.0, L=1)` via `max`:
  - `plan_policies(prune=True)` and `plan_policies(prune=False)` only see `(ru=max(2, 1)=2, L=1+max(1, 3)=4)`.
  - `enumerate_exact_pareto_frontier` reduces only at the root, sees both `(ru=2, L=2)` and `(ru=2, L=4)`, and `_oracle_pareto_reduce` keeps **`max_actions_on_path=2`**!

**Reproducible command (run from `f:/gdec-dwaop-v03`):**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier

def mk(aid, sk, app, obs, req_ob, req_cap, ru, disch, gain):
    lbls = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=app,
        observable_label_by_world=obs, required_capabilities=req_cap, required_obligations=req_ob,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'fail'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0, workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: OutcomeKind.SUCCESS for l in lbls},
        discharged_by_label=disch, capabilities_by_label=gain,
        retained_output_gb_by_label={l: 0.0 for l in lbls}, released_memory_gb_by_label={l: 0.0 for l in lbls},
        invalidates_model_by_label={l: False for l in lbls}, stale_evidence_by_label={l: False for l in lbls},
        retry_cost_by_label={l: 0 for l in lbls}, proof_id_by_label={l: f'p:{aid}:{l}' for l in lbls},
    )

u = frozenset({'w0', 'w1'})
oracle = WorldOracle(
    specification_id='ce5b', model_id='m', assurance_scope='test', universe=u,
    decision_by_world={'w0': 'ACCEPT', 'w1': 'ACCEPT'}, initial_obligations=frozenset({'ob0', 'ob1'}),
    actions={
        'split': mk('split', 'sp', u, {'w0': 'b0', 'w1': 'b1'}, frozenset({'ob0', 'ob1'}), frozenset(), 0.0,
                    {'b0': frozenset({'ob0'}), 'b1': frozenset({'ob0'})}, {'b0': frozenset({'c0'}), 'b1': frozenset({'c1'})}),
        'w0_done': mk('w0_done', 'd0', frozenset({'w0'}), {'w0': 'ok'}, frozenset({'ob1'}), frozenset({'c0'}), 2.0,
                      {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
        'w1_fast': mk('w1_fast', 'd1f', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'c1'}), 2.0,
                      {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
        'w1_s1': mk('w1_s1', 'd1s1', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'c1'}), 0.5,
                    {'ok': frozenset()}, {'ok': frozenset({'s2'})}),
        'w1_s2': mk('w1_s2', 'd1s2', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'s2'}), 0.5,
                    {'ok': frozenset()}, {'ok': frozenset({'s3'})}),
        'w1_s3': mk('w1_s3', 'd1s3', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'s3'}), 0.0,
                    {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
    },
)
budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
rp = plan_policies(oracle, budget, max_horizon=4, prune=True)
ru = plan_policies(oracle, budget, max_horizon=4, prune=False)
ro = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=4)
print('pruned  :', rp.pareto_frontier)
print('unpruned:', ru.pareto_frontier)
print('oracle  :', ro)
print('unpruned == oracle:', ru.pareto_frontier == ro)
"
```

---

## CE-6 (Q7): State-Level Pruning Drops a Frontier Policy

### Root Cause in `dwaop_integrated_planner.py`
In `plan_policies` (`dwaop_integrated_planner.py:1227-1232`) and `_enumerate_trees` (`dwaop_exhaustive_policy_oracle.py:113-120`), `OutcomeKind.UNRECOVERABLE_REFUSAL` is **sticky**: the planner immediately returns `(leaf_REFUSE,)` without expanding any recovery action.

However, in `is_local_refinement` (`dwaop_integrated_planner.py:863-886`):
1. When `coarse_term == "REFUSE"` and `coarse_sticky` is `False` (non-sticky `TIMEOUT` / `INCONCLUSIVE` / `NUMERICAL_BREAKDOWN` / `RESOURCE_EXHAUSTION` / `BACKEND_FAILURE`), lines `867-873` check only `coarse_sticky` — **never** `fine_sticky` (`fine_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`).
2. It falls through to lines `899-929`, calling `_enabled(fine_state, left_action, oracle)` (`lines 642-664`), which **does not check `state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`**.
3. `apply_action_outcome(fine_state, left_action, oracle)` produces a child transition `lt` whose `last_outcome_kind` is overwritten by `OutcomeKind.SUCCESS`, erasing the sticky `UNRECOVERABLE_REFUSAL` and reaching `ACCEPT`.
4. `is_local_refinement` and `is_complete_refinement_cover` both return **`True`**, causing `plan_policies(..., prune=True)` to prune the non-sticky `coarse` branch — even though `fine` cannot actually execute recovery in `plan_policies`!

### CE-6A: Minimal 1-World, 3-Action, Horizon-2 Counterexample (`UNRECOVERABLE_REFUSAL`)
- **Inputs:**
  - `universe = frozenset({"w0"})`, `decision_by_world = {"w0": "ACCEPT"}`, `initial_obligations = frozenset({"ob"})`, `budget = ResourceBudget(10, 10, 10, 10)`, `max_horizon = 2`.
  - `a_fine`: `semantic_key="probe"`, `ru_upper=1.0`, `OutcomeKind.UNRECOVERABLE_REFUSAL`, gains `{"probed"}`.
  - `b_coarse`: `semantic_key="probe"`, `ru_upper=1.0`, `OutcomeKind.TIMEOUT`, gains `{"probed"}`.
  - `recover`: `semantic_key="rec"`, `ru_upper=0.0`, `required_capabilities={"probed"}`, `OutcomeKind.SUCCESS`, discharges `{"ob"}`.
  - *(Note: because both `a_fine` and `b_coarse` have `1` outcome and equal `ru_upper=1.0`, `a_fine` expands before `b_coarse` via alphabetical `action_id` tie-breaking `'a_fine' < 'b_coarse'` in `candidate_groups.sort`. **CE-6B** and **CE-6C** remove this alphabetical ordering dependency via `-len(item[1])`.)*
- **Expected output (`unpruned` / `oracle`):** `(NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(1, 0, 0, 0), frozenset({'ACCEPT'}), 2),)` (which strictly dominates `REFUSE` at `ru=1`).
- **Actual observed outputs:**
  - `is_local_refinement(fc, cc, contracts, oracle, depth_left=1) == True`
  - `is_complete_refinement_cover([fc], cc, contracts, oracle, budget, depth_left=1) == True`
  - `plan_policies(..., prune=True)` -> `successful_prunes=1`, frontier is **`((('w0', 'REFUSE'),), ResourceVector(1, 0, 0, 0), max_actions=1)`**!
  - `plan_policies(..., prune=False)` -> frontier is **`((('w0', 'ACCEPT'),), ResourceVector(1, 0, 0, 0), max_actions=2)`**.
  - `enumerate_exact_pareto_frontier` -> frontier is **`((('w0', 'ACCEPT'),), ResourceVector(1, 0, 0, 0), max_actions=2)`**.

**Reproducible command:**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import (
    ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle,
    apply_action_outcome, build_action_contract,
    is_complete_refinement_cover, is_local_refinement,
    make_initial_state, plan_policies,
)
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier

def mk(aid, sk, obs, req_ob, req_cap, ru, kind, disch, gain):
    lbls = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=frozenset({'w0'}),
        observable_label_by_world=obs, required_capabilities=req_cap, required_obligations=req_ob,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'fail'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0, workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: kind for l in lbls}, discharged_by_label={l: disch for l in lbls},
        capabilities_by_label={l: gain for l in lbls}, retained_output_gb_by_label={l: 0.0 for l in lbls},
        released_memory_gb_by_label={l: 0.0 for l in lbls}, invalidates_model_by_label={l: False for l in lbls},
        stale_evidence_by_label={l: False for l in lbls}, retry_cost_by_label={l: 0 for l in lbls},
        proof_id_by_label={l: f'p:{aid}:{l}' for l in lbls},
    )

oracle = WorldOracle(
    specification_id='q7-1w', model_id='m', assurance_scope='test',
    universe=frozenset({'w0'}), decision_by_world={'w0': 'ACCEPT'}, initial_obligations=frozenset({'ob'}),
    actions={
        'a_fine': mk('a_fine', 'probe', {'w0': 'fail'}, frozenset({'ob'}), frozenset(), 1.0, OutcomeKind.UNRECOVERABLE_REFUSAL, frozenset(), frozenset({'probed'})),
        'b_coarse': mk('b_coarse', 'probe', {'w0': 'to'}, frozenset({'ob'}), frozenset(), 1.0, OutcomeKind.TIMEOUT, frozenset(), frozenset({'probed'})),
        'recover': mk('recover', 'rec', {'w0': 'ok'}, frozenset({'ob'}), frozenset({'probed'}), 0.0, OutcomeKind.SUCCESS, frozenset({'ob'}), frozenset()),
    },
)
budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
root = make_initial_state(oracle)
fc = apply_action_outcome(root, contracts['a_fine'], oracle)[0].state
cc = apply_action_outcome(root, contracts['b_coarse'], oracle)[0].state
print('is_local_refinement:', is_local_refinement(fc, cc, contracts, oracle, depth_left=1))
print('is_complete_refinement_cover:', is_complete_refinement_cover([fc], cc, contracts, oracle, budget, depth_left=1))
rp = plan_policies(oracle, budget, max_horizon=2, prune=True)
ru = plan_policies(oracle, budget, max_horizon=2, prune=False)
ro = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=2)
print('successful_prunes:', rp.metrics.successful_prunes)
print('pruned  :', rp.pareto_frontier)
print('unpruned:', ru.pareto_frontier)
print('oracle  :', ro)
"
```

### CE-6B: Action-Name-Independent 2-World Branching Variant
When `fine_probe` splits `{"w0", "w1"}` into `w0 -> TIMEOUT` and `w1 -> UNRECOVERABLE_REFUSAL` (`2` outcomes, `ru=1.0`), `candidate_groups.sort` (`dwaop_integrated_planner.py:1255`, sorting by `-len(item[1])` before `action_id`) always expands `fine_probe` before 1-outcome `coarse_probe` (`{"w0", "w1"} -> TIMEOUT`, `ru=1.0`), regardless of alphabetical naming. With `recover` (`ru=0.5`, `required_capabilities={"probed"}`, discharges `{"ob"}`):
- `is_local_refinement(w0_to, coarse, depth_left=1) == True`
- `is_local_refinement(w1_unrec, coarse, depth_left=1) == True`
- `is_complete_refinement_cover([w0_to, w1_unrec], coarse, depth_left=1) == True`
- `plan_policies(..., prune=True)` outputs `(('w0', 'ACCEPT'), ('w1', 'REFUSE')) @ ru=1.5` and `(('w0', 'REFUSE'), ('w1', 'REFUSE')) @ ru=1.0`.
- `plan_policies(..., prune=False)` and `enumerate_exact_pareto_frontier` output `(('w0', 'ACCEPT'), ('w1', 'ACCEPT')) @ ru=1.5` and `(('w0', 'REFUSE'), ('w1', 'REFUSE')) @ ru=1.0`.

### CE-6C: `SUCCESS`-Only, Action-Name-Independent Counterexample (`pruned != unpruned == oracle`)
Even when every outcome is `OutcomeKind.SUCCESS` (no failures/refusals at all), complete-cover pruning combined with internal `pareto_reduce` drops the tie-break-winning shorter policy:
- **Inputs (`universe = {"w0", "w1"}`, `decision = ACCEPT` on both, `initial_obligations = {"ob0", "ob1"}`, `max_horizon = 4`, `budget = (10, 10, 10, 10)`):**
  - `fine_split`: `semantic_key="sp"`, `ru_upper=0.0`, splits `{"w0", "w1"}` into `w0` (`b0`) and `w1` (`b1`), discharges `{"ob0"}`, gains `{"probed"}` (`2` outcomes -> expands first regardless of `action_id`).
  - `coarse_step`: `semantic_key="sp"`, `ru_upper=0.0`, single outcome `c` covering `{"w0", "w1"}`, discharges `{"ob0"}`, gains `{"probed"}`.
  - `both_fast`: `ru_upper=2.0`, applicable to `{"w0", "w1"}`, requires `{"probed"}`, discharges `{"ob1"}` in `1` step.
  - `w1_s1 -> w1_s2 -> w1_s3`: applicable to `{"w1"}` only, total `ru_upper = 0.5 + 0.5 + 0.0 = 1.0`, discharges `{"ob1"}` in `3` steps.
- **Mechanism:**
  - `is_complete_refinement_cover` returns `True` (`fine_split` simulates `both_fast` on both `w0` and `w1` at `ru=2.0`), so `plan_policies(..., prune=True)` **prunes `coarse_step`** (`successful_prunes=1`).
  - On `fine_split`'s `w1` branch, internal `pareto_reduce` drops `both_fast` (`ru=2.0, L=1`) in favor of `w1_s1->w1_s2->w1_s3` (`ru=1.0, L=3`), so `prune=True` only obtains `ru=max(2, 1)=2, max_actions_on_path=4`.
  - Without pruning (`prune=False`), `coarse_step`'s child keeps `both_fast` directly (`ru=2.0, L=1`), yielding `max_actions_on_path=2` (`unpruned == oracle`), while `pruned != unpruned`.
- **Actual observed outputs:**
  - `successful_prunes: 1`
  - `pruned  :` `(NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'ACCEPT')), ResourceVector(2, 0, 0, 0), frozenset({'ACCEPT'}), 4),)`
  - `unpruned:` `(NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'ACCEPT')), ResourceVector(2, 0, 0, 0), frozenset({'ACCEPT'}), 2),)`
  - `oracle  :` `(NormalizedPolicy((('w0', 'ACCEPT'), ('w1', 'ACCEPT')), ResourceVector(2, 0, 0, 0), frozenset({'ACCEPT'}), 2),)`

**Reproducible command (run from `f:/gdec-dwaop-v03`):**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier

def mk(aid, sk, app, obs, req_ob, req_cap, ru, disch, gain):
    lbls = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=app,
        observable_label_by_world=obs, required_capabilities=req_cap, required_obligations=req_ob,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'fail'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0, workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: OutcomeKind.SUCCESS for l in lbls},
        discharged_by_label=disch, capabilities_by_label=gain,
        retained_output_gb_by_label={l: 0.0 for l in lbls}, released_memory_gb_by_label={l: 0.0 for l in lbls},
        invalidates_model_by_label={l: False for l in lbls}, stale_evidence_by_label={l: False for l in lbls},
        retry_cost_by_label={l: 0 for l in lbls}, proof_id_by_label={l: f'p:{aid}:{l}' for l in lbls},
    )

u = frozenset({'w0', 'w1'})
oracle = WorldOracle(
    specification_id='ce6c-success-only', model_id='m', assurance_scope='test', universe=u,
    decision_by_world={'w0': 'ACCEPT', 'w1': 'ACCEPT'}, initial_obligations=frozenset({'ob0', 'ob1'}),
    actions={
        'fine_split': mk('fine_split', 'sp', u, {'w0': 'b0', 'w1': 'b1'}, frozenset({'ob0', 'ob1'}), frozenset(), 0.0,
                         {'b0': frozenset({'ob0'}), 'b1': frozenset({'ob0'})}, {'b0': frozenset({'probed'}), 'b1': frozenset({'probed'})}),
        'coarse_step': mk('coarse_step', 'sp', u, {'w0': 'c', 'w1': 'c'}, frozenset({'ob0', 'ob1'}), frozenset(), 0.0,
                          {'c': frozenset({'ob0'})}, {'c': frozenset({'probed'})}),
        'both_fast': mk('both_fast', 'fin', u, {'w0': 'ok', 'w1': 'ok'}, frozenset({'ob1'}), frozenset({'probed'}), 2.0,
                        {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
        'w1_s1': mk('w1_s1', 'd1s1', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'probed'}), 0.5,
                    {'ok': frozenset()}, {'ok': frozenset({'s2'})}),
        'w1_s2': mk('w1_s2', 'd1s2', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'s2'}), 0.5,
                    {'ok': frozenset()}, {'ok': frozenset({'s3'})}),
        'w1_s3': mk('w1_s3', 'd1s3', frozenset({'w1'}), {'w1': 'ok'}, frozenset({'ob1'}), frozenset({'s3'}), 0.0,
                    {'ok': frozenset({'ob1'})}, {'ok': frozenset()}),
    },
)
budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
rp = plan_policies(oracle, budget, max_horizon=4, prune=True)
ru = plan_policies(oracle, budget, max_horizon=4, prune=False)
ro = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=4)
print('successful_prunes:', rp.metrics.successful_prunes)
print('pruned  :', rp.pareto_frontier)
print('unpruned:', ru.pareto_frontier)
print('oracle  :', ro)
print('pruned == unpruned:', rp.pareto_frontier == ru.pareto_frontier, 'unpruned == oracle:', ru.pareto_frontier == ro)
"
```

### Bounded Fuzzing Scope Note (`max_horizon=3`, Excluding `UNRECOVERABLE_REFUSAL`)
Across `300` seeded random `2`- and `3`-world graphs at `max_horizon=3` (`seed=42`, `OutcomeKind` restricted to `{SUCCESS, TIMEOUT, INCONCLUSIVE, MODEL_INVALIDATED, STALE_EVIDENCE, BOUNDED_RETRY}`, excluding `UNRECOVERABLE_REFUSAL`), `58` successful prunes occurred with `0` frontier divergences (`plan_policies(prune=True) == plan_policies(prune=False) == enumerate_exact_pareto_frontier`). As shown by **CE-6C**, `max_horizon=3` with 4-action random pools was too shallow to expose the `SUCCESS`-only horizon-4 split + 3-step-vs-1-step Bellman/pruning interaction (`horizon >= 4` in CE-6C). Thus Q7 has **two** distinct triggers: (1) missing `UNRECOVERABLE_REFUSAL` stickiness check in `is_local_refinement` / `_enabled` (CE-6A/6B, diverging even at `horizon=2` on verdict lattice), and (2) internal `pareto_reduce` breaking Bellman optimality under sibling `max` combined with complete-cover pruning (CE-6C, diverging at `horizon=4` on `max_actions_on_path` even for `SUCCESS`-only graphs).
