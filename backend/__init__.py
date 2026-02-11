"""
NeuroInsight Research - Backend System

HPC-native neuroimaging pipeline platform with a layered architecture.

Layers:
  1. API Layer (FastAPI) - main.py, routes/
  2. Core Business Logic - core/ (config, database, execution, pipelines)
  3. Domain Models - models/ (job entity)
  4. Execution Backends - execution/ (local Docker, SLURM)
"""

__version__ = "1.0.0"
__author__ = "NeuroInsight Research Team"

from backend.core.config import get_settings
from backend.core.database import get_db, init_db
from backend.core.pipelines import get_pipeline_registry
from backend.execution import get_backend

__all__ = [
    "get_settings",
    "get_db",
    "init_db",
    "get_pipeline_registry",
    "get_backend",
]
