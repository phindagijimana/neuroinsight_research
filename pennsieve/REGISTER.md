# Pennsieve Registration Runbook

This folder translates NeuroInsight's current catalog into Pennsieve-ready records:

- 14 processors (from `plugins/*.yaml`)
- 7 workflows (from `workflows/*.yaml`)

Source file: `pennsieve/registration_bundle.yaml`
Phase 2 partial file: `pennsieve/registration_bundle_phase2_published.yaml`
Phase 4 worksheet: `pennsieve/PHASE4_REGISTRATION_WORKSHEET.md`

## 0) Prerequisites

- Pennsieve workspace with **Workflow Services V2** enabled
- Pennsieve Agent installed and authenticated
- AWS account/profile available for compute resource registration
- Docker images published and pullable (see `docker/processors/`)

## 1) Register compute resource + compute node

From docs:
- `pennsieve whoami`
- `pennsieve account register --type AWS --profile <aws_profile>`

Then in Pennsieve UI:
- `Analysis > Configuration > Create Compute Node`

## 2) Register processors (14)

In Pennsieve UI:
1. `Analysis > Configuration > Create Application`
2. For each entry in `registration_bundle.yaml > processors`:
   - Name: `application_name`
   - Source details / image: `source_url`
   - Type: `application_type`
   - CPU / Memory: `resources`
   - Parameters: `parameters`
   - Compute types: `compute_types` (default `ecs`)

## 3) Register workflows (7)

In Pennsieve workflow builder:
1. Create named workflow with `workflow_name`
2. Add processors in listed order
3. Wire dependencies using each `depends_on`
4. Save and publish

## 4) Processor contract checks

Each processor image should:
- Read input from `INPUT_DIR`
- Write output to `OUTPUT_DIR`
- Exit `0` on success and non-zero on failure

If a current image is not contract-compatible, add a thin wrapper image for Pennsieve registration.

## 5) Smoke test

For each workflow:
1. Open dataset
2. Click `Run Analysis`
3. Pick compute node
4. Select workflow
5. Run on a small subject
6. Verify status and logs in `Analysis > Activity`

## Notes

- This repository now contains a complete translation bundle. Registration itself is done in Pennsieve UI/agent using your workspace credentials.
- After registration, keep image tags pinned for reproducibility (avoid mutable `latest`).

## Phase 2 (published images only)

If you are proceeding with currently published images only:

- Register processors from `registration_bundle_phase2_published.yaml` (11 processors).
- Register workflows from `workflows_ready_now` (5 workflows).
- Defer:
  - `fmri_full` (needs `xcpd`)
  - `diffusion_full` (needs `qsiprep`, `qsirecon`)
