"""Finite-world oracle for DWAOP outcome-refinement research.

This is a research-only reference model. It does not import GDEC production
modules, solve a PDE, produce a numerical certificate, or establish physical
model validity. Its purpose is to test whether a certificate-backed
possible-world refinement relation can safely preserve finite contingent
computation policies.

Run:
    python -m unittest -v dwaop_outcome_refinement_oracle
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
from typing import FrozenSet, Mapping, Optional, Sequence, Tuple
import unittest


WorldSet = FrozenSet[str]


class ContractError(ValueError):
    """An action contract or one of its outcome certificates is invalid."""


@dataclass(frozen=True)
class ActionSemantics:
    """Trusted finite semantics used by the reference oracle.

    `observable_label_by_world` is a deterministic observation map for this
    finite test domain. Real numerical actions may be nondeterministic; that
    requires a richer outcome relation and is deliberately outside this
    first reference model.
    """

    action_id: str
    semantic_key: str
    applicable_worlds: WorldSet
    observable_label_by_world: Mapping[str, str]
    required_capabilities: FrozenSet[str]
    required_obligations: FrozenSet[str]
    evidence_contract: FrozenSet[str]
    failure_semantics: FrozenSet[str]
    ru_upper: float
    workspace_gb_upper: float
    overlap_gb_upper: float
    discharged_by_label: Mapping[str, FrozenSet[str]]
    capabilities_by_label: Mapping[str, FrozenSet[str]]
    retained_output_gb_by_label: Mapping[str, float]
    proof_id_by_label: Mapping[str, str]


@dataclass(frozen=True)
class WorldOracle:
    specification_id: str
    model_id: str
    universe: WorldSet
    decision_by_world: Mapping[str, str]
    actions: Mapping[str, ActionSemantics]


@dataclass(frozen=True)
class OutcomeCertificate:
    specification_id: str
    model_id: str
    action_id: str
    outcome_label: str
    worlds: WorldSet
    discharged_obligations: FrozenSet[str]
    gained_capabilities: FrozenSet[str]
    retained_output_gb_upper: float
    proof_id: str


@dataclass(frozen=True)
class OutcomeCell:
    label: str
    worlds: WorldSet
    discharged_obligations: FrozenSet[str]
    gained_capabilities: FrozenSet[str]
    retained_output_gb_upper: float
    certificate: OutcomeCertificate


@dataclass(frozen=True)
class ActionContract:
    action_id: str
    semantic_key: str
    specification_id: str
    model_id: str
    applicable_worlds: WorldSet
    required_capabilities: FrozenSet[str]
    required_obligations: FrozenSet[str]
    evidence_contract: FrozenSet[str]
    failure_semantics: FrozenSet[str]
    ru_upper: float
    workspace_gb_upper: float
    overlap_gb_upper: float
    outcomes: Tuple[OutcomeCell, ...]


@dataclass(frozen=True)
class EvidenceState:
    specification_id: str
    model_id: str
    worlds: WorldSet
    open_obligations: FrozenSet[str]
    capabilities: FrozenSet[str]
    remaining_actions: FrozenSet[str]
    spent_ru_upper: float = 0.0
    resident_memory_gb_upper: float = 0.0
    peak_memory_gb_upper: float = 0.0
    parent_state_snapshot: Optional["EvidenceState"] = None
    last_action_id: Optional[str] = None
    last_outcome_label: Optional[str] = None


@dataclass(frozen=True)
class ResourceBudget:
    ru_upper: float
    peak_memory_gb_upper: float


@dataclass(frozen=True)
class StateTransition:
    action_id: str
    outcome_label: str
    state: EvidenceState


@dataclass(frozen=True)
class PolicySummary:
    terminal_verdicts: FrozenSet[str]
    additional_ru_upper: float
    peak_memory_gb_upper: float
    max_actions_on_path: int


def _nonnegative(value: float, field_name: str) -> None:
    if value < 0:
        raise ContractError(f"{field_name} must be non-negative")


def validate_oracle(oracle: WorldOracle) -> None:
    if not oracle.specification_id or not oracle.model_id:
        raise ContractError("Oracle specification/model identity is required")
    if not oracle.universe:
        raise ContractError("Oracle universe must not be empty")
    if set(oracle.decision_by_world) != set(oracle.universe):
        raise ContractError("Every oracle world must have exactly one reference decision")
    if any(v not in {"ACCEPT", "REJECT"} for v in oracle.decision_by_world.values()):
        raise ContractError("Reference decisions must be ACCEPT or REJECT")
    for action_id, spec in oracle.actions.items():
        if action_id != spec.action_id:
            raise ContractError(f"Action key/id mismatch for {action_id}")
        if not spec.semantic_key:
            raise ContractError(f"Missing semantic key for {action_id}")
        if not spec.applicable_worlds or not spec.applicable_worlds <= oracle.universe:
            raise ContractError(f"Invalid applicability domain for {action_id}")
        if set(spec.observable_label_by_world) != set(spec.applicable_worlds):
            raise ContractError(f"Outcome map must cover applicability domain for {action_id}")
        labels = set(spec.observable_label_by_world.values())
        if not labels or any(not x for x in labels):
            raise ContractError(f"Invalid outcome label in {action_id}")
        if set(spec.discharged_by_label) != labels:
            raise ContractError(f"Discharge effects must cover exact labels for {action_id}")
        if set(spec.capabilities_by_label) != labels:
            raise ContractError(f"Capability effects must cover exact labels for {action_id}")
        if set(spec.retained_output_gb_by_label) != labels:
            raise ContractError(f"Memory effects must cover exact labels for {action_id}")
        if set(spec.proof_id_by_label) != labels:
            raise ContractError(f"Proof IDs must cover exact labels for {action_id}")
        _nonnegative(spec.ru_upper, f"{action_id}.ru_upper")
        _nonnegative(spec.workspace_gb_upper, f"{action_id}.workspace_gb_upper")
        _nonnegative(spec.overlap_gb_upper, f"{action_id}.overlap_gb_upper")
        for label in labels:
            _nonnegative(spec.retained_output_gb_by_label[label],
                         f"{action_id}.{label}.retained_output_gb_upper")
            if not spec.proof_id_by_label[label]:
                raise ContractError(f"Missing proof id for {action_id}/{label}")


def build_action_contract(oracle: WorldOracle, action_id: str) -> ActionContract:
    """Build a complete contract from the finite trusted semantics."""
    validate_oracle(oracle)
    try:
        spec = oracle.actions[action_id]
    except KeyError as exc:
        raise ContractError(f"Unknown action {action_id}") from exc

    cells = []
    labels = sorted(set(spec.observable_label_by_world.values()))
    for label in labels:
        worlds = frozenset(
            world for world, observed in spec.observable_label_by_world.items()
            if observed == label
        )
        discharged = spec.discharged_by_label[label]
        gained = spec.capabilities_by_label[label]
        retained = spec.retained_output_gb_by_label[label]
        cert = OutcomeCertificate(
            specification_id=oracle.specification_id,
            model_id=oracle.model_id,
            action_id=action_id,
            outcome_label=label,
            worlds=worlds,
            discharged_obligations=discharged,
            gained_capabilities=gained,
            retained_output_gb_upper=retained,
            proof_id=spec.proof_id_by_label[label],
        )
        cells.append(OutcomeCell(label, worlds, discharged, gained, retained, cert))

    return ActionContract(
        action_id=spec.action_id,
        semantic_key=spec.semantic_key,
        specification_id=oracle.specification_id,
        model_id=oracle.model_id,
        applicable_worlds=spec.applicable_worlds,
        required_capabilities=spec.required_capabilities,
        required_obligations=spec.required_obligations,
        evidence_contract=spec.evidence_contract,
        failure_semantics=spec.failure_semantics,
        ru_upper=spec.ru_upper,
        workspace_gb_upper=spec.workspace_gb_upper,
        overlap_gb_upper=spec.overlap_gb_upper,
        outcomes=tuple(cells),
    )


def verify_action_contract(oracle: WorldOracle, contract: ActionContract) -> None:
    """Check a finite action contract against the independent semantics table.

    This is an oracle consistency check, not a numerical proof checker. In a
    real GDEC implementation, the certificate checker must validate a
    mathematically justified enclosure/set transition rather than compare it
    with a synthetic truth table.
    """
    validate_oracle(oracle)
    spec = oracle.actions.get(contract.action_id)
    if spec is None:
        raise ContractError(f"Unknown action {contract.action_id}")
    if contract.specification_id != oracle.specification_id:
        raise ContractError("Action contract has the wrong specification scope")
    if contract.model_id != oracle.model_id:
        raise ContractError("Action contract has the wrong model scope")
    if contract.semantic_key != spec.semantic_key:
        raise ContractError("Action semantic key does not match trusted semantics")
    if not contract.applicable_worlds or not contract.applicable_worlds <= spec.applicable_worlds:
        raise ContractError("Contract applicability is empty or exceeds trusted applicability")
    if contract.required_capabilities != spec.required_capabilities:
        raise ContractError("Action capability preconditions mismatch")
    if contract.required_obligations != spec.required_obligations:
        raise ContractError("Action obligation preconditions mismatch")
    if contract.evidence_contract != spec.evidence_contract:
        raise ContractError("Evidence contract mismatch")
    if contract.failure_semantics != spec.failure_semantics:
        raise ContractError("Failure semantics mismatch")

    if contract.ru_upper + 1e-12 < spec.ru_upper:
        raise ContractError("RU upper bound understates trusted action cost")
    if contract.workspace_gb_upper + 1e-12 < spec.workspace_gb_upper:
        raise ContractError("Workspace upper bound understates trusted action cost")
    if contract.overlap_gb_upper + 1e-12 < spec.overlap_gb_upper:
        raise ContractError("Overlap upper bound understates trusted action cost")

    labels = [cell.label for cell in contract.outcomes]
    if not labels or any(not label for label in labels) or len(labels) != len(set(labels)):
        raise ContractError("Outcome labels must be non-empty and unique")

    expected_labels = {
        spec.observable_label_by_world[world]
        for world in contract.applicable_worlds
    }
    if set(labels) != expected_labels:
        raise ContractError("Outcome labels do not match the trusted observable partition")

    seen: set[str] = set()
    for cell in contract.outcomes:
        if not cell.worlds:
            raise ContractError(f"Outcome cell {cell.label} is empty")
        if not cell.worlds <= contract.applicable_worlds:
            raise ContractError(f"Outcome cell {cell.label} exceeds action applicability")
        if seen & set(cell.worlds):
            raise ContractError(f"Outcome cells overlap at {sorted(seen & set(cell.worlds))}")
        seen.update(cell.worlds)

        expected_worlds = frozenset(
            world for world in contract.applicable_worlds
            if spec.observable_label_by_world[world] == cell.label
        )
        if cell.worlds != expected_worlds:
            raise ContractError(f"Outcome cell {cell.label} has incorrect world semantics")
        expected_discharge = spec.discharged_by_label[cell.label]
        expected_capabilities = spec.capabilities_by_label[cell.label]
        expected_retained = spec.retained_output_gb_by_label[cell.label]
        expected_proof_id = spec.proof_id_by_label[cell.label]
        if cell.discharged_obligations != expected_discharge:
            raise ContractError(f"Unjustified obligation discharge in {cell.label}")
        if cell.gained_capabilities != expected_capabilities:
            raise ContractError(f"Unjustified capability gain in {cell.label}")
        if cell.retained_output_gb_upper + 1e-12 < expected_retained:
            raise ContractError(f"Retained-memory upper bound understates {cell.label}")

        cert = cell.certificate
        if cert.specification_id != oracle.specification_id or cert.model_id != oracle.model_id:
            raise ContractError(f"Certificate scope mismatch in {cell.label}")
        if cert.action_id != contract.action_id or cert.outcome_label != cell.label:
            raise ContractError(f"Certificate action/outcome identity mismatch in {cell.label}")
        if cert.worlds != cell.worlds:
            raise ContractError(f"Certificate world set mismatch in {cell.label}")
        if cert.discharged_obligations != expected_discharge:
            raise ContractError(f"Certificate obligation claim mismatch in {cell.label}")
        if cert.gained_capabilities != expected_capabilities:
            raise ContractError(f"Certificate capability claim mismatch in {cell.label}")
        if cert.retained_output_gb_upper + 1e-12 < expected_retained:
            raise ContractError(f"Certificate memory bound understates {cell.label}")
        if cert.retained_output_gb_upper + 1e-12 < cell.retained_output_gb_upper:
            raise ContractError(f"Certificate memory bound does not cover the cell claim in {cell.label}")
        if cert.proof_id != expected_proof_id:
            raise ContractError(f"Certificate proof ID mismatch in {cell.label}")

    if seen != set(contract.applicable_worlds):
        raise ContractError("Outcome cells do not exhaustively cover action applicability")


def _enabled(state: EvidenceState, contract: ActionContract, oracle: WorldOracle) -> bool:
    try:
        verify_action_contract(oracle, contract)
    except ContractError:
        return False
    return (
        contract.action_id in state.remaining_actions
        and state.specification_id == contract.specification_id
        and state.model_id == contract.model_id
        and state.worlds <= contract.applicable_worlds
        and contract.required_capabilities <= state.capabilities
        and contract.required_obligations <= state.open_obligations
    )


def action_transitions(
    state: EvidenceState,
    contract: ActionContract,
    oracle: WorldOracle,
) -> Tuple[StateTransition, ...]:
    if not _enabled(state, contract, oracle):
        return ()

    transitions = []
    covered: set[str] = set()
    for cell in contract.outcomes:
        child_worlds = state.worlds & cell.worlds
        if not child_worlds:
            continue
        if covered & set(child_worlds):
            raise ContractError("Enabled action outcome cells overlap the current state")
        covered.update(child_worlds)
        during_peak = (
            state.resident_memory_gb_upper
            + contract.workspace_gb_upper
            + contract.overlap_gb_upper
        )
        resident_after = state.resident_memory_gb_upper + cell.retained_output_gb_upper
        child = EvidenceState(
            specification_id=state.specification_id,
            model_id=state.model_id,
            worlds=frozenset(child_worlds),
            open_obligations=state.open_obligations - cell.discharged_obligations,
            capabilities=state.capabilities | cell.gained_capabilities,
            remaining_actions=state.remaining_actions - {contract.action_id},
            spent_ru_upper=state.spent_ru_upper + contract.ru_upper,
            resident_memory_gb_upper=resident_after,
            peak_memory_gb_upper=max(state.peak_memory_gb_upper, during_peak, resident_after),
            parent_state_snapshot=state,
            last_action_id=contract.action_id,
            last_outcome_label=cell.label,
        )
        transitions.append(StateTransition(contract.action_id, cell.label, child))

    if covered != set(state.worlds):
        raise ContractError("Action outcome cells fail to cover current possible worlds")
    return tuple(transitions)


def verify_state_provenance(
    state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
) -> bool:
    """Verify a state's ancestry through checked finite action transitions.

    A root state must represent the full oracle universe and have a zeroed
    resource ledger. Every non-root state must be exactly one child produced by
    its recorded parent/action/outcome transition. This deliberately prevents
    callers from asserting an arbitrary narrower possible-world set.
    """
    if state.specification_id != oracle.specification_id or state.model_id != oracle.model_id:
        return False
    if not state.worlds or not state.worlds <= oracle.universe:
        return False
    if state.parent_state_snapshot is None:
        return (
            state.worlds == oracle.universe
            and state.spent_ru_upper == 0.0
            and state.resident_memory_gb_upper == 0.0
            and state.peak_memory_gb_upper == 0.0
            and state.last_action_id is None
            and state.last_outcome_label is None
        )
    if not state.last_action_id or not state.last_outcome_label:
        return False
    parent = state.parent_state_snapshot
    if not verify_state_provenance(parent, contracts, oracle):
        return False
    contract = contracts.get(state.last_action_id)
    if contract is None:
        return False
    return any(
        transition.outcome_label == state.last_outcome_label
        and transition.state == state
        for transition in action_transitions(parent, contract, oracle)
    )


def terminal_verdict(state: EvidenceState, oracle: WorldOracle) -> Optional[str]:
    if not state.worlds or state.open_obligations:
        return None
    decisions = {oracle.decision_by_world[world] for world in state.worlds}
    if len(decisions) == 1:
        return next(iter(decisions))
    return None


def _summary_dominates(left: PolicySummary, right: PolicySummary) -> bool:
    no_worse = (
        left.terminal_verdicts <= right.terminal_verdicts
        and left.additional_ru_upper <= right.additional_ru_upper + 1e-12
        and left.peak_memory_gb_upper <= right.peak_memory_gb_upper + 1e-12
    )
    strict = (
        left.terminal_verdicts != right.terminal_verdicts
        or left.additional_ru_upper < right.additional_ru_upper - 1e-12
        or left.peak_memory_gb_upper < right.peak_memory_gb_upper - 1e-12
    )
    return no_worse and strict


def pareto_policy_summaries(summaries: Sequence[PolicySummary]) -> Tuple[PolicySummary, ...]:
    result = []
    for candidate in summaries:
        if not any(other is not candidate and _summary_dominates(other, candidate)
                   for other in summaries):
            result.append(candidate)
    return tuple(result)


def enumerate_complete_policies(
    state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
    depth_left: int = 10,
) -> Tuple[PolicySummary, ...]:
    """Exhaustively enumerate finite decision-complete contingent policies.

    OR: select one enabled action. AND: every possible observable outcome must
    have a complete continuation. RU adds along a realised path and takes the
    maximum over mutually exclusive branches. Peak memory uses a high-water
    maximum, never a sum of action workspaces.
    """
    if depth_left < 0 or not state.worlds:
        return ()
    if state.peak_memory_gb_upper > budget.peak_memory_gb_upper + 1e-12:
        return ()
    if state.spent_ru_upper > budget.ru_upper + 1e-12:
        return ()

    terminal = terminal_verdict(state, oracle)
    if terminal is not None:
        return (PolicySummary(frozenset({terminal}), 0.0,
                              state.peak_memory_gb_upper, 0),)
    if depth_left == 0:
        return ()

    from itertools import product as cartesian_product

    complete = []
    for action_id in sorted(state.remaining_actions):
        contract = contracts.get(action_id)
        if contract is None:
            continue
        transitions = action_transitions(state, contract, oracle)
        if not transitions:
            continue
        if any(t.state.spent_ru_upper > budget.ru_upper + 1e-12
               or t.state.peak_memory_gb_upper > budget.peak_memory_gb_upper + 1e-12
               for t in transitions):
            continue

        branch_summaries = [
            enumerate_complete_policies(t.state, contracts, oracle, budget, depth_left - 1)
            for t in transitions
        ]
        if not branch_summaries or any(not branch for branch in branch_summaries):
            continue

        for selected in cartesian_product(*branch_summaries):
            child_ru = max(s.additional_ru_upper for s in selected)
            child_peak = max(s.peak_memory_gb_upper for s in selected)
            child_actions = max(s.max_actions_on_path for s in selected)
            summary = PolicySummary(
                terminal_verdicts=frozenset().union(*(s.terminal_verdicts for s in selected)),
                additional_ru_upper=contract.ru_upper + child_ru,
                peak_memory_gb_upper=max(state.peak_memory_gb_upper,
                                         *(s.peak_memory_gb_upper for s in selected)),
                max_actions_on_path=1 + child_actions,
            )
            if state.spent_ru_upper + summary.additional_ru_upper <= budget.ru_upper + 1e-12:
                complete.append(summary)
    return pareto_policy_summaries(complete)


def _action_matches_no_worse(left: ActionContract, right: ActionContract) -> bool:
    return (
        left.semantic_key == right.semantic_key
        and left.specification_id == right.specification_id
        and left.model_id == right.model_id
        and left.required_capabilities == right.required_capabilities
        and left.required_obligations == right.required_obligations
        and left.evidence_contract == right.evidence_contract
        and left.failure_semantics == right.failure_semantics
        and left.ru_upper <= right.ru_upper + 1e-12
        and left.workspace_gb_upper <= right.workspace_gb_upper + 1e-12
        and left.overlap_gb_upper <= right.overlap_gb_upper + 1e-12
    )


def state_refines(
    left: EvidenceState,
    right: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    depth_left: int = 10,
) -> bool:
    """Conservative finite-horizon simulation over observable outcome cells.

    `left` is the more informed state. Every possible left outcome of a
    matching action must be contained in exactly one compatible right outcome
    region, and related successor states must satisfy the relation recursively.
    Labels are not compared as proof of equivalence; world-set containment is.
    """
    if depth_left < 0:
        return False
    if not verify_state_provenance(left, contracts, oracle):
        return False
    if not verify_state_provenance(right, contracts, oracle):
        return False
    if not (
        left.specification_id == right.specification_id == oracle.specification_id
        and left.model_id == right.model_id == oracle.model_id
        and left.worlds <= right.worlds
        and left.open_obligations <= right.open_obligations
        and right.capabilities <= left.capabilities
        and left.spent_ru_upper <= right.spent_ru_upper + 1e-12
        and left.resident_memory_gb_upper <= right.resident_memory_gb_upper + 1e-12
        and left.peak_memory_gb_upper <= right.peak_memory_gb_upper + 1e-12
    ):
        return False

    left_terminal = terminal_verdict(left, oracle)
    right_terminal = terminal_verdict(right, oracle)
    if left_terminal is not None or right_terminal is not None:
        return left_terminal is not None and left_terminal == right_terminal
    if depth_left == 0:
        # An unresolved state at the search horizon is not a simulation proof.
        return False

    right_enabled = []
    for action_id in sorted(right.remaining_actions):
        contract = contracts.get(action_id)
        if contract and _enabled(right, contract, oracle):
            right_enabled.append(contract)

    if not right_enabled:
        return False

    for right_action in right_enabled:
        matched = False
        for left_action_id in sorted(left.remaining_actions):
            left_action = contracts.get(left_action_id)
            if left_action is None or not _enabled(left, left_action, oracle):
                continue
            if not _action_matches_no_worse(left_action, right_action):
                continue

            left_transitions = action_transitions(left, left_action, oracle)
            right_transitions = action_transitions(right, right_action, oracle)
            if not left_transitions or not right_transitions:
                continue
            mapping_valid = True
            for lt in left_transitions:
                compatible = [rt for rt in right_transitions if lt.state.worlds <= rt.state.worlds]
                if len(compatible) != 1:
                    mapping_valid = False
                    break
                if not state_refines(lt.state, compatible[0].state, contracts, oracle,
                                     depth_left - 1):
                    mapping_valid = False
                    break
            if mapping_valid:
                matched = True
                break
        if not matched:
            return False
    return True


def _state_key(state: EvidenceState) -> tuple:
    """Stable structural identity for sibling-outcome grouping."""
    return (
        state.specification_id,
        state.model_id,
        tuple(sorted(state.worlds)),
        tuple(sorted(state.open_obligations)),
        tuple(sorted(state.capabilities)),
        tuple(sorted(state.remaining_actions)),
        round(state.spent_ru_upper, 12),
        round(state.resident_memory_gb_upper, 12),
        round(state.peak_memory_gb_upper, 12),
    )


def enumerate_action_policy_summaries(
    parent: EvidenceState,
    action_id: str,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
    depth_left: int = 10,
) -> Tuple[PolicySummary, ...]:
    """Enumerate complete policies rooted at one action and all its outcomes."""
    contract = contracts.get(action_id)
    if contract is None:
        return ()
    transitions = action_transitions(parent, contract, oracle)
    if not transitions:
        return ()
    branches = [
        enumerate_complete_policies(t.state, contracts, oracle, budget, depth_left - 1)
        for t in transitions
    ]
    if not branches or any(not choices for choices in branches):
        return ()

    summaries = []
    for selected in product(*branches):
        future_ru = contract.ru_upper + max(s.additional_ru_upper for s in selected)
        peak = max(parent.peak_memory_gb_upper,
                   *(s.peak_memory_gb_upper for s in selected))
        if parent.spent_ru_upper + future_ru > budget.ru_upper + 1e-12:
            continue
        if peak > budget.peak_memory_gb_upper + 1e-12:
            continue
        summaries.append(PolicySummary(
            terminal_verdicts=frozenset().union(*(s.terminal_verdicts for s in selected)),
            additional_ru_upper=future_ru,
            peak_memory_gb_upper=peak,
            max_actions_on_path=1 + max(s.max_actions_on_path for s in selected),
        ))
    return pareto_policy_summaries(summaries)


def _group_forms_complete_refinement_cover(
    candidate_children: Sequence[EvidenceState],
    coarse_state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
) -> bool:
    """Check that sibling children form a complete, usable cover of a coarse state.

    A single subset state is never enough. All outcomes of one checked action
    from the same parent must be present; their world sets must be disjoint and
    cover the coarse state's full world set; and each child must safely simulate
    the coarse state's continuations. The expanded action policy must also be
    complete under the supplied resource budget.
    """
    if not candidate_children:
        return False
    first = candidate_children[0]
    parent = first.parent_state_snapshot
    action_id = first.last_action_id
    if parent is None or not action_id:
        return False
    if coarse_state.parent_state_snapshot is None:
        return False
    if _state_key(parent) != _state_key(coarse_state.parent_state_snapshot):
        return False
    if parent.worlds != coarse_state.worlds:
        return False
    if coarse_state.last_action_id is None:
        return False
    if not verify_state_provenance(coarse_state, contracts, oracle):
        return False
    coarse_action = contracts.get(coarse_state.last_action_id)
    if coarse_action is None or not any(
        t.outcome_label == coarse_state.last_outcome_label and t.state == coarse_state
        for t in action_transitions(parent, coarse_action, oracle)
    ):
        return False
    if any(
        child.parent_state_snapshot is None
        or _state_key(child.parent_state_snapshot) != _state_key(parent)
        or child.last_action_id != action_id
        for child in candidate_children
    ):
        return False

    expected_transitions = action_transitions(parent, contracts[action_id], oracle)
    expected_states = {t.state for t in expected_transitions}
    actual_states = set(candidate_children)
    if actual_states != expected_states:
        return False

    seen: set[str] = set()
    for child in candidate_children:
        if seen & set(child.worlds):
            return False
        seen.update(child.worlds)
        if not state_refines(child, coarse_state, contracts, oracle):
            return False
    if seen != set(coarse_state.worlds):
        return False

    # Do not prune the coarse continuation if a refined branch cannot itself
    # reach a supported terminal outcome within the same hard budget.
    if not enumerate_action_policy_summaries(parent, action_id, contracts,
                                             oracle, budget):
        return False
    for child in candidate_children:
        if not enumerate_complete_policies(child, contracts, oracle, budget):
            return False
    return True


def prune_by_refinement_cover(
    candidates: Mapping[str, EvidenceState],
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
) -> Tuple[str, ...]:
    """Prune coarse states only when a complete sibling refinement cover exists.

    Returned identifiers are the candidates retained after pruning. This
    deliberately does not prune a broad state merely because one narrower
    state simulates its continuation.
    """
    ids = tuple(candidates)
    removed = set()
    for coarse_id in ids:
        coarse = candidates[coarse_id]
        groups: dict[tuple, list[EvidenceState]] = {}
        for candidate_id in ids:
            if candidate_id == coarse_id:
                continue
            child = candidates[candidate_id]
            if child.last_action_id is None or child.parent_state_snapshot is None:
                continue
            group_key = (_state_key(child.parent_state_snapshot), child.last_action_id)
            groups.setdefault(group_key, []).append(child)
        if any(_group_forms_complete_refinement_cover(group, coarse, contracts,
                                                      oracle, budget)
               for group in groups.values()):
            removed.add(coarse_id)
    return tuple(candidate_id for candidate_id in ids if candidate_id not in removed)


def make_fixture() -> tuple[WorldOracle, dict[str, ActionContract], EvidenceState, ResourceBudget]:
    safe = "safe_low"
    unsafe = "unsafe_high"

    def spec(
        action_id: str,
        semantic_key: str,
        applicable: WorldSet,
        labels: Mapping[str, str],
        required: FrozenSet[str],
        evidence: FrozenSet[str],
        ru: float,
        workspace: float,
        overlap: float,
        discharge: Mapping[str, FrozenSet[str]],
        gained: Mapping[str, FrozenSet[str]],
        retained: Mapping[str, float],
        required_obligations: FrozenSet[str] = frozenset(),
    ) -> ActionSemantics:
        return ActionSemantics(
            action_id, semantic_key, applicable, labels, required, required_obligations,
            evidence, frozenset(), ru, workspace, overlap,
            discharge, gained, retained,
            {label: f"{action_id}:{label}:finite-oracle-proof" for label in set(labels.values())},
        )

    both = frozenset({safe, unsafe})
    screen_fine = spec(
        "screen_fine", "measure-operating-state", both,
        {safe: "safe_observed", unsafe: "unsafe_observed"},
        frozenset({"mesh_ready"}), frozenset({"scenario_measurement"}),
        1.0, 0.25, 0.05,
        {"safe_observed": frozenset({"screen_pending"}),
         "unsafe_observed": frozenset({"screen_pending"})},
        {"safe_observed": frozenset({"screen_done", "primal_dual_ready"}),
         "unsafe_observed": frozenset({"screen_done", "primal_dual_ready"})},
        {"safe_observed": 0.10, "unsafe_observed": 0.10},
        required_obligations=frozenset({"screen_pending"}),
    )
    screen_coarse = spec(
        "screen_coarse", "measure-operating-state", both,
        {safe: "ambiguous", unsafe: "ambiguous"},
        frozenset({"mesh_ready"}), frozenset({"scenario_measurement"}),
        1.0, 0.25, 0.05,
        {"ambiguous": frozenset({"screen_pending"})},
        {"ambiguous": frozenset({"screen_done", "primal_dual_ready"})},
        {"ambiguous": 0.10},
        required_obligations=frozenset({"screen_pending"}),
    )
    cert_safe = spec(
        "cert_safe", "certified-qoi-enclosure", frozenset({safe}),
        {safe: "pass"}, frozenset({"primal_dual_ready"}),
        frozenset({"deterministic_qoi_enclosure"}), 2.0, 0.70, 0.10,
        {"pass": frozenset({"qoi_bound"})},
        {"pass": frozenset({"certificate_present"})}, {"pass": 0.20},
    )
    cert_full = spec(
        "cert_full", "certified-qoi-enclosure", both,
        {safe: "pass", unsafe: "fail"}, frozenset({"primal_dual_ready"}),
        frozenset({"deterministic_qoi_enclosure"}), 2.0, 0.70, 0.10,
        {"pass": frozenset({"qoi_bound"}), "fail": frozenset({"qoi_bound"})},
        {"pass": frozenset({"certificate_present"}), "fail": frozenset({"certificate_present"})},
        {"pass": 0.20, "fail": 0.20},
    )
    check = spec(
        "check", "independent-certificate-check", both,
        {safe: "verified", unsafe: "verified"}, frozenset({"certificate_present"}),
        frozenset({"independent_certificate_verification"}), 1.0, 0.15, 0.05,
        {"verified": frozenset({"independent_check"})},
        {"verified": frozenset()}, {"verified": 0.02},
    )
    oracle = WorldOracle(
        specification_id="heat-qoi-benchmark-v0",
        model_id="linear-heat-model-v0",
        universe=both,
        decision_by_world={safe: "ACCEPT", unsafe: "REJECT"},
        actions={a.action_id: a for a in
                 (screen_fine, screen_coarse, cert_safe, cert_full, check)},
    )
    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    initial = EvidenceState(
        specification_id=oracle.specification_id,
        model_id=oracle.model_id,
        worlds=both,
        open_obligations=frozenset({"screen_pending", "qoi_bound", "independent_check"}),
        capabilities=frozenset({"mesh_ready"}),
        remaining_actions=frozenset(oracle.actions),
    )
    budget = ResourceBudget(ru_upper=5.0, peak_memory_gb_upper=2.0)
    return oracle, contracts, initial, budget


def make_refinement_candidates(
    oracle: WorldOracle,
    contracts: Mapping[str, ActionContract],
    initial: EvidenceState,
) -> dict[str, EvidenceState]:
    """Return fine-screen siblings plus a coarse-screen state, all from transitions."""
    fine = action_transitions(initial, contracts["screen_fine"], oracle)
    coarse = action_transitions(initial, contracts["screen_coarse"], oracle)
    fine_by_label = {t.outcome_label: t.state for t in fine}
    coarse_by_label = {t.outcome_label: t.state for t in coarse}
    return {
        "fine_safe": fine_by_label["safe_observed"],
        "fine_unsafe": fine_by_label["unsafe_observed"],
        "coarse_both": coarse_by_label["ambiguous"],
    }


class OutcomeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle, self.contracts, self.initial, _ = make_fixture()

    def test_reference_contracts_are_valid(self) -> None:
        for contract in self.contracts.values():
            verify_action_contract(self.oracle, contract)

    def test_wrong_scope_certificate_is_rejected(self) -> None:
        contract = self.contracts["cert_full"]
        cell = contract.outcomes[0]
        bad_cert = replace(cell.certificate, model_id="wrong-model")
        bad_cell = replace(cell, certificate=bad_cert)
        bad = replace(contract, outcomes=(bad_cell,) + contract.outcomes[1:])
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, bad)

    def test_missing_world_outcome_is_rejected(self) -> None:
        contract = self.contracts["cert_full"]
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, replace(contract, outcomes=contract.outcomes[:1]))

    def test_overlapping_outcome_cells_are_rejected(self) -> None:
        contract = self.contracts["cert_full"]
        first, second = contract.outcomes
        overlap = replace(second, worlds=first.worlds | second.worlds)
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, replace(contract, outcomes=(first, overlap)))

    def test_forged_obligation_discharge_is_rejected(self) -> None:
        contract = self.contracts["cert_full"]
        cell = contract.outcomes[0]
        fake_discharge = cell.discharged_obligations | {"independent_check"}
        bad_cell = replace(cell, discharged_obligations=fake_discharge)
        bad_cert = replace(cell.certificate, discharged_obligations=fake_discharge)
        bad_cell = replace(bad_cell, certificate=bad_cert)
        bad = replace(contract, outcomes=(bad_cell,) + contract.outcomes[1:])
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, bad)

    def test_understated_resource_upper_bound_is_rejected(self) -> None:
        contract = self.contracts["cert_full"]
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, replace(contract, ru_upper=0.5))

    def test_contract_must_not_understate_retained_memory(self) -> None:
        contract = self.contracts["cert_full"]
        cell = contract.outcomes[0]
        bad_cell = replace(cell, retained_output_gb_upper=0.0)
        bad_cert = replace(cell.certificate, retained_output_gb_upper=0.0)
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle, replace(contract, outcomes=(bad_cell,) + contract.outcomes[1:]))

    def test_certificate_must_cover_declared_cell_memory_bound(self) -> None:
        contract = self.contracts["cert_full"]
        cell = contract.outcomes[0]
        declared = replace(cell, retained_output_gb_upper=0.30)
        certificate = replace(cell.certificate, retained_output_gb_upper=0.20)
        bad_cell = replace(declared, certificate=certificate)
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle,
                                   replace(contract, outcomes=(bad_cell,) + contract.outcomes[1:]))

    def test_unknown_outcome_label_is_rejected_as_contract_error(self) -> None:
        contract = self.contracts["cert_full"]
        first = contract.outcomes[0]
        bad_cell = replace(first, label="invented-label")
        with self.assertRaises(ContractError):
            verify_action_contract(self.oracle,
                                   replace(contract, outcomes=(bad_cell,) + contract.outcomes[1:]))


class RefinementAndPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle, self.contracts, self.initial, self.budget = make_fixture()
        self.candidates = make_refinement_candidates(
            self.oracle, self.contracts, self.initial
        )

    def test_each_fine_outcome_is_a_local_refinement_of_coarse_state(self) -> None:
        coarse = self.candidates["coarse_both"]
        self.assertTrue(state_refines(self.candidates["fine_safe"], coarse,
                                      self.contracts, self.oracle))
        self.assertTrue(state_refines(self.candidates["fine_unsafe"], coarse,
                                      self.contracts, self.oracle))

    def test_reverse_refinement_is_rejected(self) -> None:
        self.assertFalse(state_refines(
            self.candidates["coarse_both"], self.candidates["fine_safe"],
            self.contracts, self.oracle,
        ))

    def test_single_narrow_state_cannot_prune_coarse_state(self) -> None:
        incomplete_cover = {
            "fine_safe": self.candidates["fine_safe"],
            "coarse_both": self.candidates["coarse_both"],
        }
        self.assertEqual(
            prune_by_refinement_cover(incomplete_cover, self.contracts,
                                      self.oracle, self.budget),
            ("fine_safe", "coarse_both"),
        )

    def test_complete_sibling_refinement_cover_prunes_coarse_state(self) -> None:
        retained = prune_by_refinement_cover(
            self.candidates, self.contracts, self.oracle, self.budget
        )
        self.assertEqual(retained, ("fine_safe", "fine_unsafe"))

    def test_root_action_policy_frontiers_match(self) -> None:
        # Compare complete policies from the same root, not isolated child
        # states. This checks the two root-action alternatives independently;
        # it does not yet exercise an integrated dominance-pruned root search.
        fine = enumerate_action_policy_summaries(
            self.initial, "screen_fine", self.contracts, self.oracle, self.budget
        )
        coarse = enumerate_action_policy_summaries(
            self.initial, "screen_coarse", self.contracts, self.oracle, self.budget
        )
        self.assertTrue(fine)
        self.assertTrue(coarse)
        fine_frontier = {(p.terminal_verdicts, p.additional_ru_upper,
                          p.peak_memory_gb_upper) for p in fine}
        coarse_frontier = {(p.terminal_verdicts, p.additional_ru_upper,
                           p.peak_memory_gb_upper) for p in coarse}
        self.assertEqual(fine_frontier, coarse_frontier)
        self.assertEqual(fine[0].terminal_verdicts, frozenset({"ACCEPT", "REJECT"}))
        self.assertAlmostEqual(fine[0].additional_ru_upper, 4.0)

    def test_every_branch_must_reach_a_supported_decision(self) -> None:
        # Without an action that can discharge the QoI-bound obligation,
        # no terminal decision can be returned.
        incomplete = replace(
            self.candidates["coarse_both"],
            remaining_actions=frozenset({"check"}),
        )
        self.assertEqual(enumerate_complete_policies(
            incomplete, self.contracts, self.oracle, self.budget
        ), ())

    def test_budget_respects_peak_memory_not_only_ru(self) -> None:
        refined = self.candidates["fine_safe"]
        too_small = ResourceBudget(ru_upper=10.0, peak_memory_gb_upper=0.80)
        self.assertEqual(enumerate_complete_policies(
            refined, self.contracts, self.oracle, too_small
        ), ())

    def test_coarse_outcome_cannot_map_across_two_finer_cells(self) -> None:
        # Left has one outcome cell spanning both worlds; right separates them.
        # Although both contracts are individually valid, the left transition
        # cannot be mapped to exactly one compatible right outcome region.
        worlds = frozenset({"w1", "w2"})
        coarse_spec = ActionSemantics(
            "coarse", "same-computation", worlds,
            {"w1": "result", "w2": "result"}, frozenset({"ready"}),
            frozenset(), frozenset({"evidence"}), frozenset(), 1.0, 0.1, 0.0,
            {"result": frozenset({"bound"})}, {"result": frozenset()},
            {"result": 0.0}, {"result": "coarse-proof"},
        )
        fine_spec = ActionSemantics(
            "fine", "same-computation", worlds,
            {"w1": "alpha", "w2": "beta"}, frozenset({"ready"}),
            frozenset(), frozenset({"evidence"}), frozenset(), 1.0, 0.1, 0.0,
            {"alpha": frozenset({"bound"}), "beta": frozenset({"bound"})},
            {"alpha": frozenset(), "beta": frozenset()},
            {"alpha": 0.0, "beta": 0.0},
            {"alpha": "fine-proof-a", "beta": "fine-proof-b"},
        )
        oracle = WorldOracle("spec", "model", worlds,
                             {"w1": "ACCEPT", "w2": "REJECT"},
                             {"coarse": coarse_spec, "fine": fine_spec})
        contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
        left = EvidenceState("spec", "model", worlds, frozenset(),
                             frozenset({"ready"}), frozenset({"coarse"}))
        right = EvidenceState("spec", "model", worlds, frozenset(),
                              frozenset({"ready"}), frozenset({"fine"}))
        self.assertFalse(state_refines(left, right, contracts, oracle))

    def test_outcome_labels_may_differ_when_region_mapping_is_sound(self) -> None:
        # Different strings do not block a match when the fine observable
        # region is contained in exactly one coarse region.
        original = self.oracle.actions["cert_safe"]
        renamed = replace(
            original,
            observable_label_by_world={"safe_low": "within_limit"},
            discharged_by_label={"within_limit": frozenset({"qoi_bound"})},
            capabilities_by_label={"within_limit": frozenset({"certificate_present"})},
            retained_output_gb_by_label={"within_limit": 0.20},
            proof_id_by_label={"within_limit": "cert_safe:within_limit:finite-oracle-proof"},
        )
        oracle = replace(self.oracle, actions={**self.oracle.actions, "cert_safe": renamed})
        contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
        candidates = make_refinement_candidates(oracle, contracts, self.initial)
        self.assertTrue(state_refines(candidates["fine_safe"], candidates["coarse_both"],
                                      contracts, oracle))

    def test_fabricated_narrow_state_without_transition_provenance_is_rejected(self) -> None:
        fabricated = replace(self.candidates["coarse_both"],
                             worlds=frozenset({"safe_low"}),
                             parent_state_snapshot=None,
                             last_action_id=None,
                             last_outcome_label=None)
        self.assertFalse(state_refines(fabricated, self.candidates["coarse_both"],
                                       self.contracts, self.oracle))

    def test_failure_contract_is_part_of_action_matching(self) -> None:
        # Two root actions have the same numerical/evidence semantic key but
        # different failure-handling contracts. The right action must not be
        # simulated by the left action merely because their labels match.
        worlds = frozenset({"a", "b"})
        left_spec = ActionSemantics(
            "left_action", "same-numerical-method", worlds,
            {"a": "done", "b": "done"}, frozenset({"ready"}),
            frozenset(), frozenset({"bound"}), frozenset({"fail-closed-inconclusive"}),
            1.0, 0.1, 0.0, {"done": frozenset({"bound_ok"})},
            {"done": frozenset()}, {"done": 0.0}, {"done": "left-proof"},
        )
        right_spec = replace(left_spec, action_id="right_action",
                             failure_semantics=frozenset({"silent-fallback"}),
                             proof_id_by_label={"done": "right-proof"})
        oracle = WorldOracle("spec", "model", worlds,
                             {"a": "ACCEPT", "b": "ACCEPT"},
                             {"left_action": left_spec, "right_action": right_spec})
        contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
        left_state = EvidenceState("spec", "model", worlds, frozenset({"bound_ok"}),
                                   frozenset({"ready"}), frozenset({"left_action"}))
        right_state = EvidenceState("spec", "model", worlds, frozenset({"bound_ok"}),
                                    frozenset({"ready"}), frozenset({"right_action"}))
        self.assertFalse(state_refines(left_state, right_state, contracts, oracle))

    def test_unresolved_state_at_search_horizon_is_not_a_refinement_proof(self) -> None:
        self.assertFalse(state_refines(
            self.candidates["fine_safe"], self.candidates["coarse_both"],
            self.contracts, self.oracle, depth_left=0,
        ))

    def test_exhaustive_three_world_partition_pairs_match_containment_oracle(self) -> None:
        # Enumerate all 3^3 label assignments for each side (729 partition
        # pairs). The relation must hold exactly when every left outcome cell
        # lies within one right outcome cell.
        from itertools import product as iter_product

        worlds = ("w1", "w2", "w3")
        assignments = list(iter_product(("A", "B", "C"), repeat=3))

        def make_action(action_id: str, labels: tuple[str, ...]) -> ActionSemantics:
            mapping = dict(zip(worlds, labels))
            unique = set(labels)
            return ActionSemantics(
                action_id=action_id,
                semantic_key="same-observation-computation",
                applicable_worlds=frozenset(worlds),
                observable_label_by_world=mapping,
                required_capabilities=frozenset({"ready"}),
                required_obligations=frozenset(),
                evidence_contract=frozenset({"partition_evidence"}),
                failure_semantics=frozenset(),
                ru_upper=1.0,
                workspace_gb_upper=0.1,
                overlap_gb_upper=0.0,
                discharged_by_label={label: frozenset({"obligation"}) for label in unique},
                capabilities_by_label={label: frozenset() for label in unique},
                retained_output_gb_by_label={label: 0.0 for label in unique},
                proof_id_by_label={label: f"{action_id}:{label}" for label in unique},
            )

        checked = 0
        for left_labels in assignments:
            for right_labels in assignments:
                left_regions = [
                    frozenset(worlds[i] for i, label in enumerate(left_labels) if label == block)
                    for block in set(left_labels)
                ]
                right_regions = [
                    frozenset(worlds[i] for i, label in enumerate(right_labels) if label == block)
                    for block in set(right_labels)
                ]
                expected = all(
                    any(left_region <= right_region for right_region in right_regions)
                    for left_region in left_regions
                )
                left_action = make_action("left_action", left_labels)
                right_action = make_action("right_action", right_labels)
                oracle = WorldOracle(
                    specification_id="partition-spec",
                    model_id="partition-model",
                    universe=frozenset(worlds),
                    decision_by_world={world: "ACCEPT" for world in worlds},
                    actions={"left_action": left_action, "right_action": right_action},
                )
                contracts = {k: build_action_contract(oracle, k) for k in oracle.actions}
                left_state = EvidenceState(
                    "partition-spec", "partition-model", frozenset(worlds),
                    frozenset({"obligation"}), frozenset({"ready"}),
                    frozenset({"left_action"}),
                )
                right_state = replace(left_state, remaining_actions=frozenset({"right_action"}))
                actual = state_refines(left_state, right_state, contracts, oracle)
                self.assertEqual(actual, expected, (left_labels, right_labels))
                checked += 1
        self.assertEqual(checked, 729)

    def test_branch_cost_uses_max_not_sum(self) -> None:
        policies = enumerate_action_policy_summaries(
            self.initial, "screen_coarse", self.contracts, self.oracle, self.budget
        )
        self.assertTrue(policies)
        # screen 1 + certificate 2 + one checker per mutually exclusive branch 1
        self.assertAlmostEqual(policies[0].additional_ru_upper, 4.0)
        self.assertEqual(policies[0].terminal_verdicts, frozenset({"ACCEPT", "REJECT"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
