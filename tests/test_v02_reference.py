"""
Tests for Reference Solution verification and Timoshenko beam theory comparison (v0.2).
"""

from gdec.compiler import GDECCompiler
from gdec.benchmark.reference import ReferenceSolver, compute_timoshenko_cantilever


def test_reference_multi_resolution_convergence():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    assert comp.success is True

    ref = ReferenceSolver.compute_reference(comp.ir, target_dofs=15000, verify_convergence=True)
    assert ref.convergence_report is not None
    rep = ref.convergence_report

    # Must contain 3 progressive levels
    assert len(rep.levels) == 3
    # DOFs must strictly increase across levels
    assert rep.levels[0].dofs < rep.levels[1].dofs < rep.levels[2].dofs
    # Relative changes must be calculated
    assert len(rep.relative_changes_pct) == 2
    # Discretization uncertainty must be finite and positive
    assert 0.0 < rep.estimated_discretization_uncertainty_pct < 1.0


def test_timoshenko_analytical_comparison():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    geo = comp.ir.geometry
    mat = comp.ir.material
    load = comp.ir.loads[0]

    timo = compute_timoshenko_cantilever(
        width=geo.width,
        height=geo.height,
        thickness=geo.thickness,
        E=mat.E,
        nu=mat.nu,
        ty=load.ty,
    )

    # Euler-Bernoulli deflection is negative
    assert timo["delta_euler_bernoulli_mm"] < 0.0
    # Shear deflection adds additional negative displacement
    assert timo["delta_shear_mm"] < 0.0
    assert timo["delta_timoshenko_total_mm"] < timo["delta_euler_bernoulli_mm"]
    # For cantilever L=2, H=0.5, t=0.02, E=70GPa, ty=-1MPa, total Timoshenko is ~ -1.92 mm
    assert -1.95 < timo["delta_timoshenko_total_mm"] < -1.88
