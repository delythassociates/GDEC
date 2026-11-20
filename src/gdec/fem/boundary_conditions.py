"""
Boundary conditions representation and DOF mapping utilities.
"""

from __future__ import annotations
from typing import List, Tuple
from gdec.language.ir import BoundaryConditionIR, TractionLoadIR


def parse_boundary_conditions(
    bc_irs: List[BoundaryConditionIR],
) -> List[Tuple[str, List[str]]]:
    """Convert IR boundary conditions into solver format: [(boundary, [components])]."""
    return [(bc.boundary, list(bc.constrained_components)) for bc in bc_irs]


def parse_loads(load_irs: List[TractionLoadIR]) -> List[Tuple[str, float, float]]:
    """Convert IR loads into solver format: [(boundary, tx, ty)]."""
    return [(load.boundary, float(load.tx), float(load.ty)) for load in load_irs]
