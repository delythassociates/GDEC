"""Integrated DWAOP v0.2 AND-OR planner with multi-resource vectors and complete-cover pruning.

Research-only prototype extending v0.1 outcome-refinement semantics to:
1. Multi-dimensional resource vectors (ru_upper, cpu_ticks, energy_ticks, peak_memory_gb).
2. Explicit result and failure semantics (OutcomeKind) including model invalidation,
   stale evidence, and bounded retries.
3. Fail-closed 12-condition complete-cover pruning integrated into OR-node expansion.
4. Normalized canonical policy representation and Pareto frontier reduction.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
from itertools import product
from math import isfinite
import time
import tracemalloc
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple


WorldSet = FrozenSet[str]
_TOL = 1e-12


class ContractError(ValueError):
    """An action contract, resource bound, oracle, or outcome certificate is invalid."""


def _nonnegative(value: float, field_name: str) -> Fraction:
    """Convert a finite non-negative decimal resource input to exact rational units."""
    if isinstance(value, bool):
        raise ContractError(f"{field_name} must be numeric, not bool")
    if not isinstance(value, (int, float, Fraction)):
        raise ContractError(f"{field_name} must be numeric")
    if isinstance(value, float) and not isfinite(value):
        raise ContractError(f"{field_name} must be finite and non-negative")
    try:
        exact = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as exc:
        raise ContractError(f"{field_name} must be a finite numeric value") from exc
    if exact < 0:
        raise ContractError(f"{field_name} must be finite and non-negative")
    return exact


class OutcomeKind(str, Enum):
    """Explicit result and failure semantics for action outcomes."""

    SUCCESS = "SUCCESS"
    INCONCLUSIVE = "INCONCLUSIVE"
    NUMERICAL_BREAKDOWN = "NUMERICAL_BREAKDOWN"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    BACKEND_FAILURE = "BACKEND_FAILURE"
    MODEL_INVALIDATED = "MODEL_INVALIDATED"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    BOUNDED_RETRY = "BOUNDED_RETRY"
    UNRECOVERABLE_REFUSAL = "UNRECOVERABLE_REFUSAL"


FAILURE_OR_INCONCLUSIVE_KINDS: FrozenSet[OutcomeKind] = frozenset({
    OutcomeKind.NUMERICAL_BREAKDOWN,
    OutcomeKind.TIMEOUT,
    OutcomeKind.RESOURCE_EXHAUSTION,
    OutcomeKind.BACKEND_FAILURE,
    OutcomeKind.UNRECOVERABLE_REFUSAL,
    OutcomeKind.INCONCLUSIVE,
    OutcomeKind.MODEL_INVALIDATED,
    OutcomeKind.STALE_EVIDENCE,
})


@dataclass(frozen=True)
class ResourceVector:
    """Multi-dimensional resource ledger / upper bound."""

    ru_upper: float = 0.0
    cpu_ticks: float = 0.0
    energy_ticks: float = 0.0
    peak_memory_gb: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "ru_upper", _nonnegative(self.ru_upper, "ru_upper"))
        object.__setattr__(self, "cpu_ticks", _nonnegative(self.cpu_ticks, "cpu_ticks"))
        object.__setattr__(self, "energy_ticks", _nonnegative(self.energy_ticks, "energy_ticks"))
        object.__setattr__(self, "peak_memory_gb", _nonnegative(self.peak_memory_gb, "peak_memory_gb"))

    def add_sequential(
        self,
        other: "ResourceVector",
        peak_memory_override: Optional[float] = None,
    ) -> "ResourceVector":
        """Accumulate additive costs sequentially and take high-water peak memory."""
        peak = max(self.peak_memory_gb, other.peak_memory_gb)
        if peak_memory_override is not None:
            _nonnegative(peak_memory_override, "peak_memory_override")
            peak = max(peak, peak_memory_override)
        return ResourceVector(
            ru_upper=self.ru_upper + other.ru_upper,
            cpu_ticks=self.cpu_ticks + other.cpu_ticks,
            energy_ticks=self.energy_ticks + other.energy_ticks,
            peak_memory_gb=peak,
        )

    def branch_max(self, other: "ResourceVector") -> "ResourceVector":
        """Worst-case aggregation across mutually exclusive outcome branches."""
        return ResourceVector(
            ru_upper=max(self.ru_upper, other.ru_upper),
            cpu_ticks=max(self.cpu_ticks, other.cpu_ticks),
            energy_ticks=max(self.energy_ticks, other.energy_ticks),
            peak_memory_gb=max(self.peak_memory_gb, other.peak_memory_gb),
        )

    @classmethod
    def max_across(cls, vectors: Sequence["ResourceVector"]) -> "ResourceVector":
        """Component-wise maximum over a non-empty sequence of ResourceVectors."""
        if not vectors:
            return cls()
        return cls(
            ru_upper=max(v.ru_upper for v in vectors),
            cpu_ticks=max(v.cpu_ticks for v in vectors),
            energy_ticks=max(v.energy_ticks for v in vectors),
            peak_memory_gb=max(v.peak_memory_gb for v in vectors),
        )

    def dominates_or_equal(self, other: "ResourceVector", tol: float = 0.0) -> bool:
        """True if every component is <= the other vector plus an exact tolerance."""
        tol = _nonnegative(tol, "dominance tolerance")
        return (
            self.ru_upper <= other.ru_upper + tol
            and self.cpu_ticks <= other.cpu_ticks + tol
            and self.energy_ticks <= other.energy_ticks + tol
            and self.peak_memory_gb <= other.peak_memory_gb + tol
        )

    def strictly_dominates(self, other: "ResourceVector", tol: float = 0.0) -> bool:
        """True if dominates_or_equal and strictly smaller in at least one component."""
        tol = _nonnegative(tol, "dominance tolerance")
        if not self.dominates_or_equal(other, tol=tol):
            return False
        return (
            self.ru_upper < other.ru_upper - tol
            or self.cpu_ticks < other.cpu_ticks - tol
            or self.energy_ticks < other.energy_ticks - tol
            or self.peak_memory_gb < other.peak_memory_gb - tol
        )

    def exact_key(self) -> Tuple[Fraction, Fraction, Fraction, Fraction]:
        """Exact resource tuple for proof-relevant identity and deduplication."""
        return (self.ru_upper, self.cpu_ticks, self.energy_ticks, self.peak_memory_gb)

    def rounded_key(self, digits: int = 12) -> Tuple[float, float, float, float]:
        return (
            round(self.ru_upper, digits),
            round(self.cpu_ticks, digits),
            round(self.energy_ticks, digits),
            round(self.peak_memory_gb, digits),
        )


@dataclass(frozen=True)
class ResourceBudget:
    """Hard multi-resource budget constraints."""

    ru_upper: float
    cpu_ticks: float
    energy_ticks: float
    peak_memory_gb: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "ru_upper", _nonnegative(self.ru_upper, "budget.ru_upper"))
        object.__setattr__(self, "cpu_ticks", _nonnegative(self.cpu_ticks, "budget.cpu_ticks"))
        object.__setattr__(self, "energy_ticks", _nonnegative(self.energy_ticks, "budget.energy_ticks"))
        object.__setattr__(self, "peak_memory_gb", _nonnegative(self.peak_memory_gb, "budget.peak_memory_gb"))

    def allows(self, vec: ResourceVector, tol: float = 0.0) -> bool:
        tol = _nonnegative(tol, "budget tolerance")
        return (
            vec.ru_upper <= self.ru_upper + tol
            and vec.cpu_ticks <= self.cpu_ticks + tol
            and vec.energy_ticks <= self.energy_ticks + tol
            and vec.peak_memory_gb <= self.peak_memory_gb + tol
        )


def validate_resource_budget(budget: ResourceBudget) -> None:
    _nonnegative(budget.ru_upper, "budget.ru_upper")
    _nonnegative(budget.cpu_ticks, "budget.cpu_ticks")
    _nonnegative(budget.energy_ticks, "budget.energy_ticks")
    _nonnegative(budget.peak_memory_gb, "budget.peak_memory_gb")


@dataclass(frozen=True)
class ActionSemantics:
    """Trusted finite semantics used by the reference oracle."""

    action_id: str
    semantic_key: str
    applicable_worlds: WorldSet
    observable_label_by_world: Mapping[str, str]
    required_capabilities: FrozenSet[str]
    required_obligations: FrozenSet[str]
    evidence_contract: FrozenSet[str]
    failure_semantics: FrozenSet[str]
    ru_upper: float
    cpu_ticks: float
    energy_ticks: float
    workspace_gb_upper: float
    overlap_gb_upper: float
    outcome_kind_by_label: Mapping[str, OutcomeKind]
    discharged_by_label: Mapping[str, FrozenSet[str]]
    capabilities_by_label: Mapping[str, FrozenSet[str]]
    retained_output_gb_by_label: Mapping[str, float]
    released_memory_gb_by_label: Mapping[str, float]
    invalidates_model_by_label: Mapping[str, bool]
    stale_evidence_by_label: Mapping[str, bool]
    retry_cost_by_label: Mapping[str, int]
    proof_id_by_label: Mapping[str, str]


@dataclass(frozen=True)
class WorldOracle:
    """Finite possible-world oracle for DWAOP v0.2."""

    specification_id: str
    model_id: str
    assurance_scope: str
    universe: WorldSet
    decision_by_world: Mapping[str, str]
    actions: Mapping[str, ActionSemantics]
    initial_obligations: FrozenSet[str] = frozenset()
    initial_capabilities: FrozenSet[str] = frozenset()
    initial_retries: int = 0
    allow_clairvoyant_world_branching: bool = False


@dataclass(frozen=True)
class OutcomeCertificate:
    """Certificate backing a single observable outcome cell."""

    specification_id: str
    model_id: str
    assurance_scope: str
    action_id: str
    outcome_label: str
    kind: OutcomeKind
    worlds: WorldSet
    discharged_obligations: FrozenSet[str]
    gained_capabilities: FrozenSet[str]
    retained_output_gb_upper: float
    released_memory_gb: float
    invalidates_model: bool
    stale_evidence: bool
    retry_cost: int
    proof_id: str


@dataclass(frozen=True)
class OutcomeCell:
    """One observable outcome cell of an ActionContract."""

    label: str
    kind: OutcomeKind
    worlds: WorldSet
    discharged_obligations: FrozenSet[str]
    gained_capabilities: FrozenSet[str]
    retained_output_gb_upper: float
    released_memory_gb: float
    invalidates_model: bool
    stale_evidence: bool
    retry_cost: int
    certificate: OutcomeCertificate


@dataclass(frozen=True)
class ActionContract:
    """Verified finite action contract."""

    action_id: str
    semantic_key: str
    specification_id: str
    model_id: str
    assurance_scope: str
    applicable_worlds: WorldSet
    required_capabilities: FrozenSet[str]
    required_obligations: FrozenSet[str]
    evidence_contract: FrozenSet[str]
    failure_semantics: FrozenSet[str]
    ru_upper: float
    cpu_ticks: float
    energy_ticks: float
    workspace_gb_upper: float
    overlap_gb_upper: float
    outcomes: Tuple[OutcomeCell, ...]

    def __post_init__(self) -> None:
        for field_name in ("ru_upper", "cpu_ticks", "energy_ticks", "workspace_gb_upper", "overlap_gb_upper"):
            object.__setattr__(self, field_name, _nonnegative(getattr(self, field_name), f"contract.{field_name}"))


@dataclass(frozen=True)
class EvidenceState:
    """Search state tracking worlds, obligations, capabilities, validity, and provenance."""

    specification_id: str
    model_id: str
    assurance_scope: str
    worlds: WorldSet
    open_obligations: FrozenSet[str]
    capabilities: FrozenSet[str]
    remaining_actions: FrozenSet[str]
    remaining_retries: int = 0
    model_valid: bool = True
    evidence_stale: bool = False
    resource_spent: ResourceVector = ResourceVector()
    resident_memory_gb: float = 0.0
    parent_state_snapshot: Optional["EvidenceState"] = None
    last_action_id: Optional[str] = None
    last_outcome_label: Optional[str] = None
    last_outcome_kind: Optional[OutcomeKind] = None
    provenance_depth: int = 0


@dataclass(frozen=True)
class StateTransition:
    action_id: str
    outcome_label: str
    outcome_kind: OutcomeKind
    state: EvidenceState


@dataclass(frozen=True)
class NormalizedPolicy:
    """Canonical representation of a complete contingent policy."""

    world_verdict_map: Tuple[Tuple[str, str], ...]
    resource_vector: ResourceVector
    terminal_verdicts: FrozenSet[str]
    max_actions_on_path: int


@dataclass(frozen=True)
class SearchMetrics:
    states_expanded: int
    actions_considered: int
    complete_policies_enumerated: int
    dominance_checks: int
    successful_prunes: int
    rejected_prune_attempts: int
    dominance_check_time_sec: float
    total_runtime_sec: float
    peak_planner_memory_bytes: int


@dataclass(frozen=True)
class PlannerResult:
    complete_policies: Tuple[NormalizedPolicy, ...]
    pareto_frontier: Tuple[NormalizedPolicy, ...]
    metrics: SearchMetrics


def validate_oracle(oracle: WorldOracle) -> None:
    """Validate oracle invariants fail-closed."""
    if oracle.allow_clairvoyant_world_branching:
        raise ContractError("Clairvoyant world branching is forbidden")
    if not oracle.specification_id or not oracle.model_id or not oracle.assurance_scope:
        raise ContractError("Oracle specification/model/assurance_scope identity is required")
    if not oracle.universe:
        raise ContractError("Oracle universe must not be empty")
    if isinstance(oracle.initial_retries, bool) or oracle.initial_retries < 0:
        raise ContractError("Oracle initial_retries must be a non-negative integer")
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
        for mapping_name, mapping in (
            ("outcome_kind_by_label", spec.outcome_kind_by_label),
            ("discharged_by_label", spec.discharged_by_label),
            ("capabilities_by_label", spec.capabilities_by_label),
            ("retained_output_gb_by_label", spec.retained_output_gb_by_label),
            ("released_memory_gb_by_label", spec.released_memory_gb_by_label),
            ("invalidates_model_by_label", spec.invalidates_model_by_label),
            ("stale_evidence_by_label", spec.stale_evidence_by_label),
            ("retry_cost_by_label", spec.retry_cost_by_label),
            ("proof_id_by_label", spec.proof_id_by_label),
        ):
            if set(mapping) != labels:
                raise ContractError(f"{mapping_name} must cover exact labels for {action_id}")

        _nonnegative(spec.ru_upper, f"{action_id}.ru_upper")
        _nonnegative(spec.cpu_ticks, f"{action_id}.cpu_ticks")
        _nonnegative(spec.energy_ticks, f"{action_id}.energy_ticks")
        _nonnegative(spec.workspace_gb_upper, f"{action_id}.workspace_gb_upper")
        _nonnegative(spec.overlap_gb_upper, f"{action_id}.overlap_gb_upper")

        for label in labels:
            kind = spec.outcome_kind_by_label[label]
            if not isinstance(kind, OutcomeKind):
                raise ContractError(f"Invalid OutcomeKind for {action_id}/{label}")
            _nonnegative(
                spec.retained_output_gb_by_label[label],
                f"{action_id}.{label}.retained_output_gb_upper",
            )
            _nonnegative(
                spec.released_memory_gb_by_label[label],
                f"{action_id}.{label}.released_memory_gb",
            )
            rc = spec.retry_cost_by_label[label]
            if isinstance(rc, bool) or not isinstance(rc, int) or rc < 0:
                raise ContractError(f"Invalid retry_cost for {action_id}/{label}")
            if kind == OutcomeKind.BOUNDED_RETRY and rc < 1:
                raise ContractError(f"BOUNDED_RETRY outcome {action_id}/{label} must have retry_cost >= 1")
            if not spec.proof_id_by_label[label]:
                raise ContractError(f"Missing proof id for {action_id}/{label}")


def build_action_contract(oracle: WorldOracle, action_id: str) -> ActionContract:
    """Build a complete verified ActionContract from the trusted oracle semantics."""
    validate_oracle(oracle)
    spec = oracle.actions.get(action_id)
    if spec is None:
        raise ContractError(f"Unknown action {action_id}")

    cells: List[OutcomeCell] = []
    labels = sorted(set(spec.observable_label_by_world.values()))
    for label in labels:
        worlds = frozenset(
            w for w, obs in spec.observable_label_by_world.items() if obs == label
        )
        kind = spec.outcome_kind_by_label[label]
        discharged = spec.discharged_by_label[label]
        gained = spec.capabilities_by_label[label]
        retained = spec.retained_output_gb_by_label[label]
        released = spec.released_memory_gb_by_label[label]
        invalidates = spec.invalidates_model_by_label[label]
        stale = spec.stale_evidence_by_label[label]
        retry_cost = spec.retry_cost_by_label[label]
        proof_id = spec.proof_id_by_label[label]
        cert = OutcomeCertificate(
            specification_id=oracle.specification_id,
            model_id=oracle.model_id,
            assurance_scope=oracle.assurance_scope,
            action_id=action_id,
            outcome_label=label,
            kind=kind,
            worlds=worlds,
            discharged_obligations=discharged,
            gained_capabilities=gained,
            retained_output_gb_upper=retained,
            released_memory_gb=released,
            invalidates_model=invalidates,
            stale_evidence=stale,
            retry_cost=retry_cost,
            proof_id=proof_id,
        )
        cells.append(
            OutcomeCell(
                label=label,
                kind=kind,
                worlds=worlds,
                discharged_obligations=discharged,
                gained_capabilities=gained,
                retained_output_gb_upper=retained,
                released_memory_gb=released,
                invalidates_model=invalidates,
                stale_evidence=stale,
                retry_cost=retry_cost,
                certificate=cert,
            )
        )

    return ActionContract(
        action_id=spec.action_id,
        semantic_key=spec.semantic_key,
        specification_id=oracle.specification_id,
        model_id=oracle.model_id,
        assurance_scope=oracle.assurance_scope,
        applicable_worlds=spec.applicable_worlds,
        required_capabilities=spec.required_capabilities,
        required_obligations=spec.required_obligations,
        evidence_contract=spec.evidence_contract,
        failure_semantics=spec.failure_semantics,
        ru_upper=spec.ru_upper,
        cpu_ticks=spec.cpu_ticks,
        energy_ticks=spec.energy_ticks,
        workspace_gb_upper=spec.workspace_gb_upper,
        overlap_gb_upper=spec.overlap_gb_upper,
        outcomes=tuple(cells),
    )


def verify_action_contract(oracle: WorldOracle, contract: ActionContract) -> None:
    """Verify an ActionContract and all its OutcomeCertificates against the oracle."""
    validate_oracle(oracle)
    spec = oracle.actions.get(contract.action_id)
    if spec is None:
        raise ContractError(f"Unknown action {contract.action_id}")
    if contract.specification_id != oracle.specification_id:
        raise ContractError("Action contract has the wrong specification scope")
    if contract.model_id != oracle.model_id:
        raise ContractError("Action contract has the wrong model scope")
    if contract.assurance_scope != oracle.assurance_scope:
        raise ContractError("Action contract has the wrong assurance scope")
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

    _nonnegative(contract.ru_upper, f"{contract.action_id}.contract.ru_upper")
    _nonnegative(contract.cpu_ticks, f"{contract.action_id}.contract.cpu_ticks")
    _nonnegative(contract.energy_ticks, f"{contract.action_id}.contract.energy_ticks")
    _nonnegative(contract.workspace_gb_upper, f"{contract.action_id}.contract.workspace_gb_upper")
    _nonnegative(contract.overlap_gb_upper, f"{contract.action_id}.contract.overlap_gb_upper")
    if contract.ru_upper < _nonnegative(spec.ru_upper, "trusted.ru_upper"):
        raise ContractError("RU upper bound understates trusted action cost")
    if contract.cpu_ticks < _nonnegative(spec.cpu_ticks, "trusted.cpu_ticks"):
        raise ContractError("CPU ticks upper bound understates trusted action cost")
    if contract.energy_ticks < _nonnegative(spec.energy_ticks, "trusted.energy_ticks"):
        raise ContractError("Energy ticks upper bound understates trusted action cost")
    if contract.workspace_gb_upper < _nonnegative(spec.workspace_gb_upper, "trusted.workspace_gb_upper"):
        raise ContractError("Workspace upper bound understates trusted action cost")
    if contract.overlap_gb_upper < _nonnegative(spec.overlap_gb_upper, "trusted.overlap_gb_upper"):
        raise ContractError("Overlap upper bound understates trusted action cost")

    labels = [cell.label for cell in contract.outcomes]
    if not labels or any(not label for label in labels) or len(labels) != len(set(labels)):
        raise ContractError("Outcome labels must be non-empty and unique")

    expected_labels = {
        spec.observable_label_by_world[w] for w in contract.applicable_worlds
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
            w for w in contract.applicable_worlds
            if spec.observable_label_by_world[w] == cell.label
        )
        if cell.worlds != expected_worlds:
            raise ContractError(f"Outcome cell {cell.label} has incorrect world semantics")

        expected_kind = spec.outcome_kind_by_label[cell.label]
        expected_discharge = spec.discharged_by_label[cell.label]
        expected_caps = spec.capabilities_by_label[cell.label]
        expected_retained = spec.retained_output_gb_by_label[cell.label]
        expected_released = spec.released_memory_gb_by_label[cell.label]
        expected_invalidates = spec.invalidates_model_by_label[cell.label]
        expected_stale = spec.stale_evidence_by_label[cell.label]
        expected_retry_cost = spec.retry_cost_by_label[cell.label]
        expected_proof_id = spec.proof_id_by_label[cell.label]

        if cell.kind != expected_kind:
            raise ContractError(f"OutcomeKind mismatch in {cell.label}")
        if cell.discharged_obligations != expected_discharge:
            raise ContractError(f"Unjustified obligation discharge in {cell.label}")
        if cell.gained_capabilities != expected_caps:
            raise ContractError(f"Unjustified capability gain in {cell.label}")
        _nonnegative(cell.retained_output_gb_upper, f"{contract.action_id}.{cell.label}.retained")
        _nonnegative(cell.released_memory_gb, f"{contract.action_id}.{cell.label}.released")
        if cell.retained_output_gb_upper < expected_retained:
            raise ContractError(f"Retained-memory upper bound understates {cell.label}")
        if cell.released_memory_gb > expected_released:
            raise ContractError(f"Released-memory claim overstates {cell.label}")
        if cell.invalidates_model != expected_invalidates:
            raise ContractError(f"Model invalidation flag mismatch in {cell.label}")
        if cell.stale_evidence != expected_stale:
            raise ContractError(f"Stale evidence flag mismatch in {cell.label}")
        if cell.retry_cost != expected_retry_cost:
            raise ContractError(f"Retry cost mismatch in {cell.label}")

        if (cell.invalidates_model or cell.kind == OutcomeKind.MODEL_INVALIDATED) and cell.discharged_obligations:
            raise ContractError(f"Invalidated model outcome {cell.label} cannot discharge obligations")

        cert = cell.certificate
        _nonnegative(cert.retained_output_gb_upper, f"{contract.action_id}.{cell.label}.cert.retained")
        _nonnegative(cert.released_memory_gb, f"{contract.action_id}.{cell.label}.cert.released")
        if (
            cert.specification_id != oracle.specification_id
            or cert.model_id != oracle.model_id
            or cert.assurance_scope != oracle.assurance_scope
        ):
            raise ContractError(f"Certificate scope mismatch in {cell.label}")
        if cert.action_id != contract.action_id or cert.outcome_label != cell.label:
            raise ContractError(f"Certificate action/outcome identity mismatch in {cell.label}")
        if cert.kind != cell.kind:
            raise ContractError(f"Certificate OutcomeKind mismatch in {cell.label}")
        if cert.worlds != cell.worlds:
            raise ContractError(f"Certificate world set mismatch in {cell.label}")
        if cert.discharged_obligations != expected_discharge:
            raise ContractError(f"Certificate obligation claim mismatch in {cell.label}")
        if cert.gained_capabilities != expected_caps:
            raise ContractError(f"Certificate capability claim mismatch in {cell.label}")
        if cert.retained_output_gb_upper < expected_retained:
            raise ContractError(f"Certificate memory bound understates {cell.label}")
        if cert.retained_output_gb_upper < cell.retained_output_gb_upper:
            raise ContractError(f"Certificate memory bound does not cover cell claim in {cell.label}")
        if cert.released_memory_gb != cell.released_memory_gb:
            raise ContractError(f"Certificate released memory mismatch in {cell.label}")
        if cert.invalidates_model != cell.invalidates_model or cert.stale_evidence != cell.stale_evidence:
            raise ContractError(f"Certificate validity flags mismatch in {cell.label}")
        if cert.retry_cost != cell.retry_cost:
            raise ContractError(f"Certificate retry_cost mismatch in {cell.label}")
        if cert.proof_id != expected_proof_id:
            raise ContractError(f"Certificate proof ID mismatch in {cell.label}")

    if seen != set(contract.applicable_worlds):
        raise ContractError("Outcome cells do not exhaustively cover action applicability")


def _enabled(state: EvidenceState, contract: ActionContract, oracle: WorldOracle) -> bool:
    try:
        verify_action_contract(oracle, contract)
    except ContractError:
        return False
    if not (
        contract.action_id in state.remaining_actions
        and state.specification_id == contract.specification_id
        and state.model_id == contract.model_id
        and state.assurance_scope == contract.assurance_scope
        and state.worlds <= contract.applicable_worlds
        and contract.required_capabilities <= state.capabilities
        and contract.required_obligations <= state.open_obligations
    ):
        return False
    for cell in contract.outcomes:
        if not (state.worlds & cell.worlds):
            continue
        if cell.kind == OutcomeKind.BOUNDED_RETRY:
            needed = max(1, cell.retry_cost)
            if state.remaining_retries < needed:
                return False
    return True


def apply_action_outcome(
    state: EvidenceState,
    contract: ActionContract,
    oracle: WorldOracle,
) -> Tuple[StateTransition, ...]:
    """Compute all observable outcome transitions from `state` under `contract`."""
    if not _enabled(state, contract, oracle):
        return ()

    transitions: List[StateTransition] = []
    covered: set[str] = set()
    for cell in contract.outcomes:
        child_worlds = state.worlds & cell.worlds
        if not child_worlds:
            continue
        if covered & set(child_worlds):
            raise ContractError("Enabled action outcome cells overlap the current state")
        covered.update(child_worlds)

        resident_before = _nonnegative(state.resident_memory_gb, "state.resident_memory_gb")
        retained = _nonnegative(cell.retained_output_gb_upper, "outcome.retained_output_gb_upper")
        released = _nonnegative(cell.released_memory_gb, "outcome.released_memory_gb")
        during_peak = resident_before + contract.workspace_gb_upper + contract.overlap_gb_upper
        resident_after = max(Fraction(0), resident_before + retained - released)
        action_cost = ResourceVector(
            ru_upper=contract.ru_upper,
            cpu_ticks=contract.cpu_ticks,
            energy_ticks=contract.energy_ticks,
            peak_memory_gb=max(during_peak, resident_after),
        )
        new_resource_spent = state.resource_spent.add_sequential(
            action_cost,
            peak_memory_override=max(during_peak, resident_after),
        )

        next_model_valid = state.model_valid and not (
            cell.invalidates_model or cell.kind == OutcomeKind.MODEL_INVALIDATED
        )
        next_evidence_stale = state.evidence_stale or (
            cell.stale_evidence or cell.kind == OutcomeKind.STALE_EVIDENCE
        )

        if cell.kind == OutcomeKind.BOUNDED_RETRY:
            decrement = max(1, cell.retry_cost)
            next_retries = state.remaining_retries - decrement
            next_remaining_actions = state.remaining_actions
        else:
            next_retries = state.remaining_retries
            next_remaining_actions = state.remaining_actions - {contract.action_id}

        if next_model_valid and not next_evidence_stale and cell.kind not in FAILURE_OR_INCONCLUSIVE_KINDS:
            next_obligations = state.open_obligations - cell.discharged_obligations
        else:
            next_obligations = state.open_obligations

        child = EvidenceState(
            specification_id=state.specification_id,
            model_id=state.model_id,
            assurance_scope=state.assurance_scope,
            worlds=frozenset(child_worlds),
            open_obligations=next_obligations,
            capabilities=state.capabilities | cell.gained_capabilities,
            remaining_actions=next_remaining_actions,
            remaining_retries=next_retries,
            model_valid=next_model_valid,
            evidence_stale=next_evidence_stale,
            resource_spent=new_resource_spent,
            resident_memory_gb=resident_after,
            parent_state_snapshot=state,
            last_action_id=contract.action_id,
            last_outcome_label=cell.label,
            last_outcome_kind=cell.kind,
            provenance_depth=state.provenance_depth + 1,
        )
        transitions.append(StateTransition(contract.action_id, cell.label, cell.kind, child))

    if covered != set(state.worlds):
        raise ContractError("Action outcome cells fail to cover current possible worlds")
    return tuple(transitions)


def verify_state_provenance(
    state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
) -> bool:
    """Verify a state's ancestry through checked finite action transitions."""
    if (
        state.specification_id != oracle.specification_id
        or state.model_id != oracle.model_id
        or state.assurance_scope != oracle.assurance_scope
    ):
        return False
    if not state.worlds or not state.worlds <= oracle.universe:
        return False
    if state.parent_state_snapshot is None:
        return (
            state.worlds == oracle.universe
            and state.resource_spent == ResourceVector()
            and state.resident_memory_gb == 0.0
            and state.last_action_id is None
            and state.last_outcome_label is None
            and state.last_outcome_kind is None
            and state.provenance_depth == 0
        )
    if not state.last_action_id or not state.last_outcome_label or state.last_outcome_kind is None:
        return False
    parent = state.parent_state_snapshot
    if state.provenance_depth != parent.provenance_depth + 1:
        return False
    if not verify_state_provenance(parent, contracts, oracle):
        return False
    contract = contracts.get(state.last_action_id)
    if contract is None:
        return False
    return any(
        t.outcome_label == state.last_outcome_label
        and t.outcome_kind == state.last_outcome_kind
        and t.state == state
        for t in apply_action_outcome(parent, contract, oracle)
    )


