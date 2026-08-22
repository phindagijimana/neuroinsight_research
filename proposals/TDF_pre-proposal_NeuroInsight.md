# UR Ventures — Technology Development Fund
## Pre-Proposal: NeuroInsight — A Clinic-Ready Imaging Decision-Support Tool for Epilepsy

**Lead applicant:** Philbert Ndagijimana, Research Data Engineer, [Department], University of Rochester Medical Center
**Faculty sponsor / PI:** James Gugger, [Department] *(to confirm department/title)*
**Product / platform:** NeuroInsight (NI) — clinic-ready imaging decision-support platform delivering the Epilepsy Workflow package; current workflows: AutoHS (HS detection) and MELD (FCD detection); v0.1.13 pilot
**Core IP (disclosed, in UR Ventures licensing):** AutoHS — automated hippocampal asymmetry-index detection of hippocampal sclerosis, validated against histopathology-confirmed surgical specimens; validation study provisionally accepted at *Brain Communications* *(confirm disclosure/eligibility status)*
**Requested award:** $80,000 over 12 months
**Contact:** [email] · [phone]

---

### 1. The opportunity in one paragraph

Powerful, validated neuroimaging methods for epilepsy already exist — but they are trapped in research code that requires Linux, containers, and computing expertise no clinic has, so it rarely reaches patients. **NeuroInsight closes this gap: it is now a desktop app — a clinic-ready platform that any researcher or clinician can install and use. It runs validated imaging workflows at one click on their own computer, keeps patient data on-site, and returns a reviewable result that supports the clinical decision — no programming required.** NeuroInsight delivers these as an Epilepsy Workflow package, and its current workflows already show both halves of product–market fit: **AutoHS**, a URMC-invented hippocampal-asymmetry detector for hippocampal sclerosis, is validated against histopathology-confirmed surgical specimens (study provisionally accepted at *Brain Communications*) and is in active licensing discussion with UR Ventures; and **MELD**, our clinic-ready workflow built around an external academic focal-cortical-dysplasia model, already draws 15+ unprompted requests from clinicians across URMC. This award would mature NeuroInsight from a working pilot into a deployable, licensable clinical product.

### 2. The problem and unmet need

Drug-resistant epilepsy is often curable by surgery, but only when the responsible lesion is found — and the lesions that cause it (hippocampal sclerosis, focal cortical dysplasia) are frequently subtle or missed on standard visual MRI review. Two gaps block progress:

- **Usability gap (the platform problem).** Advanced, validated neuroimaging tools (FreeSurfer, fMRIPrep, the MELD pipeline, and research methods like AutoHS) demand command-line skills, container orchestration, and cluster access. Clinicians and most research staff cannot operate them, so validated science never reaches the patients who need it.
- **Detection gap.** Even where expertise exists, subtle lesions are under-called. Validated quantitative and AI methods measurably improve detection but stay in the lab.

NeuroInsight closes the usability gap for the whole package; AutoHS and MELD close the detection gap for the two highest-value epilepsy indications.

### 3. The technology and what makes it defensible

NeuroInsight is a working neuroimaging platform (pilot release v0.1.13) for macOS, Windows, and Linux that delivers validated imaging analysis as clinical decision support. It is defensible because:

- **No-DevOps delivery is the moat.** NeuroInsight installs like a consumer app and automatically handles the containers, data movement, and compute that previously required an engineer. Algorithms can be published; making them usable by clinicians at the point of care is the hard part — and it is the platform's core value.
- **Local-first data handling.** Imaging stays on the user's machine or institution and credentials live in the OS keychain, keeping protected health information on-site and easing institutional adoption.
- **An extensible workflow package.** NeuroInsight runs the **Epilepsy Workflow package**; its current workflows are AutoHS (HS detection — URMC IP) and MELD (FCD detection — our workflow around an external academic model, MELD Graph), and new workflows are added without re-engineering the product.
- **A validated, ownable anchor.** The flagship workflow, **AutoHS**, is a concrete URMC invention — validated against histopathology-confirmed surgical specimens, with a provisionally accepted publication and an active UR Ventures licensing path — giving the platform defensible, ownable IP at its core.

A single NeuroInsight install already covers the two most common surgically-treatable epilepsy lesions — hippocampal sclerosis (AutoHS) and focal cortical dysplasia (MELD) — and the platform builds on established toolkits (it uses FreeSurfer, and runs FSL/AFNI/SPM-class pipelines) rather than competing with them, packaging them for clinicians. Compared with the alternatives — research tools that require command-line expertise, recent academic detectors not delivered as clinician-ready products, and commercial neuroimaging software focused on volumetry rather than epilepsy — NeuroInsight is, to our knowledge, the only path that puts validated epilepsy detectors in a clinician's hands without DevOps and without sending data to the cloud.

### 4. Proof of concept (current status)

