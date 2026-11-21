# GDEC Phase 5.1.1 Scaling Assumption Remediation Report

**Document ID:** `GDEC-SCALE-REMED-001`  
**Date:** 2026-11-22  
**Workstream:** C — Analytical Scaling Correctness  
**Author:** Lead Engineering Research Orchestrator  
**Status:** Remediated, Validated, Tests Passing  

---

## 1. Identified Defects in Phase 5.1

In the Phase 5.1 implementation:
1. `ScalingAssumptions` defaulted all 6 boolean flags to `True`:
   ```python
   # PHASE 5.1 DEFECTIVE CODE:
   @dataclass(frozen=True)
   class ScalingAssumptions:
       uniform_material_scaling: bool = True
       fixed_geometry: bool = True
       ...
   ```
   An empty `ScalingAssumptions()` call silently attested that every assumption was satisfied without requiring positive verification or declaring an attestation source.
2. Compliance QoIs were mentioned in docstrings as compatible with $P/E$ scaling, but load-dependent compliance:
   $$C(P, E) = f(P)^T u(P, E) = (P \bar{f}_0)^T \left(\frac{P}{E} \bar{u}_0\right) = \frac{P^2}{E} \left(\bar{f}_0^T \bar{u}_0\right) = \left(\frac{P}{P_0}\right)^2 \left(\frac{E_0}{E}\right) C_0$$
   scales **quadratically with load**, not linearly ($P/E$).
3. Inputs to `evaluate_scalar` and `evaluate_batch` did not strictly reject non-finite inputs (NaN, $\pm\infty$) or empty batches.

---

## 2. Reconciled Scaling Architecture

Phase 5.1.1 remediates `src/gdec/dse/scaling.py` with uncompromising physical rigor:

### 2.1 No Default Assumptions & Mandatory Attestation
Every assumption must be positively attested by the caller with an explicit engineer/provenance identifier:
```python
@dataclass(frozen=True)
class ScalingAssumptions:
    uniform_material_scaling: bool
    fixed_geometry: bool
    fixed_poisson_ratio: bool
    linear_elastic_regime: bool
    proportional_loading: bool
    compatible_displacement_qoi: bool
    qoi_type: str = "fixed_displacement"
    attested_by: str = ""
```
If any boolean flag is `False` or if `attested_by` is empty, `validate()` raises `ScalingAssumptionError`.

### 2.2 Explicit Functional Scope Restriction
- **Supported:** Fixed linear displacement functionals $J(u) = \int_\Gamma g \cdot u \, ds$ (e.g. tip deflection, average boundary displacement) where $g$ does not depend on $P$.
- **Explicitly Rejected:**
  - `compliance` / `strain_energy`: Rejects $P/E$ formula because compliance scales as $P^2 / E$.
  - `stress` / `von_mises` / `tresca`: Rejects $P/E$ formula because stress $\sigma = C : \varepsilon(u)$ scales as $P$ (independent of $E$ under load control).
  - Multi-material domains or varying $\nu$.

### 2.3 Comprehensive Finite-Value Validation
- $E_0 > 0, P_0 \neq 0, J_0 \text{ finite}, 0 \le \nu < 0.5$.
- Scalar $E$ must be strictly positive and finite; $P$ must be finite.
- Batch arrays must be non-empty, matching in shape, and strictly finite with all $E > 0$.
- Catches floating-point overflow and raises typed `ScalingAssumptionError`.
