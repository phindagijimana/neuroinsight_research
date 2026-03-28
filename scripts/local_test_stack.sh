#!/usr/bin/env bash
# Start infrastructure + Celery worker for local NIR testing (run API separately).
#
#   ./scripts/local_test_stack.sh up     # optional: docker infra, then Celery worker
#   ./scripts/local_test_stack.sh worker # Celery only (Redis must be reachable)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cmd="${1:-up}"

run_worker() {
  export PYTHONPATH="$ROOT"
  cd "$ROOT/backend"
  exec celery -A backend.core.celery_app:celery_app worker \
    --loglevel=info --concurrency=2 -Q docker_jobs,celery
}

case "$cmd" in
  worker)
    run_worker
    ;;
  up)
    if [[ -f "$ROOT/docker-compose.infra.yml" ]]; then
      docker compose -f "$ROOT/docker-compose.infra.yml" up -d db redis minio 2>/dev/null || true
      echo "Infra (db/redis/minio) started or already running."
    fi
    echo "Starting Celery worker. In another terminal run the API, e.g.:"
    echo "  cd $ROOT/backend && PYTHONPATH=$ROOT uvicorn backend.main:app --host 0.0.0.0 --port 3051"
    echo "Frontend dev server proxies /api to port 3051 (see frontend/vite.config.ts)."
    run_worker
    ;;
  *)
    echo "Usage: $0 [up|worker]"
    exit 1
    ;;
esac
