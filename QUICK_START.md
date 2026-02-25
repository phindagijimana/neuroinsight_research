# Quick Start

## Prerequisites

- Python 3.9+, Node.js 18+, Docker (Compose v2), 8GB+ RAM

## Launch

```bash
./research start
```

Open **http://localhost:3000**. Everything is automatic on first run.

## Usage

1. Go to **Jobs** tab
2. Select a pipeline and upload input files
3. Configure resources (CPU, RAM, GPU)
4. Submit and monitor progress on the **Dashboard**
5. View results in the **Viewer**

## Commands

```bash
./research start          # Start the application
./research stop           # Stop the application
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
