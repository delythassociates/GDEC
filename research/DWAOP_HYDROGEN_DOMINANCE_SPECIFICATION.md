# DWAOP v0.3 — Formal Mathematical Specification of Pareto Dominance, `max_actions_on_path`, and Q1–Q6 Audit

**Classification:** Research Specification (Stage 1 Read-Only Audit)  
**Target Repository:** `f:/gdec-dwaop-v03`  
**Audited Commit:** `2812b000ea0241a3aee2b5580444a7e1767c3417`  
**Audited Modules:**
- `research/prototypes/dwaop_integrated_planner.py`
- `research/prototypes/dwaop_exhaustive_policy_oracle.py`
- `research/prototypes/dwaop_horizon_ladder.py`

**Formal Status:** Manual mathematical derivation + constructive read-only Python verification. Not machine-checked in a proof assistant.

---

## Executive Summary

1. **Formal Frontier Semantics Implemented:** Both `plan_policies` (`pareto_reduce`) and `enumerate_exact_pareto_frontier` (`_oracle_pareto_reduce`) define primary Pareto dominance solely over `(world_verdict_map, resource_vector)` using exact `Fraction` arithmetic (`tol=0.0`), and then use `max_actions_on_path` as a **canonical tie-breaker** (`min max_actions_on_path`) among policies with identical `(world_verdict_map, terminal_verdicts, resource_vector)`. On any flat set of policies, this two-step rule (`_canonical_dedup` followed by `_policy_dominates`) is mathematically identical to minimal elements under the **lexicographic strict partial order** $\prec_{\mathrm{lex}}$ with $(V, R) \succ_{\mathrm{lex}} L$.
2. **Role of `max_actions_on_path`:**
   - **Not** (1) a primary Pareto objective (`_policy_dominates` and `_oracle_dominates` deliberately omit it).
   - **Bounded by** (2) the hard feasibility constraint `max_horizon` ($0 \le L(\pi) \le H$), while `max_actions_on_path` itself is a per-policy realized value rather than the constraint bound.
   - **Not** (3) purely descriptive metadata in the current implementation, because `_canonical_dedup`, `_oracle_pareto_reduce`, `NormalizedPolicy.__eq__`, `dwaop_horizon_ladder.signature()`, and `test_dwaop_v03_horizon_ladder.py` (`L124-L139`) all depend on choosing $\min L$.
   - **Currently implemented as** (4) a **canonical tie-breaker** (lexicographic secondary criterion on exact $(V, R)$ ties).
3. **Critical Mathematical Defect Discovered (Failure of Bellman Optimality under $\max$):**
   Because sibling AND-composition aggregates resources via component-wise $\max$, strict resource dominance at a subtree ($R_1 < R_2$ with $L_1 > L_2$) can be **masked** by a sibling branch ($R_{\mathrm{sib}} \ge R_2, L_{\mathrm{sib}} < L_1$), turning a strict resource gap into an exact $(V, R)$ tie at an ancestor where $L_2 < L_1$ wins! Because `plan_policies` applies `pareto_reduce` **recursively at every internal OR node** (`dwaop_integrated_planner.py:1236, 1338`), both `prune=False` and `prune=True` discard the shorter-path witness $(R_2, L_2)$ prematurely and can **diverge from `enumerate_exact_pareto_frontier`** (and `prune=True` can diverge from `prune=False`) on `max_actions_on_path`.
4. **Additional Soundness Finding in State Pruning:** Independent of `max_actions_on_path`, `is_local_refinement` (`dwaop_integrated_planner.py:848-886`) checks `model_valid`, `evidence_stale`, and `coarse_sticky`, but fails to reject `fine_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL` when `coarse_state` is a non-sticky `REFUSE` (e.g., `TIMEOUT`) with enabled recovery actions. In a 1-world graph with equal costs, `plan_policies(..., prune=True)` unsafely prunes the `ACCEPT` policy and returns only `REFUSE`.

---

## 1. Formal Mathematical Specification of the DWAOP Pareto Frontier

### 1.1 Finite-World Domain, Action Contracts, and Feasible Policy Trees

Let an instance be $(\mathcal{O}, B, H)$ where $\mathcal{O}$ is a validated `WorldOracle` (`validate_oracle`, `dwaop_integrated_planner.py:363-428`), $B \in \mathbb{Q}_{\ge 0}^4$ is a `ResourceBudget` (`dwaop_integrated_planner.py:162-184`), and $H \in \mathbb{Z}_{\ge 0}$ is `max_horizon`:

- **World Universe:** Finite non-empty set $\Omega$ (`oracle.universe`), canonically ordered $w_1 < w_2 < \dots < w_n$.
- **Ground-Truth Decisions:** $d^* : \Omega \to \{\mathrm{ACCEPT}, \mathrm{REJECT}\}$ (`oracle.decision_by_world`).
- **Exact Rational Resource Space:** Every numeric cost and budget input is normalized via `Fraction(str(x))` (`_nonnegative`, lines `30-44`) into $\mathbb{Q}_{\ge 0}^4$:
  $$R = (r_{\mathrm{ru}},\, r_{\mathrm{cpu}},\, r_{\mathrm{energy}},\, r_{\mathrm{mem}}) \in \mathbb{Q}_{\ge 0}^4.$$
- **Contingent Policy Tree $\pi$:** A finite rooted AND-OR decision tree (`PolicyTree = LeafVerdict | ActionBranch`, `dwaop_exhaustive_policy_oracle.py:50`) whose internal nodes are actions $a \in \mathcal{A}$ branching exhaustively and disjointly on observable outcome labels $\ell \in \Lambda_a(X)$ (`allow_clairvoyant_world_branching=False`), and whose leaves are terminal verdicts in $\{\mathrm{ACCEPT}, \mathrm{REJECT}, \mathrm{REFUSE}\}$.

