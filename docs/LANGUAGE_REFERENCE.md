# GDEC Language Reference (v0.1)

GDEC Language (`.gdc`) is a declarative domain-specific language for goal-driven engineering simulations.

## Syntax Specification

### 1. Problem Block
Every specification starts with a named problem block:
```text
problem <Identifier> {
    <statement>
    ...
}
```

### 2. Available Statements & Signatures

| Key | Signature | Allowed Values / Parameters | Description |
| :--- | :--- | :--- | :--- |
| `physics` | `linear_elasticity` | `linear_elasticity` | Governing PDE module (v0.1 supports linear elasticity). |
| `geometry` | `rectangle(...)` | `width` (m), `height` (m), `thickness` (m) | 2D plate domain geometry. |
| `material` | `isotropic(...)` | `E` (Pa), `nu` ($-1.0 < \nu < 0.5$), `assumption` (`plane_stress` \| `plane_strain`) | Material constitution. |
| `fix` | `boundary(<name>)` | `left`, `right`, `top`, `bottom` | Essential clamped boundary ($u_x = 0, u_y = 0$). |
| `load` | `traction(...)` | `boundary`, `tx` (Pa), `ty` (Pa) | Surface traction vector. |
| `objective` | `average_displacement(...)` | `boundary`, `component` (`x` \| `y`) | Quantity of Interest to evaluate and optimize accuracy for. |
| `accuracy` | `successive_qoi_change(...)` | `percent` ($> 0.0$) | Successive discrete mesh convergence threshold. |
| `budget` | `max_dofs(...)` | `value` ($> 0$), optional `max_iterations` | Hard computational budget cap. |
| `adaptivity` | `<strategy>` | `goal_aware`, `recovery`, `uniform` | Adaptive refinement strategy. |
| `backend` | `<device>` | `cpu` (v0.1 supported), `cuda`, `hip`, `sycl` | Computational backend device. |

---

## Canonical Example

```text
problem CantileverDemo {

    physics = linear_elasticity

    geometry = rectangle(
        width = 2.0,
        height = 0.5,
        thickness = 0.02
    )

    material = isotropic(
        E = 70e9,
        nu = 0.33,
        assumption = plane_stress
    )

    fix = boundary(left)

    load = traction(
        boundary = right,
        tx = 0.0,
        ty = -1.0e6
    )

    objective = average_displacement(
        boundary = right,
        component = y
    )

    accuracy = successive_qoi_change(
        percent = 1.0
    )

    budget = max_dofs(
        value = 25000
    )

    adaptivity = goal_aware

    backend = cpu
}
```
