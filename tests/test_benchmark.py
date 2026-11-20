"""
Tests for Benchmark Suite runner, reference solver, and reporting.
"""

from pathlib import Path
from gdec.compiler import GDECCompiler
from gdec.benchmark import BenchmarkRunner, BenchmarkReporter, BenchmarkMetrics


def test_benchmark_suite_execution(tmp_path):
    compiler = GDECCompiler()
    res = compiler.compile_file("examples/cantilever.gdc")
    assert res.success is True

    runner = BenchmarkRunner(res.ir, ref_target_dofs=10000)
    suite_res = runner.run_all()

    assert suite_res.reference.dofs > 0
    assert "uniform" in suite_res.strategies
    assert "recovery" in suite_res.strategies
    assert "goal_aware" in suite_res.strategies

    # Check metrics conversion
    df = BenchmarkMetrics.to_dataframe(suite_res)
    assert len(df) > 0
    sum_df = BenchmarkMetrics.summary_table(suite_res)
    assert len(sum_df) == 3

    # Check export
    files = BenchmarkReporter.export_all(suite_res, res.ir, tmp_path)
    assert files["markdown_report"].exists()
    assert files["iterations_csv"].exists()
    assert files["summary_csv"].exists()
    assert files["json_summary"].exists()
