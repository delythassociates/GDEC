"""
Test execution wrapper for GDEC v0.2.2 test suite.
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def find_python():
    # If running inside venv, sys.executable is already good
    # If running from system python, check if local .venv exists
    venv_py_win = ROOT / ".venv" / "Scripts" / "python.exe"
    venv_py_nix = ROOT / ".venv" / "bin" / "python"
    if venv_py_win.exists():
        return str(venv_py_win)
    elif venv_py_nix.exists():
        return str(venv_py_nix)
    return sys.executable

def main():
    print("=" * 60)
    print("GDEC v0.2.3 — Automated Test Suite Runner")
    print("=" * 60)
    py_exe = find_python()
    cmd = [py_exe, "-m", "pytest", "tests", "-v", "--durations=10"]
    print("Using Python executable:", py_exe)
    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(ROOT))
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
