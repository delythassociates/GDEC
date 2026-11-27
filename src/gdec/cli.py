"""
Command-Line Interface for GDEC.
Commands:
  gdec validate <file.gdc>
  gdec compile <file.gdc> [-o <out.json>]
  gdec run <file.gdc> [--strategy ...]
  gdec benchmark <file.gdc> [--ref-dofs ...] [--out-dir ...]
  gdec hardware
"""

from __future__ import annotations
import argparse
import sys
import json
from pathlib import Path

from gdec.compiler import GDECCompiler
from gdec.core import ExecutionPlanner, GDECRuntime
from gdec.backends import BackendRegistry
from gdec.benchmark import BenchmarkRunner, BenchmarkReporter, BenchmarkMetrics


def cmd_hardware(args):
    print("=" * 60)
    print("GDEC v0.2.2 — Hardware Detection & Execution Backends")
    print("=" * 60)
    hw = BackendRegistry.detect_hardware()
    print(f"Host OS:             {hw['os']}")
    print(f"Python:              {hw['python_version']}")
    print(f"Processor:           {hw['processor']}")
    print(f"Physical CPU Cores:  {hw['cpu_count_physical']}")
    print(f"Logical CPU Cores:   {hw['cpu_count_logical']}")
    print(f"Total System RAM:    {hw['total_ram_gb']} GB")
    print(f"Available RAM:       {hw['available_ram_gb']} GB")
    print("\n[Computational Libraries]")
    for lib, ver in hw["libraries"].items():
        print(f"  {lib:<15}: v{ver}")

    acc = hw["accelerator_hardware"]
    print("\n[Accelerator Hardware]")
    print(f"  GPU Hardware Present:    {acc['gpu_hardware_detected']}")
    print(f"  GPU Device:              {acc['gpu_model']}")
    print(f"  CUDA Backend in v0.2.2:  {acc.get('cuda_backend_implemented', False)}")
    print(f"  Status Note:             {acc['status_note']}")
    print("=" * 60)
    return 0


def cmd_validate(args):
    p = Path(args.file)
    print(f"Validating GDEC source file: {p}...")
    compiler = GDECCompiler()
    res = compiler.compile_file(p)
    if res.success:
        print("[VALIDATION PASSED] Problem specification is syntactically and semantically valid.")
        print(f"  Problem Name: {res.ir.name}")
        print(f"  Physics:      {res.ir.physics}")
        print(f"  Material:     E={res.ir.material.E/1e9:.1f} GPa, nu={res.ir.material.nu}")
        print(f"  Accuracy:     {res.ir.accuracy.percent}%")
        print(f"  Budget:       {res.ir.budget.value:,} DOFs")
        return 0
    else:
        print("[VALIDATION FAILED]")
        for d in res.diagnostics:
            print(d.format())
        return 1


