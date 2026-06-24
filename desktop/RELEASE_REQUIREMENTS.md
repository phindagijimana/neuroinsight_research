# NIR Desktop — Production & Distribution Requirements

Status of the production push and the **external inputs only you can provide**.
Everything code/config-reachable is done and verified; the items below marked
"needs input" cannot be completed by code alone.

## Readiness matrix

| Area | Status | Notes |
|---|---|---|
| App launches + backend lifecycle | ✅ done | verified (E2E + screenshots) |
| Core UI flows automated (no manual click-through) | ✅ done | Playwright Electron suite + CI |
| UX polish (nav back, toast, vault, disabled states) | ✅ done | native menu + in-page Control Center button |
| Security hardening (sandbox, nav guards, IPC allowlist) | ✅ done | E2E green under sandbox |
| Licensing (validate/grace/expiry/enforcement) | ✅ done | Ed25519 verified |
| Credentials (keychain, no plaintext) | ✅ done | verified |
| Packaging (macOS dmg) + checksums + verify | ✅ done | Phase 4 |
| Self-contained backend (no venv) | ✅ built + integrated | binary serves /health; desktop auto-detects it. Installer-bundling step below |
| Auto-update wiring | ✅ wired | activates once releases publish update metadata |
| Reliability gate (CI-enforced) | ✅ done | blocks GA on no_go once a real report exists |
| **Code-signing / notarization** | ⛔ needs input | requires your certificates |
| **Linux/Windows installers built + smoke-tested** | ⛔ needs runners | build on those OSes (CI matrix is wired) |
| **Scored pilot** | ⛔ needs pilot | run the pilot, fill the report |
| **Live connector validation** | ⛔ needs creds | Pennsieve/XNAT/HPC, or build mock servers |

## External inputs required (and exactly what they unlock)

1. **macOS signing + notarization** — set repo secrets:
   `CSC_LINK` (Developer ID Application cert, base64/URL), `CSC_KEY_PASSWORD`,
   `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`.
   → unlocks signed/notarized `.dmg`; the afterSign hook + trust check are already wired.
2. **Windows code signing** — `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`.
   → unlocks a signed `.exe`; `verify_trust.js` enforces it automatically when set.
3. **Release publishing / auto-update feed** — a `GH_TOKEN` with release write, and
   build the release CI with `--publish always` so `electron-updater` metadata
   (`latest*.yml`) is uploaded. → activates auto-update.
4. **Pilot** — run `PILOT_CHECKLIST.md` with 3–10 users, fill
   `desktop/ops/pilot_reliability_report.json`. → the reliability gate then scores
   go / conditional / no-go and blocks GA on P0/P1.
5. **Connector validation** — real Pennsieve/XNAT/HPC credentials for a live smoke,
   or commission the mock-connector-server option to test the flows in CI.

## Shipping the self-contained backend in installers

The backend bundle is **built, integrated, and verified** (the desktop prefers it
over a venv automatically). To include it in the distributed installer:

1. In the release job, on **each OS runner**, set up Python + backend deps and run:
   ```bash
   bash desktop/ops/build_backend.sh        # -> desktop/dist/backend/nir-backend/
   ```
2. Add to `desktop/app/package.json` `build` (only when the bundle is present —
   keep it out of the default config so clean builds don't fail):
   ```json
   "extraResources": [
     { "from": "../dist/backend/nir-backend", "to": "backend/nir-backend", "filter": ["**/*"] }
   ]
   ```
   `backendManager.resolveBackendBin()` already looks in `resources/backend/nir-backend`.

**Follow-ups for a true zero-repo install** (works without the repo checked out):
- bundle the Celery worker the same way (currently best-effort via venv),
- resolve `plugins/`, `workflows/`, `alembic/` from the bundle (`sys._MEIPASS`) when
  frozen instead of `NIR_REPO_DIR`,
- ship default infra config (the app still needs Postgres/Redis/MinIO via Docker).

## Remaining steps to GA (ordered)

1. Add your signing secrets → run `desktop_release_multi.yml` → signed/notarized
   macOS + Windows artifacts, trust-verified.
2. Add the per-OS backend-build step + `extraResources` → installers ship the
   self-contained backend.
3. Publish a release with update metadata → auto-update live.
4. Run the pilot → fill the report → reliability gate → go-live recommendation.
5. (Optional) Mock connector servers or a live connector smoke.
