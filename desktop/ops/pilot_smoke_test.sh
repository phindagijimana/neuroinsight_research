#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/desktop/app"
DIST_DIR="$ROOT_DIR/desktop/dist"

echo "==> Phase 5 pilot smoke checks"
echo "Repo: $ROOT_DIR"

echo "==> Checking desktop source integrity"
cd "$APP_DIR"
npm run check

echo "==> Checking Linux artifacts and metadata"
if [ ! -d "$DIST_DIR" ]; then
  echo "ERROR: desktop dist directory not found: $DIST_DIR" >&2
  exit 1
fi

if ! ls "$DIST_DIR"/*.AppImage >/dev/null 2>&1; then
  echo "ERROR: no AppImage artifact found under $DIST_DIR" >&2
  exit 1
fi

if [ ! -f "$DIST_DIR/desktop-release-metadata.json" ]; then
  echo "ERROR: desktop-release-metadata.json missing" >&2
  exit 1
fi

if [ ! -f "$DIST_DIR/desktop-release-sha256.txt" ]; then
  echo "ERROR: desktop-release-sha256.txt missing" >&2
  exit 1
fi

echo "==> Validating metadata JSON format"
METADATA_PATH="$DIST_DIR/desktop-release-metadata.json" python3 - <<'PY'
import json
import os
from pathlib import Path
p = Path(os.environ["METADATA_PATH"])
data = json.loads(p.read_text())
assert "artifacts" in data and isinstance(data["artifacts"], list), "metadata artifacts missing"
print(f"metadata artifacts: {len(data['artifacts'])}")
PY

echo "==> Pilot smoke checks passed"
