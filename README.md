# NeuroInsight Research

An open-source platform for running neuroimaging tools from a web interface. Select your data, pick a plugin or workflow, choose where to process, and click Submit -- no terminal commands or container expertise required.

A **plugin** wraps a single neuroimaging tool (e.g., FreeSurfer, fMRIPrep) so it can run in a container with one click. A **workflow** chains multiple plugins into a single job with automatic data passing between steps (e.g., fMRIPrep then XCP-D). Both are defined as YAML files -- drop a new one in `plugins/` or `workflows/` to extend the platform.

## Requirements

Install these before running `./research install` (the installer handles all Python/Node packages automatically):

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.9+ | If missing, the installer detects your OS and offers to install it for you. |
| Node.js | 18+ | If missing, the installer offers to install it via nvm (no sudo needed). |
| Docker | Compose v2 | Runs infrastructure (PostgreSQL, Redis, MinIO) and all neuroimaging containers. |
| OS | Linux, macOS, or Windows (WSL2) | **Linux or WSL2 recommended.** macOS works but local processing is slower due to Docker's VM layer and Rosetta emulation on Apple Silicon. See [macOS Notes](docs/USER_GUIDE.md#macos-notes). Windows users need WSL2 with Docker Desktop. |
| License files | -- | FreeSurfer `license.txt` and/or MELD `meld_license.txt` depending on which plugins you use. Run `./research license` to set up. |

**RAM and storage:**

| | App only (orchestration + remote/HPC jobs) | Local processing (Docker) |
|---|---|---|
| RAM | 4 GB | 16 GB+ (FreeSurfer, fMRIPrep); 8 GB for lighter plugins |
| Storage | 2 GB (app + dependencies) | 10-50 GB per plugin image + space for input/output data |

If you only submit jobs to a remote server or HPC, the app itself is lightweight. Local processing requires more resources because the neuroimaging containers run on your machine.

## Quick Start

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research install        # install deps, start infra, init DB
./research license        # set up FreeSurfer / MELD license files
./research start          # launch the app
./research stop           # stop app services only (keep infra running)
./research stop infra     # stop app + infra containers (keep data volumes)
./research stop --all     # stop everything and remove infra data volumes
```

Open **http://localhost:3000** -- that's it.

`./research install` creates a Python venv, installs Node/Python dependencies, generates secure passwords, and starts PostgreSQL/Redis/MinIO via Docker. `./research license` walks you through placing the required license files interactively. `./research start` builds the frontend and launches the backend.

## How to Use

1. Open **http://localhost:3000** and go to the **Jobs** tab
2. **Select a data source** -- browse local files, remote server, HPC filesystem, Pennsieve, or XNAT
3. **Pick a plugin or workflow** -- a **plugin** runs a single tool (e.g., FreeSurfer, fMRIPrep); a **workflow** chains multiple plugins into one job (e.g., fMRIPrep then XCP-D, or QSIPrep then QSIRecon)
4. **Choose where to process** -- Local (Docker), Remote Server (SSH), or HPC (SLURM)
5. **Configure resources** -- CPU, RAM, GPU, and time limit
6. **Submit** -- the job runs in a container; monitor progress on the **Dashboard**
7. **View results** -- open outputs in the built-in **NIfTI Viewer** with segmentation overlays

## Plugin Licenses

Some plugins require a free license file before you can submit jobs. Run the interactive setup:

```bash
./research license
```

This checks for `license.txt` (FreeSurfer) and `meld_license.txt` (MELD Graph), and guides you through obtaining and placing them.

| License | Required By | Registration |
|---|---|---|
| `license.txt` | FreeSurfer, FastSurfer, fMRIPrep, MELD Graph | https://surfer.nmr.mgh.harvard.edu/registration.html |
| `meld_license.txt` | MELD Graph (v2.2.4+) | https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform |
| No license needed | QSIPrep, QSIRecon, XCP-D, dcm2niix | -- |

Place license files in the project root directory. The app also checks `~/.freesurfer/license.txt` and `~/.meld/meld_license.txt`.

## Plugins and Workflows

### Plugins

| Plugin | Description |
|--------|-------------|
| FreeSurfer recon-all | Cortical reconstruction and volumetric segmentation |
| FastSurfer | GPU-accelerated cortical segmentation |
| fMRIPrep | Functional MRI preprocessing |
| QSIPrep | Diffusion MRI preprocessing |
| QSIRecon | Diffusion MRI reconstruction and connectivity |
| XCP-D | Functional connectivity postprocessing |
| MELD Graph | Cortical lesion detection |
| Hippocampal Sclerosis Detection | Automated HS detection with postprocessing |
| FreeSurfer Longitudinal | Multi-timepoint longitudinal analysis |

### Workflows

| Workflow | Steps |
|----------|-------|
| fMRI Full Pipeline | fMRIPrep then XCP-D |
| Diffusion Full Pipeline | QSIPrep then QSIRecon |
| FreeSurfer Longitudinal Full | FreeSurfer Longitudinal then Stats |
| HS Detection | SegmentHA then HS Postprocessing |
| Cortical Lesion Detection | FreeSurfer then MELD Graph |

## Connecting to Pennsieve and XNAT

NeuroInsight can browse and pull data directly from **Pennsieve** and **XNAT** repositories.

**Pennsieve:**

1. Get an API key from your Pennsieve account (User menu > API Tokens)
2. In the app, go to **Jobs** > **Data Source** > **Pennsieve**
3. Enter your API key and secret, click **Connect**
4. Browse datasets and select files to process

**XNAT:**

1. In the app, go to **Jobs** > **Data Source** > **XNAT**
2. Enter your XNAT server URL (e.g., `https://central.xnat.org`), username, and password
3. Click **Connect**
4. Browse projects, subjects, and sessions to select input data

