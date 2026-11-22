# Work Package 1 (WP1) Changelog

**Document Identifier:** `GDEC-WP1-CHANGELOG`  
**Branch:** `research/wp1-eir-adversarial-hardening`  
**Date:** 2026-11-22  

---

## Changes Implemented

### Added
- `tests/eir/test_adversarial_hardening.py`: 29 adversarial hardening tests covering:
  - Property-based testing of dimension algebra, commutativity, associativity, and SI round-trips.
  - Cross-platform canonical SHA-256 hash determinism.
  - Adversarial input fuzzing (recursion depth, control characters, unicode confusables, huge exponents).
  - Immutability and anti-aliasing enforcement.
- `tests/test_cuda_backend.py::test_cuda_asserts_device_execution_and_no_silent_cpu_fallback`: Explicit verification that GPU execution operates on physical device memory without silent CPU fallback.
- `research/wp1/WP1_MASTER_REPORT.md`: Comprehensive completion report, assumptions list, and defect analysis.
- `research/wp1/WP1_ACCEPTANCE_MATRIX.md`: Verification evidence for Gates 1-4.
- `research/wp1/WP1_CHANGELOG.md`: WP1 change manifest.
- `research/wp1/WP1_RISK_REGISTER.md`: Residual risk tracking.

### Fixed
- `src/gdec/eir/expressions.py`:
  - Added bounded recursion limit (`MAX_EXPRESSION_DEPTH = 128`) and AST node limit (`MAX_EXPRESSION_NODES = 2048`) to `infer_expression_type`, preventing unhandled interpreter `RecursionError` crashes.
  - Sanitized reference identifiers against control characters, zero-width spaces, and bidi overrides.
  - Bounded rational exponents in `Power.__post_init__` to $\le 10,000$.
  - Inherited `ExpressionTypeError` from `TypeSystemError`.
- `src/gdec/eir/models.py`:
  - Enforced Unicode NFC normalization and rejected control characters, zero-width spaces, and bidi overrides in `_identifier`.
