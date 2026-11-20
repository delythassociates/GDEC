"""
Benchmark metrics aggregation and comparison analysis for GDEC.
"""

from __future__ import annotations
from typing import Dict, List
import pandas as pd
import numpy as np

from gdec.benchmark.runner import BenchmarkSuiteResult


class BenchmarkMetrics:
    @staticmethod
    def to_dataframe(suite_res: BenchmarkSuiteResult) -> pd.DataFrame:
        """Convert all iterations across strategies to a flat pandas DataFrame."""
        rows = []
        for strat, strat_res in suite_res.strategies.items():
            for it in strat_res.iterations:
                rows.append({
                    "Strategy": strat,
                    "Iteration": it.iteration,
                    "DOFs": it.dofs,
                    "Elements": it.nelements,
                    "Nodes": it.nnodes,
                    "QoI (m)": it.qoi_meters,
                    "QoI (mm)": it.qoi_mm,
                    "Ref Error (%)": it.reference_error_pct,
                    "Successive Change (%)": it.successive_change_pct,
                    "Marked Elements": it.elements_marked,
                    "Assembly Time (s)": it.assembly_time_sec,
                    "Solver Time (s)": it.solver_time_sec,
                    "Iter Time (s)": it.total_time_sec,
                    "Cumulative Time (s)": it.cumulative_time_sec,
                    "Peak RAM (MB)": it.peak_memory_mb,
                    "Action / Status": it.action_reason,
                })
        return pd.DataFrame(rows)

    @staticmethod
    def summary_table(suite_res: BenchmarkSuiteResult) -> pd.DataFrame:
        """Generate high-level comparison table between strategies."""
        ref = suite_res.reference
        rows = []
        for strat, s_res in suite_res.strategies.items():
            last_it = s_res.iterations[-1] if s_res.iterations else None
            rows.append({
                "Strategy": strat.replace("_", " ").title(),
                "Target Achieved": "YES" if s_res.target_achieved else "NO",
                "Final DOFs": s_res.final_dofs,
                "Final QoI (mm)": last_it.qoi_mm if last_it else 0.0,
                "Ref Error (%)": s_res.final_reference_error_pct,
                "Total Wall Time (s)": s_res.total_execution_time_sec,
                "Iterations": len(s_res.iterations),
            })
        df = pd.DataFrame(rows)
        return df
