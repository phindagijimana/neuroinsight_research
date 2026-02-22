"""API routes for NeuroInsight application."""

from .cleanup import router as cleanup_router
from .jobs import router as jobs_router
from .metrics import router as metrics_router
from .placeholder import router as placeholder_router
from .reports import router as reports_router
from .upload_simple import router as upload_router
from .visualizations import router as visualizations_router

__all__ = ["cleanup_router", "jobs_router", "metrics_router", "placeholder_router", "reports_router", "upload_router", "visualizations_router"]

