# Quick Start — Developers (run from source)

> **Desktop users:** install the app from [docs/INSTALL.md](docs/INSTALL.md) instead —
> you do not need this guide.

## Prerequisites

- Python 3.9+, Node.js 18+, Docker (Compose v2), 8GB+ RAM

## Setup, run, and common commands

```bash
./research install        # deps + infra + DB (first time)
./research license        # FreeSurfer / MELD — see docs/TOOL_LICENSES.md
./research start          # launch → http://localhost:3000
./research stop           # stop app + infra (keep data)
./research stop app       # stop app only
./research stop --all     # stop and remove infra data
./research status         # service health
./research logs all       # tail logs
./research health         # backend /health
./research restart
```

## Infrastructure only

```bash
./research infra up       # PostgreSQL, Redis, MinIO
./research infra status
./research infra down
./research infra reset    # stop + delete data
```

## Development mode

```bash
./research-dev start      # hot-reload backend + HMR frontend
./research-dev logs all
```
