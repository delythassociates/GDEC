"""
Tests for GDECMesh, boundary facet identification, and conforming refinement.
"""

import numpy as np
from gdec.fem.mesh import GDECMesh


def test_initial_mesh_creation():
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    assert mesh.nnodes == 45
    assert mesh.nelements == 64
    assert np.all(mesh.element_areas > 0)
    assert np.isclose(np.sum(mesh.element_areas), 2.0 * 0.5)


def test_boundary_facet_tagging():
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=9, ny=5)
    left_facets = mesh.get_boundary_facets("left")
    right_facets = mesh.get_boundary_facets("right")
    bottom_facets = mesh.get_boundary_facets("bottom")
    top_facets = mesh.get_boundary_facets("top")

    assert len(left_facets) == 4
    assert len(right_facets) == 4
    assert len(bottom_facets) == 8
    assert len(top_facets) == 8


def test_uniform_refinement_preserves_boundaries():
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    refined = mesh.refine_uniform()

    assert refined.nelements == mesh.nelements * 4
    assert len(refined.get_boundary_facets("left")) == len(mesh.get_boundary_facets("left")) * 2
    assert len(refined.get_boundary_facets("right")) == len(mesh.get_boundary_facets("right")) * 2
    assert np.isclose(np.sum(refined.element_areas), 1.0)


def test_local_refinement():
    mesh = GDECMesh.create_cantilever_mesh(width=2.0, height=0.5, nx=5, ny=3)
    marked = np.array([0, 1])
    refined = mesh.refine_elements(marked)

    assert refined.nelements > mesh.nelements
    assert refined.nnodes > mesh.nnodes
    # Total area must remain exactly conserved
    assert np.isclose(np.sum(refined.element_areas), 1.0)
