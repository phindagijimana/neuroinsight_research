# Quick Start Guide

## Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (with Docker Compose v2)
- 8GB+ RAM recommended

## Setup

```bash
# 1. Install everything (Python deps, npm packages, infrastructure, DB)
./research-dev install

# 2. Start all services
./research-dev start

# 3. Open the app
#    Frontend:  http://localhost:3000
#    API docs:  http://localhost:3001/docs
```

## Infrastructure

The app requires PostgreSQL, Redis, and MinIO. These are managed via Docker Compose:

```bash
# Start infrastructure
./research infra up

# Check infrastructure status
./research infra status

# Stop infrastructure
./research infra down

# Reset (deletes all data!)
./research infra reset
```

## Running a Job

1. Open http://localhost:3000
2. Navigate to "Jobs"
3. Select a pipeline (e.g., FreeSurfer)
4. Upload or select input files
5. Configure resources (CPU, RAM, GPU)
6. Submit the job
7. Monitor progress on the Dashboard
8. View results in the Viewer

## Troubleshooting

```bash
# Check all service status
./research-dev status

# View logs
./research-dev logs backend
./research-dev logs celery

# Restart everything
./research-dev restart

# Full health check
./research-dev health
```
