# Pennsieve Platform Registration Checklist (Go/No-Go)

Use this checklist to execute and verify Pennsieve registration end-to-end.

---

## Gate A — Workspace + Access

- [ ] **Workflow Services V2 enabled** for the target workspace
- [ ] **Manager/Admin permissions** to create applications/workflows/compute nodes
- [ ] **Correct workspace selected** in Pennsieve

Go/No-Go:
- **GO** only if all three are true.

---

## Gate B — Local Tooling

- [ ] `pennsieve` CLI installed
- [ ] `pennsieve whoami` works and shows expected user/workspace
- [ ] AWS CLI works (`aws --version`)
- [ ] AWS profile exists (`aws configure list-profiles`)

Verification commands:

```bash
pennsieve --help
pennsieve whoami
aws --version
aws configure list-profiles
```

Go/No-Go:
- **GO** only if all commands run successfully.

---

## Gate C — Compute Resource Setup

- [ ] Register AWS account as compute resource
- [ ] Create compute node in Pennsieve UI
- [ ] Compute node appears healthy/selectable in `Analysis > Configuration`

Registration command:

```bash
pennsieve account register --type AWS --profile <aws_profile>
```

Go/No-Go:
- **GO** only if compute node is healthy and available for runs.

---

## Gate D — Image Availability

- [ ] Required images published and pullable by Pennsieve
- [ ] Tags pinned (no `latest` for production)
- [ ] Registry visibility/auth confirmed

Current phase files:
- `docker/processors/required-images.yaml`
- `pennsieve/registration_bundle_phase2_published.yaml`

Go/No-Go:
- **GO** only if every processor in scope has a reachable image.

---

## Gate E — Processor Contract Compliance

Each processor must:
- [ ] Read input from `INPUT_DIR`
- [ ] Write outputs to `OUTPUT_DIR`
- [ ] Exit `0` on success
- [ ] Exit non-zero on error

Go/No-Go:
- **GO** only when all processors in scope pass this contract.

---

## Gate F — Register Processors

Phase 2 scope (published images):
- [ ] Register all processors listed in `registration_bundle_phase2_published.yaml`

For each processor, confirm:
- [ ] Status = Available
- [ ] Correct CPU/memory
- [ ] Correct image source URL
- [ ] Correct parameter schema

Go/No-Go:
- **GO** only when all in-scope processors are Available.

---

## Gate G — Register Workflows

Phase 2 ready workflows:
- [ ] `cortical_lesion_detection`
- [ ] `wf_freesurfer_longitudinal_full`
- [ ] `wf_hs_detection_v1`
- [ ] `hippo_subfields_t1`
- [ ] `hippo_subfields_t2`

Blocked until remaining images:
- `fmri_full` (needs `xcpd`)
- `diffusion_full` (needs `qsiprep`, `qsirecon`)

Go/No-Go:
- **GO** only when all phase-2 workflows are saved and runnable.

---

## Gate H — Smoke Validation

For each registered workflow:
- [ ] Run on a small test subject
- [ ] Job reaches terminal success
- [ ] Outputs present in expected path
- [ ] Logs are visible and readable

Go/No-Go:
- **GO** to production only if all smoke tests pass.

---

## Gate I — Production Release

- [ ] Freeze versions/digests in registration records
- [ ] Publish user runbook
- [ ] Assign support owner for first-week incidents
- [ ] Enable broader user access

Go/No-Go:
- **GO** when freeze + runbook + ownership are complete.
