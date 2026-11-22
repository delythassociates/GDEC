# Work Package 0 (WP0) Master Report: Repository Integrity & Front Door

**Document Identifier:** `GDEC-WP0-MASTER-REPORT`  
**Work Package:** WP0 — Repo Integrity & Front Door  
**Branch:** `research/wp0-repo-integrity`  
**Parent / Starting Tip:** `research/phase-5.2.1b-expression-input-integrity` (`7cd9738`)  
**Date:** 2026-11-22  
**Status:** Completed & Verified  
**Author:** Lead Engineering Research Orchestrator

---

## 1. Executive Summary

Work Package 0 (WP0) remediates the repository front door and integrity issues to present a truthful, clean, and credible open-source foundation. Prior to WP0, `main` and the development branches suffered from historical artifacts:
1. `README.md` claimed 42 tests, "CPU only", Windows-only platform, and broken local `file:///` URLs.
2. Tracked binary zip archives (`GDEC_v0.2.2_PRIVATE_REVIEW.zip` and `materials-simulation-skills-main.zip`) polluted the root directory.
3. Legacy scratch scripts from earlier review cycles sat in `scratch/`.
4. Standard community governance files (`CHANGELOG.md`, `CITATION.cff`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates) were absent.
5. The package version in `pyproject.toml` remained statically fixed at `0.2.2`.

All tasks of WP0 have been completed without modifying any numerical or finite-element solver code. The reported local-host run completed with 371 passed and 1 warning. The CPU-only pass/skip split is not independently reconciled in this package: the current CUDA test module has 11 hardware-gated tests and 2 non-hardware detection tests, so the stated 358 passed / 13 skipped split needs a full CPU-only rerun.

---

## 2. Root Inventory Audit & Justification Table

The root directory was cataloged and audited. Every file/directory that is not source, test, doc, example, or config was categorized according to the required action:

| Item | Original Path | Proposed Action | Justification |
|---|---|---|---|
| `GDEC_v0.2.2_PRIVATE_REVIEW.zip` | Root | Removed from working tree (`git rm`), added to `.gitignore` | Binary zip archive (294 KB) from private review. Retained in git commit history (`789f1f1`), removed from working tree to ensure clean clone. |
| `materials-simulation-skills-main.zip` | Root | Removed from working tree (`git rm`), added to `.gitignore` | Binary archive (974 KB) of external simulation skills. Retained in git commit history, removed from working tree. |
| `REPOSITORY_AUDIT_PREPARATION.md` | Root | Relocated to `docs/archive/v022/` | Static markdown report specific to the historical v0.2.2 review. Preserved under versioned archive. |
| `scratch/` (6 python scripts) | Root `scratch/` | Relocated to `docs/archive/scratch/`, `scratch/` added to `.gitignore` | Temporary benchmark and reconciliation scripts (`test_stage1_...`, `regenerate_v022_...`). Moved to docs archive to prevent confusion with active test suite. |
| `README.md` | Root | Completely rewritten | Replaced stale v0.2.2 claims with truthful status metrics, 10-minute cross-platform quickstart, and relative doc links. |
| `pyproject.toml` | Root | Version reconciled | Reconciled package version to `0.3.0a0` (`0.3.0-alpha`). |
| `src/gdec/__init__.py` | `src/gdec/` | Version reconciled | Reconciled `__version__ = "0.3.0a0"`. |
| `src/gdec/core/analyser.py` | `src/gdec/core/` | Strictly preserved untracked | User asset preserved without modification. |
| `src/gdec/runtime/` | `src/gdec/` | Strictly preserved untracked | User directory preserved without modification. |

---

## 3. What Was Done

1. **Root Directory Hygiene & Archive Relocation:**
   - Moved `REPOSITORY_AUDIT_PREPARATION.md` to `docs/archive/v022/REPOSITORY_AUDIT_PREPARATION.md`.
   - Moved tracked `scratch/` directory to `docs/archive/scratch/`.
   - Removed binary zips `GDEC_v0.2.2_PRIVATE_REVIEW.zip` and `materials-simulation-skills-main.zip` from working tree using `git rm`.
   - Updated `.gitignore` to ignore `*.zip` and `scratch/`.
2. **Modernized, Truthful `README.md`:**
   - Badges report the 371-test suite size, Python 3.10+ target, platform targets, and MIT license. Automated CI is currently configured for Ubuntu / Python 3.10–3.12; Windows, macOS, and Python 3.13 are not covered by that workflow.
   - Added clear "What GDEC is / What GDEC is not" section defining the Decision Sufficiency Engine, goal adaptivity, and deterministic refusal boundaries.
   - Added cross-platform 10-minute Quickstart with verified CLI commands.
   - Converted README evidence links to repository-relative links. Historical local paths in earlier audit notes are not portable and must not be treated as live evidence links.
   - Explicitly linked all numerical performance claims to repo result files.
3. **Community & Governance Infrastructure:**
   - Authored `CHANGELOG.md` adhering to Keep-a-Changelog and SemVer 2.0.0.
   - Authored `CITATION.cff` for scholarly attribution.
   - Authored `SECURITY.md` establishing vulnerability disclosure and deterministic input safety.
   - Authored `CONTRIBUTING.md` defining branch discipline, testing standards, and PR protocols.
   - Authored `CODE_OF_CONDUCT.md` establishing engineering integrity and professional conduct standards.
   - Added GitHub issue templates (`bug_report.md`, `feature_request.md`) and pull request template (`PULL_REQUEST_TEMPLATE.md`).
4. **Version Policy & Schema Decoupling:**
   - Baselined `docs/VERSION_POLICY.md` specifying SemVer platform release rules, decoupling of platform versions from schema versions (`gdec_ir_v0.1`, `eir_0.1.0`, `dse_contract_1.0.0`), and deprecation guarantees.
   - Reconciled `pyproject.toml` and `src/gdec/__init__.py` to `0.3.0a0`.
5. **Ordered Merge Plan:**
   - Authored `research/wp0/WP0_MERGE_PLAN.md` detailing the 10-PR sequence to integrate the research stack into `main` without regressing the baseline.

---

## 4. What Was NOT Done

1. **Zero Numerical Code Changes:** No finite element formulations, assembly loops, estimators, or solver routines were altered.
2. **No Git History Rewriting:** Binary files were removed from the working tree via standard commits; no `filter-branch`, `rebase -i`, or history deletion was performed.
3. **No Premature Merges:** The merge plan was staged and documented; no branches were merged into `main`.

---

## 5. Acceptance Verification Summary

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| **Gate 1** | Quickstart reproduction on clean venv | **PASS** | `gdec hardware`, `validate`, `compile`, and `run` executed successfully in 0.271s |
| **Gate 2** | README local targets exist; external badge URLs identified | **PASS WITH LIMITATION** | 17 local targets found; 5 external badge URLs were classified but not HTTP-checked |
| **Gate 3** | Claims backed by repo file paths | **PASS** | All performance metrics link to `results/` or `tests/` files |
| **Gate 4** | Full local-host suite passes | **PASS (reported)** | 371 passed (0 failed, 1 warning) in 13.35s; CPU-only skip split remains unverified |
