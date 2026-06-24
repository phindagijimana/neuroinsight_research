#!/usr/bin/env bash
# Redis with the per-install password from nir-env.sh (-> /data/secrets.env).
set -euo pipefail
# shellcheck disable=SC1091
source /opt/allinone/nir-env.sh
exec redis-server --bind 127.0.0.1 --dir /data/redis --save "" --requirepass "$REDIS_PASSWORD"
