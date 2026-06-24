#!/usr/bin/env bash
# Entrypoint for the all-in-one container. Runs as root: prepares the data dirs
# (which may be a freshly-mounted host volume), then hands off to supervisord
# which runs every service as the unprivileged `neuroinsight` user.
set -euo pipefail

mkdir -p /data/pgdata /data/redis /data/minio /data/inputs /data/outputs /data/logs
chown -R neuroinsight:neuroinsight /data 2>/dev/null || true

# Per-install secrets: generated once and persisted on the data volume, so every
# deployment gets unique credentials instead of shipped defaults. Internal
# services bind to 127.0.0.1 only, but unique-per-install is the right baseline.
# A SECRET_KEY passed via `-e` on first run is honoured (then frozen on the
# volume for token stability across restarts).
SECRETS_FILE=/data/secrets.env
if [ ! -f "$SECRETS_FILE" ]; then
  rand() { tr -dc 'a-f0-9' < /dev/urandom | head -c "${1:-48}"; }
  ( umask 077; {
      echo "export REDIS_PASSWORD=$(rand 48)"
      echo "export MINIO_ROOT_USER=nir$(rand 8)"
      echo "export MINIO_ROOT_PASSWORD=$(rand 48)"
      echo "export SECRET_KEY=${SECRET_KEY:-$(rand 64)}"
    } > "$SECRETS_FILE" )
fi
chown neuroinsight:neuroinsight "$SECRETS_FILE" 2>/dev/null || true
chmod 600 "$SECRETS_FILE" 2>/dev/null || true

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
