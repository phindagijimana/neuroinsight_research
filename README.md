# NeuroInsight Research

An open-source platform for running neuroimaging pipelines from a web interface. Select your data, pick a pipeline, choose where to process, and click Submit -- no terminal commands or container expertise required.

## Quick Start

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research start
```

Open **http://localhost:3000** -- that's it.

The first run automatically installs dependencies, generates secure passwords, starts PostgreSQL/Redis/MinIO via Docker, builds the frontend, and launches everything. No manual configuration required.

**Prerequisites:** Python 3.9+, Node.js 18+, Docker with Compose v2

## How to Use

1. Open **http://localhost:3000** and go to the **Jobs** tab
2. **Select a data source** -- browse local files, remote server, HPC filesystem, Pennsieve, or XNAT
3. **Pick a plugin or workflow** -- a **plugin** runs a single tool (e.g., FreeSurfer, fMRIPrep); a **workflow** chains multiple plugins into one job (e.g., fMRIPrep then XCP-D, or QSIPrep then QSIRecon)
4. **Choose where to process** -- Local (Docker), Remote Server (SSH), or HPC (SLURM)
5. **Configure resources** -- CPU, RAM, GPU, and time limit
6. **Submit** -- the job runs in a container; monitor progress on the **Dashboard**
7. **View results** -- open outputs in the built-in **NIfTI Viewer** with segmentation overlays

## Pipeline Licenses

Some pipelines require a free license file **before** you can submit your first job. If your pipeline doesn't need one, skip this section.

### FreeSurfer License (required by FreeSurfer, FastSurfer, fMRIPrep, MELD Graph)

1. Register at **https://surfer.nmr.mgh.harvard.edu/registration.html**
2. A `license.txt` file will be emailed to you
3. Place it in the project root:

```bash
cp ~/Downloads/license.txt ./license.txt
```

The app auto-detects the license in `./license.txt`, `./data/license.txt`, `$FREESURFER_HOME/license.txt`, or `~/.freesurfer/license.txt`. You can also set `FS_LICENSE_PATH` in `.env`.

### MELD Graph License (required by MELD Graph v2.2.4+)

1. Fill the form: **https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform**
2. Place the received `meld_license.txt` in the project root

### Which pipelines need licenses?

| License | Required By |
|---|---|
| FreeSurfer `license.txt` | FreeSurfer, FastSurfer, fMRIPrep, MELD Graph |
| MELD `meld_license.txt` | MELD Graph (v2.2.4+) |
| No license needed | QSIPrep, QSIRecon, XCP-D, dcm2niix |

## Plugins and Workflows

**Plugins** are single-tool processing steps. **Workflows** chain multiple plugins into one job with automatic data passing between steps. Both are defined as YAML files -- no code changes needed to add new ones.

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
5. Browse files on the remote system, pick a pipeline, and submit

The app uses your local SSH agent for authentication -- your private key never leaves your machine. On HPC, jobs are submitted via `sbatch` and run in Apptainer/Singularity containers (auto-detected).

For detailed SSH key setup instructions, see the [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/USER_GUIDE.md).

## Key Features

- **Multiple data sources** -- Local files, Remote Server (SSH), HPC filesystem, Pennsieve, or XNAT
- **Multiple compute backends** -- Local Docker, Remote Server (SSH + Docker), or HPC/SLURM (SSH + Singularity)
- **Mix and match** -- Browse data on XNAT, process on HPC; pull from Pennsieve, process locally
- **Real-time monitoring** -- SLURM queue monitor, job progress tracking, and log streaming
- **Plugins** -- Each tool is a single YAML file; drop a new one in `plugins/` to add a pipeline
- **Workflows** -- Chain multiple plugins into one job with automatic data passing between steps
- **Built-in NIfTI viewer** -- View results with segmentation overlays powered by Niivue

## Documentation

- [User Guide](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/USER_GUIDE.md) -- Complete setup, connections, SSH key guide, and usage instructions
- [Troubleshooting](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/TROUBLESHOOTING.md) -- Common issues and solutions

## Citing This Software

If you use NeuroInsight Research in your work, please cite:

```bibtex
@software{neuroinsight_research,
  author       = {Phindagijimana},
  title        = {NeuroInsight Research: Neuroimaging Pipeline Platform},
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
