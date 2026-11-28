# DWAOP v0.3 — Independent Technical & Proof-Obligation Review (`DWAOP_HYDROGEN_INDEPENDENT_REVIEW`)

**Repository:** `f:/gdec-dwaop-v03`  
**Audited Commit:** `2812b000ea0241a3aee2b5580444a7e1767c3417`  
**Python Environment:** `f:/fem-edit-benchmark/.venv/Scripts/python.exe` (Python `3.13.14`)  
**Scope:** Stage 1 read-only independent audit (zero source or test modifications).

---

## 1. Executive Verdict

Independent audit of [`dwaop_integrated_planner.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py), [`dwaop_exhaustive_policy_oracle.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py), and [`dwaop_horizon_ladder.py`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_horizon_ladder.py) establishes that **the current v0.3 equivalence claim ($\mathcal{P}_{\text{pruned}} = \mathcal{P}_{\text{unpruned}} = \mathcal{P}_{\text{oracle}}$) holds only on restricted graph classes (such as the H6/H8 ladder) and fails on general finite deterministic graphs due to two independent soundness/consistency defects, alongside a severe implementation-level runtime bottleneck:**

1. **Defect 1 — Unsound Sticky-Refusal Pruning (`UNRECOVERABLE_REFUSAL` vs. `TIMEOUT`):** `is_local_refinement` ([`dwaop_integrated_planner.py#L848-L886`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L848-L886)) checks `model_valid` and `evidence_stale` stickiness, but **omits `last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`**, and `_enabled` ([`#L642-L664`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L642-L664)) does not block transitions out of sticky refusal states. Consequently, `plan_policies(..., prune=True)` can prune a recoverable `TIMEOUT` coarse branch using a sticky `UNRECOVERABLE_REFUSAL` fine branch and **drop the dominating `ACCEPT`/`REJECT` Pareto policy completely** (Counterexample **E1**). Additionally, standalone `_evaluate_tree_on_world` ([`dwaop_exhaustive_policy_oracle.py#L204-L270`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py#L204-L270)) overwrites `last_kind` at line 255 without rejecting transitions after `UNRECOVERABLE_REFUSAL`.
2. **Defect 2 — Bellman Non-Monotonicity on `max_actions_on_path` Tie-Breaking (`SUCCESS`-only graphs):** `_policy_dominates` ([`#L1087-L1098`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1087-L1098)) ignores `max_actions_on_path`, whereas `_canonical_dedup` ([`#L1101-L1121`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1101-L1121)), `_oracle_pareto_reduce` ([`dwaop_exhaustive_policy_oracle.py#L299-L311`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_exhaustive_policy_oracle.py#L299-L311)), and `NormalizedPolicy` frontier equality require keeping minimum `max_actions_on_path` on exact `(world_verdict_map, terminal_verdicts, resource_vector)` ties. Because `plan_policies` calls `pareto_reduce` at every internal OR node (`#L1236, #L1338`), a strictly cheaper-resource longer child continuation can evict a costlier shorter witness whose extra resource cost is later masked by a sibling branch under `ResourceVector.max_across`. This breaks **both** `pruned == unpruned` (Counterexample **E2A**) and `unpruned == oracle` (Counterexample **E2B**).
3. **H6/H8 Benchmark Assessment:** The H6/H8 refinement ladder ([`dwaop_horizon_ladder.py#L39-L84`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_horizon_ladder.py#L39-L84)) is a strictly dominated single-chain ladder with `frontier_size == 1`, zero `REFUSE` outcomes, no splitting after stage 0, and uniform path length `n_stages + 1`, so it **never exercises** Defects 1–2. Its `7.41×` (H6) and `7.56×` (H8) pruning slowdown is dominated by repeated `validate_oracle()` / `_nonnegative()` regex-to-`Fraction` re-parsing (`80.7%` of H5 runtime in `cProfile`) and repeated root-to-node `verify_state_provenance()` walks inside `is_local_refinement`'s `2^(S+3)-2S-8` simulation tree.

**Stage 1 Baseline Verification:** `tests/research/test_dwaop_mutations.py` passed (`23 passed in 0.51s`), confirming that the existing 23 targeted mutation tests do not cover either Defect 1 (`UNRECOVERABLE_REFUSAL` vs. `TIMEOUT` in `is_local_refinement`) or Defect 2 (sibling `max`-masking of `max_actions_on_path`).

---

## 2. Independent Audit of Planner, Oracle, and H6/H8 Benchmark

### 2.1 Integrated Planner (`dwaop_integrated_planner.py`)
- **Exact rational arithmetic & budget checking:** `_nonnegative` (`#L30-L44`) converts numeric inputs via `Fraction(str(value))` and rejects `bool`, `NaN`, `Inf`, and `< 0`. `ResourceBudget.allows` (`#L177-L184`) and `ResourceVector.dominates_or_equal` / `strictly_dominates` (`#L127-L147`) default to `tol=0.0`, and `total_vec` at `#L1312-L1319` correctly checks root-to-leaf worst-case additive and peak-memory budgets.
- **Sticky vs. non-sticky refusal asymmetry:** `_search` (`#L1227-L1232`) treats three conditions as sticky `REFUSE` (immediate return of `(leaf,)`): `not state.model_valid`, `state.evidence_stale`, and `state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`. However:
  - `_enabled` (`#L642-L664`) checks none of these three stickiness flags.
  - `is_local_refinement` (`#L848-L849`) checks `model_valid` and `evidence_stale`, and `#L867-L873` checks `coarse_sticky` (which includes `UNRECOVERABLE_REFUSAL`), but **never** rejects `fine_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL` when `coarse_sticky` is `False`.
- **Internal `pareto_reduce` & telemetry note:** `_search` calls `pareto_reduce(complete_here)` at every recursive node (`#L1236, #L1338`), so `PlannerResult.complete_policies` (`#L1359`) actually holds the root-propagated reduced set rather than unreduced complete policies, and `complete_policies_enumerated` counts sub-policies constructed at internal nodes as well as leaves.

### 2.2 Exhaustive Policy Oracle (`dwaop_exhaustive_policy_oracle.py`)
- **Independence boundary:** The oracle imports contract dataclasses, `OutcomeKind`, `FAILURE_OR_INCONCLUSIVE_KINDS`, `ResourceVector`, `ResourceBudget`, `WorldOracle`, `validate_oracle`, and `validate_resource_budget` from `dwaop_integrated_planner.py` (`#L16-L36`), while independently implementing tree enumeration (`_enumerate_trees`, `#L100-L176`), single-world simulation (`_evaluate_tree_on_world`, `#L179-L272`), and Pareto reduction (`_oracle_dominates`, `_oracle_pareto_reduce`, `#L286-L311`).
- **Objective equivalence (Q6):** `_oracle_dominates` and `_oracle_pareto_reduce` replicate the exact mathematical specification of `_policy_dominates` and `_canonical_dedup`: dominance ignores `max_actions_on_path` and tie-breaks exact `(world_verdict_map, terminal_verdicts, resource_vector)` collisions by minimum `max_actions_on_path`. Thus, the oracle **cannot** detect if `max_actions_on_path` was intended to be a 5th primary Pareto objective, **but** because it reduces only once at the root over all enumerated trees, it genuinely catches planner-side defects (both Defect 1 and Defect 2).
- **Standalone `_evaluate_tree_on_world` gap:** `_enumerate_trees` (`#L114-L119`) halts on sticky `UNRECOVERABLE_REFUSAL`, so `enumerate_exact_pareto_frontier` never produces a recovery tree below `UNRECOVERABLE_REFUSAL`. However, `_evaluate_tree_on_world` (`#L204-L270`) does not check sticky refusal flags inside its `while isinstance(node, ActionBranch):` loop and overwrites `last_kind` at `#L255`, so if invoked directly on a synthetic tree `UNRECOVERABLE_REFUSAL -> recover -> ACCEPT`, it falsely returns `ACCEPT` (verified in Section 3).

### 2.3 H6/H8 Refinement-Ladder Benchmark (`dwaop_horizon_ladder.py`)
- **Coverage limits:** In `build_refinement_ladder(n_stages)` (`#L39-L84`), only stage `0` (`fine_stage_0`) splits worlds (`group_0` vs. `group_1`); stages `1..n_stages-1` are single-cell non-splitting actions (`same_cell` vs. `coarse_cell`); every `fine_stage_i` strictly halves every cost component of `coarse_stage_i`; all actions have `OutcomeKind.SUCCESS`; and every complete policy has identical `max_actions_on_path = n_stages + 1` with `pareto_frontier_size == 1`. Consequently, H6/H8 leaves multi-entry Pareto frontiers, incomparable trade-offs, failure/recovery semantics, and variable path lengths completely untested.
- **Independent H5 `cProfile` verification (`n_stages=4`, `max_horizon=5`, `32` worlds):**
  - `states_expanded=13`, `dominance_checks=7`, `successful_prunes=7`, `total_runtime_sec=47.849s` (`dominance_check_time_sec=46.401s`, `97.0%`).
  - Function call amplification observed directly: `is_complete_refinement_cover`: `7`; `is_local_refinement`: `112` (`8` top-level); `verify_state_provenance`: `1,230` (`239` top-level); `_enabled`: `1,873`; `verify_action_contract`: `1,887` (`44.831s` cumtime); `validate_oracle`: `1,898` (`38.614s` cumtime = `80.7%` of runtime); `_nonnegative`: `175,602` (`36.579s` cumtime); `Fraction.__new__`: `152,493` (`29.501s` cumtime, driven by regex parsing of raw `float` fields in `ActionSemantics`).
  - Why H6/H8 runs `7.41×` / `7.56×` slower despite `92.11%` / `97.52%` state reduction: at each stage `i >= 1`, `coarse_enabled` contains both `fine_stage_i` and `coarse_stage_i`, causing `is_local_refinement` to branch by factor `2` per remaining stage while re-walking provenance to root and re-validating the entire `WorldOracle` on every transition check.

---

## 3. Independent Counterexamples (Reproducible on Commit `2812b00`)

All three counterexamples were executed directly against commit `2812b000ea0241a3aee2b5580444a7e1767c3417` with zero file modifications:

| ID | Trigger / Mechanism | Observed Divergence |
|---|---|---|
| **E1** | `a_fine` (`UNRECOVERABLE_REFUSAL`, `ru=1.0`, splits `w0, w1`, gains `cap_op`) vs. `a_coarse` (`TIMEOUT`, `ru=1.0`, merges `w0, w1`, gains `cap_op`) + `recover` (`ru=1.0`, requires `cap_op`). | `successful_prunes=1`; `pruned` drops `(('w0', 'ACCEPT'), ('w1', 'REJECT'))` and returns **only** `(('w0', 'REFUSE'), ('w1', 'REFUSE'))` at `ru=1, L=1`. `unpruned == oracle` returns both `(ACCEPT, REJECT)` at `ru=2, L=2` and `(REFUSE, REFUSE)` at `ru=1, L=1`. Standalone `_evaluate_tree_on_world` on `a_fine -> recover -> ACCEPT` falsely returns `('ACCEPT', ResourceVector(2, 2, 2, 1/10), 2)`. |
| **E2A** | `SUCCESS`-only, 2 worlds, `max_horizon=4`. `a_fine` (`ru=1.0`, splits `w0, w1`) and `a_coarse` (`ru=1.0`, merges `w0, w1`) both discharge `ob_init` and gain `cap_init`. Under `w0`, `cheat_1 -> cheat_2` (`ru=0.5, L=2`) dominates `leaf_op` (`ru=1.0, L=1`) in `pareto_reduce`, while `w1` uses `leaf_op` (`ru=1.0, L=1`). | `successful_prunes=1`; `pruned` returns `max_actions_on_path=3` at `ru=2`, whereas `unpruned == oracle` returns **`max_actions_on_path=2`** at `ru=2` (`pruned != unpruned == oracle`). |
| **E2B** | Same graph as **E2A** with `a_coarse` removed (`no pruning possible`). | `pruned == unpruned` returns `max_actions_on_path=3` at `ru=2`, whereas `oracle` returns **`max_actions_on_path=2`** at `ru=2` (`unpruned != oracle`). |

**Reproducible command (run from `f:/gdec-dwaop-v03`):**
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'f:/gdec-dwaop-v03')
from research.prototypes.dwaop_integrated_planner import (
    ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
)
from research.prototypes.dwaop_exhaustive_policy_oracle import (
    enumerate_exact_pareto_frontier, LeafVerdict, ActionBranch, _evaluate_tree_on_world
)

def mk(aid, skey, app_worlds, obs, kinds, ru=1.0, req_obs=frozenset(), req_caps=frozenset(), disch=None, gained=None):
    labels = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=skey, applicable_worlds=app_worlds,
        observable_label_by_world=obs,
        required_capabilities=req_caps, required_obligations=req_obs,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'fs'}),
        ru_upper=ru, cpu_ticks=ru, energy_ticks=ru,
        workspace_gb_upper=0.1, overlap_gb_upper=0.0,
        outcome_kind_by_label=kinds,
        discharged_by_label=disch or {l: frozenset() for l in labels},
        capabilities_by_label=gained or {l: frozenset() for l in labels},
        retained_output_gb_by_label={l: 0.0 for l in labels},
        released_memory_gb_by_label={l: 0.0 for l in labels},
        invalidates_model_by_label={l: False for l in labels},
        stale_evidence_by_label={l: False for l in labels},
        retry_cost_by_label={l: 0 for l in labels},
        proof_id_by_label={l: 'p:' + aid + ':' + l for l in labels},
    )

u2 = frozenset({'w0', 'w1'})
d2 = {'w0': 'ACCEPT', 'w1': 'REJECT'}
b = ResourceBudget(10.0, 100.0, 100.0, 10.0)

o1 = WorldOracle(
    specification_id='e1', model_id='m', assurance_scope='a', universe=u2, decision_by_world=d2,
    actions={
        'a_fine': mk('a_fine', 'op', u2, {'w0': 'u0', 'w1': 'u1'}, {'u0': OutcomeKind.UNRECOVERABLE_REFUSAL, 'u1': OutcomeKind.UNRECOVERABLE_REFUSAL}, ru=1.0, gained={'u0': frozenset({'cap_op'}), 'u1': frozenset({'cap_op'})}),
        'a_coarse': mk('a_coarse', 'op', u2, {'w0': 'c', 'w1': 'c'}, {'c': OutcomeKind.TIMEOUT}, ru=1.0, gained={'c': frozenset({'cap_op'})}),
        'recover': mk('recover', 'rec', u2, {'w0': 'r0', 'w1': 'r1'}, {'r0': OutcomeKind.SUCCESS, 'r1': OutcomeKind.SUCCESS}, ru=1.0, req_caps=frozenset({'cap_op'})),
    }
)
e1_p, e1_u, e1_o = plan_policies(o1, b, max_horizon=4, prune=True), plan_policies(o1, b, max_horizon=4, prune=False), enumerate_exact_pareto_frontier(o1, b, max_horizon=4)
print('E1 prunes:', e1_p.metrics.successful_prunes, 'pruned==unpruned:', e1_p.pareto_frontier == e1_u.pareto_frontier, 'unpruned==oracle:', e1_u.pareto_frontier == e1_o)
bad_tree = ActionBranch('a_fine', {'u0': ActionBranch('recover', {'r0': LeafVerdict('ACCEPT')}), 'u1': ActionBranch('recover', {'r1': LeafVerdict('REJECT')})})
print('E1 standalone _evaluate_tree_on_world(w0):', _evaluate_tree_on_world(bad_tree, 'w0', o1, b))

o2a = WorldOracle(
    specification_id='e2a', model_id='m', assurance_scope='a', universe=u2, decision_by_world=d2,
    initial_obligations=frozenset({'ob_init', 'ob_leaf'}),
    actions={
        'a_fine': mk('a_fine', 'op', u2, {'w0': 'l0', 'w1': 'l1'}, {'l0': OutcomeKind.SUCCESS, 'l1': OutcomeKind.SUCCESS}, ru=1.0, req_obs=frozenset({'ob_init'}), disch={'l0': frozenset({'ob_init'}), 'l1': frozenset({'ob_init'})}, gained={'l0': frozenset({'cap_init'}), 'l1': frozenset({'cap_init'})}),
        'a_coarse': mk('a_coarse', 'op', u2, {'w0': 'c', 'w1': 'c'}, {'c': OutcomeKind.SUCCESS}, ru=1.0, req_obs=frozenset({'ob_init'}), disch={'c': frozenset({'ob_init'})}, gained={'c': frozenset({'cap_init'})}),
        'leaf_op': mk('leaf_op', 'leaf', u2, {'w0': 'd0', 'w1': 'd1'}, {'d0': OutcomeKind.SUCCESS, 'd1': OutcomeKind.SUCCESS}, ru=1.0, req_obs=frozenset({'ob_leaf'}), req_caps=frozenset({'cap_init'}), disch={'d0': frozenset({'ob_leaf'}), 'd1': frozenset({'ob_leaf'})}),
        'cheat_1': mk('cheat_1', 'c1', frozenset({'w0'}), {'w0': 'c1'}, {'c1': OutcomeKind.SUCCESS}, ru=0.5, req_obs=frozenset({'ob_leaf'}), req_caps=frozenset({'cap_init'}), gained={'c1': frozenset({'cap_w0'})}),
        'cheat_2': mk('cheat_2', 'c2', frozenset({'w0'}), {'w0': 'c2'}, {'c2': OutcomeKind.SUCCESS}, ru=0.0, req_obs=frozenset({'ob_leaf'}), req_caps=frozenset({'cap_init', 'cap_w0'}), disch={'c2': frozenset({'ob_leaf'})}),
    }
)
e2a_p, e2a_u, e2a_o = plan_policies(o2a, b, max_horizon=4, prune=True), plan_policies(o2a, b, max_horizon=4, prune=False), enumerate_exact_pareto_frontier(o2a, b, max_horizon=4)
print('E2A prunes:', e2a_p.metrics.successful_prunes, 'pruned==unpruned:', e2a_p.pareto_frontier == e2a_u.pareto_frontier, 'unpruned==oracle:', e2a_u.pareto_frontier == e2a_o)

o2b = WorldOracle(specification_id='e2b', model_id='m', assurance_scope='a', universe=u2, decision_by_world=d2, initial_obligations=frozenset({'ob_init', 'ob_leaf'}), actions={k: v for k, v in o2a.actions.items() if k != 'a_coarse'})
e2b_p, e2b_u, e2b_o = plan_policies(o2b, b, max_horizon=4, prune=True), plan_policies(o2b, b, max_horizon=4, prune=False), enumerate_exact_pareto_frontier(o2b, b, max_horizon=4)
print('E2B pruned==unpruned:', e2b_p.pareto_frontier == e2b_u.pareto_frontier, 'unpruned==oracle:', e2b_u.pareto_frontier == e2b_o)
"
```

---

## 4. Proof-Obligation Checklist

### 4.1 Policy Dominance Proof Obligations
| Proof Obligation | Code Location | Status | Notes |
|---|---|---|---|
| Verdict order $\preceq_V$ (`ACCEPT`, `REJECT` $\prec$ `REFUSE`) is a valid partial order | [`#L1081-L1084`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1081-L1084) | **Satisfied** | Reflexive, antisymmetric, transitive. |
| Exact 4D `ResourceVector` dominance (`tol=0.0`) | [`#L127-L152`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L127-L152) | **Satisfied** | Exact `Fraction` tuple comparison; no rounding slack. |
| Monotonicity of $(V, R)$ under AND-composition (`+`, `max`, budget) | [`#L1304-L1329`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1304-L1329) | **Satisfied for $(V, R)$ only** | Addition and `max` preserve component-wise `<=` and downward-closed `budget.allows`. |
| Monotonicity of `pareto_reduce` (w/ `min max_actions_on_path` tie-break) at internal OR nodes | [`#L1101-L1134`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1101-L1134), [`#L1236, #L1338`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1236) | **FAILED** | Lexicographic $(V, R) \succ L$ is **not** monotone under sibling `max_across` (Counterexamples **E2A/E2B**). |
| Canonical dedup key minimality | [`#L1104-L1108`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1104-L1108) | **Minor defect** | `terminal_verdicts` in the dedup key is redundant for planner/oracle outputs and allows malformed synthetic duplicates to bypass dedup. |

### 4.2 State Refinement Proof Obligations (`is_local_refinement` & `is_complete_refinement_cover`)
| Proof Obligation | Code Location | Status | Notes |
|---|---|---|---|
| Scope, world containment, disjoint exhaustive sibling partition | [`#L840-L844`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L840-L844), [`#L1005-L1072`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1005-L1072) | **Satisfied** | Conservatively restricted to non-splitting coarse transitions (`parent.worlds == coarse_state.worlds`). |
| Monotonic obligations, capabilities, retries, resources, resident memory | [`#L845-L851`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L845-L851), [`#L808-L823`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L808-L823) | **Satisfied** | Exact `Fraction` checks on action upper bounds and state ledgers. |
| Sticky refusal preservation (`model_valid`, `evidence_stale`, `UNRECOVERABLE_REFUSAL`) | [`#L848-L849`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L848-L849), [`#L863-L886`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L863-L886), [`#L642-L664`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L642-L664) | **FAILED** | `UNRECOVERABLE_REFUSAL` stickiness omitted in `is_local_refinement` and `_enabled` (Counterexample **E1**). |
| Complete-frontier preservation under `pareto_reduce` + pruning | [`#L1269-L1338`](file:///f:/gdec-dwaop-v03/research/prototypes/dwaop_integrated_planner.py#L1269-L1338) | **FAILED** | `is_local_refinement` checks depth preservation, but internal `pareto_reduce` discards the simulated short-path witness (Counterexample **E2A**). |

---

## 5. Summary of Peer Challenges (Agents A–D) and Verified Resolutions

| Agent & Report | Challenges Raised (`#9, #12, #15, #18`) | Resolution (`#10, #13, #16, #19`) |
|---|---|---|
| **Agent A** ([`DWAOP_HYDROGEN_DOMINANCE_SPECIFICATION.md`](file:///f:/gdec-dwaop-v03/research/DWAOP_HYDROGEN_DOMINANCE_SPECIFICATION.md)) | (1) Rec 2 patched only `is_local_refinement`, leaving `_enabled` and `_evaluate_tree_on_world` allowing transitions out of `UNRECOVERABLE_REFUSAL`. (2) Theorem 2 Corollary lacked the `is_local_refinement` induction for `L` preservation (`pruned == unpruned`) and did not contrast `product(*branch_policies)` size growth under internal $\preceq_{VRL}$ vs. Role 3 metadata projection. | **Accepted & updated (`#10`):** Expanded Rec 2 to `_enabled`, `_independent_enabled`, and `_evaluate_tree_on_world`; added explicit $\preceq_{VRL}$ induction for `pruned == unpruned` and Option A (Role 4 via $\preceq_{VRL}$) vs. Option B (Role 3 metadata projection) trade-off. |
| **Agent B** ([`DWAOP_HYDROGEN_COUNTEREXAMPLES.md`](file:///f:/gdec-dwaop-v03/research/DWAOP_HYDROGEN_COUNTEREXAMPLES.md)) | (1) `max_horizon=3` fuzzing conclusion over-claimed that Q7 unsoundness is localized specifically to `UNRECOVERABLE_REFUSAL`, missing the `SUCCESS`-only `pruned != unpruned == oracle` divergence at `max_horizon >= 4`. (2) CE-6A relied on alphabetical `'a_fine' < 'b_coarse'` tie-breaking. | **Accepted & updated (`#13`):** Added verified `SUCCESS`-only **CE-6C** (`max_horizon=4`, order-independent via `-len(item[1])`), documented the CE-6A tie-break, and corrected the fuzzing scope statement to cover both Q7 triggers. |
| **Agent C** ([`DWAOP_HYDROGEN_ORACLE_AUDIT.md`](file:///f:/gdec-dwaop-v03/research/DWAOP_HYDROGEN_ORACLE_AUDIT.md)) | (1) `940`-graph C1–C6 suite had `0` active prunes in C4–C5 and missed `SUCCESS`-only `pruned != unpruned == oracle`. (2) Standalone `_evaluate_tree_on_world` needed explicit testing on `UNRECOVERABLE_REFUSAL -> recover -> ACCEPT`, and C6's `ref_depth` column was unlogged. | **Accepted & updated (`#16`):** Added Campaign 7 (`32` graphs, `12/32` `pruned != unpruned == oracle == ref`), verified standalone `_evaluate_tree_on_world` falsely returning `ACCEPT`, and logged C6 `ref_depth` (`0/120`). |
| **Agent D** ([`DWAOP_HYDROGEN_PERFORMANCE_AUDIT.md`](file:///f:/gdec-dwaop-v03/research/DWAOP_HYDROGEN_PERFORMANCE_AUDIT.md)) | (1) `id(state)` provenance caching risks GC address reuse / `tracemalloc` overhead and must not bypass external provenance checks. (2) Residual `2^(S+3)-2S-8` scaling in `is_local_refinement` remains exponential at larger `S` even with `V2`. (3) H8 `V1`/`V2` lacked explicit `pareto_frontier` equality and `peak_planner_memory_bytes` verification. | **Accepted & updated (`#19`):** Replaced `id(state)` cache with internal `_verify_provenance=False`; verified H8 exact frontier equality and lower peak memory (`414,376 B` vs. `530,308 B` unpruned, `27.1×` faster); added residual `2^S` scaling analysis. |

---

## 6. Stage 2 Remediation Checklist

1. **Enforce sticky-refusal invariants uniformly:** Reject `not state.model_valid or state.evidence_stale or state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL` in `is_local_refinement`, `_enabled`, `_independent_enabled`, and `_evaluate_tree_on_world`.
2. **Resolve the `max_actions_on_path` specification / Bellman defect:** Either **(Option A)** keep `min max_actions_on_path` as canonical root tie-breaker by reducing internal OR nodes with the 3-way product order $\preceq_{VRL}$ (`world_verdict_map`, `resource_vector`, `max_actions_on_path`) and applying `pareto_reduce` ($\prec_{\text{lex}}$) only at the root, or **(Option B)** make `max_actions_on_path` pure descriptive metadata (Role 3) excluded from `_canonical_dedup`, `_oracle_pareto_reduce`, and frontier equality.
3. **Eliminate redundant validation & provenance walks in `plan_policies`:** Pre-normalize `ActionSemantics` and validate `oracle`/`contracts` once at `plan_policies` entry, pass an internal `_verify_provenance=False` flag inside `plan_policies`'s `is_local_refinement` / `is_complete_refinement_cover` calls (keeping public callers fail-closed), and safely memoize `is_local_refinement` using `(sim_key(fine), sim_key(coarse), depth_left)` including `last_outcome_kind`.
4. **Expand regression and ladder tests:** Add Counterexamples **E1**, **E2A**, **E2B**, standalone `_evaluate_tree_on_world` sticky-refusal rejection, and multi-entry / failure-mode ladder tests to `tests/research/`.
