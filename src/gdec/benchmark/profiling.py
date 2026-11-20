"""
Runtime computational profiling and stage breakdown for GDEC v0.2.
Performs repeated runs with warm-up, calculates medians and dispersions,
and measures factorization reuse speedup.
"""

from __future__ import annotations
import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import psutil

from gdec.language.ir import ProblemIR
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.boundary_conditions import parse_boundary_conditions, parse_loads


@dataclass
class StageTimingStats:
    stage_name: str
    median_ms: float
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    percentage_of_total: float


@dataclass
class ProfilingReport:
    dofs: int
    nelements: int
    repetitions: int
    stages: Dict[str, StageTimingStats]
    total_time_median_ms: float
    peak_memory_mb: float
    factorization_reuse_baseline_ms: float
    factorization_reuse_optimized_ms: float
    factorization_reuse_speedup: float


class RuntimeProfiler:
    @classmethod
    def profile(
        cls, ir: ProblemIR, grid_size: Tuple[int, int] = (40, 15), repetitions: int = 5
    ) -> ProfilingReport:
        geo = ir.geometry
        mat = ir.material
        c = ConstitutiveTensor.from_properties(
            E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
        )
        solver = LinearElasticitySolver(c)
        loads = parse_loads(ir.loads)
        bcs = parse_boundary_conditions(ir.boundary_conditions)

        mesh = GDECMesh.create_cantilever_mesh(
            width=geo.width, height=geo.height, nx=grid_size[0], ny=grid_size[1]
        )

        # Warm-up run
        _ = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solve_adjoint=True, reuse_factorization=True)

        stage_timings: Dict[str, List[float]] = {
            "Mesh Generation": [],
            "FEM Matrix Assembly": [],
            "BC Condensation": [],
            "Sparse Factorization": [],
            "Primal Solve": [],
            "Adjoint Solve": [],
            "Postprocessing": [],
        }

        from gdec.fem.postprocess import PostProcessor
        postprocessor = PostProcessor(c)
        proc = psutil.Process()

        baseline_solve_times = []
        optimized_solve_times = []

        for _ in range(repetitions):
            # Mesh gen
            t0 = time.perf_counter()
            m = GDECMesh.create_cantilever_mesh(
                width=geo.width, height=geo.height, nx=grid_size[0], ny=grid_size[1]
            )
            stage_timings["Mesh Generation"].append((time.perf_counter() - t0) * 1000.0)

            # Solve with reuse
            sol = solver.solve(
                m, loads=loads, fixed_boundaries=bcs, solve_adjoint=True, reuse_factorization=True
            )
            stage_timings["FEM Matrix Assembly"].append(sol.assembly_time_sec * 1000.0)
            stage_timings["BC Condensation"].append(sol.condensation_time_sec * 1000.0)
            stage_timings["Sparse Factorization"].append(sol.factorization_time_sec * 1000.0)
            stage_timings["Primal Solve"].append(sol.primal_solve_time_sec * 1000.0)
            stage_timings["Adjoint Solve"].append(sol.adjoint_solve_time_sec * 1000.0)

            optimized_solve_times.append(
                (sol.factorization_time_sec + sol.primal_solve_time_sec + sol.adjoint_solve_time_sec) * 1000.0
            )

            # Measure baseline solve without factorization reuse
            sol_base = solver.solve(
                m, loads=loads, fixed_boundaries=bcs, solve_adjoint=True, reuse_factorization=False
            )
            baseline_solve_times.append(
                (sol_base.total_solver_time_sec - sol_base.assembly_time_sec) * 1000.0
            )

            # Postprocess
            t0 = time.perf_counter()
            _ = postprocessor.process(m, sol)
            stage_timings["Postprocessing"].append((time.perf_counter() - t0) * 1000.0)

        # Aggregate statistics
        total_medians = sum(float(np.median(vals)) for vals in stage_timings.values())
        stats_dict = {}
        for name, vals in stage_timings.items():
            med = float(np.median(vals))
            stats_dict[name] = StageTimingStats(
                stage_name=name,
                median_ms=med,
                mean_ms=float(np.mean(vals)),
                std_ms=float(np.std(vals)),
                min_ms=float(np.min(vals)),
                max_ms=float(np.max(vals)),
                percentage_of_total=(med / max(total_medians, 1e-6)) * 100.0,
            )

        med_base = float(np.median(baseline_solve_times))
        med_opt = float(np.median(optimized_solve_times))
        speedup = med_base / max(med_opt, 1e-6)
        peak_mem = proc.memory_info().rss / (1024.0 * 1024.0)

        return ProfilingReport(
            dofs=mesh.nnodes * 2,
            nelements=mesh.nelements,
            repetitions=repetitions,
            stages=stats_dict,
            total_time_median_ms=total_medians,
            peak_memory_mb=peak_mem,
            factorization_reuse_baseline_ms=med_base,
            factorization_reuse_optimized_ms=med_opt,
            factorization_reuse_speedup=speedup,
        )
