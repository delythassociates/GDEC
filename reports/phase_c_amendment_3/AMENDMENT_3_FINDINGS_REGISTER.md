# GDEC Phase C Amendment 3: Findings Register
**Baseline:** `a13749c3ae441dd9ed4c1bed8893d8ce5c86bb82` (`prereg-c-amendment-2`)  
**Status:** All 4 Core Findings Remediated + 3 Additional Findings Registered  

---

## 1. Findings Summary Table

| Finding ID | Severity | Category | Description | Remediation Status | Verification Artifact |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **AM3-01** | CRITICAL | Numerical Integrity | Quadrature study compares against hardcoded $M_3$ error constant ($5.2849 \times 10^{-5}$) without independent construction or provenance. | **RESOLVED** | `quadrature_study.py`, `QUADRATURE_REPRODUCIBILITY_REPORT.md` |
| **AM3-02** | CRITICAL | Mathematical Correctness | Family 4 patch-average displacement sign discrepancy ($k_y$ positive vs negative) in validation report. | **RESOLVED** | `audit_qois.py`, `MATHEMATICAL_VALIDATION_REPORT.md` |
| **AM3-03** | HIGH | Hierarchy Evidence | Validation relied on scalar metadata rather than typed actual mesh evidence; dimensional geometric thresholds ($10^{-14}$) caused scale sensitivity. | **RESOLVED** | `MeshLevelEvidence`, `mesh_evidence.py`, `MESH_HIERARCHY_VALIDATION_REPORT.md` |
| **AM3-04** | MEDIUM | Software Reproducibility | Executive reports showed 161 passed vs 157 passed without explicit environment/commit traceability. | **RESOLVED** | `test_evidence_record.json`, `TEST_EVIDENCE_RECONCILIATION.md` |
| **AM3-05** | MEDIUM | Input Validation | `ProblemAnalyser.evaluate_contract` accepted unrecognized `verification_mode` strings, silently defaulting to three-grid. | **RESOLVED** | Strict mode enum enforcement raising `ValueError` in `analyser.py` |
| **AM3-06** | MEDIUM | Geometry Robustness | Collinear degenerate elements could cause division by zero if total area was not strictly verified before normalization. | **RESOLVED** | Fail-closed finite area checks in `check_mesh_quality` and `validate_geometry` |
| **AM3-07** | LOW | Telemetry Traceability | Lack of runtime helper to automatically generate typed `MeshLevelEvidence` from FEM mesh objects outside `src/gdec/fem/`. | **RESOLVED** | Introduced `src/gdec/runtime/mesh_evidence.py` |

---

## 2. Detailed Finding Records

### Finding AM3-01: Untraced Hardcoded $M_3$ Discretisation Error
- **Severity:** Critical
- **Root Cause:** In Phase C Amendment 2, `e_smallest_m3 = 5.2849e-5` was hardcoded as a literal constant in `quadrature_study.py`. Level $M_3$ was not constructed in the runner, leaving the ratio comparison untraceable.
- **Evidence:** Line 105 of `verification/phase_c/amendment_2/quadrature_study.py`.
- **Remediation:**
  1. Constructed full hierarchy $M_0 \to M_3$ dynamically.
  2. Solved Case B on $M_3$ (3,200 elements, 1,681 nodes) using Order 26 Duffy quadrature.
  3. Computed dynamic $E_{\text{smallest}, M_3} = |J_{M_3}^{\text{Order 26}} - J_{\text{exact}}| = 5.27914477 \times 10^{-5}$.
  4. Demonstrated geometric decay ($\rho = 0.5086$) and bounded empirical tail error $E_{\text{tail}} \le 0.010 \times E_{\text{smallest}, M_3}$ across all levels ($0.73\%$, $0.28\%$, $0.10\%$).

