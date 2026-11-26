# DWAOP v0.2 — Finite-State Reference Harness Test Report

**Status:** EXECUTED RESEARCH-ONLY TESTS  
**Repository:** \`delythassociates/GDEC\`  
**Branch:** \`research/decision-sufficiency-algorithm\`  
**Harness:** [\`research/prototypes/dwaop_reference_harness.py\`](prototypes/dwaop_reference_harness.py)  
**Harness blob SHA:** \`e05a652bc3c134fbc411d1b2aceef39eaee787ee\`  
**Runtime:** Python 3.13.5

---

## 1. Scope

The harness is an offline finite-state reference model. It is separate from the GDEC runtime and has no imports from GDEC production packages.

It tests a restricted subset of the DWAOP proposal:

- finite action/state transitions;
- complete handling of every action outcome;
- one additive resource (resource units, RU);
- peak memory as a live-set high-water mark;
- the weak blocker-distance lower bound;
- disabling pruning when the blocker-effect map is declared incomplete;
- rejection of malformed outcome/effect contracts;
- comparison of pruned and unpruned feasibility on the same finite fixture.

It does **not** implement the optional blocker-cover LP, proof-preserving state dominance, numerical witness generation, VWEC generation, or a production DAPC checker.

## 2. Provenance and commands

The GitHub file was fetched after commit. Its content was copied into a local test file and the Git blob hash was compared:

\`\`\`text
GitHub blob:     e05a652bc3c134fbc411d1b2aceef39eaee787ee
Local blob:      e05a652bc3c134fbc411d1b2aceef39eaee787ee
\`\`\`

The hashes match exactly. The executed commands were:

\`\`\`bash
python --version
python -m unittest -v /tmp/dwaop_reference/dwaop_reference_harness_remote.py
python -m py_compile /tmp/dwaop_reference/dwaop_reference_harness_remote.py
\`\`\`

Python reported \`3.13.5\`. The unit-test run completed with 12 passed and 0 failed. Bytecode compilation also completed without error.

## 3. Test results

<badge>12 passed · 0 failed</badge>

| Test | Result | What it checks |
|---|---|---|
| Exhaustive optimum and complete branch tree | PASS | Exact unpruned oracle and pruned planner both produce the 4.0 RU two-outcome plan; the pass and fail branches terminate in ACCEPT and REJECT respectively |
| Pruned/unpruned budget sweep | PASS | Feasibility agrees at 25 RU budgets from 0.00 through 6.00 in 0.25 increments |
| Lower bound versus exact cost | PASS | The blocker-distance lower bound does not exceed the exact unpruned remaining RU cost at each non-terminal fixture state |
| Incomplete effect map | PASS | Declaring the effect map incomplete disables lower-bound pruning; a feasible plan is still found without pruning |
| Omitted blocker-removal effect | PASS | An effect map marked complete is rejected when a transition removes a blocker absent from that action's declared effect |
| Malformed outcome contract | PASS | Duplicate outcome labels are rejected |
| Incomplete outcome tree | PASS | The plan-tree validator rejects a plan with one required branch deleted |
| Sequential memory high-water mark | PASS | Live-set memory is calculated as a path maximum, not the sum of workspaces |
| Mutually exclusive branch aggregation | PASS | Additive RU and peak memory use worst-branch maxima, not sums across mutually exclusive outcomes |
| Small set-cover lower-bound example | PASS | The maximum of each blocker's cheapest resolver is no greater than the exact integral cover cost |
| Exhaustive small set-cover families | PASS | The same lower-bound property holds across all \(7^4=2{,}401\) non-empty action-cover assignments for three blockers and four actions |
| Resource-limit rejection | PASS | A plan that fits the RU budget is rejected when its peak-memory limit is exceeded |

## 4. Numeric outputs

The reference fixture contains:

- \`prepare\`: 1.0 RU;
- \`certify\`: 2.0 RU, branching to pass/fail outcomes;
- \`check_pass\` / \`check_fail\`: 1.0 RU in the respective branch.

The complete worst-case plan is:

\[
C_{\mathrm{RU}}^\uparrow
=1+\max(2+1,2+1)=4.0\ \mathrm{RU}.
\]

The unpruned exhaustive oracle also returns 4.0 RU.

The fixture's declared peak-memory values produce:

\[
M_{\mathrm{peak}}^\uparrow=2.70\ \mathrm{GB}.
\]

The blocker-distance lower bound and exact cost at each non-terminal state were:

| State | Lower bound | Exact unpruned remaining cost |
|---|---:|---:|
| Root | 2.0 RU | 4.0 RU |
| Prepared | 2.0 RU | 3.0 RU |
| Certified pass | 1.0 RU | 1.0 RU |
| Certified fail | 1.0 RU | 1.0 RU |

For the independent sequential-memory example:

\[
M_{\mathrm{peak}}^\uparrow=4.20\ \mathrm{GB},
\]

rather than the invalid sum of action workspaces, 6.50 GB.

For the mutually exclusive branch example:

\[
C_{\mathrm{RU}}^\uparrow=2+\max(2,5)=7\ \mathrm{RU},
\]

\[
M_{\mathrm{peak}}^\uparrow=\max(3,4,2)=4\ \mathrm{GB}.
\]

These values are fixture outputs, not measured GDEC solver performance.

## 5. Interpretation

The harness supports a narrow conclusion:

**For this finite reference model, the implemented blocker-distance prune preserves feasibility relative to the exhaustive unpruned search, and the implemented resource aggregation returns the expected sequential and contingent-path totals.**

The test does not prove the lower-bound rule for arbitrary action contracts or state spaces. The set-cover property test covers a finite family of small instances, while the plan-search comparison uses one hand-constructed contingent graph.

The harness's \`verify_plan_tree\` function is a test-specific structural/resource checker. It does not inspect mathematical numerical certificates, validate outer QoI enclosures, establish theorem assumptions, or provide independent engineering assurance.

## 6. Known limitations and next tests

Not yet tested:

1. randomly/generated larger contingent DAGs and cyclic action graphs;
2. proof-preserving state-dominance pruning against an exhaustive oracle;
3. scenario-tree lower bounds for branching policies;
4. the blocker-cover LP relaxation;
5. resource dimensions beyond additive RU and peak memory;
6. action failure, timeout and model-invalidation transitions at planner scale;
7. any actual FEM/CFD solver, estimator or certified bound.

The next research test should add state-dominance pruning to the reference harness and compare its result against unpruned exhaustive search over generated finite graphs. Until that comparison passes, dominance pruning remains a specification only.

## 7. Classification

- **IMPLEMENTED:** standalone finite-state reference harness.
- **EXECUTED:** 12 tests, all passing; Python 3.13.5.
- **CHECKED:** exact committed Git blob was the source of the executed test copy.
- **NOT IMPLEMENTED:** GDEC runtime controller, numerical certificate producers, trusted DAPC checker, LP pruning or state-dominance pruning.
- **NOT NUMERICALLY VERIFIED:** no FEM/CFD solve or engineering QoI bound was generated.
- **NOT INDEPENDENTLY REVIEWED:** no external reviewer has checked the algorithm or its proof assumptions.
- **NOT A NOVELTY RESULT:** no novelty, performance or patentability conclusion follows from these tests.
