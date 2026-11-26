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


@dataclass(frozen=True)
class DominanceAction:
    action_id: str
    semantic_key: str
    preconditions: FrozenSet[str]
    evidence_contract: FrozenSet[str]
    failure_semantics: FrozenSet[str]
    ru_upper: float
    during_peak_gb: float
    outcomes: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class DominanceState:
    state_id: str
    model_scope: str
    assurance_mode: str
    qoi_set: FrozenSet[str]
    open_obligations: FrozenSet[str]
    capabilities: FrozenSet[str]
    live_artifacts: FrozenSet[str]
    additive_spent_ru: float
    peak_committed_gb: float
    memory_model: str
    actions: Tuple[str, ...] = ()
    terminal: Optional[str] = None


@dataclass(frozen=True)
class DominanceGraph:
    states: Mapping[str, DominanceState]
    actions: Mapping[str, DominanceAction]


def validate_dominance_graph(graph: DominanceGraph) -> None:
    for state_id, state in graph.states.items():
        if state.state_id != state_id:
            raise ValueError(f"Dominance state key/id mismatch: {state_id}")
        if state.additive_spent_ru < 0 or state.peak_committed_gb < 0:
            raise ValueError(f"Negative resource ledger in {state_id}")
        if state.terminal is not None and state.actions:
            raise ValueError(f"Terminal dominance state {state_id} cannot expose actions")
        for action_id in state.actions:
            if action_id not in graph.actions:
                raise ValueError(f"Unknown dominance action {action_id} from {state_id}")
    for action_id, action in graph.actions.items():
        if action.action_id != action_id:
            raise ValueError(f"Dominance action key/id mismatch: {action_id}")
        if action.ru_upper < 0 or action.during_peak_gb < 0 or not action.outcomes:
            raise ValueError(f"Invalid dominance action resources/outcomes: {action_id}")
        labels = [label for label, _ in action.outcomes]
        if len(labels) != len(set(labels)) or any(not label for label in labels):
            raise ValueError(f"Duplicate/empty dominance outcome label: {action_id}")
        for _, child_id in action.outcomes:
            if child_id not in graph.states:
                raise ValueError(f"Unknown dominance child state {child_id} in {action_id}")


def _locally_dominates(left: DominanceState, right: DominanceState) -> bool:
    """Necessary state-order conditions before action simulation is checked."""
    return (
        left.model_scope == right.model_scope
        and left.assurance_mode == right.assurance_mode
        and left.memory_model == right.memory_model
        and left.qoi_set.issubset(right.qoi_set)
        and left.open_obligations.issubset(right.open_obligations)
        and right.capabilities.issubset(left.capabilities)
        and left.live_artifacts.issubset(right.live_artifacts)
        and left.additive_spent_ru <= right.additive_spent_ru + 1e-12
        and left.peak_committed_gb <= right.peak_committed_gb + 1e-12
        and left.terminal == right.terminal
    )


def _action_contract_dominates(left: DominanceAction, right: DominanceAction) -> bool:
    """Require semantic, precondition, evidence and failure compatibility."""
    return (
        left.semantic_key == right.semantic_key
        and left.preconditions == right.preconditions
        and left.evidence_contract == right.evidence_contract
        and left.failure_semantics == right.failure_semantics
        and left.ru_upper <= right.ru_upper + 1e-12
        and left.during_peak_gb <= right.during_peak_gb + 1e-12
    )


