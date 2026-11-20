"""
Semantic analysis and AST-to-IR lowering for GDEC (v0.2.3).
Performs strict validation, rejects non-physical inputs, validates point coordinates,
and generates typed ProblemIR.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Set

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

    ALLOWED_TOP_LEVEL: Set[str] = {
        "physics",
        "geometry",
        "material",
        "fix",
        "boundary_condition",
        "load",
        "objective",
        "accuracy",
        "budget",
        "adaptivity",
        "backend",
    }

    SINGLE_DECLARATION_KEYS: Set[str] = {
        "physics",
        "geometry",
        "material",
        "objective",
        "accuracy",
        "budget",
        "adaptivity",
        "backend",
    }

    def __init__(self):
        pass

    def analyze(self, ast: ProblemNode) -> ProblemIR:
        if not ast.name or not ast.name.isidentifier():
            raise GDECSemanticError(f"Invalid problem identifier '{ast.name}'", ast.loc)

        # Collect statements and check for unknown declarations and duplicates
        stmts: Dict[str, List[Statement]] = {}
        for s in ast.statements:
            if s.key not in self.ALLOWED_TOP_LEVEL:
                raise GDECSemanticError(
                    f"Unknown top-level declaration '{s.key}'. Allowed declarations: {sorted(self.ALLOWED_TOP_LEVEL)}.",
                    s.loc,
                )
            stmts.setdefault(s.key, []).append(s)

        for key in self.SINGLE_DECLARATION_KEYS:
            if key in stmts and len(stmts[key]) > 1:
                second = stmts[key][1]
                raise GDECSemanticError(
                    f"Duplicate declaration of '{key}'. Only one '{key}' block is permitted per problem.",
                    second.loc,
                )

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

        # 6. Objective (validated against geometry bounds)
        objective = self._extract_objective(stmts.get("objective"), geometry)

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
            val = expr.value
            if math.isnan(val) or math.isinf(val):
                raise GDECSemanticError(f"Numeric value cannot be NaN or Infinite: {val}", expr.loc)
            return val
        elif isinstance(expr, Identifier):
            return expr.name
        elif isinstance(expr, StringLiteral):
            return expr.value
        elif isinstance(expr, FunctionCall):
            return expr
        raise GDECSemanticError(f"Unsupported expression type: {type(expr).__name__}", getattr(expr, "loc", None))

    def _eval_number(self, val: Any, name: str, loc: Optional[SourceLocation] = None) -> float:
        if not isinstance(val, (int, float)):
            raise GDECSemanticError(f"Parameter '{name}' must be a numeric value (received {val}).", loc)
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval):
            raise GDECSemanticError(f"Parameter '{name}' cannot be NaN or Infinite.", loc)
        return fval

    def _extract_physics(self, stmts: Optional[List[Statement]]) -> str:
        if not stmts:
            raise GDECSemanticError("Missing required 'physics' declaration in problem definition.")
        stmt = stmts[-1]
        val = self._eval_value(stmt.value)
        if val != "linear_elasticity":
            raise GDECSemanticError(
                f"Unsupported physics model '{val}'. GDEC v0.2.3 only supports 'linear_elasticity'.",
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
        allowed_args = {"width", "height", "thickness"}
        unknown = set(call.named_args.keys()) - allowed_args
        if unknown:
            raise GDECSemanticError(
                f"Unknown arguments for 'rectangle': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                call.loc,
            )

        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        if "width" not in args:
            raise GDECSemanticError("Geometry requires 'width'.", call.loc)
        width = self._eval_number(args["width"], "width", call.loc)
        if width <= 0:
            raise GDECSemanticError(f"Geometry 'width' must be strictly positive (received {width}).", call.loc)

        if "height" not in args:
            raise GDECSemanticError("Geometry requires 'height'.", call.loc)
        height = self._eval_number(args["height"], "height", call.loc)
        if height <= 0:
            raise GDECSemanticError(f"Geometry 'height' must be strictly positive (received {height}).", call.loc)

        thickness_val = args.get("thickness", 1.0)
        thickness = self._eval_number(thickness_val, "thickness", call.loc)
        if thickness <= 0:
            raise GDECSemanticError(f"Geometry 'thickness' must be strictly positive (received {thickness}).", call.loc)

        return GeometryIR(
            kind="rectangle",
            width=width,
            height=height,
            thickness=thickness,
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
        allowed_args = {"E", "nu", "assumption"}
        unknown = set(call.named_args.keys()) - allowed_args
        if unknown:
            raise GDECSemanticError(
                f"Unknown arguments for 'isotropic': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                call.loc,
            )

        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        if "E" not in args:
            raise GDECSemanticError("Material requires Young's modulus 'E'.", call.loc)
        E = self._eval_number(args["E"], "E", call.loc)
        if E <= 0:
            raise GDECSemanticError(
                f"Young's modulus 'E' must be a strictly positive number (received {E}).",
                call.loc,
            )

        if "nu" not in args:
            raise GDECSemanticError("Material requires Poisson's ratio 'nu'.", call.loc)
        nu = self._eval_number(args["nu"], "nu", call.loc)
        if not (-1.0 < nu < 0.5):
            raise GDECSemanticError(
                f"Poisson's ratio 'nu' must satisfy thermodynamic stability -1.0 < nu < 0.5 (received {nu}).",
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
            E=E,
            nu=nu,
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
                allowed_args = {"boundary"}
                unknown = set(call.named_args.keys()) - allowed_args
                if unknown:
                    raise GDECSemanticError(
                        f"Unknown arguments for 'boundary': {sorted(unknown)}.",
                        call.loc,
                    )
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
            allowed_args = {"boundary", "tx", "ty"}
            unknown = set(call.named_args.keys()) - allowed_args
            if unknown:
                raise GDECSemanticError(
                    f"Unknown arguments for 'traction': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                    call.loc,
                )

            args = {k: self._eval_value(v) for k, v in call.named_args.items()}

            bnd = args.get("boundary")
            if bnd not in valid_boundaries:
                raise GDECSemanticError(
                    f"Invalid load boundary '{bnd}'. Must be one of {valid_boundaries}.",
                    call.loc,
                )
            tx = self._eval_number(args.get("tx", 0.0), "tx", call.loc)
            ty = self._eval_number(args.get("ty", 0.0), "ty", call.loc)
            loads.append(TractionLoadIR(boundary=bnd, tx=tx, ty=ty))
        return loads

    def _extract_objective(self, stmts: Optional[List[Statement]], geometry: GeometryIR) -> ObjectiveIR:
        if not stmts:
            raise GDECSemanticError("Missing required 'objective' declaration.")
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name not in [
            "average_displacement",
            "point_displacement",
        ]:
            raise GDECSemanticError(
                "Objective must be defined as 'average_displacement(boundary=..., component=...)' "
                "or 'point_displacement(x=..., y=..., component=...)'",
                stmt.loc,
            )
        call = stmt.value
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}

        if call.func_name == "average_displacement":
            allowed_args = {"boundary", "component"}
            unknown = set(call.named_args.keys()) - allowed_args
            if unknown:
                raise GDECSemanticError(
                    f"Unknown arguments for 'average_displacement': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                    call.loc,
                )
            bnd = args.get("boundary", "right")
            if bnd not in {"left", "right", "top", "bottom"}:
                raise GDECSemanticError(f"Objective boundary '{bnd}' is invalid.", call.loc)

            comp = args.get("component", "y")
            if comp not in {"x", "y"}:
                raise GDECSemanticError(f"Objective component '{comp}' must be 'x' or 'y'.", call.loc)

            return ObjectiveIR(
                kind="average_displacement",
                boundary=bnd,
                component=comp,
            )

        elif call.func_name == "point_displacement":
            allowed_args = {"x", "y", "component"}
            unknown = set(call.named_args.keys()) - allowed_args
            if unknown:
                raise GDECSemanticError(
                    f"Unknown arguments for 'point_displacement': {sorted(unknown)}. Allowed: {sorted(allowed_args)}. "
                    f"Note: 'point_displacement' requires explicit spatial coordinates 'x' and 'y', not a boundary name.",
                    call.loc,
                )

            if "x" not in args or "y" not in args:
                raise GDECSemanticError(
                    "Point displacement objective requires coordinates 'x' and 'y'.",
                    call.loc,
                )
            px = self._eval_number(args["x"], "x", call.loc)
            py = self._eval_number(args["y"], "y", call.loc)

            comp = args.get("component", "y")
            if comp not in {"x", "y"}:
                raise GDECSemanticError(f"Objective component '{comp}' must be 'x' or 'y'.", call.loc)

            # Validate that the point lies within domain bounds
            if px < 0.0 or px > geometry.width or py < 0.0 or py > geometry.height:
                raise GDECSemanticError(
                    f"Objective point ({px}, {py}) lies outside domain bounds [0, {geometry.width}] x [0, {geometry.height}].",
                    call.loc,
                )

            return ObjectiveIR(
                kind="point_displacement",
                component=comp,
                point_x=px,
                point_y=py,
            )

        raise GDECSemanticError(f"Unsupported objective kind: {call.func_name}", call.loc)

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
        allowed_args = {"percent"}
        unknown = set(call.named_args.keys()) - allowed_args
        if unknown:
            raise GDECSemanticError(
                f"Unknown arguments for 'successive_qoi_change': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                call.loc,
            )
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        pct_val = args.get("percent", 1.0)
        pct = self._eval_number(pct_val, "percent", call.loc)
        if pct <= 0:
            raise GDECSemanticError(
                f"Accuracy percentage must be strictly positive (received {pct}).", call.loc
            )
        return AccuracyTargetIR(kind="successive_qoi_change", percent=pct)

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
        allowed_args = {"value", "max_iterations"}
        unknown = set(call.named_args.keys()) - allowed_args
        if unknown:
            raise GDECSemanticError(
                f"Unknown arguments for 'max_dofs': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                call.loc,
            )
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        if call.positional_args:
            val = self._eval_value(call.positional_args[0])
        else:
            val = args.get("value", 25000)

        num_val = self._eval_number(val, "value", call.loc)
        if num_val <= 0 or not float(num_val).is_integer():
            raise GDECSemanticError(f"Budget 'value' must be a positive integer (received {val}).", call.loc)

        max_iters_val = args.get("max_iterations", 15)
        max_iters = self._eval_number(max_iters_val, "max_iterations", call.loc)
        if max_iters <= 0 or not float(max_iters).is_integer():
            raise GDECSemanticError(f"Budget 'max_iterations' must be a positive integer (received {max_iters_val}).", call.loc)

        return BudgetIR(kind="max_dofs", value=int(num_val), max_iterations=int(max_iters))

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
            allowed_args = {"fraction", "cost_aware"}
            unknown = set(val.named_args.keys()) - allowed_args
            if unknown:
                raise GDECSemanticError(
                    f"Unknown arguments for adaptivity '{strategy}': {sorted(unknown)}. Allowed: {sorted(allowed_args)}.",
                    val.loc,
                )
            args = {k: self._eval_value(v) for k, v in val.named_args.items()}
            frac_val = args.get("fraction", 0.3)
            frac = self._eval_number(frac_val, "fraction", val.loc)
            if not (0.0 < frac <= 1.0):
                raise GDECSemanticError(f"Adaptivity marking fraction must be in (0, 1] (received {frac}).", val.loc)
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
            raise GDECSemanticError(
                f"Backend '{dev}' was requested, but no GPU accelerator hardware or CUDA backend is available in GDEC v0.2.3. "
                f"Per GDEC architectural integrity rules, requested accelerator computations are not silently routed to CPU.",
                stmt.loc,
            )
        return BackendIR(device="cpu")
