# Work Package 0 (WP0) Changelog

**Document Identifier:** `GDEC-WP0-CHANGELOG`  
**Branch:** `research/wp0-repo-integrity`  
**Date:** 2026-11-22  

---

## Changes Implemented

### Added
- `CHANGELOG.md`: Root project changelog adhering to Keep-a-Changelog and SemVer 2.0.0.
- `CITATION.cff`: Citation File Format for academic citation and reproducibility attribution.
- `SECURITY.md`: Vulnerability disclosure process and computational safety boundaries.
- `CONTRIBUTING.md`: Development standards, branch conventions, and testing protocols.
- `CODE_OF_CONDUCT.md`: Community integrity and professional engineering standards.
- `.github/ISSUE_TEMPLATE/bug_report.md`: Structured defect report template.
- `.github/ISSUE_TEMPLATE/feature_request.md`: Structured capability proposal template.
- `.github/PULL_REQUEST_TEMPLATE.md`: PR verification checklist template.
- `docs/VERSION_POLICY.md`: Platform SemVer rules, schema decoupling, and migration policies.
- `research/wp0/WP0_MASTER_REPORT.md`: WP0 completion report and root inventory justification.
- `research/wp0/WP0_ACCEPTANCE_MATRIX.md`: Verification evidence for Gates 1-4.
- `research/wp0/WP0_MERGE_PLAN.md`: 10-PR ordered integration sequence into `main`.
- `research/wp0/WP0_CHANGELOG.md`: WP0 change manifest.
- `research/wp0/WP0_RISK_REGISTER.md`: Residual risk tracking for WP0.

### Relocated
- `REPOSITORY_AUDIT_PREPARATION.md` -> `docs/archive/v022/REPOSITORY_AUDIT_PREPARATION.md`
- `scratch/` (6 temporary test scripts) -> `docs/archive/scratch/`

### Removed
- `GDEC_v0.2.2_PRIVATE_REVIEW.zip` (294 KB binary zip removed from working tree via `git rm`).
- `materials-simulation-skills-main.zip` (974 KB binary zip removed from working tree via `git rm`).

### Modified
- `README.md`: Complete rewrite to present truthful metrics (371 tests, cross-platform matrix), quickstart, and relative doc links.
- `pyproject.toml`: Reconciled version to `0.3.0a0`.
- `src/gdec/__init__.py`: Reconciled `__version__ = "0.3.0a0"`.
- `.gitignore`: Added `*.zip` and `scratch/` rules.
- `research/phase5/PHASE_5_DECISION_REGISTER.md`: Recorded ADR-013 owner confirmation.
