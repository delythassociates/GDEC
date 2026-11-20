"""
Registry and hardware detection for GDEC computational backends.
"""

from __future__ import annotations
import shutil
import subprocess
from typing import Dict, Any, List, Optional

from gdec.backends.base import ComputationalBackend
from gdec.backends.cpu import CPUBackend


class BackendRegistry:
    _backends: Dict[str, ComputationalBackend] = {
        "cpu": CPUBackend(),
    }

    @classmethod
    def get_backend(cls, name: str) -> ComputationalBackend:
        dev = name.lower().strip()
        if dev not in cls._backends:
            raise ValueError(
                f"Unsupported or unregistered backend: '{name}'. Registered backends: {list(cls._backends.keys())}"
            )
        backend = cls._backends[dev]
        if not backend.is_available:
            raise RuntimeError(f"Backend '{name}' is registered but not available on this host.")
        return backend

    @classmethod
    def list_available_backends(cls) -> List[str]:
        return [k for k, v in cls._backends.items() if v.is_available]

    @classmethod
    def detect_hardware(cls) -> Dict[str, Any]:
        """Detect host CPU, RAM, and check GPU presence honestly without false acceleration claims."""
        cpu_backend = cls._backends["cpu"]
        info = cpu_backend.get_device_info()

        # Check for NVIDIA GPU presence via nvidia-smi
        has_nvidia_smi = shutil.which("nvidia-smi") is not None
        gpu_detected = False
        gpu_model = None

        if has_nvidia_smi:
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0 and res.stdout.strip():
                    gpu_detected = True
                    gpu_model = res.stdout.strip().replace("\n", "; ")
            except Exception:
                pass

        info["accelerator_hardware"] = {
            "gpu_hardware_detected": gpu_detected,
            "gpu_model": gpu_model if gpu_detected else "None detected",
            "cuda_backend_implemented": False,
            "cuda_backend_implemented_v0_1": False,
            "status_note": (
                "GPU hardware detected, but GDEC v0.2.1 executes on CPU. Accelerator backends (CUDA/HIP/SYCL/TPU) are planned for future versions."
                if gpu_detected
                else "No GPU accelerator detected. CPU backend active."
            ),
        }
        return info
