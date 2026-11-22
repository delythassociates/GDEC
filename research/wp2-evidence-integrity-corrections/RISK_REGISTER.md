# GDEC WP2 Targeted Final Corrections — Risk Register

| Risk ID | Description | Severity | Likelihood | Mitigation Strategy | Status |
|---|---|---|---|---|---|
| **RISK-WP2-C01** | Production solver lacks arbitrary mesh support | Low | Medium | Option B adopted: Kirsch benchmark tests reference model formulation sensitivity; production solver defect sensitivity documented as open/deferred to future arbitrary-mesh integration | Managed |
| **RISK-WP2-C02** | Mutation testing misclassifying runner errors as kills | High | Low | Hardened runner classification captures collection, setup, teardown, and injection errors explicitly as `ERROR` or `INVALID_MUTANT`; verified with 6 negative resilience tests | Closed |
| **RISK-WP2-C03** | Status register false clean on broken Git environment | Medium | Low | Git inspection fails closed (`git_valid=False`, `dirty=True`); `verify_traceability()` rejects invalid git and unknown commit SHAs | Closed |
| **RISK-WP2-C04** | Automated tests claiming experimental physical validation | High | Low | Strict evidence-level policy caps automated test suite demonstration at `NUMERICALLY VERIFIED`; claimed `INDEPENDENTLY VALIDATED` rejected by traceability gate | Closed |
