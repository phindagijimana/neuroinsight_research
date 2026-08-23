# Desktop updates (NeuroInsight)

NeuroInsight has **two parts** that version together but update differently:

| Part | What it is | Where the version lives |
|---|---|---|
| **Desktop app** | Electron shell (menus, engine start/stop) | `NeuroInsight.app` / installer |
| **Engine** | Docker container with the workspace UI and API | `ghcr.io/phindagijimana/nir-allinone:v<version>` |

The workspace you use daily (Jobs, Results, Viewer, sidebar) is served by the
**engine**. Updating only the desktop shell may not change the workspace until
the engine is restarted on the matching image version.

---

## Check for updates (macOS)

**Help is in the macOS menu bar**, not inside the NeuroInsight window.

1. Click the NeuroInsight window so it is the active app.
2. At the **top of the screen**, open **Help → Check for Updates…**
   (menu bar: **NeuroInsight | File | Edit | View | Help**).
3. If an update exists, you get a dialog — nothing downloads until you confirm.

On startup, the app also checks silently. If you are already on the latest
version, **no dialog appears** (this is normal).

---

## In-app update flow

When a newer desktop build is available:

1. **Check** — app reads `latest*.yml` from the GitHub release feed.
2. **Confirm** — dialog: *“NeuroInsight X.Y.Z is available.”* → **Download & Install** or **Later**.
3. **Download** — ~90 MB on macOS (progress is not shown; usually under a minute).
4. **Confirm restart** — *“Restart Now”* or **Later** (installs on next quit if you choose Later).
5. **Restart** — app quits, installs, and relaunches.

### How long after **Restart Now**?

| Phase | Typical time |
|---|---|
| App quits + installs update | **10–30 seconds** (up to ~1 min) |
| Splash: preflight + start engine | **30 sec – 2 min** if the engine image is already cached |
| First pull of a new engine image | **+5–20 min** (multi-GB Docker download) |

You should see the blue splash with status text (*Running checks…*, *Starting engine…*,
*Opening workspace…*).

---

## Install location (macOS)

Always install to **Applications**:

1. Open the **`.dmg`** from the [Releases](https://github.com/phindagijimana/neuroinsight_research/releases) page.
2. Drag **NeuroInsight.app** to **Applications**.
3. Launch from **Applications**, not from Downloads or the mounted disk image.

Running from Downloads can block updates from applying cleanly (macOS
App Translocation / quarantine).

---

## Which file to download?

| File | Purpose |
|---|---|
| **`.dmg`** (macOS) | **Manual install** — open, drag to Applications |
| **`.exe`** (Windows) | Manual install |
| **`.AppImage` / `.deb`** (Linux) | Manual install |
| **`-arm64-mac.zip`** (macOS) | **Auto-update only** — used internally by the app; **do not** double-click or unzip to “install” |

---

## Refresh the engine after a desktop update

After updating the desktop app, restart the engine so the workspace matches:

1. **NeuroInsight → Settings** (`Cmd+,`)
2. **Stop engine** → wait a few seconds → **Start engine**
3. **NeuroInsight → Open Workspace** (`Cmd+Shift+O`)

The packaged app targets `nir-allinone:v<desktop version>`. If the engine was
still on an older image, the UI can look unchanged until you restart it.

Verify engine version:

```bash
curl -s http://127.0.0.1:8800/health | python3 -m json.tool | grep version
```

---

## Troubleshooting

### No prompt / “nothing happened”

- You may already be on the latest desktop version — use **Help → Check for Updates…**
  to see *You are on the latest version.*
- Startup checks are **silent** when there is nothing to install.
- Make sure NeuroInsight is the **focused app** so the **Help** menu is visible in the menu bar.

### `Please check update first` (v0.1.19 and older)

Fixed in **v0.1.20+**. Upgrade once via the **DMG**, then in-app updates work again.

### UI still looks the same after updating

The **engine** is probably still on an old image — see [Refresh the engine](#refresh-the-engine-after-a-desktop-update) above.

### Update download failed

- Confirm network access to GitHub Releases.
- Install manually from the **DMG** on the release page.
- Export a diagnostics bundle: **Settings → Advanced → Diagnostics → Export bundle**
  (logs: `~/Library/Application Support/nir-desktop-app/nir-desktop/logs/desktop.log` on macOS).

---

## For maintainers

See [RELEASING.md](RELEASING.md) for tagging and CI. Auto-update requirements:

- Publish **`desktop-v*`** releases with `latest-mac.yml`, `latest.yml`, `latest-linux.yml`.
- macOS CI must ship **both `.dmg` and `.zip`** — Squirrel.Mac auto-update requires the signed zip (`dist:mac:ci` builds `dmg zip`).
- Ship **`nir-v*`** (engine image) before or with the matching **`desktop-v*`** tag so
  `ghcr.io/phindagijimana/nir-allinone:v<version>` exists when users launch the new desktop build.

Implementation: `desktop/app/src/updater.js`, `desktop/app/src/main.js` (`promptAndUpdate`).
