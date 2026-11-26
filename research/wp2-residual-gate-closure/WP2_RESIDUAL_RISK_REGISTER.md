# WP2 Residual Acceptance-Gate Closure — Risk Register

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Status |
|---|---|---|---|---|---|
| **RISK-WP2-R01** | Non-GPU CI runners skip 14 CUDA tests, lowering `cuda.py` branch coverage vs local GPU | Low | High | Baseline in `research/wp2/coverage-baseline.json` is anchored to the locked CPU-only CI environment (`62.28%`); local GPU runs achieve `65.08%` | Managed |
| **RISK-WP2-R02** | Untracked local user files (`analyser.py`, `runtime/`) distort local coverage | Medium | High | Explicitly omitted in `[tool.coverage.run]` so local and CI denominators match | Closed |
| **RISK-WP2-R03** | Targeted runtime mutation campaign does not cover all branches in the repository | Medium | Medium | Denominator (20 mutants across 8 core modules) is explicitly disclosed; whole-repo AST mutation (`mutmut`) remains deferred due to Windows compatibility | Managed |
| **RISK-WP2-R04** | ADR-013 verbatim Session 2 owner text is not embedded in git history | Low | Low | Reconciled stale heading/consequence to match recorded WP0 confirmation without fabricating quotes; flagged for owner awareness | Managed |
