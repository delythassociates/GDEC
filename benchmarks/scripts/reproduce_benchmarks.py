"""
Portable benchmark reproduction script for GDEC v0.2.2.
Executes the standard 3-way comparative benchmark and outputs summary tables.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gdec.compiler import GDECCompiler
from gdec.benchmark.runner import BenchmarkRunner
from gdec.benchmark.metrics import BenchmarkMetrics
from gdec.benchmark.reporting import BenchmarkReporter

def main():
    source_path = ROOT / "examples" / "cantilever.gdc"
    out_dir = ROOT / "results" / "reproduced"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading benchmark source: {source_path}")
    compiler = GDECCompiler()
    res = compiler.compile_file(source_path)
    if not res.success or res.ir is None:
        print("Compilation failed!")
        sys.exit(1)

    print(f"Running comparative benchmark for: {res.ir.name}")
    runner = BenchmarkRunner(res.ir, ref_target_dofs=30000)
    suite_res = runner.run_all(progress_callback=lambda msg, p: print(f"[{int(p*100):>3}%] {msg}"))

    summary = BenchmarkMetrics.summary_table(suite_res)
    print("\n" + "=" * 80)
    print("REPRODUCED BENCHMARK SUMMARY")
    print("=" * 80)
    print(summary.to_string(index=False))

    files = BenchmarkReporter.export_all(suite_res, res.ir, out_dir)
    print(f"\nArtifacts exported to: {out_dir}")
    for k, v in files.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
