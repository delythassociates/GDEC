"""
CPU numerical execution backend using NumPy, SciPy and scikit-fem.
"""

from __future__ import annotations
import platform
import os
import psutil
import numpy as np
import scipy
import skfem
from typing import Dict, Any

from gdec.backends.base import ComputationalBackend


class CPUBackend(ComputationalBackend):
    @property
    def name(self) -> str:
        return "cpu"

    @property
    def is_available(self) -> bool:
        return True

    def get_device_info(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        return {
            "backend": "cpu",
            "processor": platform.processor() or platform.machine(),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "total_ram_gb": round(mem.total / (1024**3), 2),
            "available_ram_gb": round(mem.available / (1024**3), 2),
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "libraries": {
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "scikit-fem": skfem.__version__,
            },
        }
