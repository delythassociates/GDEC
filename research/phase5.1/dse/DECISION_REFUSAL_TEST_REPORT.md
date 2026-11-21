# GDEC Phase 5.1 Decision Refusal Test Report

**Document ID:** `GDEC-DSE-REFUSAL-001`
**Date:** 2026-11-22
**Workstream:** D — Deterministic Decision Refusal & Guardrails
**Author:** Lead Engineering Research Orchestrator
**Status:** Tested & Verified

---

## 1. Objective & Philosophy of Simulation Refusal

In safety-critical computational engineering, returning "no answer with an explanation" is vastly superior to returning a "confidently incorrect answer". Traditional FEA software almost never refuses to compute or display results, even when mesh distortion, singular conditioning, or invalid physical assumptions render the output completely unphysical.

GDEC's Decision Sufficiency Engine implements **Deterministic Refusal Gates** that intercept and reject invalid models before unsafe engineering release decisions can occur.

---

## 2. Refusal Test Matrix & Results

All refusal conditions are implemented in `src/gdec/dse/evaluator.py`, `src/gdec/dse/contract.py`, and `src/gdec/dse/scaling.py`, and verified in `tests/test_dse.py`.

### Table 1: Refusal Gate Verification Matrix

| Refusal Gate ID | Trigger Condition | Expected System Behavior | Test Evidence | Verdict |
| :--- | :--- | :--- | :--- | :---: |
| **REF-01** | Missing predictive uncertainty distribution | Refuses to evaluate; returns `INSUFFICIENT_EVIDENCE` or raises `DecisionRefusalError` | `test_evaluator_refusal_on_missing_uncertainty` | **PASS** |
| **REF-02** | Negative standard deviation ($\sigma < 0$) | Schema rejection at contract parse time or runtime refusal | `test_contract_rejects_negative_std` | **PASS** |
| **REF-03** | Non-finite values ($\mu = \text{NaN}$, $\sigma = \infty$) | Evaluator halts; returns structured diagnostic detailing non-finite inputs | `test_evaluator_refusal_on_non_finite_inputs` | **PASS** |
| **REF-04** | Unit inconsistency (e.g. QoI in `mm`, limit in `m`) | Pydantic cross-field validator raises `ContractValidationError` | `test_contract_rejects_unit_mismatch` | **PASS** |
| **REF-05** | Discretization error breaches threshold ($\eta_{\text{DWR}} / \mu > 5\%$) | Evaluator refuses release and issues mandatory `REFINE` verdict | `test_evaluator_dwr_quality_gate` | **PASS** |
| **REF-06** | Zero or negative loss consequences ($C_{\text{FA}} \le 0$) | Contract parser raises validation error | `test_contract_rejects_zero_or_negative_loss` | **PASS** |
| **REF-07** | Non-positive Young's modulus ($E \le 0$) | Scaling engine raises `ScalingAssumptionError` | `test_analytical_scaling_assumption_rejection` | **PASS** |
| **REF-08** | Non-uniform material scaling or stress QoIs | Scaling engine raises `ScalingAssumptionError` | `test_analytical_scaling_assumption_rejection` | **PASS** |

---

## 3. Deep Dive: Zero Uncertainty Guardrail

A dangerous failure mode in naive decision systems is silently defaulting missing uncertainty to zero ($\sigma = 0$).

If an engineer runs a single deterministic FEM simulation ($J = 8.0\text{ mm}$, limit $10.0\text{ mm}$), treating this as $P_{\text{fail}} = 0$ ignores mesh discretization error, load variability, and material tolerances.

GDEC's evaluator **strictly refuses** to evaluate contracts lacking an explicit predictive distribution:
- Missing distribution does **not** default to $\sigma = 0$.
- Returns recommendation `INSUFFICIENT_EVIDENCE`.
- Explains: *"Missing predictive uncertainty distribution (mean and std must be supplied)."*
- Prevents false engineering confidence.
