# GDEC WP2 Final Remediation Follow-up — Risk Register

| Risk ID | Description | Severity | Likelihood | Impact on GDEC | Mitigation Strategy | Status |
|---|---|---|---|---|---|---|
| `RISK-WP2-F01` | Self-referential commit SHA in committed status register file | High | High | Chicken-and-egg git SHA mismatch causes CI or pre-commit checks to fail | Untrack `results/status_register.json` from git; capability schema kept in version control; status registers generated as authoritative CI artifacts per run. | **MITIGATED** |
| `RISK-WP2-F02` | CI shallow git checkout fails commit provenance comparisons | High | High | CI fails with `bad object` or false stale detection | Configured `fetch-depth: 0` for all `actions/checkout@v4` steps in `.github/workflows/ci.yml`. | **MITIGATED** |
| `RISK-WP2-F03` | Tests mutating working directory and creating dirty repo state | Medium | High | Working tree dirty check fails after test runs | All tests use `tmp_path` exclusively; added automated post-test clean tree check in CI. | **MITIGATED** |
| `RISK-WP2-F04` | Accidental overwriting or staging of untracked user files (`analyser.py`, `runtime/`) | Critical | Low | Loss of proprietary user-developed runtime code | Preserved user paths explicitly whitelisted in git status cleanliness check and git preflight. | **ACTIVE MONITORING** |
| `RISK-WP2-F05` | `mutmut` native Windows platform incompatibility | Low | High | Mutation testing fails to run on Windows development machines | Documented WSL/Linux requirement for mutmut; authored cross-platform source mutation runner `scripts/run_mutation_campaign.py`. | **MITIGATED** |
| `RISK-WP2-F06` | Overclaiming capability status without numerical evidence | High | Medium | Downstream engineering decisions rely on unverified claims | Implemented strictly computed `demonstrated_status`; gate rejects claims exceeding demonstrated status or containing skipped tests. | **MITIGATED** |
