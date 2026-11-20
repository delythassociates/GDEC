"""
GDEC Phase C Amendment 3 — Exact QoI Mathematical Audit & Quadrature Concordance.
Remediates AM3-02:
1. Reconciles Family 4 patch-average displacement formulas for both horizontal (u_x) and vertical (u_y) components.
2. Formally audits all 40 Tier 1 BVP configurations against high-precision numerical quadrature (SciPy quad/dblquad).
3. Verifies that absolute differences between closed-form analytical formulas and numerical quadrature are < 1e-11 across all 40 configurations.
4. Generates results/phase_c_amendment_3/exact_qoi_audit.json.
"""

import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import scipy.integrate as integrate

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))


def evaluate_displacement_functions(
    fam_str: str, params: Dict[str, float]
):
    """Returns exact callable displacement field functions ux_fn(x, y) and uy_fn(x, y)."""
    if fam_str == "family_1_polynomial":
        a, b = params["a"], params["b"]
        ux_fn = lambda x, y, a=a, b=b: a * x**2 + b * y**2
        uy_fn = lambda x, y, a=a, b=b: a * x * y
    elif fam_str == "family_2_trigonometric":
        freq, amp = params["freq"], params["amp"]
        ux_fn = lambda x, y, f=freq, A=amp: A * math.sin(f * math.pi * x) * math.cos(f * math.pi * y)
        uy_fn = lambda x, y, f=freq, A=amp: A * math.cos(f * math.pi * x) * math.sin(f * math.pi * y)
    elif fam_str == "family_3_localized_gaussian":
        x0, y0, sigma, amp = params["x0"], params["y0"], params["sigma"], params["amp"]
        ux_fn = lambda x, y, x0=x0, y0=y0, s=sigma, A=amp: A * math.exp(-((x - x0)**2 + (y - y0)**2) / s**2)
        uy_fn = lambda x, y, x0=x0, y0=y0, s=sigma, A=amp: 0.5 * A * math.exp(-((x - x0)**2 + (y - y0)**2) / s**2)
    elif fam_str == "family_4_mixed_shear":
        kx, ky = params["kx"], params["ky"]
        ux_fn = lambda x, y, kx=kx, ky=ky: kx * x * y + ky * y**2
        uy_fn = lambda x, y, kx=kx, ky=ky: -ky * x**2 + kx * x * y
    elif fam_str == "family_5_multiscale_oscillatory":
        k1, k2, beta, amp = params["k1"], params["k2"], params["beta"], params["amp"]
        ux_fn = lambda x, y, k1=k1, k2=k2, b=beta, A=amp: A * (math.sin(k1 * math.pi * x) + b * math.sin(k2 * math.pi * x))
        uy_fn = lambda x, y, k1=k1, k2=k2, b=beta, A=amp: A * (math.cos(k1 * math.pi * y) + b * math.cos(k2 * math.pi * y))
    else:
        raise ValueError(f"Unknown family: {fam_str}")
    return ux_fn, uy_fn


def audit_single_config(item: Dict[str, Any]) -> Dict[str, Any]:
    cid = item["config_id"]
    fam = item["family"]
    params = item["parameters"]
    qoi = item["qoi"]
    qtype = qoi["type"]
    comp = qoi["component"]
    exact_analytical = qoi["exact_analytical_value"]

    ux_fn, uy_fn = evaluate_displacement_functions(fam, params)

    if qtype == "boundary_average_displacement":
        # Boundary average over top edge y = 1.0, x in [0, 1]
        target_fn = uy_fn if comp == "y" else ux_fn
        quad_val, err_est = integrate.quad(lambda x: target_fn(x, 1.0), 0.0, 1.0, epsabs=1e-14, epsrel=1e-14)
        numerical_qoi = quad_val / 1.0
    elif qtype == "patch_average_displacement":
        # Patch average over [0.25, 0.75] x [0.25, 0.75], area = 0.25
        target_fn = ux_fn if comp == "x" else uy_fn
        quad_val, err_est = integrate.dblquad(
            lambda y, x: target_fn(x, y),
            0.25,
            0.75,
            lambda x: 0.25,
            lambda x: 0.75,
            epsabs=1e-14,
            epsrel=1e-14,
        )
        numerical_qoi = quad_val / 0.25
    else:
        raise ValueError(f"Unsupported QoI type: {qtype}")

    abs_diff = abs(exact_analytical - numerical_qoi)
    rel_diff = abs_diff / abs(exact_analytical) if abs(exact_analytical) > 0 else abs_diff
    passes = bool(abs_diff < 1e-11)

    record = {
        "config_id": cid,
        "family_index": item["family_index"],
        "family": fam,
        "qoi_type": qtype,
        "component": comp,
        "target_region": qoi["target_region"],
        "exact_analytical_value": exact_analytical,
        "numerical_quadrature_value": numerical_qoi,
        "absolute_difference": abs_diff,
        "relative_difference": rel_diff,
        "quadrature_error_estimate": err_est,
        "concordance_verified": passes,
    }
    return record


