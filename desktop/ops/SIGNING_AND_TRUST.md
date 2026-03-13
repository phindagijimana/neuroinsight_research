# Desktop Signing and Trust (Phase 6)

This guide describes how to enable trusted installers in CI for macOS and
Windows while keeping unsigned fallback builds available when secrets are not
configured.

## Why this matters

- Checksums verify integrity of downloads.
- Code-signing and notarization establish platform trust.
- macOS Gatekeeper and Windows SmartScreen rely on signed artifacts.

## GitHub Secrets Required

Configure these repository secrets before expecting signed artifacts.

### macOS signing + notarization

- `CSC_LINK` - base64 or URL form of Developer ID Application certificate
- `CSC_KEY_PASSWORD` - password for the signing certificate/private key
- `APPLE_ID` - Apple account used for notarization
- `APPLE_APP_SPECIFIC_PASSWORD` - app-specific password for notarization
- `APPLE_TEAM_ID` - Apple Developer Team ID

### Windows code signing

- `WIN_CSC_LINK` - base64 or URL form of Windows signing certificate
- `WIN_CSC_KEY_PASSWORD` - password for Windows certificate/private key

## Workflow behavior

The multi-platform workflow detects signing secret availability per platform:

- If secrets are present:
  - builds signed artifacts
  - runs platform trust checks
- If secrets are not present:
  - produces unsigned artifacts
  - still publishes checksums/metadata

## Verification in CI

- Windows: `Get-AuthenticodeSignature` must report `Valid`.
- macOS: `codesign -dv` and `xcrun stapler validate` must pass.

## User-facing verification

- Integrity: `shasum -a 256 -c desktop-release-sha256-<platform>.txt`
- Trust:
  - macOS: app opens without quarantine bypass for notarized builds
  - Windows: signature details visible in installer properties

## Notes

- Linux artifacts are currently checksum-verified but not signed in this track.
- Unsigned macOS builds may show "is damaged" / blocked by Gatekeeper and need
  manual bypass for pilot testing.
