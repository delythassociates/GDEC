# GDEC Competitive Gap Analysis: The Disconnect Between Simulation Output and Engineering Decisions

**Document Reference:** `research/phase5/competitive/COMPETITIVE_GAP_ANALYSIS.md`  
**Workstream:** Agent 3 — Competitive and Market Capability Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Market and Technology Gaps Identified  

---

## 1. Executive Summary

Commercial engineering simulation software (ANSYS, Altair, Abaqus, Siemens) represents over four decades of intense numerical, geometric, and graphical refinement. These tools are unmatched in their ability to solve massive, nonlinear multi-physics problems involving complex contact, plasticity, composite damage, fluid-structure interaction, and detailed CAD defeaturing.

However, an in-depth investigation into contemporary industrial engineering practice reveals a **fundamental structural blind spot** across all established platforms:
> **The current simulation industry builds "Solution Engines", not "Decision Engines". They compute what will happen to a defined mathematical model, but they cannot determine whether that computation is sufficient, necessary, or defensible to justify a real-world engineering decision.**

This analysis documents eight specific, unaddressed market and technology gaps where GDEC can establish a defensible, non-commodity position.

---

## 2. The Eight Industrial Engineering Gaps

### Gap 1: The Chasm Between Numerical Convergence and Decision Sufficiency
- **Current State in Competitor Platforms:** Solvers terminate when algebraic residual norms drop below a tolerance ($\|r\| / \|b\| \le 10^{-6}$), or when adaptive meshing reaches a heuristic gradient threshold. Post-processors present colorful stress/displacement contours.
- **The Engineer's Dilemma:** The engineer must decide: *"Is this component safe for production?"* If the maximum von Mises stress is $245\text{ MPa}$ against a yield limit of $250\text{ MPa}$ ($2\%$ margin), the fact that the linear solver converged to $10^{-8}$ is irrelevant if discretization error is $6\%$ or material yield uncertainty is $10\%$.
- **The Unmet Need:** Software that evaluates whether the accumulated evidence conclusively resolves the engineering decision question, accounting for combined numerical and parameter uncertainties.

### Gap 2: Over-Computation and the Absence of Value-of-Information (VoI) Stopping
- **Current State:** Simulation queues in enterprise HPC environments are dominated by uniform over-refinement or arbitrary massive Monte Carlo runs ($10,000$ runs when $100$ would suffice).
- **The Unmet Need:** A system that evaluates the **Value of Information (VoI)** of further compute. If refining a mesh by $4\times$ (costing 4 core-hours) has a $< 0.1\%$ probability of altering the binary pass/fail decision, the computation should be terminated early with an explicit mathematical justification.

### Gap 3: Fragmented Evidence Across Simulation, Testing, and Analytical Models
- **Current State:** Engineering organizations store physical test data in one silo (Excel, test lab databases), hand-calculation analytical models in Mathcad/Jupyter, and finite element models in proprietary simulation databases (Ansys Minerva, Teamcenter).
- **The Unmet Need:** An **Engineering Evidence Graph** that links physical coupon test data, analytical beam models, and multi-fidelity FEM results into a unified Bayesian decision network.

### Gap 4: Invalidation and Selective Re-computation Upon Design Change
- **Current State:** When a CAD model is revised (e.g., bracket thickness increased by $1.5\text{ mm}$ or a hole relocated), standard PLM pipelines invalidate all downstream simulation runs, forcing engineers to re-run expensive full-fidelity simulations from scratch.
- **The Unmet Need:** Dependency-aware evidence inheritance. When geometry changes, an intelligent evidence engine identifies which previous evidence remains valid (e.g., material constitutive tests, remote boundary condition verifications, mesh convergence rates) and executes only the marginal computation required to restore decision confidence.

### Gap 5: Explaining Why Evidence is Sufficient or Insufficient
- **Current State:** Post-processors output raw numbers, contour plots, and CSV tables. If an auditor asks *"Why did you stop at this mesh size?"*, the engineer must manually assemble PowerPoint decks with manual convergence plots.
- **The Unmet Need:** Automated, audit-ready compliance reporting (conforming to ASME V&V 10 / ASME V&V 40 and NASA-STD-7009B) that mathematically explains why the evidence satisfies the required confidence margin.

### Gap 6: Deterministic Refusal vs. False Confidence
- **Current State:** Commercial solvers almost never refuse an ill-posed problem if the mesh can be inverted. If an unregularized point load or sharp re-entrant notch is analyzed in linear elasticity, the solver happily outputs a stress that increases unboundedly with mesh refinement, misleading junior engineers.
- **The Unmet Need:** **Deterministic Refusal Mechanics** (as prototyped in GDEC Phase C). When a requested QoI is mathematically divergent or physically unverifiable under the chosen formulation, the system must refuse to compute and explain the mathematical reason why.

### Gap 7: High-End Simulation Complexity for Mid-Market Engineering Teams
- **Current State:** Exploiting optiSLang, Isight, or HEEDS requires dedicated simulation specialists, complex multi-software licensing, and extensive scripting. Small-to-medium engineering teams cannot justify the overhead.
- **The Unmet Need:** A clean, declarative decision language (DSL) where an engineer states the question, constraints, and budget, and the system autonomously orchestrates modeling, refinement, and decision verification.

### Gap 8: Commoditization of Raw FEM Solvers
- **Current State:** Standard 2D/3D linear elastic solvers, basic thermal solvers, and pre-solve meshers are now widely available as open-source libraries (SciPy, Scikit-fem, FEniCS, MFEM, SfePy) and low-cost cloud services.
- **Strategic Implication for GDEC:** Competing directly on raw finite element feature checklists (e.g., trying to out-feature Abaqus on non-linear rubber hyperelasticity) is a guaranteed commercial failure. **GDEC must compete on Decision Intelligence, Verification Integrity, and Computational Resource Optimization.**
