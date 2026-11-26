#!/usr/bin/env python3
"""
Branch coverage ratcheting gate for GDEC CI.

Reads a pytest-cov JSON report, computes branch coverage, and compares it
against the committed ratcheting floor in research/wp2/coverage-baseline.json.
Fails closed on missing, malformed, or zero-branch coverage data, or if
observed branch coverage falls below the committed baseline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple


class CoverageGateError(RuntimeError):
    """Raised when coverage data is missing, malformed, or violates the floor."""


def evaluate_branch_coverage(coverage_json_path: Path, baseline_json_path: Path) -> Tuple[float, float, int, int]:
    """
    Validate coverage JSON and baseline JSON and check branch coverage >= floor.

    Returns
    -------
    tuple
        (observed_pct, baseline_pct, covered_branches, num_branches)
    """
    if not baseline_json_path.is_file():
        raise CoverageGateError(f"Baseline file not found: {baseline_json_path}")

    try:
        baseline_data = json.loads(baseline_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CoverageGateError(f"Malformed baseline JSON ({baseline_json_path}): {exc}") from exc

    if not isinstance(baseline_data, dict) or "baseline_branch_coverage_pct" not in baseline_data:
        raise CoverageGateError("Baseline JSON missing 'baseline_branch_coverage_pct'")

    try:
        baseline_pct = float(baseline_data["baseline_branch_coverage_pct"])
    except (TypeError, ValueError) as exc:
        raise CoverageGateError(f"Invalid baseline_branch_coverage_pct: {exc}") from exc

    if not (0.0 < baseline_pct <= 100.0):
        raise CoverageGateError(f"Baseline percentage must be in (0, 100], got {baseline_pct}")

    if not coverage_json_path.is_file():
        raise CoverageGateError(f"Coverage JSON report not found: {coverage_json_path}")

    try:
        cov_data = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CoverageGateError(f"Malformed coverage JSON ({coverage_json_path}): {exc}") from exc

    if not isinstance(cov_data, dict) or "totals" not in cov_data or not isinstance(cov_data["totals"], dict):
        raise CoverageGateError("Coverage JSON missing 'totals' object")

    totals = cov_data["totals"]
    if "num_branches" not in totals or "covered_branches" not in totals:
        raise CoverageGateError(
            "Coverage JSON 'totals' missing 'num_branches' or 'covered_branches' (was --cov-branch enabled?)"
        )

    try:
        num_branches = int(totals["num_branches"])
        covered_branches = int(totals["covered_branches"])
    except (TypeError, ValueError) as exc:
        raise CoverageGateError(f"Invalid branch counts in coverage JSON: {exc}") from exc

    if num_branches <= 0:
        raise CoverageGateError(f"Zero-branch or negative coverage data rejected (num_branches={num_branches})")
    if covered_branches < 0 or covered_branches > num_branches:
        raise CoverageGateError(
            f"Invalid covered_branches={covered_branches} for num_branches={num_branches}"
        )

    observed_pct = (covered_branches / num_branches) * 100.0
    if observed_pct < baseline_pct:
        raise CoverageGateError(
            f"Branch coverage regression: observed {observed_pct:.2f}% "
            f"({covered_branches}/{num_branches} branches) < baseline floor {baseline_pct:.2f}%"
        )

    return observed_pct, baseline_pct, covered_branches, num_branches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce GDEC branch coverage ratcheting floor.")
    parser.add_argument("--coverage-json", required=True, help="Path to pytest-cov JSON report")
    parser.add_argument(
        "--baseline",
        default="research/wp2/coverage-baseline.json",
        help="Path to committed branch coverage baseline JSON",
    )
    args = parser.parse_args(argv)

    try:
        observed_pct, baseline_pct, covered, total = evaluate_branch_coverage(
            Path(args.coverage_json), Path(args.baseline)
        )
    except CoverageGateError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print(
        f"[PASS] Branch coverage: {observed_pct:.2f}% ({covered}/{total} branches) "
        f">= baseline floor {baseline_pct:.2f}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
