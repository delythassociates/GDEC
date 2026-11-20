"""
Adaptive mesh refinement and marking strategies for GDEC.
Supports Dörfler marking, top-fraction priority marking, and budget-constrained selection.
"""

from __future__ import annotations
from typing import List, Tuple
import numpy as np

from gdec.fem.mesh import GDECMesh
from gdec.fem.estimators import IndicatorResult


class MeshAdaptor:
    @staticmethod
    def mark_elements(
        indicator_result: IndicatorResult,
        strategy: str,
        marking_fraction: float = 0.3,
        current_dofs: int = 0,
        max_dofs_budget: int = 25000,
    ) -> np.ndarray:
        """
        Mark element indices to be refined in the next iteration.
        Takes into account the remaining DOF budget.
        """
        if strategy == "uniform":
            # For uniform, all elements are marked
            return np.arange(len(indicator_result.indicators))

        priorities = indicator_result.priorities
        nelements = len(priorities)
        if nelements == 0:
            return np.array([], dtype=int)

        # Sort elements by descending priority
        sorted_indices = np.argsort(-priorities)

        # Number of elements based on marking fraction
        target_count = max(1, int(np.ceil(marking_fraction * nelements)))

        # Budget enforcement: estimate additional DOFs
        # Each marked element will add ~4 to 8 DOFs (including conforming neighbors)
        remaining_budget = max(0, max_dofs_budget - current_dofs)
        dofs_per_element_est = 6.0

        max_affordable_elements = max(1, int(remaining_budget // dofs_per_element_est))
        actual_count = min(target_count, max_affordable_elements)

        if actual_count <= 0 or current_dofs >= max_dofs_budget:
            return np.array([], dtype=int)

        marked = sorted_indices[:actual_count]
        return np.sort(marked)

    @staticmethod
    def refine_mesh(
        gdec_mesh: GDECMesh, strategy: str, marked_elements: np.ndarray
    ) -> GDECMesh:
        """Apply refinement to mesh."""
        if strategy == "uniform":
            return gdec_mesh.refine_uniform()
        else:
            return gdec_mesh.refine_elements(marked_elements)
