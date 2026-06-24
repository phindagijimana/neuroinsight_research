#!/usr/bin/env bash
# Shared runtime config for the all-in-one container. Internal services all live
# on localhost inside this one container (matching the app's default hostnames),
# so there is no Docker network / DNS / multi-port surface.
export ENVIRONMENT=production
export DATABASE_URL="postgresql://neuroinsight@127.0.0.1:5432/neuroinsight"
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
export REDIS_PASSWORD=nirredis
export MINIO_HOST=127.0.0.1
export MINIO_PORT=9000
export MINIO_ACCESS_KEY=niradmin
export MINIO_SECRET_KEY=nirminio123
export MINIO_SECURE=false
export SECRET_KEY="${SECRET_KEY:-nir-allinone-development-secret-key-change-me}"
export DATA_DIR=/data
export BACKEND_TYPE="${BACKEND_TYPE:-local}"
