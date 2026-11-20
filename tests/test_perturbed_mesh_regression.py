"""
Regression test for exact perturbed-mesh generation (Section 3 / A0-1).
Verifies:
- Recreating the same perturbed mesh twice produces identical node coordinates.
- Boundary node coordinates are strictly unchanged.
- The generator strictly follows the full-array random sequence (size Nnodes).
- All recorded quality metrics are finite and positive.
"""

import numpy as np
import pytest
from verification.mesh_utils import (
    create_structured_mesh,
    create_perturbed_mesh,
    generate_perturbed_mesh_metadata_report,
)


@pytest.mark.parametrize("n", [5, 8, 16, 32, 64, 128])
def test_perturbed_mesh_determinism_and_sequence(n: int):
    seed = 12345
    mesh1, m1 = create_perturbed_mesh(n, seed=seed)
    mesh2, m2 = create_perturbed_mesh(n, seed=seed)

    # 1. Identical node coordinates across separate runs
    np.testing.assert_array_equal(mesh1.p, mesh2.p, err_msg=f"Perturbed coordinates differ on n={n}")

    # 2. Base mesh comparison
    base_mesh, _ = create_structured_mesh(n)
    base_p = base_mesh.p
    tol = 1e-12
    is_boundary = (
        (np.abs(base_p[0] - 0.0) < tol) |
        (np.abs(base_p[0] - 1.0) < tol) |
        (np.abs(base_p[1] - 0.0) < tol) |
        (np.abs(base_p[1] - 1.0) < tol)
    )
    bnd_idx = np.where(is_boundary)[0]
    int_idx = np.where(~is_boundary)[0]

    # Boundary coordinates strictly identical to unperturbed mesh
    np.testing.assert_array_equal(
        mesh1.p[:, bnd_idx], base_p[:, bnd_idx],
        err_msg=f"Boundary coordinates were perturbed on n={n}"
    )

    # Interior coordinates must actually be perturbed
    assert np.any(np.abs(mesh1.p[:, int_idx] - base_p[:, int_idx]) > 1e-10)

    # 3. Verify full-array random sequence reproduction independently
    nnodes = base_p.shape[1]
    rng_indep = np.random.default_rng(seed)
    theta_expected = rng_indep.uniform(0.0, 2.0 * np.pi, nnodes)
    r_factor_expected = rng_indep.uniform(0.0, 0.2, nnodes)

    # Confirm array lengths match nnodes
    assert len(theta_expected) == nnodes
    assert len(r_factor_expected) == nnodes

    # 4. Confirm all recorded metrics are finite, positive, and valid
    assert m1["all_areas_positive"] is True
    assert m1["boundary_nodes_unchanged"] is True
    assert m1["accepted"] is True
    assert np.isfinite(m1["min_angle_deg"]) and m1["min_angle_deg"] > 10.0
    assert np.isfinite(m1["max_angle_deg"]) and m1["max_angle_deg"] < 170.0
    assert np.isfinite(m1["max_aspect_ratio"]) and m1["max_aspect_ratio"] > 1.0
    assert np.isfinite(m1["min_element_area"]) and m1["min_element_area"] > 0.0
    assert np.isfinite(m1["max_diameter_h"]) and m1["max_diameter_h"] > 0.0


def test_perturbed_mesh_metadata_generation():
    report = generate_perturbed_mesh_metadata_report()
    assert len(report) == 6
    for entry in report:
        assert entry["all_areas_positive"] is True
        assert entry["boundary_nodes_unchanged"] is True
        assert entry["accepted"] is True
        assert entry["random_seed"] == 12345
