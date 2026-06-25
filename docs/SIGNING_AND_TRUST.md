# Signing, Notarization & Trust

This is the runbook for shipping installers that **any user can run without scary
warnings**. Unsigned builds trigger macOS Gatekeeper ("NeuroInsight can't be
opened because Apple cannot check it for malicious software") and Windows
SmartScreen ("Windows protected your PC"). Most users will not click through
those — so for public distribution, signing is mandatory.

The release workflow (`.github/workflows/desktop_release_multi.yml`) **refuses to
publish** a `desktop-v*` release unless the platform's signing secrets are
present. Internal/pilot builds via manual `workflow_dispatch` (without
`publish_to_release`) may stay unsigned.

| Platform | Required for a public release? | Mechanism |
|----------|-------------------------------|-----------|
| macOS    | Yes — sign **and** notarize   | Developer ID Application cert + Apple notary |
| Windows  | Yes — Authenticode sign       | OV or (preferred) EV code-signing cert |
| Linux    | No                            | AppImage/.deb verified via published SHA-256 checksums |

---

## Interim trust before signing — checksums

Until code-signing certificates are in place, **checksums are the integrity
mechanism**. They're produced automatically on every build (no separate step):

- **`SHA256SUMS.txt`** is written next to the installers by the
  `afterAllArtifactBuild` hook (`build/after_all_artifact_build.js`) and
  published with each release. Verify a download before running it:

  ```bash
  # macOS / Linux
  shasum -a 256 -c SHA256SUMS.txt        # or: sha256sum -c SHA256SUMS.txt
  ```
  ```powershell
  # Windows
  (Get-FileHash .\NeuroInsight-Setup.exe -Algorithm SHA256).Hash
  # compare against the matching line in SHA256SUMS.txt
  ```

- **In-app self-check.** The `afterPack` hook (`build/after_pack.js`) bakes
  `app-integrity.json` (the SHA-256 of `app.asar`) into the app. At launch the
  main process re-hashes `app.asar` and compares; on a mismatch it logs
  `integrity_mismatch` and warns the user that the install was modified or
  corrupted. This is a no-op in dev and is superseded by the OS signature once
  signing is enabled.

Checksums detect corruption and tampering-in-transit, but they do **not** prove
origin the way a code signature does — so they are a bridge, not a replacement
for signing.

---

## GitHub Secrets to configure

Set these in **Settings → Secrets and variables → Actions** (repository secrets):

| Secret | Platform | What it is |
|--------|----------|-----------|
| `CSC_LINK` | macOS | base64 of your Developer ID Application `.p12` |
| `CSC_KEY_PASSWORD` | macOS | password for that `.p12` |
| `APPLE_ID` | macOS | Apple ID email used for notarization |
| `APPLE_APP_SPECIFIC_PASSWORD` | macOS | app-specific password (not your Apple ID password) |
| `APPLE_TEAM_ID` | macOS | 10-char Apple Developer Team ID |
| `WIN_CSC_LINK` | Windows | base64 of your code-signing `.pfx` |
| `WIN_CSC_KEY_PASSWORD` | Windows | password for that `.pfx` |

`base64` a cert: `base64 -i cert.p12 | pbcopy` (macOS) or `base64 -w0 cert.pfx` (Linux).

---

## macOS — one-time setup

1. **Enroll** in the Apple Developer Program ($99/yr) for an organization or
   individual.
2. In Xcode or developer.apple.com, create a **"Developer ID Application"**
   certificate (this is the one for distributing *outside* the App Store).
   Export it from Keychain Access as a `.p12` (includes the private key); set a
   strong password.
3. Create an **app-specific password**: appleid.apple.com → Sign-In & Security →
   App-Specific Passwords. This is `APPLE_APP_SPECIFIC_PASSWORD`.
4. Find your **Team ID**: developer.apple.com → Membership.
5. Add the five macOS secrets above.

Notarization is handled automatically by `desktop/app/build/notarize.js`
(electron-builder `afterSign` hook), which runs `xcrun notarytool submit --wait`
then `stapler staple`. The app already builds with `hardenedRuntime: true` and
`build/entitlements.mac.plist`.

Verify a built `.dmg` locally:
```bash
spctl -a -vvv -t install /path/to/NeuroInsight.dmg   # should say: accepted, source=Notarized Developer ID
xcrun stapler validate /path/to/NeuroInsight.app
```

## Windows — one-time setup

1. Buy a code-signing certificate from a CA (DigiCert, Sectigo, etc.).
   - **OV** (Organization Validation): cheaper, but SmartScreen reputation
     builds up only after many installs.
   - **EV** (Extended Validation): instant SmartScreen reputation; usually
     ships on a hardware token (harder to use in CI — some CAs offer
     cloud/HSM signing).
2. Export as `.pfx` with the private key + password.
3. Add `WIN_CSC_LINK` (base64 of the `.pfx`) and `WIN_CSC_KEY_PASSWORD`.

electron-builder signs the NSIS installer automatically when these are set
(`signingHashAlgorithms: ["sha256"]` is configured).

## Linux

No signing required. The workflow publishes `desktop-release-sha256*.txt`; the
install helper verifies the checksum before running. Optionally GPG-sign the
checksum file and publish your public key for stronger provenance.

---

## Auto-update integrity

The app auto-updates via `electron-updater` reading `latest*.yml` from GitHub
Releases. On macOS and Windows, electron-updater verifies the downloaded
artifact's **code signature** before applying — so once signing is in place,
updates are protected too. This is another reason signing is non-optional for
public distribution.

## Releasing (summary)

```bash
python3 scripts/bump_version.py 0.2.0
git commit -am "chore: release v0.2.0"
git tag nir-v0.2.0     && git push origin nir-v0.2.0      # GHCR all-in-one image v0.2.0
git tag desktop-v0.2.0 && git push origin desktop-v0.2.0  # signed installers -> GitHub Release
```

If signing secrets are missing, the `desktop-v*` build **fails fast** with a
clear error rather than publishing an unsigned installer.
