"""
Tests for refinement indicators and error estimators.
"""

import numpy as np
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.estimators import RefinementEstimator


def test_estimator_indicators():
    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption="plane_stress", thickness=0.02)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)

    loads = [("right", 0.0, -1.0e6)]
    bcs = [("left", ["x", "y"])]
    sol = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solve_adjoint=True)

    # 1. Uniform
    unif_res = estimator.compute_uniform_indicator(mesh)
    assert len(unif_res.indicators) == mesh.nelements
    assert np.all(unif_res.indicators == 1.0)

    # 2. ZZ Recovery
    zz_res = estimator.compute_zz_recovery_indicator(mesh, sol)
    assert len(zz_res.indicators) == mesh.nelements
    assert np.all(zz_res.indicators >= 0.0)
    assert np.max(zz_res.indicators) > 0.0

    # 3. Goal-Aware Heuristic
    goal_res = estimator.compute_goal_aware_indicator(mesh, sol, cost_aware=True)
    assert len(goal_res.indicators) == mesh.nelements
    assert np.all(goal_res.indicators >= 0.0)
    assert np.max(goal_res.indicators) > 0.0
    assert np.all(goal_res.priorities > 0.0)

    # 4. Goal-Oriented DWR
    dwr_res = estimator.compute_dwr_indicator(mesh, sol, loads=loads, cost_aware=True)
    assert len(dwr_res.indicators) == mesh.nelements
    assert np.all(dwr_res.indicators >= 0.0)
    assert np.max(dwr_res.indicators) > 0.0
    assert dwr_res.details["signed_qoi_error_estimate"] > 0.0
    assert dwr_res.details["classification"] == "goal_oriented_dwr_estimator"
    assert dwr_res.details["is_certified_dwr_bound"] is False

    # 5. Residual Energy Norm
    res_energy = estimator.compute_residual_energy_indicator(mesh, sol, loads=loads)
    assert len(res_energy.indicators) == mesh.nelements
    assert np.all(res_energy.indicators >= 0.0)
    assert np.max(res_energy.indicators) > 0.0