def terminal_verdict(state: EvidenceState, oracle: WorldOracle) -> Optional[str]:
    """Return ACCEPT, REJECT, REFUSE, or None if non-terminal."""
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


def _action_matches_no_worse(left: ActionContract, right: ActionContract) -> bool:
    return (
        left.semantic_key == right.semantic_key
        and left.specification_id == right.specification_id
        and left.model_id == right.model_id
        and left.assurance_scope == right.assurance_scope
        and left.required_capabilities == right.required_capabilities
        and left.required_obligations == right.required_obligations
        and left.evidence_contract == right.evidence_contract
        and left.failure_semantics == right.failure_semantics
        and left.ru_upper <= right.ru_upper
        and left.cpu_ticks <= right.cpu_ticks
        and left.energy_ticks <= right.energy_ticks
        and left.workspace_gb_upper <= right.workspace_gb_upper
        and left.overlap_gb_upper <= right.overlap_gb_upper
    )


def is_local_refinement(
    fine_state: EvidenceState,
    coarse_state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    depth_left: int = 10,
) -> bool:
    """Recursive finite-horizon local simulation `fine_state <= coarse_state`."""
    if depth_left < 0:
        return False
    if not verify_state_provenance(fine_state, contracts, oracle):
        return False
    if not verify_state_provenance(coarse_state, contracts, oracle):
        return False
    if not (
        fine_state.specification_id == coarse_state.specification_id == oracle.specification_id
        and fine_state.model_id == coarse_state.model_id == oracle.model_id
        and fine_state.assurance_scope == coarse_state.assurance_scope == oracle.assurance_scope
        and fine_state.worlds <= coarse_state.worlds
        and fine_state.open_obligations <= coarse_state.open_obligations
        and coarse_state.capabilities <= fine_state.capabilities
        and fine_state.remaining_retries >= coarse_state.remaining_retries
        and (not coarse_state.model_valid or fine_state.model_valid)
        and (coarse_state.evidence_stale or not fine_state.evidence_stale)
        and fine_state.resource_spent.dominates_or_equal(coarse_state.resource_spent, tol=0.0)
        and fine_state.resident_memory_gb <= coarse_state.resident_memory_gb
    ):
        return False

    fine_term = terminal_verdict(fine_state, oracle)
    coarse_term = terminal_verdict(coarse_state, oracle)
    if coarse_term in {"ACCEPT", "REJECT"}:
        return fine_term == coarse_term
    if fine_term in {"ACCEPT", "REJECT"}:
        # fine_state stops immediately at ACCEPT/REJECT; it cannot simulate a coarse
        # continuation unless coarse_term is None and we don't know if coarse differs.
        return False
    if coarse_term == "REFUSE":
        if fine_term != "REFUSE":
            return False
        # Sticky refusal states stop expanding immediately, so leaf simulation suffices.
        coarse_sticky = (
            not coarse_state.model_valid
            or coarse_state.evidence_stale
            or coarse_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL
        )
        if coarse_sticky:
            return True
        if depth_left == 0:
            return True
        # Non-sticky REFUSE may continue expanding recovery actions in coarse_state;
        # verify every enabled coarse action can also be simulated by fine_state.
        coarse_enabled_check = [
            contracts[aid]
            for aid in sorted(coarse_state.remaining_actions)
            if aid in contracts and _enabled(coarse_state, contracts[aid], oracle)
        ]
        if not coarse_enabled_check:
            return True
    elif fine_term == "REFUSE":
        return False
    if depth_left == 0:
        return False

    coarse_enabled: List[ActionContract] = []
    for action_id in sorted(coarse_state.remaining_actions):
        contract = contracts.get(action_id)
        if contract is not None and _enabled(coarse_state, contract, oracle):
            coarse_enabled.append(contract)

    if not coarse_enabled:
        return False

    for right_action in coarse_enabled:
        matched = False
        for left_action_id in sorted(fine_state.remaining_actions):
            left_action = contracts.get(left_action_id)
            if left_action is None or not _enabled(fine_state, left_action, oracle):
                continue
            if not _action_matches_no_worse(left_action, right_action):
                continue

            left_transitions = apply_action_outcome(fine_state, left_action, oracle)
            right_transitions = apply_action_outcome(coarse_state, right_action, oracle)
            if not left_transitions or not right_transitions:
                continue

            mapping_valid = True
            for lt in left_transitions:
                compatible = [rt for rt in right_transitions if lt.state.worlds <= rt.state.worlds]
                if len(compatible) != 1:
                    mapping_valid = False
                    break
                if not is_local_refinement(
                    lt.state, compatible[0].state, contracts, oracle, depth_left - 1
                ):
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
        state.assurance_scope,
        tuple(sorted(state.worlds)),
        tuple(sorted(state.open_obligations)),
        tuple(sorted(state.capabilities)),
        tuple(sorted(state.remaining_actions)),
        state.remaining_retries,
        state.model_valid,
        state.evidence_stale,
        state.resource_spent.exact_key(),
        state.resident_memory_gb,
        state.provenance_depth,
    )


