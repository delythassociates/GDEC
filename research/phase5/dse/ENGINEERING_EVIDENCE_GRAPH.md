# GDEC Engineering Evidence Graph: Mathematical Provenance and Invalidation Semantics

**Document Reference:** `research/phase5/dse/ENGINEERING_EVIDENCE_GRAPH.md`  
**Workstream:** Agent 4 — Decision Sufficiency Engine Scientific Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Evidence Graph Architecture Established  

---

## 1. Executive Summary

This report defines the architecture and mathematical semantics of the **GDEC Engineering Evidence Graph (EEG)**. Unlike traditional simulation data managers that store opaque monolithic files (`.step`, `.cas`, `.odb`), the EEG models the complete engineering knowledge lineage as a fine-grained, cryptographically hashed Directed Acyclic Graph (DAG).

Nodes represent mathematical artifacts (requirements, geometric parameters, material proofs, meshes, stiffness operators, QoIs, physical test records, and decision certificates). Directed edges represent mathematical derivation, projection, or conditioning operations.

Crucially, the EEG implements **Selective Invalidation Semantics**: when a design parameter changes (e.g. plate thickness or load magnitude), the graph automatically identifies which downstream evidence nodes remain valid, which require re-evaluation, and how past mesh convergence proofs can be reused to minimize re-computation.

---

## 2. Graph Topology and Node Taxonomy

The EEG defines eight discrete node archetypes:

```
+-----------------------------------------------------------------------------------+
| [R] Engineering Requirement / Decision Contract (Acceptance Limits, Alpha)        |
+-----------------------------------------------------------------------------------+
         |                                                 |
         v                                                 v
+-----------------------------+           +-----------------------------------------+
| [G] Geometric Specification |           | [M] Material Characterization (E, nu)   |
| (Length, Width, Notches)    |           | (Coupon Tests, Prior Probability Model) |
+-----------------------------+           +-----------------------------------------+
         |                                                 |
         v                                                 v
+-----------------------------------------------------------------------------------+
| [BVP] Boundary Value Problem Definition (PDE Formulation, BCs, Traction)          |
+-----------------------------------------------------------------------------------+
         |
         v
+-----------------------------------------------------------------------------------+
| [T] Discretization Hierarchy (Coarse Mesh T0 -> Refined T1 -> DWR Refined Tk)     |
+-----------------------------------------------------------------------------------+
         |
         v
+-----------------------------------------------------------------------------------+
| [S] Solution & Operator State (Stiffness K, Factorization L/U, Residuals)         |
+-----------------------------------------------------------------------------------+
         |
         v
+-----------------------------------------------------------------------------------+
| [Q] Quantities of Interest & Discretization Uncertainty (J(uh), U_DWR, GCI)       |
+-----------------------------------------------------------------------------------+
         |
         v
+-----------------------------------------------------------------------------------+
| [D] Decision Sufficiency Certificate (Verdict: Accept / Reject / Refusal)         |
+-----------------------------------------------------------------------------------+
```

---

## 3. Cryptographic Immutability and Hashing

Every node $v_i \in \mathcal{V}$ possesses a unique canonical SHA-256 hash derived recursively from its immutable attributes and parent node hashes:
$$\text{Hash}(v_i) = \text{SHA-256}\left( \text{Type}(v_i) \parallel \text{CanonicalJSON}(\text{Payload}(v_i)) \parallel \sum_{p \in \text{Parents}(v_i)} \text{Hash}(p) \right)$$

This builds directly on GDEC's proven `MeshLevelEvidence` architecture (`src/gdec/core/analyser.py`), where:
1. All payload dictionaries are deeply frozen via `types.MappingProxyType`.
2. Mutation attempts strictly raise `TypeError`.
3. Keys are sorted deterministically before hashing.

---

## 4. Selective Invalidation and Evidence Inheritance Rules

When an engineer modifies an input parameter, traditional CAE invalidates everything. In GDEC, the Evidence Graph applies strict mathematical inheritance rules:

### Rule 1: Material Property Scaling Invariance
- **Scenario:** The Young's modulus is revised ($E \to E'$), but geometry, boundary conditions, and loads remain identical.
- **Inheritance:** In linear elasticity, displacement is strictly proportional to $1/E$, while the displacement spatial profile $u / \|u\|$ and element error indicators $\eta_K$ are **invariant**!
- **Action:** The mesh hierarchy $\mathcal{T}_k$, the stiffness sparsity pattern, and the adaptive refinement trees are **100% preserved**. The new QoI and decision margin are recomputed via scalar multiplication $J' = J \cdot (E / E')$ with **zero FEA re-solves**!

### Rule 2: Load Magnitude Scaling Invariance
- **Scenario:** The design load increases ($P \to \gamma P$).
- **Inheritance:** Linear elasticity guarantees $u' = \gamma u$. The dual solution $\psi$ for linear QoIs is completely independent of the load!
- **Action:** Retain all mesh hierarchies and dual solutions. Rescale $J$ and $\eta_K$ by $\gamma$. Re-evaluate Decision Sufficiency instantly.

### Rule 3: Local Geometric Modification (e.g. Relocating a Hole or Stiffener)
- **Scenario:** A local feature is modified in sub-domain $\Omega_{\text{local}} \subset \Omega$.
- **Inheritance:** By Saint-Venant's principle, the stress field in remote regions $\Omega_{\text{far}} = \Omega \setminus \Omega_{\text{local}}$ is weakly perturbed.
- **Action:** Retain coarse background mesh in $\Omega_{\text{far}}$. Re-mesh only $\Omega_{\text{local}}$. Reuse preconditioned Krylov search directions or coarse-grid AMG operators to achieve a $4\times - 8\times$ faster convergence on the modified design.

---

## 5. Physical Test Integration (ASME V&V 40 Compliance)

The EEG natively incorporates physical experimental coupon test nodes ($T_{\text{exp}}$). When physical test data is connected to a material or QoI node:
1. The engine computes the **Model Validation Comparison Error** $E = |J_{\text{FEM}} - J_{\text{exp}}|$.
2. The engine evaluates the **Validation Uncertainty** $u_{\text{val}} = \sqrt{u_{\text{num}}^2 + u_{\text{input}}^2 + u_{\text{exp}}^2}$.
3. If $E \le u_{\text{val}}$, the model is formally **Validated** within experimental resolution, and the decision certificate cites the physical coupon test hash in its audit trail.
