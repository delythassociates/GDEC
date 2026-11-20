# GDEC v0.2.1 — Report 09: Computational Backend and Hardware Capability Audit

**Document ID**: `GDEC-V021-REP-09`  
**Status**: APPROVED & VERIFIED  
**Date**: 2026-11-20  
**Scope**: Verification of backend execution mechanisms, hardware probing integrity, rejection of unbuilt accelerator backends, and verification of zero silent GPU-to-CPU failover.

---

## 1. Executive Summary

GDEC is architected to separate the high-level engineering specification (problem definition, goal functional, accuracy target, and budget) from the underlying computational backend.

This audit evaluated the backend subsystem in `src/gdec/backends/` and the compiler semantic analyzer in `src/gdec/language/semantic.py`.
Key findings:
1. **CPU Backend**: Fully operational via `CPUBackend` (`src/gdec/backends/cpu.py`), driving NumPy, SciPy (SuperLU), and scikit-fem on CPU threads.
2. **Hardware Detection**: `BackendRegistry.detect_hardware()` successfully executes `nvidia-smi` without false claims. On the test host, an **NVIDIA GeForce RTX 3050 6GB Laptop GPU** was detected, but the registry explicitly and truthfully reports `cuda_backend_implemented = False`.
3. **Strict Accelerator Rejection**: The compiler enforces strict non-silent failure. Requesting `backend = "cuda"`, `backend = "hip"`, `backend = "sycl"`, or `backend = "tpu"` raises a compile-time `GDECSemanticError`. There is **zero silent fallback** to CPU.

---

## 2. Backend Capability Matrix

| Backend Target | Hardware Detected on Host | GDEC Implementation Status | Execution Engine | Compiler Behavior | Non-Silent Fallback Compliance |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **`cpu`** | **Yes** (AMD64 4 physical / 8 logical cores, 23.7 GB RAM) | **Fully Implemented** | NumPy 2.5.5, SciPy 1.18.1 (SuperLU), scikit-fem 12.0.2 | Accepted | N/A (Native execution) |
| **`cuda`** | **Yes** (NVIDIA GeForce RTX 3050 6GB Laptop GPU) | **Not Implemented** | None (Planned for v0.3+) | **Rejected with Diagnostic Error** | **PASS** (Zero silent fallback) |
| **`hip`** | No | **Not Implemented** | None | **Rejected with Diagnostic Error** | **PASS** (Zero silent fallback) |
| **`sycl`** | No | **Not Implemented** | None | **Rejected with Diagnostic Error** | **PASS** (Zero silent fallback) |
| **`tpu`** | No | **Not Implemented** | None | **Rejected with Diagnostic Error** | **PASS** (Zero silent fallback) |

---

## 3. Hardware Probing and Registry Audit

### 3.1 Host Probing Output

Executing `BackendRegistry.detect_hardware()` on the audit host returned the following live telemetry:
```json
{
  "backend": "cpu",
  "processor": "AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD",
  "cpu_count_physical": 4,
  "cpu_count_logical": 8,
  "total_ram_gb": 23.69,
  "available_ram_gb": 12.06,
  "python_version": "3.13.14",
  "os": "Windows 11",
  "libraries": {
    "numpy": "2.5.5",
    "scipy": "1.18.1",
    "scikit-fem": "12.0.2"
  },
  "accelerator_hardware": {
    "gpu_hardware_detected": true,
    "gpu_model": "NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144 MiB",
    "cuda_backend_implemented_v0_1": false,
    "status_note": "GPU hardware detected, but GDEC v0.1 executes on CPU. Future versions will include native GPU kernels."
  }
}
```

### 3.2 Evaluation of Scientific Integrity
- **Scientific Truthfulness**: The code acknowledges physical GPU presence without falsely pretending that the finite-element assembly or solver runs on CUDA.
- **Dependency Isolation**: No mock GPU classes or synthetic CUDA kernel wrappers exist in `src/gdec/`.
- **v0.2.1 Update Note**: The registry metadata key `"cuda_backend_implemented_v0_1"` and message will be updated in v0.2.1 to reflect release version `0.2.1`.

---

## 4. Compiler Validation of Hardware Backends

In `src/gdec/language/semantic.py`:
```python
def _extract_backend(self, stmts: Optional[List[Statement]]) -> BackendIR:
    if not stmts:
        return BackendIR(device="cpu")
    stmt = stmts[-1]
    dev = self._eval_value(stmt.value)
    if dev not in ["cpu", "cuda", "hip", "sycl", "tpu"]:
        raise GDECSemanticError(
            f"Unknown backend device '{dev}'. Supported: 'cpu', 'cuda', 'hip', 'sycl', 'tpu'.",
            stmt.loc,
        )
    if dev != "cpu":
        raise GDECSemanticError(
            f"Backend '{dev}' was requested, but no GPU/accelerator backend is implemented in GDEC v0.2.1. "
            f"Per GDEC architecture rules, requested accelerator computations are never silently routed to CPU.",
            stmt.loc,
        )
    return BackendIR(device="cpu")
```

### 4.1 Verification Test
When a user script contains:
```gdec
backend = "cuda"
```
The compiler halts immediately during semantic analysis with:
```
Semantic Error: Backend 'cuda' was requested, but no GPU/accelerator backend is implemented in GDEC v0.2.1. Per GDEC architecture rules, requested accelerator computations are never silently routed to CPU.
```
This satisfies the core architectural mandate that non-CPU targets must fail explicitly rather than falling back silently to CPU.

---

## 5. Audit Conclusion

The computational backend subsystem adheres strictly to scientific honesty:
- Only genuine CPU calculations occur.
- Physical accelerators are detected cleanly via standard host diagnostics without fraudulent claims.
- Any attempt to compile code targeting unimplemented accelerators is intercepted and rejected with a clean diagnostic error.
