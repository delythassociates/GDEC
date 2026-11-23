# GDEC WP2 Final Mutation Classification and Test Coverage — Risk Register

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Status |
|---|---|---|---|---|---|
| **RISK-WP2-MC01** | Mutation runner misclassifying runner errors or unexpected crashes as mutation kills | High | Low | Hardened runner classification captures collection, setup, teardown, and non-assertion runtime crashes as `ERROR`; validated with dedicated negative tests | Closed |
| **RISK-WP2-MC02** | Mutation testing running on invalid or failing baseline code | High | Low | Fail-fast baseline validation requires `BASELINE_PASS` across all mutants; any failure produces `INVALID_BASELINE` and halts campaign prior to injection | Closed |
| **RISK-WP2-MC03** | Status register false clean if individual Git inspection commands fail | Medium | Low | Git inspection fails closed (`git_valid=False`, `dirty=True`) if any of `git rev-parse HEAD`, `git rev-parse --abbrev-ref HEAD`, or `git status --porcelain -uall` fails; covered by 3 distinct negative tests | Closed |
| **RISK-WP2-MC04** | Mutation campaign artifact missing audit fields or schema non-compliance | Medium | Low | `validate_mutant_record` validates all 12 required fields on every record during campaign execution | Closed |
