"""
Reproducible Independent FEM Validation for Restricted Linear-Elastic Scaling.
Performs independent FEM solves from scratch across varied (E, P) parameters,
and rigorously compares them against analytical scaling predictions:
    J(E, P) = (P / P_0) * (E_0 / E) * J_0
Outputs raw evidence to CSV and validates machine-precision agreement.
"""

import os
import sys
import csv
import math
import numpy as np
import skfem as fem
from skfem.models.elasticity import linear_elasticity, lame_parameters

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.dse.scaling import (
    RestrictedLinearElasticScaling,
    ReferenceBaseline,
    ScalingAssumptions,
)


def run_fem_validation(output_csv: str) -> None:
    print("=" * 80)
    print("GDEC Phase 5.1.1 Independent FEM Validation of Linear-Elastic Scaling")
    print("=" * 80)

    # Step 1: Define Problem Specification
    # Cantilever: Length L = 2.0, Height H = 0.5, Thickness = 1.0, Poisson's ratio = 0.3
    length = 2.0
    height = 0.5
    poisson_ratio = 0.3
    mesh = GDECMesh.create_cantilever_mesh(width=length, height=height, nx=21, ny=11)

    # Reference parameters
    E_0 = 210000.0  # MPa
    P_0 = 1000.0    # N (traction at right edge: ty = -1000 / height)
    traction_y_0 = -P_0 / height

    c_0 = ConstitutiveTensor.from_properties(E=E_0, nu=poisson_ratio)
    solver_0 = LinearElasticitySolver(c_0)
    sol_0 = solver_0.solve(
        gdec_mesh=mesh,
        loads=[("right", 0.0, traction_y_0)],
        fixed_boundaries=[("left", ["x", "y"])],
        qoi_boundary="right",
        qoi_component="y",
        solve_adjoint=False,
    )
    J_0 = float(abs(sol_0.qoi))
    dofs = sol_0.u.shape[0]

    print(f"Reference Solve Completed:")
    print(f"  E_0 = {E_0:,.1f} MPa | P_0 = {P_0:,.1f} N | DOFs = {dofs}")
    print(f"  Reference Tip Deflection J_0 = {J_0:.8f} mm")
    print("-" * 80)

    baseline = ReferenceBaseline(
        E_0=E_0,
        P_0=P_0,
        J_0=J_0,
        poisson_ratio=poisson_ratio,
        dof_count=dofs,
        qoi_name="tip_deflection",
    )
    assumptions = ScalingAssumptions(
        uniform_material_scaling=True,
        fixed_geometry=True,
        fixed_poisson_ratio=True,
        linear_elastic_regime=True,
        proportional_loading=True,
        compatible_displacement_qoi=True,
        qoi_type="fixed_displacement",
        attested_by="GDEC-Phase5.1.1-Independent-FEM-Verifier",
    )
    scaler = RestrictedLinearElasticScaling(baseline, assumptions)

    # Step 2: Define Sample Matrix for Independent Reruns
    samples = [
        {"sample_id": "Sample_1_Nominal", "E": 210000.0, "P": 1000.0},
        {"sample_id": "Sample_2_Half_E",   "E": 105000.0, "P": 1000.0},
        {"sample_id": "Sample_3_Double_P", "E": 210000.0, "P": 2000.0},
        {"sample_id": "Sample_4_Scaled_EP","E": 150000.0, "P": 750.0},
        {"sample_id": "Sample_5_Extreme",  "E": 70000.0,  "P": 1500.0},
    ]

    results_rows = []
    headers = [
        "sample_id",
        "youngs_modulus_E_MPa",
        "load_factor_P_N",
        "independent_fem_solve_J_mm",
        "analytical_scaling_J_mm",
        "absolute_difference_mm",
        "relative_difference",
        "parity_pass",
    ]

    print(f"{'Sample ID':<22} | {'E (MPa)':<10} | {'P (N)':<8} | {'FEM J (mm)':<14} | {'Scaling J (mm)':<14} | {'Rel Diff':<12}")
    print("-" * 90)

    for s in samples:
        E_val = s["E"]
        P_val = s["P"]
        tr_y = -P_val / height

        # 1. Independent fresh FEM solve from scratch (new solver instance, fresh assembly)
        c_i = ConstitutiveTensor.from_properties(E=E_val, nu=poisson_ratio)
        independent_solver = LinearElasticitySolver(c_i)
        ind_sol = independent_solver.solve(
            gdec_mesh=mesh,
            loads=[("right", 0.0, tr_y)],
            fixed_boundaries=[("left", ["x", "y"])],
            qoi_boundary="right",
            qoi_component="y",
            solve_adjoint=False,
        )
        J_fem = float(abs(ind_sol.qoi))

        # 2. Analytical scaling evaluation (zero additional FEM solves)
        J_analytical = scaler.evaluate_scalar(E=E_val, P=P_val)

        # 3. Discrepancy analysis
        abs_diff = abs(J_fem - J_analytical)
        rel_diff = abs_diff / max(abs(J_fem), 1e-15)
        is_pass = rel_diff < 1e-12

        print(f"{s['sample_id']:<22} | {E_val:<10.1f} | {P_val:<8.1f} | {J_fem:<14.8f} | {J_analytical:<14.8f} | {rel_diff:<12.2e}")

        results_rows.append({
            "sample_id": s["sample_id"],
            "youngs_modulus_E_MPa": E_val,
            "load_factor_P_N": P_val,
            "independent_fem_solve_J_mm": f"{J_fem:.10f}",
            "analytical_scaling_J_mm": f"{J_analytical:.10f}",
            "absolute_difference_mm": f"{abs_diff:.6e}",
            "relative_difference": f"{rel_diff:.6e}",
            "parity_pass": is_pass,
        })

    # Step 3: Write Output CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results_rows)

    print("-" * 90)
    print(f"[DONE] Independent FEM validation complete. Results written to: {output_csv}")


if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else "research/phase5.1.1/scaling/SCALING_RAW_RESULTS.csv"
    run_fem_validation(out)
