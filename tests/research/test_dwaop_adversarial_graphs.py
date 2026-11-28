"""Adversarial graph tests (Strategies A, B, and C) for DWAOP v0.2."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import math
from pathlib import Path
import sys
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TESTS_RESEARCH_DIR = Path(__file__).resolve().parent
if str(TESTS_RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_RESEARCH_DIR))

from research.prototypes.dwaop_integrated_planner import (
    ActionContract,
    ContractError,
    EvidenceState,
    FAILURE_OR_INCONCLUSIVE_KINDS,
    NormalizedPolicy,
    OutcomeCell,
    OutcomeCertificate,
    OutcomeKind,
    ResourceBudget,
    ResourceVector,
    WorldOracle,
    _enabled,
    apply_action_outcome,
    build_action_contract,
    is_complete_refinement_cover,
    is_local_refinement,
    make_initial_state,
    plan_policies,
    terminal_verdict,
    validate_oracle,
    verify_action_contract,
    verify_state_provenance,
)
from research.prototypes.dwaop_exhaustive_policy_oracle import (
    ActionBranch,
    LeafVerdict,
    PolicyTree,
    _SimState,
    _evaluate_tree_on_world,
    _independent_enabled,
    enumerate_exact_pareto_frontier,
)
from test_dwaop_integrated_pruning import (
    _all_partitions,
    assert_frontiers_match,
    generate_seeded_oracle,
    make_action,
)


def _make_standard_oracle() -> tuple[WorldOracle, ResourceBudget]:
    universe = frozenset({"w0", "w1", "w2"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT"}
    fine = make_action(
        "fine_act",
        "op_main",
        universe,
        {"w0": "l0", "w1": "l1", "w2": "l2"},
        ru_upper=1.0,
        cpu_ticks=10.0,
        energy_ticks=5.0,
        workspace_gb_upper=1.0,
        overlap_gb_upper=0.2,
        discharged_by_label={
            "l0": frozenset({"ob1"}),
            "l1": frozenset({"ob1"}),
            "l2": frozenset({"ob1"}),
        },
        capabilities_by_label={
            "l0": frozenset({"cap1"}),
            "l1": frozenset({"cap1"}),
            "l2": frozenset({"cap1"}),
        },
    )
    coarse = make_action(
        "coarse_act",
        "op_main",
        universe,
        {"w0": "c0", "w1": "c0", "w2": "c1"},
        ru_upper=2.0,
        cpu_ticks=20.0,
        energy_ticks=10.0,
        workspace_gb_upper=1.5,
        overlap_gb_upper=0.3,
        discharged_by_label={
            "c0": frozenset({"ob1"}),
            "c1": frozenset({"ob1"}),
        },
        capabilities_by_label={
            "c0": frozenset({"cap1"}),
            "c1": frozenset({"cap1"}),
        },
    )
    oracle = WorldOracle(
        specification_id="spec_adv",
        model_id="m_adv",
        assurance_scope="adv_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"fine_act": fine, "coarse_act": coarse},
        initial_obligations=frozenset({"ob1"}),
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    return oracle, budget


# ---------------------------------------------------------------------------
# Strategy A: Exhaustive tiny 3-world cases
# ---------------------------------------------------------------------------

def test_strategy_a_exhaustive_3world_partitions() -> None:
    worlds = ("w0", "w1", "w2")
    universe = frozenset(worlds)
    partitions = _all_partitions(worlds)
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)

    checked = 0
    for dec_bits in product(("ACCEPT", "REJECT"), repeat=3):
        decisions = dict(zip(worlds, dec_bits))
        for p_a in partitions:
            obs_a = {w: f"a_{ci}" for ci, cell in enumerate(p_a) for w in cell}
            for p_b in partitions:
                obs_b = {w: f"b_{ci}" for ci, cell in enumerate(p_b) for w in cell}
                actions = {
                    "act_a": make_action("act_a", "op", universe, obs_a, ru_upper=1.0),
                    "act_b": make_action("act_b", "op", universe, obs_b, ru_upper=2.0),
                    "act_leaf": make_action(
                        "act_leaf",
                        "leaf",
                        universe,
                        {w: f"d_{decisions[w]}" for w in worlds},
                        ru_upper=0.5,
                    ),
                }
                oracle = WorldOracle(
                    specification_id="spec_a",
                    model_id="m_a",
                    assurance_scope="strategy_a",
                    universe=universe,
                    decision_by_world=decisions,
                    actions=actions,
                )
                assert_frontiers_match(oracle, budget, max_horizon=4)
                checked += 1
    assert checked == 200


# ---------------------------------------------------------------------------
# Strategy B: Deterministic seeded 4-world and 5-world graphs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", list(range(300, 320)))
def test_strategy_b_seeded_4world_graphs(seed: int) -> None:
    oracle, budget = generate_seeded_oracle(seed, 4)
    assert_frontiers_match(oracle, budget, max_horizon=5)


@pytest.mark.parametrize("seed", list(range(400, 415)))
def test_strategy_b_seeded_5world_graphs(seed: int) -> None:
    oracle, budget = generate_seeded_oracle(seed, 5)
    assert_frontiers_match(oracle, budget, max_horizon=5)


# ---------------------------------------------------------------------------
# Strategy C: All 15 hand-constructed adversarial counterexamples
# ---------------------------------------------------------------------------

def test_c01_omitted_outcomes() -> None:
    oracle, _ = _make_standard_oracle()
    contract = build_action_contract(oracle, "fine_act")
    omitted = replace(contract, outcomes=contract.outcomes[:-1])
    with pytest.raises(ContractError):
        verify_action_contract(oracle, omitted)


def test_c02_overlapping_outcome_cells() -> None:
    oracle, _ = _make_standard_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    overlapping_c1 = replace(c1, worlds=c1.worlds | {"w0"})
    bad = replace(contract, outcomes=(c0, overlapping_c1, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, bad)


def test_c03_sibling_empty_or_invalid_world_set() -> None:
    oracle, budget = _make_standard_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_act"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_act"], oracle)[0].state

    empty_sibling = replace(fine_children[0], worlds=frozenset())
    assert not is_complete_refinement_cover([empty_sibling] + fine_children[1:], coarse_child, contracts, oracle, budget)

    invalid_sibling = replace(fine_children[0], worlds=frozenset({"w_bogus"}))
    assert not is_complete_refinement_cover([invalid_sibling] + fine_children[1:], coarse_child, contracts, oracle, budget)


def test_c04_duplicate_siblings() -> None:
    oracle, budget = _make_standard_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_act"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_act"], oracle)[0].state

    duplicated = [fine_children[0], fine_children[0], fine_children[2]]
    assert not is_complete_refinement_cover(duplicated, coarse_child, contracts, oracle, budget)


def test_c05_incomplete_sibling_cover() -> None:
    oracle, budget = _make_standard_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_act"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_act"], oracle)[0].state

    assert not is_complete_refinement_cover(fine_children[:-1], coarse_child, contracts, oracle, budget)


def test_c06_wrong_parent_provenance() -> None:
    oracle, budget = _make_standard_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_act"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_act"], oracle)[0].state

    forged_parent = replace(root, resource_spent=ResourceVector(ru_upper=99.0))
    tampered_child = replace(fine_children[0], parent_state_snapshot=forged_parent)
    assert not verify_state_provenance(tampered_child, contracts, oracle)
    assert not is_complete_refinement_cover([tampered_child] + fine_children[1:], coarse_child, contracts, oracle, budget)


def test_c07_action_failure_hidden_as_success() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "ACCEPT"}
    act = make_action(
        "failing_act",
        "solve",
        universe,
        {"w0": "ok", "w1": "err"},
        outcome_kind_by_label={"ok": OutcomeKind.SUCCESS, "err": OutcomeKind.NUMERICAL_BREAKDOWN},
        discharged_by_label={"ok": frozenset({"ob"}), "err": frozenset({"ob"})},
    )
    oracle = WorldOracle(
        specification_id="spec_fail",
        model_id="m_fail",
        assurance_scope="fail_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"failing_act": act},
        initial_obligations=frozenset({"ob"}),
    )
    root = make_initial_state(oracle)
    contract = build_action_contract(oracle, "failing_act")
    transitions = apply_action_outcome(root, contract, oracle)
    err_state = next(t.state for t in transitions if t.outcome_label == "err")
    # Failed outcome must NOT discharge obligations and must terminate as REFUSE, never ACCEPT
    assert "ob" in err_state.open_obligations
    assert terminal_verdict(err_state, oracle) == "REFUSE"


def test_c08_stale_certificate_reuse_after_model_invalidation() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "ACCEPT"}
    inv = make_action(
        "inv_act",
        "inv",
        universe,
        {"w0": "broken", "w1": "broken"},
        outcome_kind_by_label={"broken": OutcomeKind.MODEL_INVALIDATED},
        invalidates_model_by_label={"broken": True},
        discharged_by_label={"broken": frozenset()},
        capabilities_by_label={"broken": frozenset({"cap_after_inv"})},
    )
    follow = make_action(
        "follow_act",
        "follow",
        universe,
        {"w0": "done", "w1": "done"},
        required_capabilities=frozenset({"cap_after_inv"}),
        discharged_by_label={"done": frozenset({"ob"})},
    )
    oracle = WorldOracle(
        specification_id="spec_inv",
        model_id="m_inv",
        assurance_scope="inv_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"inv_act": inv, "follow_act": follow},
        initial_obligations=frozenset({"ob"}),
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    res = plan_policies(oracle, budget, max_horizon=4, prune=True)
    # After inv_act, model is invalidated; even if follow_act runs, verdict must remain REFUSE
    for pol in res.pareto_frontier:
        verdicts = dict(pol.world_verdict_map)
        assert all(v == "REFUSE" for v in verdicts.values())


def test_c09_obligation_incorrectly_marked_discharged() -> None:
    oracle, _ = _make_standard_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    forged_c0 = replace(c0, discharged_obligations=frozenset({"ob1", "ob_forged"}))
    bad = replace(contract, outcomes=(forged_c0, c1, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, bad)


def test_c10_resource_underestimation_and_nonfinite_rejection() -> None:
    oracle, _ = _make_standard_oracle()
    contract = build_action_contract(oracle, "fine_act")
    under_ru = replace(contract, ru_upper=contract.ru_upper - 0.5)
    with pytest.raises(ContractError):
        verify_action_contract(oracle, under_ru)

    for bad_val in (-1.0, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ContractError):
            ResourceVector(ru_upper=bad_val)
        with pytest.raises(ContractError):
            ResourceBudget(ru_upper=bad_val, cpu_ticks=1.0, energy_ticks=1.0, peak_memory_gb=1.0)


def test_c11_incompatible_failure_contracts() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT"}
    a_fine = make_action(
        "a_fine",
        "shared",
        universe,
        {"w0": "l0", "w1": "l1"},
        failure_semantics=frozenset({"fail_a"}),
    )
    a_coarse = make_action(
        "a_coarse",
        "shared",
        universe,
        {"w0": "all", "w1": "all"},
        failure_semantics=frozenset({"fail_b"}),
        ru_upper=5.0,
    )
    oracle = WorldOracle(
        specification_id="spec_fc",
        model_id="m_fc",
        assurance_scope="fc_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"a_fine": a_fine, "a_coarse": a_coarse},
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["a_fine"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["a_coarse"], oracle)[0].state
    assert not is_complete_refinement_cover(fine_children, coarse_child, contracts, oracle, budget)


def test_c12_coarser_observation_cannot_preserve_finer_continuation() -> None:
    universe = frozenset({"w0", "w1", "w2"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT"}
    a_coarse = make_action("a_coarse", "op", universe, {"w0": "m", "w1": "m", "w2": "m"})
    a_fine = make_action("a_fine", "op", universe, {"w0": "l0", "w1": "l1", "w2": "l2"})
    oracle = WorldOracle(
        specification_id="spec_c12",
        model_id="m_c12",
        assurance_scope="c12_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"a_coarse": a_coarse, "a_fine": a_fine},
    )
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    coarse_child = apply_action_outcome(root, contracts["a_coarse"], oracle)[0].state
    fine_children = [t.state for t in apply_action_outcome(root, contracts["a_fine"], oracle)]
    # Coarse child cannot locally refine any of the finer terminal children
    assert not is_local_refinement(coarse_child, fine_children[0], contracts, oracle)


def test_c13_clairvoyant_branching_on_hidden_world_identity() -> None:
    oracle, _ = _make_standard_oracle()
    clairvoyant = replace(oracle, allow_clairvoyant_world_branching=True)
    with pytest.raises(ContractError):
        validate_oracle(clairvoyant)


def test_c14_finite_horizon_exhaustion() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT"}
    step1 = make_action("step1", "s1", universe, {"w0": "x", "w1": "x"}, capabilities_by_label={"x": frozenset({"c1"})})
    step2 = make_action(
        "step2",
        "s2",
        universe,
        {"w0": "y0", "w1": "y1"},
        required_capabilities=frozenset({"c1"}),
    )
    oracle = WorldOracle(
        specification_id="spec_h",
        model_id="m_h",
        assurance_scope="h_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"step1": step1, "step2": step2},
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    # Horizon 1 is insufficient to reach a separating terminal verdict
    res_h1 = plan_policies(oracle, budget, max_horizon=1, prune=True)
    assert res_h1.pareto_frontier == ()
    # Horizon 2 succeeds
    res_h2 = plan_policies(oracle, budget, max_horizon=2, prune=True)
    assert len(res_h2.pareto_frontier) == 1


def test_c15_bounded_retry_exhaustion_disables_infinite_retry() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT"}
    retry_act = make_action(
        "retry_act",
        "retry_op",
        universe,
        {"w0": "try", "w1": "try"},
        outcome_kind_by_label={"try": OutcomeKind.BOUNDED_RETRY},
        retry_cost_by_label={"try": 1},
    )
    oracle = WorldOracle(
        specification_id="spec_retry",
        model_id="m_retry",
        assurance_scope="retry_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"retry_act": retry_act},
        initial_retries=1,
    )
    root = make_initial_state(oracle)
    contract = build_action_contract(oracle, "retry_act")
    t1 = apply_action_outcome(root, contract, oracle)
    assert len(t1) == 1
    after_one = t1[0].state
    assert after_one.remaining_retries == 0
    # Retries exhausted -> retry_act cannot be applied again
    t2 = apply_action_outcome(after_one, contract, oracle)
    assert t2 == ()


def test_c16_refuse_with_recovery_does_not_unsoundly_prune() -> None:
    """Agent C counterexample: non-sticky REFUSE (e.g. TIMEOUT) with recovery action."""
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT"}
    fine_timeout = make_action(
        "a_fine",
        "probe",
        universe,
        {"w0": "t0", "w1": "t1"},
        outcome_kind_by_label={"t0": OutcomeKind.TIMEOUT, "t1": OutcomeKind.TIMEOUT},
        ru_upper=1.0,
    )
    coarse_timeout = make_action(
        "b_coarse",
        "probe",
        universe,
        {"w0": "tc", "w1": "tc"},
        outcome_kind_by_label={"tc": OutcomeKind.TIMEOUT},
        capabilities_by_label={"tc": frozenset({"cap_recover"})},
        ru_upper=1.0,
    )
    recover = make_action(
        "c_recover",
        "recover",
        universe,
        {"w0": "ok0", "w1": "ok1"},
        required_capabilities=frozenset({"cap_recover"}),
        ru_upper=1.0,
    )
    oracle = WorldOracle(
        specification_id="spec_c16",
        model_id="m_c16",
        assurance_scope="scope_c16",
        universe=universe,
        decision_by_world=decisions,
        actions={"a_fine": fine_timeout, "b_coarse": coarse_timeout, "c_recover": recover},
    )
    budget = ResourceBudget(ru_upper=5.0, cpu_ticks=50.0, energy_ticks=50.0, peak_memory_gb=8.0)
    unpruned = plan_policies(oracle, budget, max_horizon=4, prune=False)
    pruned = plan_policies(oracle, budget, max_horizon=4, prune=True)
    exact = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=4)
    assert pruned.pareto_frontier == unpruned.pareto_frontier == exact
    assert any(p.terminal_verdicts == frozenset({"ACCEPT", "REJECT"}) for p in pruned.pareto_frontier)


def test_c17_unrecoverable_refusal_is_sticky() -> None:
    """UNRECOVERABLE_REFUSAL must permanently terminate in REFUSE without recovery to ACCEPT."""
    universe = frozenset({"w0"})
    decisions = {"w0": "ACCEPT"}
    fail_act = make_action(
        "fail_act",
        "fail_op",
        universe,
        {"w0": "fatal"},
        outcome_kind_by_label={"fatal": OutcomeKind.UNRECOVERABLE_REFUSAL},
        ru_upper=1.0,
    )
    recover = make_action(
        "recover",
        "recover_op",
        universe,
        {"w0": "ok"},
        discharged_by_label={"ok": frozenset({"ob1"})},
        ru_upper=1.0,
    )
    oracle = WorldOracle(
        specification_id="spec_c17",
        model_id="m_c17",
        assurance_scope="scope_c17",
        universe=universe,
        decision_by_world=decisions,
        actions={"fail_act": fail_act, "recover": recover},
        initial_obligations=frozenset({"ob1"}),
    )
    budget = ResourceBudget(ru_upper=5.0, cpu_ticks=50.0, energy_ticks=50.0, peak_memory_gb=8.0)
    res_p = plan_policies(oracle, budget, max_horizon=3, prune=True)
    res_u = plan_policies(oracle, budget, max_horizon=3, prune=False)
    exact = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=3)
    assert res_p.pareto_frontier == res_u.pareto_frontier == exact
    # fail_act path cannot recover to ACCEPT; only recover-first reaches ACCEPT
    assert len(res_p.pareto_frontier) == 1
    assert res_p.pareto_frontier[0].terminal_verdicts == frozenset({"ACCEPT"})
    assert res_p.pareto_frontier[0].resource_vector.ru_upper == 1.0


# ---------------------------------------------------------------------------
# Stage 2 Regressions: Sticky UNRECOVERABLE_REFUSAL & Bellman max-masking
# ---------------------------------------------------------------------------


def _mk_zero_mem_action(
    action_id: str,
    semantic_key: str,
    applicable_worlds: FrozenSet[str],
    obs: Mapping[str, str],
    *,
    ru_upper: float = 1.0,
    cpu_ticks: float = 0.0,
    energy_ticks: float = 0.0,
    required_obligations: FrozenSet[str] = frozenset(),
    required_capabilities: FrozenSet[str] = frozenset(),
    outcome_kind_by_label: Optional[Mapping[str, OutcomeKind]] = None,
    discharged_by_label: Optional[Mapping[str, FrozenSet[str]]] = None,
    capabilities_by_label: Optional[Mapping[str, FrozenSet[str]]] = None,
    retry_cost_by_label: Optional[Mapping[str, int]] = None,
    invalidates_model_by_label: Optional[Mapping[str, bool]] = None,
    stale_evidence_by_label: Optional[Mapping[str, bool]] = None,
):
    return make_action(
        action_id,
        semantic_key,
        applicable_worlds,
        obs,
        ru_upper=ru_upper,
        cpu_ticks=cpu_ticks,
        energy_ticks=energy_ticks,
        workspace_gb_upper=0.0,
        overlap_gb_upper=0.0,
        required_obligations=required_obligations,
        required_capabilities=required_capabilities,
        outcome_kind_by_label=outcome_kind_by_label,
        discharged_by_label=discharged_by_label,
        capabilities_by_label=capabilities_by_label,
        retained_output_gb_by_label={lbl: 0.0 for lbl in set(obs.values())},
        released_memory_gb_by_label={lbl: 0.0 for lbl in set(obs.values())},
        retry_cost_by_label=retry_cost_by_label,
        invalidates_model_by_label=invalidates_model_by_label,
        stale_evidence_by_label=stale_evidence_by_label,
    )


def _explicit_reference_frontier(
    oracle: WorldOracle,
    budget: ResourceBudget,
    max_horizon: int,
) -> Tuple[NormalizedPolicy, ...]:
    """Independent reference enumerator & Pareto reducer for bounded equivalence tests."""
    sorted_worlds = sorted(oracle.universe)

    def _ref_enum(
        worlds: FrozenSet[str],
        obs: FrozenSet[str],
        caps: FrozenSet[str],
        rem_acts: FrozenSet[str],
        retries: int,
        valid: bool,
        stale: bool,
        last_kind: Optional[OutcomeKind],
        depth_left: int,
    ) -> List[PolicyTree]:
        if depth_left < 0 or not worlds:
            return []
        sticky = (not valid) or stale or (last_kind == OutcomeKind.UNRECOVERABLE_REFUSAL)
        if sticky or last_kind in FAILURE_OR_INCONCLUSIVE_KINDS:
            if sticky:
                return [LeafVerdict("REFUSE")]
            trees: List[PolicyTree] = [LeafVerdict("REFUSE")]
        elif not obs and len({oracle.decision_by_world[w] for w in worlds}) == 1:
            return [LeafVerdict(oracle.decision_by_world[next(iter(worlds))])]
        else:
            trees = []

        if depth_left == 0:
            return trees

        for aid in sorted(rem_acts):
            spec = oracle.actions[aid]
            if not (
                worlds <= spec.applicable_worlds
                and spec.required_capabilities <= caps
                and spec.required_obligations <= obs
            ):
                continue
            labels = sorted({spec.observable_label_by_world[w] for w in worlds})
            if any(
                spec.outcome_kind_by_label[lbl] == OutcomeKind.BOUNDED_RETRY
                and retries < max(1, spec.retry_cost_by_label[lbl])
                for lbl in labels
            ):
                continue

            sub_lists: List[List[PolicyTree]] = []
            ok = True
            for lbl in labels:
                sub_w = frozenset(w for w in worlds if spec.observable_label_by_world[w] == lbl)
                kind = spec.outcome_kind_by_label[lbl]
                nv = valid and not (spec.invalidates_model_by_label[lbl] or kind == OutcomeKind.MODEL_INVALIDATED)
                ns = stale or (spec.stale_evidence_by_label[lbl] or kind == OutcomeKind.STALE_EVIDENCE)
                nr = retries - max(1, spec.retry_cost_by_label[lbl]) if kind == OutcomeKind.BOUNDED_RETRY else retries
                nrem = rem_acts if kind == OutcomeKind.BOUNDED_RETRY else (rem_acts - {aid})
                nobs = obs - spec.discharged_by_label[lbl] if (nv and not ns and kind not in FAILURE_OR_INCONCLUSIVE_KINDS) else obs
                ncaps = caps | spec.capabilities_by_label[lbl]
                children = _ref_enum(sub_w, nobs, ncaps, nrem, nr, nv, ns, kind, depth_left - 1)
                if not children:
                    ok = False
                    break
                sub_lists.append(children)
            if ok:
                for combo in product(*sub_lists):
                    trees.append(ActionBranch(aid, dict(zip(labels, combo))))
        return trees

    def _ref_eval(tree: PolicyTree, world: str) -> Optional[Tuple[str, ResourceVector, int]]:
        obs = oracle.initial_obligations
        caps = oracle.initial_capabilities
        rem_acts = frozenset(oracle.actions)
        retries = oracle.initial_retries
        valid = True
        stale = False
        last_kind: Optional[OutcomeKind] = None
        ru = Fraction(0)
        cpu = Fraction(0)
        energy = Fraction(0)
        resident = Fraction(0)
        peak = Fraction(0)
        steps = 0
        node = tree
        while isinstance(node, ActionBranch):
            if (not valid) or stale or last_kind == OutcomeKind.UNRECOVERABLE_REFUSAL:
                return None
            spec = oracle.actions.get(node.action_id)
            if spec is None or node.action_id not in rem_acts or world not in spec.applicable_worlds:
                return None
            if not (spec.required_capabilities <= caps and spec.required_obligations <= obs):
                return None
            lbl = spec.observable_label_by_world[world]
            if lbl not in node.branches_by_label:
                return None
            kind = spec.outcome_kind_by_label[lbl]
            if kind == OutcomeKind.BOUNDED_RETRY:
                need = max(1, spec.retry_cost_by_label[lbl])
                if retries < need:
                    return None
                retries -= need
            else:
                rem_acts = rem_acts - {node.action_id}
            during = resident + Fraction(str(spec.workspace_gb_upper)) + Fraction(str(spec.overlap_gb_upper))
            resident = max(
                Fraction(0),
                resident
                + Fraction(str(spec.retained_output_gb_by_label[lbl]))
                - Fraction(str(spec.released_memory_gb_by_label[lbl])),
            )
            peak = max(peak, during, resident)
            ru += Fraction(str(spec.ru_upper))
            cpu += Fraction(str(spec.cpu_ticks))
            energy += Fraction(str(spec.energy_ticks))
            if not budget.allows(ResourceVector(ru, cpu, energy, peak)):
                return None
            valid = valid and not (spec.invalidates_model_by_label[lbl] or kind == OutcomeKind.MODEL_INVALIDATED)
            stale = stale or (spec.stale_evidence_by_label[lbl] or kind == OutcomeKind.STALE_EVIDENCE)
            if valid and not stale and kind not in FAILURE_OR_INCONCLUSIVE_KINDS:
                obs = obs - spec.discharged_by_label[lbl]
            caps = caps | spec.capabilities_by_label[lbl]
            last_kind = kind
            steps += 1
            node = node.branches_by_label[lbl]

        if node.verdict in {"ACCEPT", "REJECT"}:
            if not (valid and not stale and not obs and oracle.decision_by_world[world] == node.verdict):
                return None
        elif node.verdict == "REFUSE":
            if not ((not valid) or stale or last_kind in FAILURE_OR_INCONCLUSIVE_KINDS):
                return None
        else:
            return None
        return node.verdict, ResourceVector(ru, cpu, energy, peak), steps

    def _ref_dom(a: NormalizedPolicy, b: NormalizedPolicy) -> bool:
        for (wa, va), (wb, vb) in zip(a.world_verdict_map, b.world_verdict_map):
            if wa != wb:
                return False
            if va != vb and not (va in {"ACCEPT", "REJECT"} and vb == "REFUSE"):
                return False
        if not a.resource_vector.dominates_or_equal(b.resource_vector):
            return False
        return (
            a.world_verdict_map != b.world_verdict_map
            or a.resource_vector.strictly_dominates(b.resource_vector)
        )

    candidates: Dict[tuple, NormalizedPolicy] = {}
    for tree in _ref_enum(
        oracle.universe,
        oracle.initial_obligations,
        oracle.initial_capabilities,
        frozenset(oracle.actions),
        oracle.initial_retries,
        True,
        False,
        None,
        max_horizon,
    ):
        evals = [_ref_eval(tree, w) for w in sorted_worlds]
        if any(e is None for e in evals):
            continue
        vmap = tuple((w, e[0]) for w, e in zip(sorted_worlds, evals) if e is not None)
        vec = ResourceVector.max_across([e[1] for e in evals if e is not None])
        if not budget.allows(vec):
            continue
        max_len = max(e[2] for e in evals if e is not None)
        pol = NormalizedPolicy(
            world_verdict_map=vmap,
            resource_vector=vec,
            terminal_verdicts=frozenset(v for _, v in vmap),
            max_actions_on_path=max_len,
        )
        k = (pol.world_verdict_map, pol.terminal_verdicts, pol.resource_vector.exact_key())
        prev = candidates.get(k)
        if prev is None or pol.max_actions_on_path < prev.max_actions_on_path:
            candidates[k] = pol

    vals = list(candidates.values())
    kept = [c for c in vals if not any(o is not c and _ref_dom(o, c) for o in vals)]
    return tuple(
        sorted(kept, key=lambda p: (p.world_verdict_map, p.resource_vector.exact_key(), p.max_actions_on_path))
    )


def test_ce5b_bellman_max_masking_preserves_shortest_tie_witness() -> None:
    """CE-5B: Internal OR-node must keep costlier shorter witness when sibling max masks resource."""
    u = frozenset({"w0", "w1"})
    oracle = WorldOracle(
        specification_id="ce5b",
        model_id="m_ce5b",
        assurance_scope="stage2_reg",
        universe=u,
        decision_by_world={"w0": "ACCEPT", "w1": "ACCEPT"},
        initial_obligations=frozenset({"ob0", "ob1"}),
        actions={
            "split": _mk_zero_mem_action(
                "split", "sp", u, {"w0": "b0", "w1": "b1"},
                required_obligations=frozenset({"ob0", "ob1"}), ru_upper=0.0,
                discharged_by_label={"b0": frozenset({"ob0"}), "b1": frozenset({"ob0"})},
                capabilities_by_label={"b0": frozenset({"c0"}), "b1": frozenset({"c1"})},
            ),
            "w0_done": _mk_zero_mem_action(
                "w0_done", "d0", frozenset({"w0"}), {"w0": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c0"}),
                ru_upper=2.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
            "w1_fast": _mk_zero_mem_action(
                "w1_fast", "d1f", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c1"}),
                ru_upper=2.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
            "w1_s1": _mk_zero_mem_action(
                "w1_s1", "d1s1", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c1"}),
                ru_upper=0.5, capabilities_by_label={"ok": frozenset({"s2"})},
            ),
            "w1_s2": _mk_zero_mem_action(
                "w1_s2", "d1s2", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"s2"}),
                ru_upper=0.5, capabilities_by_label={"ok": frozenset({"s3"})},
            ),
            "w1_s3": _mk_zero_mem_action(
                "w1_s3", "d1s3", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"s3"}),
                ru_upper=0.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
        },
    )
    budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
    res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=4)
    assert res_p.pareto_frontier == res_u.pareto_frontier == _explicit_reference_frontier(oracle, budget, 4)
    assert len(res_p.pareto_frontier) == 1
    assert res_p.pareto_frontier[0].max_actions_on_path == 2
    assert res_p.pareto_frontier[0].resource_vector.ru_upper == Fraction(2, 1)


def test_ce6a_unrecoverable_refusal_does_not_prune_recoverable_timeout() -> None:
    """CE-6A: Sticky UNRECOVERABLE_REFUSAL fine state must not prune recoverable TIMEOUT coarse state."""
    u = frozenset({"w0"})
    oracle = WorldOracle(
        specification_id="ce6a",
        model_id="m_ce6a",
        assurance_scope="stage2_reg",
        universe=u,
        decision_by_world={"w0": "ACCEPT"},
        initial_obligations=frozenset({"ob"}),
        actions={
            "a_fine": _mk_zero_mem_action(
                "a_fine", "probe", u, {"w0": "fail"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0,
                outcome_kind_by_label={"fail": OutcomeKind.UNRECOVERABLE_REFUSAL},
                capabilities_by_label={"fail": frozenset({"probed"})},
            ),
            "b_coarse": _mk_zero_mem_action(
                "b_coarse", "probe", u, {"w0": "to"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0,
                outcome_kind_by_label={"to": OutcomeKind.TIMEOUT},
                capabilities_by_label={"to": frozenset({"probed"})},
            ),
            "recover": _mk_zero_mem_action(
                "recover", "rec", u, {"w0": "ok"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"probed"}),
                ru_upper=0.0, discharged_by_label={"ok": frozenset({"ob"})},
            ),
        },
    )
    budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
    contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
    root = make_initial_state(oracle)
    fine_child = apply_action_outcome(root, contracts["a_fine"], oracle)[0].state
    coarse_child = apply_action_outcome(root, contracts["b_coarse"], oracle)[0].state

    assert _enabled(fine_child, contracts["recover"], oracle) is False
    assert is_local_refinement(fine_child, coarse_child, contracts, oracle, depth_left=1) is False
    assert is_complete_refinement_cover([fine_child], coarse_child, contracts, oracle, budget, depth_left=1) is False

    res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=2)
    assert res_p.pareto_frontier == res_u.pareto_frontier == _explicit_reference_frontier(oracle, budget, 2)
    assert len(res_p.pareto_frontier) == 1
    assert res_p.pareto_frontier[0].world_verdict_map == (("w0", "ACCEPT"),)
    assert res_p.pareto_frontier[0].max_actions_on_path == 2


def test_ce6b_branching_unrecoverable_refusal_does_not_prune_recoverable_coarse() -> None:
    """CE-6B: 2-outcome branching fine action with one UNRECOVERABLE_REFUSAL child must not prune coarse."""
    u = frozenset({"w0", "w1"})
    oracle = WorldOracle(
        specification_id="ce6b",
        model_id="m_ce6b",
        assurance_scope="stage2_reg",
        universe=u,
        decision_by_world={"w0": "ACCEPT", "w1": "REJECT"},
        initial_obligations=frozenset({"ob"}),
        actions={
            "fine_probe": _mk_zero_mem_action(
                "fine_probe", "probe", u, {"w0": "to", "w1": "unrec"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0,
                outcome_kind_by_label={
                    "to": OutcomeKind.TIMEOUT,
                    "unrec": OutcomeKind.UNRECOVERABLE_REFUSAL,
                },
                capabilities_by_label={
                    "to": frozenset({"probed"}),
                    "unrec": frozenset({"probed"}),
                },
            ),
            "coarse_probe": _mk_zero_mem_action(
                "coarse_probe", "probe", u, {"w0": "to", "w1": "to"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0,
                outcome_kind_by_label={"to": OutcomeKind.TIMEOUT},
                capabilities_by_label={"to": frozenset({"probed"})},
            ),
            "recover": _mk_zero_mem_action(
                "recover", "rec", u, {"w0": "ok0", "w1": "ok1"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"probed"}),
                ru_upper=0.5,
                discharged_by_label={"ok0": frozenset({"ob"}), "ok1": frozenset({"ob"})},
            ),
        },
    )
    budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
    contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_probe"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_probe"], oracle)[0].state
    unrec_child = next(s for s in fine_children if s.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL)

    assert is_local_refinement(unrec_child, coarse_child, contracts, oracle, depth_left=1) is False
    assert is_complete_refinement_cover(fine_children, coarse_child, contracts, oracle, budget, depth_left=1) is False

    res_p, _ = assert_frontiers_match(oracle, budget, max_horizon=2)
    assert res_p.pareto_frontier == _explicit_reference_frontier(oracle, budget, 2)
    assert len(res_p.pareto_frontier) == 2
    assert res_p.pareto_frontier[0].world_verdict_map == (("w0", "ACCEPT"), ("w1", "REJECT"))
    assert res_p.pareto_frontier[1].world_verdict_map == (("w0", "REFUSE"), ("w1", "REFUSE"))


def test_ce6c_success_only_pruning_preserves_bellman_tie_witness() -> None:
    """CE-6C: SUCCESS-only complete-cover pruning preserves max_actions_on_path=2 under max-masking."""
    u = frozenset({"w0", "w1"})
    oracle = WorldOracle(
        specification_id="ce6c",
        model_id="m_ce6c",
        assurance_scope="stage2_reg",
        universe=u,
        decision_by_world={"w0": "ACCEPT", "w1": "ACCEPT"},
        initial_obligations=frozenset({"ob0", "ob1"}),
        actions={
            "fine_split": _mk_zero_mem_action(
                "fine_split", "sp", u, {"w0": "b0", "w1": "b1"},
                required_obligations=frozenset({"ob0", "ob1"}), ru_upper=0.0,
                discharged_by_label={"b0": frozenset({"ob0"}), "b1": frozenset({"ob0"})},
                capabilities_by_label={"b0": frozenset({"probed"}), "b1": frozenset({"probed"})},
            ),
            "coarse_step": _mk_zero_mem_action(
                "coarse_step", "sp", u, {"w0": "c", "w1": "c"},
                required_obligations=frozenset({"ob0", "ob1"}), ru_upper=0.0,
                discharged_by_label={"c": frozenset({"ob0"})},
                capabilities_by_label={"c": frozenset({"probed"})},
            ),
            "both_fast": _mk_zero_mem_action(
                "both_fast", "fin", u, {"w0": "ok", "w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"probed"}),
                ru_upper=2.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
            "w1_s1": _mk_zero_mem_action(
                "w1_s1", "d1s1", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"probed"}),
                ru_upper=0.5, capabilities_by_label={"ok": frozenset({"s2"})},
            ),
            "w1_s2": _mk_zero_mem_action(
                "w1_s2", "d1s2", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"s2"}),
                ru_upper=0.5, capabilities_by_label={"ok": frozenset({"s3"})},
            ),
            "w1_s3": _mk_zero_mem_action(
                "w1_s3", "d1s3", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"s3"}),
                ru_upper=0.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
        },
    )
    budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
    res_p, _ = assert_frontiers_match(oracle, budget, max_horizon=4)
    assert res_p.metrics.successful_prunes == 1
    assert res_p.pareto_frontier == _explicit_reference_frontier(oracle, budget, 4)
    assert len(res_p.pareto_frontier) == 1
    assert res_p.pareto_frontier[0].max_actions_on_path == 2
    assert res_p.pareto_frontier[0].resource_vector.ru_upper == Fraction(2, 1)


def test_c7_0_success_only_active_pruning_max_masking() -> None:
    """Campaign 7 (c7_0): SUCCESS-only active pruning with w1 cost-masking matches oracle and reference."""
    u = frozenset({"w0", "w1"})
    oracle = WorldOracle(
        specification_id="c7_0",
        model_id="m7",
        assurance_scope="s7",
        universe=u,
        decision_by_world={"w0": "ACCEPT", "w1": "ACCEPT"},
        initial_obligations=frozenset({"ob"}),
        actions={
            "fine_split": _mk_zero_mem_action(
                "fine_split", "op", u, {"w0": "l0", "w1": "l1"},
                ru_upper=1.0, cpu_ticks=1.0,
                capabilities_by_label={"l0": frozenset({"c_root"}), "l1": frozenset({"c_root"})},
            ),
            "coarse_step": _mk_zero_mem_action(
                "coarse_step", "op", u, {"w0": "all", "w1": "all"},
                ru_upper=1.0, cpu_ticks=1.0,
                capabilities_by_label={"all": frozenset({"c_root"})},
            ),
            "both_fast": _mk_zero_mem_action(
                "both_fast", "bf", u, {"w0": "d0", "w1": "d1"},
                required_capabilities=frozenset({"c_root"}), ru_upper=3.0, cpu_ticks=3.0,
                discharged_by_label={"d0": frozenset({"ob"}), "d1": frozenset({"ob"})},
            ),
            "w0_s1": _mk_zero_mem_action(
                "w0_s1", "ws1", frozenset({"w0"}), {"w0": "m"},
                required_capabilities=frozenset({"c_root"}), ru_upper=1.0, cpu_ticks=1.0,
                capabilities_by_label={"m": frozenset({"c_w0"})},
            ),
            "w0_s2": _mk_zero_mem_action(
                "w0_s2", "ws2", frozenset({"w0"}), {"w0": "ok"},
                required_capabilities=frozenset({"c_w0"}), ru_upper=0.0, cpu_ticks=0.0,
                discharged_by_label={"ok": frozenset({"ob"})},
            ),
            "w1_heavy": _mk_zero_mem_action(
                "w1_heavy", "wh", frozenset({"w1"}), {"w1": "ok"},
                required_capabilities=frozenset({"c_root"}), ru_upper=5.0, cpu_ticks=5.0,
                discharged_by_label={"ok": frozenset({"ob"})},
            ),
        },
    )
    budget = ResourceBudget(30.0, 30.0, 10.0, 10.0)
    res_p, _ = assert_frontiers_match(oracle, budget, max_horizon=4)
    assert res_p.metrics.successful_prunes >= 1
    assert res_p.pareto_frontier == _explicit_reference_frontier(oracle, budget, 4)
    assert len(res_p.pareto_frontier) == 1
    assert res_p.pareto_frontier[0].resource_vector.ru_upper == Fraction(4, 1)
    assert res_p.pareto_frontier[0].max_actions_on_path == 2


def test_standalone_evaluate_tree_on_world_rejects_sticky_refusal_transitions() -> None:
    """Standalone oracle evaluator and enabled predicates reject transitions out of sticky refusals."""
    u = frozenset({"w0"})
    oracle = WorldOracle(
        specification_id="standalone_sticky",
        model_id="m_sticky",
        assurance_scope="stage2_reg",
        universe=u,
        decision_by_world={"w0": "ACCEPT"},
        actions={
            "fatal": _mk_zero_mem_action(
                "fatal", "f", u, {"w0": "err"},
                ru_upper=1.0, cpu_ticks=1.0,
                outcome_kind_by_label={"err": OutcomeKind.UNRECOVERABLE_REFUSAL},
            ),
            "inv": _mk_zero_mem_action(
                "inv", "i", u, {"w0": "bad"},
                ru_upper=1.0, cpu_ticks=1.0,
                outcome_kind_by_label={"bad": OutcomeKind.MODEL_INVALIDATED},
                invalidates_model_by_label={"bad": True},
            ),
            "stale": _mk_zero_mem_action(
                "stale", "s", u, {"w0": "old"},
                ru_upper=1.0, cpu_ticks=1.0,
                outcome_kind_by_label={"old": OutcomeKind.STALE_EVIDENCE},
                stale_evidence_by_label={"old": True},
            ),
            "recover": _mk_zero_mem_action(
                "recover", "r", u, {"w0": "ok"},
                ru_upper=1.0, cpu_ticks=1.0,
            ),
        },
    )
    budget = ResourceBudget(10.0, 10.0, 10.0, 10.0)
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)

    for aid, lbl, kind in (
        ("fatal", "err", OutcomeKind.UNRECOVERABLE_REFUSAL),
        ("inv", "bad", OutcomeKind.MODEL_INVALIDATED),
        ("stale", "old", OutcomeKind.STALE_EVIDENCE),
    ):
        # Immediate leaf REFUSE is valid
        leaf_tree = ActionBranch(aid, {lbl: LeafVerdict("REFUSE")})
        leaf_res = _evaluate_tree_on_world(leaf_tree, "w0", oracle, budget)
        assert leaf_res is not None and leaf_res[0] == "REFUSE"

        # Any further transition out of sticky state must be rejected (even to LeafVerdict("REFUSE"))
        for target_verdict in ("ACCEPT", "REFUSE"):
            bad_tree = ActionBranch(aid, {lbl: ActionBranch("recover", {"ok": LeafVerdict(target_verdict)})})
            assert _evaluate_tree_on_world(bad_tree, "w0", oracle, budget) is None

        # Both planner _enabled and oracle _independent_enabled reject transitions out of sticky state
        sticky_ev_state = apply_action_outcome(root, contracts[aid], oracle)[0].state
        assert _enabled(sticky_ev_state, contracts["recover"], oracle) is False
        sim_state = _SimState(
            worlds=u,
            open_obligations=frozenset(),
            capabilities=frozenset(),
            remaining_actions=frozenset(oracle.actions) - {aid},
            remaining_retries=0,
            model_valid=(aid != "inv"),
            evidence_stale=(aid == "stale"),
            last_outcome_kind=kind,
        )
        assert _independent_enabled(sim_state, "recover", oracle) is False


def test_bounded_multi_entry_frontier_equivalence() -> None:
    """Bounded multi-entry Pareto frontiers match across pruned, unpruned, oracle, and explicit reference."""
    # Case 1: 2-world verdict-vs-resource trade-off + recoverable vs unrecoverable refusal + pruning
    u2 = frozenset({"w0", "w1"})
    o1 = WorldOracle(
        specification_id="multi_1",
        model_id="m_m1",
        assurance_scope="stage2_reg",
        universe=u2,
        decision_by_world={"w0": "ACCEPT", "w1": "REJECT"},
        initial_obligations=frozenset({"ob"}),
        actions={
            "probe_fine": _mk_zero_mem_action(
                "probe_fine", "probe", u2, {"w0": "to", "w1": "unrec"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0, cpu_ticks=2.0,
                outcome_kind_by_label={"to": OutcomeKind.TIMEOUT, "unrec": OutcomeKind.UNRECOVERABLE_REFUSAL},
                capabilities_by_label={"to": frozenset({"p"}), "unrec": frozenset({"p"})},
            ),
            "probe_coarse": _mk_zero_mem_action(
                "probe_coarse", "probe", u2, {"w0": "to", "w1": "to"},
                required_obligations=frozenset({"ob"}), ru_upper=2.0, cpu_ticks=1.0,
                outcome_kind_by_label={"to": OutcomeKind.TIMEOUT},
                capabilities_by_label={"to": frozenset({"p"})},
            ),
            "rec_w0": _mk_zero_mem_action(
                "rec_w0", "rw0", frozenset({"w0"}), {"w0": "ok"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"p"}),
                ru_upper=1.0, cpu_ticks=1.0, discharged_by_label={"ok": frozenset({"ob"})},
            ),
            "rec_all": _mk_zero_mem_action(
                "rec_all", "rall", u2, {"w0": "ok0", "w1": "ok1"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"p"}),
                ru_upper=3.0, cpu_ticks=3.0,
                discharged_by_label={"ok0": frozenset({"ob"}), "ok1": frozenset({"ob"})},
            ),
        },
    )

    # Case 2: 2-world multi-resource trade-off + variable path length + active pruning
    o2 = WorldOracle(
        specification_id="multi_2",
        model_id="m_m2",
        assurance_scope="stage2_reg",
        universe=u2,
        decision_by_world={"w0": "ACCEPT", "w1": "REJECT"},
        initial_obligations=frozenset({"ob0", "ob1"}),
        actions={
            "split_fine": _mk_zero_mem_action(
                "split_fine", "sp", u2, {"w0": "b0", "w1": "b1"},
                required_obligations=frozenset({"ob0", "ob1"}), ru_upper=1.0, cpu_ticks=1.0,
                discharged_by_label={"b0": frozenset({"ob0"}), "b1": frozenset({"ob0"})},
                capabilities_by_label={"b0": frozenset({"c"}), "b1": frozenset({"c"})},
            ),
            "split_coarse": _mk_zero_mem_action(
                "split_coarse", "sp", u2, {"w0": "all", "w1": "all"},
                required_obligations=frozenset({"ob0", "ob1"}), ru_upper=1.0, cpu_ticks=1.0,
                discharged_by_label={"all": frozenset({"ob0"})},
                capabilities_by_label={"all": frozenset({"c"})},
            ),
            "fin_fast": _mk_zero_mem_action(
                "fin_fast", "ff", u2, {"w0": "d0", "w1": "d1"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c"}),
                ru_upper=3.0, cpu_ticks=1.0,
                discharged_by_label={"d0": frozenset({"ob1"}), "d1": frozenset({"ob1"})},
            ),
            "fin_cpu": _mk_zero_mem_action(
                "fin_cpu", "fc", u2, {"w0": "d0", "w1": "d1"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c"}),
                ru_upper=1.0, cpu_ticks=4.0,
                discharged_by_label={"d0": frozenset({"ob1"}), "d1": frozenset({"ob1"})},
            ),
            "w0_s1": _mk_zero_mem_action(
                "w0_s1", "ws1", frozenset({"w0"}), {"w0": "m"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c"}),
                ru_upper=0.5, cpu_ticks=0.5, capabilities_by_label={"m": frozenset({"cw0"})},
            ),
            "w0_s2": _mk_zero_mem_action(
                "w0_s2", "ws2", frozenset({"w0"}), {"w0": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"cw0"}),
                ru_upper=0.0, cpu_ticks=0.5, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
            "w1_tail": _mk_zero_mem_action(
                "w1_tail", "wt", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob1"}), required_capabilities=frozenset({"c"}),
                ru_upper=3.0, cpu_ticks=1.0, discharged_by_label={"ok": frozenset({"ob1"})},
            ),
        },
    )

    # Case 3: 3-world multi-entry frontier with partial recovery, retry, and pruning
    u3 = frozenset({"w0", "w1", "w2"})
    o3 = WorldOracle(
        specification_id="multi_3",
        model_id="m_m3",
        assurance_scope="stage2_reg",
        universe=u3,
        decision_by_world={"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT"},
        initial_obligations=frozenset({"ob"}),
        initial_retries=1,
        actions={
            "f_act": _mk_zero_mem_action(
                "f_act", "op", u3, {"w0": "ok", "w1": "retry", "w2": "to"},
                required_obligations=frozenset({"ob"}), ru_upper=1.0, cpu_ticks=2.0,
                outcome_kind_by_label={
                    "ok": OutcomeKind.SUCCESS,
                    "retry": OutcomeKind.BOUNDED_RETRY,
                    "to": OutcomeKind.TIMEOUT,
                },
                discharged_by_label={"ok": frozenset({"ob"}), "retry": frozenset(), "to": frozenset()},
                capabilities_by_label={"ok": frozenset({"p"}), "retry": frozenset({"p"}), "to": frozenset({"p"})},
                retry_cost_by_label={"ok": 0, "retry": 1, "to": 0},
            ),
            "c_act": _mk_zero_mem_action(
                "c_act", "op", u3, {"w0": "to", "w1": "to", "w2": "to"},
                required_obligations=frozenset({"ob"}), ru_upper=2.0, cpu_ticks=3.0,
                outcome_kind_by_label={"to": OutcomeKind.TIMEOUT},
                capabilities_by_label={"to": frozenset({"p"})},
            ),
            "rec_w1": _mk_zero_mem_action(
                "rec_w1", "rw1", frozenset({"w1"}), {"w1": "ok"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"p"}),
                ru_upper=0.5, cpu_ticks=1.0, discharged_by_label={"ok": frozenset({"ob"})},
            ),
            "rec_w2": _mk_zero_mem_action(
                "rec_w2", "rw2", frozenset({"w2"}), {"w2": "ok"},
                required_obligations=frozenset({"ob"}), required_capabilities=frozenset({"p"}),
                ru_upper=1.0, cpu_ticks=0.5, discharged_by_label={"ok": frozenset({"ob"})},
            ),
        },
    )

    budget = ResourceBudget(20.0, 20.0, 20.0, 10.0)
    for oracle, horizon in ((o1, 3), (o2, 4), (o3, 3)):
        res_p, res_u = assert_frontiers_match(oracle, budget, max_horizon=horizon)
        ref = _explicit_reference_frontier(oracle, budget, horizon)
        assert res_p.pareto_frontier == res_u.pareto_frontier == ref
        assert len(res_p.pareto_frontier) > 1

