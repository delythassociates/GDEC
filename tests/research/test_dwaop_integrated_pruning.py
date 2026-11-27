"""Integrated pruning, Pareto equivalence, and campaign runner tests for DWAOP v0.2."""
from __future__ import annotations

import hashlib
import json
from itertools import product
from fractions import Fraction
from pathlib import Path
import random
import sys
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.prototypes.dwaop_exhaustive_policy_oracle import (
    enumerate_exact_pareto_frontier,
)
from research.prototypes.dwaop_integrated_planner import (
    ActionSemantics,
    OutcomeKind,
    PlannerResult,
    ResourceBudget,
    ResourceVector,
    SearchMetrics,
    WorldOracle,
    apply_action_outcome,
    build_action_contract,
    make_initial_state,
    plan_policies,
    verify_action_contract,
)


def _json_default(value: Any) -> Any:
    """Serialize exact rational resources without converting them to floats."""
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def make_action(
    action_id: str,
    semantic_key: str,
    applicable_worlds: FrozenSet[str],
    observable_label_by_world: Mapping[str, str],
    *,
    required_capabilities: FrozenSet[str] = frozenset(),
    required_obligations: FrozenSet[str] = frozenset(),
    evidence_contract: FrozenSet[str] = frozenset({"ev_std"}),
    failure_semantics: FrozenSet[str] = frozenset({"fail_std"}),
    ru_upper: float = 1.0,
    cpu_ticks: float = 10.0,
    energy_ticks: float = 5.0,
    workspace_gb_upper: float = 1.0,
    overlap_gb_upper: float = 0.25,
    outcome_kind_by_label: Optional[Mapping[str, OutcomeKind]] = None,
    discharged_by_label: Optional[Mapping[str, FrozenSet[str]]] = None,
    capabilities_by_label: Optional[Mapping[str, FrozenSet[str]]] = None,
    retained_output_gb_by_label: Optional[Mapping[str, float]] = None,
    released_memory_gb_by_label: Optional[Mapping[str, float]] = None,
    invalidates_model_by_label: Optional[Mapping[str, bool]] = None,
    stale_evidence_by_label: Optional[Mapping[str, bool]] = None,
    retry_cost_by_label: Optional[Mapping[str, int]] = None,
    proof_id_by_label: Optional[Mapping[str, str]] = None,
) -> ActionSemantics:
    """Construct a complete ActionSemantics with sensible per-label defaults."""
    labels = sorted(set(observable_label_by_world.values()))
    return ActionSemantics(
        action_id=action_id,
        semantic_key=semantic_key,
        applicable_worlds=applicable_worlds,
        observable_label_by_world=dict(observable_label_by_world),
        required_capabilities=required_capabilities,
        required_obligations=required_obligations,
        evidence_contract=evidence_contract,
        failure_semantics=failure_semantics,
        ru_upper=ru_upper,
        cpu_ticks=cpu_ticks,
        energy_ticks=energy_ticks,
        workspace_gb_upper=workspace_gb_upper,
        overlap_gb_upper=overlap_gb_upper,
        outcome_kind_by_label=(
            dict(outcome_kind_by_label)
            if outcome_kind_by_label is not None
            else {lbl: OutcomeKind.SUCCESS for lbl in labels}
        ),
        discharged_by_label=(
            dict(discharged_by_label)
            if discharged_by_label is not None
            else {lbl: frozenset() for lbl in labels}
        ),
        capabilities_by_label=(
            dict(capabilities_by_label)
            if capabilities_by_label is not None
            else {lbl: frozenset() for lbl in labels}
        ),
        retained_output_gb_by_label=(
            dict(retained_output_gb_by_label)
            if retained_output_gb_by_label is not None
            else {lbl: 0.2 for lbl in labels}
        ),
        released_memory_gb_by_label=(
            dict(released_memory_gb_by_label)
            if released_memory_gb_by_label is not None
            else {lbl: 0.0 for lbl in labels}
        ),
        invalidates_model_by_label=(
            dict(invalidates_model_by_label)
            if invalidates_model_by_label is not None
            else {lbl: False for lbl in labels}
        ),
        stale_evidence_by_label=(
            dict(stale_evidence_by_label)
            if stale_evidence_by_label is not None
            else {lbl: False for lbl in labels}
        ),
        retry_cost_by_label=(
            dict(retry_cost_by_label)
            if retry_cost_by_label is not None
            else {lbl: 0 for lbl in labels}
        ),
        proof_id_by_label=(
            dict(proof_id_by_label)
            if proof_id_by_label is not None
            else {lbl: f"proof:{action_id}:{lbl}" for lbl in labels}
        ),
    )


