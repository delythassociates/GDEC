"""
Tests for Runtime Profiler and Factorization Reuse (v0.2).
"""

from gdec.compiler import GDECCompiler
from gdec.benchmark.profiling import RuntimeProfiler
from gdec.fem.mesh import GDECMesh
from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver
from gdec.fem.boundary_conditions import parse_boundary_conditions, parse_loads


def test_factorization_reuse_speedup_and_accuracy():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    geo = comp.ir.geometry
    mat = comp.ir.material
    c = ConstitutiveTensor.from_properties(
        E=mat.E, nu=mat.nu, assumption=mat.assumption, thickness=geo.thickness
    )
    solver = LinearElasticitySolver(c)
    mesh = GDECMesh.create_cantilever_mesh(width=geo.width, height=geo.height, nx=20, ny=10)
    loads = parse_loads(comp.ir.loads)
    bcs = parse_boundary_conditions(comp.ir.boundary_conditions)

    # Solve with reuse
    sol_opt = solver.solve(
        mesh, loads=loads, fixed_boundaries=bcs, solve_adjoint=True, reuse_factorization=True
    )
    # Solve without reuse
    sol_base = solver.solve(
        mesh, loads=loads, fixed_boundaries=bcs, solve_adjoint=True, reuse_factorization=False
    )

    # Displacements must be identical to numerical precision
    import numpy as np
    diff_u = np.linalg.norm(sol_opt.u - sol_base.u) / np.linalg.norm(sol_base.u)
    diff_z = np.linalg.norm(sol_opt.z - sol_base.z) / np.linalg.norm(sol_base.z)
    assert diff_u < 1e-11
    assert diff_z < 1e-11
    assert sol_opt.factorization_reused is True
    assert sol_base.factorization_reused is False


def test_runtime_profiler():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    prof = RuntimeProfiler.profile(comp.ir, grid_size=(15, 6), repetitions=2)

    assert prof.dofs > 0
    assert "Mesh Generation" in prof.stages
    assert "FEM Matrix Assembly" in prof.stages
    assert "Sparse Factorization" in prof.stages
    assert "Primal Solve" in prof.stages
    assert "Adjoint Solve" in prof.stages
    assert prof.factorization_reuse_speedup > 1.0