def cmd_compile(args):
    p = Path(args.file)
    compiler = GDECCompiler()
    res = compiler.compile_file(p)
    if not res.success or res.ir is None:
        print("[COMPILATION FAILED]", file=sys.stderr)
        for d in res.diagnostics:
            print(d.format(), file=sys.stderr)
        return 1

    ir_json = res.ir.to_json(indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(ir_json, encoding="utf-8")
        print(f"[COMPILATION SUCCESS] Intermediate Representation written to: {out_path}")
    else:
        print(ir_json)
    return 0


def cmd_run(args):
    p = Path(args.file)
    compiler = GDECCompiler()
    res = compiler.compile_file(p)
    if not res.success or res.ir is None:
        print("[COMPILATION FAILED]", file=sys.stderr)
        for d in res.diagnostics:
            print(d.format(), file=sys.stderr)
        return 1

    planner = ExecutionPlanner()
    plan = planner.create_plan(res.ir, override_strategy=args.strategy)
    print(plan.summary())
    print("\nStarting execution runtime...")
    print("-" * 80)
    print(f"{'Iter':<5} {'DOFs':<8} {'QoI (mm)':<12} {'Change %':<10} {'Marked':<8} {'Time (ms)':<10} {'Status Reason'}")
    print("-" * 80)

    runtime = GDECRuntime(plan, res.ir)

    def iter_cb(rec, mesh, post):
        chg_str = f"{rec.successive_change_pct:.2f}%" if rec.successive_change_pct is not None else "---"
        t_ms = rec.total_iteration_time_sec * 1000.0
        reason_short = rec.action_reason[:30] + "..." if len(rec.action_reason) > 30 else rec.action_reason
        print(f"{rec.iteration:<5} {rec.dofs:<8} {rec.qoi_mm:<12.4f} {chg_str:<10} {rec.elements_marked:<8} {t_ms:<10.1f} {reason_short}")

    trace = runtime.execute(callback=iter_cb)
    print("-" * 80)
    print(f"Execution finished in {trace.total_wall_time_sec:.3f} s.")
    print(f"Final DOFs:       {trace.final_dofs:,}")
    print(f"Stop Reason:      {trace.stop_reason}")

    if trace.evidence_record is not None:
        rec = trace.evidence_record
        out_arg = getattr(args, "output", None)
        if out_arg:
            out_path = Path(out_arg)
        else:
            out_dir = Path("results") / "evidence"
            stem = Path(args.file).stem
            short_hash = rec.canonical_result_hash[:12]
            out_path = out_dir / f"{stem}_{short_hash}.json"
            idx = 1
            while out_path.exists():
                out_path = out_dir / f"{stem}_{short_hash}_{idx}.json"
                idx += 1
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rec.to_canonical_json(), encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: Failed to persist evidence record to {out_path}: {exc}", file=sys.stderr)
            return 1

        def _ev(v) -> str:
            return str(v.value if hasattr(v, "value") else v)

        print(f"Evidence Path:    {out_path}")
        print(f"Record ID:        {rec.record_id}")
        print(f"Schema Version:   {rec.schema_version}")
        print(f"Result Hash:      {rec.canonical_result_hash}")
        print(f"Estimator Class:  {_ev(rec.estimator_classification)}")
        if rec.refused:
            print(f"Refusal Status:   REFUSED ({'; '.join(rec.refusal_reasons)})")
        else:
            print("Refusal Status:   NOT REFUSED (0 refusal rules triggered)")
        print(f"Target Converged: {trace.converged}")
        print(f"Numerical Conv:   {_ev(rec.numerical_convergence_status)}")
        print(f"Model Applicab.:  {_ev(rec.model_applicability_status)}")
        print(f"Verification:     {_ev(rec.verification_status)}")
        print(f"Validation:       {_ev(rec.validation_status)}")
        print(f"Qualification:    {_ev(rec.qualification_status)}")

        qual_val = _ev(rec.qualification_status)
        role_val = _ev(rec.qoi_epistemic_role)
        if rec.refused:
            qoi_str = f"{trace.final_qoi_mm:.5f} mm" if trace.final_qoi_mm is not None else "UNAVAILABLE"
            print(f"Final QoI:        REFUSED ({qoi_str} — {role_val})")
        elif trace.final_qoi_mm is None:
            print("Final QoI:        UNAVAILABLE")
        elif qual_val == "QUALIFIED":
            print(f"Final QoI:        {trace.final_qoi_mm:.5f} mm ({role_val})")
        else:
            print(f"Final QoI:        {trace.final_qoi_mm:.5f} mm (NUMERICAL OBSERVATION — NOT VALIDATED)")
    else:
        print(f"Target Converged: {trace.converged}")
        qoi_str = f"{trace.final_qoi_mm:.5f} mm" if trace.final_qoi_mm is not None else "UNAVAILABLE"
        print(f"Final QoI:        {qoi_str} (UNVALIDATED — NO EVIDENCE RECORD)")
    return 0


def cmd_verify(args):
    from dataclasses import asdict
    from gdec.dse.verifier import verify_evidence_file

    report = verify_evidence_file(args.file)
    if getattr(args, "json", False):
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"Verification Valid: {report.valid}")
        print(f"Record ID:          {report.record_id}")
        print(f"Schema Version:     {report.schema_version}")
        print(f"Refused:            {report.refused}")
        print(f"Qualification:      {report.qualification_status}")
        print(f"Diagnostic Codes:   {', '.join(report.diagnostic_codes)}")
        for d in report.diagnostics:
            print(f"  [{d.code}] {d.message}")
    if not report.valid:
        return 1
    if getattr(args, "require_qualified", False):
        if report.refused or report.qualification_status != "QUALIFIED":
            return 2
    return 0


