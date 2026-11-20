"""
Mesh and spatial field visualizers for GDEC.
Renders 2D triangular mesh geometry, displacement magnitude contours,
and Von Mises stress fields.
"""

from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np

from gdec.fem.mesh import GDECMesh
from gdec.fem.postprocess import PostprocessResult
from gdec.visualization.plots import apply_dark_theme


def plot_mesh_geometry(
    gdec_mesh: GDECMesh,
    title: str = "Finite Element Mesh",
    highlight_elements: np.ndarray | None = None,
    dark_theme: bool = True,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 2.8), dpi=120)
    p = gdec_mesh.mesh.p
    t = gdec_mesh.mesh.t

    # Plot mesh wireframe
    ax.triplot(p[0], p[1], t.T, color="#58A6FF" if dark_theme else "#1F77B4", linewidth=0.5, alpha=0.7)

    # Highlight marked elements if provided
    if highlight_elements is not None and len(highlight_elements) > 0:
        marked_t = t[:, highlight_elements]
        ax.tripcolor(
            p[0],
            p[1],
            marked_t.T,
            facecolors=np.ones(len(highlight_elements)),
            cmap="autumn",
            alpha=0.6,
            edgecolors="#FF7B72",
            linewidth=0.8,
        )

    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    sub = f"Elements: {gdec_mesh.nelements:,} | Nodes: {gdec_mesh.nnodes:,}"
    ax.set_title(f"{title}\n{sub}", fontsize=10)

    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_von_mises_field(
    gdec_mesh: GDECMesh,
    post: PostprocessResult,
    title: str = "Von Mises Stress Field (Plane Stress)",
    dark_theme: bool = True,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=120)
    p = gdec_mesh.mesh.p
    t = gdec_mesh.mesh.t

    triang = mtri.Triangulation(p[0], p[1], t.T)
    # Convert Pa to MPa
    vm_mpa = post.nodal_von_mises / 1e6

    cntr = ax.tricontourf(triang, vm_mpa, levels=40, cmap="viridis")
    cbar = fig.colorbar(cntr, ax=ax, orientation="horizontal", pad=0.25, shrink=0.7)
    cbar.set_label("Von Mises Stress (MPa)", color="#F0F6FC" if dark_theme else "#000")
    if dark_theme:
        cbar.ax.tick_params(colors="#C9D1D9")

    # Overlay wireframe gently
    ax.triplot(triang, color="#30363D", linewidth=0.3, alpha=0.5)

    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(title, fontsize=10)

    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_displacement_field(
    gdec_mesh: GDECMesh,
    post: PostprocessResult,
    title: str = "Displacement Magnitude |u|",
    dark_theme: bool = True,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=120)
    p = gdec_mesh.mesh.p
    t = gdec_mesh.mesh.t

    triang = mtri.Triangulation(p[0], p[1], t.T)
    # Convert m to mm
    disp_mm = np.sqrt(post.u_x**2 + post.u_y**2) * 1e3

    cntr = ax.tricontourf(triang, disp_mm, levels=40, cmap="magma")
    cbar = fig.colorbar(cntr, ax=ax, orientation="horizontal", pad=0.25, shrink=0.7)
    cbar.set_label("Displacement Magnitude (mm)", color="#F0F6FC" if dark_theme else "#000")
    if dark_theme:
        cbar.ax.tick_params(colors="#C9D1D9")

    ax.triplot(triang, color="#30363D", linewidth=0.3, alpha=0.5)

    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(title, fontsize=10)

    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_indicator_field(
    gdec_mesh: GDECMesh,
    indicators: np.ndarray,
    title: str = "Refinement Sensitivity Distribution",
    dark_theme: bool = True,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=120)
    p = gdec_mesh.mesh.p
    t = gdec_mesh.mesh.t

    # Face colors
    triang = mtri.Triangulation(p[0], p[1], t.T)
    cntr = ax.tripcolor(triang, facecolors=indicators, cmap="plasma", edgecolors="#30363D", linewidth=0.4)
    cbar = fig.colorbar(cntr, ax=ax, orientation="horizontal", pad=0.25, shrink=0.7)
    cbar.set_label("Indicator Value", color="#F0F6FC" if dark_theme else "#000")
    if dark_theme:
        cbar.ax.tick_params(colors="#C9D1D9")

    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(title, fontsize=10)

    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig
