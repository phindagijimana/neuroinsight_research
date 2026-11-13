# Local-only documentation (template)

Copy this folder to **`local/`** at the repo root (ignored by git):

```bash
cp -R local.example local
```

Put here anything that should **not** be on GitHub or Read the Docs, for example:

- Site-specific HPC cheat sheets (partitions, modules, scratch paths)
- Pilot reliability reports (`pilot_reliability_report.json`)
- Internal URMC workflow IDs and contacts
- Personal analysis notes (e.g. one-off recon notes)

The public product docs live under `docs/` and https://readthedocs.org after import.
