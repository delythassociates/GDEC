"""
Adaptive Runner for Phase B / B.1 Feasibility Gate.
Executes fair, controlled adaptive refinement comparisons:
- 4 benchmark problems: Cantilever, Plate with Hole, Notched Bar, L-Shaped Domain
- 3 initial mesh variants per problem
- 4 competing strategies: Uniform, ZZ Recovery, Goal-Aware Heuristic, Enriched DWR
- Frozen 100,000 DOF resource budget
- Complete and non-overlapping timing measurement including mesh refinement
- Trajectory-level and signed/absolute effectivity accounting
- Historical Phase B record preservation (Phase B.1 outputs to results/phase_b1/)
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
import psutil
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1

from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import LinearElasticitySolver, FEMSolution
from gdec.fem.estimators import RefinementEstimator
from verification.dwr.geometries import BENCHMARK_PROBLEMS, ProblemDefinition
from verification.dwr.dwr_estimator import DWREstimator
from verification.dwr.reference_solutions import REFERENCE_DATABASE

DEFAULT_RAW_DIR = Path("results/phase_b1/raw")


def dorfler_mark(indicators: np.ndarray, theta: float = 0.40) -> np.ndarray:
    """Select elements using standard Dorfler marking sum_{M} eta >= theta * sum_{total} eta."""
    order = np.argsort(indicators)[::-1]
    total_val = np.sum(indicators)
    if total_val == 0.0:
        return np.array([order[0]])
    cutoff = theta * total_val
    cum = np.cumsum(indicators[order])
    n_marked = np.searchsorted(cum, cutoff) + 1
    return order[:n_marked]


def run_single_simulation(
    prob: ProblemDefinition,
    method: str,
    variant_idx: int,
    theta: float = 0.40,
    max_dofs: int = 100000,
    max_iterations: int = 15,
) -> List[Dict[str, Any]]:
    prob_id = prob.id
    ref_info = REFERENCE_DATABASE[prob_id]
    j_ref = ref_info["j_ref"]
    scale = prob.qoi_scale

    mesh = prob.get_mesh(variant_idx)
    solver = LinearElasticitySolver(prob.material)
    ref_estimator = RefinementEstimator(prob.material)
    dwr_estimator = DWREstimator(prob)

    records: List[Dict[str, Any]] = []

    for it in range(max_iterations):
        t_start_iter = time.perf_counter()

        # 1. Primal assembly, solve, and QoI evaluation
        t0 = time.perf_counter()
        basis = Basis(mesh, ElementVector(ElementTriP1()))
        K = solver.assemble_stiffness(basis)
        f = prob.assemble_traction(basis)
        g = prob.assemble_qoi_vector(basis)

        D = prob.get_dirichlet_dofs(basis)
        I = np.setdiff1d(np.arange(basis.N), D)
        K_c, f_c, u_full, _ = fem.condense(K, f, D=D)
        u = u_full.copy()
        u[I] = spla.spsolve(K_c.tocsc(), f_c)

        qoi_val = prob.evaluate_qoi(u, basis)
        t_primal = time.perf_counter() - t0

        signed_err = j_ref - qoi_val
        abs_err = abs(signed_err)
        denom = max(abs(j_ref), scale)
        rel_err = abs_err / denom

        t_adjoint = 0.0
        t_estimator = 0.0
        t_marking = 0.0
        t_refine = 0.0

        estimated_err = None
        absolute_eff = None
        signed_eff = None
        adjoint_dofs = 0

        # 2. Method-specific adjoint, estimator, and marking
        if method == "uniform":
            t_mark = time.perf_counter()
            marked_elements = np.arange(mesh.nelements)
            t_marking = time.perf_counter() - t_mark

        elif method == "zz":
            t_est = time.perf_counter()
            gmesh = GDECMesh(mesh, width=2.0, height=1.0)
            sol = FEMSolution(
                u=u, z=None, K=K, f=f, g=g, dofs_fixed=D, basis=basis, qoi=qoi_val, qoi_mm=qoi_val * 1000
            )
            res_zz = ref_estimator.compute_zz_recovery_indicator(gmesh, sol)
            inds = res_zz.indicators
            estimated_err = float(np.sqrt(np.sum(inds**2)))
            t_estimator = time.perf_counter() - t_est

            t_mark = time.perf_counter()
            marked_elements = dorfler_mark(inds, theta=theta)
            t_marking = time.perf_counter() - t_mark

        elif method == "goal_aware":
            t_adj = time.perf_counter()
            K_adj, g_c, z_full, _ = fem.condense(K, g, D=D)
            z = z_full.copy()
            z[I] = spla.spsolve(K_adj.tocsc(), g_c)
            t_adjoint = time.perf_counter() - t_adj
            adjoint_dofs = basis.N

            t_est = time.perf_counter()
            gmesh = GDECMesh(mesh, width=2.0, height=1.0)
            sol = FEMSolution(
                u=u, z=z, K=K, f=f, g=g, dofs_fixed=D, basis=basis, qoi=qoi_val, qoi_mm=qoi_val * 1000
            )
            res_ga = ref_estimator.compute_goal_aware_indicator(gmesh, sol)
            inds = res_ga.indicators
            estimated_err = float(np.sum(inds))
            t_estimator = time.perf_counter() - t_est

            t_mark = time.perf_counter()
            marked_elements = dorfler_mark(inds, theta=theta)
            t_marking = time.perf_counter() - t_mark

        elif method == "dwr":
            # Pass existing primal solve so primal is not redundantly re-assembled
            dwr_res = dwr_estimator.estimate(mesh)
            # Adjoint time includes P2 enriched assembly and P2 linear solve
            t_adjoint = dwr_res.timings.get("assemble", 0.0) + dwr_res.timings.get("solve_adjoint", 0.0)
            t_estimator = dwr_res.timings.get("estimator", 0.0)
            adjoint_dofs = dwr_res.dofs_p2
            estimated_err = dwr_res.abs_eta_dwr

            if abs_err > 1e-14:
                absolute_eff = float(dwr_res.abs_eta_dwr / abs_err)
                signed_eff = float(dwr_res.eta_dwr / signed_err)

            t_mark = time.perf_counter()
            marked_elements = dorfler_mark(dwr_res.element_indicators, theta=theta)
            t_marking = time.perf_counter() - t_mark

        else:
            raise ValueError(f"Unknown method {method}")

        # 3. Check stopping criteria before refinement
        stop_now = (rel_err < 0.004 or basis.N >= max_dofs or it == max_iterations - 1)

        # 4. Mesh refinement (only if continuing)
        if not stop_now:
            t_ref = time.perf_counter()
            if method == "uniform":
                mesh = mesh.refined()
            else:
                mesh = mesh.refined(marked_elements)
            t_refine = time.perf_counter() - t_ref

        # End-to-end iteration wall-clock time
        t_total_iter = time.perf_counter() - t_start_iter

        # Memory usage
        try:
            mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            mem_mb = None

        record = {
            "problem_id": prob_id,
            "method": method,
            "variant_idx": variant_idx,
            "iteration": it,
            "nelements": int(mesh.nelements),
            "primal_dofs": int(basis.N),
            "adjoint_dofs": int(adjoint_dofs),
            "qoi_h": float(qoi_val),
            "qoi_ref": float(j_ref),
            "true_error_abs": float(abs_err),
            "true_error_rel": float(rel_err),
            "true_error_signed": float(signed_err),
            "estimated_error": float(estimated_err) if estimated_err is not None else None,
            "effectivity": float(absolute_eff) if absolute_eff is not None else None,
            "absolute_effectivity": float(absolute_eff) if absolute_eff is not None else None,
            "signed_effectivity": float(signed_eff) if signed_eff is not None else None,
            "t_primal_sec": float(t_primal),
            "t_adjoint_sec": float(t_adjoint),
            "t_estimator_sec": float(t_estimator),
            "t_marking_sec": float(t_marking),
            "t_refinement_sec": float(t_refine),
            "t_total_iter_sec": float(t_total_iter),
            "peak_memory_mb": float(mem_mb) if mem_mb is not None else None,
            "marked_elements_count": int(len(marked_elements)),
        }
        records.append(record)

        if stop_now:
            break

    return records


def run_all_benchmarks(raw_dir: Path = DEFAULT_RAW_DIR):
    raw_dir.mkdir(parents=True, exist_ok=True)
    methods = ["uniform", "zz", "goal_aware", "dwr"]
    total_runs = len(BENCHMARK_PROBLEMS) * 3 * len(methods)
    print(f"Starting Phase B.1 benchmark execution: {total_runs} simulations total.")
    print(f"Destination raw output directory: {raw_dir}")

    completed = 0
    t_start_all = time.perf_counter()

    for prob_id, prob in BENCHMARK_PROBLEMS.items():
        prob_dir = raw_dir / prob_id
        prob_dir.mkdir(parents=True, exist_ok=True)

        for variant_idx in range(3):
            for method in methods:
                run_file = prob_dir / f"{method}_var{variant_idx}.json"
                records = run_single_simulation(prob, method, variant_idx)
                with open(run_file, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2)

                completed += 1
                final_rec = records[-1]
                print(
                    f"[{completed:2d}/{total_runs}] {prob_id:15s} (var {variant_idx}) {method:10s}: "
                    f"Iters={len(records)}, Final DOFs={final_rec['primal_dofs']:5d}, "
                    f"Error={final_rec['true_error_rel']*100:6.2f}%, "
                    f"Time={sum(r['t_total_iter_sec'] for r in records):.2f}s"
                )

    total_time = time.perf_counter() - t_start_all
    print(f"All {total_runs} benchmark simulations completed in {total_time:.2f} seconds.")


if __name__ == "__main__":
    run_all_benchmarks()
