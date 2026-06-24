#!/usr/bin/env bash
# Celery worker: wait for the broker + DB, then process jobs.
set -euo pipefail
cd /home/neuroinsight/app
# shellcheck disable=SC1091
source /opt/allinone/nir-env.sh
export PATH="$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1):$PATH"

until redis-cli -h 127.0.0.1 -a nirredis ping >/dev/null 2>&1; do sleep 1; done
until pg_isready -h 127.0.0.1 -U neuroinsight >/dev/null 2>&1; do sleep 1; done
sleep 4  # let the API run migrations first

exec celery -A backend.core.celery_app:celery_app worker --loglevel=info --concurrency=2 -Q docker_jobs,celery
