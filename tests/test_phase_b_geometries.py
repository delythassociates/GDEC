"""
Test Phase B Benchmark Geometries and QoI Assembly.
Verifies all 4 benchmark problems across all 3 initial mesh variants.
"""

import numpy as np
import pytest
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1
import scipy.sparse.linalg as spla

from verification.dwr.geometries import (
    BENCHMARK_PROBLEMS,
    CantileverProblem,
    PlateWithHoleProblem,
    NotchedBarProblem,
    LShapedProblem,
)
from gdec.fem.elasticity import LinearElasticitySolver


@pytest.mark.parametrize("prob_id", ["cantilever", "plate_with_hole", "notched_bar", "l_shaped"])
@pytest.mark.parametrize("variant_idx", [0, 1, 2])
def test_benchmark_problem_geometry_and_solve(prob_id: str, variant_idx: int):
    prob = BENCHMARK_PROBLEMS[prob_id]
    mesh = prob.get_mesh(variant_idx)

    # 1. Mesh validity and positive areas
    assert mesh.is_valid(), f"Mesh for {prob_id} variant {variant_idx} is not valid"
    assert mesh.nelements > 0
    assert mesh.nvertices > 0

    for e in range(mesh.t.shape[1]):
        v = mesh.p[:, mesh.t[:, e]]
        area = 0.5 * ((v[0, 1] - v[0, 0]) * (v[1, 2] - v[1, 0]) - (v[0, 2] - v[0, 0]) * (v[1, 1] - v[1, 0]))
        assert area > 1e-14, f"Non-positive area {area} in element {e}"

    # 2. Refinability check
    mesh_ref = mesh.refined()
    assert mesh_ref.nelements > mesh.nelements
    assert mesh_ref.is_valid()

    # 3. Assemble and solve primal elasticity problem
    basis = Basis(mesh, ElementVector(ElementTriP1()))
    solver = LinearElasticitySolver(prob.material)
    K = solver.assemble_stiffness(basis)
    f = prob.assemble_traction(basis)
    g = prob.assemble_qoi_vector(basis)

    assert K.shape == (basis.N, basis.N)
    assert len(f) == basis.N
    assert len(g) == basis.N
    assert np.linalg.norm(f) > 0.0, "Traction vector must not be all zero"
    assert np.linalg.norm(g) > 0.0, "QoI vector must not be all zero"

    D = prob.get_dirichlet_dofs(basis)
    assert len(D) > 0, "Must have Dirichlet boundary DOFs"
    I = np.setdiff1d(np.arange(basis.N), D)
    assert len(I) > 0

    K_c, f_c, u_full, _ = fem.condense(K, f, D=D)
    u = u_full.copy()
    u[I] = spla.spsolve(K_c.tocsc(), f_c)

    assert np.all(np.isfinite(u)), "Displacement must be finite"
    assert np.linalg.norm(u[I]) > 0.0, "Displacement must be non-trivial"

    qoi_val = prob.evaluate_qoi(u, basis)
    assert np.isfinite(qoi_val), "QoI value must be finite"
    assert abs(qoi_val) > 0.0, "QoI value must not be zero"
