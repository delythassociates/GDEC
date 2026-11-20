# GDEC Phase C Amendment 3.1: Mesh Size Definition Report

**Finding:** AM31-02 (HIGH)  
**Module:** `src/gdec/runtime/mesh_evidence.py`, `src/gdec/core/analyser.py`  
**Test Suite:** `tests/test_phase_c_amendment_3_1.py` (A31-T08, A31-T09)  
**Status:** FULLY REMEDIATED & RECONCILED  

---

## 1. Mathematical Background and Frozen Definition

In finite element analysis of elliptic boundary-value problems (Ciarlet 1978, Brenner & Scott 2008), the asymptotic convergence rate of linear triangular elements ($P_1$) in the energy and $L^2$ norms depends strictly on the maximum element diameter:

$$h_K = \operatorname{diam}(K) = \sup_{\mathbf{x}, \mathbf{y} \in K} \|\mathbf{x} - \mathbf{y}\|_2 = \max_{i, j \in \{0, 1, 2\}} \|\mathbf{x}_i - \mathbf{x}_j\|_2$$

$$h_{\max} = \max_{K \in \mathcal{T}_h} h_K$$

Under quasi-uniform triangulation, the error estimate satisfies:
$$\|u - u_h\|_{H^1(\Omega)} \le C h_{\max} |u|_{H^2(\Omega)}$$
$$\|u - u_h\|_{L^2(\Omega)} \le C h_{\max}^2 |u|_{H^2(\Omega)}$$

In Phase A (commit `01260409a0e11d8dcf97729ea25a61f20e2a4772`), $h_{\max}$ was frozen as the authoritative definition of characteristic mesh size.

---

## 2. Deviation Identified in Amendment 3

In Phase C Amendment 3, `MeshLevelEvidence.characteristic_h` was computed using an area-based root-mean-square diameter:

$$h_{\text{avg}} = \sqrt{\frac{A_{\text{total}}}{N_e}}$$

While $h_{\text{avg}}$ coincides with $h_{\max}$ on uniform right-angled isosceles triangular meshes up to a geometric constant ($\sqrt{2}$), it diverges severely on:
1. Non-uniform meshes with local refinement.
2. Anisotropic, stretched, or high-aspect-ratio triangles.
3. Meshes with localized boundary gradation or a single oversized element.

If a mesh contains 1,000 tiny triangles of diameter $0.01$ and 1 large triangle of diameter $1.0$, $h_{\text{avg}}$ will report approximately $\sqrt{1.0 / 1001} \approx 0.031$, masking the presence of the $h=1.0$ element that governs the actual discretization error bound.

---

## 3. Remediation & Implementation

1. **Primary Characteristic Mesh Size ($h_{\max}$):**
   `src/gdec/runtime/mesh_evidence.py` implements `compute_max_element_diameter()`:
   ```python
   def compute_max_element_diameter(mesh: fem.MeshTri) -> float:
       p = mesh.p
       t = mesh.t
       p0 = p[:, t[0]]
       p1 = p[:, t[1]]
       p2 = p[:, t[2]]
       e01 = np.linalg.norm(p1 - p0, axis=0)
       e12 = np.linalg.norm(p2 - p1, axis=0)
       e20 = np.linalg.norm(p0 - p2, axis=0)
       element_diameters = np.maximum(e01, np.maximum(e12, e20))
       return float(np.max(element_diameters))
   ```
2. **Delegation:**
   `compute_characteristic_h(mesh)` directly delegates to `compute_max_element_diameter(mesh)`.
3. **Auxiliary Diagnostic ($h_{\text{avg}}$):**
   The area-based average is preserved under `compute_average_element_size(mesh)` and populated in `MeshLevelEvidence.characteristic_h_avg` strictly as an auxiliary diagnostic.
4. **Refinement Ratio ($r_i$):**
   The refinement ratio between levels $i-1$ and $i$ is calculated strictly using $h_{\max}$:
   $$r_i = \frac{h_{\max, i-1}}{h_{\max, i}}$$

---

## 4. Verification Evidence

- **A31-T08 (`test_a31_t08_nonuniform_mesh_oversized_element`):**
  A 2-element mesh with one element of edge length $0.1$ and one element with vertices $(0,0)$ to $(10,10)$ (diameter $\sqrt{200} \approx 14.14$).
  `compute_characteristic_h()` exactly returns $14.1421$, matching $h_{\max}$. $h_{\text{avg}}$ is $< 0.6 \cdot h_{\max}$.
- **A31-T09 (`test_a31_t09_area_average_size_mismatch`):**
  Confirms that on non-uniform meshes, substituting $h_{\text{avg}}$ for $h_{\max}$ creates a discrepancy $> 40\%$, proving that $h_{\max}$ is essential for rigorous error bounding.
