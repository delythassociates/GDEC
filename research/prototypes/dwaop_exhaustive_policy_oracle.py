"""Independent exhaustive policy oracle for DWAOP v0.2.

This module implements a completely independent brute-force AND-OR policy tree
enumerator and world-by-world policy evaluator. It deliberately does NOT import
or call any pruning, refinement, or dominance-cover logic from
`dwaop_integrated_planner.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

try:
    from research.prototypes.dwaop_integrated_planner import (
        FAILURE_OR_INCONCLUSIVE_KINDS,
        NormalizedPolicy,
        OutcomeKind,
        ResourceBudget,
        ResourceVector,
        WorldOracle,
        validate_oracle,
        validate_resource_budget,
    )
except ImportError:
    from dwaop_integrated_planner import (
        FAILURE_OR_INCONCLUSIVE_KINDS,
        NormalizedPolicy,
        OutcomeKind,
        ResourceBudget,
        ResourceVector,
        WorldOracle,
        validate_oracle,
        validate_resource_budget,
    )


@dataclass(frozen=True)
class LeafVerdict:
    verdict: str


@dataclass(frozen=True)
class ActionBranch:
    action_id: str
    branches_by_label: Mapping[str, "PolicyTree"]


PolicyTree = Union[LeafVerdict, ActionBranch]


@dataclass(frozen=True)
class _SimState:
    worlds: FrozenSet[str]
    open_obligations: FrozenSet[str]
    capabilities: FrozenSet[str]
    remaining_actions: FrozenSet[str]
    remaining_retries: int
    model_valid: bool
    evidence_stale: bool
    last_outcome_kind: Optional[OutcomeKind]


def _independent_terminal_verdict(state: _SimState, oracle: WorldOracle) -> Optional[str]:
    if not state.worlds:
        return None
    if (
        not state.model_valid
        or state.evidence_stale
        or state.last_outcome_kind in FAILURE_OR_INCONCLUSIVE_KINDS
    ):
        return "REFUSE"
    if state.open_obligations:
        return None
    decisions = {oracle.decision_by_world[w] for w in state.worlds}
    if len(decisions) == 1:
        return next(iter(decisions))
    return None


def _independent_enabled(state: _SimState, action_id: str, oracle: WorldOracle) -> bool:
    spec = oracle.actions.get(action_id)
    if spec is None or action_id not in state.remaining_actions:
        return False
    if not (
        state.worlds <= spec.applicable_worlds
        and spec.required_capabilities <= state.capabilities
        and spec.required_obligations <= state.open_obligations
    ):
        return False
    for label in {spec.observable_label_by_world[w] for w in state.worlds}:
        if spec.outcome_kind_by_label[label] == OutcomeKind.BOUNDED_RETRY:
            needed = max(1, spec.retry_cost_by_label[label])
            if state.remaining_retries < needed:
                return False
    return True


def _enumerate_trees(
    state: _SimState,
    oracle: WorldOracle,
    depth_left: int,
) -> Tuple[PolicyTree, ...]:
    """Brute-force enumeration of all syntactically complete contingent policy trees."""
    if depth_left < 0 or not state.worlds:
        return ()

    verdict = _independent_terminal_verdict(state, oracle)
    trees: List[PolicyTree] = []
    if verdict in {"ACCEPT", "REJECT"}:
        return (LeafVerdict(verdict),)
    if verdict == "REFUSE":
        if (
            not state.model_valid
            or state.evidence_stale
            or state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL
        ):
            return (LeafVerdict("REFUSE"),)
        trees.append(LeafVerdict("REFUSE"))
    if depth_left == 0:
        return tuple(trees)
    for action_id in sorted(state.remaining_actions):
        if not _independent_enabled(state, action_id, oracle):
            continue
        spec = oracle.actions[action_id]
        labels = sorted({spec.observable_label_by_world[w] for w in state.worlds})
        child_lists: List[Tuple[PolicyTree, ...]] = []
        valid = True
        for label in labels:
            sub_worlds = frozenset(
                w for w in state.worlds if spec.observable_label_by_world[w] == label
            )
            kind = spec.outcome_kind_by_label[label]
            next_model_valid = state.model_valid and not (
                spec.invalidates_model_by_label[label] or kind == OutcomeKind.MODEL_INVALIDATED
            )
            next_stale = state.evidence_stale or (
                spec.stale_evidence_by_label[label] or kind == OutcomeKind.STALE_EVIDENCE
            )
            if kind == OutcomeKind.BOUNDED_RETRY:
                next_retries = state.remaining_retries - max(1, spec.retry_cost_by_label[label])
                next_remaining = state.remaining_actions
            else:
                next_retries = state.remaining_retries
                next_remaining = state.remaining_actions - {action_id}

            if next_model_valid and not next_stale and kind not in FAILURE_OR_INCONCLUSIVE_KINDS:
                next_obligations = state.open_obligations - spec.discharged_by_label[label]
            else:
                next_obligations = state.open_obligations

            child_state = _SimState(
                worlds=sub_worlds,
                open_obligations=next_obligations,
                capabilities=state.capabilities | spec.capabilities_by_label[label],
                remaining_actions=next_remaining,
                remaining_retries=next_retries,
                model_valid=next_model_valid,
                evidence_stale=next_stale,
                last_outcome_kind=kind,
            )
            sub_trees = _enumerate_trees(child_state, oracle, depth_left - 1)
            if not sub_trees:
                valid = False
                break
            child_lists.append(sub_trees)

        if not valid or not child_lists:
            continue

        for combo in product(*child_lists):
            branch_map = {label: tree for label, tree in zip(labels, combo)}
            trees.append(ActionBranch(action_id=action_id, branches_by_label=branch_map))

    return tuple(trees)


def _evaluate_tree_on_world(
    tree: PolicyTree,
    world: str,
    oracle: WorldOracle,
    budget: ResourceBudget,
) -> Optional[Tuple[str, ResourceVector, int]]:
    """Independently simulate a single world through `tree` and verify budget & terminal rules."""
    open_obligations = oracle.initial_obligations
    capabilities = oracle.initial_capabilities
    remaining_actions = frozenset(oracle.actions)
    remaining_retries = oracle.initial_retries
    model_valid = True
    evidence_stale = False
    last_kind: Optional[OutcomeKind] = None

    ru = 0.0
    cpu = 0.0
    energy = 0.0
    resident = 0.0
    peak = 0.0
    actions_taken = 0

    node = tree
    while isinstance(node, ActionBranch):
        spec = oracle.actions.get(node.action_id)
        if spec is None or node.action_id not in remaining_actions:
            return None
        if world not in spec.applicable_worlds:
            return None
        if not (spec.required_capabilities <= capabilities and spec.required_obligations <= open_obligations):
            return None

        label = spec.observable_label_by_world[world]
        if label not in node.branches_by_label:
            return None

        kind = spec.outcome_kind_by_label[label]
        if kind == OutcomeKind.BOUNDED_RETRY:
            needed = max(1, spec.retry_cost_by_label[label])
            if remaining_retries < needed:
                return None
            remaining_retries -= needed
        else:
            remaining_actions = remaining_actions - {node.action_id}

        during_peak = resident + spec.workspace_gb_upper + spec.overlap_gb_upper
        resident = max(
            0.0,
            resident + spec.retained_output_gb_by_label[label] - spec.released_memory_gb_by_label[label],
        )
        peak = max(peak, during_peak, resident)
        ru += spec.ru_upper
        cpu += spec.cpu_ticks
        energy += spec.energy_ticks

        vec = ResourceVector(ru, cpu, energy, peak)
        if not budget.allows(vec):
            return None

        model_valid = model_valid and not (
            spec.invalidates_model_by_label[label] or kind == OutcomeKind.MODEL_INVALIDATED
        )
        evidence_stale = evidence_stale or (
            spec.stale_evidence_by_label[label] or kind == OutcomeKind.STALE_EVIDENCE
        )
        if model_valid and not evidence_stale and kind not in FAILURE_OR_INCONCLUSIVE_KINDS:
            open_obligations = open_obligations - spec.discharged_by_label[label]
        capabilities = capabilities | spec.capabilities_by_label[label]
        last_kind = kind
        actions_taken += 1
        node = node.branches_by_label[label]

    verdict = node.verdict
    if verdict == "ACCEPT":
        if not (model_valid and not evidence_stale and not open_obligations and oracle.decision_by_world[world] == "ACCEPT"):
            return None
    elif verdict == "REJECT":
        if not (model_valid and not evidence_stale and not open_obligations and oracle.decision_by_world[world] == "REJECT"):
            return None
    elif verdict == "REFUSE":
        if not (not model_valid or evidence_stale or last_kind in FAILURE_OR_INCONCLUSIVE_KINDS):
            return None
    else:
        return None

    return verdict, ResourceVector(ru, cpu, energy, peak), actions_taken



def _oracle_verdict_no_worse(left: str, right: str) -> bool:
    if left == right:
        return True
    return left in {"ACCEPT", "REJECT"} and right == "REFUSE"


def _oracle_resource_tuple(vec: ResourceVector) -> Tuple[float, float, float, float]:
    return (vec.ru_upper, vec.cpu_ticks, vec.energy_ticks, vec.peak_memory_gb)


def _oracle_dominates(left: NormalizedPolicy, right: NormalizedPolicy) -> bool:
    if len(left.world_verdict_map) != len(right.world_verdict_map):
        return False
    for (lw, lv), (rw, rv) in zip(left.world_verdict_map, right.world_verdict_map):
        if lw != rw or not _oracle_verdict_no_worse(lv, rv):
            return False
    lv = _oracle_resource_tuple(left.resource_vector)
    rv = _oracle_resource_tuple(right.resource_vector)
    if not all(a <= b for a, b in zip(lv, rv)):
        return False
    return left.world_verdict_map != right.world_verdict_map or any(a < b for a, b in zip(lv, rv))


def _oracle_pareto_reduce(policies: List[NormalizedPolicy]) -> Tuple[NormalizedPolicy, ...]:
    unique: Dict[tuple, NormalizedPolicy] = {}
    for policy in policies:
        key = (policy.world_verdict_map, policy.terminal_verdicts, _oracle_resource_tuple(policy.resource_vector))
        current = unique.get(key)
        if current is None or policy.max_actions_on_path < current.max_actions_on_path:
            unique[key] = policy
    values = list(unique.values())
    frontier = [candidate for candidate in values
                if not any(other is not candidate and _oracle_dominates(other, candidate) for other in values)]
    return tuple(sorted(frontier, key=lambda p: (
        p.world_verdict_map, _oracle_resource_tuple(p.resource_vector), p.max_actions_on_path
    )))


def enumerate_exact_pareto_frontier(
    oracle: WorldOracle,
    budget: ResourceBudget,
    max_horizon: int = 10,
) -> Tuple[NormalizedPolicy, ...]:
    """Independently enumerate all complete policies and return the exact Pareto frontier."""
    validate_oracle(oracle)
    validate_resource_budget(budget)

    root_state = _SimState(
        worlds=oracle.universe,
        open_obligations=oracle.initial_obligations,
        capabilities=oracle.initial_capabilities,
        remaining_actions=frozenset(oracle.actions),
        remaining_retries=oracle.initial_retries,
        model_valid=True,
        evidence_stale=False,
        last_outcome_kind=None,
    )
    all_trees = _enumerate_trees(root_state, oracle, max_horizon)

    normalized: List[NormalizedPolicy] = []
    sorted_worlds = sorted(oracle.universe)
    for tree in all_trees:
        world_verdicts: List[Tuple[str, str]] = []
        world_vectors: List[ResourceVector] = []
        max_actions = 0
        valid_all = True
        for w in sorted_worlds:
            res = _evaluate_tree_on_world(tree, w, oracle, budget)
            if res is None:
                valid_all = False
                break
            verdict, vec, depth = res
            world_verdicts.append((w, verdict))
            world_vectors.append(vec)
            if depth > max_actions:
                max_actions = depth
        if not valid_all:
            continue
        worst_vec = ResourceVector.max_across(world_vectors)
        if not budget.allows(worst_vec):
            continue
        normalized.append(
            NormalizedPolicy(
                world_verdict_map=tuple(world_verdicts),
                resource_vector=worst_vec,
                terminal_verdicts=frozenset(v for _, v in world_verdicts),
                max_actions_on_path=max_actions,
            )
        )

    return _oracle_pareto_reduce(normalized)
