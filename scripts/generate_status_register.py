#!/usr/bin/env python3
"""
CLI script to generate results/status_register.json and enforce CI traceability.
Usage:
    python scripts/generate_status_register.py [--check] [--output <path>] [--skip-tests]
"""
import argparse
import json
import os
import sys

# Add src to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gdec.verification.status_register import (
    generate_status_register,
    verify_traceability,
    TraceabilityVerificationError,
    get_git_info,
)


def main():
    parser = argparse.ArgumentParser(description="Generate and verify GDEC machine-readable status register.")
    parser.add_argument("--check", action="store_true", help="Fail with non-zero exit code if traceability checks fail or file is stale.")
    parser.add_argument("--output", default="results/status_register.json", help="Path to output JSON file.")
    parser.add_argument("--input", default=None, help="Path to input JSON file for --check (defaults to --output if omitted).")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running pytest during generation (for dry runs only).")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow dirty working tree (for local testing only; forbidden in CI).")
    parser.add_argument("--allow-stale", action="store_true", help="Allow stale commit SHA (for local testing only; forbidden in CI).")
    args = parser.parse_args()

    target_file = args.input if args.input is not None else args.output

    if args.check:
        print(f"Checking GDEC Status Register -> {target_file}")
        if not os.path.exists(target_file):
            print(f"[FAIL] Status register file does not exist at {target_file}", file=sys.stderr)
            sys.exit(1)

        with open(target_file, "r", encoding="utf-8") as f:
            register = json.load(f)

        try:
            verify_traceability(
                register,
                on_disk_path=target_file,
                allow_dirty=args.allow_dirty,
                allow_stale=args.allow_stale,
            )
            print("[PASS] Status register is fresh, clean, and all NUMERICALLY VERIFIED capabilities are backed by passing tests.")
        except TraceabilityVerificationError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Generating GDEC Status Register -> {args.output}")
        run_tests = not args.skip_tests
        register = generate_status_register(output_path=args.output, run_tests=run_tests)
        print(f"Generated status register with {register['total_capabilities']} capabilities.")
        print("Summary:")
        for status, count in register["status_summary"].items():
            print(f"  {status}: {count}")
        print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
