"""
Tests for Equal-Accuracy Benchmark Evaluator (v0.2).
"""

from gdec.compiler import GDECCompiler
from gdec.benchmark.runner import BenchmarkRunner
from gdec.benchmark.evaluator import EqualAccuracyEvaluator


def test_equal_accuracy_evaluation():
    comp = GDECCompiler().compile_file("examples/cantilever.gdc")
    assert comp.success is True

    runner = BenchmarkRunner(comp.ir, ref_target_dofs=10000)
    suite_res = runner.run_all()

    assert suite_res.equal_accuracy_comparisons is not None
    assert len(suite_res.equal_accuracy_comparisons) == 4

    # Test conversion to dataframe
    df = EqualAccuracyEvaluator.comparisons_to_dataframe(suite_res.equal_accuracy_comparisons)
    assert len(df) == 12  # 4 thresholds * 3 strategies
    assert "Target Error" in df.columns
    assert "Strategy" in df.columns
    assert "Target Achieved" in df.columns
    assert "DOFs Required" in df.columns
