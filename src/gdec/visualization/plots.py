"""
Comparative benchmark plots for GDEC.
Generates publication-quality technical plots comparing Uniform, Recovery, and Goal-Aware strategies.
"""

from __future__ import annotations
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless execution and server usage
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, Optional

from gdec.benchmark.runner import BenchmarkSuiteResult


def apply_dark_theme(ax, fig=None):
    if fig:
        fig.patch.set_facecolor("#0E1117")
    ax.set_facecolor("#161B22")
    ax.tick_params(colors="#C9D1D9", which="both")
    ax.xaxis.label.set_color("#F0F6FC")
    ax.yaxis.label.set_color("#F0F6FC")
    ax.title.set_color("#58A6FF")
    for spine in ax.spines.values():
        spine.set_color("#30363D")
    ax.grid(True, linestyle="--", alpha=0.3, color="#8B949E")


STRATEGY_COLORS = {
    "uniform": "#8B949E",      # Neutral Grey
    "recovery": "#E3B341",     # Warm Gold/Amber
    "goal_aware": "#58A6FF",   # Engineering Blue
}

STRATEGY_MARKERS = {
    "uniform": "s",
    "recovery": "^",
    "goal_aware": "o",
}


def plot_qoi_vs_dofs(suite_res: BenchmarkSuiteResult, dark_theme: bool = True) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)
    ref = suite_res.reference

    # Reference line
    ax.axhline(
        ref.qoi_mm,
        color="#F85149",
        linestyle="--",
        linewidth=1.5,
        label=f"Reference ({ref.qoi_mm:.4f} mm)",
        alpha=0.8,
    )

    for strat, res in suite_res.strategies.items():
        dofs = [it.dofs for it in res.iterations]
        qois = [it.qoi_mm for it in res.iterations]
        color = STRATEGY_COLORS.get(strat, "#58A6FF")
        marker = STRATEGY_MARKERS.get(strat, "o")
        ax.plot(
            dofs,
            qois,
            marker=marker,
            color=color,
            linewidth=1.8,
            markersize=6,
            label=strat.replace("_", " ").title(),
        )

    ax.set_xlabel("Degrees of Freedom (DOFs)")
    ax.set_ylabel("Quantity of Interest: Average $u_y$ (mm)")
    ax.set_title("QoI Convergence vs DOFs")
    ax.legend(framealpha=0.8)
    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_error_vs_dofs(suite_res: BenchmarkSuiteResult, dark_theme: bool = True) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)

    for strat, res in suite_res.strategies.items():
        dofs = [it.dofs for it in res.iterations]
        errs = [max(it.reference_error_pct, 1e-4) for it in res.iterations]
        color = STRATEGY_COLORS.get(strat, "#58A6FF")
        marker = STRATEGY_MARKERS.get(strat, "o")
        ax.plot(
            dofs,
            errs,
            marker=marker,
            color=color,
            linewidth=1.8,
            markersize=6,
            label=strat.replace("_", " ").title(),
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Degrees of Freedom (log scale)")
    ax.set_ylabel("Reference QoI Error % (log scale)")
    ax.set_title("Error vs DOFs (Pareto Convergence)")
    ax.legend(framealpha=0.8)
    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_error_vs_time(suite_res: BenchmarkSuiteResult, dark_theme: bool = True) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)

    for strat, res in suite_res.strategies.items():
        times = [max(it.cumulative_time_sec, 1e-4) for it in res.iterations]
        errs = [max(it.reference_error_pct, 1e-4) for it in res.iterations]
        color = STRATEGY_COLORS.get(strat, "#58A6FF")
        marker = STRATEGY_MARKERS.get(strat, "o")
        ax.plot(
            times,
            errs,
            marker=marker,
            color=color,
            linewidth=1.8,
            markersize=6,
            label=strat.replace("_", " ").title(),
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Cumulative Wall Time (s, log scale)")
    ax.set_ylabel("Reference QoI Error % (log scale)")
    ax.set_title("Error vs Computational Time")
    ax.legend(framealpha=0.8)
    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_dofs_vs_time(suite_res: BenchmarkSuiteResult, dark_theme: bool = True) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)

    for strat, res in suite_res.strategies.items():
        times = [it.cumulative_time_sec for it in res.iterations]
        dofs = [it.dofs for it in res.iterations]
        color = STRATEGY_COLORS.get(strat, "#58A6FF")
        marker = STRATEGY_MARKERS.get(strat, "o")
        ax.plot(
            times,
            dofs,
            marker=marker,
            color=color,
            linewidth=1.8,
            markersize=6,
            label=strat.replace("_", " ").title(),
        )

    ax.set_xlabel("Cumulative Wall Time (s)")
    ax.set_ylabel("Degrees of Freedom (DOFs)")
    ax.set_title("DOF Scalability vs Time")
    ax.legend(framealpha=0.8)
    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig


def plot_memory_vs_dofs(suite_res: BenchmarkSuiteResult, dark_theme: bool = True) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)

    for strat, res in suite_res.strategies.items():
        dofs = [it.dofs for it in res.iterations]
        mems = [it.peak_memory_mb for it in res.iterations]
        color = STRATEGY_COLORS.get(strat, "#58A6FF")
        marker = STRATEGY_MARKERS.get(strat, "o")
        ax.plot(
            dofs,
            mems,
            marker=marker,
            color=color,
            linewidth=1.8,
            markersize=6,
            label=strat.replace("_", " ").title(),
        )

    ax.set_xlabel("Degrees of Freedom (DOFs)")
    ax.set_ylabel("Peak Process RSS (MB)")
    ax.set_title("Memory Usage vs Discretization Size")
    ax.legend(framealpha=0.8)
    if dark_theme:
        apply_dark_theme(ax, fig)
    fig.tight_layout()
    return fig
