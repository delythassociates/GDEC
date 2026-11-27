"""
Independent Verification Module for GDEC Engineering Evidence Records (WP3 Stage 3).

Validates schema, enforces strict JSON structural limits, recomputes canonical
SHA-256 hashes, verifies parent/artifact provenance, re-evaluates deterministic
refusal rules (comparing rule IDs, versions, triggered states, reasons, and
diagnostic contexts), checks estimator classifications, units, dependency versions,
and scientific metadata consistency without running the solver by default.

NOTE ON INDEPENDENCE:
Refusal-rule re-evaluation reuses `gdec.dse.refusal.RefusalEngine` rather than an
independent second implementation of refusal-rule semantics. Optional `rerun=True`
performs solver re-execution when explicitly supplied `reexec_fn`.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import ValidationError

from gdec.dse.evidence_graph import (
    SUPPORTED_CERT_CHECKERS,
    SUPPORTED_QOI_UNITS,
    BoundCertificateEvidence,
    EngineeringEvidenceRecord,
    EstimatorClassification,
    QualificationStatus,
    ReferenceEffectivityEvidence,
    canonical_json_dumps,
    compute_canonical_hash,
)
from gdec.dse.refusal import RefusalContext, RefusalEngine, structural_min_dofs_for_estimator


MANDATORY_DEPENDENCIES = ("numpy", "scipy", "scikit-fem")
MAX_EVIDENCE_BYTES = 5_000_000
MAX_JSON_DEPTH = 32
MAX_JSON_ITEMS = 10_000


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
    qualification_status: Optional[str]
    diagnostic_codes: List[str]
    diagnostics: List[VerificationDiagnostic] = field(default_factory=list)
    recomputed_hash: Optional[str] = None
    rerun_qoi_value: Optional[float] = None


def _validate_json_structure(obj: Any, depth: int = 0, counter: Optional[List[int]] = None) -> Optional[Tuple[str, str]]:
    """Pre-screen arbitrary Python/JSON data to prevent RecursionError, TypeError, or OverflowError."""
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_JSON_ITEMS:
        return ("VER-MALFORMED-INPUT", f"Payload exceeds maximum element limit ({MAX_JSON_ITEMS}).")
    if depth > MAX_JSON_DEPTH:
        return ("VER-MALFORMED-INPUT", f"Payload exceeds maximum nesting depth ({MAX_JSON_DEPTH}).")
    if obj is None or isinstance(obj, (bool, str)):
        if isinstance(obj, str) and len(obj) > 100_000:
            return ("VER-MALFORMED-INPUT", "String value exceeds maximum allowed length (100,000).")
        return None
    if isinstance(obj, int):
        if abs(obj) > 10**100:
            return ("VER-MALFORMED-INPUT", "Integer value exceeds supported numeric magnitude.")
        return None
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return ("VER-NONFINITE", f"Non-finite float detected: {obj}.")
        return None
    if isinstance(obj, list):
        for item in obj:
            err = _validate_json_structure(item, depth + 1, counter)
            if err is not None:
                return err
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                return ("VER-MALFORMED-INPUT", f"Non-string dictionary key detected: {type(k).__name__}.")
            err = _validate_json_structure(v, depth + 1, counter)
            if err is not None:
                return err
        return None
    return ("VER-MALFORMED-INPUT", f"Unsupported non-JSON type in payload: {type(obj).__name__}.")


def _strict_bool(d: Dict[str, Any], key: str) -> Optional[bool]:
    v = d.get(key)
    return v if isinstance(v, bool) else None


def _strict_int(d: Dict[str, Any], key: str) -> Optional[int]:
    v = d.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _strict_float(d: Dict[str, Any], key: str) -> Optional[float]:
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        fv = float(v)
    except OverflowError:
        return None
    return fv if math.isfinite(fv) else None


def _strict_str_list(d: Dict[str, Any], key: str) -> Optional[List[str]]:
    v = d.get(key)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        return None
    return list(v)


def _is_lower_hex64(val: Any) -> bool:
    return isinstance(val, str) and len(val) == 64 and all(c in "0123456789abcdef" for c in val) and val != ("0" * 64)


def verify_evidence_payload(
    payload: Dict[str, Any],
    *,
    rerun: bool = False,
    reexec_fn: Optional[Callable[[EngineeringEvidenceRecord], float]] = None,
    rtol: float = 1e-6,
) -> VerificationReport:
    """Independently verify a parsed Engineering Evidence Record dictionary (fail-closed)."""
    diags: List[VerificationDiagnostic] = []

    if not isinstance(payload, dict):
        diags.append(VerificationDiagnostic("VER-SCHEMA-INVALID", "Payload must be a JSON object."))
        return VerificationReport(False, None, None, None, None, [d.code for d in diags], diags)

    safe_rid = payload.get("record_id") if isinstance(payload.get("record_id"), str) else None
    safe_sver = payload.get("schema_version") if isinstance(payload.get("schema_version"), str) else None
    safe_ref = payload.get("refused") if isinstance(payload.get("refused"), bool) else None
    safe_qual = payload.get("qualification_status") if isinstance(payload.get("qualification_status"), str) else None

    # 0. Structural safety pre-screen (guards against RecursionError, TypeError, OverflowError, NaN)
    struct_err = _validate_json_structure(payload)
    if struct_err is not None:
        diags.append(VerificationDiagnostic(struct_err[0], struct_err[1]))
        return VerificationReport(False, safe_rid, safe_sver, safe_ref, safe_qual, [d.code for d in diags], diags)

    # 1. Schema validation
    try:
        record = EngineeringEvidenceRecord.model_validate(payload)
    except ValidationError as exc:
        diags.append(VerificationDiagnostic("VER-SCHEMA-INVALID", f"Schema validation failed: {exc}"))
        return VerificationReport(False, safe_rid, safe_sver, safe_ref, safe_qual, [d.code for d in diags], diags)

    # 2. Canonical hash verification (raw payload must match normalized dump and hash)
    try:
        raw_hash = compute_canonical_hash(payload)
        norm_hash = compute_canonical_hash(record.model_dump(mode="json"))
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        diags.append(VerificationDiagnostic("VER-MALFORMED-INPUT", f"Canonical serialization failed: {exc}"))
        return VerificationReport(False, record.record_id, record.schema_version, record.refused, record.qualification_status.value, [d.code for d in diags], diags)

    if raw_hash != record.canonical_result_hash or norm_hash != record.canonical_result_hash:
        diags.append(
            VerificationDiagnostic(
                "VER-HASH-MISMATCH",
                f"Canonical result hash mismatch: raw={raw_hash}, norm={norm_hash}, recorded={record.canonical_result_hash}.",
                field="canonical_result_hash",
            )
        )

    # 3. Provenance & parent-artifact checks
    for h_name, h_val in [
        ("problem_ir_hash", record.problem_ir_hash),
        ("canonical_eir_hash", record.canonical_eir_hash),
        ("execution_plan_hash", record.execution_plan_hash),
        ("mesh_hash", record.mesh_hash),
    ]:
        if not _is_lower_hex64(h_val):
            diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", f"Invalid lowercase 64-hex sha256 in {h_name}.", field=h_name))

    if len(record.parent_artifacts) == 0:
        diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", "parent_artifacts must not be empty.", field="parent_artifacts"))
    seen_parent_ids: Dict[str, str] = {}
    parent_hashes = set()
    for p in record.parent_artifacts:
        if not _is_lower_hex64(p.sha256_hash):
            diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", f"Invalid lowercase 64-hex sha256 in parent '{p.artifact_id}'.", field="parent_artifacts"))
        if p.artifact_id in seen_parent_ids and seen_parent_ids[p.artifact_id] != p.sha256_hash:
            diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", f"Conflicting hashes for parent '{p.artifact_id}'.", field="parent_artifacts"))
        seen_parent_ids[p.artifact_id] = p.sha256_hash
        parent_hashes.add(p.sha256_hash)
    if record.problem_ir_hash not in parent_hashes or record.mesh_hash not in parent_hashes:
        diags.append(VerificationDiagnostic("VER-PROVENANCE-INVALID", "parent_artifacts must include problem_ir_hash and mesh_hash.", field="parent_artifacts"))

    # 4. Estimator classification & certificate boundary
    if record.estimator_classification == EstimatorClassification.MATHEMATICALLY_ESTABLISHED_BOUND:
        cert = record.effectivity_evidence
        if (
            not isinstance(cert, BoundCertificateEvidence)
            or "dwr" in record.estimator_identity.lower()
            or not cert.proof_obligations_satisfied
            or cert.checker_identity not in SUPPORTED_CERT_CHECKERS
            or cert.estimator_identity != record.estimator_identity
            or cert.model_identity != record.material_identity
            or not _is_lower_hex64(cert.certificate_hash)
        ):
            diags.append(
                VerificationDiagnostic(
                    "VER-ESTIMATOR-CLASS-INVALID",
                    "mathematically_established_bound is not supported without a registered independent certificate checker.",
                    field="estimator_classification",
                )
            )
    if record.estimator_classification == EstimatorClassification.DWR_ASYMPTOTIC_ESTIMATE and "dwr" not in record.estimator_identity.lower():
        diags.append(
            VerificationDiagnostic(
                "VER-ESTIMATOR-CLASS-INVALID",
                f"Estimator '{record.estimator_identity}' cannot claim dwr_asymptotic_estimate.",
                field="estimator_classification",
            )
        )

    # 5. Units consistency
    if record.qoi_units not in SUPPORTED_QOI_UNITS or record.error_estimate_units not in SUPPORTED_QOI_UNITS:
        diags.append(VerificationDiagnostic("VER-UNITS-INCONSISTENT", "Unsupported QoI or error_estimate units.", field="qoi_units"))
    if record.qoi_units == "mm" and ("meter" in record.qoi_name.lower() or "metre" in record.qoi_name.lower()):
        diags.append(VerificationDiagnostic("VER-UNITS-INCONSISTENT", "qoi_units is 'mm' while qoi_name references meters.", field="qoi_units"))

    # 6. Mandatory dependencies
    for dep in MANDATORY_DEPENDENCIES:
        ver = record.dependency_versions.get(dep)
        if not isinstance(ver, str) or not ver.strip() or ver.strip().lower() == "unknown":
            diags.append(VerificationDiagnostic("VER-MISSING-DEPENDENCY", f"Missing or invalid dependency version for '{dep}'.", field="dependency_versions"))

    # 7. Scientific metadata & required nested keys (strictly typed, fail-closed)
    if record.outcome_metrics.final_dofs != record.dof_count:
        diags.append(VerificationDiagnostic("VER-METADATA-INCONSISTENT", "outcome_metrics.final_dofs != dof_count.", field="outcome_metrics.final_dofs"))
    if record.outcome_metrics.estimator_value != record.error_estimate:
        diags.append(VerificationDiagnostic("VER-METADATA-INCONSISTENT", "outcome_metrics.estimator_value != error_estimate.", field="outcome_metrics.estimator_value"))
    expected_ar = record.problem_features.domain_width / record.problem_features.domain_height
    if not math.isclose(record.problem_features.aspect_ratio, expected_ar, rel_tol=1e-6, abs_tol=1e-9):
        diags.append(VerificationDiagnostic("VER-METADATA-INCONSISTENT", "problem_features.aspect_ratio != width/height.", field="problem_features.aspect_ratio"))

    mesh_meta = record.mesh_metadata
    solver_cfg = record.solver_config
    res_cons = record.resource_consumption

    solver_converged = _strict_bool(solver_cfg, "solver_converged")
    adjoint_converged = _strict_bool(solver_cfg, "adjoint_converged")
    mandatory_ev = _strict_bool(solver_cfg, "mandatory_evidence_present")
    ref_req = _strict_bool(solver_cfg, "reference_required")
    problem_class = solver_cfg.get("problem_class") if isinstance(solver_cfg.get("problem_class"), str) else None
    qoi_boundary = solver_cfg.get("qoi_boundary") if isinstance(solver_cfg.get("qoi_boundary"), str) else None
    fixed_boundaries = _strict_str_list(solver_cfg, "fixed_boundaries")
    residual_norm = _strict_float(solver_cfg, "residual_norm")
    adjoint_res_norm = _strict_float(solver_cfg, "adjoint_residual_norm")
    min_req_dofs = _strict_int(solver_cfg, "min_required_dofs")

    mesh_valid = _strict_bool(mesh_meta, "mesh_valid")
    nelements = _strict_int(mesh_meta, "nelements")
    nnodes = _strict_int(mesh_meta, "nnodes")
    free_dofs = _strict_int(mesh_meta, "free_dofs")
    interior_nodes = _strict_int(mesh_meta, "interior_nodes")
    interior_facets = _strict_int(mesh_meta, "interior_facets")

    budget_exhausted = _strict_bool(res_cons, "budget_exhausted")
    target_tol_met = _strict_bool(res_cons, "target_tolerance_met")
    budget_max_dofs = _strict_int(res_cons, "budget_max_dofs")

    canon_reqs = structural_min_dofs_for_estimator(record.estimator_identity, record.estimator_classification.value)
    bad_metadata = (
        solver_converged is None
        or adjoint_converged is None
        or mandatory_ev is None
        or ref_req is None
        or problem_class is None
        or qoi_boundary is None
        or fixed_boundaries is None
        or residual_norm is None
        or residual_norm < 0.0
        or adjoint_res_norm is None
        or adjoint_res_norm < 0.0
        or min_req_dofs is None
        or min_req_dofs < canon_reqs["min_total_dofs"]
        or mesh_valid is None
        or nelements is None
        or nnodes is None
        or free_dofs is None
        or interior_nodes is None
        or interior_facets is None
        or budget_exhausted is None
        or target_tol_met is None
        or budget_max_dofs is None
        or budget_max_dofs != record.problem_features.max_dofs_budget
        or len(fixed_boundaries) != record.problem_features.num_fixed_boundaries
    )
    if bad_metadata:
        diags.append(VerificationDiagnostic("VER-METADATA-INCONSISTENT", "Missing, non-canonical, or type-invalid verification metadata in solver_config/mesh_metadata/resource_consumption."))

    # 8. Full RefusalEngine re-evaluation (all fields compared: rule_id, version, triggered, reason, diagnostic_context, aggregate refusal_reasons)
    ref_adequate: Optional[bool] = None
    if isinstance(record.effectivity_evidence, ReferenceEffectivityEvidence):
        ref_adequate = record.effectivity_evidence.adequate

    ctx = RefusalContext(
        budget_exhausted=budget_exhausted if budget_exhausted is not None else True,
        target_tolerance_met=target_tol_met if target_tol_met is not None else False,
        estimator_identity=record.estimator_identity,
        estimator_classification=record.estimator_classification.value,
        problem_class=problem_class or "",
        reference_required=ref_req if ref_req is not None else True,
        reference_adequate=ref_adequate,
        effectivity_evidence_present=isinstance(record.effectivity_evidence, ReferenceEffectivityEvidence),
        bound_certificate_verified=isinstance(record.effectivity_evidence, BoundCertificateEvidence) and record.effectivity_evidence.proof_obligations_satisfied,
        bound_checker_identity=record.effectivity_evidence.checker_identity if isinstance(record.effectivity_evidence, BoundCertificateEvidence) else "",
        qoi_boundary=qoi_boundary or "",
        fixed_boundaries=fixed_boundaries or [],
        dof_count=record.dof_count,
        free_dof_count=free_dofs if free_dofs is not None else 0,
        interior_node_count=interior_nodes if interior_nodes is not None else 0,
        interior_facet_count=interior_facets if interior_facets is not None else 0,
        min_required_dofs=max(canon_reqs["min_total_dofs"], min_req_dofs or 0),
        solver_converged=solver_converged if solver_converged is not None else False,
        adjoint_converged=adjoint_converged if adjoint_converged is not None else False,
        qoi_value=record.qoi_value,
        residual_norm=residual_norm if residual_norm is not None else float("nan"),
        adjoint_residual_norm=adjoint_res_norm if adjoint_res_norm is not None else float("nan"),
        error_estimate=record.error_estimate,
        nonfinite_detected=(record.refused and any("Non-finite" in r for r in record.refusal_reasons)),
        mesh_valid=mesh_valid if mesh_valid is not None else False,
        mesh_element_count=nelements if nelements is not None else 0,
        model_applicability_status=record.model_applicability_status,
        parent_artifacts=[p.model_dump() for p in record.parent_artifacts],
        problem_ir_hash=record.problem_ir_hash,
        canonical_eir_hash=record.canonical_eir_hash,
        execution_plan_hash=record.execution_plan_hash,
        mesh_hash=record.mesh_hash,
        mandatory_evidence_present=mandatory_ev if mandatory_ev is not None else False,
        evidence_stale=record.evidence_stale,
        evidence_invalidated=record.evidence_invalidated,
    )
    re_eval = RefusalEngine().evaluate(ctx)

    if len(record.refusal_evaluations) != len(re_eval.evaluations):
        diags.append(VerificationDiagnostic("VER-REFUSAL-MISMATCH", "refusal_evaluations length mismatch.", field="refusal_evaluations"))
    else:
        for rec_ev, exp_ev in zip(record.refusal_evaluations, re_eval.evaluations):
            if (
                rec_ev.rule_id != exp_ev.rule_id
                or rec_ev.version != exp_ev.version
                or rec_ev.triggered != exp_ev.triggered
                or rec_ev.reason != exp_ev.reason
                or canonical_json_dumps(rec_ev.diagnostic_context) != canonical_json_dumps(exp_ev.diagnostic_context)
            ):
                diags.append(
                    VerificationDiagnostic(
                        "VER-REFUSAL-MISMATCH",
                        f"Refusal evaluation mismatch on rule '{exp_ev.rule_id}'.",
                        field="refusal_evaluations",
                    )
                )
                break

    if record.refused != re_eval.refused or record.refusal_reasons != re_eval.reasons:
        diags.append(VerificationDiagnostic("VER-REFUSAL-MISMATCH", "Aggregate refused/refusal_reasons mismatch.", field="refusal_reasons"))

    # 9. Qualification consistency
    if record.refused and record.qualification_status != QualificationStatus.REFUSED:
        diags.append(VerificationDiagnostic("VER-REFUSAL-MISMATCH", "Refused record must have qualification_status='REFUSED'.", field="qualification_status"))

    # 10. Optional re-execution comparison (never runs by default)
    rerun_qoi: Optional[float] = None
    if rerun:
        if reexec_fn is None:
            diags.append(VerificationDiagnostic("VER-RERUN-MISMATCH", "Rerun requested without reexec_fn."))
        else:
            try:
                rerun_qoi = float(reexec_fn(record))
            except Exception as exc:
                diags.append(VerificationDiagnostic("VER-RERUN-MISMATCH", f"Re-execution failed: {exc}"))
                rerun_qoi = None
            if rerun_qoi is not None:
                if not math.isfinite(rerun_qoi) or record.qoi_value is None or not math.isclose(rerun_qoi, record.qoi_value, rel_tol=rtol, abs_tol=1e-12):
                    diags.append(VerificationDiagnostic("VER-RERUN-MISMATCH", f"Re-executed QoI {rerun_qoi} != recorded QoI {record.qoi_value}.", field="qoi_value"))

    if not diags:
        return VerificationReport(
            True,
            record.record_id,
            record.schema_version,
            record.refused,
            record.qualification_status.value,
            ["VER-OK"],
            [VerificationDiagnostic("VER-OK", "Evidence record schema, canonical hash, provenance, and refusal rules verified.")],
            recomputed_hash=raw_hash,
            rerun_qoi_value=rerun_qoi,
        )

    return VerificationReport(
        False,
        record.record_id,
        record.schema_version,
        record.refused,
        record.qualification_status.value,
        [d.code for d in diags],
        diags,
        recomputed_hash=raw_hash,
        rerun_qoi_value=rerun_qoi,
    )


def _reject_dup_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"Duplicate JSON key: '{k}'")
        d[k] = v
    return d


def _reject_nonfinite_constant(val: str) -> Any:
    raise ValueError(f"Non-standard JSON constant not permitted: '{val}'")


def verify_evidence_file(
    path: Union[str, Path],
    *,
    rerun: bool = False,
    reexec_fn: Optional[Callable[[EngineeringEvidenceRecord], float]] = None,
    rtol: float = 1e-6,
) -> VerificationReport:
    """Load a JSON evidence record from disk and verify it (fail-closed on OS/parse errors)."""
    try:
        p = Path(path)
        if not p.is_file():
            d = VerificationDiagnostic("VER-SCHEMA-INVALID", f"Evidence file not found: {p}")
            return VerificationReport(False, None, None, None, None, [d.code], [d])
        size = p.stat().st_size
        if size > MAX_EVIDENCE_BYTES:
            d = VerificationDiagnostic("VER-MALFORMED-INPUT", f"Evidence file exceeds {MAX_EVIDENCE_BYTES} byte limit ({size} bytes).")
            return VerificationReport(False, None, None, None, None, [d.code], [d])
        raw_text = p.read_text(encoding="utf-8")
        payload = json.loads(
            raw_text,
            object_pairs_hook=_reject_dup_keys,
            parse_constant=_reject_nonfinite_constant,
        )
    except Exception as exc:
        d = VerificationDiagnostic("VER-MALFORMED-INPUT", f"Failed to parse evidence file: {exc}")
        return VerificationReport(False, None, None, None, None, [d.code], [d])
    return verify_evidence_payload(payload, rerun=rerun, reexec_fn=reexec_fn, rtol=rtol)
