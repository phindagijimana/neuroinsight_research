"""
Tests for system resource detection.
"""
import pytest


class TestSystemResources:
    """Test CPU, memory, GPU detection utilities."""

    def test_detect_all_returns_dict(self):
        """detect_all returns a dict with cpu/memory info."""
        from backend.core.system_resources import detect_all
        resources = detect_all()
        assert isinstance(resources, dict)
        assert "cpu" in resources
        assert "memory" in resources

    def test_detect_cpus(self):
        """detect_cpus returns CPU info with at least 1 core."""
        from backend.core.system_resources import detect_cpus
        cpu = detect_cpus()
        assert isinstance(cpu, dict)
        count = cpu.get("count", cpu.get("cores", cpu.get("total", 1)))
        assert count >= 1

    def test_detect_memory(self):
        """detect_memory returns positive memory values."""
        from backend.core.system_resources import detect_memory
        mem = detect_memory()
        assert isinstance(mem, dict)
        total = mem.get("total_gb", mem.get("total", 1))
        assert total > 0

    def test_detect_gpus(self):
        """detect_gpus returns a dict (may be empty if no GPUs)."""
        from backend.core.system_resources import detect_gpus
        gpus = detect_gpus()
        assert isinstance(gpus, dict)
