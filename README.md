# NeuroInsight Research

An open-source platform for running neuroimaging pipelines from a web interface. Select your data, pick a pipeline, choose where to process, and click Submit -- no terminal commands or container expertise required.

## Supported Pipelines

| Pipeline | Description |
|----------|-------------|
| FreeSurfer recon-all | Cortical reconstruction and volumetric segmentation |
| FastSurfer | GPU-accelerated cortical segmentation |
| fMRIPrep | Functional MRI preprocessing |
| QSIPrep | Diffusion MRI preprocessing |
| QSIRecon | Diffusion MRI reconstruction and connectivity |
| XCP-D | Functional connectivity postprocessing |
| MELD Graph | Cortical lesion detection |
| Hippocampal Sclerosis Detection | Automated HS detection with postprocessing |
| FreeSurfer Longitudinal | Multi-timepoint longitudinal analysis |

Pipelines are defined as YAML plugin files. Adding a new pipeline requires no code changes.

## Key Features

- **Multiple data sources** -- Local files, Remote Server (SSH), HPC filesystem, Pennsieve, or XNAT
- **Multiple compute backends** -- Local Docker, Remote Server (SSH + Docker), or HPC/SLURM (SSH + Singularity)
- **Mix and match** -- Browse data on XNAT, process on HPC; download from Pennsieve, process locally; or any combination
- **Real-time monitoring** -- SLURM queue monitor, job progress tracking, and log streaming
- **Plugin architecture** -- Each pipeline is a single YAML file defining container image, parameters, and resource requirements
- **Multi-step workflows** -- Chain pipelines (e.g., QSIPrep then QSIRecon) with automatic inter-step data passing
- **Portable** -- No hardcoded paths or user-specific configuration in source code

## Quick Start

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research/neuroinsight_research
./research start
```

Open **http://localhost:3001** -- that's it.

The first run automatically installs dependencies, generates secure passwords, starts infrastructure (PostgreSQL, Redis, MinIO via Docker), builds the frontend, and launches the application. No manual configuration needed.

**Prerequisites:** Python 3.9+, Node.js 18+, Docker with Compose v2

### Other launch options

```bash
./research-dev start     # Development mode (hot-reload, debug logging)
docker compose up -d     # Fully containerized deployment (edit .env first)
```

## Repository Structure

```
neuroinsight_research/
  backend/            FastAPI application, connectors, execution backends
  frontend/           React/TypeScript UI (Vite)
  plugins/            Pipeline definitions (YAML)
  adapters/pennsieve/ Pennsieve processor adapters and Dockerfiles
  .env.example        Configuration template
  requirements.txt    Python dependencies
  docker-compose.yml  Production deployment
docs/
  USER_GUIDE.md       Setup, connections, usage, and troubleshooting
  TROUBLESHOOTING.md  Common issues and solutions
```

## Connecting to Compute and Data Sources

NeuroInsight supports five data sources and three compute backends that can be combined freely. The [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/master/docs/USER_GUIDE.md#compute-and-data-sources) includes step-by-step connection instructions, SSH tunneling for firewalled environments, and real-world examples for each scenario.

## Documentation

- [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/master/docs/USER_GUIDE.md) -- Complete setup, connection, and usage instructions with real-world examples
- [Troubleshooting](https://github.com/phindagijimana/neuroinsight_research/blob/master/docs/TROUBLESHOOTING.md) -- Common issues and solutions

## Contact

For questions, comments, or contributions, reach out to **phindagijimana@gmail.com**.

## License

MIT License. Individual neuroimaging tools (FreeSurfer, fMRIPrep, etc.) have their own licenses.