def oracle_hash(oracle: WorldOracle, budget: ResourceBudget) -> str:
    """Compute a deterministic SHA-256 hash of an oracle and budget."""
    payload = {
        "spec": oracle.specification_id,
        "model": oracle.model_id,
        "scope": oracle.assurance_scope,
        "universe": sorted(oracle.universe),
        "decisions": sorted(oracle.decision_by_world.items()),
        "init_ob": sorted(oracle.initial_obligations),
        "init_cap": sorted(oracle.initial_capabilities),
        "init_retries": oracle.initial_retries,
        "budget": [str(budget.ru_upper), str(budget.cpu_ticks), str(budget.energy_ticks), str(budget.peak_memory_gb)],
        "actions": [
            {
                "id": aid,
                "key": a.semantic_key,
                "app": sorted(a.applicable_worlds),
                "obs": sorted(a.observable_label_by_world.items()),
                "costs": [a.ru_upper, a.cpu_ticks, a.energy_ticks, a.workspace_gb_upper, a.overlap_gb_upper],
                "kinds": sorted((k, v.value) for k, v in a.outcome_kind_by_label.items()),
                "disch": sorted((k, sorted(v)) for k, v in a.discharged_by_label.items()),
                "caps": sorted((k, sorted(v)) for k, v in a.capabilities_by_label.items()),
            }
            for aid, a in sorted(oracle.actions.items())
        ],
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def assert_frontiers_match(
    oracle: WorldOracle,
    budget: ResourceBudget,
    max_horizon: int = 8,
) -> Tuple[PlannerResult, PlannerResult]:
    """Assert P_pruned == P_unpruned == P_oracle and return (pruned, unpruned)."""
    res_unpruned = plan_policies(oracle, budget, max_horizon=max_horizon, prune=False)
    res_pruned = plan_policies(oracle, budget, max_horizon=max_horizon, prune=True)
    p_oracle = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=max_horizon)

    assert res_pruned.pareto_frontier == res_unpruned.pareto_frontier, (
        f"Pruned vs unpruned mismatch:\n"
        f"  pruned={res_pruned.pareto_frontier}\n"
        f"  unpruned={res_unpruned.pareto_frontier}"
    )
    assert res_pruned.pareto_frontier == p_oracle, (
        f"Planner vs oracle mismatch:\n"
        f"  planner={res_pruned.pareto_frontier}\n"
        f"  oracle={p_oracle}"
    )
    return res_pruned, res_unpruned


