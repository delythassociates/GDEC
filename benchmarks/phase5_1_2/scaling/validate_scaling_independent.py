"""
GDEC Phase 5.1.2 — Genuinely Independent FEM Reference Validation for Analytical Parameter Scaling.
Uses scikit-fem (skfem v12.0.2) as an external, third-party reference implementation.
Constructs its own mesh, assembles its own plane-stress elasticity bilinear form,
applies Dirichlet boundary conditions, solves the system, and evaluates tip deflection QoI.
Zero GDEC FEM solver or mesh code is imported or used for reference generation.
"""

import os
import sys
import csv
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
from skfem.models.elasticity import linear_elasticity, plane_stress

from gdec.dse.scaling import (
    RestrictedLinearElasticScaling,
    ReferenceBaseline,
    ScalingAssumptions,
    ScalingAssumptionError,
)


def run_independent_validation(output_csv: str) -> None:
    print("=" * 80)
    print("GDEC Phase 5.1.2 — Independent Reference FEM Scaling Validation (scikit-fem)")
    print("=" * 80)
    print(f"Third-Party FEM Engine: scikit-fem v{fem.__version__}")
    print("Zero GDEC FEM solver, mesh, or assembly code imported.")
    print("-" * 80)

    # 1. Geometry and Mesh Construction in scikit-fem
    L = 5.0   # Cantilever length (mm)
    H = 1.0   # Cantilever height (mm)
    nx = 41   # Grid resolution in x
    ny = 17   # Grid resolution in y
    nu = 0.3  # Poisson's ratio (fixed)

    mesh = fem.MeshTri.init_tensor(np.linspace(0, L, nx), np.linspace(0, H, ny))
    element = fem.ElementVector(fem.ElementTriP1())
    ib = fem.Basis(mesh, element)

    n_nodes = mesh.p.shape[1]
    n_dofs = ib.N
    print(f"Mesh: 2D Uniform Triangles | Elements: {mesh.nelements:,} | Nodes: {n_nodes:,} | DOFs: {n_dofs:,}")

    # Clamped boundary at x = 0 (both u_x = 0 and u_y = 0)
    dofs_clamped = ib.get_dofs(lambda x: np.isclose(x[0], 0.0)).all()

    # Right boundary facets at x = L for shear traction load
    facets_right = mesh.facets_satisfying(lambda x: np.isclose(x[0], L))
    fb = fem.FacetBasis(mesh, element, facets=facets_right)

    # Identify mid-plane tip node at (x=L, y=H/2) for vertical tip deflection QoI
    nodes_tip_mid = np.where(np.isclose(mesh.p[0], L) & np.isclose(mesh.p[1], H / 2.0))[0]
    assert len(nodes_tip_mid) == 1, "Expected unique mid-plane tip node"
    node_tip = nodes_tip_mid[0]
    dof_tip_uy = ib.nodal_dofs[1, node_tip]

    def solve_independent_fem(E_modulus: float, P_load: float):
        """Assembles and solves plane stress elasticity using scikit-fem from scratch."""
        @fem.LinearForm
        def shear_traction(v, w):
            # Downward shear traction of total magnitude P distributed over height H
            return - (P_load / H) * v[1]

        f_vec = fem.asm(shear_traction, fb)
        mu, lmbda = plane_stress(E_modulus, nu)
        K_mat = fem.asm(linear_elasticity(mu, lmbda), ib)

        K_c, f_c, u_init, I_dofs = fem.condense(K_mat, f_vec, D=dofs_clamped)
        u_free = spla.spsolve(K_c, f_c)
        u_full = u_init.copy()
        u_full[I_dofs] = u_free

        # Residual verification: ||f - K u|| / ||f||
        res_norm = float(np.linalg.norm(f_vec - K_mat @ u_full) / max(np.linalg.norm(f_vec), 1e-14))

        # Vertical tip displacement (downward, reported as positive magnitude)
        tip_deflection = abs(float(u_full[dof_tip_uy]))
        # Compliance energy C = f^T u
        compliance = float(f_vec @ u_full)

        return tip_deflection, compliance, res_norm

    # 2. Baseline Problem Configuration
    E_0 = 210e3  # 210 GPa (in MPa)
    P_0 = 1000.0 # 1000 N shear load

    print(f"\n[Baseline Solve] Assembling independent FEM: E_0 = {E_0:,} MPa, P_0 = {P_0:,} N...")
    J_0_fem, C_0_fem, res_0 = solve_independent_fem(E_0, P_0)
    print(f"  Baseline Tip Deflection J_0: {J_0_fem:.8f} mm")
    print(f"  Baseline Compliance C_0:     {C_0_fem:.8f} N*mm")
    print(f"  Residual Relative Norm:      {res_0:.2e}")

    # 3. Setup GDEC Analytical Scaler
    baseline_record = ReferenceBaseline(
        E_0=E_0,
        P_0=P_0,
        J_0=J_0_fem,
        poisson_ratio=nu,
        dof_count=n_dofs,
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
        attested_by="Independent Verification Specialist (scikit-fem)",
    )
    gdec_scaler = RestrictedLinearElasticScaling(baseline_record, assumptions=assumptions)

    # 4. Independent Validation Variations (5 Parameter Cases)
    test_cases = [
        ("Case_1_E_doubled", 2.0 * E_0, P_0, "Increased Young's modulus (2x)"),
        ("Case_2_E_halved", 0.5 * E_0, P_0, "Decreased Young's modulus (0.5x)"),
        ("Case_3_P_doubled", E_0, 2.0 * P_0, "Increased shear load (2x)"),
        ("Case_4_P_halved", E_0, 0.5 * P_0, "Decreased shear load (0.5x)"),
        ("Case_5_Combined_E1.5_P3.0", 1.5 * E_0, 3.0 * P_0, "Combined variation (E=1.5x, P=3x)"),
    ]

    csv_rows = []
    print("\n--- Running Independent Parameter Variations ---")

    for case_id, E_val, P_val, desc in test_cases:
        # Full independent FEM re-assembly and solve
        J_fem, C_fem, res_norm = solve_independent_fem(E_val, P_val)
        # GDEC analytical scaling prediction
        J_pred = gdec_scaler.evaluate_scalar(E_val, P_val)

        abs_err = abs(J_fem - J_pred)
        rel_err = abs_err / max(abs(J_fem), 1e-14)

        # Theoretical compliance scaling: (P/P0)^2 * (E0/E) * C0
        C_scaling_expected = ((P_val / P_0) ** 2) * (E_0 / E_val) * C_0_fem
        C_err = abs(C_fem - C_scaling_expected) / max(abs(C_fem), 1e-14)

        print(f"\n[{case_id}] {desc}")
        print(f"  E = {E_val:,.1f} MPa, P = {P_val:,.1f} N")
        print(f"  Independent FEM QoI:   {J_fem:.10f} mm")
        print(f"  GDEC Analytical QoI:  {J_pred:.10f} mm")
        print(f"  Absolute Discrepancy:  {abs_err:.2e} mm")
        print(f"  Relative Discrepancy:  {rel_err:.2e}")
        print(f"  Compliance C_FEM:      {C_fem:.6f} N*mm | Quadratic Formula Diff: {C_err:.2e}")

        assert rel_err < 1e-9, f"Analytical scaling failed to match independent FEM in {case_id}: rel_err={rel_err}"

        csv_rows.append({
            "case_id": case_id,
            "description": desc,
            "engine": f"scikit-fem-{fem.__version__}",
            "elements": mesh.nelements,
            "dofs": n_dofs,
            "youngs_modulus_mpa": E_val,
            "load_factor_n": P_val,
            "independent_fem_qoi_mm": f"{J_fem:.12e}",
            "gdec_analytical_qoi_mm": f"{J_pred:.12e}",
            "abs_error_mm": f"{abs_err:.12e}",
            "rel_error": f"{rel_err:.12e}",
            "fem_residual_rel_norm": f"{res_norm:.12e}",
            "compliance_n_mm": f"{C_fem:.12e}",
        })

    # Save CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    headers = list(csv_rows[0].keys())
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\n[DONE] Saved independent validation raw results to: {output_csv}")


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "research/phase5.1.2/scaling/INDEPENDENT_SKFEM_RAW_RESULTS.csv"
    run_independent_validation(out_file)
