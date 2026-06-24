# ==============================================================================
#  NeuroInsight — ALL-IN-ONE single container
#
#  Bundles the API + Celery worker + Postgres + Redis + MinIO + the built SPA in
#  ONE image, supervised by supervisord. The desktop app (or `run.sh`) launches
#  this single container — no separate infrastructure to set up.
#
#  Additive: does not change the native (./research) flow or the multi-container
#  docker-compose stack.
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

# ---- Stage 2: build Python deps into a venv (with build tools) --------------
FROM python:3.10-slim AS pybuild
ENV DEBIAN_FRONTEND=noninteractive PATH=/opt/venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# ---- Stage 3: slim runtime (no build tools) ---------------------------------
FROM python:3.10-slim AS allinone
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

# Runtime services only — no compilers. libpq5 (runtime) instead of libpq-dev.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gosu supervisor \
      postgresql postgresql-client \
      redis-server \
      openssh-client \
      libpq5 \
    && rm -rf /var/lib/apt/lists/*

# MinIO server binary (arch-aware)
RUN set -eux; arch="$(dpkg --print-architecture)"; \
    curl -fsSL "https://dl.min.io/server/minio/release/linux-${arch}/minio" -o /usr/local/bin/minio; \
    chmod +x /usr/local/bin/minio

# Docker CLI only (static binary) — to launch sibling job containers via the
# mounted host socket. Avoids pulling the full Docker engine.
RUN set -eux; \
    arch="$(uname -m)"; ver=27.3.1; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${arch}/docker-${ver}.tgz" -o /tmp/d.tgz; \
    tar -xzf /tmp/d.tgz -C /tmp; mv /tmp/docker/docker /usr/local/bin/docker; \
    rm -rf /tmp/docker /tmp/d.tgz

# Python deps from the build stage (no compilers in this image)
COPY --from=pybuild /opt/venv /opt/venv

RUN useradd --create-home --shell /bin/bash --uid 1000 neuroinsight
WORKDIR /home/neuroinsight/app
COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY workflows/ ./workflows/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY docker/allinone/ /opt/allinone/
RUN chmod +x /opt/allinone/*.sh

RUN mkdir -p /data && chown -R neuroinsight:neuroinsight /data /home/neuroinsight

EXPOSE 8000
ENTRYPOINT ["/opt/allinone/entrypoint.sh"]
