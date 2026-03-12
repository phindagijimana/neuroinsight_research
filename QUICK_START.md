# Quick Start

## Prerequisites

- Python 3.9+, Node.js 18+, Docker (Compose v2), 8GB+ RAM

## Setup and Launch

```bash
./research install        # Install deps, start infra, init DB
./research license        # Set up FreeSurfer / MELD license files
./research start          # Launch the app
./research stop           # Stop app + infra containers (keep data volumes)
./research stop app       # Stop app services only (keep infra running)
./research stop --all     # Stop everything and remove infra data volumes
```

Open **http://localhost:3000**.

## Usage

1. Go to **Jobs** tab
2. Select a pipeline and upload input files
3. Configure resources (CPU, RAM, GPU)
4. Submit and monitor progress on the **Dashboard**
5. View results in the **Viewer**

## Commands

```bash
./research install        # First-time setup (deps + infra + DB)
./research license        # Set up pipeline license files
./research start          # Start the application
./research stop           # Stop app + infra, keep DB/object data
./research stop app       # Stop app only, keep infra running
./research stop --all     # Stop app + infra and remove infra data
./research status         # Check all services
./research logs all       # Tail all logs
./research health         # Backend health endpoint
./research restart        # Restart everything
```

## Infrastructure

```bash
./research infra up       # Start PostgreSQL, Redis, MinIO
./research infra status   # Check health
./research infra down     # Stop containers
./research infra reset    # Stop + delete all data
```

## Development mode

```bash
./research-dev start      # Hot-reload backend + HMR frontend
./research-dev logs all   # Tail all logs
```
