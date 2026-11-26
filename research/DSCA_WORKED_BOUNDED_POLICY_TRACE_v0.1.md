# DSCA Worked Bounded-Mode Policy Trace v0.1

**Status:** ANALYTICAL TOY EXAMPLE — NOT A GDEC SOLVER RESULT, NOT A VALIDATED BENCHMARK  
**Workstream:** `research/decision-sufficiency-algorithm`  
**Purpose:** Hand-calculate the first deterministic pass/fail decision trace before implementing a DSCA controller.

---

## 1. What this example is intended to test

This example tests whether a decision-aware controller can:

1. stop early when a valid QoI enclosure already establishes acceptance;
2. continue computation when the enclosure crosses a decision boundary;
3. refuse to reuse a bound for a different QoI;
4. return inconclusive when the only useful next action exceeds the remaining budget.

It is deliberately a small one-dimensional steady heat-conduction problem. The example is analytically soluble, so the QoI enclosure can be derived directly. It does not test GDEC's current FEM implementation, actual error estimators, runtime, or performance.

## 2. Model and exact solution

Consider a homogeneous slab on \(0\leq x\leq L\), with constant conductivity \(k>0\), uniform volumetric heat generation \(s>0\), and equal fixed temperatures at both ends:

\[
-\frac{d}{dx}\left(k\frac{dT}{dx}\right)=s,
\qquad T(0)=T(L)=T_b.
\]

For constant \(k\), the exact solution is

\[
T(x)=T_b+\frac{s}{2k}x(L-x).
\]

The maximum occurs at the centre:

\[
T_{\max}=T\left(\frac L2\right)
=T_b+\frac{sL^2}{8k}.
\]

Use the illustrative fixed parameters:

| Parameter | Value |
|---|---:|
| Length \(L\) | \(0.1\;\mathrm m\) |
| Conductivity \(k\) | \(10\;\mathrm{W/(m\,K)}\) |
| Volumetric generation \(s\) | \(1000\;\mathrm{W/m^3}\) |
| Boundary temperature \(T_b\) | \(300\;\mathrm K\) |

Therefore,

\[
T_{\max}
=300+\frac{1000(0.1)^2}{8(10)}
=300.125\;\mathrm K.
\]

The engineering decision is whether the maximum temperature satisfies

\[
T_{\max}\leq T_{\mathrm{lim}}.
\]

The decision threshold is part of the input specification; DSCA is not allowed to change it.

## 3. A QoI-specific enclosure for uniform P1 elements

Use a uniform one-dimensional mesh with \(n\) linear elements and exact integration of the constant source. For this constant-coefficient quadratic solution, the P1 finite-element nodal values equal the exact solution at the mesh nodes. The maximum of the P1 field is therefore the greatest nodal value:

\[
T_{h,\max}=\max_j T(x_j).
\]

Let

\[
d=\min_j\left|x_j-\frac L2\right|
\]

be the distance from the true maximum location to the nearest mesh node. From the exact parabolic solution,

\[
T_{\max}-T_{h,\max}=\frac{s}{2k}d^2.
\]

Thus the exact QoI enclosure for this model and mesh is

\[
\boxed{
T_{\max}\in
\left[
T_{h,\max},
T_{h,\max}+\frac{s d^2}{2k}
\right].
}
\]

For odd \(n\), the centre lies halfway between two nodes and \(d=L/(2n)\). For even \(n\), the centre is a node and \(d=0\), so this particular maximum-temperature QoI is represented exactly by the nodal maximum.

This is a bound for **maximum temperature in this specific model**. It is not a general bound for arbitrary heat equations, nonuniform meshes, nonlinear conductivity, uncertain parameters, heat flux, stress, or other QoIs.

### Initial mesh: one element

For \(n=1\), the only nodes are the two fixed-temperature boundaries:

\[
T_{h,\max}=300\;\mathrm K,
\qquad d=0.05\;\mathrm m.
\]

The QoI error is

\[
\Delta T_{\max}
=\frac{1000(0.05)^2}{2(10)}
=0.125\;\mathrm K.
\]

Therefore,

\[
\boxed{T_{\max}\in[300.000,\;300.125]\;\mathrm K.}
\]

The exact truth \(300.125\;\mathrm K\) is contained in this enclosure.

### After one uniform bisection: two elements

For \(n=2\), the new mesh contains a node at \(x=L/2\). Hence

\[
T_{h,\max}=300.125\;\mathrm K,
\qquad d=0,
\]

and

\[
\boxed{T_{\max}\in[300.125,\;300.125]\;\mathrm K.}
\]

The maximum-temperature QoI is now exact for this idealised problem, although the piecewise-linear field is not the exact quadratic field between the nodes.

