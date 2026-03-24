# NIR Desktop — Control Center

The Control Center is the desktop management panel for NeuroInsight Research. It gives you direct access to backend controls, diagnostics, credentials, license, and app lock — all outside the NIR web interface.

## How to Open the Control Center

When NIR is running in the main window, access the Control Center from the menu bar:

**macOS:** `NeuroInsight Research` menu → **Control Center** (or `⌘ Shift C`)
**Windows / Linux:** `NeuroInsight Research` menu → **Control Center** (or `Ctrl Shift C`)

To return to NIR from the Control Center, use the same menu → **Open NIR** (or `⌘ Shift N` / `Ctrl Shift N`).

---

## Sections

### Backend Status

Shows whether the local backend is running and on which port.

| Button | What it does |
|---|---|
| **Start Backend** | Starts the backend and Celery worker |
| **Stop App Services** | Stops backend and Celery (keeps PostgreSQL/Redis/MinIO running) |
| **Stop (App + Infra)** | Stops everything including database containers |
| **Open NIR (Same Window)** | Loads the NIR interface in the current window |
| **Refresh Status** | Re-checks backend health |
| **Auto-open NIR when desktop starts** | Toggle — when checked, NIR opens automatically after backend starts |

---

### Compatibility Checks

| Button | What it does |
|---|---|
| **Run Preflight** | Checks Python, Docker, disk space, container images, and infrastructure |
| **Export Diagnostics** | Saves a full diagnostics bundle to disk (useful for support) |

Preflight output is shown in the panel. Green = OK, warnings shown for missing container images or low disk.

---

### License

Displays current license status (valid / invalid / missing / expired).

| Action | How |
|---|---|
| Import a license file | Click **Import License File** and select your `nir_license.txt` |
| Paste license JSON | Paste into the text area and click **Import License Text** |
| Refresh status | Click **Refresh License** |

A valid license shows the plan tier, organization ID, features, and days remaining.

> **Auto-import:** If a `nir_license.txt` file is placed in the same folder as the app (or next to the `.app` bundle on macOS), it is imported automatically on launch.

---

### Local App Lock

Restricts sensitive actions (starting backend, importing license, managing secrets) behind a PIN.

| Action | How |
|---|---|
| **Enable Lock** | Enter a PIN (minimum 6 characters) and click Enable |
| **Unlock** | Enter your PIN and click Unlock to allow sensitive actions |
| **Lock Now** | Immediately lock without quitting |
| **Disable Lock** | Enter PIN and disable the lock entirely |

When the app is locked, the backend cannot be started and secrets cannot be read or written until you unlock.

---

### Credential Vault

Stores secrets (API keys, passwords) using the platform's native secure storage:
- **macOS:** Keychain
- **Windows:** Windows Credential Manager
- **Linux:** Secret Service / encrypted fallback

All keys are namespaced (e.g. `pennsieve.api_key`, `hpc.username`). Use the **Preset** dropdown to pick common key names.

| Action | How |
|---|---|
| **Save Secret** | Enter key + value, click Save |
| **Load Secret** | Enter key, click Load — value appears in the field |
| **Delete Secret** | Enter key, click Delete |

---

### Desktop Storage

Shows where the desktop stores its settings and logs:

- **Settings file:** `nir-desktop-settings.json` in the app data directory
- **Log file:** `desktop.log` — records backend start/stop, preflight runs, license events, and errors

---

## Keyboard Shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Open NIR | `⌘ Shift N` | `Ctrl Shift N` |
| Open Control Center | `⌘ Shift C` | `Ctrl Shift C` |
| Reload page | `⌘ R` | `Ctrl R` |
| Toggle DevTools | `⌘ Option I` | `Ctrl Shift I` |
| Zoom in / out | `⌘ +` / `⌘ -` | `Ctrl +` / `Ctrl -` |
| Full screen | `⌘ Ctrl F` | `F11` |

---

## Troubleshooting

**Backend shows Stopped after launch**
Run preflight to check for missing dependencies. Common causes: Docker Desktop not running, Python not found, port conflict.

**License shows Missing**
Place `nir_license.txt` next to the app and relaunch, or use Import License File in the Control Center.

**App is locked and I forgot my PIN**
Delete the app lock state file at:
- macOS: `~/Library/Application Support/nir-desktop-app/nir-desktop/applock.json`
- Windows: `%APPDATA%\nir-desktop-app\nir-desktop\applock.json`
- Linux: `~/.config/nir-desktop-app/nir-desktop/applock.json`

**Diagnostics bundle location**
Exported to your Desktop by default. The filename is `nir-diagnostics-<timestamp>.json`.
