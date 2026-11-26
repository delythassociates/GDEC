"""Adversarial graph tests (Strategies A, B, and C) for DWAOP v0.2."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
import math
from pathlib import Path
import sys

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
    OutcomeCell,
    OutcomeCertificate,
    OutcomeKind,
    ResourceBudget,
    ResourceVector,
    WorldOracle,
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
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier
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
