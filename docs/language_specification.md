# GDEC Engineering Language Specification (.gdc)

## 1. Syntax Overview
The GDEC language (`.gdc`) is a declarative domain-specific language designed for expressing mechanical engineering simulations, target outputs, and computational budgets.

## 2. Formal Grammar Rules
Parsed via Lark LALR(1) engine (`src/gdec/language/grammar.lark`):

```text
start: problem_def
problem_def: "problem" IDENTIFIER "{" statement* "}"
statement: IDENTIFIER "=" (IDENTIFIER | function_call | NUMBER)
function_call: IDENTIFIER "(" [arg_list] ")"
arg_list: argument ("," argument)*
argument: IDENTIFIER "=" (NUMBER | IDENTIFIER | STRING)
```

## 3. Supported Declarations

| Keyword | Function / Signature | Parameters | Description |
|:---|:---|:---|:---|
| `physics` | Value: `linear_elasticity` | None | PDE physics formulation (v0.2.2 supports 2D linear elasticity). |
| `geometry` | `rectangle(...)` | `width`, `height`, `thickness` | Rectangular 2D domain with uniform out-of-plane thickness. |
| `material` | `isotropic(...)` | `E`, `nu`, `assumption` | Linear isotropic elasticity (`plane_stress` or `plane_strain`). |
| `fix` | `boundary(...)` | Boundary name (`left`, `right`, `top`, `bottom`) | Essential Dirichlet constraint ($u_x = 0, u_y = 0$). |
| `load` | `traction(...)` | `boundary`, `tx`, `ty` | Natural Neumann surface traction vector (Pa). |
| `objective` | `average_displacement(...)` | `boundary`, `component` (`x` or `y`) | Engineering Quantity of Interest (QoI) to target. |
| `accuracy` | `successive_qoi_change(...)`| `percent` ($>0.0$) | Relative successive change termination threshold. |
| `budget` | `max_dofs(...)` | `value` ($>0$), optional `max_iterations` | Hard limit on total degrees of freedom. |
| `adaptivity` | Value: identifier | `goal_aware`, `recovery`, `uniform` | Adaptive meshing strategy selection. |
| `backend` | `cpu` | Device name | Target compute backend device. |

## 4. Example Specification (`examples/cantilever.gdc`)
```text
problem CantileverDemo {
    physics = linear_elasticity
    geometry = rectangle(width=2.0, height=0.5, thickness=0.02)
    material = isotropic(E=70e9, nu=0.33, assumption=plane_stress)
    fix = boundary(left)
    load = traction(boundary=right, tx=0.0, ty=-1.0e6)
    objective = average_displacement(boundary=right, component=y)
    accuracy = successive_qoi_change(percent=1.0)
    budget = max_dofs(value=25000, max_iterations=15)
    adaptivity = goal_aware
    backend = cpu
}
```