def run_qoi_audit() -> Dict[str, Any]:
    manifest_path = Path("verification/phase_c/amendment_2/tier1_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"=== Auditing {len(manifest)} Tier 1 Configurations for Analytical QoI Concordance ===")
    records = []
    max_diff = 0.0
    family_max_diff = {}

    for item in manifest:
        rec = audit_single_config(item)
        records.append(rec)
        diff = rec["absolute_difference"]
        max_diff = max(max_diff, diff)
        fam = rec["family"]
        family_max_diff[fam] = max(family_max_diff.get(fam, 0.0), diff)
        status_str = "PASS" if rec["concordance_verified"] else "FAIL"
        print(
            f"[{status_str}] {rec['config_id']:<6} Fam {rec['family_index']} ({rec['component']}): "
            f"Exact={rec['exact_analytical_value']:.10e}, Quad={rec['numerical_quadrature_value']:.10e}, "
            f"Diff={diff:.2e}"
        )

    all_passed = all(r["concordance_verified"] for r in records)
    print(f"\nAll 40 configurations verified: {all_passed}")
    print(f"Global Maximum Absolute Difference: {max_diff:.3e} (threshold: 1.00e-11)")

    # Special Family 4 formula audit verification
    # Document both horizontal and vertical patch formulas
    # For kx = 0.003, ky = 0.0012:
    # ux patch = 0.25 * kx + (13/48) * ky = 0.25 * 0.003 + (13/48) * 0.0012 = 0.00075 + 0.000325 = 0.001075
    # uy patch = 0.25 * kx - (13/48) * ky = 0.25 * 0.003 - (13/48) * 0.0012 = 0.00075 - 0.000325 = 0.000425
    kx_test, ky_test = 0.003, 0.0012
    ux_patch_analytical = 0.25 * kx_test + (13.0 / 48.0) * ky_test
    uy_patch_analytical = 0.25 * kx_test - (13.0 / 48.0) * ky_test
    uy_patch_quad, _ = integrate.dblquad(
        lambda y, x: -ky_test * x**2 + kx_test * x * y,
        0.25, 0.75, lambda x: 0.25, lambda x: 0.75
    )
    uy_patch_quad /= 0.25
    assert np.isclose(uy_patch_analytical, uy_patch_quad, atol=1e-15)

    summary = {
        "total_configurations_audited": len(records),
        "all_passed": all_passed,
        "global_max_absolute_difference": max_diff,
        "family_max_differences": family_max_diff,
        "family_4_reconciliation": {
            "displacement_field": {
                "u_x": "k_x * x * y + k_y * y^2",
                "u_y": "-k_y * x^2 + k_x * x * y",
            },
            "boundary_averages_y_equals_1": {
                "u_x": "0.5 * k_x + k_y",
                "u_y": "- (1/3) * k_y + 0.5 * k_x",
            },
            "patch_averages_domain_0p25_to_0p75_squared": {
                "u_x": "0.25 * k_x + (13/48) * k_y",
                "u_y": "0.25 * k_x - (13/48) * k_y",
            },
            "sign_verification_test": {
                "parameters": {"kx": kx_test, "ky": ky_test},
                "ux_patch_exact": ux_patch_analytical,
                "uy_patch_exact": uy_patch_analytical,
                "uy_patch_quad": uy_patch_quad,
                "concordance_diff": abs(uy_patch_analytical - uy_patch_quad),
            },
        },
        "configurations": records,
    }

    out_file = Path("results/phase_c_amendment_3/exact_qoi_audit.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Audit results written to: {out_file}")
    return summary


if __name__ == "__main__":
    run_qoi_audit()
