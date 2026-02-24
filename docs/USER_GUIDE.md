# NeuroInsight Research -- User Guide

Complete guide for deploying and using the NeuroInsight Research platform for neuroimaging analysis.

## Prerequisites

- Docker and Docker Compose (for local or containerized deployment)
- Python 3.10+ (for development setup)
- Node.js 18+ (for frontend development)
- 16GB+ RAM (32GB recommended for processing)
- SSH key-based authentication (for remote/HPC connections)

## Docker Installation

Docker is required for local processing and for containerized deployment. Choose the method for your platform.

### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

sudo systemctl start docker
sudo systemctl enable docker

sudo usermod -aG docker $USER
```

Log out and back in after the `usermod` command, then verify:

```bash
docker --version
docker compose version
docker run hello-world
```

### Windows (WSL2)

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
2. In Docker Desktop Settings, go to **Resources > WSL Integration** and enable your Ubuntu distribution
3. Open an Ubuntu terminal and verify `docker ps` works

If Docker Desktop is not installed yet, also enable WSL2:

```powershell
wsl --install -d Ubuntu
```

---

## Deployment

### Using Docker Compose (recommended)

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research/neuroinsight_research

cp .env.example .env
# Edit .env to set passwords (POSTGRES_PASSWORD, SECRET_KEY, etc.)

docker compose up -d
```

Access the UI at `http://localhost:3001` (or the port configured in `.env`).

### Development Setup

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research/neuroinsight_research

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn main:app --port 3001

# Frontend (separate terminal)
cd neuroinsight_research/neuroinsight_research/frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:3000` and proxies API requests to the backend.

### Configuration

Key environment variables (set in `.env` or passed to Docker):

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback for dev |
| `SECRET_KEY` | Session signing key (change in production) | Dev placeholder |
| `API_HOST` / `API_PORT` | Backend listen address | `0.0.0.0` / `3003` |
| `VITE_API_URL` | Frontend API target (for production builds) | `http://localhost:3000` |

See `.env.example` for the full list of options including HPC, storage, and Redis settings.

---

## Terminology

If you are new to research computing, here are the key terms used in this guide.

| Term | What it means |
|------|---------------|
| **SSH** | Secure Shell -- a way to securely log in to another computer over the network, like a remote desktop but text-based. |
| **SSH key** | A digital credential file stored on your computer that proves your identity to a remote server, replacing the need to type a password each time. You generate a key pair: a private key (stays on your machine, never shared) and a public key (copied to the server). |
| **Hostname** | The network name of a computer, similar to a website address. Example: `hpc-login.bu.edu`. |
| **Port** | A numbered channel on a computer for network communication. SSH uses port 22 by default. Think of the hostname as a building address and the port as a specific room number inside. |
| **VPN** | Virtual Private Network -- software that makes your computer appear to be on a university or company network even when you are off-site. Required to reach servers that are not exposed to the public internet. |
| **Firewall** | A security barrier that blocks unauthorized network connections. University HPCs and XNAT servers are often behind firewalls, meaning outside computers cannot reach them directly. |
| **SSH tunnel** | A technique that forwards network traffic through an SSH connection to bypass firewalls. It creates a secure "pipe" from one machine to another, allowing you to reach a server you cannot access directly. |
| **Docker** | Software that packages applications into self-contained units called containers. NeuroInsight uses Docker to run neuroimaging tools without requiring you to install them manually. |
| **HPC** | High-Performance Computing cluster -- a shared set of powerful computers managed by a university or institution. Researchers submit processing jobs to the cluster and the scheduler distributes the work. |
| **SLURM** | The job scheduler used on most HPC clusters. When you submit a job, SLURM places it in a queue and runs it when resources (CPU, memory, GPU) become available. |
| **Partition** | A group of compute nodes on an HPC cluster designated for certain types of work (e.g., `general`, `gpu`, `short`). You select a partition when submitting a job. |
| **Login node** | The computer you SSH into when connecting to an HPC cluster. It is used for submitting jobs and transferring files, not for heavy computation. |
| **Singularity / Apptainer** | Container software designed for HPC environments. It serves the same purpose as Docker but is allowed on shared clusters where Docker is not (for security reasons). Apptainer is the newer name for Singularity. |
| **API key** | A credential (like a username and password combined into one token) used to authenticate with a web service programmatically. Pennsieve uses API keys for access. |
| **SSL certificate** | A digital certificate that verifies a website's identity and enables encrypted (HTTPS) connections. When you connect through an SSH tunnel, the certificate check may fail because the certificate was issued for the real hostname, not `localhost`. |

