"""
A2.6: Refinement Verification.
Verifies topological conformity and geometric mesh quality across 8 adaptive refinement cycles
for both Goal-Aware and ZZ Recovery refinement strategies on the cantilever benchmark:
1. Conforming topology: interior edges shared by exactly 2 triangles, boundary edges by 1.
2. Zero hanging nodes: every triangle vertex is a legitimate mesh node.
3. Interior vertex angle sum: sum of incident angles around interior vertices equals 2*pi +/- 1e-9.
4. Total area conservation: |sum(A_e) - L*H| / (L*H) <= 1e-12.
5. Minimum angle preservation: theta_min_k >= max(10.0 deg, 0.5 * theta_min_0).
"""

import json
from pathlib import Path
import numpy as np
import pytest

from gdec.compiler.compiler import GDECCompiler
from gdec.core.planner import ExecutionPlanner
from gdec.core.runtime import GDECRuntime
from gdec.fem.mesh import GDECMesh
from gdec.fem.adaptivity import MeshAdaptor
from verification.mesh_utils import compute_mesh_metrics

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


def check_mesh_conformity_and_angles(
    mesh: GDECMesh,
    width: float,
    height: float,
) -> dict:
    """
    Check topological conformity, edge sharing, hanging nodes, and interior angle sums.
    """
    p = mesh.mesh.p
    t = mesh.mesh.t
    n_nodes = p.shape[1]
    n_elements = t.shape[1]
    tol = 1e-10

    # Classify boundary nodes
    is_bnd_node = (
        (np.abs(p[0] - 0.0) < tol) |
        (np.abs(p[0] - width) < tol) |
        (np.abs(p[1] - 0.0) < tol) |
        (np.abs(p[1] - height) < tol)
    )
    interior_nodes = np.where(~is_bnd_node)[0]

    # Edge sharing
    edge_counts = {}
    for e in range(n_elements):
        for i in range(3):
            nA = int(t[i, e])
            nB = int(t[(i + 1) % 3, e])
            edge = tuple(sorted((nA, nB)))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    bad_interior_edges = 0
    bad_boundary_edges = 0
    for (nA, nB), count in edge_counts.items():
        on_same_bnd = (
            (abs(p[0, nA] - 0.0) < tol and abs(p[0, nB] - 0.0) < tol) or
            (abs(p[0, nA] - width) < tol and abs(p[0, nB] - width) < tol) or
            (abs(p[1, nA] - 0.0) < tol and abs(p[1, nB] - 0.0) < tol) or
            (abs(p[1, nA] - height) < tol and abs(p[1, nB] - height) < tol)
        )
        if on_same_bnd:
            if count != 1:
                bad_boundary_edges += 1
        else:
            if count != 2:
                bad_interior_edges += 1

    # Interior vertex angle sums
    node_angle_sum = np.zeros(n_nodes)
    for e in range(n_elements):
        nodes = t[:, e]
        coords = p[:, nodes]
        for i in range(3):
            v = coords[:, i]
            v_prev = coords[:, (i - 1) % 3]
            v_next = coords[:, (i + 1) % 3]
            d1 = v_prev - v
            d2 = v_next - v
            denom = np.linalg.norm(d1) * np.linalg.norm(d2)
            cos_th = np.dot(d1, d2) / max(denom, 1e-15)
            cos_th = np.clip(cos_th, -1.0, 1.0)
            node_angle_sum[nodes[i]] += np.arccos(cos_th)

    if len(interior_nodes) > 0:
        angle_diffs = np.abs(node_angle_sum[interior_nodes] - 2.0 * np.pi)
        max_angle_sum_err = float(np.max(angle_diffs))
    else:
        max_angle_sum_err = 0.0

    # Total area conservation
    areas = mesh.element_areas
    total_area = float(np.sum(areas))
    domain_area = width * height
    area_rel_err = float(abs(total_area - domain_area) / domain_area)

    return {
        "n_nodes": n_nodes,
        "n_elements": n_elements,
        "bad_interior_edges": bad_interior_edges,
        "bad_boundary_edges": bad_boundary_edges,
        "hanging_nodes": bad_interior_edges,  # Conforming topology implies 0 hanging nodes
        "max_interior_angle_sum_err_rad": max_angle_sum_err,
        "area_relative_error": area_rel_err,
        "total_area": total_area,
    }


