# GDEC — Goal-Driven Engineering Computation (v0.3.0-alpha)
## Verified Adaptive Finite Element Mechanics, Decision Sufficiency & Engineering Evidence

![Tests](https://img.shields.io/badge/pytest-371%20tests-informational.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-informational.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
[![Status](https://img.shields.io/badge/Status-Research%20Alpha-orange.svg)](docs/GDEC_ENGINEERING_STATUS.md)

---

## 1. What GDEC Is / What GDEC Is Not

### What GDEC Is
**GDEC (Goal-Driven Engineering Computation)** is a scientific computing and finite element platform designed to answer a single critical engineering question: **"Is this simulation result accurate enough to make an engineering decision?"**

Rather than treating simulation as a black-box contour generator, GDEC inverts the computational pipeline:
1. **Goal-Driven Declaration:** The engineer declares the physical domain, material parameters, target Quantity of Interest (QoI), required accuracy threshold, and computational budget.
2. **Dual-Weighted Adaptivity:** The system formulates the primal problem and dual adjoint problem, evaluating goal-specific discretization error.
3. **Decision Sufficiency Engine (DSE):** Evaluates Bayesian expected loss against user-defined decision contracts to determine whether additional compute reduces engineering decision risk.
4. **Machine-Checkable Evidence:** GDEC includes canonical input hashing and structured decision/evidence components. End-to-end evidence completeness is still under development; DWR indicators are estimators, not certified error bounds.
5. **Deterministic Refusal:** Implemented subsystems reject selected invalid inputs and unsupported numerical operations with typed diagnostics. Refusal coverage is not yet comprehensive across every physical-model assumption.

### What GDEC Is Not
- **Not a General-Purpose Commercial FEA Replacement:** GDEC does not provide 3D solid elements, nonlinear contact, crash plasticity, or general multiphysics. It focuses intentionally on verified 2D continuum problems (linear elasticity, steady heat conduction).
- **Not an Unverified Result Generator:** GDEC aims to prevent unqualified results when implemented validity checks fail; refusal coverage remains incomplete and is tracked as a development requirement.
- **Not Hardware-Locked:** Core numerical routines run on standard CPU environments using NumPy and SciPy; GPU acceleration via CuPy is an optional execution backend.

---

## 2. Quickstart

GDEC targets Python 3.10 or higher and provides setup instructions for Linux, macOS, and Windows. The current automated CI workflow runs on Ubuntu with Python 3.10–3.12; other OS/Python combinations require separate verification.

### Step 1: Clone the Repository
```bash
git clone https://github.com/delythassociates/GDEC.git
cd GDEC
```

### Step 2: Set Up Virtual Environment

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Package and Dependencies
```bash
pip install --upgrade pip
pip install -e ".[test]"
```
*(Optional: install algebraic multigrid smoothers via `pip install -e ".[test,amg]"`).*

### Step 4: Run the Test Suite
```bash
pytest -v
```
*Expected result: the test suite should pass. CUDA-operational tests are skipped when an operational NVIDIA device is unavailable; exact pass/skip counts depend on the test revision and host. The WP0 artifacts do not yet reconcile the CPU-only skip count.*

### Step 5: Run Your First Goal-Driven Simulation
```bash
# Check available compute hardware
gdec hardware

# Validate declarative engineering specification
gdec validate examples/cantilever.gdc

# Compile into typed Intermediate Representation
gdec compile examples/cantilever.gdc -o results/cantilever_ir.json

# Execute goal-adaptive simulation loop
gdec run examples/cantilever.gdc --strategy goal_aware
```

---

## 3. System Architecture

```text
Engineering Specification (.gdc)
               │
               ▼
        Compiler Frontend (Lark LALR(1) + Semantic Typing)
               │
               ▼
     Canonical Engineering IR (Canonical SHA-256 Hashing)
               │
               ▼
  Intelligent Runtime & Execution Planner ◄─── Execution Backend Protocol
               │                                (CPUBackend / CUDABackend)
        ┌──────┴──────┐
        ▼             ▼
  Primal Solve   Adjoint Solve
        │             │
        └──────┬──────┘
               │
               ▼
  Goal-Oriented DWR Error Estimator & Dörfler Marking
               │
               ▼
  Decision Sufficiency Engine (Bayesian Loss & Refusal Rules)
               │
               ▼
  QoI Result + Solver Diagnostics and Available Evidence
```

---

## 4. Verified Capabilities & Evidence-Backed Claims

In accordance with GDEC's engineering ethics, all performance and capability claims link directly to reproducible results in this repository:

- **Goal-Adaptive Mesh Efficiency:** Goal-aware adaptivity achieves target QoI accuracy with **$2.50\times$ fewer DOFs** than uniform refinement (4,034 DOFs vs 10,098 DOFs).
  - *Evidence:* [`results/CantileverDemo_benchmark.json`](results/CantileverDemo_benchmark.json), [`results/v022/CantileverDemo_summary.csv`](results/v022/CantileverDemo_summary.csv).
- **Primal-Adjoint Factorization Reuse:** Reusing the primal sparse LU factorization for the dual adjoint solve achieves a **$1.96\times - 2.00\times$ speedup** on isolated linear solves.
  - *Evidence:* [`results/CantileverDemo_iterations.csv`](results/CantileverDemo_iterations.csv).
- **Exact Zero-Solve Parameter Scaling:** Supported analytical parameter scaling has a 5,000-sample CPU/GPU parity test; this does not establish a general 100,000-sample throughput claim.
  - *Evidence:* [`tests/test_cuda_backend.py`](tests/test_cuda_backend.py).
- **Safe Refinement Transaction Protocol:** Transactional budget bounds guarantee that adaptive refinement terminates with $\text{final\_dofs} \le \text{max\_dofs}$ in 100% of tested cases.
  - *Evidence:* [`tests/test_runtime.py`](tests/test_runtime.py).
- **Iterative Solver SPD Eligibility Gates:** PCG solver strictly enforces structural and algebraic symmetry and positive-definiteness, deterministically rejecting indefinite systems.
  - *Evidence:* [`tests/test_iterative_solvers.py`](tests/test_iterative_solvers.py).

---

## 5. Documentation Directory

- **[GDEC Engineering Status Register](docs/GDEC_ENGINEERING_STATUS.md):** Authoritative taxonomy tracking capabilities from PLANNED to NUMERICALLY VERIFIED.
- **[System Architecture](docs/ARCHITECTURE.md):** Component boundaries, runtime data flow, and execution lifecycle.
- **[Versioning & Compatibility Policy](docs/VERSION_POLICY.md):** Semantic versioning rules, schema decoupling, and migration guarantees.
- **[Mathematical Model](docs/MATHEMATICAL_MODEL.md):** Governing continuum equations, weak forms, P1 discretization, and adjoint DWR formulations.
- **[Language Reference](docs/LANGUAGE_REFERENCE.md):** `.gdc` engineering DSL keywords, grammar specifications, and syntax rules.
- **[Known Limitations](docs/known_limitations.md):** Bounded operational scope and algorithmic demarcations.
- **[Contributing Guidelines](CONTRIBUTING.md):** Development protocols, branch conventions, and testing standards.
- **[Security Policy](SECURITY.md):** Vulnerability reporting and computational safety guarantees.
- **[Code of Conduct](CODE_OF_CONDUCT.md):** Community and engineering standards.
- **[License](LICENSE):** MIT License.
