# NeuroInsight Desktop

Packaged **NeuroInsight** app — Electron shell (`desktop/app/`) plus release ops (`desktop/ops/`).

## Layout

| Path | Purpose |
|---|---|
| `app/` | Electron main process, control center, packaging config |
| `ops/` | Packaging scripts, **maintainer-only** runbooks (not on public docs site) |
| `architecture/` | Phase-0 notes (maintainer-only) |

**Public documentation:** [docs/index.md](../docs/index.md) (MkDocs / Read the Docs).  
**Doc tiers:** [docs/MAINTAINER.md](../docs/MAINTAINER.md).

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
