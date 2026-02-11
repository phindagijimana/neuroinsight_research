
'''
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
'''
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
    
    Validation:
    - Ports must be valid (1-65535)
    - Directories are created automatically if they don't exist
    - Backend type must be valid ('local' or 'slurm')
    - Database URL format validated
    
    Security:
    - SECRET_KEY must be changed in production
    - No sensitive defaults (all empty strings)
    - CORS origins validated and parsed
    """
    app_name: str = Field(default='NeuroInsight Research', description='Application display name')
    app_version: str = Field(default='1.0.0', description='Semantic version (updated on releases)')
    environment: str = Field(default='development', description='Runtime environment: development, staging, production')
    api_host: str = Field(default='0.0.0.0', description='API server bind address (0.0.0.0 = all interfaces)')
    api_port: int = Field(3003, 1024, 65535, 'API server port (3000-3050 range recommended)', **('default', 'ge', 'le', 'description'))
    cors_origins: str = Field(default='http://localhost:3000,http://localhost:5173', description='Comma-separated list of allowed frontend origins')
    
    def cors_origins_list(self = None):
        '''
        Parse CORS origins into list
        
        Returns:
            List of origin URLs with whitespace trimmed
            
        Example:
            "http://localhost:3000, https://app.example.com"
            -> ["http://localhost:3000", "https://app.example.com"]
        '''
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    # cors_origins_list = property(cors_origins_list)  # decompiler artifact
    database_url: str = Field(default='postgresql://neuroinsight:neuroinsight_secure_password@localhost:5432/neuroinsight', description='SQLAlchemy database URL (postgresql:// or sqlite://)')
    
    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v):
        '''Validate database URL format'''
        if not v.startswith(('sqlite://', 'postgresql://', 'mysql://')):
            raise ValueError('database_url must start with sqlite://, postgresql://, or mysql://')
        return v

    # validate_database_url = property(validate_database_url)  # decompiler artifact
    redis_host: str = Field(default='localhost', description='Redis host')
    redis_port: int = Field(default=6379, description='Redis port')
    redis_password: str = Field(default='redis_secure_password', description='Redis password')
    minio_host: str = Field(default='localhost', description='MinIO host')
    minio_port: int = Field(default=9000, description='MinIO port')
    minio_access_key: str = Field(default='minioadmin', description='MinIO access key')
    minio_secret_key: str = Field(default='minioadmin_secure', description='MinIO secret key')
    minio_secure: bool = Field(default=False, description='Use HTTPS for MinIO')
    data_dir: str = Field(default='./data', description='Base directory for all data storage')
    upload_dir: str = Field(default='./data/uploads', description='Directory for uploaded files (single file mode)')
    output_dir: str = Field(default='./data/outputs', description='Directory for job output results')
    pipelines_dir: str = Field(default='./pipelines', description='Directory containing pipeline YAML def initions')
    
    def ensure_directories(self = None):
        """
        Create all configured directories if they don't exist
        
        Call this during application startup to ensure filesystem structure.
        Sets permissions to 700 (owner read/write/execute only).
        """
        for dir_path in (self.data_dir, self.upload_dir, self.output_dir):
            path = Path(dir_path)
            path.mkdir(True, True, 448, **('parents', 'exist_ok', 'mode'))

    fs_license_path: Optional[str] = Field(default=None, description='Path to FreeSurfer license.txt file. If not set, the app auto-detects it from these locations (in order): 1) ./license.txt (app directory) 2) ./data/license.txt 3) $FREESURFER_HOME/license.txt 4) ~/.freesurfer/license.txt')
    
    def fs_license_resolved(self = None):
        '''
        Resolve the FreeSurfer license path by checking configured value
        first, then well-known locations.
        
        Returns:
            Absolute path to license.txt if found, None otherwise.
        '''
        if self.fs_license_path:
            p = Path(self.fs_license_path).resolve()
            if p.is_file():
                return str(p)
            search_paths = [
                None('./license.txt'),
                Path('./data/license.txt'),
                Path(os.environ.get('FREESURFER_HOME', '/nonexistent')) / 'license.txt',
                Path.home() / '.freesurfer' / 'license.txt']
            for candidate in search_paths:
                resolved = candidate.resolve()
                if resolved.is_file():
                    return str(resolved)
                return None

    # fs_license_resolved = property(fs_license_resolved)  # decompiler artifact
    backend_type: str = Field('local', "Execution backend: 'local' (Docker) or 'slurm' (HPC)", **('default', 'description'))
    
    @field_validator('backend_type')
    @classmethod
    def validate_backend_type(cls, v):
        '''Validate backend type'''
        v = v.lower().strip()
        if v not in ('local', 'slurm', 'pbs', 'local_docker'):
            raise ValueError(f'''backend_type must be \'local\' or \'slurm\', got: {v}''')
        return v

    # validate_backend_type = property(validate_backend_type)  # decompiler artifact
    max_concurrent_jobs: int = Field(2, 1, 100, 'Maximum concurrent jobs for local backend', **('default', 'ge', 'le', 'description'))
    hpc_host: Optional[str] = Field(default=None, description='HPC cluster hostname (e.g., hpc.university.edu)')
    hpc_user: Optional[str] = Field(default=None, description='HPC username (if different from local user)')
    hpc_work_dir: str = Field(default='/scratch', description='HPC working directory for job execution')
    hpc_partition: str = Field(default='general', description='Default SLURM partition for job submission')
    hpc_modules_to_load: Optional[str] = Field(None, "Comma-separated list of modules to load (e.g., 'python/3.9,cuda/11.8')", **('default', 'description'))
    log_level: str = Field(default='INFO', description='Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL')
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        '''Validate log level'''
        v = v.upper()
        valid_levels = [
            'DEBUG',
            'INFO',
            'WARNING',
            'ERROR',
            'CRITICAL']
        if v not in valid_levels:
            raise ValueError(f'''log_level must be one of: {', '.join(valid_levels)}''')
        return v

    # validate_log_level = property(validate_log_level)  # decompiler artifact
    log_file: Optional[str] = Field(default=None, description='Path to log file (if None, logs to stdout only)')
    secret_key: str = Field('dev-secret-change-in-production-INSECURE-32chars-minimum', 32, 'Secret key for JWT tokens and encryption (MUST change in production)', **('default', 'min_length', 'description'))
    
    def validate_secret_key(cls = None, v = field_validator('secret_key'), info = classmethod):
        '''Warn if using default secret key in production'''
        if info.data.get('environment') == 'production' and 'dev-secret' in v.lower():
            raise ValueError('CRITICAL: You must set a secure SECRET_KEY in production! Default dev key is INSECURE.')
        return v

    # validate_secret_key = property(validate_secret_key)  # decompiler artifact
    model_config = SettingsConfigDict('.env', 'utf-8', False, 'ignore', **('env_file', 'env_file_encoding', 'case_sensitive', 'extra'))


def get_settings():
    '''
    Get application settings (cached singleton)
    
    Settings are loaded once and cached for the application lifetime.
    Uses lru_cache to ensure single instance across all imports.
    
    Returns:
        Settings: Application configuration object
        
    Example:
        from backend.core.config import get_settings
        
        settings = get_settings()
        print(f"Running {settings.app_name} v{settings.app_version}")
        print(f"Backend: {settings.backend_type}")
        print(f"Database: {settings.database_url}")
    '''
    return Settings()

get_settings = None(get_settings)
