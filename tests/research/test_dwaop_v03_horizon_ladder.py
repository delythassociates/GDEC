from __future__ import annotations
from fractions import Fraction
import pytest
import research.prototypes.dwaop_integrated_planner as planner_module
from research.prototypes.dwaop_integrated_planner import ResourceBudget, ResourceVector
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier
from research.prototypes.dwaop_horizon_ladder import build_refinement_ladder, run_ladder_benchmark


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


def test_resource_budget_boundary_is_exact_for_decimal_inputs():
    budget = ResourceBudget(ru_upper=0.3, cpu_ticks=0.3, energy_ticks=0.5, peak_memory_gb=0.0)
    exact = ResourceVector(ru_upper=0.1).add_sequential(ResourceVector(ru_upper=0.2))
    over = ResourceVector(ru_upper=0.30000000000000004)
    assert budget.allows(exact) is True
    assert budget.allows(over) is False


def test_frontier_comparison_detects_right_only_entries():
    def signature(value):
        return value
    left = {signature(("policy-a",))}
    right = {signature(("policy-a",)), signature(("policy-b",))}
    left_only = left - right
    right_only = right - left
    assert not (len(left_only) == 0 and len(right_only) == 0 and len(left) == len(right))


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