@pytest.mark.parametrize("strategy", ["goal_aware", "recovery"])
def test_a2_6_adaptive_refinement(strategy: str):
    test_id = f"A2.6_refinement_{strategy}"

    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    ir = comp.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir, override_strategy=strategy)
    plan.max_iterations = 9
    plan.max_dofs_budget = 200000
    plan.accuracy_target_pct = 1e-6  # Ensure running full 8 cycles

    runtime = GDECRuntime(plan, ir)
    current_mesh = GDECMesh.create_cantilever_mesh(
        width=ir.geometry.width, height=ir.geometry.height, nx=plan.initial_mesh_shape[0], ny=plan.initial_mesh_shape[1]
    )

    m0_metrics = compute_mesh_metrics(current_mesh.mesh)
    theta_0 = m0_metrics["min_angle_deg"]
    min_allowed_angle = max(10.0, 0.5 * theta_0)

    cycles_data = []
    all_conforming = True

    for cycle in range(8):
        sol = runtime.solver.solve(
            gdec_mesh=current_mesh,
            loads=runtime.loads,
            fixed_boundaries=runtime.fixed_bcs,
            qoi_boundary=ir.objective.boundary,
            qoi_component=ir.objective.component,
            solve_adjoint=(strategy == "goal_aware"),
            reuse_factorization=True,
        )

        if strategy == "goal_aware":
            ind_res = runtime.estimator.compute_goal_aware_indicator(current_mesh, sol, cost_aware=False)
        else:
            ind_res = runtime.estimator.compute_zz_recovery_indicator(current_mesh, sol)

        marked = MeshAdaptor.mark_elements(
            indicator_result=ind_res,
            strategy=strategy,
            marking_fraction=plan.marking_fraction,
            current_dofs=sol.basis.N,
            max_dofs_budget=plan.max_dofs_budget,
        )

        current_mesh = current_mesh.refine_elements(marked)
        metrics = compute_mesh_metrics(current_mesh.mesh)
        conf = check_mesh_conformity_and_angles(current_mesh, ir.geometry.width, ir.geometry.height)

        cycle_pass = (
            conf["bad_interior_edges"] == 0 and
            conf["bad_boundary_edges"] == 0 and
            conf["hanging_nodes"] == 0 and
            conf["max_interior_angle_sum_err_rad"] <= 1e-9 and
            conf["area_relative_error"] <= 1e-12 and
            metrics["min_angle_deg"] >= min_allowed_angle
        )
        if not cycle_pass:
            all_conforming = False

        cycles_data.append({
            "cycle": cycle + 1,
            "elements": conf["n_elements"],
            "nodes": conf["n_nodes"],
            "min_angle_deg": float(metrics["min_angle_deg"]),
            "max_angle_deg": float(metrics["max_angle_deg"]),
            "max_aspect_ratio": float(metrics["max_aspect_ratio"]),
            "bad_interior_edges": conf["bad_interior_edges"],
            "bad_boundary_edges": conf["bad_boundary_edges"],
            "hanging_nodes": conf["hanging_nodes"],
            "max_interior_angle_sum_err_rad": conf["max_interior_angle_sum_err_rad"],
            "area_relative_error": conf["area_relative_error"],
            "pass": cycle_pass,
        })

    res = {
        "id": test_id,
        "computed": {
            "strategy": strategy,
            "cycles_completed": len(cycles_data),
            "initial_min_angle_deg": float(theta_0),
            "min_allowed_angle_deg": float(min_allowed_angle),
            "final_elements": cycles_data[-1]["elements"],
            "final_min_angle_deg": cycles_data[-1]["min_angle_deg"],
            "cycles": cycles_data,
        },
        "threshold": {
            "interior_edge_sharing": "exactly 2 triangles",
            "hanging_nodes": 0,
            "interior_vertex_angle_sum_abs_tol": 1e-9,
            "element_area_sum_rel_tol": 1e-12,
            "min_angle_deg": float(min_allowed_angle),
        },
        "pass": all_conforming,
        "failure_class": None if all_conforming else "NUM_FAIL",
        "details": f"8-cycle adaptive refinement conformity and quality verification for {strategy}.",
    }
    _record_result(res, "A2_6_refinement.json")

    assert all_conforming, f"Conformity or mesh quality check failed in {strategy} refinement."
