# UR Ventures — Technology Development Fund
## Pre-Proposal: NeuroInsight — Turnkey AI Detection of Epilepsy-Causing Brain Lesions

**Lead applicant:** Philbert Ndagijimana, Research Data Engineer, [Department], University of Rochester Medical Center
**Faculty sponsor / PI:** James Gugger, [Department] *(to confirm department/title)*
**UR Ventures invention disclosure:** Filing in progress *(confirm status with UR Ventures)*
**Requested award:** $[40,000–100,000] over 12 months
**Contact:** [email] · [phone]

---

### 1. The opportunity in one paragraph

Roughly one in three people with epilepsy do not respond to medication, and many could be cured by surgery — *if* clinicians can find the small brain lesion causing the seizures. The problem is that these lesions, especially focal cortical dysplasia, are invisible to the human eye on standard MRI in a large fraction of cases. State-of-the-art AI can now detect them, but that AI lives in research code that requires Linux, Docker, and high-performance-computing expertise to run. Epilepsy centers and neuroradiology groups therefore cannot use it. **NeuroInsight packages this detection AI into a one-click application that runs on a clinician's own computer, keeps patient data on-site, and produces a reviewable result — no programming required.** The platform already supports neurologists at URMC; this award would fund the clinical validation, productization, and pilot deployments needed to turn that early adoption into a validated, licensable product.

### 2. The problem and unmet need

Drug-resistant epilepsy affects millions worldwide and drives enormous cost in repeated hospitalizations and lost productivity. Surgery can stop seizures, but only when the seizure-causing lesion is localized. Two gaps block this today:

- **Detection gap.** Focal cortical dysplasia (FCD) is frequently "MRI-negative" to radiologists. Validated AI models — for example the MELD Graph graph-neural-network detector (Wagstyl et al., 2025) — substantially improve detection, yet remain inaccessible outside a handful of expert informatics labs.
- **Usability gap.** Advanced neuroimaging tools (FreeSurfer, fMRIPrep, the MELD pipeline) demand command-line skills, container orchestration, and cluster access. Clinicians and most research staff cannot operate them, so the science never reaches patients.

The result: proven methods sit unused while patients wait. NeuroInsight closes both gaps at once.

### 3. The technology and what makes it defensible

NeuroInsight is a working neuroimaging platform (current pilot release v0.1.13) that delivers research-grade AI through a simple desktop application for macOS, Windows, and Linux. Its differentiated, commercially relevant assets are:

- **Clinical detection pipelines, productized.** Turnkey workflows for FCD (MELD Graph), tuberous-sclerosis tuber segmentation and burden quantification, and hippocampal-sclerosis detection — delivered as one-click tools rather than research scripts.
- **No-DevOps delivery.** The application installs like any consumer app and automatically handles the containers, data movement, and compute that previously required an engineer. This usability layer is the moat: the underlying models are published, but making them usable by clinicians is not.
- **Local-first data handling.** Imaging stays on the user's machine or institution; credentials live in the OS keychain. This design keeps protected health information on-site, easing institutional adoption.
- **Extensible by design.** New tools and multi-step pipelines are defined declaratively, so the catalog can grow without re-engineering the product.

Compared with existing options — open-source toolkits (FSL, FreeSurfer, AFNI, SPM) that require expertise, and commercial neuroimaging software that lacks these epilepsy AI detectors — NeuroInsight is, to our knowledge, the only path that puts validated lesion-detection AI in a clinician's hands without DevOps and without sending data to the cloud.

### 4. Proof of concept (current status)

- **Functional product.** A feature-complete desktop and web application with 19 working imaging plugins and 8 multi-step workflows, including the epilepsy detection pipelines above.
- **Validated infrastructure.** End-to-end job execution confirmed on local Docker and a remote HPC cluster (SLURM); connectors to institutional imaging archives (XNAT) and the NIH-backed Pennsieve platform.
- **Distribution in place.** Native installers for all three desktop platforms; signed/notarized macOS distribution now established, removing a key adoption barrier.
- **Real clinical users and pull demand already.** NeuroInsight is already in active use supporting neurologists in URMC's Department of Neurology, who send us requests to run MELD-based FCD detection on their patients' scans — unprompted demand for the exact capability at the core of this proposal. The team is now extending the platform's workflows into URMC's **Patient Presurgical Conference (PRC)**, the multidisciplinary meeting where epilepsy surgery candidates are reviewed and decided. Embedding results into the PRC moves NeuroInsight from a useful tool to part of the clinical decision-making workflow — and gives us a built-in anchor site for the pilot and validation work below.

