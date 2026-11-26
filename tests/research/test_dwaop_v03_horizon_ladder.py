from __future__ import annotations
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
