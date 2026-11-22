# GDEC Master Integration & Merge Plan

**Document Identifier:** `GDEC-WP0-MERGE-PLAN`  
**Date:** 2026-11-22  
**Target Base Branch:** `main` (Commit `789f1f1`)  
**Status:** Staged & Planned (Do Not Execute Merges Without Explicit Owner Authorization)

---

## 1. Executive Summary

The GDEC development campaign operates across a series of structured research and remediation branches. To merge these developments into `main` without regressing the baseline or introducing breaking conflicts, changes must be landed in a strictly ordered, incremental Pull Request (PR) chain.

Each PR is self-contained, preserves the 371-test baseline (358 on CPU-only CI nodes), and carries its own acceptance evidence.

---

## 2. Ordered PR Chain

### PR 1: Phase 4.1 Closure — Matrix Diagnostics & Iterative Solvers
- **Source Branch:** `audit/v0.2.2-deep-review` (HEAD: `6ba8c3e`)
- **Target:** `main`
- **Existing PR:** PR #1 (Keep draft until approved)
- **Scope:**
  - Matrix diagnostics, conditioning studies, and condition number estimators.
  - PCG iterative solver with Jacobi, Incomplete Cholesky, and PyAMG smoothers.
  - Rigorous SPD eligibility contracts and indefinite matrix rejection.
- **Conflict Risk:** Low. Independent solver and diagnostic modules.
- **Verification Gate:** 174 baseline tests pass.

---

### PR 2: Phase 5.1 Closure — Execution Backend & Decision Intelligence
- **Source Branch:** `research/phase-5.1.3-validation-and-ci-closure` (HEAD: `33aed02`)
- **Target:** `main` (post-PR 1)
- **Scope:**
  - `ExecutionBackend` protocol layer (`CPUBackend`, optional `CUDABackend`).
  - Minimal CuPy GPU prototype with SpMV and PCG.
  - Decision Sufficiency Engine (DSE) core: declarative decision contract schema, Bayesian expected loss, and single-QoI decision evaluator.
  - Zero-solve analytical parameter scaling for linear elasticity.
  - Independent FEM numerical validation suite against manufactured solutions.
- **Conflict Risk:** Medium. Connects solver backend to runtime controller.
- **Verification Gate:** 343 baseline tests pass.

---

### PR 3: Phase 5.2 Closure — Foundational Types & Canonical EIR
- **Source Branch:** `research/phase-5.2.1b-expression-input-integrity` (HEAD: `7cd9738`)
- **Target:** `main` (post-PR 2)
- **Scope:**
  - Foundational engineering types (`gdec.types`): dimensions, units, physical quantities, absolute vs interval temperature semantics, spatial frames.
  - Canonical Engineering IR (`gdec.eir`): problem definition models, references, and content-addressed SHA-256 canonical hashing.
  - Strongly typed expression inference and semantic AST validation.
- **Conflict Risk:** Low. Fully additive; preserves legacy `ProblemIR` execution path.
- **Verification Gate:** 371 baseline tests pass (358 on CPU nodes).

---

### PR 4: WP0 — Repository Integrity & Front Door
- **Source Branch:** `research/wp0-repo-integrity`
- **Target:** `main` (post-PR 3)
- **Scope:**
  - Modernized `README.md` with truthful status metrics and 10-minute quickstart.
  - Community governance: `CHANGELOG.md`, `CITATION.cff`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.
  - Version reconciliation (`0.3.0a0`) and `docs/VERSION_POLICY.md`.
  - Archiving legacy audit documents and scratch scripts to `docs/archive/`.
  - Removal of tracked binary zips from working tree.
- **Conflict Risk:** Low. Non-numerical repository hygiene.
- **Verification Gate:** All README links resolve; quickstart executes cleanly; 371 tests pass.

---

### PR 5: WP1 — Adversarial Hardening of EIR Type System
- **Source Branch:** `research/wp1-eir-adversarial-hardening`
- **Target:** `main` (post-PR 4)
- **Scope:** Property-based tests (Hypothesis), hash determinism across platforms, AST fuzzing, immutability guarantees.
- **Verification Gate:** Fuzz suite runs < 60s; 0 unhandled exceptions; 371+ tests pass.

---

### PR 6: WP2 — Automated V&V Suite & CI Matrix
- **Source Branch:** `research/wp2-vv-suite-and-ci-matrix`
- **Target:** `main` (post-PR 5)
- **Scope:** Multi-OS CI matrix (Linux, Windows, macOS x Python 3.10-3.13), >=8 analytical reference problems, automated status register generation, branch coverage ratchet.
- **Verification Gate:** CI matrix 100% green; status register generated from test markers.

---

### PR 7: WP3 — Evidence Graph & Refusal Engine
- **Source Branch:** `research/wp3-evidence-and-refusal-engine`
- **Target:** `main` (post-PR 6)
- **Scope:** Machine-checkable Merkle evidence records, >=10 explicit refusal rules, CLI verifier (`gdec verify`), problem-feature vector recording for future learning.
- **Verification Gate:** Tamper detection passes 100%; refusal rules covered by positive/negative tests.

---

### PR 8: WP4 & WP5 — Numerical Contract & Steady Heat Conduction
- **Source Branch:** `research/wp4-wp5-contracts-and-physics`
- **Target:** `main` (post-PR 7)
- **Scope:** Software-only numerical contract allocator; steady 2D heat-conduction physics plugin via generic physics interface.
- **Verification Gate:** Energy balance to machine precision; >=5 heat benchmarks pass; elasticity unchanged.

---

### PR 9: WP6 — Certified-Bound Feasibility Study
- **Source Branch:** `research/wp6-certified-bounds`
- **Target:** `main` (post-PR 8)
- **Scope:** Primary literature study (equilibrated flux / Prager-Synge), prototype bound estimator, feasibility verdict.
- **Verification Gate:** Bound >= true error on 100% of test cases.

---

### PR 10: WP7 — Release Candidate & Long-Term Longevity
- **Source Branch:** `research/wp7-release-candidate`
- **Target:** `main` (post-PR 9)
- **Scope:** Material-mkdocs documentation site, IR backward-compatibility tests, clean-venv wheel build and smoke test.
- **Verification Gate:** Wheel installs and passes smoke suite on clean environments.

---

## 3. Conflict Prevention Checklist
1. Never rebase shared branches; merge forward using explicit merge commits or rebase only prior to PR submission.
2. Keep all numerical changes quarantined to `src/gdec/core`, `src/gdec/fem`, and `src/gdec/solver`.
3. Keep IR types decoupled from runtime solver code via adapters.
4. Verify full test suite on clean clone before merging any PR in the sequence.
