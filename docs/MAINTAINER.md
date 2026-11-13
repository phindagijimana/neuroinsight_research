# Maintainer documentation map

What lives **on the public docs site** (MkDocs / Read the Docs) vs **in the repo only**
vs **your machine only**.

## Public documentation site

Configured in [`mkdocs.yml`](../mkdocs.yml). Intended for users and external engineers.

- Getting started: Install, How it works, 10-minute tour (`USER_GUIDE.md` anchor)
- Using: Product, Transfer, HPC pipeline guide
- Clinical: CLINICAL_SUPPORT, REFERENCES, TOOL_LICENSES
- Latest **release notes** only (current `RELEASE_NOTES_v*.md` in nav)
- Developers: ENGINEERING.md

**Not on the site** (excluded via `exclude_docs` in `mkdocs.yml`):

| File | Why |
|------|-----|
| `docs/README.md` | GitHub index; site uses `index.md` |
| `docs/RELEASING.md` | Release tagging runbook |
| `docs/SIGNING_AND_TRUST.md` | Signing secrets / CI |
| `docs/BUILDING_DOCS.md` | MkDocs meta |
| Older `RELEASE_NOTES_*.md` | Archive; see CHANGELOG |

Full connector/HPC reference: `docs/USER_GUIDE.md` remains in the repo and is
linked from HOW_IT_WORKS; the site lists it once as **Ten-minute tour** (not twice in nav).

## In repo, maintainer / pilot (not on public site)

| Path | Purpose |
|------|---------|
| `desktop/ops/` | Packaging, pilot smoke tests, licensing ops, support SOP |
| `desktop/architecture/` | Phase-0 architecture, risk register |
| `desktop/RELEASE_REQUIREMENTS.md` | Go-live checklist |
| `eeg/EEG_PLUGINS_AND_WORKFLOWS.md` | EEG plugin design (implementers) |

Public users should use `docs/` only.

## Local only (gitignored)

| Path | Purpose |
|------|---------|
| `local/` | Private notes, URMC runbooks, pilot evidence JSON — see `local.example/README.md` |
| `clear` | Personal scratch (ignored) |
| `site/` | MkDocs build output |

Do not commit credentials, license **private** keys, or patient paths.
