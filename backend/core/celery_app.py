"""
Celery Application Configuration

Provides async task execution via Redis broker.
Used for running Docker-based neuroimaging jobs without blocking the API.

Usage:
    from backend.core.celery_app import celery_app

    @celery_app.task(bind=True)
    def run_docker_job(self, job_id: str, spec_dict: dict):
        ...
"""

import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# -- Broker & backend URLs --
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "redis_secure_password")
REDIS_DB_BROKER = int(os.getenv("REDIS_DB_BROKER", "0"))
REDIS_DB_BACKEND = int(os.getenv("REDIS_DB_BACKEND", "1"))

broker_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_BROKER}"
backend_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_BACKEND}"

# -- Create Celery app --
celery_app = Celery(
    "neuroinsight",
    broker=broker_url,
    backend=backend_url,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Concurrency -- each worker handles at most 2 Docker jobs at once
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "2")),
    worker_prefetch_multiplier=1,  # Don't prefetch (jobs are heavy)

    # Results expire after 7 days
    result_expires=60 * 60 * 24 * 7,

    # Task routing
    task_routes={
        "backend.execution.celery_tasks.run_docker_job": {"queue": "docker_jobs"},
        "backend.execution.celery_tasks.pull_docker_image": {"queue": "docker_jobs"},
    },

    # Retry policy for broker connection
    broker_connection_retry_on_startup=True,

    # Task time limits (neuroimaging jobs can run for hours)
    task_time_limit=60 * 60 * 24,       # hard kill after 24 hours
    task_soft_time_limit=60 * 60 * 23,   # soft warning at 23 hours

    # Track task state changes
    task_track_started=True,
)

# Explicitly register task modules
celery_app.conf.update(
    include=["backend.execution.celery_tasks"],
)

logger.info(f"Celery configured: broker={REDIS_HOST}:{REDIS_PORT}")
