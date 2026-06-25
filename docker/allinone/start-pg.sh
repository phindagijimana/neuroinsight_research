#!/usr/bin/env bash
# Postgres: initialize the data dir on first run, then serve on localhost only.
set -euo pipefail
PGDATA=/data/pgdata
PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)"

# A hard stop (force-quit / machine crash / `docker rm -f`) leaves a stale
# postmaster.pid that makes Postgres refuse to start ("lock file already exists").
# No other postmaster runs in this fresh container, so clear a stale lock.
if [ -f "$PGDATA/postmaster.pid" ]; then
  rm -f "$PGDATA/postmaster.pid"
fi

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  "$PGBIN/initdb" -D "$PGDATA" -U neuroinsight --auth-local=trust --auth-host=trust >/data/logs/initdb.log 2>&1
  {
    echo "listen_addresses='127.0.0.1'"
    echo "unix_socket_directories='/tmp'"
  } >> "$PGDATA/postgresql.conf"
fi

exec "$PGBIN/postgres" -D "$PGDATA" -k /tmp
