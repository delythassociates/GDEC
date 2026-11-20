"""
Unit and Integration Tests for Phase B.1.1 Accounting Corrections.
Verifies:
1. Complete component timing decomposition including internal DWR primal recomputation.
2. Time-to-target calculation strictly excludes refinement performed after target attainment.
3. Mesh and basis state consistency (solved mesh vs next mesh).
4. No double counting of nested timings.
5. Non-negativity of all timing components.
"""

import pytest
import numpy as np
from verification.dwr.geometries import CantileverProblem
from verification.dwr.adaptive_runner import run_single_simulation
from verification.dwr.evaluator import find_target_metrics


def test_time_to_target_excludes_post_target_refinement():
    """
    Verifies that for a simulation meeting a target, the cumulative time to target
    excludes the mesh refinement performed after that target was attained.
    """
    # Create mock records simulating an adaptive run
    records = [
        {
            "iteration": 0,
            "primal_dofs": 100,
            "solved_mesh_elements": 50,
            "true_error_rel": 0.05,
            "t_primal_sec": 0.10,
            "t_adjoint_sec": 0.0,
            "t_estimator_sec": 0.02,
            "t_marking_sec": 0.01,
            "t_refinement_sec": 0.05,
            "t_total_iter_sec": 0.19,  # 0.10 + 0.02 + 0.01 + 0.05 + 0.01 overhead
        },
        {
            "iteration": 1,
            "primal_dofs": 200,
            "solved_mesh_elements": 100,
            "true_error_rel": 0.008,  # Meets 1.0% target (<= 0.01)
            "t_primal_sec": 0.20,
            "t_adjoint_sec": 0.0,
            "t_estimator_sec": 0.04,
            "t_marking_sec": 0.02,
            "t_refinement_sec": 0.15,  # Refinement to produce iteration 2 (NOT needed for iter 1 target!)
            "t_total_iter_sec": 0.42,
        },
    ]

    target = 0.01
    met = find_target_metrics(records, target)
    assert met is not None, "Target should be found at iteration 1"

    # Iteration 0 total time was 0.19.
    # Iteration 1 work to reach target: 0.42 - 0.15 = 0.27.
    # Total time to target must be 0.19 + 0.27 = 0.46.
    # Total including post-target refinement would have been 0.19 + 0.42 = 0.61.
    assert np.isclose(met["t_total_cumulative_sec"], 0.46, atol=1e-6)
    assert np.isclose(met["t_target_excluding_post_refine_sec"], 0.46, atol=1e-6)
    assert np.isclose(met["t_target_including_post_refine_sec"], 0.61, atol=1e-6)
    assert np.isclose(met["post_target_refinement_deducted_sec"], 0.15, atol=1e-6)


def test_dwr_internal_primal_decomposition_non_overlapping():
    """
    Verifies that for DWR, the internal primal recomputation is explicitly exposed
    and timing components are non-negative and non-overlapping.
    """
    prob = CantileverProblem()
    records = run_single_simulation(prob, "dwr", variant_idx=0, max_iterations=2)
    assert len(records) >= 1

    for r in records:
        t_outer_primal = r.get("t_primal_outer_sec", r["t_primal_sec"])
        t_int_primal = r.get("t_dwr_internal_primal_sec", 0.0)
        t_p2_asm = r.get("t_p2_assembly_sec", 0.0)
        t_p2_adj = r.get("t_p2_adjoint_solve_sec", 0.0)
        t_est = r["t_estimator_sec"]
        t_mark = r["t_marking_sec"]
        t_ref = r["t_refinement_sec"]
        t_total = r["t_total_iter_sec"]

        # All components must be non-negative
        assert t_outer_primal >= 0.0
        assert t_int_primal >= 0.0
        assert t_p2_asm >= 0.0
        assert t_p2_adj >= 0.0
        assert t_est >= 0.0
        assert t_mark >= 0.0
        assert t_ref >= 0.0

        # Total iteration time must bound the sum of all distinct measured phases
        # outer primal + internal DWR work + marking + refinement
        sum_components = t_outer_primal + t_p2_asm + t_p2_adj + t_est + t_mark + t_ref
        assert t_total >= sum_components - 1e-6


def test_mesh_telemetry_consistency():
    """
    Verifies that solved_mesh_elements and solved_mesh_dofs match the basis and mesh
    that were actually solved, and next_mesh_elements reflects post-refinement state.
    """
    prob = CantileverProblem()
    records = run_single_simulation(prob, "zz", variant_idx=0, max_iterations=2)
    assert len(records) >= 2

    rec0 = records[0]
    rec1 = records[1]

    assert rec0["solved_mesh_elements"] > 0
    assert rec0["solved_mesh_dofs"] > 0
    assert rec0["next_mesh_elements"] is not None
    # Mesh 1 solved elements must equal Mesh 0 next_mesh_elements!
    assert rec1["solved_mesh_elements"] == rec0["next_mesh_elements"]
    assert rec1["solved_mesh_elements"] > rec0["solved_mesh_elements"]
