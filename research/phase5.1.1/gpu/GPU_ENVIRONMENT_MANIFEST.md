# GPU Execution Environment Manifest (Phase 5.1.1)

## 1. Host Hardware Specification

- **Host Processor:** AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD (AMD Ryzen series)
- **Host Physical Memory (RAM):** 24,242 MB (~23.7 GB)
- **Host Operating System:** Microsoft Windows 11 Home / Pro (10.0.26100 AMD64)
- **Python Runtime:** Python 3.13.14 (tags/v3.13.14:b0b5e28) 64-bit

---

## 2. NVIDIA GPU Hardware & Driver Configuration

- **GPU Device:** NVIDIA GeForce RTX 3050 6GB Laptop GPU
- **Compute Capability:** SM 8.6 (Ampere Architecture)
- **Streaming Multiprocessors (SMs):** 20
- **Total Dedicated VRAM:** 6,143.5 MB (6.0 GB GDDR6)
- **Memory Bus Width:** 96-bit
- **Host PCIe Interface:** PCIe Gen 4 x4
- **NVIDIA Display Driver:** 595.97
- **CUDA Driver API Version:** 13.2 (Supported up to CUDA 13.x)

---

## 3. CUDA Toolkit, Compilers & Scientific Libraries

- **NVIDIA CUDA Toolkit:** CUDA 12.9.2 (`nvcc` V12.9.86)
- **CuPy Library:** `cupy-cuda12x` version 14.2.0 (compiled for CUDA 12.x)
- **NumPy Version:** 2.2.3
- **SciPy Version:** 1.15.2
- **Compiler / Toolchain:** MSVC / Windows SDK 10.0

---

## 4. CUDA Device Diagnostics (Runtime Detection)

```json
{
  "backend": "cuda",
  "is_available": true,
  "status": "SUPPORTED_GPU_AVAILABLE",
  "diagnostic_message": "CUDA backend is fully operational with CuPy 14.2.0 on NVIDIA GeForce RTX 3050 6GB Laptop GPU.",
  "device_id": 0,
  "device_name": "NVIDIA GeForce RTX 3050 6GB Laptop GPU",
  "total_vram_mb": 6143.5,
  "cupy_version": "14.2.0",
  "driver_version": "595.97"
}
```