def build_heat_qoi_screening_fixture() -> Tuple[WorldOracle, ResourceBudget]:
    """Synthetic heat-QoI screening fixture with fine vs coarse screening actions."""
    universe = frozenset({"hot_converged", "hot_diverged", "cool_safe"})
    decisions = {
        "hot_converged": "ACCEPT",
        "hot_diverged": "REJECT",
        "cool_safe": "ACCEPT",
    }
    # Fine screening separates all 3 regimes and is cheaper than coarse screening.
    screen_fine = make_action(
        "screen_fine",
        "heat_qoi_screen",
        universe,
        {
            "hot_converged": "high_flux_ok",
            "hot_diverged": "high_flux_err",
            "cool_safe": "low_flux",
        },
        ru_upper=1.0,
        cpu_ticks=10.0,
        energy_ticks=4.0,
        workspace_gb_upper=0.5,
        overlap_gb_upper=0.1,
        required_obligations=frozenset({"ob_screen"}),
        discharged_by_label={
            "high_flux_ok": frozenset({"ob_screen"}),
            "high_flux_err": frozenset({"ob_screen"}),
            "low_flux": frozenset({"ob_screen"}),
        },
        capabilities_by_label={
            "high_flux_ok": frozenset({"cap_screened"}),
            "high_flux_err": frozenset({"cap_screened"}),
            "low_flux": frozenset({"cap_screened"}),
        },
    )
    # Coarse screening merges all 3 regimes into 1 coarse outcome and costs more.
    screen_coarse = make_action(
        "screen_coarse",
        "heat_qoi_screen",
        universe,
        {
            "hot_converged": "coarse_band",
            "hot_diverged": "coarse_band",
            "cool_safe": "coarse_band",
        },
        ru_upper=2.0,
        cpu_ticks=20.0,
        energy_ticks=8.0,
        workspace_gb_upper=1.0,
        overlap_gb_upper=0.2,
        required_obligations=frozenset({"ob_screen"}),
        discharged_by_label={
            "coarse_band": frozenset({"ob_screen"}),
        },
        capabilities_by_label={
            "coarse_band": frozenset({"cap_screened"}),
        },
    )
    # Follow-up QoI solver discharges ob_qoi.
    hot_resolve = make_action(
        "hot_resolve",
        "heat_resolve",
        universe,
        {"hot_converged": "ok", "hot_diverged": "fail", "cool_safe": "ok"},
        required_capabilities=frozenset({"cap_screened"}),
        ru_upper=1.5,
        cpu_ticks=15.0,
        energy_ticks=6.0,
        discharged_by_label={"ok": frozenset({"ob_qoi"}), "fail": frozenset({"ob_qoi"})},
    )
    oracle = WorldOracle(
        specification_id="spec_heat_qoi_v02",
        model_id="fem_heat_2d",
        assurance_scope="qoi_screening",
        universe=universe,
        decision_by_world=decisions,
        actions={
            "screen_fine": screen_fine,
            "screen_coarse": screen_coarse,
            "hot_resolve": hot_resolve,
        },
        initial_obligations=frozenset({"ob_screen", "ob_qoi"}),
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    return oracle, budget


def test_exact_resource_conversion_preserves_action_contracts_and_transitions() -> None:
    """Diagnose the planner/oracle mismatch at the fail-closed contract boundary."""
    oracle, budget = build_heat_qoi_screening_fixture()
    contracts = {
        action_id: build_action_contract(oracle, action_id)
        for action_id in oracle.actions
    }
    for action_id, contract in contracts.items():
        verify_action_contract(oracle, contract)

    root = make_initial_state(oracle)
    for action_id in ("screen_fine", "screen_coarse"):
        transitions = apply_action_outcome(root, contracts[action_id], oracle)
        assert transitions, f"{action_id}: valid root action unexpectedly has no transitions"
        for transition in transitions:
            assert budget.allows(transition.state.resource_spent)
            follow_up = apply_action_outcome(
                transition.state, contracts["hot_resolve"], oracle
            )
            assert follow_up, (
                f"hot_resolve: valid screened child has no transitions; "
                f"worlds={sorted(transition.state.worlds)}; "
                f"capabilities={sorted(transition.state.capabilities)}"
            )


def build_multi_resource_tradeoff_fixture() -> Tuple[WorldOracle, ResourceBudget]:
    """Multi-action fan-out and reconvergence with incomparable 4D resource trade-offs."""
    universe = frozenset({"w0", "w1", "w2", "w3"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT", "w3": "REJECT"}

    # Action A1: Low RU, high CPU, medium energy, low memory
    a_low_ru = make_action(
        "probe_low_ru",
        "probe_alpha",
        universe,
        {"w0": "p0", "w1": "p1", "w2": "p0", "w3": "p1"},
        ru_upper=1.0,
        cpu_ticks=50.0,
        energy_ticks=20.0,
        workspace_gb_upper=1.0,
        overlap_gb_upper=0.2,
        required_obligations=frozenset({"ob_1"}),
        discharged_by_label={"p0": frozenset({"ob_1"}), "p1": frozenset({"ob_1"})},
        capabilities_by_label={"p0": frozenset({"c1"}), "p1": frozenset({"c1"})},
    )
    # Action A2: High RU, low CPU, high energy, low memory (incomparable with A1)
    a_low_cpu = make_action(
        "probe_low_cpu",
        "probe_beta",
        universe,
        {"w0": "q0", "w1": "q1", "w2": "q0", "w3": "q1"},
        ru_upper=5.0,
        cpu_ticks=5.0,
        energy_ticks=40.0,
        workspace_gb_upper=1.0,
        overlap_gb_upper=0.2,
        discharged_by_label={"q0": frozenset({"ob_1"}), "q1": frozenset({"ob_1"})},
        capabilities_by_label={"q0": frozenset({"c1"}), "q1": frozenset({"c1"})},
    )
    # Action A3: Medium RU, medium CPU, low energy, high memory (incomparable with A1, A2)
    a_low_energy = make_action(
        "probe_low_energy",
        "probe_gamma",
        universe,
        {"w0": "r0", "w1": "r1", "w2": "r0", "w3": "r1"},
        ru_upper=3.0,
        cpu_ticks=25.0,
        energy_ticks=2.0,
        workspace_gb_upper=4.0,
        overlap_gb_upper=1.0,
        discharged_by_label={"r0": frozenset({"ob_1"}), "r1": frozenset({"ob_1"})},
        capabilities_by_label={"r0": frozenset({"c1"}), "r1": frozenset({"c1"})},
    )
    # Dominated coarse variant of probe_alpha (pruned when prune=True)
    a_dominated = make_action(
        "probe_alpha_coarse_slow",
        "probe_alpha",
        universe,
        {"w0": "all", "w1": "all", "w2": "all", "w3": "all"},
        ru_upper=2.0,
        cpu_ticks=60.0,
        energy_ticks=25.0,
        workspace_gb_upper=1.5,
        overlap_gb_upper=0.5,
        required_obligations=frozenset({"ob_1"}),
        discharged_by_label={"all": frozenset({"ob_1"})},
        capabilities_by_label={"all": frozenset({"c1"})},
    )
    a_verify = make_action(
        "verify_final",
        "verify_step",
        universe,
        {"w0": "v0", "w1": "v1", "w2": "v0", "w3": "v1"},
        required_capabilities=frozenset({"c1"}),
        ru_upper=0.5,
        cpu_ticks=5.0,
        energy_ticks=2.0,
        discharged_by_label={"v0": frozenset({"ob_2"}), "v1": frozenset({"ob_2"})},
    )

    oracle = WorldOracle(
        specification_id="spec_tradeoff_v02",
        model_id="m_tradeoff",
        assurance_scope="pareto_4d",
        universe=universe,
        decision_by_world=decisions,
        actions={
            "probe_low_ru": a_low_ru,
            "probe_low_cpu": a_low_cpu,
            "probe_low_energy": a_low_energy,
            "probe_alpha_coarse_slow": a_dominated,
            "verify_final": a_verify,
        },
        initial_obligations=frozenset({"ob_1", "ob_2"}),
    )
    budget = ResourceBudget(ru_upper=20.0, cpu_ticks=200.0, energy_ticks=100.0, peak_memory_gb=16.0)
    return oracle, budget


def build_failure_retry_invalidation_fixture() -> Tuple[WorldOracle, ResourceBudget]:
    """Fixture exercising failure, inconclusive, bounded retry, model invalidation, and stale evidence."""
    universe = frozenset({"w_ok", "w_retry_ok", "w_inconclusive", "w_invalid", "w_stale"})
    decisions = {
        "w_ok": "ACCEPT",
        "w_retry_ok": "ACCEPT",
        "w_inconclusive": "REJECT",
        "w_invalid": "ACCEPT",
        "w_stale": "REJECT",
    }

    solver = make_action(
        "adaptive_solve",
        "solve_step",
        universe,
        {
            "w_ok": "converged",
            "w_retry_ok": "transient_stall",
            "w_inconclusive": "inconclusive",
            "w_invalid": "model_broken",
            "w_stale": "stale_mesh",
        },
        ru_upper=1.0,
        cpu_ticks=10.0,
        energy_ticks=5.0,
        outcome_kind_by_label={
            "converged": OutcomeKind.SUCCESS,
            "transient_stall": OutcomeKind.BOUNDED_RETRY,
            "inconclusive": OutcomeKind.INCONCLUSIVE,
            "model_broken": OutcomeKind.MODEL_INVALIDATED,
            "stale_mesh": OutcomeKind.STALE_EVIDENCE,
        },
        discharged_by_label={
            "converged": frozenset({"ob_solve"}),
            "transient_stall": frozenset(),
            "inconclusive": frozenset(),
            "model_broken": frozenset(),
            "stale_mesh": frozenset(),
        },
        invalidates_model_by_label={
            "converged": False,
            "transient_stall": False,
            "inconclusive": False,
            "model_broken": True,
            "stale_mesh": False,
        },
        stale_evidence_by_label={
            "converged": False,
            "transient_stall": False,
            "inconclusive": False,
            "model_broken": False,
            "stale_mesh": True,
        },
        retry_cost_by_label={
            "converged": 0,
            "transient_stall": 1,
            "inconclusive": 0,
            "model_broken": 0,
            "stale_mesh": 0,
        },
    )

    fallback = make_action(
        "direct_recover",
        "recover_step",
        frozenset({"w_retry_ok"}),
        {"w_retry_ok": "recovered"},
        ru_upper=2.0,
        cpu_ticks=12.0,
        energy_ticks=6.0,
        discharged_by_label={"recovered": frozenset({"ob_solve"})},
    )

    oracle = WorldOracle(
        specification_id="spec_failure_v02",
        model_id="m_failure",
        assurance_scope="failure_modes",
        universe=universe,
        decision_by_world=decisions,
        actions={"adaptive_solve": solver, "direct_recover": fallback},
        initial_obligations=frozenset({"ob_solve"}),
        initial_retries=1,
    )
    budget = ResourceBudget(ru_upper=15.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    return oracle, budget


def _all_partitions(items: Sequence[str]) -> List[Tuple[FrozenSet[str], ...]]:
    """Return all set partitions of `items`."""
    if not items:
        return [()]
    first, rest = items[0], items[1:]
    partitions: List[Tuple[FrozenSet[str], ...]] = []
    for sub in _all_partitions(rest):
        partitions.append((frozenset({first}),) + sub)
        for i in range(len(sub)):
            updated = tuple(
                sub[j] | {first} if j == i else sub[j]
                for j in range(len(sub))
            )
            partitions.append(updated)
    return partitions


def generate_seeded_oracle(seed: int, n_worlds: int) -> Tuple[WorldOracle, ResourceBudget]:
    """Deterministic seeded generator for 4-world and 5-world DWAOP v0.2 graphs."""
    rng = random.Random(seed)
    worlds = tuple(f"w{i}" for i in range(n_worlds))
    universe = frozenset(worlds)
    decisions = {w: rng.choice(["ACCEPT", "REJECT"]) for w in worlds}
    # Ensure at least one ACCEPT and one REJECT when possible
    if len(set(decisions.values())) == 1:
        decisions[worlds[-1]] = "REJECT" if decisions[worlds[0]] == "ACCEPT" else "ACCEPT"

    has_obligation = rng.choice([True, False])
    init_obs = frozenset({"ob_main"}) if has_obligation else frozenset()
    init_retries = rng.choice([0, 1])

    actions: Dict[str, ActionSemantics] = {}

    # 1. Create a fine vs coarse refinement pair with same semantic_key
    n_fine_cells = rng.randint(2, min(4, n_worlds))
    fine_obs = {w: f"cell_{idx % n_fine_cells}" for idx, w in enumerate(worlds)}
    coarse_obs = {w: f"cell_{0 if (idx % n_fine_cells) < n_fine_cells - 1 else 1}" for idx, w in enumerate(worlds)}

    fine_labels = sorted(set(fine_obs.values()))
    coarse_labels = sorted(set(coarse_obs.values()))

    actions["a_fine"] = make_action(
        "a_fine",
        "shared_probe",
        universe,
        fine_obs,
        ru_upper=1.0,
        cpu_ticks=10.0,
        energy_ticks=5.0,
        workspace_gb_upper=0.5,
        overlap_gb_upper=0.1,
        discharged_by_label={lbl: init_obs for lbl in fine_labels},
        capabilities_by_label={lbl: frozenset({"cap_p"}) for lbl in fine_labels},
    )
    actions["a_coarse"] = make_action(
        "a_coarse",
        "shared_probe",
        universe,
        coarse_obs,
        ru_upper=1.5 + rng.uniform(0.0, 1.0),
        cpu_ticks=12.0 + rng.uniform(0.0, 5.0),
        energy_ticks=6.0 + rng.uniform(0.0, 3.0),
        workspace_gb_upper=0.8,
        overlap_gb_upper=0.2,
        discharged_by_label={lbl: init_obs for lbl in coarse_labels},
        capabilities_by_label={lbl: frozenset({"cap_p"}) for lbl in coarse_labels},
    )

    # 2. Add a differently-labelled equivalent partition with incomparable resource trade-off
    alt_obs = {w: f"alt_{fine_obs[w]}" for w in worlds}
    alt_labels = sorted(set(alt_obs.values()))
    actions["a_alt_tradeoff"] = make_action(
        "a_alt_tradeoff",
        "alt_probe",
        universe,
        alt_obs,
        ru_upper=0.5,
        cpu_ticks=25.0,
        energy_ticks=2.0,
        workspace_gb_upper=1.5,
        overlap_gb_upper=0.3,
        discharged_by_label={lbl: init_obs for lbl in alt_labels},
        capabilities_by_label={lbl: frozenset({"cap_p"}) for lbl in alt_labels},
    )

    # 3. Optional failure / invalidation / retry action
    mode = seed % 4
    if mode == 1:
        fail_obs = {w: ("ok" if i < n_worlds - 1 else "inconclusive") for i, w in enumerate(worlds)}
        actions["a_risky"] = make_action(
            "a_risky",
            "risky_probe",
            universe,
            fail_obs,
            ru_upper=0.2,
            cpu_ticks=3.0,
            energy_ticks=1.0,
            outcome_kind_by_label={"ok": OutcomeKind.SUCCESS, "inconclusive": OutcomeKind.INCONCLUSIVE},
            discharged_by_label={"ok": init_obs, "inconclusive": frozenset()},
        )
    elif mode == 2 and init_retries >= 1:
        retry_obs = {w: ("ok" if i < n_worlds - 1 else "retry") for i, w in enumerate(worlds)}
        actions["a_retry"] = make_action(
            "a_retry",
            "retry_probe",
            universe,
            retry_obs,
            ru_upper=0.4,
            cpu_ticks=4.0,
            energy_ticks=2.0,
            outcome_kind_by_label={"ok": OutcomeKind.SUCCESS, "retry": OutcomeKind.BOUNDED_RETRY},
            discharged_by_label={"ok": init_obs, "retry": frozenset()},
            retry_cost_by_label={"ok": 0, "retry": 1},
        )
    elif mode == 3:
        inv_obs = {w: ("ok" if i < n_worlds - 1 else "invalid") for i, w in enumerate(worlds)}
        actions["a_inv"] = make_action(
            "a_inv",
            "inv_probe",
            universe,
            inv_obs,
            ru_upper=0.3,
            cpu_ticks=4.0,
            energy_ticks=1.5,
            outcome_kind_by_label={"ok": OutcomeKind.SUCCESS, "invalid": OutcomeKind.MODEL_INVALIDATED},
            discharged_by_label={"ok": init_obs, "invalid": frozenset()},
            invalidates_model_by_label={"ok": False, "invalid": True},
        )

    # 4. Final disambiguation action so every world can reach a terminal verdict
    actions["a_oracle_leaf"] = make_action(
        "a_oracle_leaf",
        "leaf_check",
        universe,
        {w: f"leaf_{decisions[w]}" for w in worlds},
        required_capabilities=frozenset({"cap_p"}),
        ru_upper=0.5,
        cpu_ticks=5.0,
        energy_ticks=2.5,
        discharged_by_label={f"leaf_{d}": init_obs for d in set(decisions.values())},
    )

    oracle = WorldOracle(
        specification_id=f"spec_seed_{seed}",
        model_id=f"model_{n_worlds}w",
        assurance_scope="generated_campaign",
        universe=universe,
        decision_by_world=decisions,
        actions=actions,
        initial_obligations=init_obs,
        initial_retries=init_retries,
    )
    budget = ResourceBudget(ru_upper=20.0, cpu_ticks=200.0, energy_ticks=100.0, peak_memory_gb=16.0)
    return oracle, budget


def run_generated_fixture_campaign(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """Execute exhaustive 3-world and seeded 4/5-world campaign and write JSON report."""
    worlds_3 = ("w0", "w1", "w2")
    universe_3 = frozenset(worlds_3)
    partitions_3 = _all_partitions(worlds_3)

    exhaustive_cases: List[Dict[str, Any]] = []
    # Enumerate all 8 decision assignments x all 25 partition pairs (200 cases)
    for dec_bits in product(("ACCEPT", "REJECT"), repeat=3):
        decisions = dict(zip(worlds_3, dec_bits))
        for p_idx_a, part_a in enumerate(partitions_3):
            obs_a = {w: f"a_{ci}" for ci, cell in enumerate(part_a) for w in cell}
            for p_idx_b, part_b in enumerate(partitions_3):
                obs_b = {w: f"b_{ci}" for ci, cell in enumerate(part_b) for w in cell}
                actions = {
                    "act_a": make_action(
                        "act_a",
                        "screen_op",
                        universe_3,
                        obs_a,
                        ru_upper=1.0,
                        cpu_ticks=10.0,
                        energy_ticks=5.0,
                        capabilities_by_label={lbl: frozenset({"c"}) for lbl in set(obs_a.values())},
                    ),
                    "act_b": make_action(
                        "act_b",
                        "screen_op",
                        universe_3,
                        obs_b,
                        ru_upper=2.0,
                        cpu_ticks=15.0,
                        energy_ticks=7.0,
                        capabilities_by_label={lbl: frozenset({"c"}) for lbl in set(obs_b.values())},
                    ),
                    "act_resolve": make_action(
                        "act_resolve",
                        "resolve_op",
                        universe_3,
                        {w: f"d_{decisions[w]}" for w in worlds_3},
                        required_capabilities=frozenset({"c"}),
                        ru_upper=1.0,
                        cpu_ticks=5.0,
                        energy_ticks=2.0,
                    ),
                }
                oracle = WorldOracle(
                    specification_id="spec_3w",
                    model_id="m_3w",
                    assurance_scope="exhaustive_3w",
                    universe=universe_3,
                    decision_by_world=decisions,
                    actions=actions,
                )
                budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
                res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=4)
                exhaustive_cases.append(
                    {
                        "case_id": f"3w_{''.join(d[0] for d in dec_bits)}_p{p_idx_a}_p{p_idx_b}",
                        "fixture_hash": oracle_hash(oracle, budget),
                        "pareto_size": len(res_p.pareto_frontier),
                        "pareto_match": True,
                        "states_unpruned": res_u.metrics.states_expanded,
                        "states_pruned": res_p.metrics.states_expanded,
                        "successful_prunes": res_p.metrics.successful_prunes,
                    }
                )

    seeded_cases: List[Dict[str, Any]] = []
    for seed in range(100, 125):
        oracle, budget = generate_seeded_oracle(seed, 4)
        res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=5)
        seeded_cases.append(
            {
                "seed": seed,
                "n_worlds": 4,
                "fixture_hash": oracle_hash(oracle, budget),
                "pareto_size": len(res_p.pareto_frontier),
                "pareto_match": True,
                "states_unpruned": res_u.metrics.states_expanded,
                "states_pruned": res_p.metrics.states_expanded,
                "actions_unpruned": res_u.metrics.actions_considered,
                "actions_pruned": res_p.metrics.actions_considered,
                "successful_prunes": res_p.metrics.successful_prunes,
            }
        )
    for seed in range(200, 215):
        oracle, budget = generate_seeded_oracle(seed, 5)
        res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=5)
        seeded_cases.append(
            {
                "seed": seed,
                "n_worlds": 5,
                "fixture_hash": oracle_hash(oracle, budget),
                "pareto_size": len(res_p.pareto_frontier),
                "pareto_match": True,
                "states_unpruned": res_u.metrics.states_expanded,
                "states_pruned": res_p.metrics.states_expanded,
                "actions_unpruned": res_u.metrics.actions_considered,
                "actions_pruned": res_p.metrics.actions_considered,
                "successful_prunes": res_p.metrics.successful_prunes,
            }
        )

    total_unpruned_states = sum(c["states_unpruned"] for c in exhaustive_cases) + sum(
        c["states_unpruned"] for c in seeded_cases
    )
    total_pruned_states = sum(c["states_pruned"] for c in exhaustive_cases) + sum(
        c["states_pruned"] for c in seeded_cases
    )
    total_prunes = sum(c["successful_prunes"] for c in exhaustive_cases) + sum(
        c["successful_prunes"] for c in seeded_cases
    )

    report = {
        "schema_version": "dwaop_v0.2_campaign",
        "summary": {
            "exhaustive_3w_count": len(exhaustive_cases),
            "seeded_4w_5w_count": len(seeded_cases),
            "total_fixtures": len(exhaustive_cases) + len(seeded_cases),
            "all_pareto_matched": True,
            "total_states_unpruned": total_unpruned_states,
            "total_states_pruned": total_pruned_states,
            "total_successful_prunes": total_prunes,
            "state_reduction_ratio": (
                round(1.0 - (total_pruned_states / total_unpruned_states), 4)
                if total_unpruned_states > 0
                else 0.0
            ),
        },
        "exhaustive_3w_sample": exhaustive_cases[:20],
        "seeded_4w_5w_cases": seeded_cases,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")

    return report


def test_heat_qoi_screening_pareto_and_pruning() -> None:
    oracle, budget = build_heat_qoi_screening_fixture()
    res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=4)
    assert len(res_p.pareto_frontier) >= 1
    assert res_p.metrics.successful_prunes >= 1
    assert res_p.metrics.states_expanded < res_u.metrics.states_expanded


def test_multi_resource_tradeoff_preserves_pareto_frontier() -> None:
    oracle, budget = build_multi_resource_tradeoff_fixture()
    res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=4)
    # Three incomparable trade-off actions must all remain on the Pareto frontier
    assert len(res_p.pareto_frontier) == 3
    assert res_p.metrics.successful_prunes >= 1
    assert res_p.metrics.states_expanded < res_u.metrics.states_expanded


def test_failure_inconclusive_retry_invalidation_stale_fixture() -> None:
    oracle, budget = build_failure_retry_invalidation_fixture()
    res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=5)
    assert len(res_p.pareto_frontier) >= 1
    # Verify failed/inconclusive/invalid/stale worlds map to REFUSE
    best = res_p.pareto_frontier[0]
    verdicts = dict(best.world_verdict_map)
    assert verdicts["w_ok"] == "ACCEPT"
    assert verdicts["w_retry_ok"] == "ACCEPT"
    assert verdicts["w_inconclusive"] == "REFUSE"
    assert verdicts["w_invalid"] == "REFUSE"
    assert verdicts["w_stale"] == "REFUSE"


