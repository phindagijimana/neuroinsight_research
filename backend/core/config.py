"""
Configuration Management

Centralized, type-safe configuration using Pydantic Settings.
Supports environment variables, .env files, and defaults.

CONFIGURATION SOURCES (Priority Order):
1. Environment variables (highest priority)
2. .env file in project root
3. Default values defined in this file

USAGE:
    from backend.core.config import get_settings

    settings = get_settings()
    print(f"API running on {settings.api_host}:{settings.api_port}")
    print(f"Backend type: {settings.backend_type}")

ENVIRONMENT VARIABLES:
    See .env.example for complete list and descriptions
"""
import os
from pathlib import Path
from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, computed_field


class Settings(BaseSettings):
    """
    Application Configuration

    Type-safe settings with automatic environment variable parsing.
    All settings can be overridden via environment variables.
    """

    # -- Application --
    app_name: str = Field(default="NeuroInsight Research", description="Application display name")
    app_version: str = Field(default="1.0.0", description="Semantic version")
    environment: str = Field(default="development", description="Runtime environment: development, staging, production")

    # -- API Server --
    api_host: str = Field(default="0.0.0.0", description="API server bind address")
    api_port: int = Field(default=3003, ge=1024, le=65535, description="API server port")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed frontend origins",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list.

        Example:
            "http://localhost:3000, https://app.example.com"
            -> ["http://localhost:3000", "https://app.example.com"]
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # -- Database --
    database_url: str = Field(
        default="postgresql://neuroinsight:neuroinsight_secure_password@localhost:5432/neuroinsight",
        description="SQLAlchemy database URL (postgresql:// or sqlite://)",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(("sqlite://", "postgresql://", "mysql://")):
            raise ValueError("database_url must start with sqlite://, postgresql://, or mysql://")
        return v

    # -- Redis --
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: str = Field(default="redis_secure_password", description="Redis password")

    # -- MinIO --
    minio_host: str = Field(default="localhost", description="MinIO host")
    minio_port: int = Field(default=9000, description="MinIO port")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin_secure", description="MinIO secret key")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")

    # -- Directories --
    data_dir: str = Field(default="./data", description="Base directory for all data storage")
    upload_dir: str = Field(default="./data/uploads", description="Directory for uploaded files")
    output_dir: str = Field(default="./data/outputs", description="Directory for job output results")
    pipelines_dir: str = Field(default="./pipelines", description="Directory containing pipeline YAML definitions")

    def ensure_directories(self) -> None:
        """Create all configured directories if they don't exist."""
        for dir_path in (self.data_dir, self.upload_dir, self.output_dir):
            Path(dir_path).mkdir(parents=True, exist_ok=True, mode=0o700)

    # -- FreeSurfer License --
    fs_license_path: Optional[str] = Field(
        default=None,
        description="Path to FreeSurfer license.txt file. Auto-detected if not set.",
    )

    @property
    def fs_license_resolved(self) -> Optional[str]:
        """Resolve the FreeSurfer license path by checking configured value
        first, then well-known locations.

        Returns:
            Absolute path to license.txt if found, None otherwise.
        """
        if self.fs_license_path:
            p = Path(self.fs_license_path).resolve()
            if p.is_file():
                return str(p)

        search_paths = [
            Path("./license.txt"),
            Path("./data/license.txt"),
            Path(os.environ.get("FREESURFER_HOME", "/nonexistent")) / "license.txt",
            Path.home() / ".freesurfer" / "license.txt",
        ]
        for candidate in search_paths:
            resolved = candidate.resolve()
            if resolved.is_file():
                return str(resolved)
        return None

    # -- MELD Graph License --
    meld_license_path: Optional[str] = Field(
        default=None,
        description="Path to MELD Graph meld_license.txt file. Auto-detected if not set.",
    )

    @property
    def meld_license_resolved(self) -> Optional[str]:
        """Resolve the MELD Graph license path."""
        if self.meld_license_path:
            p = Path(self.meld_license_path).resolve()
            if p.is_file():
                return str(p)

        search_paths = [
            Path("./meld_license.txt"),
            Path("./data/meld_license.txt"),
            Path.home() / ".meld" / "meld_license.txt",
        ]
        for candidate in search_paths:
            resolved = candidate.resolve()
            if resolved.is_file():
                return str(resolved)
        return None

    # -- Execution Backend --
    backend_type: str = Field(default="local", description="Execution backend: 'local', 'remote_docker', or 'slurm'")

    @field_validator("backend_type")
    @classmethod
    def validate_backend_type(cls, v: str) -> str:
        """Validate backend type."""
        v = v.lower().strip()
        if v not in ("local", "remote_docker", "slurm", "pbs", "local_docker"):
            raise ValueError(f"backend_type must be 'local', 'remote_docker', or 'slurm', got: {v}")
        return v

    max_concurrent_jobs: int = Field(default=2, ge=1, le=100, description="Maximum concurrent jobs for local backend")

    # -- Remote Server Settings (EC2, cloud VMs, any SSH-accessible Linux) --
    remote_host: Optional[str] = Field(default=None, description="Remote server hostname (EC2, cloud VM, etc.)")
    remote_user: Optional[str] = Field(default=None, description="Remote server SSH username")
    remote_work_dir: str = Field(default="/tmp/neuroinsight", description="Working directory on remote server")

    # -- HPC/SLURM Settings --
    hpc_host: Optional[str] = Field(default=None, description="HPC cluster hostname")
    hpc_user: Optional[str] = Field(default=None, description="HPC username")
    hpc_work_dir: str = Field(default="/scratch", description="HPC working directory")
    hpc_partition: str = Field(default="general", description="Default SLURM partition")
    hpc_account: Optional[str] = Field(default=None, description="SLURM account/allocation name")
    hpc_qos: Optional[str] = Field(default=None, description="SLURM QoS level")
    hpc_ssh_port: int = Field(default=22, ge=1, le=65535, description="SSH port for HPC connection")
    hpc_ssh_key_path: Optional[str] = Field(default=None, description="Path to SSH private key (None = use agent)")
    hpc_container_runtime: str = Field(default="singularity", description="Container runtime on HPC: singularity or apptainer")
    hpc_modules_to_load: Optional[str] = Field(
        default=None,
        description="Comma-separated list of modules to load (e.g., 'singularity/3.8,cuda/11.8')",
    )

    # -- Logging --
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        v = v.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v

    log_file: Optional[str] = Field(default=None, description="Path to log file (None = stdout only)")

    # -- Security --
    secret_key: str = Field(
        default="dev-secret-change-in-production-INSECURE-32chars-minimum",
        min_length=32,
        description="Secret key for JWT tokens and encryption",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Warn if using default secret key in production."""
        if info.data.get("environment") == "production" and "dev-secret" in v.lower():
            raise ValueError("CRITICAL: You must set a secure SECRET_KEY in production!")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached singleton).

    Settings are loaded once and cached for the application lifetime.
    """
    return Settings()
