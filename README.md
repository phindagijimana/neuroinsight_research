# NeuroInsight Research

A professional-grade, HPC-native neuroimaging pipeline platform for processing, monitoring, and visualizing brain MRI data.

## Overview

NeuroInsight Research provides a unified interface for running neuroimaging analysis pipelines (FreeSurfer, FastSurfer, fMRIPrep, QSIPrep, XCP-D, and more) on local workstations or HPC clusters via SLURM.

### Key Features

- **Pipeline Execution** -- Run containerized neuroimaging pipelines with configurable resources
- **Job Management** -- Submit, monitor, and manage processing jobs with real-time progress tracking
- **Result Visualization** -- Built-in NIfTI viewer with segmentation overlays via Niivue
- **Resource Configuration** -- CPU, RAM, GPU, and parallelization settings per job
- **Plugin Architecture** -- YAML-based pipeline definitions with resource profiles
- **Dual Backends** -- Local Docker execution (development) and SLURM HPC (production)

## Architecture

```
Frontend (React + Vite)          Backend (FastAPI + Celery)
+-------------------+           +-------------------------+
| Navigation        |           | REST API (/api/*)       |
| Pipeline Selector | <-------> | Plugin/Workflow Registry |
| Job Monitor       |    HTTP   | Job Scheduler           |
| Result Viewer     |           | Celery Workers          |
+-------------------+           +-------------------------+
                                         |
                         +---------------+---------------+
                         |               |               |
                    PostgreSQL        Redis          MinIO
                    (jobs DB)       (broker)      (storage)
```

## Quick Start

```bash
# Clone and enter the project
cd neuroinsight_research

# First-time setup (installs deps, starts infra, creates DB)
./research-dev install

# Start all services (backend, celery, frontend)
./research-dev start

# Open in browser
# Frontend: http://localhost:3000
# API docs: http://localhost:3001/docs
```

## CLI Reference

Both `./research` (production) and `./research-dev` (development) support:

| Command              | Description                                  |
|----------------------|----------------------------------------------|
| `install`            | Install dependencies, start infra, init DB   |
| `start`              | Start all application services               |
| `stop`               | Stop application services                    |
| `restart`            | Restart all services                         |
| `status`             | Show service and infrastructure health       |
| `health`             | Query backend /health endpoint               |
| `logs [service]`     | Tail logs (backend, celery, frontend, all)   |
| `infra up`           | Start PostgreSQL, Redis, MinIO               |
| `infra down`         | Stop infrastructure containers               |
| `infra reset`        | Stop infra and delete all data volumes       |
| `db init`            | Create/verify database tables                |
| `db reset`           | Drop and recreate all tables                 |
| `db shell`           | Open interactive PostgreSQL shell            |
| `pull [image\|all]`  | Pre-pull pipeline Docker images              |
| `clean`              | Remove logs, caches, stale containers        |
| `env`                | Print resolved configuration                 |

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Niivue
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic
- **Task Queue**: Celery with Redis broker
- **Database**: PostgreSQL 16
- **Storage**: MinIO (S3-compatible)
- **Containers**: Docker (local), Singularity (HPC)

## Project Structure

```
neuroinsight_research/
  backend/               # Python backend
    core/                # Config, database, pipeline registry
    execution/           # Docker & SLURM backends
    models/              # SQLAlchemy models
    routes/              # API routes
    main.py              # FastAPI application
  frontend/              # React frontend
    src/
      components/        # Reusable UI components
      pages/             # Page-level components
      services/          # API client
      types/             # TypeScript interfaces
  plugins/               # Pipeline YAML definitions
  workflows/             # Multi-step workflow definitions
  research               # Production CLI
  research-dev           # Development CLI
  .research-common.sh    # Shared CLI library
  docker-compose.infra.yml  # Infrastructure services
```

## Supported Pipelines

| Pipeline    | Description                          | Container                      |
|-------------|--------------------------------------|--------------------------------|
| FreeSurfer  | Cortical reconstruction              | freesurfer/freesurfer:7.4.1    |
| FastSurfer  | GPU-accelerated segmentation         | deepmi/fastsurfer:latest       |
| fMRIPrep    | Functional MRI preprocessing         | nipreps/fmriprep:24.0.0       |
| QSIPrep     | Diffusion MRI preprocessing          | pennbbl/qsiprep:0.22.0        |
| XCP-D       | Functional connectivity              | pennbbl/xcp_d:0.7.0           |

## Development

```bash
# Development mode (hot reload for both frontend and backend)
./research-dev start

# Check status
./research-dev status

# Watch logs
./research-dev logs all

# Stop
./research-dev stop
```

## License

See [license.txt](license.txt) for details.
