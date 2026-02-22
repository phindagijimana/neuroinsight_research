"""
Core configuration module for NeuroInsight web application.

This module handles all application settings using Pydantic Settings,
enabling type-safe configuration from environment variables.

Optimized for web deployment with SQLite and threading.
"""

import os
import platform
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


def get_platform_defaults():
    """
    Get platform-appropriate default paths for uploads and outputs.

    Returns appropriate directories based on the operating system:
    - Windows: Uses APPDATA directory (persistent, user-writable)
    - Linux: Uses XDG standard directory (~/.local/share)
    """
    system = platform.system()

    if system == "Windows":
        # Windows: Use APPDATA for persistent storage
        base_dir = Path(os.environ.get("APPDATA", tempfile.gettempdir())) / "NeuroInsight"
    else:
        # Linux: Use XDG Base Directory standard
        base_dir = Path.home() / ".local" / "share" / "neuroinsight"

    return {
        "upload_dir": str(base_dir / "uploads"),
        "output_dir": str(base_dir / "outputs")
    }


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    See .env.example for a complete list of configuration options.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure storage directories exist
        self._ensure_storage_directories()

    # Application Metadata
    app_name: str = "NeuroInsight"
    app_version: str = "1.0.0"
    environment: str = Field(default="production", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost:56052,http://127.0.0.1:56052",
        env="CORS_ORIGINS"
    )

    # API Bridge Configuration (for real FreeSurfer processing)
    api_bridge_url: str = Field(default="http://localhost:8080", env="API_BRIDGE_URL")
    use_real_freesurfer: bool = Field(default=False, env="USE_REAL_FREESURFER")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Update CORS origins to include the current API port
        if hasattr(self, 'api_port') and self.api_port != 8000:
            dynamic_origins = f"http://localhost:{self.api_port},http://127.0.0.1:{self.api_port}"
            if self.cors_origins:
                self.cors_origins = f"{self.cors_origins},{dynamic_origins}"
            else:
                self.cors_origins = dynamic_origins

    # File Storage - Platform-aware defaults (no manual setup required)
    upload_dir: str = Field(default_factory=lambda: get_platform_defaults()["upload_dir"], env="UPLOAD_DIR")
    output_dir: str = Field(default_factory=lambda: get_platform_defaults()["output_dir"], env="OUTPUT_DIR")

    max_upload_size: int = Field(default=1073741824, env="MAX_UPLOAD_SIZE")  # 1GB for web

    # PostgreSQL Database Configuration (Native Deployment)
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_user: str = Field(default="neuroinsight", env="POSTGRES_USER")
    postgres_password: str = Field(default="secure_password_change_in_production", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="neuroinsight", env="POSTGRES_DB")

    # Storage Configuration (MinIO/S3)
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="neuroinsight", env="MINIO_BUCKET")
    minio_use_ssl: bool = Field(default=False, env="MINIO_USE_SSL")

    # Task Queue Configuration (Redis/Celery)
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    force_celery: bool = Field(default=False, env="FORCE_CELERY")

    # Processing Configuration
    fastsurfer_container: str = Field(
        default="fastsurfer/fastsurfer:latest",
        env="FASTSURFER_CONTAINER"
    )
    processing_timeout: int = Field(default=25200, env="PROCESSING_TIMEOUT")  # 7 hours
    max_concurrent_jobs: int = Field(default=1, env="MAX_CONCURRENT_JOBS")  # Only 1 job running at a time
    docker_cleanup_wait_timeout: int = Field(default=30, env="DOCKER_CLEANUP_WAIT_TIMEOUT")  # seconds

    @property
    def freesurfer_container_prefix(self) -> str:
        """Return container name prefix for FreeSurfer jobs (env override supported)."""
        env_prefix = os.getenv("FREESURFER_CONTAINER_PREFIX")
        if env_prefix:
            return env_prefix
        if self.environment == "development":
            return "freesurfer-dev-job-"
        return "freesurfer-job-"

    # Security
    secret_key: str = Field(default="dev-secret-key-change-me", env="SECRET_KEY")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(self.cors_origins, str):
            # Handle wildcard - if set to "*", return ["*"] for FastAPI
            if self.cors_origins.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins if isinstance(self.cors_origins, list) else []

    def _ensure_storage_directories(self):
        """Ensure upload and output directories exist."""
        try:
            Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # If we can't create the directories, log warning but don't fail
            print(f"Warning: Could not create storage directories: {e}")
            print(f"Upload dir: {self.upload_dir}")
            print(f"Output dir: {self.output_dir}")

    @property
    def database_url(self) -> str:
        """
        Database URL with PostgreSQL support for native deployment.

        Tests PostgreSQL connection and falls back to SQLite if unavailable.
        """
        # Explicit override: respect DATABASE_URL if provided
        database_url_env = os.getenv('DATABASE_URL', '')
        if database_url_env and 'postgresql' in database_url_env:
            return database_url_env

        # Production mode: Check if PostgreSQL containers are running
        try:
            import subprocess
            # Check for both neuroinsight-db (docker-compose) and neuroinsight-postgres (direct)
            result = subprocess.run(['docker', 'ps', '-q', '-f', 'name=neuroinsight-db', '-f', 'name=neuroinsight-postgres'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                # PostgreSQL container is running, try to connect with credentials from env or settings
                try:
                    import psycopg2
                    # Use password from environment or settings
                    password = self.postgres_password
                    conn = psycopg2.connect(
                        host='localhost',
                        port=5432,
                        user=self.postgres_user,
                        password=password,
                        database=self.postgres_db,
                        connect_timeout=3
                    )
                    conn.close()
                    return f'postgresql://{self.postgres_user}:{password}@localhost:5432/{self.postgres_db}'
                except Exception:
                    pass  # Fall back to normal logic
        except Exception:
            pass  # Docker not available, continue

        # Check if PostgreSQL environment variables are explicitly set or DATABASE_URL contains postgresql
        postgres_env_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_DB']
        postgres_env_set = any(os.getenv(var) for var in postgres_env_vars)
        postgres_configured = postgres_env_set or 'postgresql' in database_url_env

        if postgres_configured:
            # If DATABASE_URL is explicitly set and contains postgresql, use it directly
            # Try to construct PostgreSQL URL and test connection
            try:
                password = self.postgres_password or ""
                postgres_url = f"postgresql://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

                # Test connection
                import psycopg2
                conn = psycopg2.connect(
                    host=self.postgres_host,
                    port=self.postgres_port,
                    user=self.postgres_user,
                    password=password,
                    database=self.postgres_db,
                    connect_timeout=5
                )
                conn.close()
                return postgres_url
            except Exception:
                # PostgreSQL not available, fall back to SQLite
                pass

        # Fallback to SQLite for development/compatibility
        return "sqlite:///./neuroinsight_web.db"

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields to be ignored


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Using lru_cache ensures settings are loaded once and reused.
    This is particularly useful for dependency injection in FastAPI.
    
    Returns:
        Settings: Application settings instance
    """
    return Settings()

