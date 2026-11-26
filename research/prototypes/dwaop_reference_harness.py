"""Offline finite-state reference harness for the DWAOP research proposal.

This is deliberately separate from the GDEC runtime. It is a small,
transparent oracle/test harness for action-sequence completeness, admissible
blocker-distance pruning, contingent branch aggregation, and live-set memory
accounting. It is not an engineering solver or a trusted certificate checker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple
import unittest


@dataclass(frozen=True)
class ResourceBudget:
    ru: float
    peak_memory_gb: float


@dataclass(frozen=True)
class Action:
    action_id: str
    ru_upper: float
    ru_lower: float
    during_peak_gb: float
    outcomes: Tuple[Tuple[str, str], ...]
    may_resolve: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class State:
    state_id: str
    blockers: FrozenSet[str]
    resident_memory_gb: float
    actions: Tuple[str, ...] = ()
    terminal: Optional[str] = None


@dataclass
class Plan:
    state_id: str
    terminal: Optional[str] = None
    action_id: Optional[str] = None
    branches: Dict[str, "Plan"] = field(default_factory=dict)
    ru_upper: float = 0.0
    peak_memory_gb: float = 0.0


@dataclass(frozen=True)
class Fixture:
    states: Mapping[str, State]
    actions: Mapping[str, Action]
    effect_map_complete: bool = True


def validate_fixture(fixture: Fixture) -> None:
    """Reject malformed finite models before the planner or checker uses them."""
    for state_id, state in fixture.states.items():
        if state.state_id != state_id:
            raise ValueError(f"State key/id mismatch: {state_id}")
        if state.resident_memory_gb < 0:
            raise ValueError(f"Negative resident-memory bound in {state_id}")
        if state.terminal in {"ACCEPT", "REJECT"} and state.actions:
            raise ValueError(f"Terminal state {state_id} cannot expose actions")
        for action_id in state.actions:
            if action_id not in fixture.actions:
                raise ValueError(f"Unknown action {action_id} from state {state_id}")
            action = fixture.actions[action_id]
            for _, child_state_id in action.outcomes:
                if child_state_id in fixture.states:
                    removed = state.blockers - fixture.states[child_state_id].blockers
                    if fixture.effect_map_complete and not removed.issubset(action.may_resolve):
                        raise ValueError(
                            f"Action {action_id} removes blockers absent from its effect map: "
                            f"{sorted(removed - action.may_resolve)}"
                        )
    for action_id, action in fixture.actions.items():
        if action.action_id != action_id:
            raise ValueError(f"Action key/id mismatch: {action_id}")
        if action.ru_lower < 0 or action.ru_upper < 0 or action.ru_lower > action.ru_upper:
            raise ValueError(f"Invalid RU lower/upper bounds for {action_id}")
        if action.during_peak_gb < 0 or not action.outcomes:
            raise ValueError(f"Invalid resource/outcome contract for {action_id}")
        labels = [label for label, _ in action.outcomes]
        if len(labels) != len(set(labels)) or any(not label for label in labels):
            raise ValueError(f"Outcome labels must be non-empty and unique for {action_id}")
        for _, child_state_id in action.outcomes:
            if child_state_id not in fixture.states:
                raise ValueError(f"Unknown child state {child_state_id} in {action_id}")


def blocker_distance_lower_bound(state: State, actions: Mapping[str, Action],
                                 effect_map_complete: bool) -> Optional[float]:
    """Admissible weak LB: max over blockers of cheapest possible resolver.

    The resolver library is intentionally an over-approximation of currently
    eligible actions; prerequisites are ignored. If completeness of the effect
    map is not established, return None and disable pruning.
    """
    if not effect_map_complete:
        return None
    if not state.blockers:
        return 0.0
    per_blocker = []
    for blocker in state.blockers:
        candidates = [a.ru_lower for a in actions.values()
                      if blocker in a.may_resolve]
        if not candidates:
            return inf
        per_blocker.append(min(candidates))
    return max(per_blocker)


def find_plan(fixture: Fixture, state_id: str, budget: ResourceBudget,
              remaining_ru: Optional[float] = None,
              peak_so_far_gb: float = 0.0,
              use_pruning: bool = True,
              stack: FrozenSet[str] = frozenset(),
              depth_left: int = 12) -> Optional[Plan]:
    """Find one complete contingent plan within the declared resources.

    RU is additive along each realised path. Peak memory is a high-water mark
    over resident objects and each action's declared during-peak. Every action
    outcome must have a complete child plan (AND branch semantics).
    """
    validate_fixture(fixture)
    if remaining_ru is None:
        remaining_ru = budget.ru
    state = fixture.states[state_id]
    current_peak = max(peak_so_far_gb, state.resident_memory_gb)

    if state.terminal in {"ACCEPT", "REJECT"}:
        if current_peak <= budget.peak_memory_gb:
            return Plan(state_id=state_id, terminal=state.terminal,
                        ru_upper=0.0, peak_memory_gb=current_peak)
        return None

    if depth_left <= 0 or state_id in stack:
        return None

    if use_pruning:
        lower_bound = blocker_distance_lower_bound(
            state, fixture.actions, fixture.effect_map_complete
        )
        if lower_bound is not None and lower_bound > remaining_ru + 1e-12:
            return None

    next_stack = stack | {state_id}
    for action_id in state.actions:
        action = fixture.actions[action_id]
        next_peak = max(current_peak, action.during_peak_gb)
        if next_peak > budget.peak_memory_gb + 1e-12:
            continue
        if action.ru_upper > remaining_ru + 1e-12:
            continue

        child_plans: Dict[str, Plan] = {}
        all_outcomes_complete = True
        child_ru_worst = 0.0
        child_peak_worst = next_peak
        for outcome, child_state_id in action.outcomes:
            child = find_plan(
                fixture, child_state_id, budget,
                remaining_ru=remaining_ru - action.ru_upper,
                peak_so_far_gb=next_peak,
                use_pruning=use_pruning,
                stack=next_stack,
                depth_left=depth_left - 1,
            )
            if child is None:
                all_outcomes_complete = False
                break
            child_plans[outcome] = child
            child_ru_worst = max(child_ru_worst, child.ru_upper)
            child_peak_worst = max(child_peak_worst, child.peak_memory_gb)

        if all_outcomes_complete and len(child_plans) == len(action.outcomes):
            return Plan(
                state_id=state_id,
                action_id=action_id,
                branches=child_plans,
                ru_upper=action.ru_upper + child_ru_worst,
                peak_memory_gb=max(next_peak, child_peak_worst),
            )
    return None


def exact_unpruned_min_ru(fixture: Fixture, state_id: str,
                          stack: FrozenSet[str] = frozenset(),
                          depth_left: int = 12) -> float:
    """Exhaustive dynamic-programming oracle for the finite acyclic fixture."""
    validate_fixture(fixture)
    state = fixture.states[state_id]
    if state.terminal in {"ACCEPT", "REJECT"}:
        return 0.0
    if depth_left <= 0 or state_id in stack:
        return inf
    next_stack = stack | {state_id}
    candidates = []
    for action_id in state.actions:
        action = fixture.actions[action_id]
        child_costs = [exact_unpruned_min_ru(
            fixture, child, next_stack, depth_left - 1
        ) for _, child in action.outcomes]
        if child_costs and all(cost < inf for cost in child_costs):
            candidates.append(action.ru_upper + max(child_costs))
    return min(candidates, default=inf)


def verify_plan_tree(fixture: Fixture, plan: Plan, budget: ResourceBudget,
                     used_ru: float = 0.0, peak_so_far_gb: float = 0.0) -> bool:
    """Recompute tree completeness, branch costs and live-set peak bounds."""
    validate_fixture(fixture)

    def visit(node: Plan, path_ru: float, path_peak: float) -> Optional[Tuple[float, float]]:
        state = fixture.states.get(node.state_id)
        if state is None:
            return None
        current_peak = max(path_peak, state.resident_memory_gb)
        if state.terminal in {"ACCEPT", "REJECT"}:
            if (node.terminal != state.terminal or node.action_id is not None
                    or node.branches or path_ru > budget.ru + 1e-12
                    or current_peak > budget.peak_memory_gb + 1e-12):
                return None
            if abs(node.ru_upper) > 1e-12 or abs(node.peak_memory_gb - current_peak) > 1e-12:
                return None
            return 0.0, current_peak

        if node.terminal is not None or node.action_id not in state.actions:
            return None
        action = fixture.actions[node.action_id]
        expected = {outcome: child for outcome, child in action.outcomes}
        if len(expected) != len(action.outcomes) or set(node.branches) != set(expected):
            return None

        next_ru = path_ru + action.ru_upper
        next_peak = max(current_peak, action.during_peak_gb)
        if next_ru > budget.ru + 1e-12 or next_peak > budget.peak_memory_gb + 1e-12:
            return None

        child_ru_worst = 0.0
        child_peak_worst = next_peak
        for outcome, expected_child_id in expected.items():
            child_node = node.branches[outcome]
            if child_node.state_id != expected_child_id:
                return None
            metrics = visit(child_node, next_ru, next_peak)
            if metrics is None:
                return None
            child_ru_worst = max(child_ru_worst, metrics[0])
            child_peak_worst = max(child_peak_worst, metrics[1])

        computed_ru = action.ru_upper + child_ru_worst
        computed_peak = max(next_peak, child_peak_worst)
        if (abs(node.ru_upper - computed_ru) > 1e-12
                or abs(node.peak_memory_gb - computed_peak) > 1e-12
                or path_ru + computed_ru > budget.ru + 1e-12):
            return None
        return computed_ru, computed_peak

    return visit(plan, used_ru, peak_so_far_gb) is not None


def sequential_live_memory_peak(initial_resident_gb: float,
                                actions: Sequence[Tuple[float, float, float]]) -> float:
    """Calculate path peak for (workspace, overlap, retained_output) triples."""
    resident = initial_resident_gb
    peak = resident
    for workspace, overlap, retained_output in actions:
        during = resident + workspace + overlap
        peak = max(peak, during)
        resident += retained_output
        peak = max(peak, resident)
    return peak


def contingent_additive_cost(root_cost: float, child_costs: Sequence[float]) -> float:
    """Mutually exclusive branches: root cost plus worst child path, not sum."""
    if not child_costs:
        raise ValueError("A non-terminal contingent action needs at least one outcome")
    return root_cost + max(child_costs)


def contingent_peak_memory(root_peak: float, child_peaks: Sequence[float]) -> float:
    if not child_peaks:
        raise ValueError("A non-terminal contingent action needs at least one outcome")
    return max(root_peak, max(child_peaks))


def make_fixture(effect_map_complete: bool = True) -> Fixture:
    actions = {
        "prepare": Action("prepare", 1.0, 1.0, 2.70,
                          (("prepared", "prepared"),), frozenset()),
        "certify": Action("certify", 2.0, 2.0, 2.60,
                          (("pass", "cert_pass"), ("fail", "cert_fail")),
                          frozenset({"decision_witness"})),
        "check_pass": Action("check_pass", 1.0, 1.0, 2.30,
                             (("verified", "accept"),),
                             frozenset({"independent_check"})),
        "check_fail": Action("check_fail", 1.0, 1.0, 2.30,
                             (("verified", "reject"),),
                             frozenset({"independent_check"})),
    }
    states = {
        "root": State("root", frozenset({"decision_witness", "independent_check"}),
                       0.50, ("prepare",)),
        "prepared": State("prepared", frozenset({"decision_witness", "independent_check"}),
                           0.90, ("certify",)),
        "cert_pass": State("cert_pass", frozenset({"independent_check"}),
                            1.10, ("check_pass",)),
        "cert_fail": State("cert_fail", frozenset({"independent_check"}),
                            1.10, ("check_fail",)),
        "accept": State("accept", frozenset(), 1.20, terminal="ACCEPT"),
        "reject": State("reject", frozenset(), 1.20, terminal="REJECT"),
    }
    return Fixture(states, actions, effect_map_complete)


class TestDWAOPReferenceHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = make_fixture()

    def test_exhaustive_optimum_and_complete_branch_tree(self) -> None:
        self.assertAlmostEqual(exact_unpruned_min_ru(self.fixture, "root"), 4.0)
        plan = find_plan(self.fixture, "root", ResourceBudget(4.0, 3.0))
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertAlmostEqual(plan.ru_upper, 4.0)
        self.assertAlmostEqual(plan.peak_memory_gb, 2.70)
        self.assertEqual(set(plan.branches), {"prepared"})
        cert = plan.branches["prepared"]
        self.assertEqual(set(cert.branches), {"pass", "fail"})
        self.assertEqual(cert.branches["pass"].branches["verified"].terminal, "ACCEPT")
        self.assertEqual(cert.branches["fail"].branches["verified"].terminal, "REJECT")
        self.assertTrue(verify_plan_tree(self.fixture, plan, ResourceBudget(4.0, 3.0)))

    def test_pruned_and_unpruned_feasibility_match_budget_sweep(self) -> None:
        for ru_budget in [i / 4 for i in range(0, 25)]:
            budget = ResourceBudget(ru_budget, 3.0)
            plain = find_plan(self.fixture, "root", budget, use_pruning=False)
            pruned = find_plan(self.fixture, "root", budget, use_pruning=True)
            self.assertEqual(plain is not None, pruned is not None, ru_budget)
            if pruned is not None:
                self.assertTrue(verify_plan_tree(self.fixture, pruned, budget))

    def test_blocker_lower_bound_never_exceeds_exact_remaining_cost(self) -> None:
        for state_id in self.fixture.states:
            state = self.fixture.states[state_id]
            if state.terminal:
                continue
            lb = blocker_distance_lower_bound(state, self.fixture.actions, True)
            optimum = exact_unpruned_min_ru(self.fixture, state_id)
            self.assertIsNotNone(lb)
            self.assertLessEqual(float(lb), optimum + 1e-12, state_id)

    def test_incomplete_effect_map_disables_pruning(self) -> None:
        complete_fixture = make_fixture()
        incomplete_actions = dict(complete_fixture.actions)
        cert = incomplete_actions["certify"]
        incomplete_actions["certify"] = Action(
            cert.action_id, cert.ru_upper, cert.ru_lower, cert.during_peak_gb,
            cert.outcomes, frozenset(),
        )
        incomplete = Fixture(complete_fixture.states, incomplete_actions, False)
        state = incomplete.states["prepared"]
        self.assertIsNone(blocker_distance_lower_bound(
            state, incomplete.actions, incomplete.effect_map_complete
        ))
        budget = ResourceBudget(4.0, 3.0)
        no_prune = find_plan(incomplete, "root", budget, use_pruning=False)
        disabled_prune = find_plan(incomplete, "root", budget, use_pruning=True)
        self.assertIsNotNone(no_prune)
        self.assertIsNotNone(disabled_prune)

    def test_effect_map_that_omits_an_observed_blocker_removal_is_rejected(self) -> None:
        complete_fixture = make_fixture()
        actions = dict(complete_fixture.actions)
        cert = actions["certify"]
        actions["certify"] = Action(
            cert.action_id, cert.ru_upper, cert.ru_lower, cert.during_peak_gb,
            cert.outcomes, frozenset(),
        )
        malformed = Fixture(complete_fixture.states, actions, True)
        with self.assertRaises(ValueError):
            find_plan(malformed, "root", ResourceBudget(4.0, 3.0))

    def test_malformed_outcome_contract_is_rejected(self) -> None:
        broken = make_fixture()
        bad_actions = dict(broken.actions)
        bad_actions["certify"] = Action(
            "certify", 2.0, 2.0, 2.60,
            (("pass", "cert_pass"), ("pass", "cert_fail")),
            frozenset({"decision_witness"}),
        )
        malformed = Fixture(broken.states, bad_actions)
        with self.assertRaises(ValueError):
            find_plan(malformed, "root", ResourceBudget(4.0, 3.0))

    def test_pruned_search_does_not_accept_incomplete_outcome_tree(self) -> None:
        plan = find_plan(self.fixture, "root", ResourceBudget(4.0, 3.0))
        self.assertIsNotNone(plan)
        assert plan is not None
        cert = plan.branches["prepared"]
        del cert.branches["fail"]
        self.assertFalse(verify_plan_tree(self.fixture, plan, ResourceBudget(4.0, 3.0)))

    def test_sequential_memory_is_live_set_high_water_not_sum(self) -> None:
        peak = sequential_live_memory_peak(
            0.50,
            [(2.00, 0.20, 0.40), (1.50, 0.30, 0.20), (3.00, 0.10, 0.10)],
        )
        self.assertAlmostEqual(peak, 4.20)
        self.assertNotAlmostEqual(peak, 6.50)

    def test_mutually_exclusive_branch_costs_use_max_not_sum(self) -> None:
        self.assertAlmostEqual(contingent_additive_cost(2.0, [2.0, 5.0]), 7.0)
        self.assertAlmostEqual(contingent_peak_memory(3.0, [4.0, 2.0]), 4.0)

    def test_blocker_distance_is_admissible_for_exhaustive_small_set_covers(self) -> None:
        blockers = ("b1", "b2", "b3")
        action_costs = (1.0, 1.5, 2.0, 2.5)
        covers = (
            frozenset({"b1", "b2"}),
            frozenset({"b2", "b3"}),
            frozenset({"b1"}),
            frozenset({"b3"}),
        )
        feasible_totals = []
        for mask in range(1, 1 << len(action_costs)):
            selected = [i for i in range(len(action_costs)) if mask & (1 << i)]
            covered = frozenset().union(*(covers[i] for i in selected))
            if set(blockers).issubset(covered):
                feasible_totals.append(sum(action_costs[i] for i in selected))
        exact_cover_cost = min(feasible_totals)
        lower_bound = max(
            min(action_costs[i] for i, cover in enumerate(covers) if blocker in cover)
            for blocker in blockers
        )
        self.assertLessEqual(lower_bound, exact_cover_cost + 1e-12)

    def test_blocker_lower_bound_admissibility_over_all_small_cover_families(self) -> None:
        blockers = ("b1", "b2", "b3")
        nonempty_covers = [frozenset({blockers[i] for i in range(3) if mask & (1 << i)})
                           for mask in range(1, 1 << 3)]
        costs = (1.0, 1.5, 2.0, 2.5)
        total_families = 0

        def visit_family(index: int, selected_covers: list[FrozenSet[str]]) -> None:
            nonlocal total_families
            if index < len(costs):
                for cover in nonempty_covers:
                    visit_family(index + 1, selected_covers + [cover])
                return
            total_families += 1
            exact = inf
            for mask in range(1, 1 << len(costs)):
                selected = [i for i in range(len(costs)) if mask & (1 << i)]
                covered = frozenset().union(*(selected_covers[i] for i in selected))
                if set(blockers).issubset(covered):
                    exact = min(exact, sum(costs[i] for i in selected))
            if exact < inf:
                lb = max(min(costs[i] for i, cover in enumerate(selected_covers)
                             if blocker in cover) for blocker in blockers)
                self.assertLessEqual(lb, exact + 1e-12, selected_covers)

        visit_family(0, [])
        self.assertEqual(total_families, 2401)

    def test_resource_limits_reject_peak_overrun_even_when_ru_fits(self) -> None:
        self.assertIsNone(find_plan(self.fixture, "root", ResourceBudget(4.0, 2.5)))
        self.assertIsNotNone(find_plan(self.fixture, "root", ResourceBudget(4.0, 2.7)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