For each world $w \in \Omega$, $\pi$ determines a unique root-to-leaf path $\tau_\pi(w) = (a_1, \ell_1), \dots, (a_k, \ell_k)$ of length $d_\pi(w) = k \in \mathbb{Z}_{\ge 0}$ and terminal leaf verdict $V(\pi)(w) \in \{\mathrm{ACCEPT}, \mathrm{REJECT}, \mathrm{REFUSE}\}$. Starting from $(r_{\mathrm{ru},0}, r_{\mathrm{cpu},0}, r_{\mathrm{energy},0}, m_0, p_0) = (0,0,0,0,0)$:
$$\begin{aligned}
r_{\mathrm{ru},j}(w) &= r_{\mathrm{ru},j-1}(w) + \mathrm{ru}(a_j), \\
r_{\mathrm{cpu},j}(w) &= r_{\mathrm{cpu},j-1}(w) + \mathrm{cpu}(a_j), \\
r_{\mathrm{energy},j}(w) &= r_{\mathrm{energy},j-1}(w) + \mathrm{energy}(a_j), \\
\mathrm{during}_j(w) &= m_{j-1}(w) + \mathrm{ws}(a_j) + \mathrm{ov}(a_j), \\
m_j(w) &= \max\!\bigl(0,\; m_{j-1}(w) + \mathrm{ret}(a_j,\ell_j) - \mathrm{rel}(a_j,\ell_j)\bigr), \\
p_j(w) &= \max\!\bigl(p_{j-1}(w),\; \mathrm{during}_j(w),\; m_j(w)\bigr).
\end{aligned}$$
Let $R_w(\pi) = (r_{\mathrm{ru},k}(w), r_{\mathrm{cpu},k}(w), r_{\mathrm{energy},k}(w), p_k(w)) \in \mathbb{Q}_{\ge 0}^4$.

**Admissible (Feasible) Policy Set $\Pi_{H,B}$:** A policy tree $\pi$ belongs to $\Pi_{H,B}$ iff for every world $w \in \Omega$:
1. **Horizon constraint:** $d_\pi(w) \le H$.
2. **Precondition, one-shot/retry, and budget invariants:** At every step $1 \le j \le d_\pi(w)$, action $a_j$ is enabled (worlds $\subseteq \mathrm{app}(a_j)$, capabilities/obligations satisfied, retry budget sufficient, not already consumed unless `BOUNDED_RETRY`), and every prefix resource vector satisfies $(r_{\mathrm{ru},j}(w), r_{\mathrm{cpu},j}(w), r_{\mathrm{energy},j}(w), p_j(w)) \le B$ component-wise with zero tolerance (`tol=0.0`).
3. **Sound leaf verdict (`terminal_verdict` / `_evaluate_tree_on_world`):**
   - $V(\pi)(w) = \mathrm{ACCEPT} \iff d^*(w) = \mathrm{ACCEPT} \land O_k(w) = \varnothing \land \mathrm{valid}_k(w) \land \neg\mathrm{stale}_k(w) \land \mathrm{kind}_k(w) \notin \mathcal{K}_{\mathrm{fail}}$.
   - $V(\pi)(w) = \mathrm{REJECT} \iff d^*(w) = \mathrm{REJECT} \land O_k(w) = \varnothing \land \mathrm{valid}_k(w) \land \neg\mathrm{stale}_k(w) \land \mathrm{kind}_k(w) \notin \mathcal{K}_{\mathrm{fail}}$.
   - $V(\pi)(w) = \mathrm{REFUSE} \iff \neg\mathrm{valid}_k(w) \lor \mathrm{stale}_k(w) \lor \mathrm{kind}_k(w) \in \mathcal{K}_{\mathrm{fail}}$ (with immediate termination forced when $\neg\mathrm{valid}_k(w) \lor \mathrm{stale}_k(w) \lor \mathrm{kind}_k(w) = \mathrm{UNRECOVERABLE\_REFUSAL}$).

*(Note: `plan_policies` also permits an optional `initial_state` parameter at line `1166`; when `initial_state` is non-root with `resource_spent > 0`, `additional_vec` omits initial additive costs while `total_vec` includes them for budget checking. Under the standard root `make_initial_state(oracle)`, `additional_vec == total_vec == worst_vec`.)*

### 1.2 Canonical Policy Signature

Each feasible policy $\pi \in \Pi_{H,B}$ induces a `NormalizedPolicy` (`dwaop_integrated_planner.py:333-340`):
$$\sigma(\pi) = \bigl(V(\pi),\; R(\pi),\; T(\pi),\; L(\pi)\bigr)$$
where:
- $V(\pi) = \bigl((w_1, V(\pi)(w_1)), \dots, (w_n, V(\pi)(w_n))\bigr)$ (`world_verdict_map`),
- $R(\pi) = \bigl(\max_{w \in \Omega} R_{w,1}(\pi), \dots, \max_{w \in \Omega} R_{w,4}(\pi)\bigr) \in \mathbb{Q}_{\ge 0}^4$ (`resource_vector`),
- $T(\pi) = \{V(\pi)(w) : w \in \Omega\}$ (`terminal_verdicts`, a deterministic projection of $V(\pi)$),
- $L(\pi) = \max_{w \in \Omega} d_\pi(w) \in \{0, \dots, H\}$ (`max_actions_on_path`).

Because $T(\pi)$ is functionally determined by $V(\pi)$, the effective signature space is $(V(\pi), R(\pi), L(\pi))$.

### 1.3 Verdict and Resource Dominance Partial Orders

1. **Per-World Verdict Order $\preceq_V$ (`_verdict_no_worse`, lines `1081-1084`; `_oracle_verdict_no_worse`, lines `276-279`):**
   $$\mathrm{ACCEPT} \prec_V \mathrm{REFUSE}, \qquad \mathrm{REJECT} \prec_V \mathrm{REFUSE}, \qquad v \preceq_V v \;\forall v,$$
   with $\mathrm{ACCEPT}$ and $\mathrm{REJECT}$ incomparable (and for any fixed world $w$, any feasible policy can emit only $d^*(w)$ or $\mathrm{REFUSE}$). This relation is reflexive, antisymmetric, and transitive—a partial order. Extending pointwise to $\Omega$:
   $$V_1 \preceq_V V_2 \iff \forall w \in \Omega,\; V_1(w) \preceq_V V_2(w).$$
2. **Exact 4D Resource Order $\le$ (`dominates_or_equal` / `strictly_dominates` with `tol=0.0`, lines `127-147`):**
   $$R_1 \le R_2 \iff \forall i \in \{1,2,3,4\},\; R_{1,i} \le R_{2,i}, \qquad R_1 < R_2 \iff (R_1 \le R_2) \land (R_1 \neq R_2).$$
3. **Primary Objective Dominance $\prec_{VR}$ (`_policy_dominates`, lines `1087-1098`; `_oracle_dominates`, lines `286-296`):**
   $$(V_1, R_1) \prec_{VR} (V_2, R_2) \iff V_1 \preceq_V V_2 \;\land\; R_1 \le R_2 \;\land\; (V_1, R_1) \neq (V_2, R_2).$$

