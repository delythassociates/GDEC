# DSES v0.6 — Correlation-Aware Robust-Regret Envelope

**Status:** ANALYTICAL RESEARCH PROTOTYPE — NOT PHYSICALLY VALIDATED, NOT AN IBEX RUN, NOT PRODUCTION APPROVED  
**Date:** 2026-11-27  
**Branch:** \`research/dses-envelope-comparative-benchmarks-v0.6\`  
**Base:** \`402592a8af185706dbe8af3981838f3c065419c8\`

## 1. Executive result

DSES v0.6 compares a correlated unit-disk uncertainty set against its conservative independent rectangular outer set \`[-1,1]^2\`, and compares adaptive partitioning with a matched 64×64 uniform grid.

The certificate verifier recomputes each leaf's interval, support bound and classification; checks that split children exactly cover their parents; verifies total domain area; and recomputes the digest. A tamper test modifies certificate structure and recomputes the digest, demonstrating that semantic checks—not just the digest—detect the inconsistency.

**CI result:** 16 passed, 0 failed on each of Python 3.10, 3.11, 3.12 and 3.13 (64 test executions total). GitHub Actions run [45966199112](https://github.com/delythassociates/GDEC/actions/runs/45966199112), head commit `27504b268a648662f2613aaa7493a3e9e5982072`. The earlier local pre-hardening result of 10 tests is superseded by this CI evidence.

## 2. Mathematical contract

The design domain is \(X=[0,1]^2\). Define

\[
c(x,y)=2x-y-\frac12+\frac1{10}xy,\quad
a(x)=\frac2{25}(1+\frac{x}{4}),\quad
b(y)=\frac1{20}(1-\frac{3y}{20}).
\]

The decision-difference is
\[
D(x,y,\theta)=c(x,y)+a(x)\theta_1+b(y)\theta_2.
\]

Compare \(\Theta_{disk}=\{\theta:\theta_1^2+\theta_2^2\le1\}\) with the outer box \(\Theta_{box}=[-1,1]^2\), where \(\Theta_{disk}\subseteq\Theta_{box}\). For positive \(a,b\), disk support is \(\sqrt{a^2+b^2}\), box support is \(a+b\). The disk square root is rounded upward to the next \(10^{-6}\) rational grid point using integer arithmetic.

On a cell \(C=[x_l,x_u]\times[y_l,y_u]\), monotonicity gives \(c_l=c(x_l,y_u)\), \(c_u=c(x_u,y_l)\); \(a\) is maximized at \(x_u\), \(b\) at \(y_l\). This yields an outer enclosure \([D_l,D_u]\).

Regrets are \(R_A=\max(0,D+1/2)\), \(R_B=\max(0,1/2-D)\), with permitted regret \(\tau=0.35\) and margin \(m=0.15\):
- SELECT_A if \(D_u\le -m\);
- SELECT_B if \(D_l\ge m\);
- REFUSE_HIGH_REGRET if \(D_l>-m\) and \(D_u<m\);
- UNRESOLVED otherwise.

No sample point is used to classify a whole cell.

## 3. Adaptive versus uniform results

At max bisection depth 12, adaptive and uniform partition category areas match exactly for each uncertainty set.

| Method | Adaptive nodes | Adaptive leaves | Uniform cells | Node reduction vs 4,096 |
|---|---:|---:|---:|---:|
| Correlated disk | 2,339 | 1,170 | 4,096 | 42.90% |
| Independent box outer | 2,731 | 1,366 | 4,096 | 33.33% |

Correlated disk classification area:
- SELECT_A: \(1447/4096=35.3271\%\)
- SELECT_B: \(1553/4096=37.9150\%\)
- REFUSE_HIGH_REGRET: \(51/2048=2.4902\%\)
- UNRESOLVED: \(497/2048=24.2676\%\)

Independent box outer:
- SELECT_A: \(1375/4096=33.5693\%\)
- SELECT_B: \(185/512=36.1328\%\)
- REFUSE_HIGH_REGRET: 0%
- UNRESOLVED: \(1241/4096=30.2979\%\)

The box increases unresolved area by 6.03 percentage points and eliminates the whole-cell high-regret refusal class in this particular benchmark. This is consistent with a looser outer set, not a general DSES superiority theorem.

Nine local timings were measured. Median adaptive/uniform build times were approximately 0.1155/0.1401 s for the disk and 0.1080/0.1148 s for the box. Single-machine microbenchmark only; no general speed claim.

## 4. Uncertainty sensitivity

At scale 0.5/1.0/1.5, uncertainty growth generally increases unresolved area and contracts whole-cell decision regions. Exact summaries are in \`results/DSES_V06_BENCHMARK_RESULTS.json\`. At scale 1.0, disk refusal area is 0.1953% at max depth 10; the box has no high-regret refusal cells. At scale 1.5, unresolved area increases further.

## 5. Certificate semantics

Certificate includes exact rational cell bounds, partition tree, uncertainty identity, thresholds, support bound and SHA-256 digest. Verification checks schema/model, digest, split geometry, each leaf enclosure/support/classification, node/leaf counts and exact area=1.

**Hash non-claim:** the digest is unkeyed and does not authenticate the producer. Certificate claims remain conditional on the declared synthetic analytical model. They say nothing about physical model validity or omitted model-form uncertainty.

## 6. Prior-art and IBEX comparator

Robust regret and set-based design space reduction are established, including Claus and Collette's *Design Space Covering for Uncertainty* (Engineering Optimization 56(6), 2024, pp. 919–939; DOI 10.1080/0305215X.2023.2209016). IBEX 2.9 documentation describes interval contractors and \`CtcForAll\` for universally quantified parameter constraints. The native library has **not** been compiled or run here. The independent box outer approximation is not an IBEX result. A fair comparison needs an equivalent quantified formulation, matched tolerances and careful interpretation of inner/outer set semantics.

## 7. Honest novelty statement

v0.6 shows a small exact-rational correlation-aware analytical partitioner. It does not establish a novel robust optimisation algorithm. Potential contribution to investigate: joint uncertainty semantics, whole-region decision certificates, applicability/V&V obligations, provenance, and explicit unresolved/refusal states integrated into a decision-centric engine. Head-to-head comparison against DSC-U and native IBEX on shared problems is still required.

## 8. Next technical gate

1. Build IBEX 2.9.x and execute the same universal-parameter model natively.
2. Compare set contractions with the exact rational reference using compatible outer/inner semantics.
3. Add a non-monotone model whose cell extrema need interval subdivision.
4. Add applicability uncertainty and a model-form out-of-scope class.
5. Only then consider numerical PDE/thermal integration. DWR remains asymptotic and must not be used as a certificate.

## 9. Status discipline

- SPECIFIED: joint disk/box uncertainty model, robust-regret contract, whole-cell classification.
- IMPLEMENTED: exact-rational enclosure, adaptive partition, uniform comparator, certificate and semantic verifier.
- EXECUTED & TESTED: the focused baseline and certificate-hardening suites passed in the four-version CI matrix (16/16 for each Python version).
- NUMERICALLY VERIFIED: exact-rational outer enclosures for the declared synthetic model; partition coverage and certificate invariants recomputed.
- INDEPENDENTLY REVIEWED: not externally reviewed.
- NATIVE IBEX: not executed.
- PHYSICAL/FEM: not performed.
- GDEC integration/production approval: none.
