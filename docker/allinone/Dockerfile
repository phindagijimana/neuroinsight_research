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

# ---- MinIO server binary ----------------------------------------------------
# MinIO archived its open-source project in 2025 and removed all community
# downloads: dl.min.io returns HTTP 410 Gone and docker.io/minio/minio is no
# longer pullable. The Chainguard image still ships a current, multi-arch
# `minio` binary at /usr/bin/minio (AGPLv3, same license as before). buildx
# selects the matching arch automatically for each target platform.
FROM cgr.dev/chainguard/minio:latest AS minio-src

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

# MinIO server binary — copied from the Chainguard image (see minio-src stage).
COPY --from=minio-src /usr/bin/minio /usr/local/bin/minio
RUN chmod +x /usr/local/bin/minio

# Docker CLI only (static binary) — to launch sibling job containers via the
# mounted host socket. Avoids pulling the full Docker engine.
RUN set -eux; \
    arch="$(uname -m)"; ver=27.3.1; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${arch}/docker-${ver}.tgz" -o /tmp/d.tgz; \
    tar -xzf /tmp/d.tgz -C /tmp; mv /tmp/docker/docker /usr/local/bin/docker; \
    rm -rf /tmp/docker /tmp/d.tgz

# Pennsieve Agent/CLI — required for Pennsieve UPLOADS (manifest upload runs
# through this binary). Upstream ships a Linux binary for amd64 only (inside the
# .deb); there is no Linux arm64 build. On arm64 the image still builds and
# Pennsieve *downloads* (REST/presigned) work, but uploads are unavailable.
ARG TARGETARCH
RUN set -eux; \
    if [ "${TARGETARCH:-amd64}" = "amd64" ]; then \
      ver=2.1.1; \
      curl -fsSL "https://github.com/Pennsieve/pennsieve-agent/releases/download/v${ver}/pennsieve_${ver}_amd64.deb" -o /tmp/penn.deb; \
      dpkg-deb -x /tmp/penn.deb /tmp/penn; \
      install -m 0755 /tmp/penn/opt/pennsieve/pennsieve /usr/local/bin/pennsieve; \
      rm -rf /tmp/penn /tmp/penn.deb; \
    else \
      echo "WARNING: no Pennsieve Agent binary for ${TARGETARCH}; Pennsieve uploads unavailable on this arch (downloads still work)."; \
    fi

# Python deps from the build stage (no compilers in this image)
COPY --from=pybuild /opt/venv /opt/venv

RUN useradd --create-home --shell /bin/bash --uid 1000 neuroinsight
WORKDIR /home/neuroinsight/app
COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY workflows/ ./workflows/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY VERSION ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY docker/allinone/ /opt/allinone/
RUN chmod +x /opt/allinone/*.sh

RUN mkdir -p /data && chown -R neuroinsight:neuroinsight /data /home/neuroinsight

EXPOSE 8000
ENTRYPOINT ["/opt/allinone/entrypoint.sh"]
