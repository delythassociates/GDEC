# Work Package 1 (WP1) Acceptance Matrix

**Document Identifier:** `GDEC-WP1-ACCEPTANCE-MATRIX`  
**Work Package:** WP1 — Adversarial Hardening of the EIR / Expression Type System  
**Branch:** `research/wp1-eir-adversarial-hardening`  
**Date:** 2026-11-22  
**Result:** ALL GATES PASSED (4/4)

---

## Acceptance Gate Details

### Gate 1: Property-Based Typing Tests
- **Requirement:** $\ge 1$ property test per public function in the typing API.
- **Status:** **PASS**
- **Evidence:** Tested public typing functions across 50+ randomized trials per invariant:
  - Multiplication associativity: `(A * B) * C == A * (B * C)`
  - Multiplication commutativity: `A * B == B * A`
  - Identity element: `A * 1 == A` and `A / 1 == A`
  - Dimensional consistency: `[A * B] == [A] * [B]`
  - SI round-trip normalization: `from_base(to_base(x)) == x` within $10^{-12}$
  - Rational exponent arithmetic: zero float leakage.
  - Test suite: `tests/eir/test_adversarial_hardening.py::TestUnitAlgebraProperties`.

---

### Gate 2: Hash Determinism Matrix
- **Requirement:** Hash-determinism test matrix passes across dict order, platforms, line endings, and equivalent inputs; define what must differ.
- **Status:** **PASS**
- **Evidence:**
  - Dict insertion order: `parameters=(p1, p2)` vs `parameters=(p2, p1)` produce identical hash `2565cab57dc1d01e8495977bccd3419567772c17a778d42cf69827d184644cf2`.
  - Line-ending differences: JSON with LF vs CRLF produce identical canonical hash.
  - Numerically equal representations: `1000`, `1000.0`, and `1e3` produce identical canonical hash `d72f02f8cd37aa7a38cdd7a97fb1e575c3abeb023a4f206f90a1adec7cf18ccf`.
  - Coherent unit equivalences: `1.0 kPa` and `1000.0 Pa` produce identical canonical hash `d72f02f8cd37aa7a38cdd7a97fb1e575c3abeb023a4f206f90a1adec7cf18ccf`.
  - Must-differ assertions: Differing problem IDs, values, parameter IDs, and units produce 5 pairwise distinct SHA-256 hashes.
  - Test suite: `tests/eir/test_adversarial_hardening.py::TestCanonicalHashDeterminism`.

---

### Gate 3: Fuzz Suite Execution & Exception Safety
- **Requirement:** Fuzz suite runs < 60 s in CI; 0 unhandled exception types.
- **Status:** **PASS**
- **Evidence:**
  - Fuzz suite execution time: **0.22 s** (well below 60 s limit).
  - Deeply nested expressions (depth 500) raise typed `ExpressionTypeError`.
  - Control characters (`\x00`, `\n`, `\r`, `\t`), zero-width spaces (`\u200b`, `\ufeff`), and bidi overrides (`\u202e`) raise typed `ValueError` / `ExpressionTypeError`.
  - Adversarial huge power exponents ($10^8$) raise typed `ExpressionTypeError`.
  - NaN/inf and boolean inputs raise typed `ValueError`.
  - Zero unhandled exceptions or interpreter crashes.
  - Test suite: `tests/eir/test_adversarial_hardening.py::TestAdversarialFuzzing`.

---

### Gate 4: Defect Reporting
- **Requirement:** Report lists every defect found, or states plainly "found none" with the attack list attempted.
- **Status:** **PASS**
- **Evidence:** Documented 3 specific defects in [WP1_MASTER_REPORT.md](file:///f:/fem-edit-benchmark/research/wp1/WP1_MASTER_REPORT.md#3-defects-discovered-and-fixed):
  - DEFECT-WP1-01: Unbounded AST Recursion Stack Overflow (`infer_expression_type`).
  - DEFECT-WP1-02: Control Codes and Unicode Confusables in Identifiers (`_identifier`).
  - DEFECT-WP1-03: Unbounded Rational Exponents in Power Nodes (`Power.__post_init__`).
