"""
Tests for GDEC Intelligent Runtime, budget enforcement, and convergence tracking.
"""

from gdec.compiler import GDECCompiler
from gdec.core import ExecutionPlanner, GDECRuntime


def test_runtime_goal_aware_execution():
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    assert res.success is True

    planner = ExecutionPlanner()
    plan = planner.create_plan(res.ir, override_strategy="goal_aware")
    runtime = GDECRuntime(plan, res.ir)
    trace = runtime.execute()

    assert len(trace.iterations) >= 2
    assert trace.final_dofs <= plan.max_dofs_budget
    assert trace.converged is True
    assert "Target convergence achieved" in trace.stop_reason


def test_runtime_budget_enforcement():
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    # Set a tiny budget of 500 DOFs
    res.ir.budget.value = 500

    planner = ExecutionPlanner()
    plan = planner.create_plan(res.ir, override_strategy="goal_aware")
    runtime = GDECRuntime(plan, res.ir)
    trace = runtime.execute()

    assert trace.final_dofs <= 500
    assert trace.converged is False
    assert "Budget" in trace.stop_reason
