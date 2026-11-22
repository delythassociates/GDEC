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
from typing import Any, Dict, List, Optional


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
        notes="LALR grammar in grammar.lark. Duplicate named arguments rejected.",
    ),
    CapabilityEntry(
        capability_id="compiler_strict_declarations",
        name="Strict Top-Level Declarations",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py"],
        notes="Only known declarations accepted; unknown statements trigger source-located syntax errors.",
    ),
    CapabilityEntry(
        capability_id="compiler_singleton_enforcement",
        name="Singleton Declaration Enforcement",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py"],
        notes="Top-level blocks rejected if duplicated.",
    ),
    CapabilityEntry(
        capability_id="compiler_scalar_validation",
        name="Scalar & Type Validation",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py"],
        notes="Rejects NaN, inf, overflow, boolean-as-float, fractional budget.",
    ),
    CapabilityEntry(
        capability_id="compiler_material_bounds",
        name="Material Constant Bounds",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_compiler_validation.py",
        test_files=["tests/test_compiler_validation.py", "tests/test_language.py"],
        notes="Enforces E > 0 and -1.0 < nu < 0.5.",
    ),
    CapabilityEntry(
        capability_id="compiler_typed_problem_ir",
        name="Typed ProblemIR Contract",
        subsystem="compiler",
        claimed_status="TESTED",
        evidence_path="tests/test_ir.py",
        test_files=["tests/test_ir.py", "tests/test_compiler_validation.py"],
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
        notes="Constant-strain patch test on distorted mesh passes with error < 1e-11 m.",
    ),
    CapabilityEntry(
        capability_id="fem_stiffness_assembly_nullspace",
        name="Bilinear Stiffness Assembly Nullspace",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Unconstrained stiffness matrix has exactly 3 rigid-body null modes.",
    ),
    CapabilityEntry(
        capability_id="fem_dirichlet_condensation",
        name="Dirichlet Elimination (Condensation)",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Correct partition and elimination via boundary condensation.",
    ),
    CapabilityEntry(
        capability_id="fem_traction_boundary_assembly",
        name="Traction Boundary Assembly & Force Balance",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Total force balances to machine precision; reaction equals load.",
    ),
    CapabilityEntry(
        capability_id="fem_global_equilibrium_conservation",
        name="Global Equilibrium Conservation",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Linear force balance < 1e-7 N; scale-aware moment balance < 1e-9 relative.",
    ),
    CapabilityEntry(
        capability_id="fem_analytical_beam_convergence",
        name="Analytical Timoshenko Beam Convergence",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Tip deflection converges monotonically from below; within 1.29% on fine mesh.",
    ),
    CapabilityEntry(
        capability_id="fem_manufactured_pure_bending",
        name="Manufactured Pure Bending Solution",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Exact quadratic bending field reproduced to < 1e-11 m.",
    ),
    CapabilityEntry(
        capability_id="fem_energy_monotonicity",
        name="Rayleigh-Ritz Energy Monotonicity",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="Strain energy strictly increases monotonically under conforming uniform refinement.",
    ),
    CapabilityEntry(
        capability_id="fem_plane_strain_out_of_plane_stress",
        name="Plane Strain Out-of-Plane Stress",
        subsystem="fem",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_fem_mathematical_verification.py",
        test_files=["tests/test_fem_mathematical_verification.py"],
        notes="sigma_zz = nu*(sigma_xx + sigma_yy) accurately included in 3D von Mises invariant.",
    ),
    CapabilityEntry(
        capability_id="fem_primal_adjoint_factorization_reuse",
        name="Primal-Adjoint Factorization Reuse",
        subsystem="fem",
        claimed_status="TESTED",
        evidence_path="tests/test_v02_profiling_and_reuse.py",
        test_files=["tests/test_elasticity.py", "tests/test_v02_profiling_and_reuse.py"],
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
        notes="Ainsworth-Oden residual indicator based on interior facet traction jumps.",
    ),
    CapabilityEntry(
        capability_id="estimator_goal_oriented_dwr",
        name="Goal-Oriented DWR Estimator",
        subsystem="estimator",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dwr_verification.py",
        test_files=["tests/test_dwr_verification.py"],
        notes="Dual-weighted residual estimator with interior jumps, bubble recovery, effectivity convergence (0.51 -> 0.91).",
    ),
    CapabilityEntry(
        capability_id="estimator_amr_marking_cycle",
        name="Adaptive Refinement Marking Cycle",
        subsystem="estimator",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dwr_verification.py",
        test_files=["tests/test_dwr_verification.py", "tests/test_estimators.py"],
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
        notes="Scale-invariant condition number and symmetry metric across 1e-14 <= c <= 1e14.",
    ),
    CapabilityEntry(
        capability_id="solver_cg_direct_residual_recalculation",
        name="CG Direct Residual Recalculation",
        subsystem="solver",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_iterative_solvers.py",
        test_files=["tests/test_iterative_solvers.py"],
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
        notes="Analytical scaling agrees with independent scikit-fem elasticity within machine precision.",
    ),
    CapabilityEntry(
        capability_id="dse_single_qoi_evaluator",
        name="Single-QoI Decision Sufficiency Evaluator",
        subsystem="dse",
        claimed_status="NUMERICALLY VERIFIED",
        evidence_path="tests/test_dse.py",
        test_files=["tests/test_dse.py"],
        notes="Strict Bayesian loss evaluation, refusing when evidence is absent or insufficient.",
    ),
    CapabilityEntry(
        capability_id="eir_canonical_hash_determinism",
        name="Canonical EIR Hash Determinism",
        subsystem="eir",
        claimed_status="TESTED",
        evidence_path="tests/eir/test_adversarial_hardening.py",
        test_files=["tests/eir/test_adversarial_hardening.py"],
        notes="SHA-256 hash invariant across dict order, line endings, and equivalent units.",
    ),
]


