# WP3 Verification & Adversarial Tamper Report

- **Independent Verifier:** `src/gdec/dse/verifier.py` (`verify_evidence_payload`, `verify_evidence_file`)
- **CLI Entry Point:** `gdec verify <result.json> [--json] [--require-qualified]` (does **not** run the solver by default; exits `0` valid, `1` invalid/tampered, `2` valid-but-unqualified with `--require-qualified`).
- **Full Suite Observed Result (Post-Final-Edit):** **488 passed, 14 skipped, 0 failed** in `109.93s` (`14` CUDA tests skipped on non-GPU host).
- **Branch Coverage Gate:** **64.48% (1238/1920 branches)** >= `62.15%` baseline floor (`[PASS]`).
- **Targeted Mutation Campaign:** **20/20 mutants killed (100.0%)**, `0` surviving, `0` invalid, `0` execution errors (targeted scope, not whole-repository mutation coverage).
- **Protected Files Check:** `git diff -- src/gdec/fem/` is empty; `src/gdec/core/analyser.py` and `src/gdec/runtime/mesh_evidence.py` preserved untouched.
