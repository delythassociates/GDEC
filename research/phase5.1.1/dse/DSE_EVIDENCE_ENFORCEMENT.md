# DSE Evidence Enforcement & Verification Protocol (Phase 5.1.1)

## 1. Executive Summary

In GDEC Phase 5.1, the Decision Sufficiency Engine (DSE) prototype allowed decision evaluation to proceed directly from numerical parameters (mean, standard deviation, and bound) without formal verification of the empirical evidence backing those parameters. Furthermore, the prototype permitted callers to pass `allow_refine=False`, which bypassed DWR discretisation error bounds and forced a recommendation even under severe mesh under-refinement.

In Phase 5.1.1, evidence enforcement is instituted as a mandatory, fail-closed gate. Under this architecture:
1. A decision evaluation cannot produce an actionable engineering recommendation (`RELEASE`) without a validated, typed `EvidenceAssessment`.
2. Every declared required category in `contract.evidence.required_categories` must be satisfied by a validated `EvidenceRecord` possessing unambiguous provenance (`source_artifact`, `recorded_by`, `timestamp`).
3. Domain, model, and physical boundary condition tags must match between the decision contract and evidence records.
4. Any missing evidence record, unvalidated record (`ValidationStatus.UNVALIDATED` or `REJECTED`), or unprovenanced assumption immediately aborts decision evaluation, forcing `DecisionRecommendation.INSUFFICIENT_EVIDENCE`.
5. The `allow_refine` bypass is completely removed. Discretisation quality breaches always force `DecisionRecommendation.REFINE`.

---

## 2. Evidence Data Model (`EvidenceRecord` & `EvidenceAssessment`)

Evidence is represented by strictly typed frozen dataclasses in `src/gdec/dse/evidence.py`:

```python
class ValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    UNVALIDATED = "UNVALIDATED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    category: str  # e.g., "fem_mesh_convergence", "material_characterization", "load_calibration"
    domain_reference: str
    model_reference: str
    qoi_name: str
    status: ValidationStatus
    source_artifact: str
    recorded_by: str
    timestamp: str
    metrics: Dict[str, float] = field(default_factory=dict)
    assumptions_attested: Tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

@dataclass(frozen=True)
class EvidenceAssessment:
    assessment_id: str
    records: Tuple[EvidenceRecord, ...]
    assessor: str
    timestamp: str
    notes: str = ""
```

---

## 3. Mandatory Evidence Verification Gates

When `SingleQoIEvaluator.evaluate(contract, assessment)` is invoked, it evaluates the following sequence of evidence verification gates **before** computing loss integrals or risk metrics:

### Gate 1: Assessment Presence
- If `assessment is None`, the evaluator immediately returns `DecisionEvaluationResult(recommendation=DecisionRecommendation.INSUFFICIENT_EVIDENCE, refusal_reasons=["No EvidenceAssessment provided..."])`.
- No Bayesian expected loss calculation is performed.

### Gate 2: Category Completeness
- All categories listed in `contract.evidence.required_categories` must have at least one corresponding record in `assessment.records`.
- If any required category is missing, `INSUFFICIENT_EVIDENCE` is returned.

### Gate 3: Validation Credibility
- Every record matching a required category must have `status == ValidationStatus.VALIDATED`.
- If any record is `UNVALIDATED`, `REJECTED`, or `EXPIRED`, `INSUFFICIENT_EVIDENCE` is returned.

### Gate 4: Domain & Model Reference Consistency
- The `domain_reference` and `model_reference` on each record must match the contract's `domain_reference` and `model_reference`.
- If an evidence record belongs to a different domain or model configuration, it is rejected.

### Gate 5: Assumption Provenance & Attestation
- Required engineering assumptions (e.g., linear elasticity, small strains, boundary fixture rigidity) must be explicitly listed in `assumptions_attested` on the relevant evidence records.

---

## 4. DWR Discretisation Quality Enforcement

The finite element dual-weighted residual (DWR) discretisation error must satisfy the contract's declared relative tolerance:

$$\eta_{\text{rel}} = \frac{\eta_{\text{DWR}}}{J_{\text{ref}}} \le \varepsilon_{\text{DWR,max}}$$

### Remediation of Normalisation Anchor:
- **Phase 5.1 Defect:** The estimator normalised by $|\mu_{\text{QoI}}| + 10^{-14}$. If the QoI crossed zero or was numerically small, the relative error artificially exploded; if $\mu$ was unanchored, relative scale was meaningless.
- **Phase 5.1.1 Correction:** The relative error is normalised by an explicit positive reference physical scale $J_{\text{ref}} > 0$ provided in the evidence metrics (`dwr_reference_scale` or `reference_scale`), or the contract threshold.
- If $\eta_{\text{rel}} > \varepsilon_{\text{DWR,max}}$, the evaluator returns `DecisionRecommendation.REFINE`. Caller bypass flags are disallowed.

---

## 5. Verification Matrix

| Check | Failure Outcome | Bypassed by Flag? | Mathematical Reason |
| :--- | :--- | :--- | :--- |
| Missing Assessment | `INSUFFICIENT_EVIDENCE` | No | Decisions without evidence are ungrounded |
| Missing Category | `INSUFFICIENT_EVIDENCE` | No | Incomplete evidentiary basis |
| Unvalidated Record | `INSUFFICIENT_EVIDENCE` | No | Unverified data cannot support risk release |
| Domain Mismatch | `INSUFFICIENT_EVIDENCE` | No | Cannot apply Evidence A to Domain B |
| Model Mismatch | `INSUFFICIENT_EVIDENCE` | No | Mesh/Constitutive model divergence |
| DWR Error Exceeded | `REFINE` | No | Numerical solution has not resolved QoI |
| Non-finite Metrics | `INSUFFICIENT_EVIDENCE` | No | NaN/Inf invalidates error bounds |
