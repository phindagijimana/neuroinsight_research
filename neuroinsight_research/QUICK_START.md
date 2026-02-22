# Quick Start

## Prerequisites

- Python 3.9+, Node.js 18+, Docker (Compose v2), 8GB+ RAM

## Setup

```bash
./research-dev install    # First-time: deps + infra + DB
./research-dev start      # Launch all services
```

Open http://localhost:3000 (frontend) or http://localhost:3001/docs (API).

## Usage

1. Go to **Jobs** tab
2. Select a pipeline and upload input files
3. Configure resources (CPU, RAM, GPU)
4. Submit and monitor progress on the **Dashboard**
5. View results in the **Viewer**

## Infrastructure

```bash
./research infra up       # Start PostgreSQL, Redis, MinIO
./research infra status   # Check health
./research infra down     # Stop containers
./research infra reset    # Stop + delete all data
```

## Troubleshooting

```bash
./research-dev status     # Check all services
./research-dev logs all   # Tail all logs
./research-dev health     # Backend health endpoint
./research-dev restart    # Restart everything
```
