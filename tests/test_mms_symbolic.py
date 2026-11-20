"""
Symbolic MMS Verification for A2.4 Manufactured Solution.
Derives exact analytical expressions using SymPy:
- Exact displacement field u_x, u_y
- Strain tensor components eps_11, eps_22, gamma_12
- Stress tensor components sig_11, sig_22, sig_12
- Equilibrium body force b = - div(sigma)
- Strong-form residual div(sigma) + b == 0 (verified to be identically zero)
- Numerical equivalence against get_analytical_body_force() at deterministic sample points.
"""

import json
from pathlib import Path
import numpy as np
import pytest
import sympy as sp

from tests.test_a2_manufactured_solution import get_analytical_body_force
from gdec.fem.elasticity import ConstitutiveTensor

RESULTS_COMPLETION_DIR = Path("results/phase_a_completion")
RESULTS_VERIF_DIR = Path("results/verification")
RESULTS_COMPLETION_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_VERIF_DIR.mkdir(parents=True, exist_ok=True)


def _record_result(entry: dict, filename: str):
    for d in [RESULTS_COMPLETION_DIR, RESULTS_VERIF_DIR]:
        path = d / filename
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


def test_symbolic_mms_derivation_and_residual():
    """
    Symbolically verify the Navier-Cauchy equilibrium residual is identically zero,
    and compare symbolic evaluation against get_analytical_body_force() across
    plane_stress and plane_strain configurations.
    """
    x, y = sp.symbols("x y", real=True)
    c11_s, c12_s, c33_s = sp.symbols("c11 c12 c33", real=True, positive=True)

    # 1. Exact displacement field
    ux = sp.sin(sp.pi * x) * sp.sin(sp.pi * y)
    uy = x * (1 - x) * y * (1 - y) * (1 + x + 2 * y)

    # 2. Kinematic strain tensor
    eps11 = sp.diff(ux, x)
    eps22 = sp.diff(uy, y)
    gamma12 = sp.diff(ux, y) + sp.diff(uy, x)
    eps12 = sp.Rational(1, 2) * gamma12

    # 3. Constitutive stress relations
    sig11 = c11_s * eps11 + c12_s * eps22
    sig22 = c12_s * eps11 + c11_s * eps22
    sig12 = 2 * c33_s * eps12

    # 4. Equilibrium body forces: b = - div(sigma)
    bx_sym = -(sp.diff(sig11, x) + sp.diff(sig12, y))
    by_sym = -(sp.diff(sig12, x) + sp.diff(sig22, y))

    # 5. Verify strong form equilibrium residual: div(sigma) + b == 0
    res_x = sp.simplify(sp.diff(sig11, x) + sp.diff(sig12, y) + bx_sym)
    res_y = sp.simplify(sp.diff(sig12, x) + sp.diff(sig22, y) + by_sym)

    assert res_x == 0, f"Symbolic residual res_x is not zero: {res_x}"
    assert res_y == 0, f"Symbolic residual res_y is not zero: {res_y}"

    # 6. Evaluate numerical comparison at deterministic interior grid points
    sample_points = [0.2, 0.4, 0.6, 0.8]
    comparisons = {}

    for assumption in ["plane_stress", "plane_strain"]:
        c = ConstitutiveTensor.from_properties(E=1.0, nu=0.3, assumption=assumption, thickness=1.0)
        c11_val, c12_val, c33_val = c.c11, c.c12, c.c33

        subs_dict = {c11_s: c11_val, c12_s: c12_val, c33_s: c33_val}
        bx_sub = bx_sym.subs(subs_dict)
        by_sub = by_sym.subs(subs_dict)

        bx_func = sp.lambdify((x, y), bx_sub, modules=["numpy"])
        by_func = sp.lambdify((x, y), by_sub, modules=["numpy"])

        point_errors = []
        max_err_x, max_err_y = 0.0, 0.0

        for px in sample_points:
            for py in sample_points:
                s_bx = float(bx_func(px, py))
                s_by = float(by_func(px, py))

                a_bx, a_by = get_analytical_body_force(
                    np.array([px]), np.array([py]), c11_val, c12_val, c33_val
                )
                err_x = abs(s_bx - float(a_bx[0]))
                err_y = abs(s_by - float(a_by[0]))

                max_err_x = max(max_err_x, err_x)
                max_err_y = max(max_err_y, err_y)

                point_errors.append({
                    "x": px,
                    "y": py,
                    "symbolic_bx": s_bx,
                    "code_bx": float(a_bx[0]),
                    "diff_bx": err_x,
                    "symbolic_by": s_by,
                    "code_by": float(a_by[0]),
                    "diff_by": err_y,
                })

        comparisons[assumption] = {
            "max_abs_diff_bx": max_err_x,
            "max_abs_diff_by": max_err_y,
            "max_abs_diff": max(max_err_x, max_err_y),
            "sample_points": point_errors,
        }

    overall_max_diff = max(
        comparisons["plane_stress"]["max_abs_diff"],
        comparisons["plane_strain"]["max_abs_diff"],
    )

    passed = (res_x == 0) and (res_y == 0) and (overall_max_diff <= 1e-13)

    evidence = {
        "id": "A2.4_symbolic_mms_verification",
        "computed": {
            "symbolic_residual_res_x_zero": bool(res_x == 0),
            "symbolic_residual_res_y_zero": bool(res_y == 0),
            "plane_stress": {
                "max_abs_diff_bx": comparisons["plane_stress"]["max_abs_diff_bx"],
                "max_abs_diff_by": comparisons["plane_stress"]["max_abs_diff_by"],
            },
            "plane_strain": {
                "max_abs_diff_bx": comparisons["plane_strain"]["max_abs_diff_bx"],
                "max_abs_diff_by": comparisons["plane_strain"]["max_abs_diff_by"],
            },
            "overall_max_difference_against_code": overall_max_diff,
            "evaluated_sample_points": comparisons,
        },
        "threshold": {
            "symbolic_residual_identity": 0,
            "code_numerical_comparison_abs_tol": 1e-13,
        },
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": "Symbolic verification of manufactured solution equilibrium residual and comparison with implementation.",
    }

    _record_result(evidence, "mms_symbolic_verification.json")
    assert passed, f"Symbolic MMS check failed with max diff {overall_max_diff} > 1e-13"
