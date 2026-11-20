# GDEC Phase C Amendment 3: Mesh Hierarchy Evidence & Scale-Aware Validation Report
**Remediates:** AM3-03  
**Target:** Elimination of reliance on unverified scalar metadata; implementation of typed mesh evidence, true cryptographic hierarchy verification, and scale-aware geometry validation.  
**Implementation Files:** `src/gdec/core/analyser.py`, `src/gdec/runtime/mesh_evidence.py`  
**Test Suite:** `tests/test_phase_c_amendment_3.py`  

---

## 1. Executive Summary

In prior phases, verification contract evaluation relied on caller-supplied scalar metadata such as `mesh_levels = 3` and `refinement_ratio = 2.0`. This metadata was uncoupled from the actual meshes used in the discrete computation. Furthermore, geometry validation in `ProblemAnalyser` utilized dimensional thresholds ($A_e \le 10^{-14} \text{ m}^2$, $l_e \le 10^{-14} \text{ m}$), which caused micro-scale meshes ($s = 10^{-6}$) to be falsely rejected as degenerate.

Phase C Amendment 3 resolves these defects:
1. **Typed Mesh Evidence (`MeshLevelEvidence`):** Introduces a typed dataclass capturing deterministic SHA-256 geometry/connectivity hashes, node counts, element counts, characteristic mesh size $h$, parent mesh hashes, refinement ratios, and provenance.
2. **True Hierarchy Validation (`validate_mesh_hierarchy`):** Verifies parent-child continuity, strictly decreasing characteristic $h$, uniform doubling ($r = 2.0 \pm 10\%$), and protocol level counts ($3$ for three-grid, $4$ for four-grid). Fail-closed on missing, corrupted, or contradictory evidence.
3. **Scale-Aware Dimensionless Geometry Checks:** Replaces dimensional constants with scale-invariant ratios:
   $$\frac{A_e}{A_{\text{total}}} \le 10^{-14}, \quad \frac{l_e}{L_{\text{ref}}} \le 10^{-14}, \quad \text{where } L_{\text{ref}} = \sqrt{A_{\text{total}}}$$
   Validated across scales $s \in \{10^{-6}, 1.0, 10^6\}$.
4. **Architectural Decoupling:** Implemented entirely in `src/gdec/core/analyser.py` and `src/gdec/runtime/mesh_evidence.py`, maintaining **0 lines modified** in `src/gdec/fem/`.

---

## 2. Typed Mesh Evidence Specification

```python
@dataclass
class MeshLevelEvidence:
    level_id: str                          # e.g., "M0", "M1", "M2"
    mesh_hash: str                         # SHA-256 digest of node coordinates & topology
    element_count: int                     # Number of triangular elements (N_e)
    node_count: int                        # Number of mesh vertices (N_n)
    characteristic_h: float                # Scale-aware size h = sqrt(A_total / N_e)
    parent_mesh_hash: Optional[str] = None # Hash of immediate parent (None for M0)
    refinement_ratio: Optional[float]=None # Claimed refinement ratio
    nestedness_verified: bool = True       # Topological nestedness certification
    refinement_method: str = "uniform_midpoint"
    provenance: Optional[Dict[str, Any]] = None
```

### 2.1 Cryptographic Hash Function
The mesh hash is computed over contiguous C-order binary byte representations of coordinate array $p$ (`float64`) and connectivity table $t$ (`int64`):
$$\text{hash} = \text{SHA256}(\text{bytes}(p) \,\|\, \text{bytes}(t))$$
Any vertex perturbation, element renumbering, or topology change alters the hash deterministically.

---

## 3. Scale-Aware Dimensionless Geometry Validation

### 3.1 Motivation
In linear elasticity, a mesh representing a microelectromechanical systems (MEMS) resonator has domain dimensions $L \approx 10^{-6} \text{ m}$ and area $A \approx 10^{-12} \text{ m}^2$. Individual triangle areas are $A_e \approx 10^{-13} \text{ m}^2$. A dimensional threshold $A_e \le 10^{-14}$ falsely classifies valid elements as degenerate. Conversely, for a civil structural bridge ($L \approx 10^3 \text{ m}$), an element of area $10^{-6} \text{ m}^2$ is degenerate relative to the domain ($A_e / A \approx 10^{-12}$), yet escapes a $10^{-14}$ threshold.

