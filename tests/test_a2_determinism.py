"""
A2.9: Runtime Determinism Verification.
Verifies bit-for-bit repeatability of production GDECRuntime across:
- Strategies: uniform, recovery, goal_aware
- Sequence of degrees of freedom (DOFs)
- Quantity of Interest (QoI) convergence progression
- Explicit match with preregistered sequence prefix [200, 418, 894, 1908, 4034] for goal_aware.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from gdec.compiler import GDECCompiler
from gdec.core.planner import ExecutionPlanner
from gdec.core.runtime import GDECRuntime

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


EXPECTED_GOAL_AWARE_DOFS = [200, 418, 894, 1908, 4034]


@pytest.mark.parametrize("strategy", ["uniform", "recovery", "goal_aware"])
def test_a2_9_runtime_determinism(strategy: str):
    test_id = f"A2.9_determinism_{strategy}"

    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    ir = comp.ir

    planner = ExecutionPlanner()
    plan = planner.create_plan(ir, override_strategy=strategy)
    plan.max_iterations = 5
    plan.max_dofs_budget = 50000
    plan.accuracy_target_pct = 1e-6

    # Run 1
    rt1 = GDECRuntime(plan, ir)
    trace1 = rt1.execute()
    dofs1 = [int(it.dofs) for it in trace1.iterations]
    qois1 = [float(it.qoi_meters) for it in trace1.iterations]

    # Run 2
    rt2 = GDECRuntime(plan, ir)
    trace2 = rt2.execute()
    dofs2 = [int(it.dofs) for it in trace2.iterations]
    qois2 = [float(it.qoi_meters) for it in trace2.iterations]

    dof_identical = bool(dofs1 == dofs2)
    max_qoi_diff = float(max(abs(q1 - q2) / abs(q1) for q1, q2 in zip(qois1, qois2)))
    qoi_identical = max_qoi_diff <= 1e-8

    prefix_match = True
    if strategy == "goal_aware":
        prefix_match = (dofs1[:5] == EXPECTED_GOAL_AWARE_DOFS)

    passed = bool(dof_identical and qoi_identical and prefix_match)

    res = {
        "id": test_id,
        "computed": {
            "strategy": strategy,
            "dofs_run1": dofs1,
            "dofs_run2": dofs2,
            "dof_identical": dof_identical,
            "max_qoi_relative_difference": max_qoi_diff,
            "goal_aware_prefix_match": prefix_match,
        },
        "threshold": {
            "dof_sequence_equality": "exact",
            "qoi_relative_tolerance": 1e-8,
            "expected_prefix": EXPECTED_GOAL_AWARE_DOFS if strategy == "goal_aware" else None,
        },
        "pass": passed,
        "failure_class": None if passed else "NUM_FAIL",
        "details": f"Deterministic execution repeatability for {strategy} strategy.",
    }
    _record_result(res, "A2_9_determinism.json")

    assert dof_identical, f"DOF sequence mismatch between runs: {dofs1} vs {dofs2}"
    assert qoi_identical, f"QoI difference between runs {max_qoi_diff} > 1e-8"
    if strategy == "goal_aware":
        assert prefix_match, f"Goal-aware DOFs {dofs1[:5]} did not match preregistered prefix {EXPECTED_GOAL_AWARE_DOFS}"