def _has_complete_policy_within_budget(
    state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
    depth_left: int,
) -> bool:
    if depth_left < 0 or not state.worlds:
        return False
    if not budget.allows(state.resource_spent):
        return False
    if terminal_verdict(state, oracle) is not None:
        return True
    if depth_left == 0:
        return False
    for action_id in sorted(state.remaining_actions):
        contract = contracts.get(action_id)
        if contract is None:
            continue
        transitions = apply_action_outcome(state, contract, oracle)
        if not transitions:
            continue
        if any(not budget.allows(t.state.resource_spent) for t in transitions):
            continue
        if all(
            _has_complete_policy_within_budget(t.state, contracts, oracle, budget, depth_left - 1)
            for t in transitions
        ):
            return True
    return False


def is_complete_refinement_cover(
    candidate_children: Sequence[EvidenceState],
    coarse_state: EvidenceState,
    contracts: Mapping[str, ActionContract],
    oracle: WorldOracle,
    budget: ResourceBudget,
    depth_left: int = 10,
) -> bool:
    """Fail-closed 12-condition check for complete-cover pruning."""
    validate_resource_budget(budget)
    if not candidate_children:
        return False

    first = candidate_children[0]
    parent = first.parent_state_snapshot
    fine_action_id = first.last_action_id
    if parent is None or not fine_action_id:
        return False
    if coarse_state.parent_state_snapshot is None or not coarse_state.last_action_id:
        return False

    # 1. Common canonical parent
    if _state_key(parent) != _state_key(coarse_state.parent_state_snapshot):
        return False
    if parent.worlds != coarse_state.worlds:
        return False

    # 2. Same specification_id, model_id, assurance_scope
    if not (
        parent.specification_id == coarse_state.specification_id == oracle.specification_id
        and parent.model_id == coarse_state.model_id == oracle.model_id
        and parent.assurance_scope == coarse_state.assurance_scope == oracle.assurance_scope
    ):
        return False

    # 6 & 12. Valid provenance & verified contracts
    if not verify_state_provenance(coarse_state, contracts, oracle):
        return False
    fine_contract = contracts.get(fine_action_id)
    coarse_contract = contracts.get(coarse_state.last_action_id)
    if fine_contract is None or coarse_contract is None:
        return False
    try:
        verify_action_contract(oracle, fine_contract)
        verify_action_contract(oracle, coarse_contract)
    except ContractError:
        return False

    # 8. Compatible action semantics and failure handling
    if (
        fine_contract.semantic_key != coarse_contract.semantic_key
        or fine_contract.failure_semantics != coarse_contract.failure_semantics
    ):
        return False

    if any(
        child.parent_state_snapshot is None
        or _state_key(child.parent_state_snapshot) != _state_key(parent)
        or child.last_action_id != fine_action_id
        or child.specification_id != oracle.specification_id
        or child.model_id != oracle.model_id
        or child.assurance_scope != oracle.assurance_scope
        for child in candidate_children
    ):
        return False

    # 3 & 12. Complete observable outcome set of a_+ (no omitted branch)
    expected_transitions = apply_action_outcome(parent, fine_contract, oracle)
    if not expected_transitions:
        return False
    if len(candidate_children) != len(expected_transitions):
        return False
    expected_states = {t.state for t in expected_transitions}
    if set(candidate_children) != expected_states:
        return False

    # 4, 5, 6, 7, 9, 10, 11. Disjointness, exact union coverage, provenance, recursive simulation,
    # monotonic obligations/capabilities, validity, and resource feasibility
    seen_worlds: set[str] = set()
    for child in candidate_children:
        if not verify_state_provenance(child, contracts, oracle):
            return False
        if seen_worlds & set(child.worlds):
            return False
        seen_worlds.update(child.worlds)
        if not is_local_refinement(child, coarse_state, contracts, oracle, depth_left):
            return False

    if seen_worlds != set(coarse_state.worlds):
        return False

    # Budget feasibility across all refined siblings
    for child in candidate_children:
        if not _has_complete_policy_within_budget(child, contracts, oracle, budget, depth_left):
            return False
    return True


