"""
Independent Verification Module for GDEC Engineering Evidence Records (WP3 Stage 3).

Validates schema, recomputes canonical SHA-256 hashes, verifies parent/artifact
provenance, re-evaluates deterministic refusal rules, checks estimator classifications,
units, dependency versions, and scientific metadata consistency without running
the solver by default.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import ValidationError

from gdec.dse.evidence_graph import (
    SUPPORTED_QOI_UNITS,
    EngineeringEvidenceRecord,
    EstimatorClassification,
    compute_canonical_hash,
)
from gdec.dse.refusal import RefusalContext, RefusalEngine


MANDATORY_DEPENDENCIES = ("numpy", "scipy", "scikit-fem")


@dataclass(frozen=True)
class VerificationDiagnostic:
    code: str
    message: str
    field: Optional[str] = None


@dataclass(frozen=True)
class VerificationReport:
    valid: bool
    record_id: Optional[str]
    schema_version: Optional[str]
    refused: Optional[bool]
    diagnostic_codes: List[str]
    diagnostics: List[VerificationDiagnostic] = field(default_factory=list)
    recomputed_hash: Optional[str] = None
    rerun_qoi_value: Optional[float] = None


def verify_evidence_payload(
    payload: Dict[str, Any],
    *,
    rerun: bool = False,
    reexec_fn: Optional[Callable[[EngineeringEvidenceRecord], float]] = None,
    rtol: float = 1e-6,
) -> VerificationReport:
    """Independently verify a parsed Engineering Evidence Record dictionary."""
    diags: List[VerificationDiagnostic] = []

    if not isinstance(payload, dict):
        diags.append(VerificationDiagnostic("VER-SCHEMA-INVALID", "Payload must be a JSON object."))
        return VerificationReport(False, None, None, None, [d.code for d in diags], diags)

    # 1. Schema validation
    try:
        record = EngineeringEvidenceRecord.model_validate(payload)
    except ValidationError as exc:
        diags.append(VerificationDiagnostic("VER-SCHEMA-INVALID", f"Schema validation failed: {exc}"))
        return VerificationReport(
            False,
            payload.get("record_id"),
            payload.get("schema_version"),
            payload.get("refused") if isinstance(payload.get("refused"), bool) else None,
            [d.code for d in diags],
            diags,
        )

    # 2. Canonical hash verification (use raw payload dict to detect extra/altered fields)
    try:
        recomputed = compute_canonical_hash(payload)
    except ValueError as exc:
        diags.append(VerificationDiagnostic("VER-NONFINITE", f"Non-finite value in payload: {exc}"))
        return VerificationReport(False, record.record_id, record.schema_version, record.refused, [d.code for d in diags], diags)
    if recomputed != record.canonical_result_hash:
        diags.append(
            VerificationDiagnostic(
                "VER-HASH-MISMATCH",
                f"Canonical result hash mismatch: expected {recomputed}, found {record.canonical_result_hash}.",
                field="canonical_result_hash",
            )
        )

    # 3. Finite numeric values
    if record.qoi_value is not None and not math.isfinite(record.qoi_value):
        diags.append(VerificationDiagnostic("VER-NONFINITE", "qoi_value is non-finite.", field="qoi_value"))
    if record.error_estimate is not None and not math.isfinite(record.error_estimate):
        diags.append(VerificationDiagnostic("VER-NONFINITE", "error_estimate is non-finite.", field="error_estimate"))
    if not math.isfinite(record.outcome_metrics.wall_time_sec):
        diags.append(VerificationDiagnostic("VER-NONFINITE", "wall_time_sec is non-finite.", field="outcome_metrics.wall_time_sec"))

    # 4. Provenance checks
    if len(record.parent_artifacts) == 0:
        diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", "parent_artifacts must not be empty.", field="parent_artifacts"))
    for p in record.parent_artifacts:
        if not all(c in "0123456789abcdef" for c in p.sha256_hash.lower()):
            diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", f"Invalid hex sha256 in parent '{p.artifact_id}'.", field="parent_artifacts"))
    for h_name, h_val in [("canonical_eir_hash", record.canonical_eir_hash), ("mesh_hash", record.mesh_hash)]:
        if not all(c in "0123456789abcdef" for c in h_val.lower()):
            diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", f"Invalid hex sha256 in {h_name}.", field=h_name))

    # 5. Estimator classification check
    if (
        "dwr" in record.estimator_identity.lower()
        and record.estimator_classification == EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND
    ):
        diags.append(
            VerificationDiagnostic(
                "VER-ESTIMATOR-CLASS-INVALID",
                "DWR estimator must not be classified as mathematically_established_bound.",
                field="estimator_classification",
            )
        )

    # 6. Units consistency
    if record.qoi_units not in SUPPORTED_QOI_UNITS:
        diags.append(
            VerificationDiagnostic(
                "VER-UNITS-INCONSISTENT",
                f"Unsupported qoi_units '{record.qoi_units}'.",
                field="qoi_units",
            )
        )
    if record.qoi_units == "mm" and "meters" in record.qoi_name.lower():
        diags.append(
            VerificationDiagnostic(
                "VER-UNITS-INCONSISTENT",
                "qoi_units is 'mm' while qoi_name specifies meters.",
                field="qoi_units",
            )
        )

    # 7. Mandatory dependencies
    for dep in MANDATORY_DEPENDENCIES:
        ver = record.dependency_versions.get(dep)
        if not ver or not str(ver).strip():
            diags.append(
                VerificationDiagnostic(
                    "VER-MISSING-DEPENDENCY",
                    f"Missing mandatory dependency version for '{dep}'.",
                    field="dependency_versions",
                )
            )

    # 8. Scientific metadata & required config key consistency (fail-closed)
    if record.outcome_metrics.final_dofs != record.dof_count:
        diags.append(
            VerificationDiagnostic(
                "VER-METADATA-INCONSISTENT",
                f"outcome_metrics.final_dofs ({record.outcome_metrics.final_dofs}) != dof_count ({record.dof_count}).",
                field="outcome_metrics.final_dofs",
            )
        )
    if record.outcome_metrics.estimator_value != record.error_estimate:
        diags.append(
            VerificationDiagnostic(
                "VER-METADATA-INCONSISTENT",
                f"outcome_metrics.estimator_value ({record.outcome_metrics.estimator_value}) != error_estimate ({record.error_estimate}).",
                field="outcome_metrics.estimator_value",
            )
        )
    expected_ar = record.problem_features.domain_width / record.problem_features.domain_height
    if not math.isclose(record.problem_features.aspect_ratio, expected_ar, rel_tol=1e-6, abs_tol=1e-9):
        diags.append(
            VerificationDiagnostic(
                "VER-METADATA-INCONSISTENT",
                f"problem_features.aspect_ratio ({record.problem_features.aspect_ratio}) != width/height ({expected_ar}).",
                field="problem_features.aspect_ratio",
            )
        )

    mesh_meta = record.mesh_metadata
    solver_cfg = record.solver_config
    res_cons = record.resource_consumption
    missing_cfg = [k for k in ("solver_converged", "problem_class", "qoi_boundary", "fixed_boundaries") if k not in solver_cfg]
    missing_mesh = [k for k in ("mesh_valid", "nelements") if k not in mesh_meta]
    missing_res = [k for k in ("budget_exhausted", "target_tolerance_met") if k not in res_cons]
    if missing_cfg or missing_mesh or missing_res:
        diags.append(
            VerificationDiagnostic(
                "VER-METADATA-INCONSISTENT",
                f"Missing required verification metadata keys: solver_config={missing_cfg}, mesh_metadata={missing_mesh}, resource_consumption={missing_res}.",
            )
        )
    elif len(solver_cfg["fixed_boundaries"]) != record.problem_features.num_fixed_boundaries:
        diags.append(
            VerificationDiagnostic(
                "VER-METADATA-INCONSISTENT",
                "solver_config.fixed_boundaries count does not match problem_features.num_fixed_boundaries.",
                field="solver_config.fixed_boundaries",
            )
        )

    # 9. Re-evaluate refusal rules independently (fail-closed defaults if keys missing)
    ctx = RefusalContext(
        budget_exhausted=bool(res_cons.get("budget_exhausted", True)),
        target_tolerance_met=bool(res_cons.get("target_tolerance_met", False)),
        estimator_identity=record.estimator_identity,
        estimator_classification=record.estimator_classification.value,
        problem_class=str(solver_cfg.get("problem_class", "")),
        reference_required=bool(solver_cfg.get("reference_required", False)),
        reference_adequate=None if record.effectivity_evidence == "NONE" else bool(
            isinstance(record.effectivity_evidence, dict) and record.effectivity_evidence.get("adequate", True)
        ),
        qoi_boundary=str(solver_cfg.get("qoi_boundary", "")),
        fixed_boundaries=list(solver_cfg.get("fixed_boundaries", [])),
        dof_count=record.dof_count,
        min_required_dofs=int(solver_cfg.get("min_required_dofs", 6)),
        solver_converged=bool(solver_cfg.get("solver_converged", False)),
        qoi_value=record.qoi_value,
        residual_norm=solver_cfg.get("residual_norm", 0.0),
        error_estimate=record.error_estimate,
        mesh_valid=bool(mesh_meta.get("mesh_valid", False)),
        mesh_element_count=int(mesh_meta.get("nelements", 0)),
        model_applicability_status=record.model_applicability_status,
        parent_artifacts=[p.model_dump() for p in record.parent_artifacts],
        canonical_eir_hash=record.canonical_eir_hash,
        mesh_hash=record.mesh_hash,
        mandatory_evidence_present=bool(solver_cfg.get("mandatory_evidence_present", False)),
        evidence_stale=record.evidence_stale,
        evidence_invalidated=record.evidence_invalidated,
    )
    re_eval = RefusalEngine().evaluate(ctx)
    recorded_triggered = sorted(ev.rule_id for ev in record.refusal_evaluations if ev.triggered)
    if (
        len(record.refusal_evaluations) != len(re_eval.evaluations)
        or re_eval.refused != record.refused
        or sorted(re_eval.triggered_rule_ids) != recorded_triggered
    ):
        diags.append(
            VerificationDiagnostic(
                "VER-REFUSAL-MISMATCH",
                f"Recorded refusal ({record.refused}, {recorded_triggered}) disagrees with re-evaluation ({re_eval.refused}, {re_eval.triggered_rule_ids}).",
                field="refusal_evaluations",
            )
        )

    if not record.refused and (record.evidence_stale or record.evidence_invalidated):
        diags.append(
            VerificationDiagnostic(
                "VER-STALE-OR-INVALIDATED",
                "Unrefused record has stale or invalidated evidence.",
                field="evidence_stale",
            )
        )
    if not record.refused and record.model_applicability_status != "established":
        diags.append(
            VerificationDiagnostic(
                "VER-APPLICABILITY-UNESTABLISHED",
                f"Unrefused record has model_applicability_status='{record.model_applicability_status}'.",
                field="model_applicability_status",
            )
        )

    # 10. Optional re-execution comparison (never runs by default)
    rerun_qoi: Optional[float] = None
    if rerun:
        if reexec_fn is None:
            diags.append(VerificationDiagnostic("VER-RERUN-MISMATCH", "Rerun requested without reexec_fn."))
        else:
            rerun_qoi = float(reexec_fn(record))
            if record.qoi_value is None or not math.isclose(rerun_qoi, record.qoi_value, rel_tol=rtol, abs_tol=1e-12):
                diags.append(
                    VerificationDiagnostic(
                        "VER-RERUN-MISMATCH",
                        f"Re-executed QoI {rerun_qoi} != recorded QoI {record.qoi_value} (rtol={rtol}).",
                        field="qoi_value",
                    )
                )

    if not diags:
        return VerificationReport(
            True,
            record.record_id,
            record.schema_version,
            record.refused,
            ["VER-OK"],
            [VerificationDiagnostic("VER-OK", "Evidence record schema, canonical hash, provenance, and refusal rules verified.")],
            recomputed_hash=recomputed,
            rerun_qoi_value=rerun_qoi,
        )

    return VerificationReport(
        False,
        record.record_id,
        record.schema_version,
        record.refused,
        [d.code for d in diags],
        diags,
        recomputed_hash=recomputed,
        rerun_qoi_value=rerun_qoi,
    )


def verify_evidence_file(
    path: Union[str, Path],
    *,
    rerun: bool = False,
    reexec_fn: Optional[Callable[[EngineeringEvidenceRecord], float]] = None,
    rtol: float = 1e-6,
) -> VerificationReport:
    """Load a JSON evidence record from disk and verify it."""
    p = Path(path)
    if not p.is_file():
        d = VerificationDiagnostic("VER-SCHEMA-INVALID", f"Evidence file not found: {p}")
        return VerificationReport(False, None, None, None, [d.code], [d])
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        d = VerificationDiagnostic("VER-SCHEMA-INVALID", f"Malformed JSON in {p}: {exc}")
        return VerificationReport(False, None, None, None, [d.code], [d])
    return verify_evidence_payload(payload, rerun=rerun, reexec_fn=reexec_fn, rtol=rtol)
