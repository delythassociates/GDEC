# DWAOP v0.3 — Post-Fix Independent Verification (Stage 3)

**Repository:** `delythassociates/GDEC`  
**Branch:** `research/dwaop-horizon-six-formal-gate-v0.3`  
**Reviewed Implementation Commit:** `c87f217b71a1f63bc9ccca4d7bb99e5f8a089b53` (diff against `2812b000ea0241a3aee2b5580444a7e1767c3417`)  
**Reviewer:** `agent-e` (`Gemini 4 Hydrogen (High)`)  
**Historical Stage 1 Audit (preserved untouched):** [DWAOP_HYDROGEN_INDEPENDENT_REVIEW.md](DWAOP_HYDROGEN_INDEPENDENT_REVIEW.md) (against `2812b00`)

---

## 1. Scope & Distinction from Full CI Matrix

This document records the **Stage 3 fast independent verification** performed by `agent-e` on the Stage 2 fixes before the full 4-job Python 3.10–3.13 CI run. It is **not** a substitute for the full H6/H8 run (`101 passed in 1253.57s`) or the 4-job Python 3.10–3.13 GitHub Actions matrix (`46130302893`), which separately corroborated H6/H8 and all matrix versions.

---

## 2. Diff & Scope Inspection

- Verified Stage 2 code/test changes were limited to:
  - `research/prototypes/dwaop_integrated_planner.py` (`+66/-26` lines)
  - `research/prototypes/dwaop_exhaustive_policy_oracle.py` (`+12` lines)
  - `tests/research/test_dwaop_adversarial_graphs.py` (`+716` lines)
- Confirmed zero modifications to `src/gdec/`, WP2, WP3, DSES, or `main`, and confirmed exact `Fraction` arithmetic (`tol=0.0`, `_nonnegative`, `exact_key`) remained intact.

---

## 3. Code & Counterexample Verification

1. **Sticky Refusal Fix (`_is_sticky_refusal`):** Inspected enforcement in `_enabled()`, `is_local_refinement()` (rejecting sticky `fine_state` when non-sticky `coarse_state` has enabled continuations), `_search()`, `_independent_enabled()`, and `_evaluate_tree_on_world()` (at top of `while isinstance(node, ActionBranch):`).
   - Re-ran `E1`: `pruned == unpruned == oracle` (`len=2`, `prunes=0`).
   - Re-ran standalone `_evaluate_tree_on_world` on `a_fine -> recover -> ACCEPT`: returns `None` (rejected).
2. **Bellman Internal-Reduction Fix (`_internal_policy_dominates`, `_internal_pareto_reduce`):** Inspected internal OR-node reduction in `_search()` preserving `(world_verdict_map, resource_vector, max_actions_on_path)` witnesses while retaining `min max_actions_on_path` tie-breaking at root `pareto_reduce(all_policies)`.
   - Re-ran `E2A` and `E2B`: `pruned == unpruned == oracle` (`L=2`).

---

## 4. Exact Fast Regression Command & Output

```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -m pytest f:/gdec-dwaop-v03/tests/research/ -k "not (5-6 or 7-8)" -v
```

- **Result:** **`99 passed, 2 deselected, 0 failed`** in **`91.78s`** (H6/H8 `(5-6 or 7-8)` deselected in this fast Stage 3 review).
- **Corroboration:** Subsequently corroborated by the full local DWAOP suite (`101 passed in 1253.57s`) and GitHub Actions run [`46130302893`](https://github.com/delythassociates/GDEC/actions/runs/46130302893) (`4/4` jobs, Python 3.10–3.13, `101 passed, 0 failed` per job) on exact commit `c87f217b71a1f63bc9ccca4d7bb99e5f8a089b53`.

---

## 5. Remaining Concerns

- Performance overhead of recursive `is_local_refinement` checks on H6/H8 (~6.65×–7.56× slower than unpruned search) remains unoptimized and deferred.
- Synthetic `NormalizedPolicy` objects constructed externally with mismatched `terminal_verdicts` vs. `world_verdict_map` remain an unsupported malformed-input edge case (`NormalizedPolicy.__post_init__` does not enforce consistency).
- Finite-horizon proof sketch remains not machine-checked.
