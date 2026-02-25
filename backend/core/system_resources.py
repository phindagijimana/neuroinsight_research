"""
System Resource Detection

Detects host machine CPU, RAM, and GPU capabilities.
Used by the frontend to show realistic resource limits.
"""
import os
import logging
import shutil
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def detect_cpus() -> Dict[str, Any]:
    """Detect CPU information."""
    physical_cores = os.cpu_count() or 4
    # Try to get physical vs logical core count
    logical_cores = physical_cores
    try:
        # On Linux, parse /proc/cpuinfo for physical cores
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
        # Count unique physical id + core id combos
        core_ids = set()
        current_phys_id = None
        for line in content.split("\n"):
            if line.startswith("physical id"):
                current_phys_id = line.split(":")[1].strip()
            elif line.startswith("core id") and current_phys_id is not None:
                core_id = line.split(":")[1].strip()
                core_ids.add((current_phys_id, core_id))
        if core_ids:
            physical_cores = len(core_ids)
            logical_cores = os.cpu_count() or physical_cores
    except (FileNotFoundError, PermissionError):
        pass

    # Recommend leaving 1-2 cores for system
    recommended_max = max(1, physical_cores - 1)

    return {
        "physical_cores": physical_cores,
        "logical_cores": logical_cores,
        "recommended_max": recommended_max,
    }


def detect_memory() -> Dict[str, Any]:
    """Detect system memory."""
    total_gb = 8  # fallback
    available_gb = 4
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    total_gb = round(kb / (1024 * 1024), 1)
                elif line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    available_gb = round(kb / (1024 * 1024), 1)
    except (FileNotFoundError, PermissionError):
        pass

    # Recommend leaving ~2 GB for system
    recommended_max_gb = max(1, int(total_gb - 2))

    return {
        "total_gb": total_gb,
        "available_gb": available_gb,
        "recommended_max_gb": recommended_max_gb,
    }


def detect_gpus() -> Dict[str, Any]:
    """Detect GPU availability and info."""
    gpus: List[Dict[str, Any]] = []
    nvidia_available = False

    # Check for nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                nvidia_available = True
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpus.append({
                            "name": parts[0],
                            "memory_mb": int(float(parts[1])),
                            "driver_version": parts[2],
                        })
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

    return {
        "available": nvidia_available,
        "count": len(gpus),
        "devices": gpus,
    }


def detect_all() -> Dict[str, Any]:
    """Detect all system resources."""
    cpu = detect_cpus()
    memory = detect_memory()
    gpu = detect_gpus()
    return {
        "cpu": cpu,
        "memory": memory,
        "gpu": gpu,
        "limits": {
            "max_cpus": cpu["recommended_max"],
            "max_memory_gb": memory["recommended_max_gb"],
            "gpu_available": gpu["available"],
            "gpu_count": gpu["count"],
        },
    }
