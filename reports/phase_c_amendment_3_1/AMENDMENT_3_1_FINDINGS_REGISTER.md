# GDEC Phase C Amendment 3.1: Findings Register

**Repository:** `delythassociates/GDEC`  
**Base Tag:** `prereg-c-amendment-3`  
**Base Commit:** `4173ab500aacc94c3d168413e32c11aa9375b517`  
**Target Branch:** `phase-c/amendment-3.1`  
**Status:** REMEDIATED / AUDITED  
**Date:** 2026-11-21  

---

## 1. Executive Summary

Phase C Amendment 3.1 was initiated following an independent source inspection of `prereg-c-amendment-3` (`4173ab500aacc94c3d168413e32c11aa9375b517`). The audit revealed critical and high-severity defects where verification contracts accepted unverified assertions, deviated from frozen Phase A mathematical definitions, masked non-convergent numerical quadrature via empirical fallbacks, and committed evidence prior to test execution.

This register tracks all six formal audit findings (AM31-01 through AM31-06), documenting their severity, root cause, exact corrective actions, and verification evidence.

---

## 2. Findings Matrix

| Finding ID | Title | Severity | Core Root Cause | Remediation Status | Verification Artifact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AM31-01** | Mesh Hierarchy Verification Accepted Fabricated Boolean Claims | **CRITICAL** | `validate_mesh_hierarchy()` checked only scalar attributes and accepted `nestedness_verified=True` without independent topological proof | **CLOSED** | `src/gdec/core/analyser.py`, `src/gdec/runtime/mesh_evidence.py`, `test_a31_t01`–`t07` |
| **AM31-02** | Characteristic Mesh Size Substituted Area-Average for Frozen $h_{\max}$ | **HIGH** | `MeshLevelEvidence.characteristic_h` was computed as $\sqrt{A/N_e}$ rather than Phase A diameter $h_{\max} = \max_{K} \operatorname{diam}(K)$ | **CLOSED** | `src/gdec/runtime/mesh_evidence.py`, `test_a31_t08`–`t09` |
| **AM31-03** | Quadrature Failure Mode Substituted Sensitivity Difference for Bound | **HIGH** | `quadrature_study.py` substituted $\delta_{22,26}$ directly when geometric decay failed ($\rho \ge 1$ or non-decaying) | **CLOSED** | `verification/phase_c/amendment_3_1/quadrature_study.py`, `test_a31_t10`–`t12` |
| **AM31-04** | Self-Referential Test Provenance (Evidence Preceded Tested Commit) | **HIGH** | Acceptance records and evidence files were committed in the same commit whose SHA they claimed to record | **CLOSED** | Two-stage commit architecture, `TEST_PROVENANCE_REPORT.md` |
| **AM31-05** | Mathematical Verification Conflated QoI Concordance with Full BVP Audit | **MEDIUM** | QoI quadrature concordance was conflated with full boundary-value problem mathematical verification | **CLOSED** | `verify_tier1_bvps.py`, `tier1_bvp_verification_record.json`, `test_a31_t15` |
| **AM31-06** | Mutable Evidence Dataclass Allowed Post-Hoc Falsification | **LOW** | `MeshLevelEvidence` was a mutable dataclass, permitting modification of verified attributes post-construction | **CLOSED** | `@dataclass(frozen=True)`, `test_a31_t16` |

---

## 3. Detailed Finding Remediation

### AM31-01: Genuine Mesh Hierarchy Topological Verification
- **Defect:** Prior to Amendment 3.1, `MeshLevelEvidence.nestedness_verified` defaulted to `True`. `ProblemAnalyser.validate_mesh_hierarchy()` merely inspected `lvl.nestedness_verified`, allowing forged evidence with matching SHA-256 parent hashes to pass validation even if child elements were completely arbitrary, non-nested, or located outside the parent domain.
- **Remediation:**
  1. Defaulted `nestedness_verified` to `False` in `MeshLevelEvidence`. Added fields `topology_verified: bool = False` and `refinement_evidence: Optional[Dict[str, Any]] = None`.
  2. Implemented `verify_mesh_refinement_topology()` in `src/gdec/runtime/mesh_evidence.py` to independently evaluate:
     - Node inheritance ($\mathcal{V}_{\text{parent}} \subset \mathcal{V}_{\text{child}}$).
     - Midpoint provenance (all new child vertices are midpoints of parent edges $\mathbf{v}_{\text{child}} = \frac{1}{2}(\mathbf{v}_i + \mathbf{v}_j)$).
     - Element centroid containment via barycentric coordinates inside parent triangles.
     - Element count ratio ($N_{e,\text{child}} / N_{e,\text{parent}} = 4.0$).
     - Non-nested conforming meshes (`independent_conforming`): verifies $h$-reduction and domain coverage without falsely claiming nestedness.
     - Fails closed on unknown refinement methods.
  3. Extended `validate_mesh_hierarchy(evidence_list, meshes=None)` to independently evaluate actual skfem mesh topologies when provided, and strictly reject any unproven claim (`nestedness_verified=True` without `topology_verified=True` and valid `refinement_evidence`).

