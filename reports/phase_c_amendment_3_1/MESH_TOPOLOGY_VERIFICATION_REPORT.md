# GDEC Phase C Amendment 3.1: Mesh Topology Verification Report

**Finding:** AM31-01 (CRITICAL)  
**Module:** `src/gdec/runtime/mesh_evidence.py`, `src/gdec/core/analyser.py`  
**Test Suite:** `tests/test_phase_c_amendment_3_1.py` (A31-T01 through A31-T07)  
**Status:** FULLY REMEDIATED & VERIFIED  

---

## 1. Context and Problem Statement

In computational mechanics, a mesh sequence $\{\mathcal{T}_h\}_{h}$ must satisfy precise mathematical relationships to justify Richardson extrapolation, GCI estimates, and asymptotic error bounds:
1. **Nestedness / Subgrid Property:** For nested hierarchical solvers, every coarse element $K \in \mathcal{T}_{2h}$ must be exactly the union of fine elements $K = \bigcup_{j=1}^4 K'_{j}$, and every coarse vertex must belong to the fine vertex set.
2. **Topological Refinement Provenance:** Under uniform midpoint refinement (red refinement), every newly introduced vertex $\mathbf{v}' \in \mathcal{V}_{h} \setminus \mathcal{V}_{2h}$ must be the exact midpoint of a unique edge in $\mathcal{E}_{2h}$.
3. **Domain Invariance:** The physical domain represented by the child mesh must match the parent domain: $\Omega(\mathcal{T}_{h}) = \Omega(\mathcal{T}_{2h})$.

In Amendment 3, `MeshLevelEvidence` tracked mesh hashes and refinement ratios, but `nestedness_verified` defaulted to `True` without executing any topological checks. A caller could pass fabricated metadata asserting `nestedness_verified=True` for completely arbitrary, disjoint, or distorted meshes.

---

## 2. Mathematical Definition of Topological Checks

### 2.1 Uniform Midpoint Refinement (`uniform_midpoint`)

Given parent mesh $\mathcal{T}_{\text{parent}} = (\mathcal{V}_P, \mathcal{E}_P, \mathcal{K}_P)$ and child mesh $\mathcal{T}_{\text{child}} = (\mathcal{V}_C, \mathcal{E}_C, \mathcal{K}_C)$:

1. **Element Count Doubling:**
   $$N_{e, \text{child}} = 4 N_{e, \text{parent}}$$
2. **Node Inheritance:**
   Every parent vertex must exist in the child mesh within tolerance $\epsilon = 10^{-10}$:
   $$\forall \mathbf{v}_P \in \mathcal{V}_P, \quad \exists \mathbf{v}_C \in \mathcal{V}_C \quad \text{s.t.} \quad \|\mathbf{v}_P - \mathbf{v}_C\|_2 \le \epsilon$$
3. **Midpoint Provenance:**
   Every newly introduced child vertex $\mathbf{v}_C \in \mathcal{V}_C \setminus \mathcal{V}_P$ must be the midpoint of an edge in $\mathcal{E}_P$:
   $$\forall \mathbf{v}_C \in \mathcal{V}_C \setminus \mathcal{V}_P, \quad \exists (i, j) \in \mathcal{E}_P \quad \text{s.t.} \quad \left\|\mathbf{v}_C - \frac{\mathbf{v}_i + \mathbf{v}_j}{2}\right\|_2 \le \epsilon$$
4. **Centroid Geometric Containment:**
   For every child element $K \in \mathcal{K}_C$, its centroid $\mathbf{c}_K = \frac{1}{3}\sum_{i=1}^3 \mathbf{x}_{K, i}$ must lie within the parent mesh domain:
   $$\forall K \in \mathcal{K}_C, \quad \mathbf{c}_K \in \bigcup_{P \in \mathcal{K}_P} P$$
   Containment is checked via barycentric coordinates $\lambda_1, \lambda_2, \lambda_3 \ge -\epsilon$ with $\sum_{i=1}^3 \lambda_i = 1$.
5. **Diameter Scaling:**
   $$\frac{h_{\max, \text{parent}}}{h_{\max, \text{child}}} \approx 2.0 \quad (\pm 10\%)$$

### 2.2 Independent Conforming Non-Nested Meshes (`independent_conforming`)

When meshes are generated independently without nested subdivision:
1. $h$-reduction: $h_{\max, \text{child}} < h_{\max, \text{parent}}$ with ratio $r > 1.05$.
2. Domain coverage: Parent and child bounding boxes and element containment match domain boundaries.
3. Nestedness is explicitly set to `False` (`nestedness_proven: False`), preventing false claims of nestedness while certifying that the mesh hierarchy is valid for non-nested extrapolation.

### 2.3 Unknown / Unsupported Refinement Methods

Any refinement method not explicitly supported (e.g. arbitrary adaptive quadtrees or unverified unstructured meshes) fails closed with `RefusalCode.UNVERIFIED_INSUFFICIENT_LEVELS`.

---

## 3. Implementation Details

In `src/gdec/runtime/mesh_evidence.py`:
- `verify_mesh_refinement_topology(parent_mesh, child_mesh, refinement_method="uniform_midpoint", tol=1e-10)`:
  Performs complete vectorised topological audit.
  Returns `(ok: bool, reason: str, details: Dict[str, Any])`.
- `build_mesh_hierarchy_evidence(mesh_sequence, level_ids=None, refinement_method="uniform_midpoint")`:
  Constructs frozen `MeshLevelEvidence` records with `topology_verified=True`, `refinement_evidence=details`, and `nestedness_verified=True/False`.

In `src/gdec/core/analyser.py`:
- `validate_mesh_hierarchy(evidence_list, verification_mode="three_grid", meshes=None)`:
  - If `meshes` are provided: directly executes `verify_mesh_refinement_topology()`.
  - If only evidence objects are provided: rejects unproven assertions (`nestedness_verified=True` without `topology_verified=True` and `refinement_evidence`).

---

## 4. Verification Evidence

The implementation is verified across 7 adversarial tests in `tests/test_phase_c_amendment_3_1.py`:
- `test_a31_t01_fabricated_parent_hashes`: Unrelated mesh with fabricated hash rejected (`Element count ratio does not match uniform doubling`).
- `test_a31_t02_correct_hashes_incorrect_topology`: Perturbed midpoint rejected (`Child vertex is neither parent vertex nor edge midpoint`).
- `test_a31_t03_false_nestedness_boolean_ignored`: Bare `nestedness_verified=True` rejected without topological proof.
- `test_a31_t04_child_element_outside_parent`: Shifted child mesh rejected (`Child mesh fails node inheritance`).
- `test_a31_t05_invalid_child_parent_mapping`: Partially refined mesh rejected (`Element count ratio does not match uniform doubling`).
- `test_a31_t06_supported_non_nested_method`: `independent_conforming` accepted with `nestedness_proven=False` and `topology_verified=True`.
- `test_a31_t07_unknown_refinement_method_refusal`: Unknown method refused (`Unsupported or unverified refinement method`).