Data from either platform is pulled to the compute backend before processing. You can combine any data source with any compute backend (e.g., pull from Pennsieve, process on HPC).

## Running on Remote Servers / HPC

The app runs jobs locally by default. To process on a remote machine or HPC cluster:

1. Make sure you can `ssh user@server` without a password (using SSH keys)
2. In the app, go to **Jobs** and select **Remote Server** or **HPC (SLURM)**
3. Enter your hostname and username, click **Connect**
4. For HPC, configure the partition, account, and work directory in **Advanced Settings**
5. Browse files on the remote system, pick a plugin or workflow, and submit

The app uses your local SSH agent for authentication -- your private key never leaves your machine. On HPC, jobs are submitted via `sbatch` and run in Apptainer/Singularity containers (auto-detected).

For detailed SSH key setup instructions, see the [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/USER_GUIDE.md).

## Key Features

- **Multiple data sources** -- Local files, Remote Server (SSH), HPC filesystem, Pennsieve, or XNAT
- **Multiple compute backends** -- Local Docker, Remote Server (SSH + Docker), or HPC/SLURM (SSH + Singularity)
- **Mix and match** -- Browse data on XNAT, process on HPC; pull from Pennsieve, process locally
- **Real-time monitoring** -- SLURM queue monitor, job progress tracking, and log streaming
- **Plugins** -- Each tool is a single YAML file; drop a new one in `plugins/` to add support for a new tool
- **Workflows** -- Chain multiple plugins into one job with automatic data passing between steps
- **Built-in NIfTI viewer** -- View results with segmentation overlays powered by Niivue

## Documentation

- [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/USER_GUIDE.md) -- Complete setup, connections, SSH key guide, and usage instructions
- [Troubleshooting](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/TROUBLESHOOTING.md) -- Common issues and solutions
- [Processor Image Mirror](docker/processors/README.md) -- Required tested images and mirror script for `phindagijimana321/*`
- [Pennsieve Registration Bundle](pennsieve/REGISTER.md) -- 14 processors + 7 workflows translation and registration runbook
- [Pennsieve Go/No-Go Checklist](pennsieve/PLATFORM_REGISTRATION_CHECKLIST.md) -- strict phased checks for platform registration

## Citing This Software

If you use NeuroInsight Research in your work, please cite:

```bibtex
@software{neuroinsight_research,
  author       = {Phindagijimana},
  title        = {NeuroInsight Research: Neuroimaging Processing Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  version      = {1.0.0}
}
```

Please also cite the individual tools you use (FreeSurfer, fMRIPrep, QSIPrep, etc.) as required by their respective licenses.

## Contact

For questions, comments, or contributions, reach out to **phindagijimana@gmail.com**.

## License

MIT License. Individual neuroimaging tools (FreeSurfer, fMRIPrep, etc.) have their own licenses.
