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
./research install    # Install deps, start infra, init DB
./research start      # Start backend + celery + frontend
# Frontend: http://localhost:3000
# API docs: http://localhost:3001/docs
```

## Docker Compose Deployment

For a fully containerized production deployment:

```bash
# Copy and edit environment variables
cp .env.example .env
# Edit .env to set secure passwords and SECRET_KEY

# Start the full stack (app, worker, PostgreSQL, Redis, MinIO, nginx)
docker compose up -d

# View logs
docker compose logs -f app

# Stop everything
docker compose down
```

Frontend: `http://localhost:3000`, API: `http://localhost:3001`

## CLI

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

## Connecting to Remote Servers / HPC

The app runs jobs locally by default. To run on a remote machine (cloud VM or HPC cluster), you connect via SSH. No passwords are stored -- authentication uses your SSH keys.

### SSH Key Setup (one-time)

If you already have an SSH key and can `ssh user@server` without a password, skip to [Connecting from the App](#connecting-from-the-app).

**1. Generate an SSH key pair** (on your local machine):

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

- `-t ed25519` selects the key type (modern and secure)
- `-C` (capital C) adds a comment to identify the key
- Press Enter to accept the default file location (`~/.ssh/id_ed25519`)
- Enter a passphrase when prompted (or leave empty)

This creates two files:
- `~/.ssh/id_ed25519` -- private key (never share this)
- `~/.ssh/id_ed25519.pub` -- public key (install this on remote servers)

**2. Install your public key on the remote server:**

```bash
ssh-copy-id user@server
```

This copies your public key to the server's `~/.ssh/authorized_keys`. You'll be prompted for your password one last time. After this, password-free login is set up.

**3. Load your key into the SSH agent:**

```bash
eval "$(ssh-agent -s)"     # Start the agent (if not running)
ssh-add ~/.ssh/id_ed25519  # Add your key (enter passphrase if set)
```

On macOS, the Keychain handles this automatically after first use. On Linux with GNOME/KDE, the desktop keyring does the same.

**4. Verify:**

```bash
ssh user@server
# Should connect without asking for a password
```

### Connecting from the App

On the **Jobs** page, choose your execution backend:

**Remote Server** (AWS EC2, Google Cloud, Azure, any Linux with Docker):

1. Click **Remote Server**
2. Enter Host (e.g., `54.123.45.67`) and Username (e.g., `ubuntu`)
3. Click **Connect** -- authenticates via your SSH agent
4. Browse remote files, select a plugin, and submit -- jobs run via `docker run` on the remote machine

**HPC with SLURM** (university/research clusters):

1. Click **HPC (SLURM)**
2. Enter Host (e.g., `hpc.university.edu`) and Username (e.g., `jsmith`)
3. Click **Connect**
4. Expand **Advanced Settings** to configure:
   - Work Directory (e.g., `/scratch/jsmith/neuroinsight`)
   - Partition (dropdown populated from the cluster)
   - Account (your SLURM allocation, e.g., `neuroscience_lab`)
5. Browse files on the HPC, select a plugin, and submit -- jobs are submitted via `sbatch` and run in Singularity containers

### How Authentication Works

The app uses `paramiko` (Python SSH library) which talks to your local `ssh-agent`. Your private key never leaves your machine and is never stored by the app. If you can `ssh` into a server from your terminal, you can connect from NeuroInsight -- it uses the exact same keys.

## License

See [license.txt](license.txt).
