# NeuroInsight Desktop

Packaged **NeuroInsight** app — Electron shell (`desktop/app/`) plus release ops (`desktop/ops/`).

## Layout

| Path | Purpose |
|---|---|
| `app/` | Electron main process, control center, packaging config |
| `ops/` | Install helpers, release metadata, pilot checklists |
| `architecture/` | Baseline notes (internal) |
| `PHASE_PLAN.md` | Implementation history (internal) |

## User & maintainer docs

- Install: [docs/INSTALL.md](../docs/INSTALL.md)
- Updates: [docs/DESKTOP_UPDATES.md](../docs/DESKTOP_UPDATES.md)
- Release: [docs/RELEASING.md](../docs/RELEASING.md)
- Signing: [docs/SIGNING_AND_TRUST.md](../docs/SIGNING_AND_TRUST.md)

## Build (maintainers)

```bash
cd desktop/app && npm install && npm run dist:mac:ci   # or dist:linux:ci / dist:win:ci
```

CI builds on `desktop-v*` tags — see RELEASING.md.