## 4. Action portfolio and illustrative resource model

The action costs below are deliberately hypothetical normalised compute units (CU). They are not measured timings and must not be used as GDEC performance claims.

| Action | Evidence channel targeted | Preconditions | Upper cost |
|---|---|---|---:|
| `A_SOLVE_TIGHTEN` | Algebraic error | Non-negligible algebraic error exists | 0.10 CU |
| `A_UNIFORM_BISECT` | Discretisation contribution to maximum-temperature QoI | This exact model and mesh-bound assumptions apply | 0.40 CU |
| `A_FLUX_BOUND` | Flux QoI | A separately derived and applicable flux bound exists | Not available in this example |

Assume the initial one-element baseline has already been computed and costs 1.00 CU. The discrete system is treated as solved exactly for this analytical trace, so there is no unresolved algebraic component for `A_SOLVE_TIGHTEN` to reduce. Its decision-ambiguity gain is zero and it is not a useful next action.

For this binary pass/fail example, define the decision-ambiguity measure:

\[
A([\underline T,\overline T])=
\begin{cases}
1,&\underline T\leq T_{\mathrm{lim}}<\overline T,\\
0,&\text{the interval lies wholly on one decision side}.
\end{cases}
\]

The value 1 means the current interval permits both pass and fail; 0 means it supports one robust decision. This indicator is tailored to a single deterministic threshold and is not a general multi-objective regret metric.

For the two-element bisection, the exact analytical outcome is known. If the initial interval straddles the threshold, then

\[
G_{\mathrm{bisect}}=A(Q_{\mathrm{before}})-A(Q_{\mathrm{after}})=1-0=1.
\]

The illustrative score is

\[
S_{\mathrm{bisect}}=\frac{1}{0.40}=2.5\;\mathrm{CU}^{-1}.
\]

The score is a ranking device only. The robust decision gate—not the score—determines whether the controller may stop.

## 5. Trace A — early acceptance without over-solving

Set

\[
T_{\mathrm{lim}}=300.20\;\mathrm K.
\]

Initial evidence:

\[
Q_0=[300.000,300.125]\;\mathrm K.
\]

Because

\[
\sup Q_0=300.125\;\mathrm K
\leq300.20\;\mathrm K,
\]

the design is robustly acceptable under the stated deterministic model and assumptions.

**Controller trace**

| Step | State | Result |
|---|---|---|
| 1 | Baseline computed | One-element P1 result and analytical QoI enclosure available |
| 2 | Evidence assessed | Algebraic component exact in this toy trace; QoI interval valid for the stated model |
| 3 | Decision tested | Entire interval is below the limit |
| 4 | Mandatory obligations | Assumed complete for this deliberately minimal example |
| 5 | Terminal | `ACCEPT` with interval \([300.000,300.125]\;\mathrm K\) |

No refinement is required to support this decision. A fixed absolute QoI-error target of \(0.01\;\mathrm K\) would not be met by the initial enclosure and would request additional work. DSCA's possible saving is therefore **decision-specific stopping**, not a better solution field.

**What this trace demonstrates:** an engineering decision can be sufficiently supported before a uniform solution-accuracy target is reached, provided the relevant bound is valid and all required obligations are complete.

## 6. Trace B — near-boundary case requires refinement

Change only the decision threshold:

\[
T_{\mathrm{lim}}=300.10\;\mathrm K.
\]

The initial interval remains

\[
Q_0=[300.000,300.125]\;\mathrm K.
\]

It crosses the limit, so neither robust acceptance nor robust rejection is supported. The controller returns an interim `INCONCLUSIVE` state and evaluates eligible actions.

- `A_SOLVE_TIGHTEN` is not useful because the algebraic component is already exact in this trace.
- `A_UNIFORM_BISECT` is eligible and has positive guaranteed ambiguity reduction.

After bisection:

\[
Q_1=[300.125,300.125]\;\mathrm K.
\]

Since

\[
\inf Q_1=300.125\;\mathrm K
>300.10\;\mathrm K,
\]

the design is robustly unacceptable under the declared constraint.

**Controller trace**

| Step | State | Result |
|---|---|---|
| 1 | Baseline computed | Initial interval \([300.000,300.125]\;\mathrm K\) |
| 2 | Decision tested | Interval crosses 300.10 K; remain inconclusive |
| 3 | Actions filtered | Solver tightening has no target error; mesh bisection is eligible |
| 4 | Budget checked | 0.40 CU is available |
| 5 | Action executed | One uniform bisection, illustrative cost 0.40 CU |
| 6 | Evidence updated | Interval tightens to \([300.125,300.125]\;\mathrm K\) |
| 7 | Decision tested | Entire interval violates the limit |
| 8 | Terminal | `REJECT` with the supporting enclosure |

