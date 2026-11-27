"""
Runtime convergence controller and budget manager.
Requires two consecutive iterations below target tolerance to certify observed convergence.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ControllerDecision:
    should_stop: bool
    converged: bool
    reason: str
    budget_exhausted: bool = False


class RuntimeController:
    def __init__(self, target_accuracy_pct: float, max_dofs_budget: int, max_iterations: int):
        self.target_pct = float(target_accuracy_pct)
        self.max_dofs = int(max_dofs_budget)
        self.max_iterations = int(max_iterations)
        self.consecutive_converged_count = 0
        self.eps = 1e-12

    def calculate_successive_change(
        self, current_qoi: float, previous_qoi: Optional[float]
    ) -> Optional[float]:
        if previous_qoi is None:
            return None
        denom = max(abs(current_qoi), self.eps)
        pct = (abs(current_qoi - previous_qoi) / denom) * 100.0
        return float(pct)

    def evaluate(
        self,
        iteration: int,
        current_dofs: int,
        predicted_next_dofs: int,
        successive_change_pct: Optional[float],
        marked_elements_count: int,
    ) -> ControllerDecision:
        # 1. Check convergence condition
        if successive_change_pct is not None and successive_change_pct <= self.target_pct:
            self.consecutive_converged_count += 1
        else:
            self.consecutive_converged_count = 0

        # Require 2 consecutive iterations below threshold
        if self.consecutive_converged_count >= 2:
            return ControllerDecision(
                should_stop=True,
                converged=True,
                reason=f"Target convergence achieved: successive change {successive_change_pct:.3f}% <= {self.target_pct}% for 2 consecutive iterations.",
            )

        # 2. Check if no elements were marked
        if marked_elements_count == 0 and iteration > 1:
            return ControllerDecision(
                should_stop=True,
                converged=False,
                reason="Budget limit prevents further refinement: no elements affordable within remaining budget.",
                budget_exhausted=True,
            )

        # 3. Check hard DOF budget
        if current_dofs >= self.max_dofs:
            return ControllerDecision(
                should_stop=True,
                converged=False,
                reason=f"Budget exhausted: current DOFs ({current_dofs:,}) reached limit ({self.max_dofs:,}). Target accuracy not achieved.",
                budget_exhausted=True,
            )

        if predicted_next_dofs > self.max_dofs:
            return ControllerDecision(
                should_stop=True,
                converged=False,
                reason=f"Budget constraint: next planned refinement ({predicted_next_dofs:,} DOFs) would exceed budget ({self.max_dofs:,}). Stopping execution.",
                budget_exhausted=True,
            )

        # 4. Check iteration limit
        if iteration >= self.max_iterations:
            return ControllerDecision(
                should_stop=True,
                converged=False,
                reason=f"Iteration limit reached ({self.max_iterations} iterations). Accuracy target not achieved within budget.",
                budget_exhausted=True,
            )

        # Continue refinement
        return ControllerDecision(
            should_stop=False,
            converged=False,
            reason=f"Continuing computation (iteration {iteration}): successive change "
            + (f"{successive_change_pct:.3f}% > {self.target_pct}%" if successive_change_pct is not None else "initial solve")
            + f", DOFs {current_dofs:,}/{self.max_dofs:,}.",
        )
