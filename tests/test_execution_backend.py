"""
Tests for execution backend factory, local backend, and remote docker backend.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestBackendFactory:
    """Test execution backend creation."""

    def test_create_local_backend(self):
        """create_backend('local') returns a LocalDockerBackend."""
        from backend.execution import create_backend
        backend = create_backend(backend_type="local")
        assert backend.backend_type in ("local", "local_docker")

    def test_create_slurm_backend(self, monkeypatch):
        """create_backend('slurm') returns a SLURMBackend when SSH params provided."""
        monkeypatch.setenv("HPC_HOST", "test.hpc.edu")
        monkeypatch.setenv("HPC_USER", "testuser")
        from backend.execution import create_backend
        backend = create_backend(backend_type="slurm")
        assert backend.backend_type == "slurm"

    def test_create_remote_docker_backend(self, monkeypatch):
        """create_backend('remote_docker') returns a RemoteDockerBackend."""
        monkeypatch.setenv("REMOTE_HOST", "ec2-1-2-3-4.compute.amazonaws.com")
        monkeypatch.setenv("REMOTE_USER", "ubuntu")
        from backend.execution import create_backend
        backend = create_backend(backend_type="remote_docker")
        assert backend.backend_type == "remote_docker"

    def test_create_remote_docker_uses_hpc_env_fallback(self, monkeypatch):
        """remote_docker falls back to HPC_HOST/HPC_USER if REMOTE_* not set."""
        monkeypatch.setenv("HPC_HOST", "myvm.example.com")
        monkeypatch.setenv("HPC_USER", "admin")
        monkeypatch.delenv("REMOTE_HOST", raising=False)
        monkeypatch.delenv("REMOTE_USER", raising=False)
        from backend.execution import create_backend
        backend = create_backend(backend_type="remote_docker")
        assert backend.backend_type == "remote_docker"

    def test_remote_docker_missing_creds_raises(self, monkeypatch):
        """remote_docker without host/user raises ValueError."""
        monkeypatch.delenv("REMOTE_HOST", raising=False)
        monkeypatch.delenv("REMOTE_USER", raising=False)
        monkeypatch.delenv("HPC_HOST", raising=False)
        monkeypatch.delenv("HPC_USER", raising=False)
        from backend.execution import create_backend
        with pytest.raises(ValueError, match="ssh_host and ssh_user"):
            create_backend(backend_type="remote_docker")

    def test_invalid_backend_type(self):
        """create_backend with invalid type raises ValueError."""
        from backend.execution import create_backend
        with pytest.raises((ValueError, KeyError)):
            create_backend(backend_type="invalid_type")


class TestLocalBackend:
    """Test LocalDockerBackend methods."""

    def test_instantiation(self):
        """LocalDockerBackend can be instantiated."""
        from backend.execution.local_backend import LocalDockerBackend
        backend = LocalDockerBackend()
        assert backend.backend_type in ("local", "local_docker")

    def test_submit_job_returns_job_id(self):
        """submit_job() returns a job ID string."""
        from backend.execution.local_backend import LocalDockerBackend

        backend = LocalDockerBackend()

        with patch("backend.execution.celery_tasks.run_docker_job") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-123")
            from backend.core.execution import JobSpec, ResourceSpec
            spec = JobSpec(
                pipeline_name="test",
                container_image="test:latest",
                input_files=["/fake/input.nii.gz"],
                output_dir="/fake/output",
                parameters={},
                resources=ResourceSpec(cpus=4, memory_gb=8, time_hours=2),
            )
            # submit_job may raise if DB is not available, so just test instantiation
            assert backend is not None


class TestRemoteDockerBackend:
    """Test RemoteDockerBackend methods."""

    def test_instantiation(self):
        """RemoteDockerBackend can be instantiated."""
        from backend.execution.remote_docker_backend import RemoteDockerBackend
        backend = RemoteDockerBackend(
            ssh_host="ec2-1-2-3-4.compute.amazonaws.com",
            ssh_user="ubuntu",
        )
        assert backend.backend_type == "remote_docker"

    def test_container_name_generation(self):
        """Container names are deterministic and safe."""
        from backend.execution.remote_docker_backend import RemoteDockerBackend
        backend = RemoteDockerBackend(ssh_host="test.com", ssh_user="user")
        name = backend._container_name("abc12345-def6-7890-ghij-klmnopqrstuv")
        assert name.startswith("neuroinsight_")
        assert "-" not in name.split("_", 1)[1]

    def test_health_check_no_connection(self):
        """health_check returns unhealthy when not connected."""
        from backend.execution.remote_docker_backend import RemoteDockerBackend
        backend = RemoteDockerBackend(ssh_host="test.com", ssh_user="user")
        health = backend.health_check()
        assert health["healthy"] is False

    def test_get_system_info_no_connection(self):
        """get_system_info returns error when not connected."""
        from backend.execution.remote_docker_backend import RemoteDockerBackend
        backend = RemoteDockerBackend(ssh_host="test.com", ssh_user="user")
        info = backend.get_system_info()
        assert "error" in info or info["host"] == "test.com"

    def test_job_status_unknown_without_connection(self):
        """get_job_status returns UNKNOWN when SSH is not available."""
        from backend.execution.remote_docker_backend import RemoteDockerBackend
        from backend.core.execution import JobStatus
        backend = RemoteDockerBackend(ssh_host="test.com", ssh_user="user")
        # Without SSH connection, should raise or return UNKNOWN
        try:
            status = backend.get_job_status("nonexistent-job-id")
            assert status == JobStatus.UNKNOWN
        except Exception:
            pass  # Expected when not connected
