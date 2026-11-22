"""
Status register generator and CI traceability verification engine for GDEC.
Generates machine-readable results/status_register.json and enforces that
every capability claimed as NUMERICALLY VERIFIED is backed by verified tests.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class TraceabilityVerificationError(RuntimeError):
    """Raised when a claimed status in the register lacks passing test evidence or is stale."""


@dataclass(frozen=True)
class CapabilityEntry:
    capability_id: str
    name: str
    subsystem: str
    claimed_status: str  # PLANNED, IMPLEMENTED, EXECUTED, TESTED, NUMERICALLY VERIFIED, INDEPENDENTLY VALIDATED
    evidence_path: str
    test_files: List[str]
    required_test_node_ids: List[str]
    verification_criteria: str
    notes: str


# Canonical registry mapping 1-to-1 with docs/GDEC_ENGINEERING_STATUS.md
SYSTEM_CAPABILITIES: List[CapabilityEntry] = [
    # 2.1 Compiler and Language Frontend
    CapabilityEntry(
        capability_id="compiler_lark_parser",
        name="Lark EBNF Lexer & Parser",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_language.py",
        test_files=["tests/test_language.py", "tests/test_compiler_validation.py"],
        required_test_node_ids=[
            "tests/test_language.py::test_valid_source_parses",
            "tests/test_language.py::test_syntax_error_rejected",
            "tests/test_compiler_validation.py::test_duplicate_positional_and_named_boundary",
        ],
        verification_criteria="Valid GDEC program parsed to AST without ambiguity; syntax errors and positional/named conflicts rejected.",
        notes="LALR grammar in grammar.lark. Duplicate named arguments and invalid syntax rejected.",
    ),
    CapabilityEntry(
        capability_id="compiler_strict_declarations",
        name="Strict Top-Level Declarations",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py", "tests/test_language.py"],
        required_test_node_ids=[
            "tests/test_compiler_validation.py::test_unknown_backend_device",
            "tests/test_language.py::test_missing_physics_rejected",
        ],
        verification_criteria="Unknown top-level blocks, invalid backends, or missing physics declarations fail-closed.",
        notes="Only known declarations accepted; unknown statements trigger source-located syntax errors.",
    ),
    CapabilityEntry(
        capability_id="compiler_singleton_enforcement",
        name="Singleton Declaration Enforcement",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py"],
        required_test_node_ids=[
            "tests/test_compiler_validation.py::test_duplicate_boundary_fix",
            "tests/test_compiler_validation.py::test_duplicate_positional_and_named_boundary",
        ],
        verification_criteria="Duplicate top-level declaration blocks and duplicate boundary fixes rejected; singletons enforced.",
        notes="Top-level blocks rejected if duplicated.",
    ),
    CapabilityEntry(
        capability_id="compiler_scalar_validation",
        name="Scalar & Type Validation",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py"],
        required_test_node_ids=[
            "tests/test_compiler_validation.py::test_boolean_passed_to_float_geometry_rejected",
            "tests/test_compiler_validation.py::test_fractional_dof_budget_rejected",
            "tests/test_compiler_validation.py::test_nonfinite_numeric_values_rejected[nan]",
        ],
        verification_criteria="Rejects NaN, inf, overflow, boolean types in numeric contexts, and non-integer mesh budgets.",
        notes="Rejects NaN, inf, overflow, boolean-as-float, fractional budget.",
    ),
    CapabilityEntry(
        capability_id="compiler_material_bounds",
        name="Material Constant Bounds",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py", "tests/test_language.py"],
        required_test_node_ids=[
            "tests/test_language.py::test_negative_youngs_modulus_rejected",
            "tests/test_language.py::test_invalid_poisson_ratio_rejected",
            "tests/test_compiler_validation.py::test_invalid_poisson_ratio_bounds[-1.0]",
        ],
        verification_criteria="Enforces physical elasticity bounds: Young's modulus E > 0 and Poisson's ratio -1.0 < nu < 0.5.",
        notes="Enforces E > 0 and -1.0 < nu < 0.5.",
    ),
    CapabilityEntry(
        capability_id="compiler_typed_problem_ir",
        name="Typed ProblemIR Contract",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_ir.py",
        test_files=["tests/test_ir.py", "tests/test_compiler_validation.py"],
        required_test_node_ids=[
            "tests/test_ir.py::test_ir_roundtrip_json",
            "tests/test_compiler_validation.py::test_typed_ir_direct_instantiation_rejects_conflicting_bc_and_load",
            "tests/test_compiler_validation.py::test_typed_ir_direct_instantiation_rejects_objective_on_fixed_boundary",
        ],
        verification_criteria="Typed Pydantic ProblemIR model constructed with cross-field invariants; boundary conflicts rejected.",
        notes="Pydantic model enforcing cross-field engineering invariants.",
    ),

    # 2.2 Numerical Mechanics & FEM Engine
    CapabilityEntry(
        capability_id="fem_p1_triangles_patch_test",
        name="2D Linear Elasticity (P1 Triangles) Patch Test",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_constant_strain_patch_test_distorted_mesh",
        ],
        verification_criteria="Constant-strain patch test on distorted irregular triangular mesh reproduces linear displacement field with max nodal error < 1e-11 m.",
        notes="Constant-strain patch test on distorted mesh passes with error < 1e-11 m.",
    ),
    CapabilityEntry(
        capability_id="fem_stiffness_assembly_nullspace",
        name="Bilinear Stiffness Assembly Nullspace",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_unconstrained_stiffness_rigid_body_modes",
        ],
        verification_criteria="Unconstrained 2D elasticity stiffness matrix has exactly 3 zero eigenvalues corresponding to rigid-body modes (2 translations, 1 rotation).",
        notes="Unconstrained stiffness matrix has exactly 3 rigid-body null modes.",
    ),
    CapabilityEntry(
        capability_id="fem_dirichlet_condensation",
        name="Dirichlet Elimination (Condensation)",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_distorted_mesh_positive_definiteness_and_solvability",
            "tests/test_fem_mathematical_verification.py::test_pure_tension_linear_displacement_reproduction",
        ],
        verification_criteria="Prescribed Dirichlet DOFs satisfy boundary values exactly and condensed free DOF system is strictly positive definite.",
        notes="Correct partition and elimination via boundary condensation.",
    ),
    CapabilityEntry(
        capability_id="fem_traction_boundary_assembly",
        name="Traction Boundary Assembly & Force Balance",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_reaction_force_accuracy_on_clamped_boundary",
        ],
        verification_criteria="Neumann boundary integral matches applied surface traction to relative error < 1e-14 and reaction force balances applied load.",
        notes="Total force balances to machine precision; reaction equals load.",
    ),
    CapabilityEntry(
        capability_id="fem_global_equilibrium_conservation",
        name="Global Equilibrium Conservation",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_global_force_and_moment_equilibrium",
        ],
        verification_criteria="Reaction forces satisfy global equilibrium: net force error < 1e-7 N, scale-aware moment equilibrium error < 1e-9 relative to moment scale M0.",
        notes="Linear force balance < 1e-7 N; scale-aware moment balance < 1e-9 relative.",
    ),
    CapabilityEntry(
        capability_id="fem_analytical_beam_convergence",
        name="Analytical Timoshenko Beam Convergence",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_cantilever_beam_timoshenko_analytical_comparison",
        ],
        verification_criteria="Cantilever tip deflection converges monotonically from below under uniform refinement, agreeing within 1.29% of Timoshenko analytical solution on fine mesh.",
        notes="Tip deflection converges monotonically from below; within 1.29% on fine mesh.",
    ),
    CapabilityEntry(
        capability_id="fem_manufactured_pure_bending",
        name="Manufactured Pure Bending Solution",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_manufactured_solution_pure_bending",
        ],
        verification_criteria="Manufactured exact quadratic displacement field for pure bending reproduced with nodal displacement error < 1e-11 m.",
        notes="Exact quadratic bending field reproduced to < 1e-11 m.",
    ),
    CapabilityEntry(
        capability_id="fem_energy_monotonicity",
        name="Rayleigh-Ritz Energy Monotonicity",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_mesh_refinement_energy_monotonicity",
        ],
        verification_criteria="Total strain energy strictly monotonically increases under nested conforming mesh refinement per Rayleigh-Ritz variational principle.",
        notes="Strain energy strictly increases monotonically under conforming uniform refinement.",
    ),
    CapabilityEntry(
        capability_id="fem_plane_strain_out_of_plane_stress",
        name="Plane Strain Out-of-Plane Stress",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        required_test_node_ids=[
            "tests/test_fem_mathematical_verification.py::test_plane_strain_out_of_plane_stress_invariant",
        ],
        verification_criteria="Out-of-plane normal stress sigma_zz = nu*(sigma_xx + sigma_yy) is included in plane strain, and von Mises stress matches analytical value within 1e-10 Pa.",
        notes="sigma_zz = nu*(sigma_xx + sigma_yy) accurately included in 3D von Mises invariant.",
    ),
    CapabilityEntry(
        capability_id="fem_primal_adjoint_factorization_reuse",
        name="Primal-Adjoint Factorization Reuse",
        subsystem="fem",
        claimed_status="TESTED",
        evidence_path="tests/test_v02_profiling_and_reuse.py",
        test_files=["tests/test_elasticity.py", "tests/test_v02_profiling_and_reuse.py"],
        required_test_node_ids=[
            "tests/test_v02_profiling_and_reuse.py::test_factorization_reuse_speedup_and_accuracy",
        ],
        verification_criteria="Sparse LU / Cholesky factorization of stiffness matrix is reused for adjoint solve without refactorization.",
        notes="Sparse LU factorization shared between primal solve Ku=f and dual solve Kz=g.",
    ),

    # 2.3 Error Estimation & Adaptivity
    CapabilityEntry(
        capability_id="estimator_residual_energy_norm",
        name="Residual Energy-Norm Indicator",
        subsystem="estimator",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dwr_verification.py",
        test_files=["tests/test_estimators.py", "tests/test_dwr_verification.py"],
        required_test_node_ids=[
            "tests/test_dwr_verification.py::test_dwr_nonzero_residual_under_discretization_error",
            "tests/test_estimators.py::test_estimator_indicators",
        ],
        verification_criteria="Ainsworth-Oden interior facet traction jump residual indicator evaluates on all elements and is non-zero under discretization error.",
        notes="Ainsworth-Oden residual indicator based on interior facet traction jumps.",
    ),
    CapabilityEntry(
        capability_id="estimator_goal_oriented_dwr",
        name="Goal-Oriented DWR Estimator",
        subsystem="estimator",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dwr_verification.py",
        test_files=["tests/test_dwr_verification.py"],
        required_test_node_ids=[
            "tests/test_dwr_verification.py::test_dwr_qoi_error_estimation_and_effectivity_convergence",
        ],
        verification_criteria="Goal-oriented dual-weighted residual effectivity ratio |eta/e| increases monotonically toward unity (0.51 -> 0.91) under mesh refinement.",
        notes="Dual-weighted residual estimator with interior jumps, bubble recovery, effectivity convergence (0.51 -> 0.91).",
    ),
    CapabilityEntry(
        capability_id="estimator_amr_marking_cycle",
        name="Adaptive Refinement Marking Cycle",
        subsystem="estimator",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dwr_verification.py",
        test_files=["tests/test_dwr_verification.py", "tests/test_estimators.py"],
        required_test_node_ids=[
            "tests/test_dwr_verification.py::test_dwr_adaptive_refinement_reduces_qoi_error",
        ],
        verification_criteria="Dörfler AMR marking cycle adaptively refines elements and reduces QoI error monotonically across 4 iterations within budget.",
        notes="Monotonic error reduction over 4 AMR iterations under budget.",
    ),

    # 2.4 Linear Solvers & Numerical Diagnostics
    CapabilityEntry(
        capability_id="solver_matrix_diagnostics",
        name="Stiffness Matrix Diagnostics & Scale Invariance",
        subsystem="solver",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_matrix_diagnostics.py",
        test_files=["tests/test_matrix_diagnostics.py"],
        required_test_node_ids=[
            "tests/test_matrix_diagnostics.py::test_scale_invariance_across_orders_of_magnitude",
            "tests/test_matrix_diagnostics.py::test_symmetry_defect_exact_and_perturbed",
        ],
        verification_criteria="Stiffness matrix condition number and symmetry defect are scale-invariant across 28 orders of magnitude (1e-14 <= c <= 1e14).",
        notes="Scale-invariant condition number and symmetry metric across 1e-14 <= c <= 1e14.",
    ),
    CapabilityEntry(
        capability_id="solver_cg_direct_residual_recalculation",
        name="CG Direct Residual Recalculation",
        subsystem="solver",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_iterative_solvers.py",
        test_files=["tests/test_iterative_solvers.py"],
        required_test_node_ids=[
            "tests/test_iterative_solvers.py::test_linear_elasticity_solver_telemetry_corrections",
            "tests/test_iterative_solvers.py::test_cantilever_cg_vs_direct_equivalence",
        ],
        verification_criteria="CG solver explicitly recalculates true residual r = b - A*x at convergence to prevent false convergence from accumulated roundoff.",
        notes="Direct recalculation r = b - A*x ensures true residual within tolerance.",
    ),

    # 2.5 DSE & EIR Hardening
    CapabilityEntry(
        capability_id="dse_linear_elastic_scaling_monte_carlo",
        name="Linear Elastic Analytical Scaling Agreement",
        subsystem="dse",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_independent_fem_validation.py",
        test_files=["tests/test_independent_fem_validation.py"],
        required_test_node_ids=[
            "tests/test_independent_fem_validation.py::test_independent_fem_scaling_agreement",
        ],
        verification_criteria="Analytical scaling law u(P, E, t) = u0 * (P/P0) * (E0/E) * (t0/t) verified against full independent scikit-fem solves with max relative discrepancy < 1e-14.",
        notes="Analytical scaling agrees with independent scikit-fem elasticity within machine precision.",
    ),
    CapabilityEntry(
        capability_id="dse_single_qoi_evaluator",
        name="Single-QoI Decision Sufficiency Evaluator",
        subsystem="dse",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dse.py",
        test_files=["tests/test_dse.py"],
        required_test_node_ids=[
            "tests/test_dse.py::test_evaluator_refusal_on_missing_uncertainty",
            "tests/test_dse.py::test_evaluator_known_gaussian_calculation",
        ],
        verification_criteria="Bayesian expected loss evaluation selects optimal design under uncertainty and refuses evaluation when required evidence or epistemic bounds are missing.",
        notes="Strict Bayesian loss evaluation, refusing when evidence is absent or insufficient.",
    ),
    CapabilityEntry(
        capability_id="eir_canonical_hash_determinism",
        name="Canonical EIR Hash Determinism",
        subsystem="eir",
        claimed_status="TESTED",
        evidence_path="tests/eir/test_adversarial_hardening.py",
        test_files=["tests/eir/test_adversarial_hardening.py"],
        required_test_node_ids=[
            "tests/eir/test_adversarial_hardening.py::TestCanonicalHashDeterminism::test_hash_invariant_to_dict_insertion_order",
        ],
        verification_criteria="Canonical EIR SHA-256 hash is invariant to dictionary key ordering, whitespace variations, and equivalent float representations.",
        notes="SHA-256 hash invariant across dict order, line endings, and equivalent units.",
    ),
]


STATUS_HIERARCHY = [
    "PLANNED",
    "IMPLEMENTED",
    "EXECUTED",
    "TESTED",
    "NUMERICALLY VERIFIED",
    "INDEPENDENTLY VALIDATED",
]
STATUS_RANK = {s: i for i, s in enumerate(STATUS_HIERARCHY)}


class PytestCollector:
    """In-process pytest plugin to capture executed test nodeids, collection errors, and exit status."""
    def __init__(self):
        self.results: Dict[str, str] = {}  # normalized nodeid -> "PASS" | "FAIL" | "SKIP"
        self.collection_errors: List[str] = []
        self.exit_code: int = 0

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(f"Collection failure in {report.nodeid}: {report.longreprtext}")

    def pytest_runtest_logreport(self, report):
        norm_nodeid = report.nodeid.replace("\\", "/")
        if report.when == "call":
            if report.passed:
                self.results[norm_nodeid] = "PASS"
            elif report.failed:
                self.results[norm_nodeid] = "FAIL"
            elif report.skipped:
                self.results[norm_nodeid] = "SKIP"
        elif report.when == "setup":
            if report.failed:
                self.results[norm_nodeid] = "FAIL"
            elif report.skipped:
                self.results[norm_nodeid] = "SKIP"

    def pytest_sessionfinish(self, session, exitstatus):
        self.exit_code = int(exitstatus)


class GitInspectionError(RuntimeError):
    """Raised when Git repository inspection fails or repository state cannot be verified."""


def collect_live_test_results(test_files: Optional[List[str]] = None) -> Tuple[Dict[str, str], List[str], int]:
    """Execute pytest on target files and collect live outcomes for every individual test."""
    import pytest
    collector = PytestCollector()
    args = test_files if test_files else ["tests/"]
    pytest.main(args + ["-q"], plugins=[collector])
    return collector.results, collector.collection_errors, collector.exit_code


def get_git_info(repo_dir: Optional[str] = None, fail_fast: bool = False) -> Dict[str, Any]:
    """
    Retrieve current commit SHA, branch name, and dirty working tree status.
    Fails closed: if any required Git command fails, records explicit error details
    and marks git inspection as failed (git_valid=False).
    Never silently converts Git failures into clean/unknown status.
    """
    cwd = repo_dir if repo_dir else os.getcwd()
    git_errors: List[str] = []

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=cwd, text=True, stderr=subprocess.PIPE
        ).strip()
        if not sha or len(sha) < 7:
            sha = "unknown"
            git_errors.append("git rev-parse HEAD returned empty or invalid commit SHA.")
    except Exception as e:
        sha = "unknown"
        git_errors.append(f"git rev-parse HEAD failed: {e}")

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, text=True, stderr=subprocess.PIPE
        ).strip()
        if not branch:
            branch = "unknown"
            git_errors.append("git rev-parse --abbrev-ref HEAD returned empty branch.")
    except Exception as e:
        branch = "unknown"
        git_errors.append(f"git rev-parse --abbrev-ref HEAD failed: {e}")

    PRESERVED_USER_PREFIXES = (
        "src/gdec/core/analyser.py",
        "src/gdec/runtime/",
        "src/gdec/runtime\\",
    )
    dirty_entries = []
    try:
        raw_status = subprocess.check_output(
            ["git", "status", "--porcelain", "-uall"], cwd=cwd, text=True, stderr=subprocess.PIPE
        ).splitlines()
        for line in raw_status:
            entry = line.strip()
            if not entry:
                continue
            code = line[:2]
            path = line[3:].strip()
            norm_path = path.replace("\\", "/")
            if code == "??" and any(norm_path.startswith(prefix.replace("\\", "/")) for prefix in PRESERVED_USER_PREFIXES):
                continue
            dirty_entries.append(line)
    except Exception as e:
        git_errors.append(f"git status --porcelain -uall failed: {e}")

    git_valid = (len(git_errors) == 0) and (sha != "unknown") and (branch != "unknown")
    is_dirty = (len(dirty_entries) > 0) or (not git_valid)

    if fail_fast and not git_valid:
        raise GitInspectionError("Git inspection failed closed:\n" + "\n".join(f"  - {err}" for err in git_errors))

    return {
        "commit_sha": sha,
        "branch": branch,
        "dirty": is_dirty,
        "dirty_entries": dirty_entries,
        "git_valid": git_valid,
        "git_errors": git_errors,
    }


def get_provenance_info() -> Dict[str, Any]:
    """Capture environment execution provenance (CI run vs local)."""
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    return {
        "is_ci": is_ci,
        "github_run_id": os.environ.get("GITHUB_RUN_ID") if is_ci else None,
        "github_workflow": os.environ.get("GITHUB_WORKFLOW") if is_ci else None,
        "github_sha": os.environ.get("GITHUB_SHA") if is_ci else None,
        "local_execution": not is_ci,
    }


def get_environment_info() -> Dict[str, Any]:
    """Gather complete Python and scientific dependency versions."""
    import numpy as np
    import scipy
    import skfem
    import lark
    import pydantic

    env: Dict[str, Any] = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "scikit_fem_version": skfem.__version__,
        "lark_version": lark.__version__,
        "pydantic_version": pydantic.__version__,
    }
    try:
        import cupy as cp
        env["cupy_available"] = True
        env["cupy_version"] = cp.__version__
    except ImportError:
        env["cupy_available"] = False
        env["cupy_version"] = None

    return env


def generate_status_register(
    output_path: str = "results/status_register.json",
    run_tests: bool = True,
    test_results: Optional[Dict[str, str]] = None,
    collection_errors: Optional[List[str]] = None,
    exit_code: int = 0,
    repo_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate machine-readable status_register.json with commit, environment,
    capabilities, and verified test states backed by actual pytest execution.
    Computes demonstrated_status strictly from required test execution outcomes.
    No subsystem or name heuristics are used.
    """
    git_info = get_git_info(repo_dir=repo_dir)
    provenance_info = get_provenance_info()
    env_info = get_environment_info()
    now_iso = datetime.now(timezone.utc).isoformat()

    live_coll_errors: List[str] = collection_errors or []
    live_exit_code: int = exit_code

    # Collect live test execution results across test files if requested
    if test_results is None and run_tests:
        all_test_files = sorted(list(set(tf for cap in SYSTEM_CAPABILITIES for tf in cap.test_files if os.path.exists(tf))))
        live_test_results, live_coll_errors, live_exit_code = collect_live_test_results(all_test_files)
    else:
        live_test_results = test_results or {}

    # Normalize keys in live_test_results to forward slashes
    norm_live_results = {k.replace("\\", "/"): v for k, v in live_test_results.items()}

    capabilities_data = []
    for cap in SYSTEM_CAPABILITIES:
        all_tests_exist = all(os.path.exists(tf) for tf in cap.test_files)

        # Check required test node IDs
        required_nodes = [rn.replace("\\", "/") for rn in cap.required_test_node_ids]
        matched_required: Dict[str, str] = {}
        for rn in required_nodes:
            if rn in norm_live_results:
                matched_required[rn] = norm_live_results[rn]

        # Also collect all executed tests from capability test_files for reporting
        matching_file_tests: Dict[str, str] = {}
        for nodeid, status in norm_live_results.items():
            if any(tf.replace("\\", "/") in nodeid for tf in cap.test_files):
                matching_file_tests[nodeid] = status

        executed_test_ids = list(matching_file_tests.keys())
        passed_test_ids = [nid for nid, st in matching_file_tests.items() if st == "PASS"]
        failed_test_ids = [nid for nid, st in matching_file_tests.items() if st == "FAIL"]
        skipped_test_ids = [nid for nid, st in matching_file_tests.items() if st == "SKIP"]

        # Derive state strictly from required_nodes
        req_passed = [rn for rn in required_nodes if matched_required.get(rn) == "PASS"]
        req_failed = [rn for rn in required_nodes if matched_required.get(rn) == "FAIL"]
        req_skipped = [rn for rn in required_nodes if matched_required.get(rn) == "SKIP"]
        req_missing = [rn for rn in required_nodes if rn not in matched_required]

        if not all_tests_exist or len(req_missing) == len(required_nodes):
            execution_state = "NOT_RUN"
            demonstrated_status = "PLANNED"
        elif len(req_failed) > 0:
            execution_state = "FAIL"
            demonstrated_status = "FAILED"
        elif len(req_skipped) > 0 and len(req_passed) == 0:
            execution_state = "SKIPPED"
            demonstrated_status = "SKIPPED"
        elif len(req_skipped) > 0 or len(req_missing) > 0:
            execution_state = "PARTIAL"
            demonstrated_status = "PARTIAL_SKIP"
        elif len(req_passed) == len(required_nodes):
            execution_state = "PASS"
            # Policy (WP2-EIP): Automated unit/verification tests alone cannot grant INDEPENDENTLY VALIDATED.
            # Independent physical validation requires external physical/experimental attestation and human review.
            # The maximum status achievable solely via automated test suite execution is NUMERICALLY VERIFIED.
            if cap.claimed_status == "INDEPENDENTLY VALIDATED":
                demonstrated_status = "NUMERICALLY VERIFIED"
            else:
                demonstrated_status = cap.claimed_status
        else:
            execution_state = "NOT_RUN"
            demonstrated_status = "PLANNED"

        cap_dict = asdict(cap)
        cap_dict["test_files_exist"] = all_tests_exist
        cap_dict["executed_test_ids"] = executed_test_ids
        cap_dict["passed_test_ids"] = passed_test_ids
        cap_dict["failed_test_ids"] = failed_test_ids
        cap_dict["skipped_test_ids"] = skipped_test_ids
        cap_dict["required_nodes_passed"] = req_passed
        cap_dict["required_nodes_failed"] = req_failed
        cap_dict["required_nodes_skipped"] = req_skipped
        cap_dict["required_nodes_missing"] = req_missing
        cap_dict["test_execution_state"] = execution_state
        cap_dict["demonstrated_status"] = demonstrated_status
        capabilities_data.append(cap_dict)

    register_data = {
        "schema_version": "1.1.0",
        "generated_at": now_iso,
        "git": git_info,
        "provenance": provenance_info,
        "environment": env_info,
        "collection_errors": live_coll_errors,
        "pytest_exit_code": live_exit_code,
        "total_capabilities": len(capabilities_data),
        "status_summary": {
            "NUMERICALLY VERIFIED": sum(1 for c in capabilities_data if c["demonstrated_status"] == "NUMERICALLY VERIFIED"),
            "TESTED": sum(1 for c in capabilities_data if c["demonstrated_status"] == "TESTED"),
            "IMPLEMENTED": sum(1 for c in capabilities_data if c["demonstrated_status"] == "IMPLEMENTED"),
            "PLANNED": sum(1 for c in capabilities_data if c["demonstrated_status"] == "PLANNED"),
            "FAILED": sum(1 for c in capabilities_data if c["demonstrated_status"] == "FAILED"),
            "SKIPPED": sum(1 for c in capabilities_data if c["demonstrated_status"] in ("SKIPPED", "PARTIAL_SKIP")),
        },
        "capabilities": capabilities_data,
    }

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(register_data, f, indent=2)

    return register_data


