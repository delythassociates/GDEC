"""Structured finite-horizon refinement-ladder benchmark for DWAOP v0.3."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, Optional

from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier


def _action(action_id, semantic_key, universe, observations, *, required_obligations,
            required_capabilities=frozenset(), ru_upper, cpu_ticks, energy_ticks,
            workspace_gb_upper=0.1, overlap_gb_upper=0.02, discharged=None, gained=None):
    labels = sorted(set(observations.values()))
    return ActionSemantics(
        action_id=action_id, semantic_key=semantic_key, applicable_worlds=universe,
        observable_label_by_world=dict(observations),
        required_capabilities=required_capabilities, required_obligations=required_obligations,
        evidence_contract=frozenset({"evidence-v1"}), failure_semantics=frozenset({"fail-closed-v1"}),
        ru_upper=ru_upper, cpu_ticks=cpu_ticks, energy_ticks=energy_ticks,
        workspace_gb_upper=workspace_gb_upper, overlap_gb_upper=overlap_gb_upper,
        outcome_kind_by_label={label: OutcomeKind.SUCCESS for label in labels},
        discharged_by_label=dict(discharged or {label: frozenset() for label in labels}),
        capabilities_by_label=dict(gained or {label: frozenset() for label in labels}),
        retained_output_gb_by_label={label: 0.02 for label in labels},
        released_memory_gb_by_label={label: 0.0 for label in labels},
        invalidates_model_by_label={label: False for label in labels},
        stale_evidence_by_label={label: False for label in labels},
        retry_cost_by_label={label: 0 for label in labels},
        proof_id_by_label={label: "proof:" + action_id + ":" + label for label in labels},
    )


def build_refinement_ladder(n_stages: int):
    if n_stages < 2 or n_stages > 8:
        raise ValueError("n_stages must be in [2,8]")
    n_worlds = 2 ** (n_stages + 1)
    worlds = tuple("w" + str(i).zfill(3) for i in range(n_worlds))
    universe = frozenset(worlds)
    decisions = {w: ("ACCEPT" if ((int(w[1:]) // 2) % 2 == 0) else "REJECT") for w in worlds}
    obligations = frozenset(set("stage_" + str(i) for i in range(n_stages)) | {"decision"})
    actions = {}
    for i in range(n_stages):
        req_caps = frozenset() if i == 0 else frozenset({"cap_" + str(i)})
        stage_ob = frozenset({"stage_" + str(i)})
        fine_obs = ({w: ("group_0" if int(w[1:]) % 2 == 0 else "group_1") for w in worlds}
                    if i == 0 else {w: "same_cell" for w in worlds})
        coarse_obs = {w: "coarse_cell" for w in worlds}
        fine_labels, coarse_labels = sorted(set(fine_obs.values())), sorted(set(coarse_obs.values()))
        fine_discharge = {label: stage_ob for label in fine_labels}
        coarse_discharge = {label: stage_ob for label in coarse_labels}
        fine_gain = {label: frozenset({"cap_" + str(i+1)}) for label in fine_labels}
        coarse_gain = {label: frozenset({"cap_" + str(i+1)}) for label in coarse_labels}
        actions["fine_stage_" + str(i)] = _action(
            "fine_stage_" + str(i), "probe-stage-" + str(i), universe, fine_obs,
            required_obligations=stage_ob, required_capabilities=req_caps,
            ru_upper=0.10, cpu_ticks=1.0, energy_ticks=0.5, workspace_gb_upper=0.05,
            overlap_gb_upper=0.01, discharged=fine_discharge, gained=fine_gain)
        actions["coarse_stage_" + str(i)] = _action(
            "coarse_stage_" + str(i), "probe-stage-" + str(i), universe, coarse_obs,
            required_obligations=stage_ob, required_capabilities=req_caps,
            ru_upper=0.20, cpu_ticks=2.0, energy_ticks=1.0, workspace_gb_upper=0.10,
            overlap_gb_upper=0.02, discharged=coarse_discharge, gained=coarse_gain)
    decision_obs = {w: decisions[w].lower() for w in worlds}
    labels = sorted(set(decision_obs.values()))
    actions["final_decision"] = _action(
        "final_decision", "final-decision", universe, decision_obs,
        required_obligations=frozenset({"decision"}),
        required_capabilities=frozenset({"cap_" + str(n_stages)}),
        ru_upper=0.05, cpu_ticks=0.5, energy_ticks=0.25,
        discharged={label: frozenset({"decision"}) for label in labels})
    oracle = WorldOracle(
        specification_id="dwaop-v03-ladder-H" + str(n_stages+1),
        model_id="finite-observable-refinement-ladder",
        assurance_scope="research-only-finite-horizon",
        universe=universe, decision_by_world=decisions, actions=actions,
        initial_obligations=obligations)
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=200.0, energy_ticks=100.0, peak_memory_gb=16.0)
    return oracle, budget


def run_ladder_benchmark(n_stages: int) -> Dict[str, object]:
    oracle, budget = build_refinement_ladder(n_stages)
    horizon = n_stages + 1
    pruned = plan_policies(oracle, budget, max_horizon=horizon, prune=True)
    unpruned = plan_policies(oracle, budget, max_horizon=horizon, prune=False)
    exact = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=horizon)
    def signature(policy):
        return (
            policy.world_verdict_map,
            tuple(sorted(policy.terminal_verdicts)),
            policy.resource_vector.exact_key(),
            policy.max_actions_on_path,
        )

    def compare_frontiers(left, right):
        left_set = {signature(p) for p in left}
        right_set = {signature(p) for p in right}
        return {
            "left_size": len(left_set),
            "right_size": len(right_set),
            "left_only_count": len(left_set - right_set),
            "right_only_count": len(right_set - left_set),
            "left_only_examples": [repr(x) for x in sorted(left_set - right_set, key=repr)[:2]],
            "right_only_examples": [repr(x) for x in sorted(right_set - left_set, key=repr)[:2]],
        }

    pruned_vs_unpruned = compare_frontiers(pruned.pareto_frontier, unpruned.pareto_frontier)
    unpruned_vs_oracle = compare_frontiers(unpruned.pareto_frontier, exact)
    pruned_vs_oracle = compare_frontiers(pruned.pareto_frontier, exact)
    equal = (
        pruned_vs_unpruned["left_only_count"] == 0
        and unpruned_vs_oracle["left_only_count"] == 0
        and pruned_vs_oracle["left_only_count"] == 0
    )
    debug = {
        "pruned_vs_unpruned": pruned_vs_unpruned,
        "unpruned_vs_oracle": unpruned_vs_oracle,
        "pruned_vs_oracle": pruned_vs_oracle,
    }
    if not equal:
        raise AssertionError("Pareto frontiers diverged at horizon " + str(horizon) + ": " + json.dumps(debug, sort_keys=True))
    def metrics(result):
        m = result.metrics
        return {
            "states_expanded": m.states_expanded, "actions_considered": m.actions_considered,
            "complete_policies_enumerated": m.complete_policies_enumerated,
            "dominance_checks": m.dominance_checks, "successful_prunes": m.successful_prunes,
            "rejected_prune_attempts": m.rejected_prune_attempts,
            "dominance_check_time_sec": m.dominance_check_time_sec,
            "total_runtime_sec": m.total_runtime_sec,
            "peak_planner_memory_bytes": m.peak_planner_memory_bytes,
            "pareto_frontier_size": len(result.pareto_frontier),
        }
    return {
        "horizon": horizon, "stages": n_stages, "world_count": len(oracle.universe),
        "frontiers_equal_pruned_unpruned_oracle": equal,
        "pruned": metrics(pruned), "unpruned": metrics(unpruned),
        "oracle_frontier_size": len(exact),
        "state_reduction_percent": 100.0*(1.0-pruned.metrics.states_expanded/unpruned.metrics.states_expanded),
        "runtime_ratio_pruned_over_unpruned": pruned.metrics.total_runtime_sec/unpruned.metrics.total_runtime_sec,
        "scope_note": "Finite deterministic synthetic observable-world planning; no PDE/FEM computation or production use.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stages", type=int, nargs="+", default=[5, 7])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = {"schema_version":"dwaop_horizon_campaign_v0.3",
              "benchmarks":[run_ladder_benchmark(n) for n in args.stages],
              "formal_status":"PROOF_SKETCH_ONLY_NOT_MACHINE_CHECKED"}
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
