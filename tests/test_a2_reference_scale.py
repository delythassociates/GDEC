"""
A2.8: Reference Study Reproduction and Scale Invariance.
Verifies:
1. Multi-resolution 4-level reference study matching stored baseline QoIs to 1e-8.
2. Independent implementation of Celik / Richardson Extrapolation / Grid Convergence Index (GCI)
   matching reference calculation to 1e-6.
3. SI vs dimensionless formulation equivalence matching back-transformed QoI to 1e-9.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.fem.mesh import GDECMesh

RESULTS_DIR = Path("results/verification")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _record_result(entry: dict, filename: str):
    path = RESULTS_DIR / filename
    results = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            results = []
    results = [r for r in results if r.get("id") != entry.get("id")]
    results.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


# Stored golden reference QoIs from v0.2.2 4-level study
STORED_REFERENCE_QOIS = {
    "16x4": -0.0014275033998,
    "32x8": -0.0017864721953,
    "64x16": -0.0018791431716,
    "128x32": -0.0019017824927,
}


def compute_celik_gci(f1: float, f2: float, f3: float, r: float = 2.0, Fs: float = 1.25) -> dict:
    """
    Standard ASME / Celik et al. (2008) discretization uncertainty estimator:
    - f1: fine grid solution
    - f2: medium grid solution
    - f3: coarse grid solution
    - r: grid refinement ratio (h_coarse / h_fine)
    - Fs: safety factor (1.25 for 3 grids)
    """
    # Order of convergence p
    ratio = abs((f3 - f2) / (f2 - f1))
    p = float(np.log(ratio) / np.log(r))

    # Richardson extrapolation
    denom = (r**p) - 1.0
    f_ext = float(f1 + (f1 - f2) / denom)

    # Errors
    ea = float(abs((f1 - f2) / f1))
    e_ext = float(abs((f_ext - f1) / f_ext))

    # Grid Convergence Index
    gci_fine = float((Fs * ea) / denom)
    gci_coarse = float((Fs * ea * (r**p)) / denom)

    return {
        "order_p": p,
        "f_extrapolated": f_ext,
        "approximate_relative_error_ea": ea,
        "extrapolated_relative_error": e_ext,
        "gci_fine_pct": gci_fine * 100.0,
        "gci_coarse_pct": gci_coarse * 100.0,
    }


def test_a2_8_reference_reproduction():
    test_id = "A2.8_reference_study_reproduction"

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)

    levels = [(16, 4), (32, 8), (64, 16), (128, 32)]
    computed_qois = {}
    diffs = {}

    for nx, ny in levels:
        key = f"{nx}x{ny}"
        m = GDECMesh.create_cantilever_mesh(2.0, 0.5, nx=nx, ny=ny)
        sol = solver.solve(
            m,
            loads=[("right", 0.0, -1e6)],
            fixed_boundaries=[("left", ["x", "y"])],
            qoi_boundary="right",
            qoi_component="y",
        )
        computed_qois[key] = float(sol.qoi)
        expected = STORED_REFERENCE_QOIS[key]
        rel_diff = abs(sol.qoi - expected) / abs(expected)
        diffs[key] = float(rel_diff)

    max_rel_diff = max(diffs.values())
    passed = max_rel_diff <= 1e-8

    res = {
        "id": test_id,
        "computed": {
            "computed_qois": computed_qois,
            "relative_differences": diffs,
            "max_relative_difference": max_rel_diff,
        },
        "threshold": {"relative_tolerance": 1e-8},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "Reproduction of 4-level cantilever reference study.",
    }
    _record_result(res, "A2_8_reference_scale.json")
    assert passed, f"Reference reproduction failed {max_rel_diff} > 1e-8"


def test_a2_8_celik_richardson_gci():
    test_id = "A2.8_celik_richardson_gci"

    f3 = STORED_REFERENCE_QOIS["32x8"]
    f2 = STORED_REFERENCE_QOIS["64x16"]
    f1 = STORED_REFERENCE_QOIS["128x32"]

    celik_res = compute_celik_gci(f1=f1, f2=f2, f3=f3, r=2.0, Fs=1.25)

    expected_p = 2.0333
    expected_f_ext = -0.0019091011668
    expected_gci_fine_pct = 0.4810

    diff_p = abs(celik_res["order_p"] - expected_p) / expected_p
    diff_ext = abs(celik_res["f_extrapolated"] - expected_f_ext) / abs(expected_f_ext)
    diff_gci = abs(celik_res["gci_fine_pct"] - expected_gci_fine_pct) / expected_gci_fine_pct

    passed = (diff_p <= 1e-3 and diff_ext <= 1e-6 and diff_gci <= 1e-3)
    res = {
        "id": test_id,
        "computed": celik_res,
        "threshold": {
            "order_p_rel_tol": 1e-3,
            "f_ext_rel_tol": 1e-6,
            "gci_rel_tol": 1e-3,
        },
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "Independent Celik / Richardson / GCI discretization uncertainty analysis.",
    }
    _record_result(res, "A2_8_reference_scale.json")
    assert passed, f"Celik GCI mismatch: p={diff_p}, ext={diff_ext}, gci={diff_gci}"


def test_a2_8_scale_invariance():
    test_id = "A2.8_scale_invariance"

    # SI Problem definition
    L, H, t = 2.0, 0.5, 0.02
    E, nu = 70e9, 0.33
    ty = -1e6

    c_si = ConstitutiveTensor.from_properties(E=E, nu=nu, assumption="plane_stress", thickness=t)
    solver_si = LinearElasticitySolver(c_si)
    mesh_si = GDECMesh.create_cantilever_mesh(width=L, height=H, nx=10, ny=5)
    sol_si = solver_si.solve(
        mesh_si,
        loads=[("right", 0.0, ty)],
        fixed_boundaries=[("left", ["x", "y"])],
        qoi_boundary="right",
        qoi_component="y",
    )
    qoi_si = float(sol_si.qoi)

    # Dimensionless Problem definition
    # Scale length by L_0 = L, modulus by E_0 = E
    c_dim = ConstitutiveTensor.from_properties(E=1.0, nu=nu, assumption="plane_stress", thickness=t / L)
    solver_dim = LinearElasticitySolver(c_dim)
    mesh_dim = GDECMesh.create_cantilever_mesh(width=1.0, height=H / L, nx=10, ny=5)
    sol_dim = solver_dim.solve(
        mesh_dim,
        loads=[("right", 0.0, ty / E)],
        fixed_boundaries=[("left", ["x", "y"])],
        qoi_boundary="right",
        qoi_component="y",
    )
    qoi_dim = float(sol_dim.qoi)

    # Reconstructed SI QoI: J_SI = L * J_dimensionless
    qoi_recon = float(L * qoi_dim)
    diff = float(abs(qoi_si - qoi_recon) / abs(qoi_si))

    passed = diff <= 1e-9
    res = {
        "id": test_id,
        "computed": {
            "si_qoi_m": qoi_si,
            "dimensionless_qoi": qoi_dim,
            "reconstructed_qoi_m": qoi_recon,
            "relative_difference": diff,
        },
        "threshold": {"relative_tolerance": 1e-9},
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "SI vs dimensionless formulation scale invariance test.",
    }
    _record_result(res, "A2_8_reference_scale.json")
    assert passed, f"Scale invariance error {diff} > 1e-9"
