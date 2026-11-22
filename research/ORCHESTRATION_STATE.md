# GDEC Orchestration State
Last updated: 2026-11-23T03:25:00+05:30  | Session #: 3
Branch tip: research/wp2-evidence-integrity-corrections  | Baseline: 448 passed / 0 skips / 0 failures on host with operational NVIDIA GPU (434 passed / 14 skipped in non-GPU CI)

## Work package board
| WP | Status (todo/active/blocked/done) | Branch | Gates passed / total | Evidence path |
|---|---|---|---|---|
| WP0 | done | research/wp0-repo-integrity | 4 / 4 | research/wp0/ |
| WP1 | done | research/wp1-eir-adversarial-hardening | 4 / 4 | research/wp1/ |
| WP2 | active (final evidence integrity corrections complete — ready for review) | research/wp2-evidence-integrity-corrections | 8 / 8 gates passed | research/wp2-evidence-integrity-corrections/ |
| WP3 | todo | pending | 0 / 4 | pending |
| WP4 | todo | pending | 0 / 2 | pending |
| WP5 | todo | pending | 0 / 3 | pending |
| WP6 | todo | pending | 0 / 2 | pending |
| WP7 | todo | pending | 0 / 3 | pending |

## Open defects
- None currently open.
- Resolved in WP1:
  - `DEFECT-WP1-01`: Unbounded AST recursion stack overflow -> fixed with `MAX_EXPRESSION_DEPTH = 128` and `MAX_EXPRESSION_NODES = 2048`.
  - `DEFECT-WP1-02`: Control codes and confusable characters accepted in identifiers -> fixed with NFC normalization and explicit character rejection.
  - `DEFECT-WP1-03`: Unbounded rational exponents in `Power` -> bounded to $\le 10,000$.

## Decisions recorded (owner-confirm needed marked)
- `ADR-013: Phase 5.2 Execution Authorization` — Confirmed by Owner in Session 2 note (2026-11-22).
- `Owner Directive (Session 2)` — WP1/WP2 must audit `tests/test_cuda_backend.py` to ensure GPU tests assert actual device residency without silent CPU fallback. (Verified and closed in WP1).
- `Owner Directive (Session 2)` — WP3 evidence record schema must incorporate a compact problem-feature vector and outcome metrics (final DOFs, refinement steps, wall time, estimator value) for future learning.

## Research memos (id | claim | status: alive/killed | next action)
- (Initialized; candidate claims formulation in progress per Scientific Research Track protocol).

## Metrics history (date | tests | coverage | mutation | CI green | docs warnings)
| Date | Tests | Coverage | Mutation | CI Green | Docs Warnings |
|---|---|---|---|---|---|
| 2026-11-22 (S1) | 358 (371 w/ GPU) passed / 0 failed / 1 warning | unmeasured (offline venv) | pending | 100% (Linux py3.10-3.12) | 0 (pending docs build) |
| 2026-11-22 (S2) | 371 passed / 0 failed / 1 warning | unmeasured (offline venv) | pending | 100% (Linux py3.10-3.12) | 0 (README link check 22/22 green) |
| 2026-11-22 (S3) | 401 passed / 0 failed / 1 warning | unmeasured (offline venv) | pending | 100% (Linux py3.10-3.12) | 0 (WP1 hardening clean) |
| 2026-11-23 (S3 WP2) | 426 passed / 0 failed / 1 warning | unmeasured (offline venv) | 100% (6/6 killed) | 100% matrix (Linux, Win, macOS x 3.10-3.13) + drift + status register | 0 (WP2 verification clean) |
| 2026-11-23 (S3 WP2 Remediation) | 429 passed / 0 failed / 1 warning | unmeasured (offline venv) | 100% (6/6 killed) | 100% matrix (Linux, Win, macOS x 3.10-3.13) + drift + status register | 0 (WP2 remediation clean) |
| 2026-11-23 (S3 WP2 Followup) | 434 passed / 0 failed / 1 warning | unmeasured (offline venv) | 100% (14/14 campaign + 6/6 targeted) | 100% matrix (Linux, Win, macOS x 3.10-3.13) + drift + status register gate | 0 (clean) |
| 2026-11-23 (S3 WP2 Evidence Closure) | 437 passed / 0 failed / 1 warning | unmeasured (offline venv) | 100% (14/14 campaign + 6/6 targeted) | 100% matrix + drift + status register gate + mutation | 0 (clean) |

## Deferred list (idea | why deferred)
- Hardware synthesis & custom GPU/FPGA/ISA kernels | Deferred per Rule R5 and Parking Lot until WP3/WP4 produce profile-guided evidence.
- Adjoint-weighted condensation | Deferred per Parking Lot (targeted at AHCE/EAIMC codebase, not GDEC core).
- 3D continuum elements, P2 higher-order elements, nonlinear plasticity, transient dynamics | Deferred per Parking Lot until WP5 completion.
