"""
Deterministic Adaptive QoI-Error-vs-DOFs Regression Test (WP2-D).

Verifies that GDEC's DWR-guided adaptive mesh refinement on the cantilever beam
produces a deterministic, reproducible DOF-vs-QoI-error trajectory that matches
the committed baseline in research/wp2/adaptive_qoi_dof_baseline.json without
regression.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.estimators import RefinementEstimator
from gdec.fem.adaptivity import MeshAdaptor


BASELINE_PATH = Path(__file__).resolve().parents[2] / "research" / "wp2" / "adaptive_qoi_dof_baseline.json"


def run_deterministic_adaptive_sequence(n_steps: int = 5) -> Dict[str, Any]:
    """Execute a deterministic DWR adaptive refinement sequence on the cantilever benchmark."""
    E = 70e9
    nu = 0.33
    thickness = 0.02
    loads = [("right", 0.0, -1.0e6)]
    fixed_bcs = [("left", ["x", "y"])]

    c = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=thickness)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)

    ref_mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=129, ny=65)
    sol_ref = solver.solve(ref_mesh, loads=loads, fixed_boundaries=fixed_bcs, solve_adjoint=False)
    qoi_ref = float(sol_ref.qoi)

    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    steps: List[Dict[str, Any]] = []

    for step_idx in range(n_steps + 1):
        sol = solver.solve(mesh, loads=loads, fixed_boundaries=fixed_bcs, solve_adjoint=True)
        dwr_res = estimator.compute_dwr_indicator(mesh, sol, loads=loads, cost_aware=True)

        qoi_val = float(sol.qoi)
        abs_err = abs(qoi_ref - qoi_val)
        rel_err = abs_err / abs(qoi_ref)
        signed_est = float(dwr_res.details["signed_qoi_error_estimate"])

        marked_count = 0
        if step_idx < n_steps:
            marked = MeshAdaptor.mark_elements(
                dwr_res,
                strategy="dwr",
                marking_fraction=0.3,
                current_dofs=sol.basis.N,
                max_dofs_budget=15000,
            )
            marked_count = int(len(marked))

        steps.append({
            "step": step_idx,
            "dofs": int(sol.basis.N),
            "nelements": int(mesh.nelements),
            "qoi": qoi_val,
            "reference_qoi": qoi_ref,
            "abs_qoi_error": abs_err,
            "rel_qoi_error": rel_err,
            "estimator_value": abs(signed_est),
            "estimator_signed_value": signed_est,
            "estimator_classification": str(dwr_res.details["classification"]),
            "is_certified_dwr_bound": bool(dwr_res.details["is_certified_dwr_bound"]),
            "marked_elements": marked_count,
        })

        if step_idx < n_steps:
            mesh = mesh.refine_elements(marked)

    return {
        "schema_version": "1.0",
        "problem": "cantilever_beam_end_shear",
        "reference_mesh": "129x65",
        "reference_dofs": int(sol_ref.basis.N),
        "reference_qoi": qoi_ref,
        "num_refinement_steps": n_steps,
        "estimator_note": "Goal-oriented DWR is an asymptotically exact error indicator, not a certified upper bound.",
        "steps": steps,
    }


def test_adaptive_qoi_dof_regression_against_locked_baseline():
    """
    Verify adaptive DOF-vs-QoI-error trajectory is valid, monotonically improving
    against the reference, and within 1% relative tolerance of the locked baseline.
    """
    assert BASELINE_PATH.is_file(), f"Missing locked baseline: {BASELINE_PATH}"
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    observed = run_deterministic_adaptive_sequence(n_steps=baseline["num_refinement_steps"])

    assert observed["reference_qoi"] == pytest.approx(baseline["reference_qoi"], rel=1e-10)
    obs_steps = observed["steps"]
    base_steps = baseline["steps"]
    assert len(obs_steps) == len(base_steps)

    # 1. Valid and strictly increasing DOFs
    dofs_seq = [s["dofs"] for s in obs_steps]
    assert all(dofs_seq[i] > dofs_seq[i - 1] for i in range(1, len(dofs_seq)))

    # 2. Consistent QoI error reduction
    assert obs_steps[-1]["rel_qoi_error"] < obs_steps[0]["rel_qoi_error"]

    # 3. Non-certified DWR indicator labelling preserved
    for s in obs_steps:
        assert s["is_certified_dwr_bound"] is False
        assert s["estimator_classification"] == "goal_oriented_dwr_estimator"

    # 4. No regression against locked baseline (1% relative margin for cross-platform BLAS rounding)
    for obs_s, base_s in zip(obs_steps, base_steps):
        assert obs_s["dofs"] == base_s["dofs"], f"Step {obs_s['step']} DOF mismatch: {obs_s['dofs']} != {base_s['dofs']}"
        assert obs_s["marked_elements"] == base_s["marked_elements"]
        assert obs_s["rel_qoi_error"] <= base_s["rel_qoi_error"] * 1.01 + 1e-12, (
            f"Step {obs_s['step']} QoI error regressed: {obs_s['rel_qoi_error']} > {base_s['rel_qoi_error']}"
        )