- **Working platform with a clinical package.** NeuroInsight is a feature-complete desktop/web application with one-click installers for macOS, Windows, and Linux, already delivering the Epilepsy Workflow package (AutoHS, MELD) in our lab for clinical studies. Download integrity is verified by published SHA-256 checksums; macOS code-signing and notarization are in final testing.
- **Validated flagship workflow + commercial interest.** AutoHS is supported by the study *"MRI-derived hippocampal asymmetry identifies hippocampal sclerosis in epilepsy surgical specimens"* — validated against histopathology-confirmed surgical specimens, provisionally accepted at *Brain Communications* — and is in active licensing discussion with UR Ventures.
- **Clinical pull demand, quantified.** URMC neurologists already send NeuroInsight unprompted requests to run the **MELD** workflow on their patients' scans — over 15 requests to date, from clinicians across URMC — demonstrating real demand for the package.
- **Path into clinical decision-making.** We are integrating NeuroInsight's workflows into URMC's **Patient Presurgical Conference (PRC)** — the multidisciplinary meeting where epilepsy surgery candidates are decided — moving the platform from a useful aid to part of the decision workflow, and giving us a built-in anchor site.
- **Validated infrastructure.** End-to-end execution confirmed on local Docker and a remote HPC cluster (SLURM); connectors to institutional imaging archives (XNAT) and the NIH-backed Pennsieve platform.

What does **not** yet exist — and is exactly what this award funds — is multi-dataset clinical validation beyond our own studies, hardening for deployment outside our lab, and external pilot evidence beyond URMC.

### 5. Commercialization plan and 12-month objectives

This award matures NeuroInsight from a working pilot into a deployable, licensable clinical platform along four parallel tracks:

1. **Clinical validation.** Validate the package's detectors — AutoHS first, then MELD/FCD — on independent, expert-labeled, multi-site datasets to quantify accuracy and produce the evidence licensees and clinicians require.
2. **Platform productization (technical staff).** Harden NeuroInsight for deployment outside our lab: workflow packaging, remote job monitoring, Windows signing, reliability, and an installable clinical configuration.
3. **Pilot deployments.** Formalize the URMC anchor site by integrating the package into the Patient Presurgical Conference, then expand to additional epilepsy centers and imaging cores to demonstrate real-world use and secure letters of commercial interest.
4. **Market validation.** Use NSF I-Corps and fee-for-service consulting to confirm customer segments, pricing, freedom-to-operate, and competitive positioning, in coordination with the UR Ventures AutoHS licensing process.

**Success at 12 months** = a deployment-ready signed NeuroInsight release, quantified AutoHS accuracy on independent datasets, the Epilepsy Workflow package operationally integrated into URMC's Patient Presurgical Conference, ≥1–2 external pilots with a letter of commercial interest, and a defined go-to-market path — the package needed to complete the AutoHS license and scale the platform.

### 6. Budget summary (eligible categories)

| Category | Use | Amount |
|---|---|---|
| Technical/staff salary | Developer/research staff for platform productization and AutoHS validation | $58,000 |
| Outsourcing / fee-for-service | I-Corps and market/competitive validation; dataset access, de-identification, and expert annotation | $16,000 |
| Supplies & small equipment (<$5K each) | Cloud/test compute, storage, and pilot-site support | $6,000 |
| **Total** | | **$80,000** |

*Excludes ineligible costs (faculty salary, basic research, overhead, gap funding).*

### 7. Impact

For epilepsy care, NeuroInsight means subtle, surgically-relevant lesions are far less likely to be missed, because validated detectors — starting with AutoHS — reach the clinicians making surgical decisions instead of staying in a research repository. More broadly, NeuroInsight changes how neuroimaging analysis gets done: today the best pipelines run only where a lab employs someone fluent in Linux, containers, and clusters; NeuroInsight removes that gate, letting any clinician or researcher run validated, reproducible analyses from their own computer. This shortens the path from imaging-research method to patient care, standardizes how analyses are run across sites, and lets newly published models reach front-line users quickly. Epilepsy is where we prove the model; the same platform extends to other detectors and to structural, functional, and diffusion MRI across neuroscience.

### 8. Team and commitment

The lead applicant, a Research Data Engineer who architected and built the NeuroInsight platform, will direct the project with appropriate effort, supported by faculty sponsor James Gugger and UR Ventures. The team commits to NSF I-Corps participation, regular UR Ventures progress reviews, and the Fund's revenue-sharing terms.

---

*Open items to finalize before submission: (1) confirm AutoHS invention-disclosure status with UR Ventures, and confirm the active licensing discussion does not affect TDF eligibility (the fund excludes technologies with existing licensing options/agreements); (2) confirm James Gugger's department/title and his agreement to sponsor; (3) fill department and contact details; (4) secure at least one letter of commercial interest — your URMC Neurology PRC users (via James Gugger) are the natural first ask.*