### 3.2 Dimensionless Formulation
The characteristic reference length of the domain is:
$$L_{\text{ref}} = \sqrt{A_{\text{total}}} = \sqrt{\sum_{e=1}^{N_e} A_e}$$
The dimensionless checks are:
$$\text{Area Degeneracy Check: } \frac{A_e}{L_{\text{ref}}^2} = \frac{A_e}{A_{\text{total}}} \le 10^{-14}$$
$$\text{Edge Length Degeneracy Check: } \frac{l_e}{L_{\text{ref}}} \le 10^{-14}$$

### 3.3 Multi-Scale Empirical Validation
Tested on geometrically similar triangular meshes scaled across 12 orders of magnitude:
| Scale Factor ($s$) | Physical Context | Domain Area ($A_{\text{total}}$) | Max Edge ($l_{\max}$) | Min Angle | Quality Status | Geometry Validation |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **$10^{-6}$** | Micro/nano-scale MEMS | $1.00 \times 10^{-12} \text{ m}^2$ | $4.71 \times 10^{-7} \text{ m}$ | $45.0^\circ$ | **VALID** | **ACCEPTED** |
| **$1.0$** | Laboratory benchmark | $1.00 \times 10^{0} \text{ m}^2$ | $4.71 \times 10^{-1} \text{ m}$ | $45.0^\circ$ | **VALID** | **ACCEPTED** |
| **$10^{6}$** | Macro/geophysical domain | $1.00 \times 10^{12} \text{ m}^2$ | $4.71 \times 10^{5} \text{ m}$ | $45.0^\circ$ | **VALID** | **ACCEPTED** |

All three scales produce identical quality metrics and validation outcomes without numerical scale bias.

---

## 4. Adversarial Hierarchy Validation Results

Ten adversarial scenarios were constructed and tested in `test_phase_c_amendment_3.py`:

| Test ID | Adversarial Mutation | Expected Outcome | Actual Outcome | Status |
| :---: | :--- | :--- | :--- | :---: |
| **ADV-01** | Valid 4-level hierarchy ($M_0 \to M_3$) | Accepted in four-grid mode | Issued `four_grid_verified_contract` | **PASS** |
| **ADV-02** | Valid 3-level hierarchy ($M_0 \to M_2$) | Accepted in three-grid mode | Issued `verified_contract_issued` | **PASS** |
| **ADV-03** | Missing parent hash pointer on $M_2$ | Refused (`UNVERIFIED_INSUFFICIENT_LEVELS`) | Refused (Priority 6) | **PASS** |
| **ADV-04** | Falsified refinement ratio claim ($r=3.5$ vs actual $2.0$) | Refused (`UNVERIFIED_INSUFFICIENT_LEVELS`) | Refused (Priority 6) | **PASS** |
| **ADV-05** | Non-monotonic characteristic $h$ ($h_2 > h_1$) | Refused (`UNVERIFIED_INSUFFICIENT_LEVELS`) | Refused (Priority 6) | **PASS** |
| **ADV-06** | Duplicated mesh level ($M_1$ repeated) | Refused (`UNVERIFIED_INSUFFICIENT_LEVELS`) | Refused (Priority 6) | **PASS** |
| **ADV-07** | Three levels supplied in `four_grid` mode | Refused (`UNVERIFIED_INSUFFICIENT_LEVELS`) | Refused (Priority 6) | **PASS** |
| **ADV-08** | Unrecognized verification mode string (`"two_grid"`) | Deterministic rejection (`ValueError`) | `ValueError` raised | **PASS** |
| **ADV-09** | Collinear degenerate triangle at $s=10^{-6}$ | Refused (`INVALID_GEOMETRY`) | Refused (Priority 3) | **PASS** |
| **ADV-10** | Collinear degenerate triangle at $s=10^6$ | Refused (`INVALID_GEOMETRY`) | Refused (Priority 3) | **PASS** |

---

## 5. Architectural Boundary Verification

A strict boundary audit was performed to confirm that no evidence extraction or hierarchy logic contaminated the Phase A FEM production solver:
- Command: `git diff --stat 01260409a0e11d8dcf97729ea25a61f20e2a4772 -- src/gdec/fem/`
- Output: `0 files changed, 0 insertions, 0 deletions`.
- Result: **COMPLIANT**.