---

## Compute and Data Sources

NeuroInsight separates **where your data lives** from **where processing runs**. You can mix and match any data source with any compute backend to suit your environment.

### Data Sources

| Source | Description | Authentication |
|--------|-------------|----------------|
| **Local** | Files on the machine running NeuroInsight | None (filesystem access) |
| **Remote Server** | Files on any SSH-accessible Linux machine | SSH key (same credentials as compute) |
| **HPC** | Files on an HPC cluster filesystem | SSH key (same credentials as compute) |
| **Pennsieve** | Browse and download from the Pennsieve platform | API key + secret |
| **XNAT** | Browse and download from any XNAT instance | XNAT username + password |

### Compute Backends

| Backend | Description | Requirements |
|---------|-------------|--------------|
| **Local Docker** | Process on the NeuroInsight server using Docker containers | Docker installed |
| **Remote Server** | Process on a remote Linux machine via SSH + Docker | SSH access, Docker on remote |
| **HPC/SLURM** | Submit jobs to an HPC cluster via SLURM | SSH access, SLURM, Singularity/Apptainer |

### How They Work Together

You select both a **data source** (top row) and a **compute backend** (bottom row) on the main processing page. A description line below explains the current combination. Examples:

- **Local + Local Docker**: Everything runs on this machine -- simplest setup
- **Local + HPC/SLURM**: Browse files locally, submit processing to an HPC cluster
- **HPC + HPC/SLURM**: Browse and process data entirely on the HPC cluster
- **Pennsieve + HPC/SLURM**: Download data from Pennsieve, process on HPC
- **XNAT + Local Docker**: Download data from XNAT, process locally with Docker

When **Remote Server** or **HPC** is selected as a data source or compute backend, an SSH configuration panel appears for entering the host, username, and port. A single SSH connection is shared when both data and compute point to the same remote machine.

When **Pennsieve** or **XNAT** is selected as a data source, a platform login form replaces the SSH panel. After connecting, you can browse and select files through the platform's data hierarchy, then process them on any compute backend.

---

## Connecting to a Remote Server

NeuroInsight can run neuroimaging jobs on any SSH-accessible Linux machine with Docker installed. This is useful for offloading processing to a more powerful server, a cloud VM (AWS, GCP, Azure), or a lab workstation.

### Example Scenario

Dr. Reyes runs NeuroInsight on her laptop (8 GB RAM), but FreeSurfer and fMRIPrep need far more memory. Her lab has a shared Linux workstation (`brainlab-ws01.med.stanford.edu`) with 128 GB RAM, 32 CPU cores, and Docker installed. She wants to keep browsing and uploading files from her laptop while the heavy processing happens on the lab workstation.

**What she enters in the UI:**

| Field | Value |
|-------|-------|
| Data Source | **Local** (files are on her laptop) |
| Compute Source | **Remote Server** |
| Host | `brainlab-ws01.med.stanford.edu` |
| Username | `sreyes` |
| Port | `22` |

After clicking **Connect & Activate**, she uploads a T1 NIfTI file from her laptop. NeuroInsight transfers it to the workstation, runs FreeSurfer inside a Docker container there, and streams the results back.

If she were working from home and the workstation were behind the university firewall, she would first connect her VPN, then enter the same hostname. Alternatively, she could set up a reverse SSH tunnel as described in the HPC section below and use `localhost` / port `2222` instead.

### Prerequisites

1. **A Linux server** with Docker installed and running
2. **SSH access** from the NeuroInsight server to the remote machine (key-based authentication)
3. **Docker permissions** for your SSH user on the remote machine (user must be in the `docker` group)

### Step 1: Set Up SSH Key Authentication

Follow the same SSH key setup as for HPC connections (see "Connecting to HPC" below, Step 1). The NeuroInsight server needs passwordless SSH access to the remote machine.

### Step 2: Connect in the NeuroInsight UI

