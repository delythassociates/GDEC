"""
Typed Intermediate Representation (IR) for GDEC.
Solvers and runtimes consume this representation, which is completely
decoupled from the FEM assembly routines.
"""

from __future__ import annotations
import json
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


IR_SCHEMA_VERSION = "gdec_ir_v0.1"


class GeometryIR(BaseModel):
    kind: Literal["rectangle"] = "rectangle"
    width: float = Field(..., gt=0.0, description="Plate length/width in meters")
    height: float = Field(..., gt=0.0, description="Plate height in meters")
    thickness: float = Field(default=1.0, gt=0.0, description="Out-of-plane thickness in meters")


class MaterialIR(BaseModel):
    kind: Literal["isotropic"] = "isotropic"
    E: float = Field(..., gt=0.0, description="Young's modulus in Pascals")
    nu: float = Field(..., gt=-1.0, lt=0.5, description="Poisson's ratio")
    assumption: Literal["plane_stress", "plane_strain"] = "plane_stress"


class BoundaryConditionIR(BaseModel):
    boundary: Literal["left", "right", "top", "bottom"]
    constrained_components: List[Literal["x", "y"]] = Field(
        default_factory=lambda: ["x", "y"],
        description="Constrained displacement directions",
    )


class TractionLoadIR(BaseModel):
    boundary: Literal["left", "right", "top", "bottom"]
    tx: float = Field(default=0.0, description="Traction in x-direction (Pa)")
    ty: float = Field(default=0.0, description="Traction in y-direction (Pa)")


class ObjectiveIR(BaseModel):
    kind: Literal["average_displacement", "point_displacement"] = "average_displacement"
    boundary: Literal["left", "right", "top", "bottom"] = "right"
    component: Literal["x", "y"] = "y"


class AccuracyTargetIR(BaseModel):
    kind: Literal["successive_qoi_change"] = "successive_qoi_change"
    percent: float = Field(default=1.0, gt=0.0, description="Convergence percent threshold")


class BudgetIR(BaseModel):
    kind: Literal["max_dofs"] = "max_dofs"
    value: int = Field(default=25000, gt=0, description="Maximum degrees of freedom allowed")
    max_iterations: int = Field(default=15, gt=0, description="Maximum adaptive iterations")


class AdaptivityIR(BaseModel):
    strategy: Literal["goal_aware", "recovery", "uniform"] = "goal_aware"
    marking_fraction: float = Field(default=0.3, gt=0.0, le=1.0, description="Fraction of elements to refine")
    cost_aware: bool = Field(default=True, description="Whether to weigh indicator by estimated cost")


class BackendIR(BaseModel):
    device: Literal["cpu", "cuda", "hip", "sycl"] = "cpu"


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

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ProblemIR:
        data = json.loads(json_str)
        return cls.model_validate(data)
