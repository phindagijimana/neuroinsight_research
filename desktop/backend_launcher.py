#!/usr/bin/env python3
"""
NIR backend launcher — entry point for a self-contained (PyInstaller) backend.

Runs the existing FastAPI app under uvicorn with no external venv required.
When frozen by PyInstaller, repo data directories (plugins/, workflows/,
alembic/) are bundled next to the executable and exposed to the backend via
NIR_REPO_DIR so the plugin/workflow registry resolves them.

Usage:
    nir-backend --host 127.0.0.1 --port 3001
"""
import argparse
import os
import sys
from pathlib import Path


def _resolve_repo_dir() -> str:
    # Explicit override always wins.
    env = os.environ.get("NIR_REPO_DIR")
    if env and Path(env).exists():
        return str(Path(env).resolve())
    # Frozen build: data is unpacked alongside the executable / in _MEIPASS.
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return str(base)
    # Dev: repo root is two levels up from desktop/.
    return str(Path(__file__).resolve().parent.parent)


def main() -> int:
    parser = argparse.ArgumentParser(prog="nir-backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3001)
    args = parser.parse_args()

    repo_dir = _resolve_repo_dir()
    os.environ.setdefault("NIR_REPO_DIR", repo_dir)
    # The backend reads .env and resolves plugins/ relative to the working dir.
    try:
        os.chdir(repo_dir)
    except OSError:
        pass

    import uvicorn
    from backend.main import app  # imported here so PyInstaller traces backend.*

    uvicorn.run(app, host=args.host, port=args.port, workers=1, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