The controller does not accept the original point estimate of 300 K and does not keep refining after the decision becomes robustly reject.

## 7. Trace C — estimator/bound is inapplicable to the requested QoI

Keep the same physical model, but change the requested QoI to maximum heat-flux magnitude:

\[
q_{\max}=\max_{x\in[0,L]}|{-kT'(x)}|.
\]

The enclosure derived in Section 3 is for maximum temperature. It does not bound maximum heat flux. The action descriptor `A_UNIFORM_BISECT` is not permitted to claim a flux assurance result merely because it uses the same mesh.

Assume no flux-specific bound or independent flux-verification action is available in the declared capability set.

**Required response:** `REFUSE` the requested bounded flux claim, or return `INCONCLUSIVE` if the user explicitly requested a non-assured exploratory result and that mode is permitted. Do not reuse the temperature enclosure, and do not mark the flux QoI as verified.

This trace tests action/QoI applicability, not the accuracy of any flux estimator.

## 8. Trace D — budget exhaustion while the decision remains unresolved

Return to the near-boundary threshold:

\[
T_{\mathrm{lim}}=300.10\;\mathrm K,
\qquad
Q_0=[300.000,300.125]\;\mathrm K.
\]

Assume only 0.20 CU remain. The mesh-bisection action requires an upper cost of 0.40 CU. The algebraic-tightening action costs 0.10 CU but cannot reduce the unresolved discretisation contribution in this example.

No eligible positive-gain action fits the remaining budget.

**Required response:** `INCONCLUSIVE`, with:

- current interval \([300.000,300.125]\;\mathrm K\);
- decision boundary 300.10 K;
- unresolved obligation: narrow the maximum-temperature QoI enclosure;
- candidate action: `A_UNIFORM_BISECT`;
- required upper cost: 0.40 CU;
- remaining budget: 0.20 CU;
- reason: `BUDGET_EXHAUSTED_BEFORE_DECISION_SUFFICIENCY`.

The controller must not run a zero-gain solver action merely to appear active, reduce the requested assurance level, or convert the unresolved interval into acceptance.

## 9. Trace summary

| Trace | Initial interval | Threshold / request | Action | Correct outcome |
|---|---|---|---|---|
| A — safe margin | [300.000, 300.125] K | \(T_{\max}\leq300.20\) K | None | `ACCEPT` |
| B — near boundary | [300.000, 300.125] K | \(T_{\max}\leq300.10\) K | Uniform bisection | `REJECT` after refinement |
| C — wrong QoI for bound | Temperature enclosure only | Maximum heat flux | No applicable flux action | `REFUSE` bounded flux claim |
| D — insufficient budget | [300.000, 300.125] K | \(T_{\max}\leq300.10\) K | Mesh action over budget | `INCONCLUSIVE` |

## 10. Assumptions and limitations

This worked trace is intentionally idealised:

1. one-dimensional, steady, linear conduction;
2. constant positive conductivity and constant uniform heat generation;
3. exact geometry and fixed boundary temperatures;
4. exact integration and exact arithmetic in the derivation;
5. uniform P1 mesh;
6. no uncertain inputs, model discrepancy, contact resistance, nonlinearities or transient effects;
7. the analytical nodal-value and QoI-bound identities apply only to this specified problem;
8. illustrative compute costs are assumed, not measured.

A production implementation would have to include algebraic error, quadrature error, floating-point effects, geometry/data approximation and any other required error components in the claimed enclosure. It would also need an independent implementation/check of the analytical reference and interval calculation. The example does not establish that GDEC currently supplies any of those capabilities.

## 11. What this establishes—and what it does not

**Established by hand derivation for this toy model:**

- the exact solution and exact maximum-temperature QoI;
- the stated mesh-dependent QoI enclosure;
- the four expected decision traces under the stated action and budget assumptions.

**Not established:**

- correctness of a GDEC implementation;
- general validity of the enclosure for other heat problems or QoIs;
- performance benefit on real hardware;
- optimality of the action-selection policy;
- physical validation or certification of an engineering design.

## Classification

- **ANALYTICALLY DERIVED:** exact solution and QoI-specific enclosure for the stated toy problem.
- **MANUALLY TRACED:** four controller paths under declared illustrative action costs.
- **NOT IMPLEMENTED:** no DSCA code, FEM code or benchmark harness.
- **NOT EXECUTED:** no numerical solver run.
- **NOT INDEPENDENTLY VERIFIED:** no separate checker or second derivation has reviewed this note.
- **NOT A GDEC CAPABILITY CLAIM:** this is a research test case only.