### 1.4 Two Formal Frontier Definitions: Quotient $\mathcal{F}_{VR}$ vs. Lexicographic $\mathcal{F}_{\mathrm{lex}}$

Depending on whether `max_actions_on_path` is excluded from frontier identity (Role 3) or used as a canonical tie-breaker (Role 4), there are two distinct mathematical frontiers over $\Sigma_{H,B} = \{\sigma(\pi) : \pi \in \Pi_{H,B}\}$:

1. **Primary-Objective Quotient Frontier $\mathcal{F}_{VR}$ (Role 3):**
   Define the equivalence relation $\pi_1 \sim_{VR} \pi_2 \iff (V(\pi_1), R(\pi_1)) = (V(\pi_2), R(\pi_2))$. The Pareto frontier in objective space is the set of minimal equivalence classes:
   $$\mathcal{F}_{VR}(\Pi_{H,B}) = \min_{\prec_{VR}} \bigl\{ (V(\pi), R(\pi)) : \pi \in \Pi_{H,B} \bigr\}.$$
   Here `max_actions_on_path` is **not** part of frontier identity.

2. **Lexicographic Tie-Broken Frontier $\mathcal{F}_{\mathrm{lex}}$ (Role 4 — what `pareto_reduce` and `_oracle_pareto_reduce` compute globally):**
   Define the lexicographic strict partial order on $(V, R, L)$:
   $$(V_1, R_1, L_1) \prec_{\mathrm{lex}} (V_2, R_2, L_2) \iff (V_1, R_1) \prec_{VR} (V_2, R_2) \;\lor\; \bigl((V_1, R_1) = (V_2, R_2) \land L_1 < L_2\bigr).$$
   **Lemma 1 (Strict Partial Order):** Because $\preceq_V$, $\le$ on $\mathbb{Q}_{\ge 0}^4$, and $<$ on $\mathbb{Z}_{\ge 0}$ are antisymmetric and transitive, $\prec_{\mathrm{lex}}$ is irreflexive and transitive (a strict partial order).  
   **Theorem 1 (Exact Correspondence with `pareto_reduce` / `_oracle_pareto_reduce`):** For any finite set $S$ of `NormalizedPolicy` objects satisfying $T(\pi) = \mathrm{im}(V(\pi))$,
   $$\mathrm{pareto\_reduce}(S) = \mathrm{sorted}\Bigl(\min_{\prec_{\mathrm{lex}}} \bigl\{(V(\pi), R(\pi), T(\pi), L(\pi)) : \pi \in S\bigr\}\Bigr).$$
   *Proof:* `_canonical_dedup` (`lines 1101-1121`) partitions $S$ by $(V, T, R)$ and keeps exactly one element per class with $L^* = \min \{L(\pi) : \pi \in \text{class}\}$, eliminating all elements with $(V_1, R_1) = (V_2, R_2)$ and $L_1 < L_2$ (plus duplicates with $L_1 = L_2$). Since $(V, R)$ dominance depends only on $(V, R)$, the second pass filtering by `_policy_dominates` (`lines 1128-1133`) retains an element iff no element in $S$ has $(V', R') \prec_{VR} (V, R)$ and no element in its $(V, R)$-class has $L' < L$. Sorting by `(V, R, L)` produces a unique canonical tuple. $\blacksquare$

### 1.5 Non-Separability Theorem (Why Subtree `pareto_reduce` Fails $\mathcal{F}_{\mathrm{lex}}$)

At any internal AND-node applying action $a$ over observable outcome branches $i = 1, \dots, m$ with child policies $\pi_i$, the combined signature is:
$$\Phi_a(\pi_1, \dots, \pi_m) = \Bigl(\bigsqcup_{i=1}^m V(\pi_i),\;\; c_{\mathrm{add}}(a) + \max_{i=1}^m R(\pi_i),\;\; 1 + \max_{i=1}^m L(\pi_i)\Bigr)$$
where $c_{\mathrm{add}}(a) = (\mathrm{ru}(a), \mathrm{cpu}(a), \mathrm{energy}(a), 0)$ and root `peak_memory_gb` at leaves already carries $\max$ over ancestor steps (`dwaop_integrated_planner.py:1207, 1310`).

