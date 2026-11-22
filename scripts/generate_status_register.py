#!/usr/bin/env python3
"""
CLI script to generate results/status_register.json and enforce CI traceability.
Usage:
    python scripts/generate_status_register.py [--check] [--output <path>]
"""
import argparse
import sys
import os

# Add src to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gdec.verification.status_register import (
    generate_status_register,
    verify_traceability,
    TraceabilityVerificationError,
)


def main():
    parser = argparse.ArgumentParser(description="Generate and verify GDEC machine-readable status register.")
    parser.add_argument("--check", action="store_true", help="Fail with non-zero exit code if traceability checks fail.")
    parser.add_argument("--output", default="results/status_register.json", help="Path to output JSON file.")
    args = parser.parse_args()

    print(f"Generating GDEC Status Register -> {args.output}")
    register = generate_status_register(output_path=args.output)
    print(f"Generated status register with {register['total_capabilities']} capabilities.")
    print("Summary:")
    for status, count in register["status_summary"].items():
        print(f"  {status}: {count}")

    if args.check:
        print("\nEnforcing strict traceability for NUMERICALLY VERIFIED capabilities...")
        try:
            verify_traceability(register)
            print("[PASS] All NUMERICALLY VERIFIED capabilities are backed by passing tests.")
        except TraceabilityVerificationError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
