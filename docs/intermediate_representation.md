# GDEC Intermediate Representation (IR)

## 1. Schema Design Principles
The GDEC Intermediate Representation (`ProblemIR`) decouples the language frontend from backend execution engines. It is:
- **Solver-Independent**: Expresses physical boundary value problems rather than finite-element matrices.
- **Typed and Validated**: Built with Pydantic v2 schemas (`schema_version = "gdec_ir_v0.1"`).
- **Fully Serializable**: Directly exportable to and loadable from JSON.

## 2. IR Structure
```json
{
  "schema_version": "gdec_ir_v0.1",
  "name": "CantileverDemo",
  "physics": "linear_elasticity",
  "geometry": {
    "kind": "rectangle",
    "width": 2.0,
    "height": 0.5,
    "thickness": 0.02
  },
  "material": {
    "kind": "isotropic",
    "E": 70000000000.0,
    "nu": 0.33,
    "assumption": "plane_stress"
  },
  "boundary_conditions": [
    {
      "boundary": "left",
      "constrained_components": ["x", "y"]
    }
  ],
  "loads": [
    {
      "boundary": "right",
      "tx": 0.0,
      "ty": -1000000.0
    }
  ],
  "objective": {
    "kind": "average_displacement",
    "boundary": "right",
    "component": "y"
  },
  "accuracy": {
    "kind": "successive_qoi_change",
    "percent": 1.0
  },
  "budget": {
    "kind": "max_dofs",
    "value": 25000,
    "max_iterations": 15
  },
  "adaptivity": {
    "strategy": "goal_aware",
    "marking_fraction": 0.3,
    "cost_aware": true
  },
  "backend": {
    "device": "cpu"
  }
}
```

## 3. Backward Compatibility
The schema version `gdec_ir_v0.1` is maintained across v0.2.x releases to guarantee compatibility with historical benchmarks and saved experiment logs.