**Theorem 2 (Failure of Bellman's Principle for $\prec_{\mathrm{lex}}$, Preservation for $\preceq_{VRL}$):**
1. **$\prec_{\mathrm{lex}}$ is NOT monotone under $\Phi_a$:** If $(V_1, R_1) \prec_{VR} (V_2, R_2)$ and $L_1 > L_2$ at child branch $1$, then $(V_1, R_1, L_1) \prec_{\mathrm{lex}} (V_2, R_2, L_2)$. However, if sibling branch $2$ has a policy $\pi_{\mathrm{sib}}$ with $R(\pi_{\mathrm{sib}}) \ge R_2$ and $L(\pi_{\mathrm{sib}}) < L_1$, then
   $$\max(R_1, R(\pi_{\mathrm{sib}})) = R(\pi_{\mathrm{sib}}) = \max(R_2, R(\pi_{\mathrm{sib}})),$$
   while $1 + \max(L_1, L(\pi_{\mathrm{sib}})) = 1 + L_1 > 1 + \max(L_2, L(\pi_{\mathrm{sib}}))$. Thus $\Phi_a(\pi_2, \pi_{\mathrm{sib}}) \prec_{\mathrm{lex}} \Phi_a(\pi_1, \pi_{\mathrm{sib}})$—**reversing** the preference at the parent!
2. **Product partial order $\preceq_{VRL}$ IS monotone under $\Phi_a$:** Define
   $$(V_1, R_1, L_1) \preceq_{VRL} (V_2, R_2, L_2) \iff V_1 \preceq_V V_2 \;\land\; R_1 \le R_2 \;\land\; L_1 \le L_2.$$
   Because disjoint-world union $\bigsqcup$, addition $+$, and component-wise $\max$ are all monotone in $(V, R, L)$ jointly, $\pi_i' \preceq_{VRL} \pi_i$ for all $i$ implies $\Phi_a(\pi_1', \dots, \pi_m') \preceq_{VRL} \Phi_a(\pi_1, \dots, \pi_m)$. Moreover, $\min_{\prec_{\mathrm{lex}}} S \subseteq \min_{\prec_{VRL}} S$ for every finite set $S$ (since $p \prec_{VRL} q \implies p \prec_{\mathrm{lex}} q$).
   **Corollary (Internal $\preceq_{VRL}$ Soundness for Unpruned and Pruned Search):**
   1. *Unpruned equivalence ($\mathcal{P}_{\mathrm{unpruned}} = \mathcal{P}_{\mathrm{oracle}}$):* Computing $\preceq_{VRL}$-minimal frontiers at internal OR nodes and reducing by $\prec_{\mathrm{lex}}$ **only at the root** yields the exact global $\mathcal{F}_{\mathrm{lex}}$ frontier; whereas reducing by $\prec_{\mathrm{lex}}$ (`pareto_reduce`) at internal OR nodes does **not**.
   2. *Pruned equivalence ($\mathcal{P}_{\mathrm{pruned}} = \mathcal{P}_{\mathrm{unpruned}}$):* Assume sticky-refusal enforcement (Section 5, item 2) and internal $\preceq_{VRL}$ reduction at OR nodes. By induction on remaining horizon $h \in \{0, \dots, H\}$, `is_local_refinement(fine_s, coarse_s, ..., h)` guarantees that every budget-feasible complete policy $T_c$ from `coarse_s` of depth $\le h$ is matched by a policy $T_f$ retained in `_search(fine_s, h)` with $V(T_f) \preceq_V V(T_c)$, $R(T_f) \le R(T_c)$, and $L(T_f) \le L(T_c)$:
      - *Base / terminal case ($h = 0$ or terminal `coarse_term`):* `is_local_refinement` (`L857-875`) enforces `fine_term == coarse_term` with `fine_s.resource_spent <= coarse_s.resource_spent` (`L850`), so `fine_s` emits the matching leaf with $L_f = 0 \le L_c$.
      - *Inductive step ($h > 0$, non-terminal `coarse_s` or recoverable `REFUSE` with action `right_action`):* `is_local_refinement` (`L899-929`) yields an enabled `left_action` with 5D bounds $\le$ `right_action` such that each fine child `lt.state` maps to a unique coarse child `rt.state` satisfying `lt.state.resource_spent <= rt.state.resource_spent` and `is_local_refinement(..., h - 1)`. By the induction hypothesis, `_search(lt.state, h - 1)` retains a $\preceq_{VRL}$-no-worse continuation $T_{f,lt}^*$ for each `lt` (because $\preceq_{VRL}$-domination preserves all three coordinates $V, R, L$ simultaneously). Composing `left_action` via $\Phi_{\mathrm{left}}$ preserves $V$, $R$ (including budget feasibility at every prefix since `lt.state.resource_spent <= rt.state.resource_spent`), and $L = 1 + \max_{lt} L(T_{f,lt}^*) \le 1 + \max_{rt} L(T_{c,rt}) = L(T_c)$.
      - *Cover step (`is_complete_refinement_cover`, `L983-1078`):* Because `fine_children` share `parent` with `coarse_state`, checking `child.resource_spent <= coarse_state.resource_spent` (`L850`) enforces `fine_contract` additive costs $\le$ `coarse_contract` additive costs, and exact disjoint union coverage `seen_worlds == coarse_state.worlds` (`L1071`) composes the per-sibling $\preceq_{VRL}$ witnesses into a $\preceq_{VRL}$-no-worse policy under `fine_contract`. Hence pruning `coarse_contract` cannot remove a root $\mathcal{F}_{\mathrm{lex}}$-minimal element. $\blacksquare$

---

## 2. Evaluation of `max_actions_on_path` Across the Four Candidate Roles

| Candidate Role | Definition | Implemented in Current Code? | Mathematically Consistent As-Is? | Verdict |
|---|---|---|---|---|
| **(1) Pareto objective** | Minimize $L(\pi)$ simultaneously with $V(\pi)$ and $R(\pi)$ (`_policy_dominates` checks $L_1 \le L_2$) | **No.** `_policy_dominates` (`L1087-1098`) and `_oracle_dominates` (`L286-296`) ignore $L(\pi)$. | Would retain expensive short paths alongside cheap long paths; conflicts with 4D `ResourceVector` design. | **Rejected** (not intended and not implemented). |
| **(2) Hard feasibility constraint** | Enforce $L(\pi) \le H$ (`max_horizon`) | **Partially (`max_horizon` is, `max_actions_on_path` is not).** `depth_left == 0` enforces $L(\pi) \le H$; `max_actions_on_path` is a realized output field in $[0, H]$. | Necessary feasibility bound on $\Pi_{H,B}$, but does not explain why `max_actions_on_path` is minimized in `_canonical_dedup` and checked in `signature()`. | **Incomplete description** (describes $H$, not the per-policy field $L(\pi)$). |
| **(3) Descriptive metadata** | Diagnostic attribute on a witness policy; excluded from dominance and frontier identity | **No.** `_canonical_dedup` (`L1104-1111`), `_oracle_pareto_reduce` (`L302-305`), `NormalizedPolicy.__eq__`, and `signature()` (`dwaop_horizon_ladder.py:108`) all depend on `max_actions_on_path`. | **Only** consistent if `pareto_frontier` equality projects out `max_actions_on_path` (comparing $\mathcal{F}_{VR}$ rather than `NormalizedPolicy` tuples). | **Not currently implemented**, though valid if frontier equality is redefined over $(V, R)$. |
| **(4) Tie-breaker** | Secondary lexicographic minimization of $L(\pi)$ only among policies tied on $(V(\pi), R(\pi))$ | **Yes at root (`pareto_reduce` / `_oracle_pareto_reduce`)**, explicitly tested in `test_dwaop_v03_horizon_ladder.py:124-139`. | **Inconsistent in `plan_policies` (`_search`):** internal OR-node `pareto_reduce` breaks Bellman optimality under $\max$ (Theorem 2). Fixable cleanly by reducing under $\preceq_{VRL}$ internally and $\prec_{\mathrm{lex}}$ at root. | **Primary intended role in v0.3**, requiring internal $\preceq_{VRL}$ fix (or formal downgrade to Role 3). |

---

## 3. Rigorous Answers to Q1–Q6

### Q1. Is maximum path action count an optimization objective?
**Answer:**
- **Not a primary Pareto objective:** In DWAOP v0.2/v0.3, the primary Pareto objectives are strictly per-world verdict quality $V(\pi)$ and the 4D exact rational `ResourceVector` $R(\pi) = (r_{\mathrm{ru}}, r_{\mathrm{cpu}}, r_{\mathrm{energy}}, r_{\mathrm{mem}})$. Neither `_policy_dominates` (`dwaop_integrated_planner.py:1087-1098`) nor `_oracle_dominates` (`dwaop_exhaustive_policy_oracle.py:286-296`) includes `max_actions_on_path` in dominance checks. Every modeled physical/computational cost of taking an action is already accounted for in $R(\pi)$.
- **Yes as a secondary (lexicographic) tie-breaker:** Whenever two policies have identical $(V(\pi), R(\pi))$, both `_canonical_dedup` (`L1110`) and `_oracle_pareto_reduce` (`L304`) minimize `max_actions_on_path`. Mathematically, on a flat policy set, this realizes lexicographic dominance $\prec_{\mathrm{lex}}$ with $(V, R) \succ_{\mathrm{lex}} L$, bounded by the hard feasibility constraint $L(\pi) \le H$ (`max_horizon`).

### Q2. Should a policy with lower resources but more actions dominate a policy with higher resources but fewer actions?
**Answer: Yes** (assuming no-worse verdicts $V(\pi_1) \preceq_V V(\pi_2)$ and component-wise $R(\pi_1) < R(\pi_2)$).  
*Justification:* Under DWAOP's finite-horizon contract semantics, all execution costs (`ru_upper`, `cpu_ticks`, `energy_ticks`, `workspace_gb_upper`, `overlap_gb_upper`, `retained_output_gb_upper`) are explicitly tracked in the 4D `ResourceVector`, and horizon admissibility ($L(\pi) \le H$) is already enforced as a hard constraint. A multi-step contingent refinement policy that achieves the same or better verdicts with strictly lower worst-case resources across all four dimensions is strictly preferable to a coarser, costlier single-step policy; refusing dominance on action count would turn step count into a 5th Pareto objective and clutter the frontier with resource-dominated policies. Both `_policy_dominates` and `_oracle_dominates` currently enforce this (`cheap_long` dominates `exp_short`, verified in Section 4). *(If step count / sequential latency were ever an unmodeled physical cost, it should be modeled as an explicit resource dimension or bounded via `max_horizon`, not left implicit.)*

### Q3. If two policies have identical verdict maps and resource vectors but different maximum path lengths, should both remain on the frontier?
**Answer: No.**  
*Justification:* Two policies $\pi_1, \pi_2$ with $V(\pi_1) = V(\pi_2)$ and $R(\pi_1) = R(\pi_2)$ occupy the exact same point in primary objective space $(V, R)$ and offer no distinct verdict-resource trade-off. Retaining multiple payoff-identical representatives would make the frontier non-canonical and sensitive to action enumeration/naming order. Under the implemented canonical tie-breaking specification (Role 4, $\mathcal{F}_{\mathrm{lex}}$), only the single representative with minimum `max_actions_on_path` is retained—which is deterministic because `NormalizedPolicy` has no other distinguishing fields (`(V, R, T, L)` uniquely identifies the dataclass value). Under the alternative metadata-only design (Role 3, $\mathcal{F}_{VR}$), only one equivalence class $[(V, R)]$ remains on the frontier regardless, with `max_actions_on_path` excluded from frontier equality. In neither consistent design do both policies remain on the frontier.

### Q4. Does the current canonical deduplication rule implement the intended answer to Q3 consistently?
**Answer: Locally yes (on a flat policy list), globally NO (inside `plan_policies`'s recursive `_search`).**  
*Detailed Audit:*
1. **Flat-set behavior (`_canonical_dedup`, `L1101-1121`; `_oracle_pareto_reduce`, `L299-311`):** Given any flat collection of valid `NormalizedPolicy` objects, `_canonical_dedup` keys on `(world_verdict_map, terminal_verdicts, resource_vector.exact_key())` and keeps the policy with minimum `max_actions_on_path`, returning a canonically sorted tuple. (Note: `terminal_verdicts` is functionally redundant in the key since `terminal_verdicts == frozenset(v for _, v in world_verdict_map)` for all planner/oracle outputs.) This satisfies Q3 on flat sets and matches `test_dwaop_v03_horizon_ladder.py:124-139`.
2. **Global inconsistency in `plan_policies` (`_search`, `L1236, L1338`):** `plan_policies` calls `pareto_reduce(complete_here)` at **every internal OR node** before propagating sub-policies upward through $\Phi_a$. By Theorem 2, $\prec_{\mathrm{lex}}$ is not monotone under sibling $\max$: when a subtree has $\pi_1 = (V, R_1, L_1)$ and $\pi_2 = (V, R_2, L_2)$ with $R_1 < R_2$ and $L_1 > L_2$, internal `pareto_reduce` discards $\pi_2$. If an ancestor later combines that branch with a sibling having $R_{\mathrm{sib}} \ge R_2$ and $L_{\mathrm{sib}} < L_1$, $\pi_2$ would have tied $\pi_1$ on $(V, R)$ at the root and won the tie-breaker ($L_2 < L_1$). Consequently, `plan_policies(..., prune=False)` returns a policy with **strictly larger `max_actions_on_path`** than `enumerate_exact_pareto_frontier` (Section 4, Check 3: `4` vs `2`)!

### Q5. Does the state-level pruning relation preserve the relevant action-count information?
**Answer: Partially at the single-state simulation level, and NO at the integrated planner level (when `max_actions_on_path` is part of frontier equality).**  
*Detailed Audit:*
1. **Raw simulation relation (`is_local_refinement`, `L826-929`; `is_complete_refinement_cover`, `L983-1078`):** `is_local_refinement` does not inspect `provenance_depth` or `max_actions_on_path` explicitly, **but** it is indexed by `depth_left` and matches every enabled `coarse_state` action 1-for-1 with a `fine_state` action over `depth_left - 1` (and requires `fine_term == coarse_term` when `coarse_term` is terminal, rejecting `fine_term in {"ACCEPT", "REJECT"}` when `coarse_term` is non-terminal). Therefore, whenever `is_local_refinement(fine_s, coarse_s, ..., depth_left)` holds soundly, every coarse continuation $T_c$ of depth $\le d$ is simulated by a fine continuation $T_f$ with $V(T_f) \preceq_V V(T_c)$, $R(T_f) \le R(T_c)$, **and $L(T_f) \le L(T_c)$**.
2. **Integrated failure with bottom-up `pareto_reduce` (`prune=True` vs `prune=False`):** Because `_search(fine_child)` reduces its returned frontier using `pareto_reduce` (rather than $\preceq_{VRL}$), `_search(fine_child)` can **discard** the short-path simulated witness $T_f$ in favor of a resource-cheaper, longer-path policy $T_f'$ ($R(T_f') < R(T_f)$, $L(T_f') > L(T_f)$). Once `is_complete_refinement_cover` prunes `coarse_act`, a sibling branch with $R_{\mathrm{sib}} \ge R(T_f)$ masks $T_f'$'s resource advantage, causing `plan_policies(..., prune=True)` to emit a strictly larger `max_actions_on_path` than `plan_policies(..., prune=False)` and `enumerate_exact_pareto_frontier` (Section 4, Check 4: `pruned` gives `4`, `unpruned == oracle` gives `2`)!
3. **Separate soundness gap (`UNRECOVERABLE_REFUSAL`):** Independently of action counts, `is_local_refinement` (`L848-886`) does not reject `fine_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL` when `coarse_state` is a non-sticky `REFUSE` with enabled recovery actions (because `_enabled` and `apply_action_outcome` do not check `UNRECOVERABLE_REFUSAL`, whereas `_search` at `L1230` halts immediately). In equal-cost 1-world graphs, `prune=True` unsafely prunes the `ACCEPT` continuation (Section 4, Check 5).

### Q6. Is the exhaustive oracle independently checking the same mathematical objective, or reproducing the same potentially incomplete objective definition?
**Answer: It reproduces the same potentially incomplete objective definition—but evaluates it globally rather than bottom-up.**  
*Detailed Audit:*
- **Same objective definition:** `dwaop_exhaustive_policy_oracle.py` (`_oracle_verdict_no_worse` `L276-279`, `_oracle_dominates` `L286-296`, `_oracle_pareto_reduce` `L299-311`) implements an independent codebase copy of the exact same rules as `dwaop_integrated_planner.py`: `max_actions_on_path` is excluded from `_oracle_dominates`, used as `min(max_actions_on_path)` tie-breaking inside `_oracle_pareto_reduce`, and included in `NormalizedPolicy` equality. Thus, the oracle does **not** independently resolve whether `max_actions_on_path` is Role 3 (metadata) or Role 4 (lexicographic tie-breaker).
- **Critical operational difference (Root-only vs. Internal OR-node reduction):** Because `enumerate_exact_pareto_frontier` enumerates all complete trees globally and applies `_oracle_pareto_reduce` **only once at the root**, it computes the true global $\mathcal{F}_{\mathrm{lex}}$ frontier. By contrast, `plan_policies` (even with `prune=False`) applies `pareto_reduce` at every internal OR node, so **the oracle and unpruned planner do not even implement the same global mathematical function on general graphs** (Theorem 2; Section 4, Check 3). Existing v0.2/v0.3 test suites passed because none of their fixtures combined a child $(R_1 < R_2, L_1 > L_2)$ trade-off with a cost-masking sibling branch.

---

## 4. Reproducible Read-Only Verification Evidence

All checks below were executed on commit `2812b000ea0241a3aee2b5580444a7e1767c3417` using `f:/fem-edit-benchmark/.venv/Scripts/python.exe` without modifying any repository source or test files.

### 4.1 Checks 1–2 & 5: Dominance Direction, Exact Tie Deduplication, and Sticky-Refusal Soundness Edge Case

Command:
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'f:/gdec-dwaop-v03')
from research.prototypes.dwaop_integrated_planner import (
    ActionSemantics, OutcomeKind, ResourceBudget, ResourceVector,
    NormalizedPolicy, WorldOracle, plan_policies, pareto_reduce, _policy_dominates
)
from research.prototypes.dwaop_exhaustive_policy_oracle import (
    enumerate_exact_pareto_frontier, _oracle_dominates, _oracle_pareto_reduce
)

u = frozenset({'w0'})
dec = {'w0': 'ACCEPT'}
def act(aid, sk, kind, req_cap=frozenset(), req_ob=frozenset(), gain=frozenset(), dis=frozenset(), ru=1.0):
    lbl = aid + '_lbl'
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=u,
        observable_label_by_world={'w0': lbl},
        required_capabilities=req_cap, required_obligations=req_ob,
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'f'}),
        ru_upper=ru, cpu_ticks=1.0, energy_ticks=1.0,
        workspace_gb_upper=0.1, overlap_gb_upper=0.0,
        outcome_kind_by_label={lbl: kind},
        discharged_by_label={lbl: dis},
        capabilities_by_label={lbl: gain},
        retained_output_gb_by_label={lbl: 0.0},
        released_memory_gb_by_label={lbl: 0.0},
        invalidates_model_by_label={lbl: False},
        stale_evidence_by_label={lbl: False},
        retry_cost_by_label={lbl: 0},
        proof_id_by_label={lbl: 'p_' + aid},
    )