def greatest_simulation_relation(graph: DominanceGraph) -> FrozenSet[Tuple[str, str]]:
    """Compute a finite greatest simulation relation by monotone elimination.

    (left, right) means left can safely dominate right: every action offered by
    right has a semantically compatible, no-more-expensive action from left,
    and each outcome possible from the left action maps to a no-worse successor
    under the current relation.
    """
    validate_dominance_graph(graph)
    relation = {
        (left_id, right_id)
        for left_id, left in graph.states.items()
        for right_id, right in graph.states.items()
        if _locally_dominates(left, right)
    }

    changed = True
    while changed:
        changed = False
        remove = set()
        for left_id, right_id in relation:
            left_state = graph.states[left_id]
            right_state = graph.states[right_id]
            if right_state.terminal is not None:
                continue

            all_right_actions_simulated = True
            for right_action_id in right_state.actions:
                right_action = graph.actions[right_action_id]
                matching_left_action = False
                for left_action_id in left_state.actions:
                    left_action = graph.actions[left_action_id]
                    if not _action_contract_dominates(left_action, right_action):
                        continue

                    every_left_outcome_maps = True
                    for _, left_child_id in left_action.outcomes:
                        if not any((left_child_id, right_child_id) in relation
                                   for _, right_child_id in right_action.outcomes):
                            every_left_outcome_maps = False
                            break
                    if every_left_outcome_maps:
                        matching_left_action = True
                        break

                if not matching_left_action:
                    all_right_actions_simulated = False
                    break

            if not all_right_actions_simulated:
                remove.add((left_id, right_id))

        if remove:
            relation.difference_update(remove)
            changed = True

    return frozenset(relation)


def prune_dominated_frontier(graph: DominanceGraph, state_ids: Sequence[str]) -> Tuple[str, ...]:
    """Remove strictly dominated states; keep equivalent states deterministically."""
    relation = greatest_simulation_relation(graph)
    dominated = set()
    for weaker_id in state_ids:
        for stronger_id in state_ids:
            if stronger_id == weaker_id:
                continue
            if ((stronger_id, weaker_id) in relation
                    and (weaker_id, stronger_id) not in relation):
                dominated.add(weaker_id)
                break
    return tuple(state_id for state_id in state_ids if state_id not in dominated)


@dataclass(frozen=True)
class PolicySummary:
    terminal_verdicts: FrozenSet[str]
    additional_ru_upper: float
    peak_memory_gb: float


def enumerate_complete_policy_summaries(
    graph: DominanceGraph,
    state_id: str,
    stack: FrozenSet[str] = frozenset(),
    depth_left: int = 12,
) -> Tuple[PolicySummary, ...]:
    """Exhaustively enumerate complete contingent policies from one state.

    RU is additional future cost from this state. Each action's outcomes are
    AND branches: every child must have at least one complete policy. Branch
    RU is aggregated by maximum because outcomes are mutually exclusive.
    """
    validate_dominance_graph(graph)
    state = graph.states[state_id]

    if state.terminal in {"ACCEPT", "REJECT"}:
        if state.open_obligations:
            return ()
        return (PolicySummary(
            frozenset({state.terminal}), 0.0, state.peak_committed_gb
        ),)

    if state.terminal is not None or depth_left <= 0 or state_id in stack:
        return ()

    from itertools import product

    next_stack = stack | {state_id}
    summaries = []
    for action_id in state.actions:
        action = graph.actions[action_id]
        child_summary_sets = [
            enumerate_complete_policy_summaries(
                graph, child_id, next_stack, depth_left - 1
            )
            for _, child_id in action.outcomes
        ]
        if not child_summary_sets or any(not child_set for child_set in child_summary_sets):
            continue

        for selected_children in product(*child_summary_sets):
            verdicts = frozenset().union(
                *(child.terminal_verdicts for child in selected_children)
            )
            child_ru_worst = max(
                (child.additional_ru_upper for child in selected_children),
                default=0.0,
            )
            child_peak_worst = max(
                (child.peak_memory_gb for child in selected_children),
                default=state.peak_committed_gb,
            )
            summaries.append(PolicySummary(
                terminal_verdicts=verdicts,
                additional_ru_upper=action.ru_upper + child_ru_worst,
                peak_memory_gb=max(
                    state.peak_committed_gb,
                    action.during_peak_gb,
                    child_peak_worst,
                ),
            ))
    return tuple(summaries)


