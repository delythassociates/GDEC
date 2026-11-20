"""
verification/mesh_utils.py
Exact mesh generators and geometry metric utilities for Phase A verification.
Follows A0-1 specifications strictly:
- Structured tensor meshes
- Perturbed meshes with seed 12345, h_loc minimum incident edge length, interior only
- Mesh metric reporting (angles, aspect ratios, areas, diameter)
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
import numpy as np
import skfem


def compute_mesh_metrics(mesh: skfem.MeshTri) -> Dict[str, Any]:
    """Calculate exact geometric metrics for a triangular mesh."""
    p = mesh.p
    t = mesh.t
    nelements = t.shape[1]
    nnodes = p.shape[1]

    # Vertex coordinates for all triangles: shape (2, nelements)
    p0 = p[:, t[0]]
    p1 = p[:, t[1]]
    p2 = p[:, t[2]]

    # Edge vectors: e0 = p1 - p0, e1 = p2 - p1, e2 = p0 - p2
    v01 = p1 - p0
    v12 = p2 - p1
    v20 = p0 - p2

    # Edge lengths
    l01 = np.linalg.norm(v01, axis=0)
    l12 = np.linalg.norm(v12, axis=0)
    l20 = np.linalg.norm(v20, axis=0)

    # Element diameter h = max edge length
    longest_edge = np.maximum(l01, np.maximum(l12, l20))
    shortest_edge = np.minimum(l01, np.minimum(l12, l20))
    aspect_ratios = longest_edge / np.maximum(shortest_edge, 1e-15)

    # Element signed areas relative to triangle orientation
    # det = v01_x * v02_y - v01_y * v02_x
    detJ = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
    ori = mesh.orientation()
    signed_areas = 0.5 * ori * detJ
    element_areas = np.abs(0.5 * detJ)

    # Angles at vertices via law of cosines
    # cos(A) = (b^2 + c^2 - a^2) / (2bc)
    # At vertex 0: between edges v01 and -v20
    a2 = l12**2
    b2 = l20**2
    c2 = l01**2

    cos_ang0 = np.clip((b2 + c2 - a2) / (2.0 * np.maximum(l20 * l01, 1e-15)), -1.0, 1.0)
    cos_ang1 = np.clip((c2 + a2 - b2) / (2.0 * np.maximum(l01 * l12, 1e-15)), -1.0, 1.0)
    cos_ang2 = np.clip((a2 + b2 - c2) / (2.0 * np.maximum(l12 * l20, 1e-15)), -1.0, 1.0)

    ang0 = np.degrees(np.arccos(cos_ang0))
    ang1 = np.degrees(np.arccos(cos_ang1))
    ang2 = np.degrees(np.arccos(cos_ang2))
    all_angles = np.concatenate([ang0, ang1, ang2])

    return {
        "node_count": int(nnodes),
        "element_count": int(nelements),
        "dof_count": int(nnodes * 2),
        "min_angle_deg": float(np.min(all_angles)),
        "max_angle_deg": float(np.max(all_angles)),
        "max_aspect_ratio": float(np.max(aspect_ratios)),
        "max_diameter_h": float(np.max(longest_edge)),
        "min_element_area": float(np.min(element_areas)),
        "max_element_area": float(np.max(element_areas)),
        "all_areas_positive": bool(np.all(signed_areas > 0)),
    }


def create_structured_mesh(
    nx: int,
    ny: int | None = None,
    domain: Tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0)
) -> Tuple[skfem.MeshTri, Dict[str, Any]]:
    """Create structured tensor mesh on domain [x0, x1, y0, y1]."""
    if ny is None:
        ny = nx
    elif isinstance(ny, (tuple, list)):
        domain = tuple(ny)  # type: ignore
        ny = nx

    x0, x1, y0, y1 = domain
    mesh = skfem.MeshTri.init_tensor(
        np.linspace(x0, x1, nx + 1),
        np.linspace(y0, y1, ny + 1)
    )
    metrics = compute_mesh_metrics(mesh)
    metrics["refinement_level_n"] = nx
    metrics["nx"] = nx
    metrics["ny"] = ny
    metrics["type"] = "structured"
    metrics["accepted"] = metrics["all_areas_positive"]
    return mesh, metrics


def create_perturbed_mesh(
    n: int,
    seed: int = 12345,
    domain: Tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0)
) -> Tuple[skfem.MeshTri, Dict[str, Any]]:
    """
    Create perturbed triangular mesh on domain [x0, x1, y0, y1] strictly per frozen A0-1:
    - rng = numpy.random.default_rng(seed) re-created per level
    - h_loc = minimum incident edge length of that node on unperturbed mesh
    - Full-array generation:
        theta = rng.uniform(0.0, 2.0 * np.pi, Nnodes)
        r = rng.uniform(0.0, 0.2, Nnodes) * h_loc
        delta = r[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))
    - Apply displacement ONLY to interior nodes:
        p[:, interior_indices] += delta[interior_indices].T
    - Boundary nodes remain unchanged
    - Reject if non-positive element area
    """
    base_mesh, _ = create_structured_mesh(n, domain=domain)
    base_p = base_mesh.p.copy()
    p = base_mesh.p.copy()
    t = base_mesh.t
    nnodes = p.shape[1]
    x0, x1, y0, y1 = domain

    # Identify interior and boundary nodes
    tol = 1e-12
    is_boundary = (
        (np.abs(p[0] - x0) < tol) |
        (np.abs(p[0] - x1) < tol) |
        (np.abs(p[1] - y0) < tol) |
        (np.abs(p[1] - y1) < tol)
    )
    boundary_indices = np.where(is_boundary)[0]
    interior_indices = np.where(~is_boundary)[0]
    n_interior = len(interior_indices)

    # Compute h_loc: minimum incident edge length for each node on unperturbed mesh
    h_loc = np.full(nnodes, np.inf)
    p0 = p[:, t[0]]
    p1 = p[:, t[1]]
    p2 = p[:, t[2]]
    l01 = np.linalg.norm(p1 - p0, axis=0)
    l12 = np.linalg.norm(p2 - p1, axis=0)
    l20 = np.linalg.norm(p0 - p2, axis=0)

    for i in range(t.shape[1]):
        v0, v1, v2 = t[0, i], t[1, i], t[2, i]
        h_loc[v0] = min(h_loc[v0], l01[i], l20[i])
        h_loc[v1] = min(h_loc[v1], l01[i], l12[i])
        h_loc[v2] = min(h_loc[v2], l12[i], l20[i])

    # Re-create RNG independently per level
    rng = np.random.default_rng(seed)

    # Generate arrays of length Nnodes, not Ninterior (frozen preregistration A0-1)
    theta = rng.uniform(0.0, 2.0 * np.pi, nnodes)
    r = rng.uniform(0.0, 0.2, nnodes) * h_loc

    delta = r[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))

    # Apply displacement ONLY to interior nodes
    p[:, interior_indices] += delta[interior_indices].T

    # Verify boundary nodes are strictly unchanged
    boundary_unchanged = bool(np.all(p[:, boundary_indices] == base_p[:, boundary_indices]))

    perturbed_mesh = skfem.MeshTri(p, t)
    metrics = compute_mesh_metrics(perturbed_mesh)
    metrics["n"] = n
    metrics["refinement_level_n"] = n
    metrics["type"] = "perturbed"
    metrics["random_seed"] = seed
    metrics["interior_node_count"] = n_interior
    metrics["boundary_nodes_unchanged"] = boundary_unchanged
    metrics["accepted"] = metrics["all_areas_positive"] and boundary_unchanged

    if not metrics["all_areas_positive"]:
        metrics["rejection_reason"] = "Non-positive element area detected"

    return perturbed_mesh, metrics


def generate_perturbed_mesh_metadata_report(
    levels: list[int] = [5, 8, 16, 32, 64, 128],
    seed: int = 12345,
    output_paths: list[str] = [
        "results/phase_a_completion/perturbed_mesh_metadata.json",
        "results/verification/perturbed_mesh_metadata.json",
    ]
) -> list[dict[str, Any]]:
    """Generate and record exact mesh metadata per A0-1 and Section 3 brief."""
    import json
    from pathlib import Path

    report = []
    for n in levels:
        mesh, metrics = create_perturbed_mesh(n, seed=seed)
        entry = {
            "n": n,
            "node_count": int(metrics["node_count"]),
            "element_count": int(metrics["element_count"]),
            "interior_node_count": int(metrics["interior_node_count"]),
            "random_seed": seed,
            "max_diameter_h": float(metrics["max_diameter_h"]),
            "min_angle_deg": float(metrics["min_angle_deg"]),
            "max_angle_deg": float(metrics["max_angle_deg"]),
            "max_aspect_ratio": float(metrics["max_aspect_ratio"]),
            "min_element_area": float(metrics["min_element_area"]),
            "max_element_area": float(metrics["max_element_area"]),
            "boundary_nodes_unchanged": bool(metrics["boundary_nodes_unchanged"]),
            "all_areas_positive": bool(metrics["all_areas_positive"]),
            "accepted": bool(metrics["accepted"]),
        }
        report.append(entry)

    for out_str in output_paths:
        p = Path(out_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report
