"""
Semantic analysis and AST-to-IR lowering for GDEC.
Performs strict validation and generates typed ProblemIR.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import math

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

        # Reject misspelled declarations and duplicate singleton declarations.
        allowed = {
            "physics", "geometry", "material", "fix", "boundary_condition",
            "load", "objective", "accuracy", "budget", "adaptivity", "backend",
        }
        singleton = {
            "physics", "geometry", "material", "objective", "accuracy",
            "budget", "adaptivity", "backend",
        }
        stmts: Dict[str, List[Statement]] = {}
        for statement in ast.statements:
            if statement.key not in allowed:
                raise GDECSemanticError(
                    f"Unknown declaration '{statement.key}'. Supported declarations: {sorted(allowed)}.",
                    statement.loc,
                )
            stmts.setdefault(statement.key, []).append(statement)
            if statement.key in singleton and len(stmts[statement.key]) > 1:
                raise GDECSemanticError(
                    f"Duplicate declaration '{statement.key}'. This declaration may appear only once.",
                    statement.loc,
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

        # Cross-validation: conflicting boundary conditions between fix and load
        fixed_boundaries = {bc.boundary for bc in bcs}
        for statement in stmts.get("load", []):
            if isinstance(statement.value, FunctionCall) and statement.value.func_name == "traction":
                load_bnd = self._eval_value(statement.value.named_args.get("boundary"))
                if load_bnd in fixed_boundaries:
                    raise GDECSemanticError(
                        f"Conflicting boundary condition on '{load_bnd}': cannot apply traction load to fixed Dirichlet boundary.",
                        statement.loc,
                    )

        # Cross-validation: objective boundary cannot be on a fixed Dirichlet boundary
        if objective.boundary in fixed_boundaries:
            obj_stmts = stmts.get("objective", [])
            loc = obj_stmts[0].loc if obj_stmts else None
            raise GDECSemanticError(
                f"Conflicting objective boundary '{objective.boundary}': cannot evaluate displacement objective on a fixed Dirichlet boundary.",
                loc,
            )

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

    @staticmethod
    def _validate_named_args(
        call: FunctionCall,
        allowed: set[str],
        required: Optional[set[str]] = None,
    ) -> None:
        unknown = set(call.named_args) - allowed
        if unknown:
            raise GDECSemanticError(
                f"Unknown argument(s) for '{call.func_name}': {sorted(unknown)}. "
                f"Supported arguments: {sorted(allowed)}.",
                call.loc,
            )
        missing = (required or set()) - set(call.named_args)
        if missing:
            raise GDECSemanticError(
                f"Missing required argument(s) for '{call.func_name}': {sorted(missing)}.",
                call.loc,
            )

    @staticmethod
    def _finite_number(value: Any, label: str, loc: Optional[SourceLocation]) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise GDECSemanticError(f"'{label}' must be a finite number (received {value}).", loc)
        return float(value)

    @classmethod
    def _positive_number(cls, value: Any, label: str, loc: Optional[SourceLocation]) -> float:
        result = cls._finite_number(value, label, loc)
        if result <= 0.0:
            if "Young's modulus" in label:
                raise GDECSemanticError(
                    f"Young's modulus 'E' must be a strictly positive number (received {value}).",
                    loc,
                )
            raise GDECSemanticError(f"'{label}' must be strictly positive (received {value}).", loc)
        return result

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
        if call.positional_args:
            raise GDECSemanticError(
                "Geometry 'rectangle' takes only named arguments (width, height, thickness).",
                call.loc,
            )
        self._validate_named_args(call, {"width", "height", "thickness"}, {"width", "height"})
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        width = self._positive_number(args["width"], "geometry width", call.loc)
        height = self._positive_number(args["height"], "geometry height", call.loc)
        thickness = self._positive_number(args.get("thickness", 1.0), "geometry thickness", call.loc)

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
        if call.positional_args:
            raise GDECSemanticError(
                "Material 'isotropic' takes only named arguments (E, nu, assumption).",
                call.loc,
            )
        self._validate_named_args(call, {"E", "nu", "assumption"}, {"E", "nu"})
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        youngs_modulus = self._positive_number(args["E"], "Young's modulus E", call.loc)
        poisson = self._finite_number(args["nu"], "Poisson's ratio nu", call.loc)
        if not (-1.0 < poisson < 0.5):
            raise GDECSemanticError(
                f"Poisson's ratio 'nu' must satisfy -1.0 < nu < 0.5 (received {poisson}).",
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
            E=youngs_modulus,
            nu=poisson,
            assumption=assumption,
        )

    def _extract_bcs(self, stmts: List[Statement]) -> List[BoundaryConditionIR]:
        if not stmts:
            raise GDECSemanticError("At least one boundary condition ('fix') must be specified.")
        bcs = []
        valid_boundaries = {"left", "right", "top", "bottom"}
        seen_bcs = set()
        for stmt in stmts:
            call = stmt.value
            bnd = None
            comps = ["x", "y"]
            if isinstance(call, FunctionCall) and call.func_name == "boundary":
                self._validate_named_args(call, {"boundary"})
                if len(call.positional_args) > 1 or (call.positional_args and "boundary" in call.named_args):
                    raise GDECSemanticError(
                        "boundary accepts exactly one boundary name, either positional or named.",
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
            if bnd in seen_bcs:
                raise GDECSemanticError(
                    f"Duplicate boundary condition on boundary '{bnd}'. Each boundary may have at most one fix declaration.",
                    stmt.loc,
                )
            seen_bcs.add(bnd)
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
            if call.positional_args:
                raise GDECSemanticError(
                    "Load 'traction' takes only named arguments (boundary, tx, ty).",
                    call.loc,
                )
            self._validate_named_args(call, {"boundary", "tx", "ty"}, {"boundary"})
            args = {k: self._eval_value(v) for k, v in call.named_args.items()}

            bnd = args.get("boundary")
            if bnd not in valid_boundaries:
                raise GDECSemanticError(
                    f"Invalid load boundary '{bnd}'. Must be one of {valid_boundaries}.",
                    call.loc,
                )
            tx = self._finite_number(args.get("tx", 0.0), "traction tx", call.loc)
            ty = self._finite_number(args.get("ty", 0.0), "traction ty", call.loc)
            loads.append(TractionLoadIR(boundary=bnd, tx=tx, ty=ty))
        return loads

    def _extract_objective(self, stmts: Optional[List[Statement]]) -> ObjectiveIR:
        if not stmts:
            raise GDECSemanticError("Missing required 'objective' declaration.")
        stmt = stmts[-1]
        if not isinstance(stmt.value, FunctionCall) or stmt.value.func_name != "average_displacement":
            raise GDECSemanticError(
                "Only 'average_displacement(boundary=..., component=...)' is implemented. "
                "point_displacement is rejected until point-evaluation semantics are implemented.",
                stmt.loc,
            )
        call = stmt.value
        if call.positional_args:
            raise GDECSemanticError(
                "Objective 'average_displacement' takes only named arguments (boundary, component).",
                call.loc,
            )
        self._validate_named_args(call, {"boundary", "component"})
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
        if call.positional_args:
            raise GDECSemanticError(
                "Accuracy target 'successive_qoi_change' takes only named arguments (percent).",
                call.loc,
            )
        self._validate_named_args(call, {"percent"})
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        pct = self._positive_number(args.get("percent", 1.0), "accuracy percentage", call.loc)
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
        self._validate_named_args(call, {"value", "max_iterations"})
        if len(call.positional_args) > 1 or (call.positional_args and "value" in call.named_args):
            raise GDECSemanticError(
                "max_dofs accepts one value, either positional or named, not both.",
                call.loc,
            )
        args = {k: self._eval_value(v) for k, v in call.named_args.items()}
        if call.positional_args:
            val = self._eval_value(call.positional_args[0])
        else:
            val = args.get("value", 25000)
        budget_value = self._finite_number(val, "DOF budget", call.loc)
        if budget_value <= 0 or not budget_value.is_integer():
            raise GDECSemanticError(
                f"Budget 'value' must be a positive whole number (received {val}).", call.loc
            )
        max_iters_value = self._finite_number(args.get("max_iterations", 15), "max_iterations", call.loc)
        if max_iters_value <= 0 or not max_iters_value.is_integer():
            raise GDECSemanticError(
                f"'max_iterations' must be a positive whole number (received {max_iters_value}).",
                call.loc,
            )
        return BudgetIR(
            kind="max_dofs", value=int(budget_value), max_iterations=int(max_iters_value)
        )

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
            if val.positional_args:
                raise GDECSemanticError(
                    f"Adaptivity strategy '{strategy}' takes only named arguments (fraction, cost_aware).",
                    val.loc,
                )
            self._validate_named_args(val, {"fraction", "cost_aware"})
            args = {k: self._eval_value(v) for k, v in val.named_args.items()}
            frac = self._finite_number(args.get("fraction", 0.3), "adaptivity fraction", val.loc)
            raw_cost_aware = args.get("cost_aware", True)
            if raw_cost_aware is True or (
                isinstance(raw_cost_aware, str) and raw_cost_aware == "true"
            ):
                cost_aware = True
            elif raw_cost_aware is False or (
                isinstance(raw_cost_aware, str) and raw_cost_aware == "false"
            ):
                cost_aware = False
            else:
                raise GDECSemanticError(
                    "'cost_aware' must be the literal true or false.", val.loc
                )
        else:
            raise GDECSemanticError("Invalid adaptivity specification.", stmt.loc)

        if not (0.0 < frac <= 1.0):
            raise GDECSemanticError(
                f"Adaptivity fraction must satisfy 0 < fraction <= 1 (received {frac}).",
                stmt.loc,
            )
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
                f"Backend '{dev}' was requested, but no GPU accelerator hardware or CUDA backend is available in GDEC v0.2.1 "
                f"(no accelerator backend is implemented in this GDEC release). "
                f"Per GDEC architecture rules, requested accelerator computations are not silently routed to CPU.",
                stmt.loc,
            )
        return BackendIR(device="cpu")