class PytestCollector:
    """In-process pytest plugin to capture executed test nodeids and outcomes."""
    def __init__(self):
        self.results: Dict[str, str] = {}  # nodeid -> "PASS" | "FAIL" | "SKIP"

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.results[report.nodeid] = "PASS"
            elif report.failed:
                self.results[report.nodeid] = "FAIL"
            else:
                self.results[report.nodeid] = "SKIP"


def collect_live_test_results(test_files: Optional[List[str]] = None) -> Dict[str, str]:
    """Execute pytest on target files and collect live outcomes for every individual test."""
    import pytest
    collector = PytestCollector()
    args = test_files if test_files else ["tests/"]
    pytest.main(args + ["-q"], plugins=[collector])
    return collector.results


def get_git_info() -> Dict[str, Any]:
    """Retrieve current commit SHA, branch name, and dirty working tree status safely."""
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        sha = "unknown"
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    except Exception:
        branch = "unknown"
    try:
        raw_status = subprocess.check_output(["git", "status", "--porcelain", "-uno"], text=True).splitlines()
        # Ignore self-modifications to results/status_register.json during generation
        tracked_changes = [l for l in raw_status if not l.strip().endswith("results/status_register.json")]
        is_dirty = len(tracked_changes) > 0
    except Exception:
        is_dirty = False
    return {"commit_sha": sha, "branch": branch, "dirty": is_dirty}


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
) -> Dict[str, Any]:
    """
    Generate machine-readable status_register.json with commit, environment,
    capabilities, and verified test states backed by actual pytest execution.
    """
    git_info = get_git_info()
    env_info = get_environment_info()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Collect live test execution results across test files if requested
    if test_results is None and run_tests:
        all_test_files = sorted(list(set(tf for cap in SYSTEM_CAPABILITIES for tf in cap.test_files if os.path.exists(tf))))
        live_test_results = collect_live_test_results(all_test_files)
    else:
        live_test_results = test_results or {}

    capabilities_data = []
    for cap in SYSTEM_CAPABILITIES:
        all_tests_exist = all(os.path.exists(tf) for tf in cap.test_files)

        # Match executed tests for this capability
        matching_executed_tests: Dict[str, str] = {}
        for nodeid, status in live_test_results.items():
            # Check if this nodeid belongs to any of cap.test_files
            normalized_nodeid = nodeid.replace("\\", "/")
            if any(tf.replace("\\", "/") in normalized_nodeid for tf in cap.test_files):
                matching_executed_tests[nodeid] = status

        executed_test_ids = list(matching_executed_tests.keys())

        # Determine execution state based strictly on real execution evidence
        if not all_tests_exist or len(matching_executed_tests) == 0:
            execution_state = "NOT_RUN"
        elif any(st == "FAIL" for st in matching_executed_tests.values()):
            execution_state = "FAIL"
        elif all(st == "PASS" for st in matching_executed_tests.values()):
            execution_state = "PASS"
        else:
            execution_state = "NOT_RUN"

        cap_dict = asdict(cap)
        cap_dict["test_files_exist"] = all_tests_exist
        cap_dict["executed_test_ids"] = executed_test_ids
        cap_dict["test_execution_state"] = execution_state
        capabilities_data.append(cap_dict)

    register_data = {
        "schema_version": "1.0.0",
        "generated_at": now_iso,
        "git": git_info,
        "environment": env_info,
        "total_capabilities": len(capabilities_data),
        "status_summary": {
            "NUMERICALLY VERIFIED": sum(1 for c in capabilities_data if c["claimed_status"] == "NUMERICALLY VERIFIED"),
            "TESTED": sum(1 for c in capabilities_data if c["claimed_status"] == "TESTED"),
            "IMPLEMENTED": sum(1 for c in capabilities_data if c["claimed_status"] == "IMPLEMENTED"),
            "PLANNED": sum(1 for c in capabilities_data if c["claimed_status"] == "PLANNED"),
        },
        "capabilities": capabilities_data,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(register_data, f, indent=2)

    return register_data


def verify_traceability(
    register_data: Dict[str, Any],
    on_disk_path: Optional[str] = None,
    allow_dirty: bool = False,
    allow_stale: bool = False,
) -> None:
    """
    Strict traceability gate:
    1. Detects stale status register by comparing recorded commit SHA against current HEAD.
    2. Enforces that working tree is not dirty.
    3. Fails if any capability claimed as 'NUMERICALLY VERIFIED' lacks passing tests
       or has test_execution_state != 'PASS'.
    """
    git_info = get_git_info()
    current_sha = git_info.get("commit_sha", "unknown")
    recorded_sha = register_data.get("git", {}).get("commit_sha", "unknown")

    # Detect stale status register
    if not allow_stale and recorded_sha != "unknown" and current_sha != "unknown" and recorded_sha != current_sha:
        # Allow if recorded_sha is a valid ancestor whose only changes to current_sha are status register or metadata/docs
        try:
            diff_files = subprocess.check_output(
                ["git", "diff", "--name-only", recorded_sha, current_sha],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip().splitlines()
            non_meta_diff = [
                f for f in diff_files
                if not f.startswith("results/status_register.json")
                and not f.startswith("research/")
                and not f.endswith(".md")
            ]
            if non_meta_diff:
                raise TraceabilityVerificationError(
                    f"Stale status register detected: recorded commit SHA '{recorded_sha}' "
                    f"does not match current HEAD commit SHA '{current_sha}' (modified code/tests: {non_meta_diff})."
                )
        except Exception as e:
            if isinstance(e, TraceabilityVerificationError):
                raise
            raise TraceabilityVerificationError(
                f"Stale status register detected: recorded commit SHA '{recorded_sha}' "
                f"does not match current HEAD commit SHA '{current_sha}'."
            )

    # Detect dirty state
    if not allow_dirty and register_data.get("git", {}).get("dirty", False):
        raise TraceabilityVerificationError(
            "Status register indicates a dirty working tree. "
            "Verification and status register must be generated on a clean commit."
        )

    # If on-disk path provided, verify file consistency
    if on_disk_path and os.path.exists(on_disk_path):
        with open(on_disk_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        disk_sha = disk_data.get("git", {}).get("commit_sha", "unknown")
        if not allow_stale and disk_sha != current_sha and disk_sha != "unknown" and current_sha != "unknown":
            try:
                diff_files = subprocess.check_output(
                    ["git", "diff", "--name-only", disk_sha, current_sha],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip().splitlines()
                non_meta_diff = [
                    f for f in diff_files
                    if not f.startswith("results/status_register.json")
                    and not f.startswith("research/")
                    and not f.endswith(".md")
                ]
                if non_meta_diff:
                    raise TraceabilityVerificationError(
                        f"Committed status register at '{on_disk_path}' is stale: "
                        f"records commit '{disk_sha}', but current HEAD is '{current_sha}' (modified code/tests: {non_meta_diff})."
                    )
            except Exception as e:
                if isinstance(e, TraceabilityVerificationError):
                    raise
                raise TraceabilityVerificationError(
                    f"Committed status register at '{on_disk_path}' is stale: "
                    f"records commit '{disk_sha}', but current HEAD is '{current_sha}'."
                )

    failures = []
    for cap in register_data["capabilities"]:
        if cap["claimed_status"] == "NUMERICALLY VERIFIED":
            if not cap.get("test_files_exist", False):
                failures.append(
                    f"Capability '{cap['capability_id']}' ({cap['name']}) is claimed as NUMERICALLY VERIFIED "
                    f"but test files are missing: {cap['test_files']}"
                )
            elif cap.get("test_execution_state") != "PASS":
                failures.append(
                    f"Capability '{cap['capability_id']}' ({cap['name']}) is claimed as NUMERICALLY VERIFIED "
                    f"but test state is '{cap.get('test_execution_state')}' (expected 'PASS')"
                )
            elif len(cap.get("executed_test_ids", [])) == 0:
                failures.append(
                    f"Capability '{cap['capability_id']}' ({cap['name']}) is claimed as NUMERICALLY VERIFIED "
                    f"but 0 tests were executed to support it."
                )

    if failures:
        msg = f"Status Register Traceability Failure ({len(failures)} violation(s)):\n" + "\n".join(f"  - {f}" for f in failures)
        raise TraceabilityVerificationError(msg)
