# GDEC Phase C Amendment 3.2 — Adversarial Test Report

**Test Modules:** `tests/test_phase_c_amendment_3_2_reproductions.py`, `tests/test_phase_c_amendment_3_2.py`  
**Total Tests:** 31  
**Passed:** 31  
**Failed:** 0  
**Pass Rate:** **100.0%**  

---

## 1. Reproduction Test Results (AM32-01 to AM32-04)

| Test Name | Audit Defect | Verified Remediation Behavior | Result |
|:---------:|:------------:|:-----------------------------:|:------:|
| `test_reproduce_am32_01_metadata_trust_rejected_in_amendment_3_2` | AM32-01 | Rejects fabricated mesh metadata without proof | **PASSED** |
| `test_reproduce_am32_02_bvp_verification_rejects_corrupted_manifest_fields` | AM32-02 | Detects corrupted manifest c33 and body force | **PASSED** |
| `test_reproduce_am32_03_deep_immutability_enforced` | AM32-03 | Prevents post-construction mutation via MappingProxyType | **PASSED** |
| `test_reproduce_am32_04_zero_difference_rejected_without_precision_floor` | AM32-04 | Rejects zero difference without precision floor | **PASSED** |

---

## 2. Adversarial Test Results Matrix

| Category | Test Function | Target Failure Mode | Observed Behavior | Status |
|:--------:|:-------------:|:-------------------:|:-----------------:|:------:|
| Topology | `test_topology_vertex_outside_parent_even_if_centroid_inside` | Vertex outside parent | Rejected (containment failure) | **PASSED** |
| Topology | `test_topology_missing_region_in_child_mesh` | Missing child triangle | Rejected (area conservation failure) | **PASSED** |
| Topology | `test_topology_duplicated_child_elements` | Duplicate elements | Rejected (duplicate element failure) | **PASSED** |
| Topology | `test_topology_overlapping_child_elements_with_correct_area` | Overlapping elements | Rejected (element nesting failure) | **PASSED** |
| Topology | `test_topology_inverted_degenerate_child_triangle` | Zero-area element | Rejected (degenerate element failure) | **PASSED** |
| Topology | `test_topology_hanging_nodes_on_interior_edges` | Hanging node on edge | Rejected (hanging node detected) | **PASSED** |
| Topology | `test_topology_midpoint_not_matching_parent_edge` | Perturbed midpoint | Rejected (provenance failure) | **PASSED** |
| Topology | `test_topology_child_element_not_assigned_to_parent` | Out-of-bounds child | Rejected (domain bounding box failure) | **PASSED** |
| Topology | `test_topology_bisection_with_provenance_and_without_provenance` | Bisection provenance | Verified with sig; UNVERIFIED without sig | **PASSED** |
| Topology | `test_topology_conforming_non_nested_mesh_pair` | Independent grids | Classified as CONFORMING_NON_NESTED | **PASSED** |
| Topology | `test_topology_fabricated_metadata_rejected` | Fabricated flags | Refused with UNVERIFIED_INSUFFICIENT_LEVELS | **PASSED** |
| BVP | `test_bvp_missing_body_force` | Empty body force | Status: INVALID_SPECIFICATION | **PASSED** |
| BVP | `test_bvp_corrupted_c33_violating_isotropy` | Corrupted c33 | Status: INVALID_SPECIFICATION (isotropy error) | **PASSED** |
| BVP | `test_bvp_non_symmetric_elasticity_tensor` | Asymmetric tensor | Status: INVALID_SPECIFICATION (symmetry error) | **PASSED** |
| BVP | `test_bvp_wrong_plane_stress_vs_plane_strain` | Mismatched formula | Status: INVALID_SPECIFICATION (constitutive error) | **PASSED** |
| BVP | `test_bvp_boundary_data_mismatch` | Incomplete boundaries | Status: PARTIALLY_VERIFIED / INVALID | **PASSED** |
| BVP | `test_bvp_corner_trace_mismatch` | Invalid prescription | Status: PARTIALLY_VERIFIED / INVALID | **PASSED** |
| BVP | `test_bvp_matching_qoi_but_invalid_differential_equation` | Invalid equilibrium | Status: QOI_ONLY_VERIFIED | **PASSED** |
| Immutability | `test_immutability_attribute_mutation_raises` | Top-level mutation | Raises FrozenInstanceError | **PASSED** |
| Immutability | `test_immutability_nested_dictionary_mutation_raises` | Nested dict mutation | Raises TypeError | **PASSED** |
| Immutability | `test_immutability_nested_list_mutation_raises` | Nested list mutation | Raises AttributeError | **PASSED** |
| Immutability | `test_immutability_caller_retained_reference_mutation_has_no_effect` | Caller dict mutation | Instance unaffected | **PASSED** |
| Immutability | `test_immutability_canonical_serialization_roundtrip_and_hash` | Hash stability | Identical SHA-256 hash | **PASSED** |
| Quadrature | `test_quadrature_non_geometric_error_reduction` | Non-geometric decay | Status: NON_GEOMETRIC_CONVERGENCE | **PASSED** |
| Quadrature | `test_quadrature_unjustified_zero_difference_rejected` | Unjustified zeros | Status: INCOMPLETE_UNJUSTIFIED_ZERO_DIFF | **PASSED** |
| Quadrature | `test_quadrature_machine_precision_zero_difference_passed` | Machine precision zeros | Status: PASSED_MACHINE_PRECISION | **PASSED** |
| Quadrature | `test_quadrature_json_report_consistency` | JSON-Report consistency | All numbers match exact JSON values | **PASSED** |