"""Mutation testing suite (14 targeted mutants) for DWAOP v0.2."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TESTS_RESEARCH_DIR = Path(__file__).resolve().parent
if str(TESTS_RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_RESEARCH_DIR))

import research.prototypes.dwaop_integrated_planner as planner_mod
from research.prototypes.dwaop_exhaustive_policy_oracle import (
    enumerate_exact_pareto_frontier,
)
from research.prototypes.dwaop_integrated_planner import (
    ContractError,
    OutcomeKind,
    ResourceBudget,
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
from test_dwaop_integrated_pruning import make_action


def _fixture_oracle() -> tuple[WorldOracle, ResourceBudget]:
    universe = frozenset({"w0", "w1", "w2"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT"}
    fine = make_action(
        "fine_act",
        "op_main",
        universe,
        {"w0": "ok_0", "w1": "fail_1", "w2": "ok_2"},
        required_obligations=frozenset({"ob1"}),
        ru_upper=1.0,
        cpu_ticks=10.0,
        energy_ticks=5.0,
        workspace_gb_upper=1.0,
        overlap_gb_upper=0.2,
        outcome_kind_by_label={
            "ok_0": OutcomeKind.SUCCESS,
            "fail_1": OutcomeKind.NUMERICAL_BREAKDOWN,
            "ok_2": OutcomeKind.SUCCESS,
        },
        discharged_by_label={
            "ok_0": frozenset({"ob1"}),
            "fail_1": frozenset(),
            "ok_2": frozenset({"ob1"}),
        },
        retained_output_gb_by_label={"ok_0": 0.5, "fail_1": 0.1, "ok_2": 0.5},
    )
    coarse = make_action(
        "coarse_act",
        "op_main",
        universe,
        {"w0": "c0", "w1": "c1", "w2": "c0"},
        required_obligations=frozenset({"ob1"}),
        ru_upper=2.0,
        cpu_ticks=20.0,
        energy_ticks=10.0,
        workspace_gb_upper=1.5,
        overlap_gb_upper=0.3,
        outcome_kind_by_label={
            "c0": OutcomeKind.SUCCESS,
            "c1": OutcomeKind.NUMERICAL_BREAKDOWN,
        },
        discharged_by_label={"c0": frozenset({"ob1"}), "c1": frozenset()},
    )
    oracle = WorldOracle(
        specification_id="spec_mut",
        model_id="m_mut",
        assurance_scope="mut_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"fine_act": fine, "coarse_act": coarse},
        initial_obligations=frozenset({"ob1"}),
        initial_retries=1,
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    return oracle, budget


def test_mutant_01_remove_one_outcome() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    mutated = replace(contract, outcomes=contract.outcomes[:-1])
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_02_merge_incompatible_outcome_cells() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    merged = replace(c0, worlds=c0.worlds | c1.worlds)
    mutated = replace(contract, outcomes=(merged, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_03_change_successor_world_set() -> None:
    oracle, budget = _fixture_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["fine_act"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["coarse_act"], oracle)[0].state

    mutated_child = replace(fine_children[0], worlds=frozenset({"w0", "w2"}))
    assert not verify_state_provenance(mutated_child, contracts, oracle)
    assert not is_complete_refinement_cover(
        [mutated_child] + fine_children[1:], coarse_child, contracts, oracle, budget
    )


def test_mutant_04_alter_certificate_scope() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    bad_cert = replace(c0.certificate, assurance_scope="forged_scope")
    mutated = replace(contract, outcomes=(replace(c0, certificate=bad_cert), c1, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_05_forge_proof_identifier() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    bad_cert = replace(c0.certificate, proof_id="forged_proof_999")
    mutated = replace(contract, outcomes=(replace(c0, certificate=bad_cert), c1, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


@pytest.mark.parametrize("field_name", ["ru_upper", "cpu_ticks", "energy_ticks"])
def test_mutant_06_understate_additive_cost(field_name: str) -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    mutated = replace(contract, **{field_name: getattr(contract, field_name) - 0.5})
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_07_understate_retained_or_peak_memory() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    c0, c1, c2 = contract.outcomes
    # c1 is "ok_0" with retained_output_gb_upper=0.5; understate to 0.1
    under_retained = replace(c1, retained_output_gb_upper=0.1)
    mutated_retained = replace(contract, outcomes=(c0, under_retained, c2))
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated_retained)

    under_workspace = replace(contract, workspace_gb_upper=0.1)
    with pytest.raises(ContractError):
        verify_action_contract(oracle, under_workspace)


def test_mutant_08_omit_failure_branch() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    # Remove the NUMERICAL_BREAKDOWN cell
    no_fail = tuple(c for c in contract.outcomes if c.kind != OutcomeKind.NUMERICAL_BREAKDOWN)
    mutated = replace(contract, outcomes=no_fail)
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_09_bypass_model_invalidation(monkeypatch: pytest.MonkeyPatch) -> None:
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
    )
    oracle = WorldOracle(
        specification_id="spec_m9",
        model_id="m_m9",
        assurance_scope="m9_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"inv_act": inv},
        initial_obligations=frozenset({"ob"}),
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)

    # Independent oracle returns REFUSE
    p_oracle = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=3)
    assert dict(p_oracle[0].world_verdict_map) == {"w0": "REFUSE", "w1": "REFUSE"}

    # Mutate terminal_verdict to ignore model_valid and return ACCEPT/REJECT
    def mutated_terminal_verdict(state, orc):
        if not state.worlds:
            return None
        decisions_set = {orc.decision_by_world[w] for w in state.worlds}
        return next(iter(decisions_set)) if len(decisions_set) == 1 else None

    monkeypatch.setattr(planner_mod, "terminal_verdict", mutated_terminal_verdict)
    res_mutated = plan_policies(oracle, budget, max_horizon=3, prune=True)
    # Mutant is killed by frontier divergence against the independent oracle
    assert res_mutated.pareto_frontier != p_oracle


def test_mutant_10_reverse_containment_comparison(monkeypatch: pytest.MonkeyPatch) -> None:
    universe = frozenset({"w0", "w1", "w2"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT", "w2": "ACCEPT"}
    a_fine = make_action("a_fine", "op", universe, {"w0": "l0", "w1": "l1", "w2": "l2"}, ru_upper=1.0)
    a_coarse = make_action("a_coarse", "op", universe, {"w0": "c0", "w1": "c0", "w2": "c1"}, ru_upper=2.0)
    oracle = WorldOracle(
        specification_id="spec_m10",
        model_id="m_m10",
        assurance_scope="m10_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"a_fine": a_fine, "a_coarse": a_coarse},
    )
    budget = ResourceBudget(ru_upper=10.0, cpu_ticks=100.0, energy_ticks=50.0, peak_memory_gb=8.0)
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    fine_children = [t.state for t in apply_action_outcome(root, contracts["a_fine"], oracle)]
    coarse_child = apply_action_outcome(root, contracts["a_coarse"], oracle)[0].state

    # Normally coarse_child does NOT refine fine_children[0] (|coarse_child.worlds|=2 > |fine_children[0].worlds|=1)
    assert not is_local_refinement(coarse_child, fine_children[0], contracts, oracle)

    # Reversing containment in a mutated refinement check would falsely claim coarse <= fine,
    # which is killed by verify_action_contract / world-cover check or exact oracle comparison.
    orig_local = planner_mod.is_local_refinement

    def reversed_local(fine_s, coarse_s, ctrs, orc, depth_left=10):
        return orig_local(coarse_s, fine_s, ctrs, orc, depth_left)

    monkeypatch.setattr(planner_mod, "is_local_refinement", reversed_local)
    # Under reversed containment, fine_children[0] <= coarse_child fails because coarse <= fine is False
    assert not is_complete_refinement_cover(fine_children, coarse_child, contracts, oracle, budget)


def test_mutant_11_remove_one_obligation_precondition() -> None:
    oracle, _ = _fixture_oracle()
    contract = build_action_contract(oracle, "fine_act")
    mutated = replace(contract, required_obligations=frozenset())
    with pytest.raises(ContractError):
        verify_action_contract(oracle, mutated)


def test_mutant_12_permit_action_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    oracle, budget = _fixture_oracle()
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = make_initial_state(oracle)
    t_fine = apply_action_outcome(root, contracts["fine_act"], oracle)[0].state
    # Normally fine_act is removed from remaining_actions after use
    assert "fine_act" not in t_fine.remaining_actions

    # Mutate child state to retain fine_act in remaining_actions -> provenance check kills it
    reused_state = replace(t_fine, remaining_actions=t_fine.remaining_actions | {"fine_act"})
    assert not verify_state_provenance(reused_state, contracts, oracle)


def test_mutant_13_corrupt_retry_limits() -> None:
    universe = frozenset({"w0", "w1"})
    decisions = {"w0": "ACCEPT", "w1": "REJECT"}
    retry_act = make_action(
        "retry_act",
        "retry_op",
        universe,
        {"w0": "try", "w1": "try"},
        outcome_kind_by_label={"try": OutcomeKind.BOUNDED_RETRY},
        retry_cost_by_label={"try": 0},  # Invalid: BOUNDED_RETRY must have retry_cost >= 1
    )
    bad_oracle = WorldOracle(
        specification_id="spec_m13",
        model_id="m_m13",
        assurance_scope="m13_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={"retry_act": retry_act},
        initial_retries=1,
    )
    with pytest.raises(ContractError):
        validate_oracle(bad_oracle)

    neg_retry_oracle = WorldOracle(
        specification_id="spec_m13b",
        model_id="m_m13b",
        assurance_scope="m13_scope",
        universe=universe,
        decision_by_world=decisions,
        actions={},
        initial_retries=-1,
    )
    with pytest.raises(ContractError):
        validate_oracle(neg_retry_oracle)


def test_mutant_14_allow_clairvoyant_world_branching() -> None:
    oracle, _ = _fixture_oracle()
    clairvoyant = replace(oracle, allow_clairvoyant_world_branching=True)
    with pytest.raises(ContractError):
        validate_oracle(clairvoyant)
