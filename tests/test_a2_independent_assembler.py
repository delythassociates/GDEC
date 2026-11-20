"""
A2.3: Independent P1 Linear Elasticity Assembler Verification.
Pure NumPy loop-based implementation (zero scikit-fem assembly routines used for independent path).
Standard formulation (Hughes / Zienkiewicz / Bathe):
  K_e = t * A_e * B_e^T * C * B_e
Global COO assembly and boundary condition condensation.
Compared against production LinearElasticitySolver.
"""

import json
import os
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem
import skfem as fem
import pytest

from gdec.fem.elasticity import LinearElasticitySolver, ConstitutiveTensor
from gdec.fem.mesh import GDECMesh
from verification.mesh_utils import create_structured_mesh, create_perturbed_mesh

RESULTS_DIR = Path("results/verification")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _record_result(entry: dict, filename: str):
    path = RESULTS_DIR / filename
    results = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            results = []
    results = [r for r in results if r.get("id") != entry.get("id")]
    results.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def assemble_independent_p1(
    points: np.ndarray,
    triangles: np.ndarray,
    C: np.ndarray,
    thickness: float = 1.0,
) -> sp.csr_matrix:
    """
    Pure NumPy implementation of 2D P1 linear elasticity stiffness assembly.
    No scikit-fem routines are used.
    """
    n_nodes = points.shape[1]
    n_elements = triangles.shape[1]
    n_dofs = 2 * n_nodes

    I_idx = []
    J_idx = []
    V_val = []

    for e in range(n_elements):
        elem = triangles[:, e]
        n0, n1, n2 = elem[0], elem[1], elem[2]
        x0, y0 = points[0, n0], points[1, n0]
        x1, y1 = points[0, n1], points[1, n1]
        x2, y2 = points[0, n2], points[1, n2]

        detJ = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        area = 0.5 * abs(detJ)

        # Gradients of shape functions
        dN1_dx = (y2 - y0) / detJ
        dN1_dy = -(x2 - x0) / detJ
        dN2_dx = -(y1 - y0) / detJ
        dN2_dy = (x1 - x0) / detJ
        dN0_dx = -dN1_dx - dN2_dx
        dN0_dy = -dN1_dy - dN2_dy

        # B-matrix (3x6) for [u0, v0, u1, v1, u2, v2]
        B = np.zeros((3, 6))
        grads = [(dN0_dx, dN0_dy), (dN1_dx, dN1_dy), (dN2_dx, dN2_dy)]
        for i, (gx, gy) in enumerate(grads):
            B[0, 2 * i] = gx
            B[1, 2 * i + 1] = gy
            B[2, 2 * i] = gy
            B[2, 2 * i + 1] = gx

        # Element stiffness: K_e = t * area * B^T * C * B
        Ke = thickness * area * (B.T @ C @ B)

        dofs = [2 * n0, 2 * n0 + 1, 2 * n1, 2 * n1 + 1, 2 * n2, 2 * n2 + 1]
        for r in range(6):
            for c in range(6):
                I_idx.append(dofs[r])
                J_idx.append(dofs[c])
                V_val.append(Ke[r, c])

    K = sp.coo_matrix((V_val, (I_idx, J_idx)), shape=(n_dofs, n_dofs)).tocsr()
    return K