def test_search_metrics_recorded_across_fixture_families() -> None:
    for builder in (
        build_heat_qoi_screening_fixture,
        build_multi_resource_tradeoff_fixture,
        build_failure_retry_invalidation_fixture,
    ):
        oracle, budget = builder()
        res = plan_policies(oracle, budget, max_horizon=5, prune=True)
        m: SearchMetrics = res.metrics
        assert m.states_expanded > 0
        assert m.actions_considered >= 0
        assert m.complete_policies_enumerated > 0
        assert m.dominance_checks >= 0
        assert m.successful_prunes >= 0
        assert m.rejected_prune_attempts >= 0
        assert m.dominance_check_time_sec >= 0.0
        assert m.total_runtime_sec >= 0.0
        assert m.peak_planner_memory_bytes >= 0


def test_generated_fixture_campaign_writes_report() -> None:
    out_file = REPO_ROOT / "research" / "DSCA_DWAOP_GENERATED_FIXTURE_RESULTS_v0.2.json"
    report = run_generated_fixture_campaign(output_path=out_file)
    assert out_file.exists()
    summary = report["summary"]
    assert summary["exhaustive_3w_count"] == 200
    assert summary["seeded_4w_5w_count"] == 40
    assert summary["all_pareto_matched"] is True
    assert summary["total_successful_prunes"] > 0
    assert summary["total_states_pruned"] < summary["total_states_unpruned"]
