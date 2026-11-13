# Quick Start — developers

> **Engineers:** read **[docs/ENGINEERING.md](docs/ENGINEERING.md)** first (architecture, map, tests).  
> **Desktop users:** [docs/INSTALL.md](docs/INSTALL.md).

**Prerequisites:** Python 3.9+, Node 18+, Docker Compose v2.

```bash
./research install        # first time: deps + infra + DB
./research license        # FreeSurfer / MELD — docs/TOOL_LICENSES.md
./research start          # http://localhost:3000
./research stop           # stop app + infra (keep data)
./research status
./research health
./research-dev start      # hot-reload backend + frontend
```

**Tests:**

```bash
pip install -r requirements.txt pytest httpx
PYTHONPATH=. python -m pytest tests/ -v --tb=short
```
