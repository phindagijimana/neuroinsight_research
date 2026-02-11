# NeuroInsight Research

Neuroimaging pipeline platform for processing, monitoring, and visualizing brain MRI data.

## Features

- Run containerized pipelines (FreeSurfer, FastSurfer, fMRIPrep, QSIPrep, XCP-D) with configurable CPU/RAM/GPU
- Real-time job monitoring with progress tracking
- Built-in NIfTI viewer with segmentation overlays (Niivue)
- Plugin architecture with YAML-based pipeline definitions
- Three execution backends: Local Docker, Remote Server (EC2/cloud VMs via SSH), or HPC SLURM

## Tech Stack

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Niivue
**Backend:** Python 3.10+, FastAPI, Celery, SQLAlchemy
**Infrastructure:** PostgreSQL, Redis, MinIO, Docker

## Quick Start

Prerequisites: Python 3.9+, Node.js 18+, Docker with Compose v2

```bash
./research-dev install    # Install deps, start infra, init DB
./research-dev start      # Start backend + celery + frontend
# Frontend: http://localhost:3000
# API docs: http://localhost:3001/docs
```

## CLI

Both `./research` (production) and `./research-dev` (development):

```
install          Install dependencies, start infra, init DB
start / stop     Start or stop application services
status           Service and infrastructure health
infra up/down    Manage PostgreSQL, Redis, MinIO
db init/reset    Database schema management
logs [service]   Tail logs (backend|celery|frontend|all)
pull [image]     Pre-pull pipeline Docker images
health           Query /health API endpoint
```

## License

See [license.txt](license.txt).
