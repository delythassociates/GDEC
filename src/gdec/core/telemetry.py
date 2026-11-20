"""
Telemetry and execution logging for GDEC.
Measures high-resolution stage timings and memory consumption.
"""

from __future__ import annotations
import time
import psutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class IterationRecord:
    iteration: int
    nelements: int
    nnodes: int
    dofs: int
    qoi_meters: float
    qoi_mm: float
    successive_change_pct: Optional[float]
    max_refinement_indicator: float
    elements_marked: int
    assembly_time_sec: float
    solver_time_sec: float
    indicator_time_sec: float
    total_iteration_time_sec: float
    peak_memory_mb: float
    action_reason: str
    # Detailed stage profiling
    condensation_time_sec: float = 0.0
    factorization_time_sec: float = 0.0
    primal_solve_time_sec: float = 0.0
    adjoint_solve_time_sec: float = 0.0
    refinement_time_sec: float = 0.0
    postprocess_time_sec: float = 0.0

    def to_dict(self) -> Dict[str, any]:
        return {
            "iteration": self.iteration,
            "nelements": self.nelements,
            "nnodes": self.nnodes,
            "dofs": self.dofs,
            "qoi_meters": self.qoi_meters,
            "qoi_mm": self.qoi_mm,
            "successive_change_pct": self.successive_change_pct,
            "max_indicator": self.max_refinement_indicator,
            "elements_marked": self.elements_marked,
            "assembly_time_sec": self.assembly_time_sec,
            "condensation_time_sec": self.condensation_time_sec,
            "factorization_time_sec": self.factorization_time_sec,
            "primal_solve_time_sec": self.primal_solve_time_sec,
            "adjoint_solve_time_sec": self.adjoint_solve_time_sec,
            "solver_time_sec": self.solver_time_sec,
            "indicator_time_sec": self.indicator_time_sec,
            "refinement_time_sec": self.refinement_time_sec,
            "postprocess_time_sec": self.postprocess_time_sec,
            "total_time_sec": self.total_iteration_time_sec,
            "peak_memory_mb": self.peak_memory_mb,
            "action_reason": self.action_reason,
        }


@dataclass
class ExecutionTrace:
    problem_name: str
    strategy: str
    target_accuracy_pct: float
    budget_max_dofs: int
    converged: bool
    stop_reason: str
    total_wall_time_sec: float
    iterations: List[IterationRecord] = field(default_factory=list)

    @property
    def final_qoi_mm(self) -> float:
        return self.iterations[-1].qoi_mm if self.iterations else 0.0

    @property
    def final_dofs(self) -> int:
        return self.iterations[-1].dofs if self.iterations else 0

    @property
    def final_elements(self) -> int:
        return self.iterations[-1].nelements if self.iterations else 0


class TelemetryTracker:
    def __init__(self):
        self._process = psutil.Process()

    def get_current_memory_mb(self) -> float:
        try:
            return self._process.memory_info().rss / (1024.0 * 1024.0)
        except Exception:
            return 0.0

    @staticmethod
    def now() -> float:
        return time.perf_counter()
