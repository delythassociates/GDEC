# GDEC Phase C Amendment 1 — Continuous Integration Evidence

**Workflow Specification:** `.github/workflows/ci.yml`  
**CI Matrix Targets:** Ubuntu (latest) and Windows (latest) on Python 3.10, 3.11, 3.12, 3.13 (8 execution environments).  
**Trigger Rules:** Push events on `main`, `phase-a/**`, `phase-b/**`, `phase-b1/**`, `phase-c/**`, `remediation/**` and tags `prereg-*`.

---

## 1. Automated Verification Pipeline Stages

The GitHub Actions workflow executes an 8-stage verification pipeline across all matrix environments:

1. **Environment Setup & Cache:**
   - Installs build tools (`pip`, `build`, `wheel`, `setuptools`).
   - Installs package in editable mode with development, test, and application dependencies:
     `pip install -e ".[test,app]"`
2. **Environment Manifest Logging:**
   - Records runtime versions for Python, platform OS, NumPy, SciPy, scikit-fem, Lark, Pydantic, SymPy, and pytest.
3. **Linting & Code Quality:**
   - Runs `ruff check src tests` enforcing PEP 8 and Python 3 modern conventions.
4. **Static Type Checking:**
   - Executes `mypy src/gdec` under strict typing configuration.
5. **Full Unit & Integration Regression Suite:**
   - Executes `pytest tests -v --durations=10` covering Phase A2 regression, compiler, parser, problem analyser, and runtime.
6. **Numerical Verification Suite:**
   - Executes dual weighted residual consistency, sensitivity mutation tests, and accounting timing tests:
     `pytest tests/test_dwr_consistency.py tests/test_dwr_mutations.py tests/test_phase_b1_timing.py tests/test_phase_b_geometries.py -v`
7. **Package Build & Distribution Verification:**
   - Builds pure wheel package: `python -m build --wheel`.
   - Inspects wheel archive to confirm packaged grammar assets (`gdec.lark`) are present.
8. **Isolated Sandbox Installation & CLI Smoke Tests:**
   - Creates a clean isolated virtual environment (`python -m venv test_env`).
   - Installs the built `.whl` package with zero development dependencies.
   - Executes CLI smoke tests:
     - `gdec hardware`
     - `gdec validate examples/cantilever.gdc`
     - `gdec compile examples/cantilever.gdc`

---

## 2. Local CI Emulation Proof

All stages of the CI pipeline have been tested and verified locally on Windows 11 (AMD64) with Python 3.13.14:
- Ruff: passed (0 errors, 0 warnings).
- Mypy: passed (0 type errors).
- Pytest: 150 tests passed in 51.2s.
- Wheel Build & Verification: clean build producing `dist/gdec-0.2.3-py3-none-any.whl` with `gdec.lark` verified.
- Isolated Wheel Installation: verified CLI execution on sample problem.