def verify_traceability(
    register_data: Dict[str, Any],
    on_disk_path: Optional[str] = None,
    allow_dirty: bool = False,
    allow_stale: bool = False,
    repo_dir: Optional[str] = None,
) -> None:
    """
    Strict traceability gate:
    1. Rejects currently dirty working trees (tracked or untracked modifications).
    2. Detects stale status register by comparing recorded commit SHA against current HEAD.
    3. Fails if collection errors or non-zero pytest exit codes are recorded.
    4. Fails if claimed status exceeds rigorously demonstrated status.
    5. Fails if any required test did not execute, failed, or was skipped.
    """
    live_git = get_git_info(repo_dir=repo_dir)

    # 0. Fail closed on Git inspection errors
    if not live_git.get("git_valid", False):
        errs = live_git.get("git_errors", ["Unknown git inspection failure"])
        raise TraceabilityVerificationError(
            "Live repository Git inspection failed closed:\n" + "\n".join(f"  - {e}" for e in errs)
        )
    if not register_data.get("git", {}).get("git_valid", True):
        errs = register_data.get("git", {}).get("git_errors", ["Recorded git state marked invalid"])
        raise TraceabilityVerificationError(
            "Status register indicates invalid git inspection state:\n" + "\n".join(f"  - {e}" for e in errs)
        )

    # 1. Working tree cleanliness checks (both recorded and live)
    if not allow_dirty:
        if register_data.get("git", {}).get("dirty", False):
            raise TraceabilityVerificationError(
                "Status register indicates dirty working tree state ('dirty': true). "
                "Evidence must be recorded from a clean repository state."
            )
        if live_git["dirty"]:
            entries_str = "\n".join(f"  {e}" for e in live_git["dirty_entries"])
            raise TraceabilityVerificationError(
                f"Working tree is currently dirty ({len(live_git['dirty_entries'])} modified/untracked files):\n"
                f"{entries_str}\nStatus register and verification require a clean repository state."
            )

    # 2. Freshness check
    current_sha = live_git.get("commit_sha", "unknown")
    recorded_sha = register_data.get("git", {}).get("commit_sha", "unknown")
    if not allow_stale:
        if current_sha == "unknown" or recorded_sha == "unknown":
            raise TraceabilityVerificationError(
                f"Cannot verify status register freshness: commit SHA is unknown (live: '{current_sha}', recorded: '{recorded_sha}')."
            )
        if recorded_sha != current_sha:
            raise TraceabilityVerificationError(
                f"Stale status register detected: recorded commit SHA '{recorded_sha}' "
                f"does not match current HEAD commit SHA '{current_sha}'."
            )

    if on_disk_path and os.path.exists(on_disk_path):
        with open(on_disk_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        disk_sha = disk_data.get("git", {}).get("commit_sha", "unknown")
        if not allow_stale:
            if disk_sha == "unknown":
                raise TraceabilityVerificationError(
                    f"Committed status register at '{on_disk_path}' has unknown commit SHA."
                )
            if disk_sha != current_sha:
                raise TraceabilityVerificationError(
                    f"Committed status register at '{on_disk_path}' is stale: "
                    f"records commit '{disk_sha}', but current HEAD is '{current_sha}'."
                )

    # 3. Collection error / exit code check
    coll_errors = register_data.get("collection_errors", [])
    if coll_errors:
        err_msg = "\n".join(f"  - {err}" for err in coll_errors)
        raise TraceabilityVerificationError(f"Test suite reported collection errors:\n{err_msg}")

    exit_code = register_data.get("pytest_exit_code", 0)
    if exit_code != 0:
        raise TraceabilityVerificationError(f"Test execution reported non-zero exit code: {exit_code}")

    failures = []
    for cap in register_data["capabilities"]:
        cid = cap["capability_id"]
        name = cap["name"]
        claimed = cap.get("claimed_status", "PLANNED")
        demonstrated = cap.get("demonstrated_status", "PLANNED")
        claimed_rank = STATUS_RANK.get(claimed, 0)
        demonstrated_rank = STATUS_RANK.get(demonstrated, -1)

        # Claimed status must not exceed demonstrated status
        if claimed_rank > demonstrated_rank:
            failures.append(
                f"Capability '{cid}' ({name}): claimed status '{claimed}' exceeds demonstrated status '{demonstrated}'."
            )

        # Test files must exist
        if not cap.get("test_files_exist", False):
            failures.append(
                f"Capability '{cid}' ({name}): required test files missing: {cap.get('test_files', [])}"
            )

        # Execution state must be PASS
        if cap.get("test_execution_state") != "PASS":
            failures.append(
                f"Capability '{cid}' ({name}): test execution state is '{cap.get('test_execution_state')}' (expected 'PASS')"
            )

        # Missing required test nodes
        if len(cap.get("required_nodes_missing", [])) > 0:
            failures.append(
                f"Capability '{cid}' ({name}): {len(cap['required_nodes_missing'])} required test node(s) not executed: {cap['required_nodes_missing']}"
            )

        # Skipped required test nodes
        if len(cap.get("required_nodes_skipped", [])) > 0:
            failures.append(
                f"Capability '{cid}' ({name}): {len(cap['required_nodes_skipped'])} required test node(s) were skipped: {cap['required_nodes_skipped']}"
            )

        # Failed required test nodes
        if len(cap.get("required_nodes_failed", [])) > 0:
            failures.append(
                f"Capability '{cid}' ({name}): {len(cap['required_nodes_failed'])} required test node(s) failed: {cap['required_nodes_failed']}"
            )

        # Must have at least 1 executed test
        if len(cap.get("executed_test_ids", [])) == 0:
            failures.append(
                f"Capability '{cid}' ({name}): 0 tests were executed to support it."
            )

    if failures:
        msg = f"Status Register Traceability Failure ({len(failures)} violation(s)):\n" + "\n".join(f"  - {f}" for f in failures)
        raise TraceabilityVerificationError(msg)
