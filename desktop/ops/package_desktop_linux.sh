#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/desktop/app"
DIST_DIR="$ROOT_DIR/desktop/dist"

echo "==> Packaging NIR Desktop (Linux)"
cd "$APP_DIR"
npm install --no-audit --no-fund
npm run check
npm run dist:linux

echo "==> Generating release metadata and checksums"
node "$ROOT_DIR/desktop/ops/release_metadata.js" "$DIST_DIR" "$DIST_DIR"

echo "==> Done. Artifacts in: $DIST_DIR"
