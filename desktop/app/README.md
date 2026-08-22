# NeuroInsight desktop app (Electron)

Electron shell for the packaged **NeuroInsight** desktop app (`desktop/app/`).

## What it does

- Control center: engine start/stop, preflight (Docker, disk, keychain), diagnostics export
- Hosts the web UI in-window; backend runs in the **all-in-one Docker** container
- OS keychain credential vault, optional license import, user-confirmed auto-update
- Builds via `electron-builder` → `.dmg` / `.exe` / AppImage (see [docs/RELEASING.md](../../docs/RELEASING.md))

## Develop locally

```bash
cd desktop/app
npm install
npm start          # requires Docker Desktop + repo checkout for engine image
npm run check      # static source checks
```

Packaging and release ops: [../ops/README.md](../ops/README.md). Product docs:
[../../docs/INSTALL.md](../../docs/INSTALL.md).