1. Open NeuroInsight in your browser
2. Under **Data Source**, select **Local** (or **Remote Server** if your data is on the remote machine)
3. Under **Compute Source**, select **Remote Server**
4. Fill in the SSH connection fields:
   - **Host** -- hostname or IP of the remote machine (or `localhost` if using a reverse tunnel)
   - **Username** -- your SSH username on the remote machine
   - **Port** -- `22` (default) or `2222` if using a reverse tunnel
5. Click **Connect & Activate**
6. A green "Connected" badge confirms the connection

### Step 3: Verify Docker Access

After connecting, NeuroInsight verifies that Docker is available on the remote machine. If Docker is not found or the user lacks permissions, an error message will explain the issue.

### Network Access (Remote Server Behind a Firewall)

If the remote server is on a private network (e.g., behind a university firewall), use a reverse SSH tunnel, following the same pattern described in "Connecting to HPC" Step 2 below. Replace the HPC login node with the remote server's hostname.

### How Remote Server Differs from HPC

| Feature | Remote Server | HPC/SLURM |
|---------|---------------|-----------|
| Container runtime | Docker | Singularity/Apptainer |
| Job scheduling | Immediate (docker run) | Queued (sbatch) |
| Multi-node | No (single machine) | Yes (SLURM partitions) |
| Shared filesystem | No | Yes (NFS/Lustre) |
| Best for | Single-server setups, cloud VMs | Multi-user clusters with job queuing |

---

## Connecting to Pennsieve

