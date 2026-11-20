# Phase A — Section 5: Mutation Testing Report

## Executive Summary

To establish the rigor and non-triviality of the Phase A verification suite, systematic mutation testing was executed against key components of the numerical pipeline (`ConstitutiveTensor`, `LinearElasticitySolver`, Dirichlet boundary condition mapping, and assumption handling).

All 5 required mutations were killed by the verification test suite, achieving a **100% Mutation Kill Score (5/5)**.

---

## Mutation Log

### Mutant 1: Sign Inversion in Constitutive Coupling ($c_{12}$)
- **Target:** `src/gdec/fem/elasticity.py:37`
- **Mutation:** Inverted sign of Poisson ratio term in plane stress:
  ```python
  # Baseline
  c12 = nu * c11
  # Mutant
  c12 = -nu * c11
  ```
- **Result:** **KILLED**
- **Killing Test:** `tests/test_a2_patch_operator.py::test_a2_1b_production_uniform_tension`
- **Failure Output:**
  ```text
  AssertionError: A2.1b_plane_stress failed: rel_err=0.6599999999999997 > 1e-10
  ```
- **Restoration Verification:** `git diff --exit-code` verified clean.

---

### Mutant 2: Omission of Factor 2 in Engineering Shear Strain ($\gamma_{12}$)
- **Target:** `src/gdec/fem/elasticity.py:103`
- **Mutation:** Dropped the factor of 2 in shear stress computation during stiffness assembly:
  ```python
  # Baseline
  sig_12 = 2.0 * c33 * eps_u[0, 1]
  # Mutant
  sig_12 = 1.0 * c33 * eps_u[0, 1]
  ```
- **Result:** **KILLED**
- **Killing Test:** `tests/test_a2_independent_assembler.py::test_a2_3_independent_assembler[mesh_case0-plane_stress]`
- **Failure Output:**
  ```text
  AssertionError: Stiffness matrix difference 0.13120603066921122 > 1e-10
  AssertionError: Displacement difference 57.68549838264128 > 1e-10
  ```
- **Restoration Verification:** `git diff --exit-code` verified clean.

---

### Mutant 3: Component Transposition in Boundary Traction Assembly ($t_x \leftrightarrow t_y$)
- **Target:** `src/gdec/fem/elasticity.py:122`
- **Mutation:** Swapped traction vector components $t_x$ and $t_y$ in boundary facet linear form:
  ```python
  # Baseline
  return thickness * (tx * v[0] + ty * v[1])
  # Mutant
  return thickness * (ty * v[0] + tx * v[1])
  ```
- **Result:** **KILLED**
- **Killing Test:** `tests/test_a2_independent_assembler.py::test_a2_3_independent_assembler[mesh_case0-plane_stress]`
- **Failure Output:**
  ```text
  AssertionError: Displacement difference 57.68549838264128 > 1e-10
  ```
- **Restoration Verification:** `git diff --exit-code` verified clean.

---

### Mutant 4: Indexing Off-by-One in $y$-Component Boundary DOF Map
- **Target:** `src/gdec/fem/elasticity.py:171`
- **Mutation:** Introduced off-by-one error when indexing $y$-component Dirichlet DOFs:
  ```python
  # Baseline
  res.append(dofs_view.nodal["u^2"])
  # Mutant
  res.append(dofs_view.nodal["u^2"] + 1)
  ```
- **Result:** **KILLED**
- **Killing Tests:**
  1. `tests/test_a2_patch_operator.py::test_a2_1b_production_uniform_tension`
     ```text
     AssertionError: A2.1b_plane_stress failed: rel_err=1.0 > 1e-10
     ```
  2. `tests/test_a2_patch_operator.py::test_a2_2_operator_checks`
     ```text
     AssertionError: A2.2_cantilever_residual failed: rel_res=3.828511196445571
     ```
- **Restoration Verification:** `git diff --exit-code` verified clean.

---

### Mutant 5: Plane-Stress Substitution for Plane-Strain Formulation
- **Target:** `src/gdec/fem/elasticity.py:39`
- **Mutation:** Substituted plane-stress constitutive formulas when `plane_strain` was requested:
  ```python
  # Baseline
  elif assumption == "plane_strain":
      lam = (E * nu) / ((1.0 + nu) * (1.0 - 2.0 * nu))
      mu = E / (2.0 * (1.0 + nu))
      c11 = lam + 2.0 * mu
      c12 = lam
      c33 = mu
  # Mutant
  elif assumption == "plane_strain":
      c11 = E / (1.0 - nu**2)
      c12 = nu * c11
      c33 = E / (2.0 * (1.0 + nu))
  ```
- **Result:** **KILLED**
- **Killing Test:** `tests/test_a2_patch_operator.py::test_a2_1b_production_uniform_tension`
- **Failure Output:**
  ```text
  AssertionError: A2.1b_plane_strain failed: rel_err=0.12220850634047993 > 1e-10
  ```
- **Restoration Verification:** `git diff --exit-code` verified clean.

---

## Conclusion

| Mutant ID | Description | Killing Test | Status |
|:---|:---|:---|:---:|
| **M1** | Sign inversion in $c_{12}$ | `test_a2_1b_production_uniform_tension` | **KILLED** |
| **M2** | Missing factor 2 in shear strain | `test_a2_3_independent_assembler` | **KILLED** |
| **M3** | Traction vector transposition ($t_x \leftrightarrow t_y$) | `test_a2_3_independent_assembler` | **KILLED** |
| **M4** | Off-by-one in $y$-DOF mapping | `test_a2_1b_production_uniform_tension`, `test_a2_2_operator_checks` | **KILLED** |
| **M5** | Plane-stress fallback in plane-strain | `test_a2_1b_production_uniform_tension` | **KILLED** |

**Mutation Score:** $5 / 5 = 100\%$
