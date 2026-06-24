#!/usr/bin/env bash
# Launch the NIR all-in-one container (the single-container deployment).
# This is what the Electron desktop app will call (Phase B). Mounts:
#   - a host data dir (persistence)
#   - the host Docker socket (so the backend can run sibling job containers)
#   - the user's ~/.ssh + SSH agent (so Remote/HPC connectors keep working)
set -euo pipefail

IMAGE="${NIR_IMAGE:-nir-allinone:dev}"
DATA_DIR="${NIR_DATA_DIR:-$HOME/.nir/data}"
PORT="${NIR_PORT:-8800}"
NAME="${NIR_NAME:-nir-allinone}"
mkdir -p "$DATA_DIR"

docker rm -f "$NAME" >/dev/null 2>&1 || true
ARGS=(-d --name "$NAME" -p "127.0.0.1:${PORT}:8000" -v "${DATA_DIR}:/data")

# Local job execution: Docker-out-of-Docker via the host socket.
if [ -S /var/run/docker.sock ]; then
  ARGS+=(-v /var/run/docker.sock:/var/run/docker.sock)
fi

# Remote / HPC connectors: SSH keys (read-only) + agent.
if [ -d "$HOME/.ssh" ]; then
  ARGS+=(-v "$HOME/.ssh:/home/neuroinsight/.ssh:ro")
fi
if [ -S /run/host-services/ssh-auth.sock ]; then
  # Docker Desktop (macOS/Windows) host SSH agent.
  ARGS+=(-v /run/host-services/ssh-auth.sock:/ssh-agent -e SSH_AUTH_SOCK=/ssh-agent)
elif [ -n "${SSH_AUTH_SOCK:-}" ] && [ -S "${SSH_AUTH_SOCK}" ]; then
  ARGS+=(-v "${SSH_AUTH_SOCK}:/ssh-agent" -e SSH_AUTH_SOCK=/ssh-agent)
fi

docker run "${ARGS[@]}" "$IMAGE"
echo "NIR (all-in-one) → http://127.0.0.1:${PORT}"
echo "  data: ${DATA_DIR}   logs: docker logs -f ${NAME}"
