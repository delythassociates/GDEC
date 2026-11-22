# Work Package 0 (WP0) Risk Register

**Document Identifier:** `GDEC-WP0-RISK-REGISTER`  
**Work Package:** WP0 — Repo Integrity & Front Door  
**Date:** 2026-11-22  

---

## Residual Risks & Mitigations

| Risk ID | Description | Severity | Probability | Mitigation Strategy | Owner / Next Phase |
|---|---|---|---|---|---|
| **RISK-WP0-01** | Historical binary zips remain in git history of commit `789f1f1` (clone size ~1.3 MB larger than pure source). | Low | High | Preserved intentionally per hard rule "Do NOT rewrite history". If repository is published to public mirrors in WP7, assess git filter-repo only with explicit owner sign-off. | WP7 Release Packaging |
| **RISK-WP0-02** | Documentation sprawl remains in `docs/` root (~45 historical audit files mixed with specs). | Medium | High | Root cleanup prioritized in WP0 (`docs/archive/` established); full consolidation and mkdocs-material site generation scheduled for WP7. | WP7 Longevity & Docs |
| **RISK-WP0-03** | CI matrix in `.github/workflows/ci.yml` currently tests Ubuntu Linux only; Windows/macOS runners not yet automated. | Medium | High | Identified in Phase 0 audit and documented in README quickstart; full cross-platform matrix (Linux + Windows + macOS x Python 3.10-3.13) is the primary deliverable of WP2. | WP2 V&V Suite & CI |
| **RISK-WP0-04** | CuPy environment warning `CUDA path could not be detected` appears on some hosts despite operational GPU. | Low | Medium | Tests in `test_cuda_backend.py` assert device residency; owner instructed explicit device assertion audit in WP1/WP2. | WP1 & WP2 |
| **RISK-WP0-05** | Merging PR sequence could encounter minor conflicts if downstream branches modify overlapping metadata. | Low | Low | Ordered 10-PR merge plan documented in `research/wp0/WP0_MERGE_PLAN.md` with strict conflict prevention checklist. | Integration Lead |