def assemble_independent_boundary(
    points: np.ndarray,
    triangles: np.ndarray,
    bnd_nodes: np.ndarray,
    boundary_length: float,
    tx: float = 0.0,
    ty: float = 0.0,
    qoi_comp: str = "y",
    thickness: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pure NumPy implementation of facet boundary traction and QoI assembly.
    """
    n_nodes = points.shape[1]
    n_dofs = 2 * n_nodes
    f_indep = np.zeros(n_dofs)
    g_indep = np.zeros(n_dofs)
    qoi_idx = 0 if qoi_comp == "x" else 1

    bnd_set = set(bnd_nodes)
    seen_edges = set()

    for e in range(triangles.shape[1]):
        elem = triangles[:, e]
        for i in range(3):
            nA = elem[i]
            nB = elem[(i + 1) % 3]
            edge = tuple(sorted((nA, nB)))
            if nA in bnd_set and nB in bnd_set and edge not in seen_edges:
                seen_edges.add(edge)
                Le = float(np.linalg.norm(points[:, nA] - points[:, nB]))
                # Traction
                f_indep[2 * nA] += 0.5 * thickness * Le * tx
                f_indep[2 * nA + 1] += 0.5 * thickness * Le * ty
                f_indep[2 * nB] += 0.5 * thickness * Le * tx
                f_indep[2 * nB + 1] += 0.5 * thickness * Le * ty
                # QoI representation
                g_indep[2 * nA + qoi_idx] += (0.5 * Le) / boundary_length
                g_indep[2 * nB + qoi_idx] += (0.5 * Le) / boundary_length

    return f_indep, g_indep


@pytest.mark.parametrize("plane_type", ["plane_stress", "plane_strain"])
@pytest.mark.parametrize("mesh_case", [
    ("tensor_17x9", "structured", 17, 9, 2.0, 1.0),
    ("perturbed_5x5", "perturbed", 5, 5, 1.0, 1.0),
    ("cantilever_20x5", "structured", 20, 5, 2.0, 0.5),
])
def test_a2_3_independent_assembler(plane_type: str, mesh_case: tuple):
    mesh_name, mtype, nx, ny, width, height = mesh_case
    test_id = f"A2.3_{plane_type}_{mesh_name}"

    if mtype == "structured":
        skfem_mesh, mesh_metrics = create_structured_mesh(nx, ny, domain=(0.0, width, 0.0, height))
    else:
        skfem_mesh, mesh_metrics = create_perturbed_mesh(nx, seed=12345)

    c = ConstitutiveTensor.from_properties(E=70e9, nu=0.33, assumption=plane_type, thickness=1.0)
    solver = LinearElasticitySolver(c)
    gmesh = GDECMesh(skfem_mesh, width, height)
    basis = solver.create_basis(gmesh)

    # Production assembly
    K_prod = solver.assemble_stiffness(basis)
    f_prod = solver.assemble_traction(gmesh, "right", tx=0.0, ty=-1000.0)
    g_prod = solver.assemble_qoi_adjoint_vector(gmesh, "right", component="y")

    # Independent assembly
    K_indep = assemble_independent_p1(
        points=skfem_mesh.p,
        triangles=skfem_mesh.t,
        C=c.matrix_3x3,
        thickness=c.thickness,
    )

    right_dofs = solver.find_dirichlet_dofs(basis, gmesh, "right", ["x", "y"])
    right_nodes = np.unique(right_dofs // 2)
    f_indep, g_indep = assemble_independent_boundary(
        points=skfem_mesh.p,
        triangles=skfem_mesh.t,
        bnd_nodes=right_nodes,
        boundary_length=height,
        tx=0.0,
        ty=-1000.0,
        qoi_comp="y",
        thickness=c.thickness,
    )

    # Matrix differences
    diff_K = sp.linalg.norm(K_prod - K_indep) / sp.linalg.norm(K_prod)
    diff_f = np.linalg.norm(f_prod - f_indep) / np.linalg.norm(f_prod)
    diff_g = np.linalg.norm(g_prod - g_indep) / np.linalg.norm(g_prod)

    # Fixed boundary: left clamped (ux=0, uy=0)
    fixed_dofs = solver.find_dirichlet_dofs(basis, gmesh, "left", ["x", "y"])

    # Production solve
    K_free_p, f_free_p, u_full_p, I_p = skfem.condense(K_prod, f_prod, D=fixed_dofs)
    u_free_p = spla.spsolve(K_free_p.tocsc(), f_free_p)
    u_prod = u_full_p.copy()
    u_prod[I_p] = u_free_p
    qoi_prod = float(g_prod @ u_prod)

    # Independent solve
    K_free_i, f_free_i, u_full_i, I_i = skfem.condense(K_indep, f_indep, D=fixed_dofs)
    u_free_i = spla.spsolve(K_free_i.tocsc(), f_free_i)
    u_indep = u_full_i.copy()
    u_indep[I_i] = u_free_i
    qoi_indep = float(g_indep @ u_indep)

    # Solution differences
    max_u = float(np.max(np.abs(u_prod)))
    diff_u = float(np.max(np.abs(u_prod - u_indep)) / max_u)
    diff_qoi = float(abs(qoi_prod - qoi_indep) / abs(qoi_prod))

    passed = bool(diff_K <= 1e-10 and diff_u <= 1e-10 and diff_qoi <= 1e-10)
    fail_class = None if passed else "NUM_FAIL"

    res = {
        "id": test_id,
        "computed": {
            "stiffness_frobenius_rel_diff": float(diff_K),
            "traction_rel_diff": float(diff_f),
            "qoi_vector_rel_diff": float(diff_g),
            "displacement_inf_rel_diff": diff_u,
            "qoi_rel_diff": diff_qoi,
            "qoi_production": qoi_prod,
            "qoi_independent": qoi_indep,
            "dofs": int(basis.N),
            "elements": int(skfem_mesh.t.shape[1]),
            "mesh_name": mesh_name,
            "plane_type": plane_type,
        },
        "threshold": {
            "stiffness_rel_tol": 1e-10,
            "displacement_rel_tol": 1e-10,
            "qoi_rel_tol": 1e-10,
        },
        "pass": passed,
        "failure_class": fail_class,
        "details": f"Independent pure-NumPy P1 assembly comparison for {mesh_name} ({plane_type}).",
    }
    _record_result(res, "A2_3_independent_assembler.json")

    assert diff_K <= 1e-10, f"Stiffness matrix difference {diff_K} > 1e-10"
    assert diff_u <= 1e-10, f"Displacement difference {diff_u} > 1e-10"
    assert diff_qoi <= 1e-10, f"QoI difference {diff_qoi} > 1e-10"
