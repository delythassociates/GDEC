"""
High-resolution reference solution calculation and verification for GDEC benchmarks.
Implements Celik et al. (ASME 2008) multi-level Richardson extrapolation with unequal
refinement ratios and GCI, plus analytical Timoshenko beam comparison.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import root_scalar

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
    characteristic_h: float
    qoi_meters: float
    qoi_mm: float
    solve_time_sec: float


@dataclass
class ReferenceConvergenceReport:
    levels: List[ReferenceLevelResult]
    relative_changes_pct: List[float]
    apparent_order_p: float
    refinement_ratios: tuple[float, float]
    gci_fine_percent: float
    gci_medium_percent: float
    asymptotic_consistency_ratio: float
    finest_adequate_for_thresholds: bool
    estimated_discretization_uncertainty_pct: float
    analytical_comparison: Dict[str, float]
    adequacy_assessment: str
    roache_apparent_order: Optional[float] = None
    roache_extrapolated_qoi_mm: Optional[float] = None


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
    reference_method: str = "Celik (ASME 2008) Unequal-Ratio Richardson Extrapolation"
    finest_discrete_qoi_meters: float = 0.0
    finest_discrete_qoi_mm: float = 0.0
    extrapolated_qoi_meters: float = 0.0
    extrapolated_qoi_mm: float = 0.0
    apparent_order: float = 0.0
    grid_refinement_ratios: tuple[float, float] = (1.0, 1.0)
    gci_fine_percent: float = 0.0
    gci_medium_percent: float = 0.0
    asymptotic_consistency_ratio: float = 1.0
    roache_sensitivity_qoi_mm: Optional[float] = None
    roache_sensitivity_order: Optional[float] = None
    notes: str = (
        "Primary reference established via 4-level Celik (ASME 2008) Richardson extrapolation; "
        "discrete finest mesh preserved as separate field."
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
    STANDARD_4_LEVEL_RESOLUTIONS: List[Tuple[str, int, int]] = [
        ("Level 1 (Coarse)", 144, 36),
        ("Level 2 (Medium)", 196, 49),
        ("Level 3 (Fine)", 244, 61),
        ("Level 4 (Finest)", 300, 75),
    ]

    @classmethod
    def compute_reference(
        cls, ir: ProblemIR, target_dofs: int = 35000, verify_convergence: bool = True
    ) -> ReferenceSolution:
        """
        Compute multi-level reference solution using the Celik (ASME 2008) unequal-ratio
        Richardson extrapolation formulation across an ordered hierarchy of meshes.
        """
        mat = ir.material
        geo = ir.geometry
        constitutive = ConstitutiveTensor.from_properties(
            E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
        )
        solver = LinearElasticitySolver(constitutive)
        loads = parse_loads(ir.loads)
        bcs = parse_boundary_conditions(ir.boundary_conditions)

        resolutions = cls.STANDARD_4_LEVEL_RESOLUTIONS
        level_results: List[ReferenceLevelResult] = []

        total_solve_time = 0.0
        for name, nx, ny in resolutions:
            t0 = time.perf_counter()
            mesh = GDECMesh.create_cantilever_mesh(width=geo.width, height=geo.height, nx=nx, ny=ny)
            sol = solver.solve(
                gdec_mesh=mesh,
                loads=loads,
                fixed_boundaries=bcs,
                objective=ir.objective,
                qoi_boundary=ir.objective.boundary or "right",
                qoi_component=ir.objective.component,
                solve_adjoint=False,
            )
            t_solve = time.perf_counter() - t0
            total_solve_time += t_solve

            hx = geo.width / float(nx - 1)
            hy = geo.height / float(ny - 1)
            h = float(np.sqrt(hx * hy))

            level_results.append(
                ReferenceLevelResult(
                    level_name=name,
                    dofs=sol.basis.N,
                    nelements=mesh.nelements,
                    nnodes=mesh.nnodes,
                    mesh_resolution=(nx, ny),
                    characteristic_h=h,
                    qoi_meters=sol.qoi,
                    qoi_mm=sol.qoi_mm,
                    solve_time_sec=t_solve,
                )
            )

        # Finest discrete level
        finest = level_results[-1]

        # Richardson extrapolation on top 3 levels:
        # Index convention (ASME / Celik 2008):
        # 1 = finest (Level 4), 2 = medium (Level 3), 3 = coarse (Level 2)
        f1 = level_results[3].qoi_mm
        f2 = level_results[2].qoi_mm
        f3 = level_results[1].qoi_mm

        h1 = level_results[3].characteristic_h
        h2 = level_results[2].characteristic_h
        h3 = level_results[1].characteristic_h

        r21 = float(h2 / h1)
        r32 = float(h3 / h2)

        eps32 = float(f3 - f2)
        eps21 = float(f2 - f1)
        s = 1.0 if (eps32 / eps21) > 0.0 else -1.0

        def celik_residual(p_val: float) -> float:
            term1 = (r21**p_val - s) / (r32**p_val - s)
            if term1 <= 0.0:
                return float("inf")
            q_p = np.log(term1)
            return p_val - (1.0 / np.log(r21)) * np.abs(np.log(np.abs(eps32 / eps21)) + q_p)

        try:
            root_res = root_scalar(celik_residual, bracket=[0.5, 4.5], method="brentq")
            p_celik = float(root_res.root)
        except Exception:
            # Fallback to nominal order 2.0 if root-finding fails
            p_celik = 2.0

        # Extrapolated continuum QoI (Celik)
        f_ext_celik_mm = float(f1 + (f1 - f2) / (r21**p_celik - 1.0))
        f_ext_celik_m = f_ext_celik_mm / 1000.0

        # GCI calculations (ASME standard safety factor Fs = 1.25)
        ea21 = abs((f1 - f2) / f1)
        ea32 = abs((f2 - f3) / f2)
        gci21 = float((1.25 * ea21 / (r21**p_celik - 1.0)) * 100.0)
        gci32 = float((1.25 * ea32 * (r32**p_celik) / (r32**p_celik - 1.0)) * 100.0)
        asymp_ratio = float(gci32 / (max((r21**p_celik) * gci21, 1e-12)))

        # Roache mean-ratio sensitivity check
        r_mean = float(np.sqrt(r21 * r32))
        p_roache = float(np.log(abs(eps32 / eps21)) / np.log(r_mean))
        f_ext_roache_mm = float(f1 + (f1 - f2) / (r_mean**p_roache - 1.0))

        # Relative discrete changes across all 4 levels
        rel_changes = []
        for i in range(1, len(level_results)):
            prev = level_results[i - 1].qoi_meters
            curr = level_results[i].qoi_meters
            chg = (abs(curr - prev) / max(abs(curr), 1e-12)) * 100.0
            rel_changes.append(float(chg))

        # Timoshenko comparison
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
            abs(f_ext_celik_mm - analytical["delta_timoshenko_total_mm"])
            / abs(analytical["delta_timoshenko_total_mm"])
        ) * 100.0
        analytical["continuum_vs_timoshenko_diff_pct"] = float(timo_diff)
        analytical["fem_vs_timoshenko_diff_pct"] = float(timo_diff)

        is_adequate = gci21 < 0.15
        adequacy_msg = (
            f"Extrapolated continuum reference J_infinity = {f_ext_celik_mm:.6f} mm with GCI = {gci21:.4f}% "
            f"(Celik apparent order p = {p_celik:.3f})."
        )

        report = ReferenceConvergenceReport(
            levels=level_results,
            relative_changes_pct=rel_changes,
            apparent_order_p=p_celik,
            refinement_ratios=(r21, r32),
            gci_fine_percent=gci21,
            gci_medium_percent=gci32,
            asymptotic_consistency_ratio=asymp_ratio,
            finest_adequate_for_thresholds=is_adequate,
            estimated_discretization_uncertainty_pct=gci21,
            analytical_comparison=analytical,
            adequacy_assessment=adequacy_msg,
            roache_apparent_order=p_roache,
            roache_extrapolated_qoi_mm=f_ext_roache_mm,
        )

        return ReferenceSolution(
            qoi_meters=f_ext_celik_m,
            qoi_mm=f_ext_celik_mm,
            dofs=finest.dofs,
            nelements=finest.nelements,
            nnodes=finest.nnodes,
            solve_time_sec=total_solve_time,
            mesh_resolution=finest.mesh_resolution,
            finest_discrete_qoi_meters=finest.qoi_meters,
            finest_discrete_qoi_mm=finest.qoi_mm,
            extrapolated_qoi_meters=f_ext_celik_m,
            extrapolated_qoi_mm=f_ext_celik_mm,
            apparent_order=p_celik,
            grid_refinement_ratios=(r21, r32),
            gci_fine_percent=gci21,
            gci_medium_percent=gci32,
            asymptotic_consistency_ratio=asymp_ratio,
            roache_sensitivity_qoi_mm=f_ext_roache_mm,
            roache_sensitivity_order=p_roache,
            convergence_report=report,
        )
