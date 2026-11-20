"""
tests/test_v021_corrections.py
Unit and regression tests for GDEC v0.2.1 corrections:
1. Safe Refinement Transaction & strict budget enforcement
2. Goal-aware heuristic relabeling (goal_heuristic_v1) & ZZ area-weighted averaging classification
3. Unsupported backend explicit rejection (CUDA, TPU, HIP, SYCL)
4. Multi-QoI adjoint sensitivity verification against finite differences
"""

import pytest
import numpy as np
import scipy.sparse.linalg as spla

from gdec.language.parser import GDECParser
from gdec.language.semantic import SemanticAnalyzer, GDECSemanticError
from gdec.compiler.compiler import GDECCompiler
from gdec.core.runtime import GDECRuntime
from gdec.core.planner import ExecutionPlanner
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.estimators import RefinementEstimator, GoalOrientedEstimator


def test_transactional_refinement_budget_enforcement():
    """Verify that candidate refinement exceeding budget rolls back to the previous valid mesh."""
    source = """
    problem BudgetTest {
        physics = linear_elasticity
        geometry = rectangle(width=100.0, height=20.0)
        material = isotropic(E=210000.0, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-10.0)
        objective = average_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=0.01)
        budget = max_dofs(500, max_iterations=10)
        adaptivity = goal_aware(fraction=0.4, cost_aware=true)
    }
    """
    compiler = GDECCompiler()
    res = compiler.compile_source(source)
    assert res.success is True
    ir = res.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir)
    runtime = GDECRuntime(plan, ir)
    trace = runtime.execute()

    # The hard budget is 500 DOFs.
    # Every iteration recorded in the trace must strictly respect dofs <= budget.
    for r in trace.iterations:
        assert r.dofs <= 500, f"Iteration {r.iteration} has {r.dofs} DOFs, exceeding hard budget 500!"
    
    # Final iteration must have <= 500 DOFs
    final_record = trace.iterations[-1]
    assert final_record.dofs <= 500
    assert "budget" in trace.stop_reason.lower()


def test_transactional_refinement_severe_underprediction():
    """Verify rollback if cost model underpredicts growth and actual refinement exceeds budget."""
    source = """
    problem UnderpredictTest {
        physics = linear_elasticity
        geometry = rectangle(width=100.0, height=20.0)
        material = isotropic(E=210000.0, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-10.0)
        objective = average_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=0.001)
        budget = max_dofs(254, max_iterations=10)
        adaptivity = goal_aware(fraction=0.8, cost_aware=false)
    }
    """
    compiler = GDECCompiler()
    res = compiler.compile_source(source)
    assert res.success is True
    ir = res.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir)
    runtime = GDECRuntime(plan, ir)
    
    # Mock cost model to claim zero growth so controller allows the step
    runtime.cost_model.predict_additional_dofs = lambda marked, total_elements: 0

    trace = runtime.execute()

    # Budget is 254 DOFs. Initial mesh is 250 DOFs.
    # Refinement produces candidate_dofs = 256 > 254.
    # Transactional rollback aborts and preserves iteration 1 (250 DOFs).
    assert len(trace.iterations) == 1
    assert trace.final_dofs == 250
    assert trace.final_dofs <= 254
    assert trace.converged is False
    assert "exceeds budget" in trace.stop_reason.lower()
    assert "rollback" in trace.stop_reason.lower()


def test_budget_pathway_initial_mesh_above_budget():
    """Verify that if initial mesh exceeds budget, execution aborts before solving with no violation."""
    source = """
    problem InfeasibleInitial {
        physics = linear_elasticity
        geometry = rectangle(width=100.0, height=20.0)
        material = isotropic(E=210000.0, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-10.0)
        objective = average_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=0.01)
        budget = max_dofs(100, max_iterations=10)
        adaptivity = goal_aware(fraction=0.4, cost_aware=true)
    }
    """
    compiler = GDECCompiler()
    res = compiler.compile_source(source)
    assert res.success is True
    ir = res.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir)
    runtime = GDECRuntime(plan, ir)
    trace = runtime.execute()

    # Initial mesh for 100x20 is 250 DOFs (125 nodes), budget is 100 DOFs.
    # Must abort pre-solve with 0 solved iterations.
    assert len(trace.iterations) == 0
    assert trace.final_dofs == 0
    assert trace.final_dofs <= 100
    assert trace.converged is False
    assert "infeasible" in trace.stop_reason.lower()
    assert "exceeds" in trace.stop_reason.lower()


