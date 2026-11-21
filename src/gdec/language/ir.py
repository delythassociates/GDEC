"""
Typed Intermediate Representation (IR) for GDEC.
Solvers and runtimes consume this representation, which is completely
decoupled from the FEM assembly routines.
"""

from __future__ import annotations
import json
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


IR_SCHEMA_VERSION = "gdec_ir_v0.1"


class GeometryIR(BaseModel):
    kind: Literal["rectangle"] = "rectangle"
    width: float = Field(..., gt=0.0, description="Plate length/width in meters", allow_inf_nan=False)
    height: float = Field(..., gt=0.0, description="Plate height in meters", allow_inf_nan=False)
    thickness: float = Field(default=1.0, gt=0.0, description="Out-of-plane thickness in meters", allow_inf_nan=False)


class MaterialIR(BaseModel):
    kind: Literal["isotropic"] = "isotropic"
    E: float = Field(..., gt=0.0, description="Young's modulus in Pascals", allow_inf_nan=False)
    nu: float = Field(..., gt=-1.0, lt=0.5, description="Poisson's ratio", allow_inf_nan=False)
    assumption: Literal["plane_stress", "plane_strain"] = "plane_stress"


class BoundaryConditionIR(BaseModel):
    boundary: Literal["left", "right", "top", "bottom"]
    constrained_components: List[Literal["x", "y"]] = Field(
        default_factory=lambda: ["x", "y"],
        description="Constrained displacement directions",
    )


class TractionLoadIR(BaseModel):
    boundary: Literal["left", "right", "top", "bottom"]
    tx: float = Field(default=0.0, description="Traction in x-direction (Pa)", allow_inf_nan=False)
    ty: float = Field(default=0.0, description="Traction in y-direction (Pa)", allow_inf_nan=False)


class ObjectiveIR(BaseModel):
    kind: Literal["average_displacement"] = "average_displacement"
    boundary: Literal["left", "right", "top", "bottom"] = "right"
    component: Literal["x", "y"] = "y"


class AccuracyTargetIR(BaseModel):
    kind: Literal["successive_qoi_change"] = "successive_qoi_change"
    percent: float = Field(default=1.0, gt=0.0, description="Convergence percent threshold", allow_inf_nan=False)


class BudgetIR(BaseModel):
    kind: Literal["max_dofs"] = "max_dofs"
    value: int = Field(default=25000, gt=0, description="Maximum degrees of freedom allowed")
    max_iterations: int = Field(default=15, gt=0, description="Maximum adaptive iterations")


class AdaptivityIR(BaseModel):
    strategy: Literal["goal_aware", "recovery", "uniform", "dwr", "goal_oriented_dwr"] = "goal_aware"
    marking_fraction: float = Field(default=0.3, gt=0.0, le=1.0, description="Fraction of elements to refine", allow_inf_nan=False)
    cost_aware: bool = Field(default=True, description="Whether to weigh indicator by estimated cost")


class BackendIR(BaseModel):
    device: Literal["cpu", "cuda", "hip", "sycl", "tpu"] = "cpu"


class ProblemIR(BaseModel):
    schema_version: str = Field(default=IR_SCHEMA_VERSION, description="GDEC IR Schema version")
    name: str = Field(..., description="Problem identifier")
    physics: Literal["linear_elasticity"] = "linear_elasticity"
    geometry: GeometryIR
    material: MaterialIR
    boundary_conditions: List[BoundaryConditionIR]
    loads: List[TractionLoadIR]
    objective: ObjectiveIR
    accuracy: AccuracyTargetIR
    budget: BudgetIR
    adaptivity: AdaptivityIR
    backend: BackendIR

    @model_validator(mode="after")
    def validate_cross_field_invariants(self) -> ProblemIR:
        if not self.boundary_conditions:
            raise ValueError("Problem must contain at least one boundary condition.")
        if not self.loads:
            raise ValueError("Problem must contain at least one load.")
        fixed_bnds = {bc.boundary for bc in self.boundary_conditions}
        for load in self.loads:
            if load.boundary in fixed_bnds:
                raise ValueError(
                    f"Conflicting boundary condition on '{load.boundary}': "
                    f"cannot apply traction to fixed Dirichlet boundary."
                )
        if self.objective.boundary in fixed_bnds:
            raise ValueError(
                f"Conflicting objective boundary '{self.objective.boundary}': "
                f"cannot evaluate displacement objective on a fixed Dirichlet boundary."
            )
        return self

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ProblemIR:
        data = json.loads(json_str)
        return cls.model_validate(data)