def cmd_benchmark(args):
    p = Path(args.file)
    compiler = GDECCompiler()
    res = compiler.compile_file(p)
    if not res.success or res.ir is None:
        print("[COMPILATION FAILED]", file=sys.stderr)
        for d in res.diagnostics:
            print(d.format(), file=sys.stderr)
        return 1

    ref_dofs = args.ref_dofs or 30000
    print(f"Running automated benchmark for '{res.ir.name}'...")
    print(f"Target Reference DOFs: {ref_dofs:,}")

    runner = BenchmarkRunner(res.ir, ref_target_dofs=ref_dofs)

    def progress(msg, pct):
        print(f"[{int(pct*100):>3}%] {msg}")

    suite_res = runner.run_all(progress_callback=progress)

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 80)
    summary_df = BenchmarkMetrics.summary_table(suite_res)
    print(summary_df.to_string(index=False))

    out_dir = Path(args.out_dir or "results")
    files = BenchmarkReporter.export_all(suite_res, res.ir, out_dir)
    print("\nExported Artifacts:")
    for k, fpath in files.items():
        print(f"  {k:<20}: {fpath}")

    hyp = suite_res.hypothesis_evaluation
    supp = hyp.get("hypothesis_supported", False)
    print("\nResearch Hypothesis Status:")
    print(f"  Supported: {supp}")
    for r in hyp.get("reasons", []):
        print(f"  - {r}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="gdec",
        description="GDEC — Goal-Driven Engineering Computation CLI (v0.1)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # hardware
    p_hw = subparsers.add_parser("hardware", help="Display host hardware, CPU, and backend info.")
    p_hw.set_defaults(func=cmd_hardware)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a .gdc engineering source file.")
    p_val.add_argument("file", help="Path to .gdc file")
    p_val.set_defaults(func=cmd_validate)

    # compile
    p_comp = subparsers.add_parser("compile", help="Compile .gdc into Typed Intermediate Representation (JSON).")
    p_comp.add_argument("file", help="Path to .gdc file")
    p_comp.add_argument("-o", "--output", help="Optional output JSON path")
    p_comp.set_defaults(func=cmd_compile)

    # run
    p_run = subparsers.add_parser("run", help="Run simulation using specified strategy.")
    p_run.add_argument("file", help="Path to .gdc file")
    p_run.add_argument(
        "--strategy",
        choices=["goal_aware", "dwr", "goal_oriented_dwr", "recovery", "uniform"],
        default=None,
        help="Strategy override",
    )
    p_run.add_argument("-o", "--output", help="Optional output JSON path for EngineeringEvidenceRecord")
    p_run.set_defaults(func=cmd_run)

    # verify
    p_ver = subparsers.add_parser("verify", help="Independently verify an EngineeringEvidenceRecord JSON file.")
    p_ver.add_argument("file", help="Path to evidence result JSON file")
    p_ver.add_argument("--json", action="store_true", help="Output verification report as JSON")
    p_ver.add_argument(
        "--require-qualified",
        action="store_true",
        help="Exit with code 2 if the record is valid but refused or not QUALIFIED",
    )
    p_ver.set_defaults(func=cmd_verify)

    # benchmark
    p_bm = subparsers.add_parser("benchmark", help="Run comparative benchmark of all 3 strategies.")
    p_bm.add_argument("file", help="Path to .gdc file")
    p_bm.add_argument("--ref-dofs", type=int, default=30000, help="Target DOFs for high-resolution reference")
    p_bm.add_argument("--out-dir", default="results", help="Directory for exported reports and CSVs")
    p_bm.set_defaults(func=cmd_benchmark)

    parsed = parser.parse_args()
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main() or 0)
