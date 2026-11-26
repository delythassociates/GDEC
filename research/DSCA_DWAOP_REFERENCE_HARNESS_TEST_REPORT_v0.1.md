# DWAOP v0.2 — Finite-State Reference Harness Test Report

**Status:** EXECUTED RESEARCH-ONLY TESTS  
**Repository:** delythassociates/GDEC  
**Branch:** research/decision-sufficiency-algorithm  
**Harness:** [research/prototypes/dwaop_reference_harness.py](prototypes/dwaop_reference_harness.py)  
**Harness blob SHA:** f884a11a21d648418b1d1e30ce5a333245214414  
**Runtime:** Python 3.13.5

---

## 1. Scope

The harness is an offline finite-state reference model. It is separate from the GDEC runtime and has no imports from GDEC production packages.

It tests a restricted subset of DWAOP:

- finite action/state transitions and complete handling of each action outcome;
- one additive resource (resource units, RU);
- peak memory as a live-set high-water mark;
- the weak blocker-distance lower bound;
- disabling lower-bound pruning when the action-effect map is declared incomplete;
- malformed action/effect/outcome contract rejection;
- pruned versus unpruned feasibility on the same finite fixture;
- a finite greatest-simulation relation for state dominance;
- a candidate-frontier reducer that removes strictly dominated finite states;
- model, assurance, capability, evidence-contract, failure-semantics, cost and successor-state mismatch cases.

The dominance implementation is isolated from the planner's original find_plan recursion. A separate finite policy-summary enumerator now compares complete contingent-policy frontiers before/after candidate-state pruning on one constructed graph. It does **not** yet prune states during the general controller's AND-OR search, and the harness does not compare dominance-pruned search against an exhaustive search oracle over generated graph families.

It does **not** implement the optional blocker-cover LP, numerical witness generation, VWEC generation, a production DAPC checker, or GDEC runtime integration.

## 2. Provenance and commands

The current GitHub file was fetched after commit. Its content was copied into a local test file and the Git blob hash was compared:

~~~text
GitHub blob:     ebeaa85a6c22c473333d4d0b88fd9b017c82d480
Local blob:      ebeaa85a6c22c473333d4d0b88fd9b017c82d480
~~~

The hashes match exactly. Executed commands:

~~~bash
python --version
python -m unittest -v /tmp/dwaop_reference/dwaop_reference_harness_final_candidate.py
python -m py_compile /tmp/dwaop_reference/dwaop_reference_harness_final_candidate.py
~~~

Python reported 3.13.5. The unit-test run completed with **25 passed, 0 failed**. Bytecode compilation completed without error.

## 3. Test results

25 passed · 0 failed

| Test | Result | What it checks |
|---|---|---|
| Exhaustive optimum and complete branch tree | PASS | Exact unpruned oracle and pruned planner produce the 4.0 RU two-outcome plan; pass and fail branches end in ACCEPT and REJECT |
| Pruned/unpruned budget sweep | PASS | Feasibility agrees at 25 RU budgets from 0.00 through 6.00 in 0.25 increments |
| Lower bound versus exact cost | PASS | Blocker-distance lower bound does not exceed exact unpruned remaining RU cost at each non-terminal fixture state |
| Incomplete effect map | PASS | Incomplete blocker-effect map disables lower-bound pruning |
| Omitted blocker-removal effect | PASS | A claimed-complete effect map is rejected when a transition removes an undeclared blocker |
| Malformed outcome contract | PASS | Duplicate outcome labels are rejected |
| Incomplete outcome tree | PASS | Plan-tree validator rejects a missing required branch |
| Sequential memory high-water mark | PASS | Live-set memory is a path maximum, not a sum of workspaces |
| Mutually exclusive branch aggregation | PASS | RU and peak memory aggregate by worst realised branch, not by summing mutually exclusive branches |
| Small set-cover lower-bound example | PASS | Maximum of each blocker's cheapest resolver is no greater than exact integral cover cost |
| Exhaustive small set-cover families | PASS | Lower-bound property checked on all 7^4=2,401 non-empty action-cover assignments for three blockers/four actions |
| Resource-limit rejection | PASS | A plan is rejected when peak-memory limit is exceeded even though RU budget fits |
| State dominance requires full action simulation | PASS | Better root dominates weaker root only when a matching action and successor simulation exist |
| Narrower QoI set without matching action | PASS | Smaller QoI set alone does not imply dominance |
| More expensive action | PASS | A semantically matching action with higher upper resource cost cannot establish dominance |
| Unmatched successor | PASS | Dominance is rejected when an outcome successor cannot be simulated |
| Cyclic action graph | PASS | Greatest-simulation fixed point handles a simple cyclic finite graph |
| Outcome labels versus successor semantics | PASS | Different outcome labels are allowed when successor-state simulation establishes the mapping |
| Model-scope mismatch | PASS | States from different model scopes are not comparable |
| Evidence/failure contract mismatch | PASS | Mismatched evidence and failure semantics prevent action matching |
| Relation transitivity on reference graph | PASS | Returned relation is transitive on the finite test graph |
| ACCEPT versus REJECT terminal states | PASS | Opposite terminal verdicts are not related by dominance |
| Frontier pruning preserves complete policy cost/verdicts | PASS | Exhaustive policy summaries before/after candidate-state pruning preserve ACCEPT/REJECT coverage and the nondominated RU/peak-memory result in the constructed graph |
| Frontier pruning can remove an impossible verdict branch | PASS | A narrower QoI state with only a PASS outcome safely removes a FAIL branch; its policy remains complete and matches the pruned/exhaustive frontier |
| Parameterized candidate-frontier family | PASS | For seven fast-action costs, dominance-pruned and unpruned candidate frontiers agree on verdict sets, RU cost and peak memory |

