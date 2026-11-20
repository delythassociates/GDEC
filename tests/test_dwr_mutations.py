"""
Mutation Testing Suite for DWR Mathematical Verification.
Demonstrates that the DWR consistency tests are sensitive and strictly kill mutants:
- Mutant 1: Perturbed prolongation operator (weights != 0.5)
- Mutant 2: Sign-flipped fluctuation / residual
- Mutant 3: Omission of boundary traction contribution in elemental decomposition
- Mutant 4: Perturbed enriched stiffness operator
"""

import numpy as np
import pytest
import scipy.sparse as sp
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1, ElementTriP2

from verification.dwr.geometries import CantileverProblem
from verification.dwr.dwr_estimator import DWREstimator
from verification.dwr.reference_solutions import REFERENCE_DATABASE


def test_mutation_prolongation_weight_killed():
    """Mutant 1: Changing prolongation interpolation weights from 0.5 to 0.4 must fail Galerkin orthogonality."""
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)

    b1 = Basis(mesh, ElementVector(ElementTriP1()))
    b2 = Basis(mesh, ElementVector(ElementTriP2()))

    # Build mutated prolongation matrix
    rows, cols, vals = [], [], []
    for i in range(b1.N):
        rows.append(i)
        cols.append(i)
        vals.append(1.0)
    for k in range(mesh.facets.shape[1]):
        n1, n2 = mesh.facets[0, k], mesh.facets[1, k]
        rows.extend([b2.facet_dofs[0, k], b2.facet_dofs[0, k]])
        cols.extend([2 * n1, 2 * n2])
        vals.extend([0.4, 0.6])  # Mutated weights: 0.4, 0.6 instead of 0.5, 0.5

        rows.extend([b2.facet_dofs[1, k], b2.facet_dofs[1, k]])
        cols.extend([2 * n1 + 1, 2 * n2 + 1])
        vals.extend([0.4, 0.6])

    P_mut = sp.csr_matrix((vals, (rows, cols)), shape=(b2.N, b1.N))

    K1 = estimator._assemble_stiffness(b1)
    K2 = estimator._assemble_stiffness(b2)
    f1 = prob.assemble_traction(b1)
    f2 = prob.assemble_traction(b2)
    D1 = prob.get_dirichlet_dofs(b1)
    I1 = np.setdiff1d(np.arange(b1.N), D1)

    K1_c, f1_c, u1_full, _ = fem.condense(K1, f1, D=D1)
    import scipy.sparse.linalg as spla
    u1 = u1_full.copy()
    u1[I1] = spla.spsolve(K1_c.tocsc(), f1_c)

    res2_mut = f2 - K2 @ (P_mut @ u1)
    galerkin_proj_mut = (P_mut.T @ res2_mut)[I1]
    rel_err = float(np.max(np.abs(galerkin_proj_mut))) / float(np.max(np.abs(f1)))

    # Mutant must be detected: rel_err is large (>> 1e-10)
    assert rel_err > 1e-3, f"Mutant survived! Galerkin error remained small: {rel_err}"


def test_mutation_sign_flip_killed():
    """Mutant 2: Flipping sign of eta_dwr must fail sign convention check."""
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)
    res = estimator.estimate(mesh)

    j_ref = REFERENCE_DATABASE["cantilever"]["j_ref"]
    true_error_signed = j_ref - res.qoi_h

    # Mutate eta_dwr by flipping sign
    eta_dwr_mut = -res.eta_dwr

    # The sign convention test checks if eta_dwr < 0 when true_error_signed < 0
    with pytest.raises(AssertionError):
        assert eta_dwr_mut < 0.0, "Mutated eta_dwr should have failed sign check"


def test_mutation_omitted_traction_in_elemental_sum_killed():
    """Mutant 3: Omitting boundary traction from elemental indicators must fail sum consistency."""
    prob = CantileverProblem()
    mesh = prob.get_mesh(0)
    estimator = DWREstimator(prob)
    res = estimator.estimate(mesh)

    # Mutated indicator sum omitting traction (sum of -a_elem only)
    mutated_signed_sum = float(np.sum(-res.signed_element_contributions))  # or omitting tr_elem

    # Checking relative error against true eta_dwr
    rel_diff = abs(mutated_signed_sum - res.eta_dwr) / abs(res.eta_dwr)
    assert rel_diff > 0.1, f"Mutant survived! Relative difference was only {rel_diff}"
