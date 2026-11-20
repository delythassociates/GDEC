"""
Scalability testing framework for GDEC v0.2.
Benchmarks sparse system scaling from ~10k DOFs up to 200k DOFs,
evaluating execution time, memory footprint, assembly vs solve scaling,
and reporting hardware bounds gracefully.
"""

from __future__ import annotations
import time
import psutil
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from gdec.language.ir import ProblemIR
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.boundary_conditions import parse_boundary_conditions, parse_loads


@dataclass
class ScaleDataPoint:
    target_dofs: int
    actual_dofs: int
    nelements: int
    grid_resolution: Tuple[int, int]
    assembly_time_sec: float
    factorization_time_sec: float
    primal_solve_time_sec: float
    adjoint_solve_time_sec: float
    total_time_sec: float
    peak_memory_mb: float
    qoi_mm: float
    completed: bool
    status_note: str


@dataclass
class ScalingExperimentResult:
    problem_name: str
    points: List[ScaleDataPoint]
    max_dofs_achieved: int
    hardware_limit_encountered: bool
    hardware_limit_reason: str


class ScalabilityRunner:
    DEFAULT_SCALE_TARGETS = [10000, 50000, 100000, 200000]

    @classmethod
    def run_scaling(
        cls,
        ir: ProblemIR,
        scale_targets: Optional[List[int]] = None,
        max_ram_headroom_gb: float = 2.0,
    ) -> ScalingExperimentResult:
        if scale_targets is None:
            scale_targets = cls.DEFAULT_SCALE_TARGETS

        geo = ir.geometry
        mat = ir.material
        c = ConstitutiveTensor.from_properties(
            E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
        )
        solver = LinearElasticitySolver(c)
        loads = parse_loads(ir.loads)
        bcs = parse_boundary_conditions(ir.boundary_conditions)

        aspect = geo.width / geo.height
        proc = psutil.Process()

        points: List[ScaleDataPoint] = []
        limit_encountered = False
        limit_reason = ""

        for tgt in scale_targets:
            # Check available system RAM
            mem_info = psutil.virtual_memory()
            avail_gb = mem_info.available / (1024.0**3)

            # Heuristic memory limit: 200k DOFs in 2D triangular sparse LU requires ~1.5 - 2.5 GB
            if tgt >= 150000 and avail_gb < max_ram_headroom_gb:
                limit_encountered = True
                limit_reason = (
                    f"Scale {tgt:,} DOFs halted: available system RAM ({avail_gb:.2f} GB) "
                    f"below safety headroom threshold ({max_ram_headroom_gb} GB)."
                )
                points.append(
                    ScaleDataPoint(
                        target_dofs=tgt,
                        actual_dofs=0,
                        nelements=0,
                        grid_resolution=(0, 0),
                        assembly_time_sec=0.0,
                        factorization_time_sec=0.0,
                        primal_solve_time_sec=0.0,
                        adjoint_solve_time_sec=0.0,
                        total_time_sec=0.0,
                        peak_memory_mb=proc.memory_info().rss / (1024.0**2),
                        qoi_mm=0.0,
                        completed=False,
                        status_note=limit_reason,
                    )
                )
                break

            ny = max(8, int(np.sqrt(tgt / (2.0 * aspect))))
            nx = int(round(ny * aspect))

            t0 = time.perf_counter()
            try:
                mesh = GDECMesh.create_cantilever_mesh(
                    width=geo.width, height=geo.height, nx=nx, ny=ny
                )
                sol = solver.solve(
                    mesh,
                    loads=loads,
                    fixed_boundaries=bcs,
                    qoi_boundary=ir.objective.boundary,
                    qoi_component=ir.objective.component,
                    solve_adjoint=True,
                    reuse_factorization=True,
                )
                t_tot = time.perf_counter() - t0
                peak_mem = proc.memory_info().rss / (1024.0**2)

                points.append(
                    ScaleDataPoint(
                        target_dofs=tgt,
                        actual_dofs=sol.basis.N,
                        nelements=mesh.nelements,
                        grid_resolution=(nx, ny),
                        assembly_time_sec=sol.assembly_time_sec,
                        factorization_time_sec=sol.factorization_time_sec,
                        primal_solve_time_sec=sol.primal_solve_time_sec,
                        adjoint_solve_time_sec=sol.adjoint_solve_time_sec,
                        total_time_sec=t_tot,
                        peak_memory_mb=peak_mem,
                        qoi_mm=sol.qoi_mm,
                        completed=True,
                        status_note=f"Successfully solved {sol.basis.N:,} DOFs in {t_tot:.2f}s.",
                    )
                )
            except MemoryError as e:
                limit_encountered = True
                limit_reason = f"MemoryError at {tgt:,} DOFs: {e}"
                points.append(
                    ScaleDataPoint(
                        target_dofs=tgt,
                        actual_dofs=0,
                        nelements=0,
                        grid_resolution=(nx, ny),
                        assembly_time_sec=0.0,
                        factorization_time_sec=0.0,
                        primal_solve_time_sec=0.0,
                        adjoint_solve_time_sec=0.0,
                        total_time_sec=0.0,
                        peak_memory_mb=proc.memory_info().rss / (1024.0**2),
                        qoi_mm=0.0,
                        completed=False,
                        status_note=limit_reason,
                    )
                )
                break
            except Exception as e:
                limit_encountered = True
                limit_reason = f"Execution stopped at {tgt:,} DOFs: {e}"
                break

        max_dofs = max((p.actual_dofs for p in points if p.completed), default=0)
        return ScalingExperimentResult(
            problem_name=ir.name,
            points=points,
            max_dofs_achieved=max_dofs,
            hardware_limit_encountered=limit_encountered,
            hardware_limit_reason=limit_reason,
        )