oracle_eq = WorldOracle(
    specification_id='s', model_id='m', assurance_scope='a',
    universe=u, decision_by_world=dec,
    initial_obligations=frozenset({'ob'}),
    actions={
        'a_fine': act('a_fine', 'op', OutcomeKind.UNRECOVERABLE_REFUSAL, gain=frozenset({'rec'}), ru=1.0),
        'b_coarse': act('b_coarse', 'op', OutcomeKind.TIMEOUT, gain=frozenset({'rec'}), ru=1.0),
        'recover': act('recover', 'rec_op', OutcomeKind.SUCCESS, req_cap=frozenset({'rec'}), dis=frozenset({'ob'}), ru=1.0),
    }
)
budget = ResourceBudget(10.0, 100.0, 100.0, 10.0)
p = plan_policies(oracle_eq, budget, max_horizon=3, prune=True)
up = plan_policies(oracle_eq, budget, max_horizon=3, prune=False)
ex = enumerate_exact_pareto_frontier(oracle_eq, budget, max_horizon=3)
print('EQ RU match:', p.pareto_frontier == up.pareto_frontier == ex, 'prunes:', p.metrics.successful_prunes)
print('  pruned:', p.pareto_frontier)
print('  oracle:', ex)

p_cheap_long = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT'}), 5)
p_exp_short = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=2.0), frozenset({'ACCEPT'}), 1)
print('cheap_long dominates exp_short:', _policy_dominates(p_cheap_long, p_exp_short), _oracle_dominates(p_cheap_long, p_exp_short))
print('pareto_reduce([cheap_long, exp_short]):', pareto_reduce([p_cheap_long, p_exp_short]))

