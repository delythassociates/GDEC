# Work Package 1 (WP1) Master Report: Adversarial Hardening of EIR Type System

**Document Identifier:** `GDEC-WP1-MASTER-REPORT`  
**Work Package:** WP1 — Adversarial Hardening of the EIR / Expression Type System  
**Branch:** `research/wp1-eir-adversarial-hardening`  
**Starting Commit:** `e3497b1` (tip of `research/wp0-repo-integrity`)  
**Date:** 2026-11-22  
**Status:** Completed & Verified  
**Author:** Lead Engineering Research Orchestrator

---

## 1. Executive Summary

Work Package 1 (WP1) conducted an independent adversarial attack on the Phase 5.2.x Engineering-IR (EIR) foundational type system, unit conversion engine, and expression type inference pipeline. The codebase was treated as third-party code and subjected to rigorous property-based testing, cross-platform hash determinism checks, and adversarial fuzzing (deep nesting, control characters, huge exponents, NaN/inf, boolean values).

The adversarial pass discovered two critical security and stability vulnerabilities:
1. **Unbounded AST Recursion Crash (DEFECT-WP1-01):** Deeply nested expression trees crashed Python with an unhandled built-in `RecursionError` instead of raising a typed domain error.
2. **Confusable and Control Character Acceptance (DEFECT-WP1-02):** The entity identifier validator accepted control characters (`\x00`, `\n`, `\r`, `\t`), zero-width spaces (`\u200b`, `\ufeff`), and bidirectional overrides (`\u202e`), and failed to normalize decomposed Unicode (NFD).

Both vulnerabilities were reproduced with failing tests, repaired, and validated. In addition, an explicit device-residency and anti-silent-fallback assertion test was added to `tests/test_cuda_backend.py` per owner directive.

The total test suite expanded from 371 to 401 tests (all passing in 11.19s).

---

## 2. Assumptions List

An audit of `src/gdec/types` and `src/gdec/eir` identified the following implicit assumptions:
1. **Exact Dimension Exponents:** Physical dimension exponents are assumed to be exact bounded rationals (`Fraction`), with floats coerced to rationals with denominator $\le 10,000$.
2. **Coherent Base Units:** Every quantity and field has a single coherent SI base unit defined in `_BASE_UNITS`. Conversions to base units are assumed exact within floating-point roundoff.
3. **Identifier Normalization:** Identifiers are assumed to be canonical Unicode strings. Prior to WP1, NFD vs NFC differences were implicitly ignored, which caused hash discrepancies across platforms (e.g. macOS vs Linux).
4. **Finite AST Depth:** Expressions were assumed to have modest nesting depth, leaving the interpreter vulnerable to stack overflows.
5. **No Tensor Broadcasting:** Tensor operations assume identical shapes and explicit coordinate frames; implicit broadcasting is rejected.

---

## 3. Defects Discovered and Fixed

### DEFECT-WP1-01: Unbounded AST Recursion Stack Overflow
- **Symptom:** Passing deeply nested expressions to `infer_expression_type` crashed the Python interpreter with `RecursionError: maximum recursion depth exceeded`.
- **Root Cause:** `infer_expression_type` traversed expression nodes via direct recursive calls without a depth counter or node tally.
- **Fix:** Introduced `MAX_EXPRESSION_DEPTH = 128` and `MAX_EXPRESSION_NODES = 2048`. Traversal tracks current recursion depth and total visited nodes, raising a typed `ExpressionTypeError` when limits are exceeded.
- **Evidence:** Verified by `test_deeply_nested_expression_rejected_with_typed_error`.

### DEFECT-WP1-02: Control Codes and Unicode Confusables in Identifiers
- **Symptom:** Identifiers containing null bytes (`\x00`), newlines (`\n`), zero-width spaces (`\u200b`), and right-to-left overrides (`\u202e`) were accepted. Decomposed Unicode (`cafe\u0301`) failed string equality with composed Unicode (`café`).
- **Root Cause:** `_identifier` in `models.py` and `_validate_reference_id` in `expressions.py` only checked `value.strip()`.
- **Fix:** Added NFC normalization via `unicodedata.normalize("NFC", value)` and explicit character inspection rejecting ASCII/Unicode control characters (`Cc`), format characters (`Cf` such as zero-width spaces and bidi isolates), surrogates (`Cs`), and null bytes.
- **Evidence:** Verified by `test_identifier_rejects_control_and_confusable_characters` and `test_identifier_unicode_nfc_normalization`.

### DEFECT-WP1-03: Unbounded Rational Exponents in Power Nodes
- **Symptom:** Power nodes accepted arbitrarily huge Fraction numerators and denominators (e.g. $10^{100}$), risking memory exhaustion during dimensional exponent multiplication.
- **Root Cause:** `Power.__post_init__` accepted any Fraction without bounds checking.
- **Fix:** Enforced `abs(numerator) <= 10,000` and `denominator <= 10,000` in `Power.__post_init__`, raising `ExpressionTypeError` if violated.
- **Evidence:** Verified by `test_power_rejects_adversarial_huge_exponents`.

---

## 4. Owner Directive: CUDA Backend Device Residency Verification

Per owner directive:
*"verify tests/test_cuda_backend.py asserts the arrays/solves actually ran on the GPU device (no silent CPU fallback), despite the CuPy 'CUDA path could not be detected' warning."*

- **Audit Finding:** `CUDABackend.solve_cg` operates strictly on GPU memory via `cp_spla.cg` and `cp.linalg.norm`. It raises `NumericalBackendError` upon numerical failure and `BackendNotAvailableError` if CUDA is uninstalled; it possesses zero code paths for silent CPU fallback.
- **Verification Added:** Implemented `test_cuda_asserts_device_execution_and_no_silent_cpu_fallback` in `tests/test_cuda_backend.py`. Confirmed:
  1. SpMV and CG operate on device-resident `cp.ndarray` and `cp_sp.csr_matrix` instances with zero host matrix transfers (`info["host_matrix_transfers"] == 0`).
  2. Residual evaluation executes on device memory.
  3. Non-finite GPU inputs raise `NumericalBackendError` on device without delegating to SciPy.

---

## 5. Acceptance Verification Summary

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| **Gate 1** | $\ge 1$ property test per public typing API | **PASS** | 5 property suites testing dimension algebra, associativity, commutativity, identity, SI roundtrips, and rational arithmetic in `tests/eir/test_adversarial_hardening.py` |
| **Gate 2** | Hash-determinism test matrix | **PASS** | Verified across dict ordering, CRLF vs LF line endings, equivalent numbers (1e3 vs 1000.0 vs 1000), equivalent units (1 kPa vs 1000 Pa), and distinct definitions |
| **Gate 3** | Fuzz suite < 60s, 0 unhandled exceptions | **PASS** | Entire 29-test adversarial suite executes in **0.22s**; all invalid inputs produce typed errors |
| **Gate 4** | Complete defect reporting | **PASS** | Documented DEFECT-WP1-01, DEFECT-WP1-02, and DEFECT-WP1-03 with failing-test-first logs |
