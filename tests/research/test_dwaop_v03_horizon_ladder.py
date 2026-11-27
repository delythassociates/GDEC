from __future__ import annotations
from fractions import Fraction
import pytest
import research.prototypes.dwaop_integrated_planner as planner_module
from research.prototypes.dwaop_integrated_planner import (
    ResourceBudget,
    ResourceVector,
    build_action_contract,
    verify_action_contract,
)
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier
from research.prototypes.dwaop_horizon_ladder import (
    _frontier_comparisons_are_equal,
    build_refinement_ladder,
    run_ladder_benchmark,
)


def test_hard_resource_budget_uses_exact_not_epsilon_slack():
    budget = ResourceBudget(ru_upper=1.0, cpu_ticks=1.0, energy_ticks=1.0, peak_memory_gb=1.0)
    over = ResourceVector(ru_upper=1.0 + 5e-13, cpu_ticks=0.0, energy_ticks=0.0, peak_memory_gb=0.0)
    assert budget.allows(over) is False


def test_resource_proof_identity_does_not_round():
    left = ResourceVector(ru_upper=1.0000000000001, cpu_ticks=0.0, energy_ticks=0.0, peak_memory_gb=0.0)
    right = ResourceVector(ru_upper=1.0000000000002, cpu_ticks=0.0, energy_ticks=0.0, peak_memory_gb=0.0)
    assert left.exact_key() != right.exact_key()

def test_decimal_resource_accumulation_uses_exact_rational_values():
    left = ResourceVector(ru_upper=0.1, cpu_ticks=0.2, energy_ticks=0.3, peak_memory_gb=0.0)
    right = ResourceVector(ru_upper=0.2, cpu_ticks=0.1, energy_ticks=0.2, peak_memory_gb=0.0)
    total = left.add_sequential(right)
    assert total.ru_upper == Fraction(3, 10)
    assert total.cpu_ticks == Fraction(3, 10)
    assert total.energy_ticks == Fraction(1, 2)
    assert isinstance(total.ru_upper, Fraction)

def test_decimal_action_costs_verify_after_exact_boundary_conversion():
    oracle, _ = build_refinement_ladder(3)
    for action_id in oracle.actions:
        contract = build_action_contract(oracle, action_id)
        verify_action_contract(oracle, contract)


def test_resource_budget_boundary_is_exact_for_decimal_inputs():
    budget = ResourceBudget(ru_upper=0.3, cpu_ticks=0.3, energy_ticks=0.5, peak_memory_gb=0.0)
    exact = ResourceVector(ru_upper=0.1).add_sequential(ResourceVector(ru_upper=0.2))
    over = ResourceVector(ru_upper=0.30000000000000004)
    assert budget.allows(exact) is True
    assert budget.allows(over) is False

def test_strict_dominance_does_not_round_tiny_rational_differences():
    left = ResourceVector(ru_upper=Fraction(1, 10**400))
    right = ResourceVector(ru_upper=Fraction(2, 10**400))
    assert left.strictly_dominates(right) is True


def test_frontier_comparison_rejects_right_only_entries():
    comparison = {
        "left_size": 1,
        "right_size": 2,
        "left_only_count": 0,
        "right_only_count": 1,
    }
    assert _frontier_comparisons_are_equal(comparison) is False


def test_frontier_comparison_accepts_exact_symmetric_match():
    comparison = {
        "left_size": 2,
        "right_size": 2,
        "left_only_count": 0,
        "right_only_count": 0,
    }
    assert _frontier_comparisons_are_equal(comparison) is True


@pytest.mark.parametrize("n_stages,expected_horizon", [(5, 6), (7, 8)])
def test_horizon_ladder_frontiers_match(n_stages, expected_horizon):
    result = run_ladder_benchmark(n_stages)
    assert result["horizon"] == expected_horizon
    assert result["frontiers_equal_pruned_unpruned_oracle"] is True
    assert result["pruned"]["successful_prunes"] > 0
    assert result["pruned"]["states_expanded"] < result["unpruned"]["states_expanded"]


def test_exhaustive_oracle_does_not_call_planner_pareto_reducer(monkeypatch):
    oracle, budget = build_refinement_ladder(3)
    def forbidden(_):
        raise AssertionError("oracle called planner pareto reducer")
    monkeypatch.setattr(planner_module, "pareto_reduce", forbidden)
    frontier = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=4)
    assert frontier


def test_adversarial_exact_arithmetic_budget_ties_and_horizon_cutoffs():
    from research.prototypes.dwaop_integrated_planner import (
        ContractError,
        NormalizedPolicy,
        pareto_reduce,
        plan_policies,
    )

    # 1. Repeated fractional accumulation & mixed int/Fraction/float
    acc = ResourceVector()
    for _ in range(10):
        acc = acc.add_sequential(ResourceVector(ru_upper=0.1, cpu_ticks=1, energy_ticks=Fraction(1, 3)))
    assert acc.ru_upper == Fraction(1, 1)
    assert acc.cpu_ticks == Fraction(10, 1)
    assert acc.energy_ticks == Fraction(10, 3)

    # 2. Exact budget equality vs 1e-50 rational excess
    budget = ResourceBudget(ru_upper=1, cpu_ticks=10.0, energy_ticks=Fraction(10, 3), peak_memory_gb=0.0)
    assert budget.allows(acc) is True
    over = ResourceVector(ru_upper=Fraction(1, 1) + Fraction(1, 10**50))
    assert budget.allows(over) is False

    # 3. Invalid inputs rejected by ContractError
    for bad in (-0.1, float("nan"), float("inf"), True):
        with pytest.raises(ContractError):
            ResourceVector(ru_upper=bad)

    # 4. Pareto ties deduplicated to minimum max_actions_on_path
    p_long = NormalizedPolicy(
        world_verdict_map=(("w0", "ACCEPT"),),
        resource_vector=ResourceVector(ru_upper=0.5),
        terminal_verdicts=frozenset({"ACCEPT"}),
        max_actions_on_path=4,
    )
    p_short = NormalizedPolicy(
        world_verdict_map=(("w0", "ACCEPT"),),
        resource_vector=ResourceVector(ru_upper=0.5),
        terminal_verdicts=frozenset({"ACCEPT"}),
        max_actions_on_path=2,
    )
    reduced = pareto_reduce([p_long, p_short])
    assert len(reduced) == 1
    assert reduced[0].max_actions_on_path == 2

    # 5. Empty frontier (impossible budget) & horizon-dependent cutoff on 2-stage ladder
    oracle, full_budget = build_refinement_ladder(2)
    zero_budget = ResourceBudget(ru_upper=0.0, cpu_ticks=0.0, energy_ticks=0.0, peak_memory_gb=0.0)
    assert plan_policies(oracle, zero_budget, max_horizon=3, prune=True).pareto_frontier == ()
    assert enumerate_exact_pareto_frontier(oracle, zero_budget, max_horizon=3) == ()
    # Horizon 2 is insufficient for 2 stages + final_decision (requires horizon 3)
    assert plan_policies(oracle, full_budget, max_horizon=2, prune=True).pareto_frontier == ()
    assert enumerate_exact_pareto_frontier(oracle, full_budget, max_horizon=2) == ()
    # Horizon 3 succeeds and matches oracle
    pruned_h3 = plan_policies(oracle, full_budget, max_horizon=3, prune=True)
    exact_h3 = enumerate_exact_pareto_frontier(oracle, full_budget, max_horizon=3)
    assert len(exact_h3) >= 1
    assert pruned_h3.pareto_frontier == exact_h3
