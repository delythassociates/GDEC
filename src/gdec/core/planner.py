"""
GDEC Execution Planner.
Translates compiled ProblemIR into a concrete execution plan with rationale for each decision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

from gdec.language.ir import ProblemIR


@dataclass
class PlanRationale:
    category: str
    decision: str
    explanation: str


@dataclass
class ExecutionPlan:
    problem_name: str
    initial_mesh_shape: tuple[int, int]  # (nx, ny)
    constitutive_model: str
    qoi_description: str
    refinement_strategy: str
    marking_fraction: float
    accuracy_target_pct: float
    max_dofs_budget: int
    max_iterations: int
    backend_device: str
    rationales: List[PlanRationale] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"=== Execution Plan for '{self.problem_name}' ===",
            f"Strategy: {self.refinement_strategy.upper()}",
            f"Initial Discretization: {self.initial_mesh_shape[0]}x{self.initial_mesh_shape[1]} grid",
            f"Target Accuracy: {self.accuracy_target_pct}% successive QoI change",
            f"Budget Limit: {self.max_dofs_budget:,} DOFs (max {self.max_iterations} iterations)",
            f"Backend: {self.backend_device.upper()}",
            "Rationales:",
        ]
        for r in self.rationales:
            lines.append(f"  [{r.category}] {r.decision}: {r.explanation}")
        return "\n".join(lines)


class ExecutionPlanner:
    def create_plan(self, ir: ProblemIR, override_strategy: str | None = None) -> ExecutionPlan:
        strategy = override_strategy or ir.adaptivity.strategy
        rationales: List[PlanRationale] = []

        # Mesh sizing rationale
        aspect_ratio = ir.geometry.width / ir.geometry.height
        ny = 5
        nx = max(5, int(round(ny * aspect_ratio)))
        rationales.append(
            PlanRationale(
                category="Discretization",
                decision=f"Initial grid {nx}x{ny} (Aspect ratio {aspect_ratio:.1f})",
                explanation="Coarse initial mesh minimizes startup latency and leaves maximum budget for adaptive refinement.",
            )
        )

        # Constitutive model rationale
        mat = ir.material
        rationales.append(
            PlanRationale(
                category="Physics & Material",
                decision=f"{mat.assumption.replace('_', ' ').title()} Linear Elasticity (E={mat.E/1e9:.1f} GPa, nu={mat.nu})",
                explanation=f"Plane stress assumption selected for thin plate thickness {ir.geometry.thickness}m.",
            )
        )

        # Strategy rationale
        if strategy in ["dwr", "goal_oriented_dwr"]:
            strat_desc = "Goal-Oriented Dual-Weighted Residual (DWR) Refinement"
            strat_exp = (
                f"Evaluates primal traction jumps and enriched dual weighting to directly target QoI error "
                f"for objective '{ir.objective.kind}' on boundary '{ir.objective.boundary}'."
            )
        elif strategy == "goal_aware":
            strat_desc = "Adjoint-informed Goal-Aware Sensitivity Refinement"
            strat_exp = (
                f"Dual adjoint problem K^T z = g will be solved to compute element sensitivity for objective "
                f"'{ir.objective.kind}' on boundary '{ir.objective.boundary}'."
            )
        elif strategy == "recovery":
            strat_desc = "Zienkiewicz-Zhu Stress Recovery Refinement"
            strat_exp = "Averages nodal stresses to assess overall strain energy error independent of target QoI."
        else:
            strat_desc = "Uniform Mesh Refinement"
            strat_exp = "Refines all elements globally. Serves as reference baseline."

        rationales.append(
            PlanRationale(
                category="Adaptivity Strategy",
                decision=strat_desc,
                explanation=strat_exp,
            )
        )

        # Budget & accuracy rationale
        rationales.append(
            PlanRationale(
                category="Resource Budget",
                decision=f"Max {ir.budget.value:,} DOFs, target <={ir.accuracy.percent}% change",
                explanation="Refinement stops when successive QoI change satisfies target across two consecutive iterations or budget is reached.",
            )
        )

        # Backend rationale
        rationales.append(
            PlanRationale(
                category="Execution Backend",
                decision=f"{ir.backend.device.upper()} Sparse Direct Solver",
                explanation="NumPy/SciPy sparse LU factorization chosen for 2D P1 triangular finite elements.",
            )
        )

        qoi_desc = f"{ir.objective.kind} on {ir.objective.boundary} ({ir.objective.component}-component)"

        return ExecutionPlan(
            problem_name=ir.name,
            initial_mesh_shape=(nx, ny),
            constitutive_model=f"{mat.assumption} (E={mat.E}, nu={mat.nu})",
            qoi_description=qoi_desc,
            refinement_strategy=strategy,
            marking_fraction=ir.adaptivity.marking_fraction,
            accuracy_target_pct=ir.accuracy.percent,
            max_dofs_budget=ir.budget.value,
            max_iterations=ir.budget.max_iterations,
            backend_device=ir.backend.device,
            rationales=rationales,
        )
