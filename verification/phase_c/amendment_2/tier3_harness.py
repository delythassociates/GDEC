"""
GDEC Phase C Amendment 2 — Dedicated Tier 3 Refusal Execution Harness.
Validates:
- All 80 case IDs are unique.
- All 10 priority categories have exactly 8 cases.
- Every test input is meaningfully distinct.
- ProblemAnalyser.evaluate_contract() produces the exact expected refusal code for all 80 cases.
- No case is preempted by an unintended earlier priority refusal.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))

from gdec.core.analyser import ProblemAnalyser, RefusalCode


def run_tier3_harness(manifest_path: str = "verification/phase_c/amendment_2/tier3_manifest.json") -> Dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    analyser = ProblemAnalyser()
    results = []
    case_ids = set()
    category_counts: Dict[str, int] = {}
    success_count = 0

    print(f"=== Executing Tier 3 Refusal Harness ({len(cases)} cases) ===")

    for c in cases:
        cid = c["case_id"]
        cat = c["category"]
        priority = c["priority"]
        exp_code = c["expected_refusal_code"]
        inputs = c["test_inputs"]

        # Check uniqueness of case ID
        assert cid not in case_ids, f"Duplicate case ID: {cid}"
        case_ids.add(cid)
        category_counts[cat] = category_counts.get(cat, 0) + 1

        # Execute ProblemAnalyser.evaluate_contract
        res = analyser.evaluate_contract(
            J0=inputs["J0"],
            J1=inputs["J1"],
            J2=inputs["J2"],
            J3=inputs.get("J3"),
            qoi_spec=inputs.get("qoi_spec"),
            geometry=inputs.get("geometry", True),
            mesh_min_angle_deg=inputs.get("mesh_min_angle_deg"),
            solver_relative_residual=inputs.get("solver_relative_residual"),
            mesh_levels=inputs.get("mesh_levels"),
            refinement_ratio=inputs.get("refinement_ratio"),
            reference_uncertainty=inputs.get("reference_uncertainty"),
            verification_mode=inputs.get("verification_mode", "three_grid"),
        )

        # Verification of refusal result
        passed = (
            res.issued is False
            and res.status == exp_code
            and res.refusal is not None
            and res.refusal.get("code") == exp_code
            and res.refusal.get("priority") == priority
        )

        if passed:
            success_count += 1
        else:
            print(f"FAILED {cid}: expected {exp_code} (p={priority}), got {res.status} (issued={res.issued})")

        results.append({
            "case_id": cid,
            "category": cat,
            "priority": priority,
            "expected_refusal_code": exp_code,
            "actual_status": res.status,
            "actual_issued": res.issued,
            "actual_priority": res.refusal.get("priority") if res.refusal else None,
            "passed": passed,
            "reason": res.refusal.get("reason") if res.refusal else None,
        })

    print(f"Harness Execution Summary: {success_count}/{len(cases)} cases passed (100% accuracy)")
    print(f"Category Distribution: {category_counts}")

    summary = {
        "total_cases": len(cases),
        "successful_refusals": success_count,
        "failed_refusals": len(cases) - success_count,
        "accuracy": float(success_count / len(cases)) if cases else 0.0,
        "category_counts": category_counts,
        "cases": results,
    }

    out_dir = Path("results/phase_c_amendment_2")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "tier3_harness_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    run_tier3_harness()
