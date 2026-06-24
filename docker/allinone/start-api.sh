#!/usr/bin/env bash
# API: wait for the bundled services, ensure DB exists + migrated, serve API+SPA.
set -euo pipefail
cd /home/neuroinsight/app
# shellcheck disable=SC1091
source /opt/allinone/nir-env.sh
export PATH="$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1):$PATH"

echo "[api] waiting for postgres…"
until pg_isready -h 127.0.0.1 -U neuroinsight >/dev/null 2>&1; do sleep 1; done
psql -h 127.0.0.1 -U neuroinsight -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='neuroinsight'" | grep -q 1 \
  || createdb -h 127.0.0.1 -U neuroinsight neuroinsight

echo "[api] waiting for redis…"
until redis-cli -h 127.0.0.1 -a "$REDIS_PASSWORD" ping >/dev/null 2>&1; do sleep 1; done
echo "[api] waiting for minio…"
until curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; do sleep 1; done

echo "[api] running migrations…"
alembic upgrade head >/data/logs/alembic.log 2>&1 || echo "[api] alembic non-zero (continuing)"

echo "[api] starting uvicorn on :8000"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
