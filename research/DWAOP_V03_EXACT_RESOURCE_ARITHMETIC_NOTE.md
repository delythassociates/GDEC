# DWAOP v0.3 exact-resource correction note

**Branch:** `research/dwaop-horizon-six-formal-gate-v0.3`  
**Scope:** finite deterministic research benchmark; not production planning or a PDE/FEM certificate.

## Defects addressed

1. The H6/H8 frontier comparison previously checked only left-only set differences. It could accept a frontier containing extra entries on the right. The comparison now requires zero differences in both directions and equal set cardinalities for pruned-vs-unpruned, unpruned-vs-exhaustive, and pruned-vs-exhaustive comparisons.
2. Resource totals were accumulated as binary floating-point values in different orders by the planner and exhaustive evaluator. This made exact frontier identity sensitive to floating-point rounding.
3. The Python CI matrix had been narrowed to 3.11 during diagnostic work. It has been restored to 3.10, 3.11, 3.12, and 3.13.

## Exact resource semantics implemented

- Numeric resource inputs are converted at the resource-contract boundary to `Fraction` using their decimal string representation. For example, a Python input written as `0.1` is interpreted as the exact decimal rational (1/10), not as the exact binary floating-point encoding of that literal.
- `ResourceVector`, `ResourceBudget`, and planner `ActionContract` normalize resource quantities to rational values.
- Sequential accumulation, branch maxima, peak-memory accounting, budget comparisons, Pareto dominance, and frontier identity therefore operate on exact rational values.
- The exhaustive evaluator independently performs per-world sequential resource accumulation with rational values before applying its world-wise maxima.

## Independence limitation

The exhaustive evaluator does not call the planner's pruning or Pareto-reduction implementation. It still shares core data types, the resource-vector container, and oracle validation with the planner. The resource accumulation order and Pareto dominance calculation remain separately implemented. This is an independent algorithmic oracle with shared trusted infrastructure, not a fully independent codebase or formal proof.

## Tests added

- Exact decimal accumulation for RU, CPU, and energy.
- Exact resource-budget boundary behavior.
- Action-contract verification after decimal-to-rational conversion.
- Direct regression that a right-only frontier entry is rejected.
- Existing H6/H8 comparisons continue to require pruned, unpruned, and exhaustive frontier equivalence.

## Verification status

- IMPLEMENTED: exact resource arithmetic and symmetric frontier equality.
- TESTS ADDED: the cases listed above, alongside existing v0.2 regression and H6/H8 gates.
- CI: the branch-scoped workflow is configured to run the full four-version Python matrix and H6/H8 campaign.
- EXECUTED / TESTED: pending an accessible workflow result; no passing result is claimed here.
- FORMAL STATUS: finite-horizon theorem remains a proof sketch, not machine-checked.
- DOMAIN STATUS: no cyclic, stochastic, continuous, PDE/FEM, or physical certificate soundness is established.