### Finding AM3-02: Family 4 Patch QoI Formula Sign Discrepancy
- **Severity:** Critical
- **Root Cause:** In `reports/phase_c_amendment_2/BVP_MATHEMATICAL_VALIDATION.md`, line 59 wrote `J_exact = 0.25 kx + 13/48 ky`. This formula is exact for horizontal displacement $u_x$, but if interpreted as vertical displacement $u_y$, the correct formula has a negative sign on $k_y$: $-\frac{13}{48} k_y + \frac{1}{4} k_x$.
- **Evidence:** Line 59 of `BVP_MATHEMATICAL_VALIDATION.md` vs analytical integration of $u_y = -k_y x^2 + k_x x y$.
- **Remediation:**
  1. Derived step-by-step closed-form integrals for both $u_x$ and $u_y$ over $[0.25, 0.75]^2$.
  2. Confirmed that in `tier1_manifest.json`, items T1_26, T1_28, T1_30, T1_32 target $u_x$, which has $+ \frac{13}{48} k_y$.
  3. Audited all 40 Tier 1 configurations symbolically and against SciPy numerical quadrature (`quad` / `dblquad`). All 40 matched with error $< 10^{-18} \ll 10^{-11}$.
  4. Updated mathematical documentation with both formulas and explicit component labeling.

### Finding AM3-03: Mesh Hierarchy Validation Absent Actual Mesh Evidence
- **Severity:** High
- **Root Cause:** `ProblemAnalyser.evaluate_contract` accepted scalar `mesh_levels` and `refinement_ratio` metadata, but had no interface to inspect actual mesh hierarchy topology or parent-child lineage. Additionally, dimensional thresholds ($A \le 10^{-14}$) caused false rejections on scaled geometries.
- **Evidence:** Lines 128, 140, 198 of `src/gdec/core/analyser.py`.
- **Remediation:**
  1. Created typed dataclass `MeshLevelEvidence` with cryptographic mesh hashes, parent pointers, element/node counts, and characteristic $h$.
  2. Implemented `ProblemAnalyser.validate_mesh_hierarchy()` enforcing parent continuity, monotonic $h$, independent refinement ratio calculation, and protocol level counts.
  3. Replaced dimensional thresholds with scale-aware dimensionless checks ($A_e / L_{\text{ref}}^2$, $l_e / L_{\text{ref}}$).
  4. Verified scale invariance across scales $s \in \{10^{-6}, 1.0, 10^6\}$.
  5. Implemented `src/gdec/runtime/mesh_evidence.py` to extract evidence from actual FEM meshes.

### Finding AM3-04: Contradictory Test Evidence Counts Across Reports
- **Severity:** Medium
- **Root Cause:** Earlier drafts cited 157 passing tests, whereas the final baseline commit suite collected and ran 161 tests following the addition of `test_phase_c_amendment_2.py` (7 tests).
- **Evidence:** Section 5 audit table.
- **Remediation:**
  1. Traced exact execution logs for all runs.
  2. Executed full non-confirmatory regression suite (171 tests passed in 42.32s).
  3. Created machine-readable `results/phase_c_amendment_3/test_evidence_record.json`.
  4. Fully reconciled figures in `TEST_EVIDENCE_RECONCILIATION.md`.

### Finding AM3-05: Silent Defaulting of Invalid Verification Modes
- **Severity:** Medium
- **Root Cause:** Passing an invalid mode string (e.g. `verification_mode="two_grid"`) did not raise an error and silently fell back to three-grid behavior.
- **Remediation:** Enforced strict parameter validation in `evaluate_contract()` and `validate_mesh_hierarchy()`, raising `ValueError` on unrecognized modes.

### Finding AM3-06: Potential Division by Zero in Collinear Elements
- **Severity:** Medium
- **Root Cause:** If a degenerate mesh consisted entirely of collinear vertices, `total_area == 0.0`. Evaluating `areas / total_area` produced runtime warnings or NaNs.
- **Remediation:** Guarded with `if total_area <= 0.0 or not np.isfinite(total_area): return False, 0.0`.

### Finding AM3-07: Telemetry Adapter Boundary Preservation
- **Severity:** Low
- **Root Cause:** No utility existed outside `src/gdec/fem/` to extract cryptographic mesh evidence.
- **Remediation:** Implemented `src/gdec/runtime/mesh_evidence.py` preserving strict 0-diff read-only status on `src/gdec/fem/`.
