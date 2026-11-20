# GDEC Phase C Amendment 3.2 — Findings and Remediation Register

**Status:** ALL FINDINGS RESOLVED  
**Baseline Preregistration Tag:** `prereg-c-amendment-3.1` (`1adf18e1156a9956f9024088cdd1882ff60fb120`)  
**Target Working Branch:** `phase-c/amendment-3.2`  
**Governing Standard:** GDEC Evidence Verification Standard v1.0  

---

## Executive Summary

Phase C Amendment 3.2 provides complete independent remediation of the four material verification defects (AM32-01 through AM32-04) and two structural verification safeguards (AM32-05 and AM32-06) identified during independent technical audit of commit `1adf18e1156a9956f9024088cdd1882ff60fb120`.

Every defect has been independently reproduced, repaired at the algorithmic and structural level, verified against adversarial test cases, and confirmed through immutable machine-readable evidence records.

---

## Defect Register

### AM32-01 (Critical): False-Positive Mesh Topology Verification
- **Issue:** Amendment 3.1 validated mesh hierarchies relying only on node inheritance, scalar refinement ratios, and centroid containment. It accepted fabricated metadata flags without Skfem mesh objects and could not detect child elements whose vertices extend outside parent elements, overlapping child triangles, or hanging nodes.
- **Root Cause:** Centroid containment testing is mathematically insufficient to prove geometric element inclusion (child element in parent element). ProblemAnalyser trusted boolean claims in evidence metadata when mesh objects were omitted.
- **Remediation:**
  1. Implemented full triangle containment: every child element must have all 3 vertices inside the parent triangle via barycentric coordinates (w1, w2, w3 >= -1e-6).
  2. Implemented parent element coverage: every parent triangle must be partitioned into exactly 4 child triangles for uniform red refinement, with exact area conservation.
  3. Implemented global conformity: verified shared-edge multiplicities (<= 2) and detected hanging nodes across all interior edges.
  4. Implemented method classification: NESTED_VERIFIED, CONFORMING_NON_NESTED_VERIFIED, UNVERIFIED, INVALID.
  5. Strictly reject fabricated metadata without verifiable topological signatures.
- **Status:** **RESOLVED**
- **Evidence:** `src/gdec/runtime/mesh_evidence.py`, `tests/test_phase_c_amendment_3_2.py` (Adversarial Section 1).

---

### AM32-02 (Critical): Mathematical BVP Audit Manifest Bypass
- **Issue:** verify_bvp_single in Amendment 3.1 bypassed actual manifest fields: it recomputed c33 = (c11 - c12)/2 without checking manifest c33, derived its own body forces without checking manifest fx, fy, and only checked boundary list lengths rather than evaluating actual displacement traces and corner compatibility.
- **Root Cause:** Verification functions acted as re-generators rather than independent auditors of manifest expressions.
- **Remediation:**
  1. Parsed actual string expressions from tier1_manifest.json for displacement, body force, elasticity tensor, and boundary conditions.
  2. Independently audited elasticity tensor isotropy (C11 - C12 - 2*C33 = 0) and plane stress/strain consistency with material parameters (E, nu).
  3. Derived body force from static equilibrium (-div sigma) and compared against manifest body force across domain.
  4. Verified boundary displacement traces and tested corner compatibility across all 4 Dirichlet boundaries.
  5. Implemented distinct status classifications: FULL_BVP_VERIFIED, QOI_ONLY_VERIFIED, PARTIALLY_VERIFIED, INVALID_SPECIFICATION, INSUFFICIENT_EVIDENCE, VERIFICATION_FAILED.
- **Status:** **RESOLVED** (40/40 configurations verified as FULL_BVP_VERIFIED).
- **Evidence:** `verification/phase_c/amendment_3_2/verify_tier1_bvps.py`, `results/phase_c_amendment_3_2/tier1_bvp_verification_record.json`.

---

### AM32-03 (High): Shallow Immutability of Mesh Evidence
- **Issue:** MeshLevelEvidence was declared @dataclass(frozen=True), but refinement_evidence was a standard Python dictionary, allowing post-construction in-place mutation of verification fields.
- **Root Cause:** Standard Python @dataclass(frozen=True) provides shallow immutability only.
- **Remediation:**
  1. Implemented defensive deep copy in MeshLevelEvidence.__post_init__.
  2. Recursively froze all nested dictionaries and lists using types.MappingProxyType and tuples.
  3. Implemented deterministic canonical serialization (to_canonical_dict) with sorted keys and stable SHA-256 hash generation (canonical_hash).
  4. Post-construction mutation attempts strictly raise TypeError.
- **Status:** **RESOLVED**
- **Evidence:** `src/gdec/core/analyser.py`, `tests/test_phase_c_amendment_3_2.py` (Adversarial Section 3).

---

### AM32-04 (High): Quadrature Report-Record Discrepancy & Zero-Difference Semantics
- **Issue:** The Amendment 3.1 Markdown report displayed values from an earlier run (0.40722) while the JSON contained Case B values (0.283809). In addition, assess_quadrature_convergence accepted zero differences without verifying a machine precision floor across preceding steps.
- **Root Cause:** Manual transcription of report numbers and missing precision floor preconditions for zero-difference plateaus.
- **Remediation:**
  1. Established machine-readable JSON as the single source of truth; all reports generated directly from JSON.
  2. Eliminated unjustified zero-difference convergence: plateau to zero accepted only when preceding difference satisfies delta_14_18 <= 1e-12. If preceding difference exceeds floor, returns INCOMPLETE_UNJUSTIFIED_ZERO_DIFFERENCE.
  3. Labeled empirical tail estimate strictly as EMPIRICAL_GEOMETRIC_TAIL_ESTIMATE.
  4. Verified Case B exact analytical QoI (0.2838096843988563), M3 spatial error (5.279145e-5), and tail ratio (0.1049% <= 1.0%).
- **Status:** **RESOLVED**
- **Evidence:** `verification/phase_c/amendment_3_2/quadrature_study.py`, `results/phase_c_amendment_3_2/quadrature_study_results.json`.

---

### AM32-05 (High): Preservation of Amendment 3.1 Baseline Safeguards
- **Status:** **RESOLVED**
- **Evidence:**
  - Mesh size definition frozen: h_max = max element diameter.
  - Phase A solver immutable: `src/gdec/fem/` has 0 lines diff relative to `01260409a0e11d8dcf97729ea25a61f20e2a4772`.
  - Confirmatory evaluation frozen: 0 confirmatory runs executed.

---

### AM32-06 (High): Test Quality & Oracle Independence
- **Status:** **RESOLVED**
- **Evidence:**
  - Adversarial test suite with 31 independent tests covering all failure modes.
  - Zero tests use production solver as oracle; all use analytical exact values or independent high-order methods.