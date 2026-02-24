# NeuroInsight

Automated hippocampal segmentation and analysis from T1-weighted MRI scans using FreeSurfer.

## Platform Support

- **Linux:** Ubuntu 20.04+ (native installation)
- **Windows:** WSL2 with systemd (full support - see Docker Installation section below)
- **Docker:** Full containerized deployment available

## Requirements

- Ubuntu 20.04+ Linux (or WSL2 on Windows)
- Docker and Docker Compose
- Redis (message broker for job processing)
- 16GB+ RAM (32GB recommended)
- 4+ CPU cores, 50GB storage
- FreeSurfer license (free for research)

## Docker Installation

Docker is required for NeuroInsight. If you need help installing Docker:

**See docs/USER_GUIDE.md for detailed Docker installation instructions for:**
- Linux (Ubuntu/Debian)
- Windows (WSL2)
- Docker Desktop configuration
- Troubleshooting common issues

## FreeSurfer Setup

NeuroInsight requires a FreeSurfer license for MRI processing. FreeSurfer is free for research use.

### Get FreeSurfer License

1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html
2. Complete the registration form
3. Save the license file as `license.txt` in your NeuroInsight project directory

### License File Location

The license file must be named `license.txt` and placed in the root directory of the NeuroInsight project.

Example structure:
```
neuroinsight_local/
├── neuroinsight
├── license.txt
├── data/
└── ...
```

## Quick Start

### Native Linux (Ubuntu 20.04+)

```bash
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local

# For WSL users: Check environment first (optional but recommended)
./neuroinsight check-wsl

# Install (one-time setup - auto-detects Linux/WSL)
./neuroinsight install

# Setup FreeSurfer license
./neuroinsight license

# Start NeuroInsight
./neuroinsight start

# Access at http://localhost:8000
```

**Best for:** Direct Ubuntu/Debian installation with systemd services

---

### Linux Docker (Ubuntu 20.04+ / WSL2)

```bash
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local/deploy

# Install and run (auto-pulls from Docker Hub)
./neuroinsight-docker install

# Access at http://localhost:8000
```

**Best for:** Containerized deployment, isolated environment, easy updates

---

### Windows Docker (Windows 10/11)

```powershell
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local\neuroinsight_windows

# Install Docker Desktop first:
# https://www.docker.com/products/docker-desktop/

# Install NeuroInsight
.\neuroinsight-docker.ps1 install

# Access at http://localhost:8000
```

**Best for:** Windows users, uses Docker Desktop with WSL2 backend

---

## Desktop Application Available

NeuroInsight is now available as a native desktop application with one-click installers:

- **Windows & Linux:** Download from [neuroinsight_desktop releases](https://github.com/phindagijimana/neuroinsight_desktop/releases)
- **Easy Installation:** No command line required
- **Native Experience:** System tray, desktop shortcuts, modern UI

**Choose Desktop App if you want:**
- Easiest installation (click and run)
- Native desktop experience
- Perfect for researchers and clinicians

**Choose Docker/Native if you want:**
- Server deployments
- HPC cluster integration
- Multi-user environments
- Advanced customization

---

### Deployment Comparison

| Feature | Native Linux | Linux Docker | Windows Docker | Desktop App |
|---------|--------------|--------------|----------------|-------------|
| **Platform** | Ubuntu 20.04+ | Ubuntu 20.04+ / WSL2 | Windows 10/11 | Windows 10/11, Linux |
| **Installation** | Direct on system | Containerized | Containerized via WSL2 | One-click installer |
| **Updates** | Manual | One command | One command | Auto-update |
| **Isolation** | System-wide | Containerized | Containerized | Containerized |
| **Best For** | Direct Linux install | Isolated environments | Windows users | Researchers, clinicians |

---

## File Requirements

NeuroInsight processes T1-weighted MRI scans only. Filenames must contain:
`t1`, `t1w`, `t1-weighted`, `mprage`, `spgr`, `tfl`, `tfe`, `fspgr`

Supported formats: NIfTI (`.nii`, `.nii.gz`) only.

## Commands Management

| Command | Native Linux<br>`./neuroinsight` | Linux Docker<br>`./neuroinsight-docker` | Windows Docker<br>`.\neuroinsight-docker.ps1` |
|---------|----------------------------------|----------------------------------------|---------------------------------------------|
| **Installation** | `install` | `install` | `install` |
| **Start** | `start` | `start` | `start` |
| **Stop** | `stop` | `stop` | `stop` |
| **Restart** | _(stop + start)_ | `restart` | `restart` |
| **Status** | `status` | `status` | `status` |
| **Health Check** | `monitor` | `health` | `health` |
| **View Logs** | `logs` | `logs` | `logs` |
| **Clean Jobs** | `clean` | `clean` | `clean` |
| **Recover Job** | `bring <job_id>` | `bring <job_id>` | _(not implemented)_ |
| **License** | `license` | `license` | `license` |
| **Update** | _(manual)_ | `update` | `update` |
| **Backup** | _(manual)_ | `backup` | `backup` |
| **Restore** | _(manual)_ | `restore <file>` | `restore <file>` |
| **Remove/Uninstall** | `reinstall` | _(manual)_ | `remove` |
| **Sleep Prevention** | `nosleep` | _(not needed)_ | _(not needed)_ |

### Command Examples

#### Native Linux
```bash
cd neuroinsight_local
./neuroinsight install          # One-time setup
./neuroinsight start            # Start services
./neuroinsight status           # Check health
./neuroinsight logs             # View logs
./neuroinsight clean            # Clean old jobs
./neuroinsight bring <job_id>   # Recover completed job
```

#### Linux Docker
```bash
cd neuroinsight_local/deploy
./neuroinsight-docker install       # Install and run
./neuroinsight-docker status        # Check status
./neuroinsight-docker logs          # View logs
./neuroinsight-docker logs backend  # Backend logs only
./neuroinsight-docker clean         # Clean old jobs (30+ days)
./neuroinsight-docker clean 7       # Clean jobs older than 7 days
./neuroinsight-docker backup        # Backup data
./neuroinsight-docker update        # Update to latest version
```

#### Windows Docker
```powershell
cd neuroinsight_windows
.\neuroinsight-docker.ps1 install           # Install and run
.\neuroinsight-docker.ps1 status            # Check status
.\neuroinsight-docker.ps1 logs              # View all logs
.\neuroinsight-docker.ps1 logs backend      # Backend logs only
.\neuroinsight-docker.ps1 clean             # Clean old jobs (30+ days)
.\neuroinsight-docker.ps1 clean 7           # Clean jobs older than 7 days
.\neuroinsight-docker.ps1 backup            # Backup data
.\neuroinsight-docker.ps1 restore backup.tar.gz  # Restore from backup
.\neuroinsight-docker.ps1 update            # Update to latest version
```

### Command Notes

- **Native Linux:** Uses systemd services, runs directly on Linux
- **Linux/Windows Docker:** Uses Docker containers, identical functionality across platforms
- **Backup/Restore:** Only available in Docker deployments (native uses manual backup)
- **Update:** Docker deployments can update with one command; native requires manual update

## Connecting to Compute and Data Sources

NeuroInsight supports multiple data sources and compute backends that can be mixed and matched:

**Data Sources:** Local files, Remote Server (SSH), HPC filesystem (SSH), Pennsieve, XNAT

**Compute Backends:** Local Docker, Remote Server (SSH + Docker), HPC/SLURM (SSH + Singularity)

See the [User Guide](docs/USER_GUIDE.md#compute-and-data-sources) for detailed connection instructions for each source and backend, including SSH tunneling for firewalled environments.

## Further Documentation

- [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/master/docs/USER_GUIDE.md) - Complete setup, connection, and usage instructions
- [Troubleshooting](docs/TROUBLESHOUTING.md) - Common issues
- [FreeSurfer License Setup](https://surfer.nmr.mgh.harvard.edu/registration.html) - Get your license

## License

MIT License. FreeSurfer requires separate license for research use.

© 2025 University of Rochester. All rights reserved.