p_tie_long = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT'}), 5)
p_tie_short = NormalizedPolicy((('w0', 'ACCEPT'),), ResourceVector(ru_upper=1.0), frozenset({'ACCEPT'}), 2)
print('tie_short dominates tie_long:', _policy_dominates(p_tie_short, p_tie_long), _oracle_dominates(p_tie_short, p_tie_long))
print('pareto_reduce([tie_long, tie_short]):', pareto_reduce([p_tie_long, p_tie_short]))
print('_oracle_pareto_reduce([tie_long, tie_short]):', _oracle_pareto_reduce([p_tie_long, p_tie_short]))
"
```
Observed output:
```text
EQ RU match: False prunes: 1
  pruned: (NormalizedPolicy(world_verdict_map=(('w0', 'REFUSE'),), resource_vector=ResourceVector(ru_upper=Fraction(1, 1), cpu_ticks=Fraction(1, 1), energy_ticks=Fraction(1, 1), peak_memory_gb=Fraction(1, 10)), terminal_verdicts=frozenset({'REFUSE'}), max_actions_on_path=1),)
  oracle: (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'),), resource_vector=ResourceVector(ru_upper=Fraction(2, 1), cpu_ticks=Fraction(2, 1), energy_ticks=Fraction(2, 1), peak_memory_gb=Fraction(1, 10)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2), NormalizedPolicy(world_verdict_map=(('w0', 'REFUSE'),), resource_vector=ResourceVector(ru_upper=Fraction(1, 1), cpu_ticks=Fraction(1, 1), energy_ticks=Fraction(1, 1), peak_memory_gb=Fraction(1, 10)), terminal_verdicts=frozenset({'REFUSE'}), max_actions_on_path=1))
cheap_long dominates exp_short: True True
pareto_reduce([cheap_long, exp_short]): (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'),), resource_vector=ResourceVector(ru_upper=Fraction(1, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=5),)
tie_short dominates tie_long: False False
pareto_reduce([tie_long, tie_short]): (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'),), resource_vector=ResourceVector(ru_upper=Fraction(1, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2),)
_oracle_pareto_reduce([tie_long, tie_short]): (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'),), resource_vector=ResourceVector(ru_upper=Fraction(1, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2),)
```

### 4.2 Check 3: Minimal 2-World Counterexample Where `unpruned != oracle` (Bellman Failure of Subtree `pareto_reduce`)

Command:
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'f:/gdec-dwaop-v03')
from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier

u = frozenset({'w0', 'w1'})
dec = {'w0': 'ACCEPT', 'w1': 'ACCEPT'}
def act(aid, sk, app, obs, req_cap=frozenset(), gain=frozenset(), dis=frozenset(), ru=0.0):
    labels = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=app,
        observable_label_by_world=obs,
        required_capabilities=req_cap, required_obligations=frozenset(),
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'f'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0,
        workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: OutcomeKind.SUCCESS for l in labels},
        discharged_by_label={l: dis for l in labels},
        capabilities_by_label={l: gain for l in labels},
        retained_output_gb_by_label={l: 0.0 for l in labels},
        released_memory_gb_by_label={l: 0.0 for l in labels},
        invalidates_model_by_label={l: False for l in labels},
        stale_evidence_by_label={l: False for l in labels},
        retry_cost_by_label={l: 0 for l in labels},
        proof_id_by_label={l: 'p_' + aid + '_' + l for l in labels},
    )

oracle = WorldOracle(
    specification_id='s', model_id='m', assurance_scope='a',
    universe=u, decision_by_world=dec,
    initial_obligations=frozenset({'ob'}),
    actions={
        'split': act('split', 'sp', u, {'w0': 'l0', 'w1': 'l1'}, gain=frozenset({'s'}), ru=0.0),
        'c1': act('c1', 'c1', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'s'}), gain=frozenset({'g1'}), ru=0.5),
        'c2': act('c2', 'c2', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'g1'}), gain=frozenset({'g2'}), ru=0.5),
        'c3': act('c3', 'c3', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'g2'}), dis=frozenset({'ob'}), ru=0.0),
        'fast': act('fast', 'fast', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'s'}), dis=frozenset({'ob'}), ru=2.0),
        'heavy': act('heavy', 'heavy', frozenset({'w1'}), {'w1': 'ok'}, req_cap=frozenset({'s'}), dis=frozenset({'ob'}), ru=5.0),
    }
)
budget = ResourceBudget(20.0, 100.0, 100.0, 10.0)
p = plan_policies(oracle, budget, max_horizon=5, prune=True)
up = plan_policies(oracle, budget, max_horizon=5, prune=False)
ex = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=5)
print('pruned:  ', p.pareto_frontier)
print('unpruned:', up.pareto_frontier)
print('oracle:  ', ex)
print('unpruned == oracle:', up.pareto_frontier == ex)
"
```
Observed output:
```text
pruned:   (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(5, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=4),)
unpruned: (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(5, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=4),)
oracle:   (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(5, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2),)
unpruned == oracle: False
```

### 4.3 Check 4: Minimal 2-World Counterexample Where `pruned != unpruned == oracle`

Command:
```powershell
f:/fem-edit-benchmark/.venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'f:/gdec-dwaop-v03')
from research.prototypes.dwaop_integrated_planner import ActionSemantics, OutcomeKind, ResourceBudget, WorldOracle, plan_policies
from research.prototypes.dwaop_exhaustive_policy_oracle import enumerate_exact_pareto_frontier

u = frozenset({'w0', 'w1'})
dec = {'w0': 'ACCEPT', 'w1': 'ACCEPT'}
def act(aid, sk, app, obs, req_cap=frozenset(), gain=frozenset(), dis=frozenset(), ru=0.0):
    labels = sorted(set(obs.values()))
    return ActionSemantics(
        action_id=aid, semantic_key=sk, applicable_worlds=app,
        observable_label_by_world=obs,
        required_capabilities=req_cap, required_obligations=frozenset(),
        evidence_contract=frozenset({'ev'}), failure_semantics=frozenset({'f'}),
        ru_upper=ru, cpu_ticks=0.0, energy_ticks=0.0,
        workspace_gb_upper=0.0, overlap_gb_upper=0.0,
        outcome_kind_by_label={l: OutcomeKind.SUCCESS for l in labels},
        discharged_by_label={l: dis for l in labels},
        capabilities_by_label={l: gain for l in labels},
        retained_output_gb_by_label={l: 0.0 for l in labels},
        released_memory_gb_by_label={l: 0.0 for l in labels},
        invalidates_model_by_label={l: False for l in labels},
        stale_evidence_by_label={l: False for l in labels},
        retry_cost_by_label={l: 0 for l in labels},
        proof_id_by_label={l: 'p_' + aid + '_' + l for l in labels},
    )

oracle = WorldOracle(
    specification_id='s', model_id='m', assurance_scope='a',
    universe=u, decision_by_world=dec,
    initial_obligations=frozenset({'ob'}),
    actions={
        'a_fine': act('a_fine', 'sp', u, {'w0': 'l0', 'w1': 'l1'}, gain=frozenset({'s'}), ru=0.0),
        'b_coarse': act('b_coarse', 'sp', u, {'w0': 'all', 'w1': 'all'}, gain=frozenset({'s'}), ru=0.0),
        'c1': act('c1', 'c1', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'s'}), gain=frozenset({'g1'}), ru=0.5),
        'c2': act('c2', 'c2', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'g1'}), gain=frozenset({'g2'}), ru=0.5),
        'c3': act('c3', 'c3', frozenset({'w0'}), {'w0': 'ok'}, req_cap=frozenset({'g2'}), dis=frozenset({'ob'}), ru=0.0),
        'fast': act('fast', 'fast', u, {'w0': 'ok', 'w1': 'ok'}, req_cap=frozenset({'s'}), dis=frozenset({'ob'}), ru=2.0),
    }
)
budget = ResourceBudget(20.0, 100.0, 100.0, 10.0)
p = plan_policies(oracle, budget, max_horizon=5, prune=True)
up = plan_policies(oracle, budget, max_horizon=5, prune=False)
ex = enumerate_exact_pareto_frontier(oracle, budget, max_horizon=5)
print('prunes:', p.metrics.successful_prunes)
print('pruned:  ', p.pareto_frontier)
print('unpruned:', up.pareto_frontier)
print('oracle:  ', ex)
print('pruned == unpruned:', p.pareto_frontier == up.pareto_frontier)
print('unpruned == oracle:', up.pareto_frontier == ex)
"
```
Observed output:
```text
prunes: 1
pruned:   (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(2, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=4),)
unpruned: (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(2, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2),)
oracle:   (NormalizedPolicy(world_verdict_map=(('w0', 'ACCEPT'), ('w1', 'ACCEPT')), resource_vector=ResourceVector(ru_upper=Fraction(2, 1), cpu_ticks=Fraction(0, 1), energy_ticks=Fraction(0, 1), peak_memory_gb=Fraction(0, 1)), terminal_verdicts=frozenset({'ACCEPT'}), max_actions_on_path=2),)
pruned == unpruned: False
unpruned == oracle: True
```

---

## 5. Specification Recommendations for Stage 2

1. **Resolve the `max_actions_on_path` Frontier Consistency Gap (Two Explicit Design Options):**
   - **Option A — Preserve Role (4) (Lexicographic Tie-Breaker $\mathcal{F}_{\mathrm{lex}}$ Exact):**
     - Keep `_policy_dominates` and `_oracle_dominates` on `(world_verdict_map, resource_vector)` only (preserving Q1/Q2).
     - Replace internal OR-node `pareto_reduce(complete_here)` inside `_search` (`dwaop_integrated_planner.py:1236, 1338`) with an internal $\preceq_{VRL}$-reducer that only prunes $q$ when there exists $p$ with $V_p \preceq_V V_q$, $R_p \le R_q$, **and** $L_p \le L_q$ (strict on at least one of $V, R, L$), keeping `pareto_reduce(all_policies)` ($\prec_{\mathrm{lex}}$) **only at the root** (`L1341`). Under the Section 1.5 Corollary, this restores exact equivalence $\mathcal{P}_{\mathrm{pruned}} = \mathcal{P}_{\mathrm{unpruned}} = \mathcal{P}_{\mathrm{oracle}}$ (once item 2 is also fixed).
     - *Complexity trade-off:* Because internal OR nodes must retain $(R_2, L_1)$ alongside $(R_1 < R_2, L_2 > L_1)$ when resource-vs-depth trade-offs exist, `branch_policies` can grow larger at intermediate nodes, increasing the Cartesian product `product(*branch_policies)` (`L1304`).
   - **Option B — Downgrade to Role (3) (Descriptive Metadata Only $\mathcal{F}_{VR}$):**
     - Keep internal `pareto_reduce` over $(V, R)$ (avoiding any `product(*branch_policies)` growth from $(R, L)$ trade-offs), drop `min(max_actions_on_path)` tie-breaking as a frontier invariant, and redefine frontier equivalence / `NormalizedPolicy` comparison / `dwaop_horizon_ladder.signature()` (`L103-109`) to project out `max_actions_on_path` (updating `test_dwaop_v03_horizon_ladder.py:124-139` accordingly).
2. **Enforce Sticky Refusal Across Transition Eligibility, Oracle Evaluation, and `is_local_refinement`:**
   - Enforce sticky-refusal termination (`not state.model_valid or state.evidence_stale or state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL`) directly at transition eligibility in `_enabled` (`dwaop_integrated_planner.py:642-664`), `_independent_enabled` (`dwaop_exhaustive_policy_oracle.py:82-97`), and world-by-world simulation `_evaluate_tree_on_world` (`dwaop_exhaustive_policy_oracle.py:204-258`)—not only via early return in `_search` (`L1227-1233`) and `_enumerate_trees` (`L114-119`).
   - Additionally guard `is_local_refinement` (`dwaop_integrated_planner.py:848-886`) with `coarse_state.last_outcome_kind == OutcomeKind.UNRECOVERABLE_REFUSAL or fine_state.last_outcome_kind != OutcomeKind.UNRECOVERABLE_REFUSAL` (mirroring `model_valid` and `evidence_stale` checks at `L848-L849`) so a sticky `UNRECOVERABLE_REFUSAL` fine state can never claim to simulate a recoverable `coarse_state`.
3. **Add Regression Coverage:**
   - Add the Check 3 (`unpruned == oracle`), Check 4 (`pruned == unpruned == oracle`), and Check 5 (`UNRECOVERABLE_REFUSAL` vs `TIMEOUT`) fixtures to `tests/research/`.