NeuroInsight can browse, download, and process data stored on the [Pennsieve](https://app.pennsieve.io) data management platform. Pennsieve is a cloud-based research data management system used by NIH SPARC, RE-JOIN, and other programs to store, organize, and share biomedical datasets.

### Example Scenario

Dr. Okonkwo's epilepsy lab at the University of Pennsylvania stores all their MRI datasets on Pennsieve under the organization "Penn Epilepsy Center". A research assistant, James, needs to run the hippocampal sclerosis detection pipeline on 12 subjects from the dataset "Temporal Lobe Epilepsy Cohort 2025".

James does not have the MRI files on his local machine -- they are only on Pennsieve. He also wants to process them on the lab's HPC cluster.

**Step 1 -- Generate API credentials:** James logs into `app.pennsieve.io`, goes to his profile, and creates an API key named "NeuroInsight". He copies the key (`a3f8e1d2-...`) and the secret.

**Step 2 -- Connect in NeuroInsight:**

| Field | Value |
|-------|-------|
| Data Source | **Pennsieve** |
| Compute Source | **HPC/SLURM** |
| API Key | `a3f8e1d2-7b4c-49e1-8f6a-2d9c0e5b1a73` |
| API Secret | (pasted from clipboard) |

**Step 3 -- Browse and select data:** After connecting, he clicks Browse, selects "Temporal Lobe Epilepsy Cohort 2025", navigates into the subject folders, and selects the T1-weighted NIfTI files for his 12 subjects.

**Step 4 -- Process:** NeuroInsight downloads the selected files from Pennsieve and submits them to the HPC cluster for processing via SLURM. James monitors progress in the SLURM Queue Monitor panel.

### Prerequisites

1. **A Pennsieve account** with access to at least one dataset
2. **An API key and secret** generated from your Pennsieve account

### Step 1: Generate API Credentials

1. Log in to Pennsieve at [https://app.pennsieve.io](https://app.pennsieve.io)
2. Click your profile icon (top-right) and select **View My Profile**
3. Scroll down to the **API Keys** section
4. Click **Create API Key**
5. Enter a name (e.g., "NeuroInsight") and click **Create**
6. **Copy both the API Key and the API Secret** -- the secret is only shown once

If you lose the secret, delete the key and create a new one.

### Step 2: Connect in the NeuroInsight UI

1. Open NeuroInsight and click **Get Started**
2. Under **Data Source**, click the **Pennsieve** tab (blue database icon)
3. Enter your credentials:
   - **API Key** -- the key from Step 1 (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - **API Secret** -- the secret from Step 1
4. Click **Connect**
5. A green "Connected" badge confirms the connection, showing your email and workspace

### Step 3: Browse Data

After connecting, click **Browse** in the input section to open the Pennsieve Data Browser. The Pennsieve hierarchy is:

```
Workspace (Organization)
 └── Dataset
      └── Package (folder or file collection)
           └── Files
```

1. **Datasets** -- listed automatically after connecting; select the dataset containing your data
2. **Packages** -- navigate through folder structure within the dataset
3. **Files** -- select the files you want to process, then click **Select for Processing**

### Step 4: Process Data

After selecting files from Pennsieve, the files are downloaded to the NeuroInsight server and submitted to your chosen compute backend (Local Docker, Remote Server, or HPC/SLURM) for processing.

### Troubleshooting Pennsieve Connection

| Problem | Solution |
|---------|----------|
| **"API Key and Secret are required"** | Both fields must be filled in |
| **"Authentication failed"** | API key or secret is incorrect -- generate a new pair from Pennsieve |
| **"Connection timed out"** | Network issue reaching Pennsieve API (`api.pennsieve.io`) -- check firewall/proxy |
| **Empty dataset list** | Your account may not have access to any datasets -- verify in the Pennsieve web UI |
| **"Token expired"** | Session expired after long idle time -- click Disconnect and reconnect |

### Important Notes

- **API key security**: API keys provide full access to your Pennsieve account. Do not share them or commit them to version control.
- **Data download**: Files are downloaded to the NeuroInsight server before processing. Ensure sufficient disk space for your datasets.
- **Large files**: Download speed depends on network bandwidth between the NeuroInsight server and Pennsieve's cloud storage.
- **Pennsieve organizations**: If you belong to multiple organizations, NeuroInsight connects to your primary (default) organization.

---

## Connecting to HPC (SLURM Cluster)

NeuroInsight can submit neuroimaging jobs to a remote HPC cluster via SSH and SLURM, running containerized tools (Singularity/Apptainer) on cluster nodes instead of locally.

### Example Scenario

Priya is a PhD student in neuroscience at Boston University. She has 50 subjects to process through the full diffusion pipeline (QSIPrep + QSIRecon), which takes about 8 hours per subject. Running all 50 sequentially on her laptop would take over 16 days. The university's Shared Computing Cluster (SCC) has hundreds of nodes and can run multiple subjects in parallel.

NeuroInsight is deployed on an AWS EC2 instance so Priya can access it from anywhere. The SCC is behind BU's campus firewall, so Priya uses a reverse SSH tunnel from her laptop (connected to BU's VPN) to bridge the two.

**Setting up the tunnel (on her laptop, VPN connected):**

```bash
ssh -i ~/keys/aws-neuroinsight.pem \
    -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -R 2222:scc-login.bu.edu:22 \
    ubuntu@54.89.123.45
```

This single command does three things: forwards the NeuroInsight UI (port 3000) and API (port 8000) to her browser, and creates a reverse tunnel so the AWS server can reach the SCC through her VPN.

**What she enters in the NeuroInsight UI:**

| Field | Value |
|-------|-------|
| Data Source | **HPC** (her BIDS data is on `/projectnb/epilepsy/priya/`) |
| Compute Source | **HPC/SLURM** |
| Host | `localhost` (because of the reverse tunnel) |
| Username | `priya` |
| Port | `2222` (the tunnel port) |
| Work Directory | `/scratch/priya/neuroinsight` |
| Partition | `general` (auto-populated after connecting) |
| Modules | `singularity/3.10` |

After connecting, she browses her BIDS directory on the SCC through the file browser, selects all 50 subjects, chooses "Diffusion Full Pipeline", and clicks Submit. SLURM queues the jobs and processes multiple subjects in parallel across cluster nodes. She monitors everything from the SLURM Queue Monitor panel in her browser.

If Priya were on campus (connected to BU's network directly), she would skip the tunnel and enter the real hostname (`scc-login.bu.edu`, port `22`) instead of `localhost:2222`.

### Prerequisites

Before connecting, ensure you have:

1. **An HPC account** with SSH access to a login node
2. **SLURM** scheduler running on the cluster
3. **Singularity or Apptainer** installed on the cluster (for containerized tools)
4. **SSH key-based authentication** configured (see Step 1 below)

### Step 1: Set Up SSH Key Authentication

The NeuroInsight server needs passwordless SSH access to your HPC login node. You must copy the server's public key to your HPC account.

#### 1a. Get the server's public key

On the NeuroInsight server, display the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the output (starts with `ssh-ed25519 ...`).

If no key exists, generate one:

```bash
ssh-keygen -t ed25519 -C "neuroinsight" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

#### 1b. Add the key to your HPC account

From a machine that can reach the HPC (your laptop, or the HPC terminal itself), add the key:

```bash
ssh <your-username>@<hpc-login-node> "mkdir -p ~/.ssh && echo '<paste-public-key-here>' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Or log into the HPC directly and append the key manually to `~/.ssh/authorized_keys`.

#### 1c. Verify it works

From the NeuroInsight server:

```bash
ssh -o BatchMode=yes <your-username>@<hpc-login-node> hostname
```

If this prints the HPC hostname without asking for a password, you're ready.

### Step 2: Network Access (If HPC Is Behind a Firewall)

If NeuroInsight runs on an external server (e.g., AWS) and the HPC is on a private university network, the server cannot reach the HPC directly. You need a **reverse SSH tunnel** from a machine that has VPN/network access.

#### Architecture

```
NeuroInsight Server (AWS)                    Your Laptop (VPN)                   HPC Login Node
      localhost:2222  ---- reverse tunnel ---->  laptop ---- VPN ---->  hpc-login.university.edu:22
```

#### Set up the reverse tunnel

On your **local machine** (with VPN connected), run:

```bash
ssh -i /path/to/server-key.pem \
    -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -R 2222:<hpc-login-node>:22 \
    ubuntu@<neuroinsight-server-ip>
```

| Flag | Purpose |
|------|---------|
| `-L 3000:localhost:3000` | Forward the UI to your browser |
| `-L 8000:localhost:8000` | Forward the API to your browser |
| `-R 2222:<hpc-login-node>:22` | Reverse tunnel: server port 2222 reaches HPC via your VPN |

Keep this terminal open while using NeuroInsight.

**When using the reverse tunnel**, enter these values in the UI:
- **Host**: `localhost`
- **Port**: `2222`
- **Username**: your HPC username

**If NeuroInsight can reach the HPC directly** (same network, or VPN on the server), use the actual hostname:
- **Host**: `hpc-login.university.edu`
- **Port**: `22`
- **Username**: your HPC username

### Step 3: Connect in the NeuroInsight UI

1. Open NeuroInsight in your browser
2. In the top toolbar, click the **HPC** tab (purple server icon)
3. Fill in the SSH connection fields:
   - **Host** -- HPC login node hostname (or `localhost` if using a reverse tunnel)
   - **Username** -- your HPC username
   - **Port** -- `22` (or `2222` if using a reverse tunnel)
4. Click **Connect**
5. A green "Connected" badge appears on success

### Step 4: Configure SLURM Settings

After connecting:

1. Set the **Work Directory** -- the path on the HPC where jobs will run (e.g., `/scratch/<username>` or `/home/<username>/neuroinsight`)
2. Click **Show SLURM Settings** to expand advanced options:
   - **Partition** -- dropdown auto-populated from the cluster's `sinfo` output
   - **Account** -- your SLURM allocation/account name (if required by your cluster)
   - **QoS** -- quality of service tier (optional)
   - **Modules** -- comma-separated list of modules to load before each job (e.g., `singularity/3.8, cuda/11.8`)
3. Click **Activate SLURM Backend**

All subsequent neuroimaging jobs will be submitted to the cluster via `sbatch`.

### Step 5: Monitor Jobs

Once connected, the **SLURM Queue Monitor** panel appears automatically, showing:
- Your SLURM jobs with status (RUNNING, PENDING, COMPLETED, FAILED)
- Auto-refreshes every 10 seconds
- Color-coded status indicators

You can also browse remote files on the HPC using the **File Browser** panel in HPC mode.

### Switching Back to Local

To return to local Docker execution:
- Click the **Local** tab in the backend selector, or
- Click **Disconnect** in the HPC panel

### Troubleshooting HPC Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | HPC is unreachable -- check VPN/firewall, verify hostname, set up reverse tunnel |
| **"Authentication failed"** | SSH key not on HPC -- follow Step 1b to add the public key |
| **"Connection refused"** | Wrong port, or the hostname is a web portal (OOD) not an SSH server -- use the actual login node |
| **"No SLURM partitions found"** | SLURM not available on this node -- verify `sinfo` works when you SSH in manually |
| **Reverse tunnel not working** | Ensure your VPN is active and the SSH session with `-R` flag is still open |

### Important Notes

- **Open OnDemand (OOD)**: OOD servers are web portals and typically do not accept SSH connections. Use the underlying HPC login node hostname instead. You can find it by opening a terminal session within the OOD web interface.
- **SSH Agent Forwarding**: Not required -- NeuroInsight uses key-based auth directly from the server.
- **Multiple Users**: Each user needs their own SSH key added to their HPC account.

---

## Connecting to XNAT

NeuroInsight can browse, download, and process data directly from any XNAT instance (CIDUR, CNDA, NITRC, Central, or your own). XNAT is an open-source imaging informatics platform used by hospitals and research centers to archive and share neuroimaging data.

### Example Scenario

Dr. Nakamura is a neuroradiologist at the University of Rochester Medical Center. The imaging center stores all research MRI data on an internal XNAT server at `https://xnat.urmc.rochester.edu`. She wants to run the cortical lesion detection pipeline on five subjects from the "Focal Epilepsy MRI Study" project.

NeuroInsight is running on an AWS EC2 instance, and the XNAT server is on the hospital's internal network (not accessible from the internet). Dr. Nakamura is already connected to the university HPC via NeuroInsight. She uses the HPC login node as a bridge to reach XNAT.

**Setting up the tunnel (on the NeuroInsight server):**

```bash
ssh -L 8443:xnat.urmc.rochester.edu:443 dnakamura@smdodlogin01.urmc.rochester.edu -N
```

This forwards port 8443 on the NeuroInsight server through the HPC login node to the XNAT server. The HPC login node can reach XNAT because both are on the hospital network.

**What she enters in the NeuroInsight UI:**

| Field | Value |
|-------|-------|
| Data Source | **XNAT** |
| Compute Source | **HPC/SLURM** (already connected) |
| XNAT URL | `https://localhost:8443` |
| Skip SSL verification | **checked** (required because the certificate is for `xnat.urmc.rochester.edu`, not `localhost`) |
| Username | `dnakamura` |
| Password | (her XNAT password) |

**Browsing data:** After connecting, she clicks Browse and sees the project list. She selects "Focal Epilepsy MRI Study", clicks into the first subject, opens their MR Session, selects Scan 1 (T1 MPRAGE), opens the NIFTI resource, and selects the `.nii.gz` file. She repeats for all five subjects.

**Processing:** She selects "Cortical Lesion Detection" as the pipeline and clicks Submit. NeuroInsight downloads the five NIfTI files from XNAT (via the tunnel), then submits them to the HPC for processing via SLURM.

If the XNAT server were publicly accessible (e.g., `https://central.xnat.org`), no tunnel would be needed. She would enter the real URL directly and leave SSL verification enabled.

### Prerequisites

1. **An XNAT account** with read access to at least one project
2. **Network access** from the NeuroInsight server to the XNAT instance (see "XNAT Behind a Firewall" below)

### Step 1: Connect to XNAT

1. Open NeuroInsight and click **Get Started**
2. Under **Data Source**, click the **XNAT** tab
3. Fill in:
   - **XNAT URL** -- the full URL of the XNAT instance (e.g., `https://xnat.example.edu`)
   - **Username** -- your XNAT username
   - **Password** -- your XNAT password
4. Click **Connect**
5. A green "Connected" badge confirms the connection

### Step 2: Browse Data

After connecting, click **Browse** in the input section to open the XNAT Data Browser. The XNAT hierarchy is:

```
Project
 └── Subject
      └── Experiment (session)
           └── Scan
                └── Resource (NIFTI, DICOM, etc.)
                     └── Files
```

1. **Projects** -- select the project containing your data
2. **Subjects** -- click a subject to view their sessions
3. **Experiments** -- click a session to view scans
4. **Scans** -- click a scan to view available resources (NIFTI, DICOM, etc.)
5. **Resources** -- click a resource to see individual files
6. **Files** -- select the files you want to process, then click **Select for Processing**

Use the breadcrumb navigation at the top to go back to any level.

### Step 3: Process Data

After selecting files from XNAT, the files are downloaded to the NeuroInsight server and submitted to your chosen compute backend (Local Docker, Remote Server, or HPC/SLURM) for processing.

### XNAT Behind a Firewall (SSH Tunnel)

If NeuroInsight runs on an external server (e.g., AWS EC2) and the XNAT instance is on a private institutional network, the server cannot reach XNAT directly. Use an **SSH local port forward** through an intermediary that can reach both networks.

#### Architecture

```
NeuroInsight Server (AWS)                    Intermediary (HPC/VPN)                   XNAT Instance
      localhost:8443  ---- SSH tunnel ---->  hpc-login  ---- network ---->  xnat.university.edu:443
```

The intermediary can be any machine that:
- Is reachable from the NeuroInsight server via SSH
- Can reach the XNAT instance over the network (e.g., on the same campus network or VPN)

An HPC login node you are already connected to is a common choice.

#### Set up the tunnel

On the **NeuroInsight server**, run:

```bash
ssh -L 8443:<xnat-hostname>:443 <username>@<intermediary-host> -N
```

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `8443` | `8443` | Local port on the NeuroInsight server that will proxy to XNAT |
| `<xnat-hostname>` | `xnat.university.edu` | The XNAT hostname as reachable from the intermediary |
| `443` | `443` | XNAT's HTTPS port (use `80` for HTTP, or `8080` if non-standard) |
| `<intermediary-host>` | `hpc-login.university.edu` | The SSH-accessible intermediary machine |
| `-N` | | Don't open a shell, just forward ports |

Keep this terminal open while using XNAT.

**Example** (tunneling through an HPC login node):

```bash
ssh -L 8443:xnat.your-institution.edu:443 youruser@hpc-login.your-institution.edu -N
```

#### Connect in the UI

When using the tunnel, enter:
- **XNAT URL**: `https://localhost:8443`
- **Skip SSL verification**: **checked** (required -- see below)
- **Username / Password**: your XNAT credentials

### SSL Certificate Verification

When connecting through an SSH tunnel, the browser/server connects to `localhost:8443` but the XNAT server's SSL certificate was issued for its real hostname (e.g., `xnat.university.edu`). This hostname mismatch causes SSL verification to fail with an error like:

```
SSL certificate verification failed for https://localhost:8443
```

**Solution**: Check the **"Skip SSL verification"** checkbox in the XNAT Login form before clicking Connect. This is safe when using an SSH tunnel because the tunnel itself provides encrypted transport to the intermediary.

When connecting directly to an XNAT instance (no tunnel), leave SSL verification **enabled** unless the XNAT instance uses a self-signed certificate.

### XNAT on the Transfer Page

The XNAT connection is also available on the **Transfer** page for downloading/uploading data without processing. Click the **XNAT** tab in either the source or destination pane, enter credentials, and browse the same Project > Subject > Experiment > Scan hierarchy.

### Troubleshooting XNAT Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | XNAT is unreachable -- check network/VPN, set up an SSH tunnel if on a different network |
| **"SSL certificate verification failed"** | Check **"Skip SSL verification"** if using an SSH tunnel or self-signed certificate |
| **"Authentication failed (401)"** | Wrong username or password |
| **"Access denied (403)"** | Account lacks permission for this XNAT instance -- contact your XNAT admin |
| **"XNAT REST API not found (404)"** | Incorrect URL -- verify the URL points to the XNAT web root (not a sub-path) |
| **Empty project list** | Your account may not have read access to any projects -- verify in the XNAT web UI |
| **Tunnel connection refused** | SSH tunnel may have closed -- check and restart the `ssh -L` command |

### Important Notes

- **Session timeout**: XNAT sessions expire after inactivity (typically 15-30 minutes). If you get errors after being idle, click **Disconnect** and reconnect.
- **Large downloads**: When downloading many files or large datasets, ensure sufficient disk space on the NeuroInsight server.
- **XNAT versions**: NeuroInsight uses the standard XNAT REST API and works with XNAT 1.7+ instances.
- **No uploads during processing**: File uploads to XNAT require the experiment and resource to already exist. Use the XNAT web interface to create them first.

---

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions

---

MIT License. Individual neuroimaging tools (FreeSurfer, fMRIPrep, etc.) have their own licenses.
