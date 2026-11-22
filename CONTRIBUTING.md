# Contributing to GDEC

Thank you for contributing to Goal-Driven Engineering Computation (GDEC).

## Core Principles
1. **Evidence over Assertion:** Every numerical capability claim must cite an automated test verifying it against analytical, manufactured, or peer-reviewed benchmarks.
2. **Refusal when Unsure:** When numerical assumptions (such as matrix positive-definiteness or linear strain bounds) are violated, GDEC must raise a typed refusal, never return an uncertified answer.
3. **Deterministic Execution:** Avoid unseeded random generators, non-deterministic hash iteration, or wall-clock dependencies in numerical assertions.

## Development Workflow
1. Cut a branch from `research/phase-5.2.1b-expression-input-integrity` (or current branch tip designated in `research/ORCHESTRATION_STATE.md`).
2. Adhere to conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
3. Ensure all tests pass locally:
   ```bash
   pytest -v
   ```
4. Never weaken existing tests or widen numerical tolerances without an entry in `docs/adr/ADR_REGISTER.md`.
5. Submit PRs against the appropriate active research branch.
