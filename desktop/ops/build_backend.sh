#!/usr/bin/env bash
# Build a self-contained NIR backend with PyInstaller so the desktop app does
# not require a separate `./research install` venv on the target machine.
#
# Output: desktop/dist/backend/nir-backend/nir-backend  (onedir bundle)
# backendManager.js auto-detects this binary and prefers it over python+uvicorn.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${NIR_BUILD_PYTHON:-$ROOT_DIR/venv/bin/python}"
DIST="$ROOT_DIR/desktop/dist/backend"
WORK="$ROOT_DIR/desktop/dist/backend-build"

echo "==> Building self-contained NIR backend (PyInstaller)"
echo "    python: $PY"

"$PY" -m pip install --quiet --upgrade pyinstaller

"$PY" -m PyInstaller \
  --noconfirm --clean \
  --name nir-backend \
  --distpath "$DIST" \
  --workpath "$WORK" \
  --specpath "$WORK" \
  --collect-all fastapi \
  --collect-all starlette \
  --collect-all uvicorn \
  --collect-all pydantic \
  --collect-all pydantic_settings \
  --collect-all sqlalchemy \
  --collect-all alembic \
  --collect-all celery \
  --collect-all kombu \
  --collect-all redis \
  --collect-all minio \
  --collect-all paramiko \
  --collect-submodules backend \
  --add-data "$ROOT_DIR/plugins:plugins" \
  --add-data "$ROOT_DIR/workflows:workflows" \
  --add-data "$ROOT_DIR/alembic:alembic" \
  --add-data "$ROOT_DIR/alembic.ini:." \
  "$ROOT_DIR/desktop/backend_launcher.py"

echo "==> Done: $DIST/nir-backend/nir-backend"
echo "    Smoke test:  $DIST/nir-backend/nir-backend --host 127.0.0.1 --port 3055"
