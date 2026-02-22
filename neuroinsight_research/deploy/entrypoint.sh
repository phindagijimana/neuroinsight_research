#!/bin/bash
# ==============================================================================
#  NeuroInsight Research -- Container Entrypoint
#
#  Starts the FastAPI backend via gunicorn with uvicorn workers.
#  The frontend is served as static files by nginx (separate process or
#  by the host's reverse proxy).
# ==============================================================================
set -euo pipefail

PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

echo "=== NeuroInsight Research ==="
echo "Environment: ${ENVIRONMENT:-production}"
echo "Backend port: ${PORT}"
echo "Workers: ${WORKERS}"
echo ""

# Run Alembic migrations if alembic.ini exists
if [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    python -m alembic upgrade head 2>/dev/null || echo "Migration skipped (falling back to create_all)"
fi

# Start gunicorn with uvicorn workers
exec gunicorn backend.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WORKERS}" \
    --bind "0.0.0.0:${PORT}" \
    --timeout 3600 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
