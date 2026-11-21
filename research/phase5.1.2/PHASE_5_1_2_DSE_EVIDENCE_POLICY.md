# GDEC Phase 5.1.2 — Decision Sufficiency Engine Evidence Policy Specification

**Author:** Lead Engineering Research Orchestrator & Decision Intelligence Architect  
**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.2-evidence-integrity-closure`  
**Governing Standard:** Fail-closed decision gating with non-maskable evidence qualification

---

## 1. Principles of Decision Sufficiency

In mission-critical structural mechanics and computational engineering, a numerical recommendation (such as `RELEASE` or `REFINE`) must never be derived from unverified, expired, or discredited evidence. 

A high-level passing status for an evidence category (e.g. `ValidationStatus.VERIFIED`) is insufficient if individual simulation runs within that category were invalidated due to solver divergence, mesh distortion, or expired calibration certificates. 

GDEC Phase 5.1.2 enforces **record-level evidence auditing** with strict precedence and non-omittable discretization error gates.

---

## 2. Evidence State Machine & Classifications

### 2.1 Validation Status (`ValidationStatus`)
- `PENDING`: Initial state upon data generation.
- `VERIFIED`: Mathematically, numerically, or experimentally confirmed valid.
- `UNVALIDATED`: Evidence exists but has never undergone qualification.
- `EXPIRED`: Previously verified evidence whose certificate or validation validity period has elapsed.
- `REJECTED`: Discredited evidence that failed mesh convergence, violated conservation laws, or exhibited solver instability.

### 2.2 Record-Level Eligibility (`EvidenceEligibility`)
When evaluated against a specific `DecisionContract`, each `EvidenceRecord` is assigned an eligibility classification:
- `ACCEPTED`: Record is verified, unexpired, model-compatible, domain-compatible, and carries full provenance.
- `REJECTED`: Explicitly discredited (`status == REJECTED`) or tainted.
- `UNASSESSED`: Record is marked `PENDING` or `UNVALIDATED`.
- `INCOMPATIBLE_MODEL`: Record model identifier does not match contract `model_reference`.
- `INCOMPATIBLE_DOMAIN`: Record domain identifier does not match contract `applicable_domain`.
- `INSUFFICIENT_PROVENANCE`: Missing or whitespace-only provenance metadata.
- `INSUFFICIENT_METRIC`: Missing numeric value in declared metric dictionary.
- `MISSING`: Expected record was not supplied.

---

## 3. Strict Record-Level Precedence and Category Satisfaction

### 3.1 Precedence Ordering
When evaluating evidence records within a category, severity follows the strict ranking:
$$\text{REJECTED} \succ \text{EXPIRED} \succ \text{INSUFFICIENT} \succ \text{UNASSESSED} \succ \text{ACCEPTED}$$

### 3.2 Category Satisfaction Axiom
For any required evidence category $C \in \text{contract.evidence.required_categories}$:
$$\text{Satisfied}(C) \iff \Big( \exists r \in C : \text{eligibility}(r) = \text{ACCEPTED} \Big) \land \Big( \forall r \in C : \text{eligibility}(r) \ne \text{REJECTED} \Big)$$

**The Poisoning Principle:** If any record in a required category is `REJECTED`, the entire category is deemed unsatisfied, regardless of how many other records in that category are `ACCEPTED`. The evaluation immediately fails closed.

---

## 4. Evaluation Gates in `SingleQoIEvaluator`

1. **Gate 1: Contract & Prior Validation**
   - Asserts non-null contract, prior variance $\sigma^2 > 0$, and non-null loss matrix.
2. **Gate 2: Record-Level Evidence Eligibility Audit**
   - Evaluates all supplied records via `evaluate_record_eligibility`.
   - Rejects evaluation if `assessment is None` or if assessment status is `REJECTED` / `UNVALIDATED`.
   - Confirms model and domain compatibility.
   - Evaluates category satisfaction axiom across all required categories.
   - Any failure emits `DecisionRecommendation.INSUFFICIENT_EVIDENCE` and attaches detailed `record_reports`.
3. **Gate 3: Non-Omittable Discretisation Quality Gate (DWR)**
   - If contract requires mesh discretisation or numerical quality thresholds:
     - DWR evidence records must be present and `ACCEPTED`.
     - DWR metric must provide numeric error bound $\eta_{\text{dwr}}$.
     - If missing, evaluation fails closed with `DecisionRecommendation.INSUFFICIENT_EVIDENCE`.
     - If $\eta_{\text{dwr}} / J_{\text{ref}} > \tau_{\text{tol}}$, evaluation unconditionally forces `DecisionRecommendation.REFINE`.
4. **Gate 4: Bayesian Expected Loss Minimization**
   - Integrates posterior loss:
     $$R_{\text{release}} = \mathbb{E}[L(\text{release}, \theta)], \quad R_{\text{revise}} = \mathbb{E}[L(\text{revise}, \theta)]$$
   - Releases only if $R_{\text{release}} < R_{\text{revise}}$.
   - Exact tie ($R_{\text{release}} == R_{\text{revise}}$) fails closed with `DecisionRecommendation.REFINE`.

---

## 5. Audit Trail & Diagnostics

Every `DecisionResult` returns an immutable audit dictionary containing:
- `record_reports`: List of `RecordEvaluationReport` detailing the eligibility status and reason for every record examined.
- `dwr_error`: Reported DWR discretisation error.
- `relative_dwr_error`: DWR error normalized by reference scale.
- `risk_release` and `risk_revise`: Expected posterior loss values.
- `refusal_reason`: Detailed textual explanation when recommendation is `INSUFFICIENT_EVIDENCE` or `REFINE`.
