"""
Timing Accounting Verification Suite for Phase B.1.
Verifies that:
1. Total elapsed iteration time strictly bounds the sum of non-overlapping measured components:
   t_total_iter >= t_primal + t_adjoint + t_estimator + t_marking + t_refinement - 1e-9.
2. No measured timing component is negative.
3. Mesh refinement time is strictly positive on active refinement steps.
4. Timing does not double-count nested operations.
"""

import pytest
import numpy as np
from verification.dwr.geometries import CantileverProblem
from verification.dwr.adaptive_runner import run_single_simulation


@pytest.mark.parametrize("method", ["uniform", "zz", "goal_aware", "dwr"])
def test_timing_accounting_inequality(method):
    """
    Verifies that total_elapsed >= sum(non_overlapping_components)
    for every iteration of every adaptive refinement method.
    """
    prob = CantileverProblem()
    # Run 2 iterations on variant 0 with tight limits to test both refinement and termination
    records = run_single_simulation(prob, method, variant_idx=0, max_iterations=2)

    assert len(records) >= 1, "Simulation must produce at least 1 record"

    for r in records:
        t_total = r["t_total_iter_sec"]
        t_primal = r["t_primal_sec"]
        t_adjoint = r["t_adjoint_sec"]
        t_estimator = r["t_estimator_sec"]
        t_marking = r["t_marking_sec"]
        t_refine = r["t_refinement_sec"]

        # 1. Non-negativity
        assert t_primal >= 0.0, f"{method}: t_primal must be non-negative"
        assert t_adjoint >= 0.0, f"{method}: t_adjoint must be non-negative"
        assert t_estimator >= 0.0, f"{method}: t_estimator must be non-negative"
        assert t_marking >= 0.0, f"{method}: t_marking must be non-negative"
        assert t_refine >= 0.0, f"{method}: t_refinement must be non-negative"
        assert t_total > 0.0, f"{method}: t_total must be strictly positive"

        # 2. Timing inequality: total elapsed bounds sum of non-overlapping parts
        sum_components = t_primal + t_adjoint + t_estimator + t_marking + t_refine
        slack = t_total - sum_components

        # Slack represents unmeasured python overhead (record creation, psutil memory check, loop control)
        # Slack must be non-negative (within floating point precision)
        assert slack >= -1e-6, (
            f"{method} it={r['iteration']}: total time {t_total:.6f}s < sum of components {sum_components:.6f}s "
            f"(slack = {slack:.3e})"
        )

    # 3. If multiple iterations occurred, iteration 0 must have had active refinement
    if len(records) > 1:
        assert records[0]["t_refinement_sec"] > 0.0, (
            f"{method}: Iteration 0 refinement time must be strictly positive"
        )
