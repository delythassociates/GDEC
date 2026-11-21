# GDEC Decision Contract Schema Reference (v1.0.0)

**Document ID:** `GDEC-DSE-SCHEMA-001`
**Schema Version:** `1.0.0`
**Date:** 2026-11-22
**Status:** Approved Reference

---

## 1. JSON Schema Definition

The full JSON Schema exported by `DecisionContract.get_json_schema()` defines the formal structure of GDEC contracts.

```json
{
  "$defs": {
    "AcceptanceCriterion": {
      "properties": {
        "operator": { "enum": ["<=", "<", ">=", ">"], "type": "string" },
        "limit": { "type": "number" },
        "unit": { "minLength": 1, "type": "string" },
        "safety_margin": { "default": 0.0, "minimum": 0.0, "type": "number" }
      },
      "required": ["operator", "limit", "unit"],
      "type": "object"
    },
    "ComputationalBudget": {
      "properties": {
        "max_evaluations": { "exclusiveMinimum": 0.0, "type": "integer" },
        "max_wall_clock_seconds": { "exclusiveMinimum": 0.0, "type": "number" },
        "enforced": { "default": false, "type": "boolean" }
      },
      "type": "object"
    },
    "DecisionIdentity": {
      "properties": {
        "id": { "minLength": 1, "type": "string" },
        "schema_version": { "default": "1.0.0", "type": "string" },
        "title": { "minLength": 1, "type": "string" },
        "question": { "minLength": 1, "type": "string" },
        "description": { "type": "string" }
      },
      "required": ["id", "title", "question"],
      "type": "object"
    },
    "DecisionLoss": {
      "properties": {
        "cost_false_acceptance": { "exclusiveMinimum": 0.0, "type": "number" },
        "cost_false_rejection": { "exclusiveMinimum": 0.0, "type": "number" },
        "cost_unit": { "default": "USD", "minLength": 1, "type": "string" }
      },
      "required": ["cost_false_acceptance", "cost_false_rejection"],
      "type": "object"
    },
    "EvidenceRequirements": {
      "properties": {
        "required_categories": { "items": { "type": "string" }, "type": "array" },
        "model_assumptions": { "items": { "type": "string" }, "minItems": 1, "type": "array" },
        "applicable_domain": { "minLength": 1, "type": "string" },
        "numerical_quality_threshold": { "default": 0.05, "exclusiveMinimum": 0.0, "type": "number" },
        "validation_status": { "default": "unvalidated", "type": "string" },
        "known_limitations": { "items": { "type": "string" }, "type": "array" }
      },
      "required": ["model_assumptions", "applicable_domain"],
      "type": "object"
    },
    "PredictiveDistribution": {
      "properties": {
        "family": { "default": "normal", "enum": ["normal"], "type": "string" },
        "mean": { "type": "number" },
        "std": { "minimum": 0.0, "type": "number" },
        "unit": { "minLength": 1, "type": "string" },
        "provenance": { "minLength": 1, "type": "string" }
      },
      "required": ["mean", "std", "unit", "provenance"],
      "type": "object"
    },
    "QuantityOfInterest": {
      "properties": {
        "qoi_id": { "minLength": 1, "type": "string" },
        "name": { "minLength": 1, "type": "string" },
        "unit": { "minLength": 1, "type": "string" },
        "expected_sign": { "default": "any", "enum": ["positive", "negative", "any"], "type": "string" },
        "model_reference": { "type": "string" }
      },
      "required": ["qoi_id", "name", "unit"],
      "type": "object"
    }
  },
  "properties": {
    "identity": { "$ref": "#/$defs/DecisionIdentity" },
    "qoi": { "$ref": "#/$defs/QuantityOfInterest" },
    "criterion": { "$ref": "#/$defs/AcceptanceCriterion" },
    "predictive_distribution": { "$ref": "#/$defs/PredictiveDistribution" },
    "loss": { "$ref": "#/$defs/DecisionLoss" },
    "evidence": { "$ref": "#/$defs/EvidenceRequirements" },
    "budget": { "$ref": "#/$defs/ComputationalBudget" }
  },
  "required": ["identity", "qoi", "criterion", "loss", "evidence"],
  "type": "object"
}
```

---

## 2. Canonical JSON Example

```json
{
  "identity": {
    "id": "DEC-CANTILEVER-001",
    "schema_version": "1.0.0",
    "title": "Cantilever Beam Tip Deflection Release",
    "question": "Does the tip deflection under 1 kN load remain below allowable threshold?",
    "description": "2D elasticity verification for aerospace bracket support"
  },
  "qoi": {
    "qoi_id": "tip_deflection",
    "name": "Vertical Tip Displacement",
    "unit": "mm",
    "expected_sign": "positive"
  },
  "criterion": {
    "operator": "<=",
    "limit": 10.0,
    "unit": "mm",
    "safety_margin": 0.5
  },
  "predictive_distribution": {
    "family": "normal",
    "mean": 8.0,
    "std": 0.5,
    "unit": "mm",
    "provenance": "FEM Solve with Material UQ"
  },
  "loss": {
    "cost_false_acceptance": 1000.0,
    "cost_false_rejection": 100.0,
    "cost_unit": "USD"
  },
  "evidence": {
    "required_categories": ["discretization_error", "boundary_conditions"],
    "model_assumptions": ["linear_elasticity", "small_strain"],
    "applicable_domain": "slender_beam_L_ge_5H",
    "numerical_quality_threshold": 0.05
  }
}
```
