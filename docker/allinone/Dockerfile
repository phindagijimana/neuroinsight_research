# ==============================================================================
#  NeuroInsight Research — ALL-IN-ONE single container
#
#  Bundles the API + Celery worker + Postgres + Redis + MinIO + the built SPA in
#  ONE image, supervised by supervisord. The desktop app (or `run.sh`) launches
#  this single container — no separate infrastructure to set up.
#
#  This is ADDITIVE: it does not change the native (./research) flow or the
#  multi-container docker-compose stack.
#
#  Build (from repo root):
#    docker build -f docker/allinone/Dockerfile -t nir-allinone:dev .
# ==============================================================================

# ---- Stage 1: build the React SPA -------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: all-in-one runtime --------------------------------------------
FROM python:3.10-slim AS allinone
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# System services: Postgres, Redis, MinIO deps, supervisor, docker CLI (for
# launching sibling job containers), ssh client (Remote/HPC connectors).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gosu supervisor \
      postgresql postgresql-client \
      redis-server \
      openssh-client \
      libpq-dev build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

# MinIO server binary (arch-aware: amd64 / arm64)
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    curl -fsSL "https://dl.min.io/server/minio/release/linux-${arch}/minio" -o /usr/local/bin/minio; \
    chmod +x /usr/local/bin/minio

# Docker CLI (talks to the mounted host socket for local job execution)
RUN curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh || true

RUN useradd --create-home --shell /bin/bash --uid 1000 neuroinsight

WORKDIR /home/neuroinsight/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY workflows/ ./workflows/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY docker/allinone/ /opt/allinone/
RUN chmod +x /opt/allinone/*.sh

# /data holds Postgres + Redis + MinIO data + inputs/outputs (mount a host dir
# here for persistence).
RUN mkdir -p /data && chown -R neuroinsight:neuroinsight /data /home/neuroinsight

EXPOSE 8000
ENTRYPOINT ["/opt/allinone/entrypoint.sh"]
