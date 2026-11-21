# DSE Refusal Policy & Conditional Recommendation Semantics (Phase 5.1.1)

## 1. Scope & Purpose

This document establishes the official refusal policy, recommendation taxonomy, and risk-tie resolution semantics for the GDEC Decision Sufficiency Engine (DSE).

In safety-critical computational mechanics and engineering design, an algorithmic decision recommendation must be clear regarding what is being asserted. A decision engine must refuse to release an engineering artifact when information is incomplete, invalid, or ambiguous.

---

## 2. Recommendation Taxonomy

The DSE produces four mutually exclusive recommendations:

```python
class DecisionRecommendation(str, Enum):
    RELEASE = "RELEASE"
    REVISE = "REVISE"
    REFINE = "REFINE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
```

### Recommendation Semantics

1. **`RELEASE` (Conditional on Evidentiary Scope)**:
   - *Meaning:* Under the explicit prior distribution, loss matrix, and validated evidentiary records submitted, the expected loss of releasing the design is strictly lower than revising it, and all discretisation quality tolerances are satisfied.
   - *Legal & Epistemic Boundary:* `RELEASE` does not certify absolute structural safety in the physical world; it certifies mathematical sufficiency of the evidence with respect to the declared decision contract.

2. **`REVISE`**:
   - *Meaning:* The numerical solution is sufficiently resolved, but the predicted performance carries excessive probability of exceeding the declared limit state, resulting in a higher expected loss for release than for revision. The engineering design parameters must be revised.

3. **`REFINE`**:
   - *Meaning:* The engineering decision cannot be determined because numerical discretisation error (measured via DWR error estimators) exceeds the acceptable threshold, or epistemic parameter uncertainty dominates the risk comparison. The finite element mesh or sampling budget must be refined.

4. **`INSUFFICIENT_EVIDENCE`**:
   - *Meaning:* The input evidentiary basis is incomplete, unvalidated, mismatched in domain/model, or mathematically invalid. The decision engine refuses to evaluate risk until valid evidence is supplied.

---

## 3. Strict Refusal Policy & Trigger Conditions

The DSE halts and returns `INSUFFICIENT_EVIDENCE` under any of the following conditions:

1. **No Evidence Assessment:** `assessment is None`.
2. **Missing Required Evidence Category:** Any category declared in `contract.evidence.required_categories` is absent from `assessment.records`.
3. **Unvalidated Evidence Record:** Any relevant evidence record has a status other than `ValidationStatus.VALIDATED`.
4. **Domain Identifier Mismatch:** An evidence record's `domain_reference` differs from `contract.identity.domain_reference`.
5. **Model Identifier Mismatch:** An evidence record's `model_reference` differs from `contract.identity.model_reference`.
6. **Zero or Non-Positive Standard Deviation:** A predictive distribution with $\sigma \le 0$ without explicit caller certification of deterministic exactness.
7. **Non-Finite Distribution Parameters:** Any $\mu = \text{NaN}$, $\sigma = \text{NaN}$, or threshold $= \text{NaN}$.
8. **Asymmetrical or Degenerate Loss Matrix:** Loss parameters with negative consequences ($L_{\text{FN}} < 0$, $L_{\text{FP}} < 0$) or trivial zero loss for failure.

---

## 4. Risk Tie-Breaking Policy

In Bayesian loss minimization:
$$R_{\text{release}} = L_{\text{FP}} \cdot P(\text{breach})$$
$$R_{\text{revise}} = L_{\text{FN}} \cdot (1 - P(\text{breach})) + C_{\text{rev}}$$

When $R_{\text{release}} == R_{\text{revise}}$ within numerical precision ($\Delta R < 10^{-12}$):
- **Safety-First Conservative Default:** The engine **refuses to arbitrarily release**.
- In the event of an exact tie or indistinguishable risk delta, the engine yields `REFINE`, requesting additional computational or experimental evidence to break the epistemic tie before committing engineering capital.

---

## 5. DWR Discretisation Quality Precedence

Mesh refinement precedence is absolute:
- Even if $R_{\text{release}} \ll R_{\text{revise}}$, if the finite element discretisation error $\eta_{\text{rel}} > \varepsilon_{\text{DWR,max}}$, the engine returns `REFINE`.
- An engineering design cannot be released on the basis of an under-resolved computational grid.
