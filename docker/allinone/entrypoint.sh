#!/usr/bin/env bash
# Entrypoint for the all-in-one container. Runs as root: prepares the data dirs
# (which may be a freshly-mounted host volume), then hands off to supervisord
# which runs every service as the unprivileged `neuroinsight` user.
set -euo pipefail

mkdir -p /data/pgdata /data/redis /data/minio /data/inputs /data/outputs /data/logs
chown -R neuroinsight:neuroinsight /data 2>/dev/null || true

# Local job execution (Docker-out-of-Docker): grant the neuroinsight user access
# to the mounted host docker socket by matching its group id.
if [ -S /var/run/docker.sock ]; then
  SOCK_GID="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || echo 0)"
  if [ "${SOCK_GID}" != "0" ]; then
    getent group "${SOCK_GID}" >/dev/null 2>&1 || groupadd -g "${SOCK_GID}" dockerhost || true
    GRP="$(getent group "${SOCK_GID}" | cut -d: -f1)"
    usermod -aG "${GRP}" neuroinsight || true
  else
    usermod -aG root neuroinsight || true
  fi
fi

exec supervisord -c /opt/allinone/supervisord.conf
