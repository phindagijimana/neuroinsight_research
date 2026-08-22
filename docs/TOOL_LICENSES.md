# Tool licenses (FreeSurfer, MELD, and others)

Some neuroimaging **plugins** require a free license file before jobs can run.
This is separate from a commercial **NeuroInsight app license** (`nir_license.txt`)
— see [license_future.md](../license_future.md).

## Setup

**From source:** run `./research license` — it checks for required files and
guides you through placement.

**Desktop app:** upload licenses in **Settings → Licenses** (stored locally;
used automatically for jobs).

## Required files

| File | Required by | Registration |
|---|---|---|
| `license.txt` | FreeSurfer, FastSurfer, fMRIPrep, MELD Graph | https://surfer.nmr.mgh.harvard.edu/registration.html |
| `meld_license.txt` | MELD Graph (v2.2.4+) | https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform |
| *(none)* | QSIPrep, QSIRecon, XCP-D, dcm2niix | — |

## Where files are read

- **Source deployment:** project root, or `~/.freesurfer/license.txt` and
  `~/.meld/meld_license.txt`
- **HPC jobs:** copied into each job's `scripts/` directory on submit when
  configured on the NeuroInsight host
