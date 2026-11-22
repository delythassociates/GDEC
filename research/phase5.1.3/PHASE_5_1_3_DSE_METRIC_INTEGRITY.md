# GDEC Phase 5.1.3 — DSE Numerical Evidence Integrity Specification

**Author:** Lead Decision Intelligence Architect & Scientific Software Verification Specialist  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.3-validation-and-ci-closure`  
**Status:** Audited Specification & Reference Implementation

---

## 1. Context and Problem Statement

In previous implementations, `SingleQoIEvaluator` selected the numerical discretization error metric by inspecting evidence records in a loose loop:
```python
# Legacy vulnerable selection pattern
for rec in evidence_assessment.evidence_records:
    if rec.category.strip().lower() in ("discretization_error", "mesh_convergence", "dwr"):
        if rec.numerical_metric is not None and math.isfinite(rec.numerical_metric):
            effective_dwr = rec.numerical_metric
            break
```
This pattern introduced several safety risks:
1. **Selection of Ineligible Evidence:** If a record had status `UNASSESSED`, `UNVALIDATED`, `EXPIRED`, or mismatched `model_reference` or `applicable_domain`, it could still be selected as the source of truth for the discretization quality threshold.
2. **Arbitrary Category Usage:** Non-discretization records could contaminate evaluation if category names overlapped.
3. **Conflicting Metrics Masking:** If multiple eligible records supplied differing quality metrics (e.g. h-refinement vs p-refinement studies producing contradictory estimates), the first encountered record was silently used, concealing numerical disagreement.
4. **Unit Incompatibility:** Numerical metrics were compared against reference scales without validating physical dimensional consistency.
5. **Reference Scale Erosion:** Missing or near-zero reference scales defaulted silently to arbitrary threshold limits.

Phase 5.1.3 completely eliminates these vulnerabilities through an explicit, auditable selection and validation policy.

---

## 2. Formal Selection Policy for DWR Metrics

### 2.1 Scope of Quality Categories
A numerical metric can only serve as discretization quality evidence if its record belongs to the sanctioned set:
$$\mathcal{C}_{\text{DWR}} = \{\text{"discretization\_error"}, \text{"mesh\_convergence"}, \text{"dwr"}, \text{"numerical\_quality"}\}$$
Records from any other category (e.g. `boundary_conditions`, `material_properties`) are disqualified from supplying the DWR metric, even if they contain finite numerical metrics.

### 2.2 Record-Level Eligibility Filter
A record $r \in \text{assessment.evidence\_records}$ is eligible to supply the DWR metric if and only if all of the following conditions hold:
1. **Category Match:** $\text{category}(r) \in \mathcal{C}_{\text{DWR}}$.
2. **Audited Acceptance:** $r$ has been audited by `evaluate_record_eligibility` and declared acceptable (`rep.is_acceptable == True`).
3. **Maturity / Credibility Status:** $\text{status}(r) \in \{\text{VERIFIED}, \text{VALIDATED}, \text{INDEPENDENTLY\_VALIDATED}, \text{CALIBRATED}\}$. Discredited (`REJECTED`) or stale (`EXPIRED`) records are strictly disqualified.
4. **Model Consistency:** $\text{model\_reference}(r) = \text{contract.qoi.model\_reference}$.
5. **Domain Consistency:** $\text{applicable\_domain}(r) = \text{contract.evidence.applicable\_domain}$.
6. **Provenance Integrity:** Provenance is non-empty and non-whitespace.
7. **Metric Presence:** $\text{numerical\_metric}(r) \ne \text{None}$.

### 2.3 Deterministic Conflict Resolution Policy
Let $\mathcal{R}_{\text{eligible}}$ be the set of eligible records in $\mathcal{C}_{\text{DWR}}$.
- **Case 0 ($\|\mathcal{R}_{\text{eligible}}\| = 0$):**
  If discretization error is required by the contract, evaluation immediately fails closed with `DecisionRecommendation.INSUFFICIENT_EVIDENCE`.
- **Case 1 ($\|\mathcal{R}_{\text{eligible}}\| = 1$):**
  The unique eligible record supplies the metric: $r^* = \mathcal{R}_{\text{eligible}}[0]$.
- **Case $K$ ($\|\mathcal{R}_{\text{eligible}}\| > 1$):**
  The evaluator tests for pairwise agreement between all eligible metrics:
  $$\max_{i, j} \frac{|m_i - m_j|}{\max(|m_i|, 10^{-14})} \le 10^{-6} \quad \text{and} \quad |m_i - m_j| \le 10^{-12}$$
  - **If all metrics agree within numerical tolerance:** Deterministically select the first record $r^* = \mathcal{R}_{\text{eligible}}[0]$.
  - **If any pair disagrees:** **Explicit Refusal Policy Enforced.** The evaluator must never guess or average conflicting metrics. Evaluation immediately fails closed with `DecisionRecommendation.INSUFFICIENT_EVIDENCE` (or raises `DecisionRefusalError` if `raise_on_refusal=True`), logging all conflicting record IDs and values in the diagnostic trail.

---

## 3. Metric Semantics & Threshold Mathematics

### 3.1 Meaning of the DWR Metric
The DWR metric $\eta_{\text{dwr}}$ represents the absolute magnitude of the estimated error in the Quantity of Interest:
$$\eta_{\text{dwr}} \approx |J(u) - J(u_h)| \ge 0$$
- $\eta_{\text{dwr}}$ must be finite (`math.isfinite(effective_dwr)`).
- $\eta_{\text{dwr}}$ must be strictly non-negative ($\eta_{\text{dwr}} \ge 0.0$). Negative values indicate an invalid estimator and trigger immediate refusal.

### 3.2 Unit Consistency
If the selected evidence record specifies a physical unit (`rec.units is not None`), it must strictly match the contract QoI unit:
$$\text{rec.units.strip().lower()} == \text{contract.qoi.unit.strip().lower()}$$
Any discrepancy (e.g. `rec.units = "MPa"` vs `contract.qoi.unit = "mm"`) triggers immediate refusal.

### 3.3 Reference Scale Requirement
Relative discretization error is defined as:
$$\eta_{\text{rel}} = \frac{\eta_{\text{dwr}}}{J_{\text{ref}}}$$
where $J_{\text{ref}}$ is the positive physical reference scale representing the characteristic magnitude of the functional.
- The reference scale must be explicitly provided in `evidence_assessment.reference_scale`.
- If `reference_scale is None`, the evaluation fails closed with `INSUFFICIENT_EVIDENCE`. Silent fallback to arbitrary limit values is forbidden.
- If $\text{reference\_scale} \le 10^{-12}$ or non-finite, the evaluation fails closed.

### 3.4 Quality Gate Enforcement
If $\eta_{\text{rel}} > \tau_{\text{tol}}$ (where $\tau_{\text{tol}} = \text{contract.evidence.numerical_quality_threshold}$), the decision recommendation is unconditionally forced to `DecisionRecommendation.REFINE`.

---

## 4. Diagnostics & Auditable Provenance

Every evaluation result exposes the selected record identifier:
- Property: `result.selected_dwr_record_id: Optional[str]`
- Diagnostics dictionary: `result.diagnostics["selected_dwr_record_id"]`
- Serialized dictionary: `result.to_dict()["selected_dwr_record_id"]`

If no DWR record was selected (e.g. non-discretization decisions or refused evaluations), this field is explicitly `None`.
