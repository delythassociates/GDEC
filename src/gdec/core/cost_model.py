"""
Cost model and refinement prediction tracking for GDEC v0.2.
Tracks predicted vs observed DOF growth, calculates prediction errors,
and models topological mesh closure overhead.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import numpy as np


@dataclass
class CostRecord:
    iteration: int
    elements_marked: int
    total_elements_in_mesh: int
    predicted_dofs_delta: int
    observed_dofs_delta: int
    prediction_error: int
    prediction_error_pct: float
    observed_time_sec: float


class CostModel:
    def __init__(self):
        self.history: List[CostRecord] = []
        # Base multiplier parameters: alpha (isolated bisection) - beta * sqrt(density)
        self.base_alpha: float = 7.5
        self.density_beta: float = 3.0

    def predict_additional_dofs(
        self, marked_count: int, total_elements: int = 100
    ) -> int:
        """
        Topological cost prediction:
        Isolated elements induce green-closure splits on neighbors (higher DOF delta per element).
        Clustered elements share new edge vertices (lower DOF delta per element).
        """
        if marked_count <= 0:
            return 0

        density = min(1.0, max(0.01, marked_count / max(total_elements, 1)))
        dofs_per_elem = self.base_alpha - self.density_beta * np.sqrt(density)
        # Bounded between 3.5 and 9.0 DOFs per marked element
        dofs_per_elem = max(3.5, min(9.0, dofs_per_elem))

        return int(round(marked_count * dofs_per_elem))

    def update(
        self,
        iteration: int,
        marked_count: int,
        observed_delta: int,
        observed_time: float,
        total_elements: int = 100,
    ) -> None:
        predicted = self.predict_additional_dofs(marked_count, total_elements)
        err = abs(observed_delta - predicted)
        err_pct = (err / max(observed_delta, 1)) * 100.0

        rec = CostRecord(
            iteration=iteration,
            elements_marked=marked_count,
            total_elements_in_mesh=total_elements,
            predicted_dofs_delta=predicted,
            observed_dofs_delta=observed_delta,
            prediction_error=err,
            prediction_error_pct=err_pct,
            observed_time_sec=observed_time,
        )
        self.history.append(rec)

        # Adaptive correction: update base_alpha toward observed rate
        if marked_count > 0 and observed_delta > 0:
            observed_rate = observed_delta / marked_count
            self.base_alpha = 0.8 * self.base_alpha + 0.2 * (observed_rate + 1.0)

    @property
    def mean_absolute_error_pct(self) -> float:
        if not self.history:
            return 0.0
        return float(np.mean([r.prediction_error_pct for r in self.history]))