### AM31-02: Restoration of Phase A Frozen Mesh-Size Definition
- **Defect:** Amendment 3 introduced $h_{\text{avg}} = \sqrt{A_{\text{total}} / N_e}$ as `characteristic_h`. In Phase A (and the finite element literature), element diameter is rigorously defined as:
  $$h_K = \operatorname{diam}(K) = \max_{i, j \in \{0, 1, 2\}} \|\mathbf{x}_i - \mathbf{x}_j\|_2, \quad h_{\max} = \max_{K \in \mathcal{T}_h} h_K$$
  Using an area-based root-mean-square diameter obscures local element distortion, anisotropic elongation, and localized boundary refinement.
- **Remediation:**
  1. Restored Phase A definition: `compute_max_element_diameter()` calculates exact $h_{\max}$ as the maximum triangle edge length across the mesh.
  2. Routed `compute_characteristic_h()` to return $h_{\max}$.
  3. Retained $h_{\text{avg}} = \sqrt{A / N_e}$ strictly as an auxiliary diagnostic in `characteristic_h_avg` (optional field).
  4. Calculated refinement ratio strictly as $r_i = h_{\max, i} / h_{\max, i+1}$.

### AM31-03: Strict Fail-Closed Quadrature Failure Handling
- **Defect:** In `verification/phase_c/amendment_3/quadrature_study.py`, if geometric convergence failed ($\rho \ge 1$ or non-decaying sensitivities), the code fell back to returning $E_{\text{tail}} = \delta_{22,26}$. This obscured divergence or lack of asymptotic decay by substituting an ungrounded point estimate.
- **Remediation:**
  1. Re-implemented `assess_quadrature_convergence()` in `verification/phase_c/amendment_3_1/quadrature_study.py` with strict fail-closed semantics.
  2. If $\delta_{14,18} \le \delta_{18,22}$ or $\delta_{18,22} \le \delta_{22,26}$, status is `FAILED_NON_GEOMETRIC` and `tail_error_estimate` is `None`.
  3. If $\delta_{18,22} = 0$, status is `INCOMPLETE_ZERO_DENOMINATOR` and `tail_error_estimate` is `None`.
  4. If any input is NaN or infinite, status is `FAILED_NON_FINITE` and `tail_error_estimate` is `None`.
  5. Tail bound is computed only when strict geometric convergence holds ($0 \le \rho < 1$):
     $$E_{\text{tail}} = \frac{\delta_{22,26}}{1 - \rho}$$
     If $E_{\text{tail}} / E_{\text{smallest}, M_3} > 0.010$, status is `FAILED_THRESHOLD_EXCEEDED` and verification fails.

### AM31-04: Two-Stage Test Provenance
- **Defect:** Prior amendment commits committed test records that recorded the commit hash of the *same* commit. In git, a commit's SHA-1 hash is computed over its entire tree content, making it mathematically impossible for a single commit to contain a valid hash of itself without cheating (recording a pre-calculated hash before execution).
- **Remediation:**
  - Enforced a rigorous two-stage commit workflow:
    - **Stage A (Implementation & Test Commit):** All source modifications, test implementations, and mathematical verification scripts are staged and committed. The exact commit SHA $C_A$ is captured.
    - **Stage B (Execution & Evidence Commit):** The entire test suite is executed against commit $C_A$. Raw terminal logs, test durations, and environment metadata are captured. `test_evidence_record.json` and `amendment_acceptance_record.json` are authored with `tested_commit = $C_A$`. Evidence is committed in a distinct documentation commit $C_B$.

### AM31-05: Complete Tier 1 BVP Mathematical Verification
- **Defect:** Prior verification tested QoI concordance (analytical QoI vs SciPy quad) but did not formally verify the governing PDEs, kinematics, constitutive relations, equilibrium $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$, or boundary conditions across all 40 configurations.
- **Remediation:**
  1. Authored `verification/phase_c/amendment_3_1/verify_tier1_bvps.py`.
  2. Symbolically derived displacements, strains, stresses, and body forces for all 40 BVPs using SymPy.
  3. Proved that under isotropic elasticity ($C_{33} = (C_{11}-C_{12})/2$), equilibrium $\nabla \cdot \boldsymbol{\sigma} + \mathbf{f} \equiv \mathbf{0}$ simplifies identically to exact zero `0` for all 40 BVPs.
  4. Verified pointwise numerical equilibrium across $[0, 1]^2$ with relative residuals $< 10^{-12}$.
  5. Verified Dirichlet trace boundary conditions on all 4 boundaries ($x=0, 1; y=0, 1$).
  6. Verified QoI analytical values against high-precision numerical quadrature (SciPy quad/dblquad) with difference $< 10^{-12}$.
  7. Formally distinguished complete BVP verification from QoI concordance in `results/phase_c_amendment_3_1/tier1_bvp_verification_record.json`.

### AM31-06: Frozen Evidence Dataclasses
- **Defect:** `MeshLevelEvidence` was an unconstrained, mutable dataclass. Any component could mutate fields (such as `nestedness_verified`, `characteristic_h`, or `refinement_ratio`) after validation.
- **Remediation:**
  - Decorated `MeshLevelEvidence` with `@dataclass(frozen=True)`.
  - Verified via adversarial test `test_a31_t16_mutation_of_immutable_evidence_object` that any attempted field assignment raises `dataclasses.FrozenInstanceError`.