def candidate_policy_frontier(
    graph: DominanceGraph,
    candidate_state_ids: Sequence[str],
) -> Tuple[Tuple[str, FrozenSet[str], float, float], ...]:
    """Exhaustively compute nondominated complete policy summaries.

    Entries are (candidate state, terminal verdict set, total RU upper, peak
    memory). Candidate state ledger values are pre-existing resource use.
    """
    candidates = []
    for state_id in candidate_state_ids:
        state = graph.states[state_id]
        for summary in enumerate_complete_policy_summaries(graph, state_id):
            candidates.append((
                state_id,
                summary.terminal_verdicts,
                state.additive_spent_ru + summary.additional_ru_upper,
                max(state.peak_committed_gb, summary.peak_memory_gb),
            ))

    frontier = []
    for candidate in candidates:
        _, verdicts, ru, peak = candidate
        dominated = False
        for other in candidates:
            if other is candidate:
                continue
            _, other_verdicts, other_ru, other_peak = other
            no_worse = (
                other_verdicts.issuperset(verdicts)
                and other_ru <= ru + 1e-12
                and other_peak <= peak + 1e-12
            )
            strictly_better = (
                other_verdicts != verdicts
                or other_ru < ru - 1e-12
                or other_peak < peak - 1e-12
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return tuple(frontier)


def make_dominance_graph(fast_action_cost: float = 1.0,
                         include_fast_action: bool = True,
                         fast_fail_child: str = "good_fail") -> DominanceGraph:
    actions = {
        "fast": DominanceAction(
            "fast", "certified-qoi-reconstruction",
            frozenset({"mesh_ready", "dual_ready"}),
            frozenset({"deterministic_qoi_enclosure"}),
            frozenset({"timeout", "not_applicable"}),
            fast_action_cost, 2.4,
            (("pass", "good_pass"), ("fail", fast_fail_child)),
        ),
        "slow": DominanceAction(
            "slow", "certified-qoi-reconstruction",
            frozenset({"mesh_ready", "dual_ready"}),
            frozenset({"deterministic_qoi_enclosure"}),
            frozenset({"timeout", "not_applicable"}),
            2.0, 2.8,
            (("pass", "bad_pass"), ("fail", "bad_fail"), ("boundary", "bad_boundary")),
        ),
        "resolve_boundary": DominanceAction(
            "resolve_boundary", "resolve-boundary-interval",
            frozenset({"boundary_case"}),
            frozenset({"deterministic_qoi_enclosure"}),
            frozenset({"timeout", "not_applicable"}),
            3.0, 3.1,
            (("resolved", "bad_boundary_reject"),),
        ),
    }
    states = {
        "good_root": DominanceState(
            "good_root", "model-v1", "bounded",
            frozenset({"pass", "fail"}), frozenset({"independent_check"}),
            frozenset({"mesh_ready", "dual_ready", "independent_checker"}),
            frozenset({"mesh", "dual"}), 1.0, 2.0, "sequential-live-set-v1",
            ("fast",) if include_fast_action else (),
        ),
        "bad_root": DominanceState(
            "bad_root", "model-v1", "bounded",
            frozenset({"pass", "fail", "boundary"}),
            frozenset({"independent_check", "model_check"}),
            frozenset({"mesh_ready", "dual_ready"}),
            frozenset({"mesh", "dual", "legacy_cache"}), 2.0, 2.5,
            "sequential-live-set-v1", ("slow",),
        ),
        "good_pass": DominanceState(
            "good_pass", "model-v1", "bounded", frozenset({"pass"}), frozenset(),
            frozenset({"mesh_ready", "verified_bound"}), frozenset({"mesh", "bound"}),
            2.0, 2.4, "sequential-live-set-v1", terminal="ACCEPT",
        ),
        "good_fail": DominanceState(
            "good_fail", "model-v1", "bounded", frozenset({"fail"}), frozenset(),
            frozenset({"mesh_ready", "verified_bound"}), frozenset({"mesh", "bound"}),
            2.0, 2.4, "sequential-live-set-v1", terminal="REJECT",
        ),
        "bad_pass": DominanceState(
            "bad_pass", "model-v1", "bounded", frozenset({"pass", "near"}),
            frozenset({"extra_review"}), frozenset({"mesh_ready"}),
            frozenset({"mesh", "bound", "legacy_cache"}), 3.0, 2.8,
            "sequential-live-set-v1", terminal="ACCEPT",
        ),
        "bad_fail": DominanceState(
            "bad_fail", "model-v1", "bounded", frozenset({"fail", "near"}),
            frozenset({"extra_review"}), frozenset({"mesh_ready"}),
            frozenset({"mesh", "bound", "legacy_cache"}), 3.0, 2.8,
            "sequential-live-set-v1", terminal="REJECT",
        ),
        "bad_boundary": DominanceState(
            "bad_boundary", "model-v1", "bounded", frozenset({"pass", "fail", "boundary"}),
            frozenset({"extra_review"}), frozenset({"mesh_ready", "boundary_case"}),
            frozenset({"mesh", "legacy_cache"}), 4.0, 2.8,
            "sequential-live-set-v1", ("resolve_boundary",),
        ),
        "bad_boundary_reject": DominanceState(
            "bad_boundary_reject", "model-v1", "bounded", frozenset({"boundary"}),
            frozenset(), frozenset({"mesh_ready", "verified_bound"}),
            frozenset({"mesh", "bound"}), 7.0, 3.1,
            "sequential-live-set-v1", terminal="REJECT",
        ),
    }
    return DominanceGraph(states, actions)


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

    def test_state_dominance_requires_full_action_simulation(self) -> None:
        graph = make_dominance_graph()
        relation = greatest_simulation_relation(graph)
        self.assertIn(("good_root", "bad_root"), relation)
        self.assertNotIn(("bad_root", "good_root"), relation)
        self.assertEqual(prune_dominated_frontier(graph, ("good_root", "bad_root")),
                         ("good_root",))

    def test_narrower_qoi_set_without_matching_action_does_not_dominate(self) -> None:
        graph = make_dominance_graph(include_fast_action=False)
        relation = greatest_simulation_relation(graph)
        self.assertNotIn(("good_root", "bad_root"), relation)

    def test_more_expensive_action_does_not_dominate(self) -> None:
        graph = make_dominance_graph(fast_action_cost=3.0)
        relation = greatest_simulation_relation(graph)
        self.assertNotIn(("good_root", "bad_root"), relation)

    def test_unmatched_successor_prevents_dominance(self) -> None:
        graph = make_dominance_graph(fast_fail_child="bad_boundary")
        actions = dict(graph.actions)
        slow = actions["slow"]
        actions["slow"] = DominanceAction(
            slow.action_id, slow.semantic_key, slow.preconditions,
            slow.evidence_contract, slow.failure_semantics, slow.ru_upper,
            slow.during_peak_gb, (("pass", "bad_pass"), ("fail", "bad_fail")),
        )
        graph = DominanceGraph(graph.states, actions)
        relation = greatest_simulation_relation(graph)
        self.assertNotIn(("good_root", "bad_root"), relation)

    def test_outcome_labels_do_not_replace_successor_semantics(self) -> None:
        graph = make_dominance_graph()
        actions = dict(graph.actions)
        fast = actions["fast"]
        actions["fast"] = DominanceAction(
            fast.action_id, fast.semantic_key, fast.preconditions,
            fast.evidence_contract, fast.failure_semantics, fast.ru_upper,
            fast.during_peak_gb,
            (("green", "good_pass"), ("red", "good_fail")),
        )
        graph = DominanceGraph(graph.states, actions)
        relation = greatest_simulation_relation(graph)
        self.assertIn(("good_root", "bad_root"), relation)

    def test_different_model_scope_blocks_dominance(self) -> None:
        graph = make_dominance_graph()
        states = dict(graph.states)
        bad = states["bad_root"]
        states["bad_root"] = DominanceState(
            bad.state_id, "model-v2", bad.assurance_mode, bad.qoi_set,
            bad.open_obligations, bad.capabilities, bad.live_artifacts,
            bad.additive_spent_ru, bad.peak_committed_gb, bad.memory_model,
            bad.actions, bad.terminal,
        )
        relation = greatest_simulation_relation(DominanceGraph(states, graph.actions))
        self.assertNotIn(("good_root", "bad_root"), relation)

    def test_different_evidence_or_failure_contract_blocks_action_match(self) -> None:
        graph = make_dominance_graph()
        actions = dict(graph.actions)
        slow = actions["slow"]
        actions["slow"] = DominanceAction(
            slow.action_id, slow.semantic_key, slow.preconditions,
            frozenset({"statistical_estimate_only"}),
            frozenset({"timeout", "not_applicable", "model_invalid"}),
            slow.ru_upper, slow.during_peak_gb, slow.outcomes,
        )
        relation = greatest_simulation_relation(DominanceGraph(graph.states, actions))
        self.assertNotIn(("good_root", "bad_root"), relation)

    def test_simulation_relation_is_transitive_on_reference_graph(self) -> None:
        graph = make_dominance_graph()
        relation = greatest_simulation_relation(graph)
        for left, middle in relation:
            for middle_2, right in relation:
                if middle == middle_2:
                    self.assertIn((left, right), relation, (left, middle, right))

    def test_accept_and_reject_terminal_states_are_not_dominated(self) -> None:
        graph = make_dominance_graph()
        relation = greatest_simulation_relation(graph)
        self.assertNotIn(("good_pass", "good_fail"), relation)
        self.assertNotIn(("good_fail", "good_pass"), relation)

    def test_frontier_pruning_preserves_complete_policy_cost_and_verdicts(self) -> None:
        graph = make_dominance_graph()
        unpruned_candidates = ("good_root", "bad_root")
        pruned_candidates = prune_dominated_frontier(graph, unpruned_candidates)

        unpruned_frontier = candidate_policy_frontier(graph, unpruned_candidates)
        pruned_frontier = candidate_policy_frontier(graph, pruned_candidates)

        self.assertEqual(pruned_candidates, ("good_root",))
        self.assertEqual(len(unpruned_frontier), 1)
        self.assertEqual(len(pruned_frontier), 1)
        self.assertEqual(unpruned_frontier[0][1], frozenset({"ACCEPT", "REJECT"}))
        self.assertEqual(pruned_frontier[0][1], frozenset({"ACCEPT", "REJECT"}))
        self.assertAlmostEqual(unpruned_frontier[0][2], 2.0)
        self.assertAlmostEqual(pruned_frontier[0][2], 2.0)
        self.assertAlmostEqual(unpruned_frontier[0][3], 2.4)
        self.assertAlmostEqual(pruned_frontier[0][3], 2.4)

    def test_dominance_fixed_point_handles_cyclic_action_graph(self) -> None:
        actions = {
            "left_loop": DominanceAction(
                "left_loop", "loop", frozenset(), frozenset({"evidence"}), frozenset(),
                1.0, 1.0, (("again", "left"),),
            ),
            "right_loop": DominanceAction(
                "right_loop", "loop", frozenset(), frozenset({"evidence"}), frozenset(),
                2.0, 2.0, (("again", "right"),),
            ),
        }
        common = dict(
            model_scope="m", assurance_mode="bounded",
            capabilities=frozenset({"evidence"}), live_artifacts=frozenset(),
            memory_model="sequential-live-set-v1",
        )
        states = {
            "left": DominanceState(
                "left", qoi_set=frozenset({"q"}), open_obligations=frozenset(),
                additive_spent_ru=0.0, peak_committed_gb=0.0, actions=("left_loop",), **common
            ),
            "right": DominanceState(
                "right", qoi_set=frozenset({"q", "extra"}), open_obligations=frozenset({"review"}),
                additive_spent_ru=1.0, peak_committed_gb=1.0, actions=("right_loop",), **common
            ),
        }
        relation = greatest_simulation_relation(DominanceGraph(states, actions))
        self.assertIn(("left", "right"), relation)

    def test_resource_limits_reject_peak_overrun_even_when_ru_fits(self) -> None:
        self.assertIsNone(find_plan(self.fixture, "root", ResourceBudget(4.0, 2.5)))
        self.assertIsNotNone(find_plan(self.fixture, "root", ResourceBudget(4.0, 2.7)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
