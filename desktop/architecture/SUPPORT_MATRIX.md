# Phase 0 Support Matrix

This matrix defines what platforms are targeted and in what order, without impacting current NIR CLI-hosted deployment.

## Initial Desktop Support Policy

- Tier 1 (Phase 1-2 focus): Linux
- Tier 2 (next): macOS
- Tier 3 (after stabilization): Windows

## Desktop Platform Matrix

| Platform | Version Baseline | Phase Priority | Notes |
|---|---|---:|---|
| Ubuntu Linux | 22.04 LTS / 24.04 LTS | 1 | Primary target for first desktop stabilization |
| Rocky/Alma Linux | 9.x | 1 | Optional institutional validation target |
| macOS | latest - 2 major versions | 2 | Requires signing/notarization workflow |
| Windows | 11 (supported enterprise builds) | 3 | Requires MSI/signing and endpoint policy testing |

## Runtime Dependencies

| Dependency | Requirement | Applies To |
|---|---|---|
| Docker | Required for standardized backend runtime | Linux/macOS/Windows |
| Node.js | Used for desktop build toolchain | dev/build environment |
| Python | Used by NIR backend runtime | bundled/managed runtime path |

## Compatibility Guardrails

- Desktop must not break existing web-hosted NIR usage.
- Desktop behavior differences by platform must be feature-flagged and clearly surfaced in UI.
- Any unsupported feature on an OS must fail with actionable messaging, not silent errors.

## Test Expectations by Stage

## Stage A (Linux)

- install desktop app
- start backend successfully
- open Jobs/Transfer pages
- browse connector data and submit a smoke workflow

## Stage B (macOS)

- all Stage A checks
- signed installer validation
- keychain and permission prompts validated

## Stage C (Windows)

- all Stage A checks
- signed installer/upgrade flow
- Windows Defender/policy compatibility checks

## Revision Policy

This matrix should be reviewed at the start of each implementation phase and updated only with explicit acceptance of support impact.
