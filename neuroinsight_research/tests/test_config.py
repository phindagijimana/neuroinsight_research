"""
Tests for the configuration system.
"""
import os
import pytest


class TestConfig:
    """Test Pydantic-based configuration loading and validation."""

    def test_default_config_loads(self):
        """Config loads with default values when no env vars are set."""
        from backend.core.config import Settings
        settings = Settings()
        assert settings.api_port >= 1
        assert settings.backend_type in ("local", "remote_docker", "slurm", "pbs", "local_docker")

    def test_backend_type_validation(self):
        """Invalid backend_type raises validation error."""
        from backend.core.config import Settings
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Settings(backend_type="invalid_backend")

    def test_hpc_settings_defaults(self):
        """HPC settings have sensible defaults."""
        from backend.core.config import Settings
        settings = Settings()
        assert settings.hpc_ssh_port == 22
        assert settings.hpc_container_runtime in ("singularity", "apptainer")
        assert settings.hpc_work_dir is not None

    def test_env_override(self, monkeypatch):
        """Environment variables override default config values."""
        monkeypatch.setenv("API_PORT", "8080")
        monkeypatch.setenv("BACKEND_TYPE", "slurm")
        from backend.core.config import Settings
        settings = Settings()
        assert settings.api_port == 8080
        assert settings.backend_type == "slurm"

    def test_max_concurrent_jobs_range(self):
        """max_concurrent_jobs must be between 1 and 100."""
        from backend.core.config import Settings
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Settings(max_concurrent_jobs=0)
        with pytest.raises(ValidationError):
            Settings(max_concurrent_jobs=101)