What does **not** yet exist — and is exactly what this award funds — is formal clinical validation, hardened productization, and external pilot evidence beyond our initial URMC users.

### 5. Commercialization plan and 12-month objectives

This award advances NeuroInsight from working prototype to validated, deployable product along four parallel tracks:

1. **Clinical validation.** Benchmark the FCD/TSC/hippocampal-sclerosis detectors against expert-labeled, retrospective imaging datasets to quantify accuracy and generate the evidence licensees and clinicians require.
2. **Productization (technical staff).** Hire technical staff to harden the application for deployment: remote job monitoring, Windows signing, packaging, reliability, and an installable clinical configuration.
3. **Pilot deployments.** Formalize the URMC anchor site by integrating NeuroInsight's epilepsy workflows into the Patient Presurgical Conference, then expand to additional epilepsy centers and imaging core facilities to demonstrate real-world use and secure letters of commercial interest.
4. **Market and regulatory validation.** Use NSF I-Corps and fee-for-service consulting to confirm customer segments, pricing, the regulatory pathway, and freedom-to-operate / competitive positioning.

**Success at 12 months** = validated accuracy metrics on real datasets, a deployment-ready signed product, NeuroInsight workflows operationally integrated into URMC's Patient Presurgical Conference, ≥1–2 external pilots with a letter of commercial interest, and a defined regulatory and go-to-market path — the package needed to pursue licensing or a startup.

### 6. Budget summary (eligible categories)

| Category | Use | Approx. |
|---|---|---|
| Technical/staff salary | Developer/research staff for validation + productization | $[ ] |
| Outsourcing / fee-for-service | Market/regulatory consulting, I-Corps, dataset/annotation services | $[ ] |
| Supplies & small equipment (<$5K each) | Test compute, storage, pilot support | $[ ] |
| **Total** | | **$[40–100K]** |

*Excludes ineligible costs (faculty salary, basic research, overhead, gap funding).*

### 7. Market and impact on neuroimaging analysis

Primary customers are epilepsy surgery centers, neuroradiology practices, and academic imaging cores — on the order of thousands of sites globally, with expansion across the broader neuroimaging tool market and adjacent rare-disease indications (e.g., tuberous sclerosis). The clinical detection tools are the wedge; the platform is the durable delivery channel for a growing catalog.

The larger impact is on how neuroimaging analysis gets done. Today, advanced analysis is gated by technical skill: the best pipelines run only where a lab employs someone fluent in Linux, containers, and clusters. NeuroInsight removes that gate, letting any clinician or researcher run validated, reproducible pipelines from their own computer. This shortens the path from imaging-research method to patient care from years to weeks, standardizes how analyses are run across sites, and lets new AI models reach front-line users as soon as they are published. Epilepsy is where we prove this; the same engine extends to structural, functional, and diffusion MRI across neuroscience — turning advanced neuroimaging analysis from an expert-only activity into routine infrastructure.

### 8. Team and commitment

The lead applicant, a Research Data Engineer who architected and built the NeuroInsight platform, will direct the project with appropriate effort, supported by faculty sponsor James Gugger and UR Ventures. The team commits to NSF I-Corps participation, regular UR Ventures progress reviews, and the Fund's revenue-sharing terms.

---

*Open items to finalize before submission: (1) confirm invention disclosure is on file with UR Ventures; (2) confirm James Gugger's department/title and his agreement to sponsor; (3) fill department, budget figures, and contact details; (4) secure at least one letter of commercial interest — your existing URMC Neurology users (e.g., via James Gugger) are the natural first ask.*
