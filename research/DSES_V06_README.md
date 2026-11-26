# DSES v0.6 — Correlation-aware robust-regret envelopes

Research-only exact-rational analytical benchmark. It is not a FEM solver or physical validation result.

Model:
\`D=2x-y-1/2+(1/10)xy+a(x)theta1+b(y)theta2\`, with design \`(x,y)∈[0,1]^2\`,
\`a=(2/25)(1+x/4)\`, \`b=(1/20)(1-3y/20)\`.
Compares correlated unit disk \`theta1²+theta2²≤1\` with conservative box outer approximation \`[-1,1]²\`.
Regrets: \`R_A=max(0,D+1/2)\`, \`R_B=max(0,1/2-D)\`, limit \`tau=0.35\`.
Whole-cell decisions are SELECT_A, SELECT_B, REFUSE_HIGH_REGRET or UNRESOLVED.

Reproduce:
\`\`\`bash
PYTHONPATH=src python -m pytest -q tests/test_dses_v06.py
PYTHONPATH=src python src/run_benchmarks.py
\`\`\`

Local test result: 10 passed. Both certificates are independently semantically rechecked by the prototype verifier. The disk/box results are not a comparison against native IBEX: IBEX has not been built or run here. No FEM/physical validation, formal proof or novelty claim is established. SHA-256 is unkeyed integrity metadata, not producer authentication.
