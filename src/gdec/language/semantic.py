"""
Semantic analysis and AST-to-IR lowering for GDEC.
Performs strict validation and generates typed ProblemIR.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import shutil

from gdec.language.ast import (
    ProblemNode,
    Statement,
    Expression,
    FunctionCall,
    Identifier,
    NumberLiteral,
    StringLiteral,
    SourceLocation,
)
from gdec.language.ir import (
    ProblemIR,
    GeometryIR,
    MaterialIR,
    BoundaryConditionIR,
    TractionLoadIR,
    ObjectiveIR,
    AccuracyTargetIR,
    BudgetIR,
    AdaptivityIR,
    BackendIR,
)


class GDECSemanticError(Exception):
    def __init__(self, message: str, loc: Optional[SourceLocation] = None):
        self.message = message
        self.loc = loc
        super().__init__(self.__str__())

    def __str__(self) -> str:
        loc_str = f" at {self.loc}" if self.loc else ""
        return f"Semantic Error{loc_str}: {self.message}"


class SemanticAnalyzer:
    """Validates AST and lowers it to ProblemIR."""

    def __init__(self):
        pass

    def analyze(self, ast: ProblemNode) -> ProblemIR:
        if not ast.name or not ast.name.isidentifier():
            raise GDECSemanticError(f"Invalid problem identifier '{ast.name}'", ast.loc)

        # Collect statements
        stmts: Dict[str, List[Statement]] = {}
        for s in ast.statements:
            stmts.setdefault(s.key, []).append(s)

        # 1. Physics
        physics = self._extract_physics(stmts.get("physics"))

        # 2. Geometry
        geometry = self._extract_geometry(stmts.get("geometry"))

        # 3. Material
        material = self._extract_material(stmts.get("material"))

        # 4. Boundary conditions (fix)
        bcs = self._extract_bcs(stmts.get("fix", []) + stmts.get("boundary_condition", []))

        # 5. Loads
        loads = self._extract_loads(stmts.get("load", []))

        # 6. Objective
        objective = self._extract_objective(stmts.get("objective"))

        # 7. Accuracy
        accuracy = self._extract_accuracy(stmts.get("accuracy"))

        # 8. Budget
        budget = self._extract_budget(stmts.get("budget"))

        # 9. Adaptivity
        adaptivity = self._extract_adaptivity(stmts.get("adaptivity"))

        # 10. Backend
        backend = self._extract_backend(stmts.get("backend"))

        return ProblemIR(
            name=ast.name,
            physics=physics,
            geometry=geometry,
            material=material,
            boundary_conditions=bcs,
            loads=loads,
            objective=objective,
            accuracy=accuracy,
            budget=budget,
            adaptivity=adaptivity,
            backend=backend,
        )

    def _eval_value(self, expr: Expression) -> Any:
        if isinstance(expr, NumberLiteral):
            return expr.value
        elif isinstance(expr, Identifier):
            return expr.name
        elif isinstance(expr, StringLiteral):
            return expr.value
        elif isinstance(expr, FunctionCall):
            return expr
        raise GDECSemanticError(f"Unsupported expression type: {type(expr).__name__}", expr.loc)

    def _extract_physics(self, stmts: Optional[List[Statement]]) -> str:
        if not stmts:
            raise GDECSemanticError("Missing required 'physics' declaration in problem definition.")
        stmt = stmts[-1]
        val = self._eval_value(stmt.value)
        if val != "linear_elasticity":
            raise GDECSemanticError(
                f"Unsupported physics model '{val}'. Version 0.1 only supports 'linear_elasticity'.",
                stmt.loc,
            )
        return "linear_elasticity"

    def _extract_geometry(self, stmts: Optional[List[Statement]]) -> GeometryIR:
        if not stmts:
            raise GDECSemanticError("Missing required 'geometry' declaration in problem definition.")
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "rectangle":
            raise GDECSemanticError(
                "Geometry must be defined as 'rectangle(width=..., height=..., [thickness=...])'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        if "width" not in args or not isinstance(args["width"], (int, float)) or args["width"] <= 0:
            raise GDECSemanticError("Geometry 'width' must be a positive number.", call.loc)
        if "height" not in args or not isinstance(args["height"], (int, float)) or args["height"] <= 0:
            raise GDECSemanticError("Geometry 'height' must be a positive number.", call.loc)

        thickness = args.get("thickness", 1.0)
        if not isinstance(thickness, (int, float)) or thickness <= 0:
            raise GDECSemanticError("Geometry 'thickness' must be a positive number.", call.loc)

        return GeometryIR(
            kind="rectangle",
            width=float(args["width"]),
            height=float(args["height"]),
            thickness=float(thickness),
        )

    def _extract_material(self, stmts: Optional[List[Statement]]) -> MaterialIR:
        if not stmts:
            raise GDECSemanticError("Missing required 'material' declaration in problem definition.")
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "isotropic":
            raise GDECSemanticError(
                "Material must be defined as 'isotropic(E=..., nu=..., [assumption=...])'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        if "E" not in args or not isinstance(args["E"], (int, float)) or args["E"] <= 0:
            raise GDECSemanticError(
                f"Young's modulus 'E' must be a strictly positive number (received {args.get('E')}).",
                call.loc,
            )
        if "nu" not in args or not isinstance(args["nu"], (int, float)) or not (-1.0 < args["nu"] < 0.5):
            raise GDECSemanticError(
                f"Poisson's ratio 'nu' must satisfy -1.0 < nu < 0.5 (received {args.get('nu')}).",
                call.loc,
            )

        assumption = args.get("assumption", "plane_stress")
        if assumption not in ["plane_stress", "plane_strain"]:
            raise GDECSemanticError(
                f"Unsupported elasticity assumption '{assumption}'. Must be 'plane_stress' or 'plane_strain'.",
                call.loc,
            )

        return MaterialIR(
            kind="isotropic",
            E=float(args["E"]),
            nu=float(args["nu"]),
            assumption=assumption,
        )

    def _extract_bcs(self, stmts: List[Statement]) -> List[BoundaryConditionIR]:
        if not stmts:
            raise GDECSemanticError("At least one boundary condition ('fix') must be specified.")
        bcs = []
        valid_boundaries = {"left", "right", "top", "bottom"}
        for stmt in stmts:
            call = stmt.value
            bnd = None
            comps = ["x", "y"]
            if isinstance(call, FunctionCall) and call.func_name == "boundary":
                if call.positional_args:
                    bnd = self._eval_value(call.positional_args[0])
                elif "boundary" in call.named_args:
                    bnd = self._eval_value(call.named_args["boundary"])
            elif isinstance(call, Identifier):
                bnd = call.name

            if bnd not in valid_boundaries:
                raise GDECSemanticError(
                    f"Invalid boundary '{bnd}'. Supported boundaries are {valid_boundaries}.",
                    stmt.loc,
                )
            bcs.append(BoundaryConditionIR(boundary=bnd, constrained_components=comps))
        return bcs

    def _extract_loads(self, stmts: List[Statement]) -> List[TractionLoadIR]:
        if not stmts:
            raise GDECSemanticError("At least one 'load' must be specified in the problem.")
        loads = []
        valid_boundaries = {"left", "right", "top", "bottom"}
        for stmt in stmts:
            if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "traction":
                raise GDECSemanticError(
                    "Loads must be specified as 'traction(boundary=..., tx=..., ty=...)'",
                    stmt.loc,
                )
            call = stmt.value
            args = {k: self._eval_value(v) for k, v in call.named_args.items()}

            bnd = args.get("boundary")
            if bnd not in valid_boundaries:
                raise GDECSemanticError(
                    f"Invalid load boundary '{bnd}'. Must be one of {valid_boundaries}.",
                    call.loc,
                )
            tx = float(args.get("tx", 0.0))
            ty = float(args.get("ty", 0.0))
            loads.append(TractionLoadIR(boundary=bnd, tx=tx, ty=ty))
        return loads

    def _extract_objective(self, stmts: Optional[List[Statement]]) -> ObjectiveIR:
        if not stmts:
            raise GDECSemanticError("Missing required 'objective' declaration.")
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name not in [
            "average_displacement",
            "point_displacement",
        ]:
            raise GDECSemanticError(
                "Objective must be defined as 'average_displacement(boundary=..., component=...)'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        bnd = args.get("boundary", "right")
        if bnd not in {"left", "right", "top", "bottom"}:
            raise GDECSemanticError(f"Objective boundary '{bnd}' is invalid.", call.loc)

        comp = args.get("component", "y")
        if comp not in {"x", "y"}:
            raise GDECSemanticError(f"Objective component '{comp}' must be 'x' or 'y'.", call.loc)

        return ObjectiveIR(
            kind=call.func_name,  # type: ignore
            boundary=bnd,
            component=comp,
        )

    def _extract_accuracy(self, stmts: Optional[List[Statement]]) -> AccuracyTargetIR:
        if not stmts:
            return AccuracyTargetIR(kind="successive_qoi_change", percent=1.0)
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "successive_qoi_change":
            raise GDECSemanticError(
                "Accuracy target must be 'successive_qoi_change(percent=...)'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        pct = args.get("percent", 1.0)
        if not isinstance(pct, (int, float)) or pct <= 0:
            raise GDECSemanticError(
                f"Accuracy percentage must be positive (received {pct}).", call.loc
            )
        return AccuracyTargetIR(kind="successive_qoi_change", percent=float(pct))

    def _extract_budget(self, stmts: Optional[List[Statement]]) -> BudgetIR:
        if not stmts:
            return BudgetIR(kind="max_dofs", value=25000, max_iterations=15)
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "max_dofs":
            raise GDECSemanticError(
                "Budget must be defined as 'max_dofs(value=..., [max_iterations=...])'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        if call.positional_args:
            val = self._eval_value(call.positional_args[0])
        else:
            val = args.get("value", 25000)
        if not isinstance(val, (int, float)) or int(val) <= 0:
            raise GDECSemanticError(f"Budget 'value' must be a positive integer (received {val}).", call.loc)
        max_iters = args.get("max_iterations", 15)
        return BudgetIR(kind="max_dofs", value=int(val), max_iterations=int(max_iters))

    def _extract_adaptivity(self, stmts: Optional[List[Statement]]) -> AdaptivityIR:
        if not stmts:
            return AdaptivityIR(strategy="goal_aware", marking_fraction=0.3, cost_aware=True)
        stmt = stmts[-1]
        val = self._eval_value(stmt.value)
        if isinstance(val, str):
            strategy = val
            frac = 0.3
            cost_aware = True
        elif isinstance(val, FunctionCall):
            strategy = val.func_name
            args = {k: self._eval_value(v) for k, v in val.named_args.items()}
            frac = float(args.get("fraction", 0.3))
            cost_aware = bool(args.get("cost_aware", True))
        else:
            raise GDECSemanticError("Invalid adaptivity specification.", stmt.loc)

        if strategy not in ["goal_aware", "recovery", "uniform"]:
            raise GDECSemanticError(
                f"Unsupported adaptivity strategy '{strategy}'. Supported are 'goal_aware', 'recovery', 'uniform'.",
                stmt.loc,
            )
        return AdaptivityIR(
            strategy=strategy,  # type: ignore
            marking_fraction=frac,
            cost_aware=cost_aware,
        )

    def _extract_backend(self, stmts: Optional[List[Statement]]) -> BackendIR:
        if not stmts:
            return BackendIR(device="cpu")
        stmt = stmts[-1]
        dev = self._eval_value(stmt.value)
        if dev not in ["cpu", "cuda", "hip", "sycl", "tpu"]:
            raise GDECSemanticError(
                f"Unknown backend device '{dev}'. Supported: 'cpu', 'cuda', 'hip', 'sycl', 'tpu'.",
                stmt.loc,
            )
        if dev != "cpu":
            # Strict Part 2.D compliance:
            # "Do not silently route a requested GPU calculation to the CPU. If CUDA is unavailable or not implemented, explicitly report that."
            raise GDECSemanticError(
                f"Backend '{dev}' was requested, but no GPU accelerator hardware or CUDA backend is available in GDEC v0.2.1. "
                f"Per GDEC architecture rules, requested accelerator computations are not silently routed to CPU.",
                stmt.loc,
            )
        return BackendIR(device="cpu")
