# Installing NeuroInsight (Desktop)

NeuroInsight is a desktop app for macOS, Windows, and Linux. It runs its
processing engine locally in a container, so **your data never leaves your
machine**.

## System requirements

| | Minimum |
|---|---|
| **OS** | macOS 12+, Windows 10/11 (64-bit), or Linux (x86-64 / arm64) |
| **Docker** | **Docker Desktop** (macOS/Windows) or Docker Engine (Linux) — required |
| **Disk** | ~20 GB free (the engine image is ~1.8 GB; pipelines pull more) |
| **RAM** | 8 GB minimum, 16 GB recommended |
| **Network** | Needed once, on first launch, to download the engine image |

> NeuroInsight uses Docker to run its engine. If Docker isn't installed/running,
> the app will prompt you with a link to get it. Install **Docker Desktop**, start
> it, then open NeuroInsight.

## 1. Install Docker Desktop

- **macOS / Windows:** download from <https://www.docker.com/products/docker-desktop/>,
  install, and **launch it** (wait until the whale icon says "running").
- **Linux:** install Docker Engine for your distro (<https://docs.docker.com/engine/install/>)
  and ensure your user can run `docker` (`sudo usermod -aG docker $USER`, then re-login).

## 2. Download NeuroInsight

Get the installer for your platform from the
[Releases page](https://github.com/phindagijimana/neuroinsight_research/releases):

| Platform | File |
|---|---|
| macOS | `NeuroInsight-<version>.dmg` |
| Windows | `NeuroInsight-Setup-<version>.exe` |
| Linux | `NeuroInsight-<version>.AppImage` or `.deb` |

### Verify your download (recommended)

Each release includes `SHA256SUMS.txt`. Confirm the file wasn't corrupted or
tampered with:

```bash
# macOS / Linux
shasum -a 256 -c SHA256SUMS.txt
```
```powershell
# Windows (PowerShell)
(Get-FileHash .\NeuroInsight-Setup-<version>.exe -Algorithm SHA256).Hash
# compare against the matching line in SHA256SUMS.txt
```

## 3. Install & launch

- **macOS:** open the `.dmg`, drag **NeuroInsight** to Applications, launch it.
- **Windows:** run the `.exe` installer, then launch from the Start menu.
- **Linux:** `chmod +x NeuroInsight-*.AppImage && ./NeuroInsight-*.AppImage`, or
  `sudo dpkg -i NeuroInsight-*.deb`.

## 4. First launch

1. NeuroInsight checks that Docker is running.
2. On the **first run only**, it downloads the engine image (~1.8 GB) — you'll see
   a progress message on the splash screen. This can take a few minutes depending
   on your connection.
3. Once ready, the app opens into the **Workspace**. Start with **New job** or
   **Open an imaging file**.

Subsequent launches are fast (the image is cached).

## Updating

NeuroInsight checks for updates automatically and can install them in the
background. You can also check via **Help → Check for Updates…**.

## Troubleshooting

- **"Docker is required" / engine won't start** — make sure Docker Desktop is
  installed **and running**, then reopen NeuroInsight (or **Settings → Engine →
  Start engine**).
- **First launch is slow** — it's downloading the ~1.8 GB engine image; this only
  happens once.
- **Something's wrong** — open **Settings**, expand **Advanced → Diagnostics**, and
  **Export bundle**; attach it when reporting an issue.

## Security & privacy

NeuroInsight runs entirely on your machine; the engine binds to `localhost` only
and generates unique local credentials per install. See the README "Security &
data" section. Do not expose the backend to the internet.