def _verdict_no_worse(left: str, right: str) -> bool:
    if left == right:
        return True
    return left in {"ACCEPT", "REJECT"} and right == "REFUSE"


def _policy_dominates(left: NormalizedPolicy, right: NormalizedPolicy) -> bool:
    if len(left.world_verdict_map) != len(right.world_verdict_map):
        return False
    for (lw, lv), (rw, rv) in zip(left.world_verdict_map, right.world_verdict_map):
        if lw != rw or not _verdict_no_worse(lv, rv):
            return False
    if not left.resource_vector.dominates_or_equal(right.resource_vector):
        return False
    return (
        left.world_verdict_map != right.world_verdict_map
        or left.resource_vector.strictly_dominates(right.resource_vector)
    )


def _canonical_dedup(policies: Sequence[NormalizedPolicy]) -> Tuple[NormalizedPolicy, ...]:
    by_key: Dict[tuple, NormalizedPolicy] = {}
    for p in policies:
        key = (
            p.world_verdict_map,
            p.terminal_verdicts,
            p.resource_vector.exact_key(),
        )
        existing = by_key.get(key)
        if existing is None or p.max_actions_on_path < existing.max_actions_on_path:
            by_key[key] = p
    return tuple(
        sorted(
            by_key.values(),
            key=lambda p: (
                p.world_verdict_map,
                p.resource_vector.exact_key(),
                p.max_actions_on_path,
            ),
        )
    )


