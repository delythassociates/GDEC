# GDEC Phase 5.1.3 — Risk Register

**Repository:** `delythassociates/GDEC`  
**Development Branch:** `research/phase-5.1.3-validation-and-ci-closure`  
**Required Parent Commit:** `33aed0202aa5f4c359c9df3cb8d28e3a7753f475`

---

## Risk Analysis & Mitigation Matrix

| Risk ID | Category | Risk Description | Pre-Mitigation Severity / Likelihood | Remediation / Mitigation Action Taken | Residual Risk | Monitoring Strategy |
|---|---|---|---|---|---|---|
| **RSK-513-01** | Decision Safety | **Ineligible DWR Metric Hijacking**: Unassessed, expired, or model-mismatched records supplying discretization quality metrics. | **CRITICAL / HIGH** | Enforced record-level binding in `SingleQoIEvaluator`: only records with `is_acceptable == True` in `DWR_CATEGORIES` can supply metrics. | **LOW** | 15 adversarial tests in `test_phase5_1_3_dse_adversarial.py`. |
| **RSK-513-02** | Decision Safety | **Conflicting Metrics Silent Pass**: Conflicting DWR error estimates between different valid studies causing silent decision release. | **HIGH / MEDIUM** | Implemented deterministic refusal: if multiple eligible records supply differing numerical values, evaluator fails closed with `INSUFFICIENT_EVIDENCE`. | **VERY LOW** | Automated test `test_05_conflicting_dwr_values_refusal`. |
| **RSK-513-03** | Semantic Safety | **Unit Incompatibility in Error Indicators**: Comparing stress units (MPa) against displacement thresholds (mm). | **HIGH / MEDIUM** | Strict unit verification: if record specifies `units`, it must match `contract.qoi.unit` exactly. | **VERY LOW** | Automated test `test_06_incorrect_units_refusal`. |
| **RSK-513-04** | Semantic Safety | **Reference Scale Missing or Zero**: Silently defaulting to limit when reference scale is omitted, distorting relative error. | **HIGH / MEDIUM** | Reference scale must be non-null and $> 10^{-12}$ in `EvidenceAssessment`. Missing/near-zero scale fails closed. | **LOW** | Automated tests `test_07_missing_reference_scale_refusal`, `test_08_near_zero_reference_scale_refusal`. |
| **RSK-513-05** | Numerical Mechanics | **Conflating Reaction Forces with Solver Residual**: Evaluating $\|f - K u\|_2$ over all DOFs instead of free DOFs. | **HIGH / HIGH** | Partitioned system into free ($I$) and constrained ($D$) DOFs; evaluated $\|\mathbf{f}_I - K_{II} \mathbf{u}_I\|_2 / \|\mathbf{f}_I\|_2 = 2.38 \times 10^{-11}$. Evaluated wall reactions separately. | **VERY LOW** | Automated check in `test_independent_fem_validation.py` and benchmark script. |
| **RSK-513-06** | Configuration | **Benchmark Documentation Discrepancy**: Benchmark script using $5.0 \times 1.0\text{ mm}$ while documentation reported $2.0 \times 0.5\text{ m}$. | **MEDIUM / HIGH** | Reconciled all documentation, script, test fixture, and CSV outputs to the authoritative $5.0 \times 1.0\text{ mm}$ specification. | **VERY LOW** | All artifacts audited and cross-checked against regenerated CSV observations. |
| **RSK-513-07** | DevOps / CI | **CI Trigger Blind Spot on Research Branches**: Pushes to `research/**` not triggering GitHub Actions workflows. | **HIGH / HIGH** | Updated `.github/workflows/ci.yml` push branches to include `"research/**"`. | **LOW** | Live GitHub Actions workflow run verification and documentation. |