def test_budget_pathway_initial_mesh_equal_budget():
    """Verify that if initial mesh exactly equals budget, solve proceeds but refinement is rejected."""
    source = """
    problem ExactBudgetInitial {
        physics = linear_elasticity
        geometry = rectangle(width=100.0, height=20.0)
        material = isotropic(E=210000.0, nu=0.3)
        fix = boundary(left)
        load = traction(boundary=right, ty=-10.0)
        objective = average_displacement(boundary=right, component=y)
        accuracy = successive_qoi_change(percent=0.0001)
        budget = max_dofs(250, max_iterations=10)
        adaptivity = goal_aware(fraction=0.4, cost_aware=true)
    }
    """
    compiler = GDECCompiler()
    res = compiler.compile_source(source)
    assert res.success is True
    ir = res.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir)
    runtime = GDECRuntime(plan, ir)
    trace = runtime.execute()

    # Initial mesh is 250 DOFs == budget 250 DOFs.
    # Solves iteration 1, then halts because no further refinement is affordable.
    assert len(trace.iterations) == 1
    assert trace.final_dofs == 250
    assert trace.final_dofs <= 250
    assert trace.converged is False
    assert "budget" in trace.stop_reason.lower()


def test_estimator_heuristic_v1_and_zz_classification():
    """Verify estimator classification metadata and heuristic v1 naming."""
    c = ConstitutiveTensor.from_properties(E=210e3, nu=0.3, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)
    estimator = RefinementEstimator(c)
    mesh = GDECMesh.create_cantilever_mesh(width=100.0, height=20.0, nx=10, ny=5)

    loads = [("right", 0.0, -10.0)]
    bcs = [("left", ["x", "y"])]
    sol = solver.solve(mesh, loads=loads, fixed_boundaries=bcs, solve_adjoint=True)

    # 1. Goal heuristic v1
    goal_res = estimator.compute_goal_heuristic_v1_indicator(mesh, sol, cost_aware=True)
    assert goal_res.details["method"] == "goal_heuristic_v1"
    assert goal_res.details["classification"] == "heuristic_priority_indicator"
    assert goal_res.details["is_certified_dwr_bound"] is False
    assert len(goal_res.indicators) == mesh.nelements
    assert np.all(goal_res.priorities > 0.0)

    # 2. ZZ Recovery classification
    zz_res = estimator.compute_zz_recovery_indicator(mesh, sol)
    assert zz_res.details["classification"] == "area_weighted_nodal_stress_averaging"
    assert len(zz_res.indicators) == mesh.nelements
    assert np.all(zz_res.indicators >= 0.0)


def test_unsupported_backend_rejections():
    """Verify that cuda, tpu, hip, sycl are strictly rejected with GDECSemanticError."""
    parser = GDECParser()
    analyzer = SemanticAnalyzer()

    for backend in ["cuda", "tpu", "hip", "sycl"]:
        src = f"""
        problem BackendCheck {{
            physics = linear_elasticity
            geometry = rectangle(width=1.0, height=1.0)
            material = isotropic(E=70e9, nu=0.3)
            fix = boundary(left)
            load = traction(boundary=right, ty=-100)
            objective = average_displacement(boundary=right, component=y)
            backend = {backend}
        }}
        """
        ast = parser.parse(src)
        with pytest.raises(GDECSemanticError) as exc_info:
            analyzer.analyze(ast)
        msg = str(exc_info.value).lower()
        assert backend in msg
        assert "no accelerator backend is implemented in gdec v0.2.1" in msg or "no gpu accelerator" in msg


def test_multi_qoi_adjoint_sensitivity():
    """Verify adjoint force sensitivity identity dJ/df = z for multiple QoIs."""
    c = ConstitutiveTensor.from_properties(E=210e3, nu=0.3, assumption="plane_stress", thickness=1.0)
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=100.0, height=20.0, nx=20, ny=8)
    bcs = [("left", ["x", "y"])]
    loads = [("right", 0.0, -10.0)]

    # Test 1: Right boundary y-displacement
    sol_y = solver.solve(mesh, loads, bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=True)
    assert sol_y.z is not None
    # Perturb force by df
    df = 0.01
    loads_pert = [("right", 0.0, -10.0 + df)]
    sol_y_pert = solver.solve(mesh, loads_pert, bcs, qoi_boundary="right", qoi_component="y", solve_adjoint=False)
    fd_dJ_df = (sol_y_pert.qoi - sol_y.qoi) / df
    # Adjoint predicted dJ/df: (z @ delta_f) / df
    delta_f = (sol_y_pert.f - sol_y.f) / df
    adj_dJ_df = float(sol_y.z @ delta_f)
    rel_err_y = abs(adj_dJ_df - fd_dJ_df) / max(abs(fd_dJ_df), 1e-12)
    assert rel_err_y < 1e-6, f"Right-y QoI adjoint force sensitivity mismatch: {rel_err_y}"

    # Test 2: Right boundary x-displacement
    sol_x = solver.solve(mesh, loads, bcs, qoi_boundary="right", qoi_component="x", solve_adjoint=True)
    assert sol_x.z is not None
    sol_x_pert = solver.solve(mesh, loads_pert, bcs, qoi_boundary="right", qoi_component="x", solve_adjoint=False)
    fd_dJ_df_x = (sol_x_pert.qoi - sol_x.qoi) / df
    adj_dJ_df_x = float(sol_x.z @ delta_f)
    rel_err_x = abs(adj_dJ_df_x - fd_dJ_df_x) / max(abs(fd_dJ_df_x), 1e-12)
    assert rel_err_x < 1e-6, f"Right-x QoI adjoint force sensitivity mismatch: {rel_err_x}"