## 4. Numeric outputs

The reference planning fixture contains:

- prepare: 1.0 RU;
- certify: 2.0 RU, branching to pass/fail outcomes;
- check_pass / check_fail: 1.0 RU in the respective branch.

The complete worst-case plan is:

\[
C_{\mathrm{RU}}^\uparrow
=1+\max(2+1,2+1)=4.0\ \mathrm{RU}.
\]

The exhaustive unpruned oracle also returns 4.0 RU. The fixture's peak-memory limit is satisfied at a 2.70 GB high-water mark.

The blocker-distance lower bound and exact cost at each non-terminal planning state:

| State | Lower bound | Exact unpruned remaining cost |
|---|---:|---:|
| Root | 2.0 RU | 4.0 RU |
| Prepared | 2.0 RU | 3.0 RU |
| Certified pass | 1.0 RU | 1.0 RU |
| Certified fail | 1.0 RU | 1.0 RU |

For the separate sequential-memory example, the high-water mark is 4.20 GB rather than the invalid sum of action workspaces, 6.50 GB.

For the separate mutually exclusive branch example:

\[
C_{\mathrm{RU}}^\uparrow=2+\max(2,5)=7\ \mathrm{RU},
\qquad
M_{\mathrm{peak}}^\uparrow=\max(3,4,2)=4\ \mathrm{GB}.
\]

The finite dominance example returns:
- ("good_root", "bad_root") in the greatest-simulation relation;
- the reverse pair is absent;
- the candidate frontier ("good_root", "bad_root") reduces to ("good_root",);
- exhaustive policy-frontier enumeration before/after candidate pruning retains the same terminal verdict set {ACCEPT, REJECT}, total RU upper cost 2.0 and peak memory 2.4 GB;
- in a narrower pass-only variant, the possible verdict set reduces from {ACCEPT, REJECT} to {ACCEPT} while the candidate remains decision-complete and the exhaustive/pruned frontier still agrees.

These are abstract fixture outputs, not measured GDEC solver performance.

## 5. Interpretation

The harness supports two narrow conclusions:

1. For its finite planning fixture, the implemented blocker-distance prune preserves feasibility relative to the exhaustive unpruned search and the resource aggregation returns the expected path totals.
2. For its finite dominance graph, the implemented greatest-simulation relation refuses several unsafe local comparisons and removes a strictly dominated candidate from a small frontier.

The tests do **not** prove admissibility for arbitrary engineering action graphs. The set-cover property test covers a finite family of 2,401 small instances. The planning oracle comparison uses one hand-constructed contingent graph. Dominance tests use a hand-constructed finite graph. The policy-frontier comparison covers seven parameterised action-cost instances and one additional pass-only refinement case; it still does not verify integration into the general planner or generated graph families.

The harness's verify_plan_tree function is a test-specific structural/resource checker. It does not inspect mathematical numerical certificates, validate outer QoI enclosures, establish theorem assumptions, or provide independent engineering assurance.

## 6. Known limitations and next tests

Not yet tested:

1. generated larger contingent DAGs and adversarial cyclic action/state graphs with independently computed simulation oracles;
2. dominance-pruned versus exhaustive unpruned search on generated finite graphs and cyclic transition systems;
3. correctness of frontier pruning across broader generated state sets, verdict refinements, and resource/capability combinations;
4. scenario-tree lower bounds for branching policies;
5. the blocker-cover LP relaxation;
6. resource dimensions beyond additive RU and peak memory;
7. action failure, timeout and model-invalidation transitions at planner scale;
8. any actual FEM/CFD solver, estimator or certified bound.

The next research test should integrate the greatest-simulation relation into the finite reference search, then compare its pruned and unpruned Pareto frontiers against exhaustive enumeration over generated small graphs. Until that passes, state-dominance pruning is **implemented as an isolated relation/frontier prototype only**, not as a validated DWAOP search optimisation.

## 7. Classification

- **IMPLEMENTED:** standalone finite-state planner/oracle harness; greatest-simulation relation; strict candidate-frontier reducer; exhaustive complete-policy summary comparison for a small constructed graph.
- **EXECUTED:** 25 Python unittest cases passed; Python 3.13.5.
- **CHECKED:** the exact committed Git blob was the source of the executed test copy.
- **NOT INTEGRATED:** the dominance reducer is not called from the harness's find_plan search recursion or any GDEC runtime. The policy-frontier comparison is a separate finite reference check, not search integration.
- **NOT IMPLEMENTED:** GDEC DWAOP controller, numerical certificate producers, trusted DAPC checker, LP pruning or production resource ledger.
- **NOT NUMERICALLY VERIFIED:** no FEM/CFD solve or engineering QoI bound was generated.
- **NOT INDEPENDENTLY REVIEWED:** no external reviewer has checked the algorithm or its proof assumptions.
- **NOT A NOVELTY RESULT:** no novelty, performance or patentability conclusion follows from these tests.