def pareto_reduce(policies: Sequence[NormalizedPolicy]) -> Tuple[NormalizedPolicy, ...]:
    """Normalize, deduplicate, and return the non-dominated Pareto frontier."""
    unique = _canonical_dedup(policies)
    frontier: List[NormalizedPolicy] = []
    for candidate in unique:
        if not any(
            other is not candidate and _policy_dominates(other, candidate)
            for other in unique
        ):
            frontier.append(candidate)
    return tuple(frontier)


def make_initial_state(oracle: WorldOracle) -> EvidenceState:
    """Construct the canonical root EvidenceState for an oracle."""
    validate_oracle(oracle)
    return EvidenceState(
        specification_id=oracle.specification_id,
        model_id=oracle.model_id,
        assurance_scope=oracle.assurance_scope,
        worlds=oracle.universe,
        open_obligations=oracle.initial_obligations,
        capabilities=oracle.initial_capabilities,
        remaining_actions=frozenset(oracle.actions),
        remaining_retries=oracle.initial_retries,
        model_valid=True,
        evidence_stale=False,
        resource_spent=ResourceVector(),
        resident_memory_gb=0.0,
        parent_state_snapshot=None,
        last_action_id=None,
        last_outcome_label=None,
        last_outcome_kind=None,
        provenance_depth=0,
    )


