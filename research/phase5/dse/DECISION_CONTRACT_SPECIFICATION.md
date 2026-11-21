# GDEC Decision Contract Specification: Schema and Declarative Syntax

**Document Reference:** `research/phase5/dse/DECISION_CONTRACT_SPECIFICATION.md`  
**Workstream:** Agent 4 — Decision Sufficiency Engine Scientific Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Contract Specification Standardized  

---

## 1. Executive Summary

A **Decision Contract** is a formal, machine-verifiable engineering specification that defines:
1. The exact engineering question to be answered.
2. The relevant physical quantities of interest (QoIs) and bounding constraints.
3. The acceptable probability of false acceptance ($\alpha_{\text{critical}}$) and consequence weighting.
4. The computational and resource budgets.
5. The required evidence standards (discretization error bounds, verification mode).
6. The explicit criteria under which the system must refuse to decide.

This document defines the schema, validation rules, and GDEC DSL representation of a Decision Contract.

---

## 2. Decision Contract Schema (JSON / Typed Representation)

```json
{
  "$schema": "https://gdec.internal/schemas/v0.3/decision_contract.json",
  "contract_id": "DC-2026-BRACKET-001",
  "version": "1.0.0",
  "engineering_question": "Does the cantilever bracket support the design shear load with less than 2.0 mm tip deflection under 99.5% decision confidence?",
  "decision_type": "CONFORMANCE_VERIFICATION",
  
  "design_parameters": {
    "geometry": {
      "type": "CANTILEVER_2D",
      "length": 2.0,
      "height": 0.5,
      "thickness": 0.05
    },
    "material": {
      "model": "ISOTROPIC_LINEAR_ELASTIC",
      "youngs_modulus_nominal": 7.0e10,
      "poissons_ratio": 0.33,
      "modulus_uncertainty": {
        "distribution": "GAUSSIAN",
        "std_dev_ratio": 0.05
      }
    },
    "boundary_conditions": {
      "fixed_boundaries": [{"boundary": "left", "constrained_dofs": ["x", "y"]}],
      "tractions": [{"boundary": "right", "type": "parabolic_shear", "total_load_y": -1000.0}]
    }
  },

  "quantity_of_interest": {
    "qoi_id": "tip_displacement_y",
    "functional_type": "average_boundary_displacement",
    "boundary": "right",
    "direction": "y",
    "scaling": 1000.0,
    "unit": "mm"
  },

  "decision_criteria": {
    "constraint_type": "UPPER_BOUND",
    "limit_value": -2.0,
    "required_decision_confidence": 0.995,
    "loss_consequences": {
      "false_acceptance_cost": 500000.0,
      "false_rejection_cost": 5000.0
    },
    "safety_margin_multiplier": 3.0
  },

  "computational_budget": {
    "max_dofs_hard_limit": 50000,
    "max_adaptive_iterations": 10,
    "max_wallclock_seconds": 60.0,
    "preferred_backend": "AUTO"
  },

  "evidence_standards": {
    "discretization_uncertainty_estimator": "DUAL_WEIGHTED_RESIDUAL",
    "verification_mode": "FOUR_GRID_ASYMPTOTIC",
    "require_m3_stability": true,
    "asymptotic_stability_tolerance": 0.50,
    "allow_unregularized_singularities": false
  }
}
```

---

## 3. Declarative GDEC DSL Syntax Extension

We propose an intuitive, high-level DSL syntax block that integrates seamlessly into GDEC's existing compiler pipeline:

```gdec
contract bracket_safety_audit {
    question: "Verify tip deflection conforms to serviceability limit under 5% modulus uncertainty";
    
    // Geometry & Material
    geometry cantilever { L: 2.0, H: 0.5, thickness: 0.05 }
    material aluminium { E: 70.0e9 +/- 5%, nu: 0.33 }
    
    // Boundary Conditions
    support left_clamped { boundary: "left", fixed: [ux, uy] }
    load tip_shear { boundary: "right", shear_force_y: -1000.0 }
    
    // Quantity of Interest and Decision Threshold
    qoi tip_deflection = average_boundary_displacement("right", direction="y")
    
    decision serviceability_check {
        assert tip_deflection > -2.0 mm;
        confidence: 99.5%;
        false_acceptance_consequence: CRITICAL;
    }
    
    // Computational Governance
    budget {
        max_dofs: 50000;
        max_iterations: 8;
        stopping_policy: VALUE_OF_INFORMATION;
    }
    
    evidence {
        estimator: DWR;
        verify_asymptotic_order: true;
    }
}
```

---

## 4. Contract Output: The Decision Sufficiency Certificate

Upon completion, the engine emits an immutable, cryptographically hashed **Decision Sufficiency Certificate**:

```json
{
  "certificate_id": "CERT-2026-B8572D-001",
  "timestamp": "2026-11-22T01:05:00Z",
  "contract_id": "DC-2026-BRACKET-001",
  "decision_verdict": "ACCEPTED_CONFORMING",
  "decision_statement": "Component tip deflection complies with the 2.0 mm limit with 99.82% posterior confidence (exceeding 99.5% requirement). Discretization error is bounded to 0.012 mm by DWR.",
  
  "quantitative_summary": {
    "qoi_computed": -1.9082,
    "qoi_unit": "mm",
    "constraint_limit": -2.0000,
    "raw_safety_margin": 0.0918,
    "dwr_discretization_uncertainty": 0.0142,
    "parameter_uncertainty_99_5": 0.0195,
    "net_effective_margin": 0.0581,
    "margin_to_error_ratio": 6.46
  },
  
  "computational_efficiency": {
    "final_mesh_dofs": 4034,
    "iterations_executed": 4,
    "budget_utilized_percent": 8.07,
    "stopping_reason": "SUFFICIENCY_ACHIEVED_EVSI_ZERO",
    "unnecessary_dofs_saved_vs_uniform": 6064
  },
  
  "evidence_hash_sha256": "4a3e4a7efddcec3329550fba8886b9daae3cd329"
}
```
If an ill-posed problem is supplied, the engine emits a **Deterministic Refusal Certificate** with exact mathematical reasons, safeguarding the engineering organization.
