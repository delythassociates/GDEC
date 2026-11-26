# DWAOP v0.2 — Greedy Selector Comparison and Contingent Proof Plan

**Status:** SYNTHETIC ALGORITHM TEST CASE — NOT A GDEC RUN, NOT A VALIDATED BENCHMARK  
**Algorithm:** Decision-Witness and Assurance-Obligation Planning (DWAOP)  
**Related specification:** \`research/DSCA_DWAOP_ALGORITHM_REDESIGN_v0.2.md\`

---

## 1. Test question

Does bounded look-ahead over numerical action contracts find a decision-completing action sequence that a myopic one-step selector misses?

The example isolates one behaviour:

- the only action that can produce the required bounded QoI certificate has a prerequisite;
- the prerequisite has no immediate QoI-set contraction;
- a separate independent checker is mandatory and cannot run until the certificate exists;
- a cheap heuristic action appears to improve an error indicator but cannot close the bounded decision witness or the verifier obligation.

The example is intentionally constructed to expose the limit of an immediate-gain-per-cost rule. It does **not** prove DWAOP is novel or superior to strong planning algorithms.

## 2. Decision problem and state

The engineering requirement is:

\[
T_{\max}\le T_{\mathrm{lim}},\qquad
T_{\mathrm{lim}}=300.0\ \mathrm K.
\]

A small deterministic benchmark family contains two instances whose exact QoIs are separated from the decision boundary. Before the certifiable computation, the controller has only the coarse sound enclosure:

\[
\mathcal Q_0=[299.4,300.6]\ \mathrm K.
\]

Therefore the current evidence permits both acceptance and rejection.

Mandatory obligations:

- \(o_{\mathrm{bound}}\): a deterministic, applicable enclosure for \(T_{\max}\);
- \(o_{\mathrm{independent}}\): independent checking of the enclosure, input/configuration identity and scope.

The controller cannot lower either obligation.

The benchmark family is stipulated to contain two cases:

- Case P has exact \(T_{\max}=299.7\ \mathrm K\);
- Case R has exact \(T_{\max}=300.3\ \mathrm K\).

These exact values are held by the offline reference evaluator only. They are not visible to the planner. The numerical action outcome distinguishes which case is being executed.

## 3. Candidate action contracts

All costs below are hypothetical resource units (RU), not measured execution times.

| Action | Preconditions | Possible effect | Upper cost |
|---|---|---|---:|
| \(A_{\mathrm{prep}}\): build primal/dual reconstruction state | Valid model and mesh; not yet prepared | Produces primal/dual data needed by the certifying reconstruction. Does not itself narrow \(\mathcal Q\) or discharge an obligation | 1.0 RU |
| \(A_{\mathrm{cert}}\): certified QoI reconstruction | \(A_{\mathrm{prep}}\) artefact present and applicable | Emits a deterministic outer enclosure and bound certificate. It may yield one of the two case-specific outcome cells below | 2.0 RU |
| \(A_{\mathrm{check}}\): independent certificate check | A certifying artefact from \(A_{\mathrm{cert}}\) exists | Checks scope, set enclosure, proof assumptions and provenance; discharges \(o_{\mathrm{independent}}\) only on VERIFIED | 1.0 RU |
| \(A_{\mathrm{DWR}}\): one heuristic indicator/refinement step | Existing primal/dual approximation | May reduce an asymptotic DWR indicator. Does not change the certified outer set or discharge either mandatory obligation in this example | 0.25 RU |

### 3.1 Outcomes of the certifying action

The action contract stipulates a complete two-cell outcome cover for this specific benchmark family:

\[
y_P:\quad \mathcal Q_P=[299.65,299.75]\ \mathrm K,
\]

\[
y_R:\quad \mathcal Q_R=[300.25,300.35]\ \mathrm K.
\]

The cells are disjoint and cover the benchmark family’s possible exact QoI values. The certifying action must produce an applicable mathematical enclosure for the executed case, not just a point estimate or DWR indicator.

- On \(y_P\), the interval is wholly below the limit.
- On \(y_R\), the interval is wholly above the limit.

The action does not discharge the independent-check obligation. The subsequent checker action is still mandatory in both branches.

**Critical assumption:** the complete two-cell outcome cover is part of the synthetic test contract. A real problem could produce a boundary-overlap outcome. If that outcome is possible, it must be represented as another branch and either resolved by more actions or terminated as INCONCLUSIVE. It must never be silently dropped.

## 4. Resource budget

The available budget is:

\[
B=4.5\ \mathrm{RU}.
\]

The complete plan cost is:

\[
C(A_{\mathrm{prep}},A_{\mathrm{cert}},A_{\mathrm{check}})
=1+2+1=4.0\ \mathrm{RU}\le4.5\ \mathrm{RU}.
\]

The heuristic action is not part of the certificate-producing sequence.

## 5. DWAOP plan

At the root state, the planner records:

- \(\mathcal Q_0=[299.4,300.6]\ \mathrm K\);
- one unresolved decision witness region crossing 300.0 K;
- \(o_{\mathrm{bound}}\) open;
- \(o_{\mathrm{independent}}\) open.

The relevant dependency structure is:

\[
A_{\mathrm{prep}}\prec A_{\mathrm{cert}}\prec A_{\mathrm{check}}.
\]

The bounded AND-OR planner finds the complete contingent policy:

~~~text
                         Root S0
              Q0=[299.4, 300.6] K
              bound obligation OPEN
              independent check OPEN
                          |
                    A_PREP (1 RU)
                          |
                    A_CERT (2 RU)
                          |
                 AND: two covered outcomes
                    /                 \
                  yP                   yR
                   |                    |
         QP=[299.65,299.75]   QR=[300.25,300.35]
          ACCEPT candidate          REJECT candidate
                   |                    |
             A_CHECK (1 RU)       A_CHECK (1 RU)
                   |                    |
                VERIFIED              VERIFIED
                   |                    |
                 ACCEPT                REJECT
~~~

The plan is decision-complete because both covered branches reach a valid terminal decision and satisfy the independent-check obligation.

### Branch P

\[
\sup\mathcal Q_P=299.75\ \mathrm K\le300.0\ \mathrm K.
\]

After the independent checker verifies the enclosure and its scope, the branch terminates:

\`ACCEPT\`, conditional on the declared model and benchmark contract.

### Branch R

\[
\inf\mathcal Q_R=300.25\ \mathrm K>300.0\ \mathrm K.
\]

After the independent checker verifies the enclosure and its scope, the branch terminates:

\`REJECT\`, conditional on the declared model and benchmark contract.

The DAPC contains both branches, the three action artefacts, the outcome-cover certificate, all transition certificates, both terminal decision proofs and the worst-case resource total.

## 6. Compare against myopic selectors

### 6.1 Greedy selector G1 — immediate certified blocker reduction per cost

Define a myopic score:

\[
G(a)=
\frac{\text{number/measure of blockers closed immediately by }a}
{\text{upper resource cost of }a}.
\]

At the root:

- \(A_{\mathrm{prep}}\) is enabled but closes no blocker immediately, so \(G=0\);
- \(A_{\mathrm{cert}}\) is not yet enabled because its prerequisite is absent;
- \(A_{\mathrm{check}}\) is not enabled because no certificate exists;
- \(A_{\mathrm{DWR}}\) is enabled but has no verified effect on either mandatory blocker.

A strict immediate-gain policy either stops with INCONCLUSIVE (no positive admissible action) or cannot choose the prerequisite chain. It does not discover the three-step completion policy unless it adds look-ahead, backward chaining or prerequisite-aware search.

### 6.2 Greedy selector G2 — apparent indicator reduction per cost

Suppose \(A_{\mathrm{DWR}}\) reduces a reported indicator from 0.60 K to 0.30 K for 0.25 RU.

An indicator-only policy may rank it highly. But the certified state remains:

\[
\mathcal Q_0=[299.4,300.6]\ \mathrm K,
\]

and both assurance obligations remain OPEN. The point-estimate/indicator change cannot be substituted for a deterministic enclosure.

A correctly assurance-aware selector must classify \(A_{\mathrm{DWR}}\) as \`HEURISTIC_GUIDANCE\`; it may use the action to target later work, but it cannot count it as closing either bounded blocker. A policy that claims acceptance after this step is unsound under the stated contracts.

### 6.3 Greedy selector G3 — obligation-aware but no look-ahead

An obligation-aware greedy selector knows that \(A_{\mathrm{cert}}\) is needed and that \(A_{\mathrm{check}}\) is mandatory. If it only ranks currently enabled actions by immediate verified effect, \(A_{\mathrm{prep}}\) still has zero immediate certificate/obligation gain. It may return INCONCLUSIVE even though a feasible sequence exists.

A greedy algorithm with backward chaining over action prerequisites may find the sequence. At that point it has added a planning mechanism similar to the relevant part of DWAOP. The claim tested here is only that **one-step immediate-gain ranking is insufficient** for this constructed dependency pattern.

## 7. Ablation matrix

| Policy | Prerequisite look-ahead | Evidence class respected | Mandatory checker enforced | Expected result on this test |
|---|---|---|---|---|
| Indicator-only greedy | No | No | No | May spend work on DWR and make an unsupported acceptance claim |
| Immediate certified-gain greedy | No | Yes | Yes | INCONCLUSIVE at root or fails to find the prerequisite chain |
| Obligation-aware greedy with backward chaining | Yes, limited | Yes | Yes | May find the same plan |
| DWAOP with AND-OR search and DAPC | Yes, bounded contingent search | Yes | Yes | Finds the complete two-branch plan under the stipulated contracts |

The last two rows are important. DWAOP must not be compared only with a deliberately weak greedy baseline. It must be compared with a strong prerequisite-aware planner and existing proof-carrying planning methods.

## 8. Budget and adverse-outcome variants

### 8.1 Insufficient budget

If the budget is reduced to 3.5 RU, the full sequence requires 4.0 RU. The controller returns:

\`INCONCLUSIVE: NO_COMPLETE_ASSURANCE_PLAN_WITHIN_BUDGET\`.

It must not execute \(A_{\mathrm{prep}}\) and then claim that the problem is solved.

### 8.2 Boundary-overlap outcome added

If \(A_{\mathrm{cert}}\) can produce a third outcome:

\[
y_B:\quad \mathcal Q_B=[299.9,300.1]\ \mathrm K,
\]

then the original plan is no longer decision-complete. The controller must add a supported further action for this branch or make the branch INCONCLUSIVE. Since a plan with an INCONCLUSIVE leaf is not a complete decision plan, the controller cannot claim that its original four-RU plan guarantees a terminal decision for every outcome.

### 8.3 Checker failure

If \(A_{\mathrm{check}}\) returns NOT_VERIFIED, the relevant branch is not ACCEPT or REJECT. The certificate artefact is preserved, the evidence state is marked conflicted/incomplete, and the controller may only continue with an applicable conflict-resolution action. If none exists within budget, return INCONCLUSIVE or REFUSE according to the failure cause.

## 9. What this comparison does and does not show

**It shows by construction:**

1. a prerequisite action can have zero immediate decision gain but be necessary for a later certificate-producing action;
2. a separate verifier can remain mandatory after the QoI enclosure becomes decision-resolving;
3. branch-specific outcomes require all branches to be planned and checked;
4. indicator reduction and certified decision progress are not interchangeable;
5. a strict one-step immediate-gain policy can fail to find a feasible complete policy.

**It does not show:**

- empirical runtime savings;
- superior search performance over a strong contingent planner;
- a new FEM error estimator or rigorous bound;
- that real GDEC solvers can generate these artefacts;
- novelty, patentability or freedom to operate.

## 10. Experimental falsification plan

Implement only after formal authorisation and WP0–WP7 campaign closure.

Compare:

1. immediate certified-gain greedy;
2. indicator-reduction greedy with mandatory assurance gates;
3. obligation-aware greedy with backward chaining;
4. bounded AND-OR DWAOP without pruning;
5. DWAOP with blocker-distance pruning;
6. DWAOP with blocker-cover LP relaxation;
7. DWAOP with proof-preserving state dominance.

Measure:

- fraction of cases reaching complete supported decisions;
- false ACCEPT count;
- number of states/nodes expanded;
- plan cost in every resource dimension;
- planning overhead and LP/dominance overhead;
- search timeout and INCONCLUSIVE rate;
- correctness of every pruning decision checked against an unpruned exhaustive search on small finite instances;
- DAPC checker rejection of corrupted/missing branches, wrong-scope certificates and invalid resource totals.

**Kill criterion:** if DWAOP's pruning does not reduce search effort on nontrivial finite action graphs, if it cannot beat a strong prerequisite-aware planner in end-to-end cost or decision completion, or if any invalid certificate/pruning operation produces a false ACCEPT, narrow or stop the proposal.

## 11. Classification

- **HAND-CONSTRUCTED:** decision state, action contracts, costs, branches and policy comparison.
- **ANALYTICALLY CHECKED:** interval-to-threshold decisions and total synthetic budget arithmetic.
- **NOT NUMERICALLY SIMULATED:** no FEM or CFD solve.
- **NOT IMPLEMENTED:** no planner, VWEC generator or DAPC checker.
- **NOT TESTED:** no automated greedy/DWAOP comparison.
- **NOT INDEPENDENTLY REVIEWED:** no external mathematical or planning review.
- **NOT A GDEC CAPABILITY CLAIM:** all actions and certificates are hypothetical.
