"""
High-resolution reference solution calculation and verification for GDEC benchmarks.
Provides progressive multi-resolution convergence checks and analytical Timoshenko beam comparison.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from gdec.language.ir import ProblemIR
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.boundary_conditions import parse_boundary_conditions, parse_loads


@dataclass
class ReferenceLevelResult:
    level_name: str
    dofs: int
    nelements: int
    nnodes: int
    mesh_resolution: tuple[int, int]
    qoi_meters: float
    qoi_mm: float
    solve_time_sec: float


@dataclass
class ReferenceConvergenceReport:
    levels: List[ReferenceLevelResult]
    relative_changes_pct: List[float]
    finest_adequate_for_thresholds: bool
    estimated_discretization_uncertainty_pct: float
    analytical_comparison: Dict[str, float]
    adequacy_assessment: str


@dataclass
class ReferenceSolution:
    qoi_meters: float
    qoi_mm: float
    dofs: int
    nelements: int
    nnodes: int
    solve_time_sec: float
    mesh_resolution: tuple[int, int]
    is_analytical: bool = False
    notes: str = (
        "High-resolution numerical finite-element approximation on fine mesh; "
        "not an exact closed-form analytical solution."
    )
    convergence_report: Optional[ReferenceConvergenceReport] = None


def compute_timoshenko_cantilever(
    width: float, height: float, thickness: float, E: float, nu: float, ty: float
) -> Dict[str, float]:
    """
    Classical analytical cantilever beam deflection with shear deformation (Timoshenko theory).
    P = ty * height * thickness (total downward load in Newtons)
    I = (thickness * height^3) / 12 (moment of inertia)
    G = E / (2 * (1 + nu)) (shear modulus)
    A = height * thickness (cross-sectional area)
    kappa = 5/6 (shear correction factor for rectangular section)
    """
    P = ty * height * thickness
    L = width
    I = (thickness * (height**3)) / 12.0
    G = E / (2.0 * (1.0 + nu))
    A = height * thickness
    kappa = 5.0 / 6.0

    delta_eb = (P * (L**3)) / (3.0 * E * I)
    delta_shear = (P * L) / (kappa * G * A)
    delta_timo = delta_eb + delta_shear

    return {
        "P_total_N": float(P),
        "I_m4": float(I),
        "G_Pa": float(G),
        "delta_euler_bernoulli_mm": float(delta_eb * 1000.0),
        "delta_shear_mm": float(delta_shear * 1000.0),
        "delta_timoshenko_total_mm": float(delta_timo * 1000.0),
    }


class ReferenceSolver:
    @staticmethod
    def compute_reference(
        ir: ProblemIR, target_dofs: int = 35000, verify_convergence: bool = True
    ) -> ReferenceSolution:
        """
        Compute high-resolution reference solution and verify multi-resolution mesh convergence.
        """
        mat = ir.material
        geo = ir.geometry
        constitutive = ConstitutiveTensor.from_properties(
            E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
        )
        solver = LinearElasticitySolver(constitutive)
        loads = parse_loads(ir.loads)
        bcs = parse_boundary_conditions(ir.boundary_conditions)

        aspect = geo.width / geo.height

        # If verification requested, generate progressive levels: e.g. target/3, target/1.5, target
        levels_to_run: list[tuple[str, int]] = []
        if verify_convergence:
            targets = [
                ("Level 1 (Coarse Ref)", max(6000, int(target_dofs * 0.35))),
                ("Level 2 (Medium Ref)", max(12000, int(target_dofs * 0.65))),
                ("Level 3 (Fine Ref)", target_dofs),
            ]
        else:
            targets = [("Single Ref", target_dofs)]

        level_results: List[ReferenceLevelResult] = []

        for name, dof_tgt in targets:
            ny = max(8, int(np.sqrt(dof_tgt / (2.0 * aspect))))
            nx = int(round(ny * aspect))

            t0 = time.perf_counter()
            mesh = GDECMesh.create_cantilever_mesh(width=geo.width, height=geo.height, nx=nx, ny=ny)
            sol = solver.solve(
                gdec_mesh=mesh,
                loads=loads,
                fixed_boundaries=bcs,
                qoi_boundary=ir.objective.boundary,
                qoi_component=ir.objective.component,
                solve_adjoint=False,
            )
            t_solve = time.perf_counter() - t0

            level_results.append(
                ReferenceLevelResult(
                    level_name=name,
                    dofs=sol.basis.N,
                    nelements=mesh.nelements,
                    nnodes=mesh.nnodes,
                    mesh_resolution=(nx, ny),
                    qoi_meters=sol.qoi,
                    qoi_mm=sol.qoi_mm,
                    solve_time_sec=t_solve,
                )
            )

        # Finest level is the primary reference
        finest = level_results[-1]

        # Convergence analysis across levels
        relative_changes: List[float] = []
        for i in range(1, len(level_results)):
            prev_qoi = level_results[i - 1].qoi_meters
            curr_qoi = level_results[i].qoi_meters
            rel_chg = (abs(curr_qoi - prev_qoi) / max(abs(curr_qoi), 1e-12)) * 100.0
            relative_changes.append(float(rel_chg))

        finest_rel_change = relative_changes[-1] if relative_changes else 0.0
        # If relative difference between last two reference levels is <= 0.1%, it is adequate for 0.25% error tests
        is_adequate = finest_rel_change <= 0.15

        # Analytical Timoshenko comparison (downward traction)
        traction_ty = ir.loads[0].ty if ir.loads else -1.0e6
        analytical = compute_timoshenko_cantilever(
            width=geo.width,
            height=geo.height,
            thickness=geo.thickness,
            E=mat.E,
            nu=mat.nu,
            ty=traction_ty,
        )
        timo_diff = (
            abs(finest.qoi_mm - analytical["delta_timoshenko_total_mm"])
            / abs(analytical["delta_timoshenko_total_mm"])
        ) * 100.0
        analytical["fem_vs_timoshenko_diff_pct"] = float(timo_diff)

        adequacy_msg = (
            f"Finest reference mesh has estimated discretization uncertainty of {finest_rel_change:.3f}%, "
            f"adequate for benchmark error comparisons down to 0.25% threshold."
            if is_adequate
            else f"Discretization uncertainty ({finest_rel_change:.3f}%) exceeds recommended 0.15% threshold; consider increasing reference DOFs."
        )

        report = ReferenceConvergenceReport(
            levels=level_results,
            relative_changes_pct=relative_changes,
            finest_adequate_for_thresholds=is_adequate,
            estimated_discretization_uncertainty_pct=finest_rel_change,
            analytical_comparison=analytical,
            adequacy_assessment=adequacy_msg,
        )

        return ReferenceSolution(
            qoi_meters=finest.qoi_meters,
            qoi_mm=finest.qoi_mm,
            dofs=finest.dofs,
            nelements=finest.nelements,
            nnodes=finest.nnodes,
            solve_time_sec=finest.solve_time_sec,
            mesh_resolution=finest.mesh_resolution,
            convergence_report=report,
        )