def plan_policies(
    oracle: WorldOracle,
    budget: ResourceBudget,
    max_horizon: int = 10,
    prune: bool = True,
    initial_state: Optional[EvidenceState] = None,
) -> PlannerResult:
    """Integrated AND-OR planner with optional complete-cover pruning."""
    validate_oracle(oracle)
    validate_resource_budget(budget)

    started_tracing = False
    if not tracemalloc.is_tracing():
        tracemalloc.start()
        started_tracing = True
    t_start = time.perf_counter()

    contracts = {aid: build_action_contract(oracle, aid) for aid in oracle.actions}
    root = initial_state if initial_state is not None else make_initial_state(oracle)

    stats = {
        "states_expanded": 0,
        "actions_considered": 0,
        "complete_policies_enumerated": 0,
        "dominance_checks": 0,
        "successful_prunes": 0,
        "rejected_prune_attempts": 0,
        "dominance_check_time_sec": 0.0,
    }

    def _search(state: EvidenceState, depth_left: int) -> Tuple[NormalizedPolicy, ...]:
        if depth_left < 0 or not state.worlds:
            return ()
        if not budget.allows(state.resource_spent):
            return ()

        stats["states_expanded"] += 1
        verdict = terminal_verdict(state, oracle)
        complete_here: List[NormalizedPolicy] = []
        if verdict in {"ACCEPT", "REJECT"}:
            leaf = NormalizedPolicy(
                world_verdict_map=tuple((w, verdict) for w in sorted(state.worlds)),
                resource_vector=ResourceVector(
                    ru_upper=0.0,
                    cpu_ticks=0.0,
                    energy_ticks=0.0,
                    peak_memory_gb=state.resource_spent.peak_memory_gb,
                ),
                terminal_verdicts=frozenset({verdict}),
                max_actions_on_path=0,
            )
            stats["complete_policies_enumerated"] += 1
            return (leaf,)
        if verdict == "REFUSE":
            leaf = NormalizedPolicy(
                world_verdict_map=tuple((w, "REFUSE") for w in sorted(state.worlds)),
                resource_vector=ResourceVector(
                    ru_upper=0.0,
                    cpu_ticks=0.0,
                    energy_ticks=0.0,
                    peak_memory_gb=state.resource_spent.peak_memory_gb,
                ),
                terminal_verdicts=frozenset({"REFUSE"}),
                max_actions_on_path=0,
            )
            stats["complete_policies_enumerated"] += 1
            if (
                not state.model_valid
                or state.evidence_stale
                or state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL
            ):
                return (leaf,)
            complete_here.append(leaf)

        if depth_left == 0:
            return pareto_reduce(complete_here)

        candidate_groups: List[Tuple[ActionContract, Tuple[StateTransition, ...]]] = []
        for action_id in sorted(state.remaining_actions):
            contract = contracts.get(action_id)
            if contract is None:
                continue
            transitions = apply_action_outcome(state, contract, oracle)
            if not transitions:
                continue
            if any(not budget.allows(t.state.resource_spent) for t in transitions):
                continue
            candidate_groups.append((contract, transitions))

        if prune:
            # Expand finer-grained (more outcomes) and cheaper actions first so
            # complete-cover pruning can eliminate dominated coarser actions.
            candidate_groups.sort(
                key=lambda item: (
                    -len(item[1]),
                    item[0].ru_upper,
                    item[0].cpu_ticks,
                    item[0].energy_ticks,
                    item[0].workspace_gb_upper,
                    item[0].action_id,
                )
            )

        expanded_covers: List[Tuple[ActionContract, Tuple[EvidenceState, ...]]] = []

        for contract, transitions in candidate_groups:
            stats["actions_considered"] += 1

            if prune and expanded_covers:
                pruned = False
                for fine_contract, fine_children in expanded_covers:
                    if fine_contract.semantic_key != contract.semantic_key:
                        continue
                    t0 = time.perf_counter()
                    stats["dominance_checks"] += 1
                    covers_all = all(
                        is_complete_refinement_cover(
                            fine_children,
                            t.state,
                            contracts,
                            oracle,
                            budget,
                            depth_left - 1,
                        )
                        for t in transitions
                    )
                    stats["dominance_check_time_sec"] += time.perf_counter() - t0
                    if covers_all:
                        stats["successful_prunes"] += 1
                        pruned = True
                        break
                    else:
                        stats["rejected_prune_attempts"] += 1
                if pruned:
                    continue

            branch_policies = [
                _search(t.state, depth_left - 1) for t in transitions
            ]
            if not branch_policies or any(not bp for bp in branch_policies):
                continue

            action_policies: List[NormalizedPolicy] = []
            for selected in product(*branch_policies):
                child_max = ResourceVector.max_across([p.resource_vector for p in selected])
                additional_vec = ResourceVector(
                    ru_upper=contract.ru_upper + child_max.ru_upper,
                    cpu_ticks=contract.cpu_ticks + child_max.cpu_ticks,
                    energy_ticks=contract.energy_ticks + child_max.energy_ticks,
                    peak_memory_gb=max(state.resource_spent.peak_memory_gb, child_max.peak_memory_gb),
                )
                total_vec = ResourceVector(
                    ru_upper=state.resource_spent.ru_upper + additional_vec.ru_upper,
                    cpu_ticks=state.resource_spent.cpu_ticks + additional_vec.cpu_ticks,
                    energy_ticks=state.resource_spent.energy_ticks + additional_vec.energy_ticks,
                    peak_memory_gb=additional_vec.peak_memory_gb,
                )
                if not budget.allows(total_vec):
                    continue

                merged_map = tuple(
                    sorted(pair for p in selected for pair in p.world_verdict_map)
                )
                policy = NormalizedPolicy(
                    world_verdict_map=merged_map,
                    resource_vector=additional_vec,
                    terminal_verdicts=frozenset().union(*(p.terminal_verdicts for p in selected)),
                    max_actions_on_path=1 + max(p.max_actions_on_path for p in selected),
                )
                stats["complete_policies_enumerated"] += 1
                action_policies.append(policy)

            if action_policies:
                complete_here.extend(action_policies)
                if prune:
                    expanded_covers.append((contract, tuple(t.state for t in transitions)))

        return pareto_reduce(complete_here)

    all_policies = _search(root, max_horizon)
    frontier = pareto_reduce(all_policies)
    total_time = time.perf_counter() - t_start
    _, peak_bytes = tracemalloc.get_traced_memory()
    if started_tracing:
        tracemalloc.stop()

    metrics = SearchMetrics(
        states_expanded=stats["states_expanded"],
        actions_considered=stats["actions_considered"],
        complete_policies_enumerated=stats["complete_policies_enumerated"],
        dominance_checks=stats["dominance_checks"],
        successful_prunes=stats["successful_prunes"],
        rejected_prune_attempts=stats["rejected_prune_attempts"],
        dominance_check_time_sec=stats["dominance_check_time_sec"],
        total_runtime_sec=total_time,
        peak_planner_memory_bytes=peak_bytes,
    )
    return PlannerResult(
        complete_policies=all_policies,
        pareto_frontier=frontier,
        metrics=metrics,
    )
