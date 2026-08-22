# UR Ventures — Technology Development Fund — Application Form Answers
## NeuroInsight — Clinic-Ready Epilepsy Imaging Platform

*Form-field answers for the TDF online application. Each field below shows the form's actual question prompt (in italics), followed by the answer to paste. Companion long-form narrative: TDF_pre-proposal_NeuroInsight. Bracketed items still need your input. Character limits are noted per field and apply to the answer only.*

---

### Proposal Title (≤120 characters)

> Proposal Title (Required). 120-character maximum.

NeuroInsight: A Clinic-Ready Imaging Decision-Support Tool for Epilepsy

*(Alternative minimal entry: "NeuroInsight". The descriptive title above is stronger and well within the limit.)*

---

### Amount of Funding Requested

> Amount of Funding Requested (Required). $100,000 maximum funding amount.

$80,000

---

### Background (≤3500 characters)

> Briefly describe your recent research, the problem that you are solving, and the benefits of your proposed solution. How is this innovation differentiated from commercially available technologies? What is the competitive landscape (including technologies in development that are not yet commercial)? What is the estimated market potential?

NeuroInsight (NI) is a clinic-ready imaging decision-support platform developed at URMC — now a desktop app that any researcher or clinician can install and use — that surfaces validated, reviewable image analysis to support clinical decisions, without programming: it runs validated workflows at one click and keeps patient data on-site. NI delivers these as an Epilepsy Workflow package; its current workflows are AutoHS (hippocampal sclerosis) and MELD (focal cortical dysplasia). AutoHS, a URMC invention, is validated against histopathology-confirmed surgical specimens (provisionally accepted at Brain Communications) and is in active UR Ventures licensing discussion. MELD — our clinic-ready workflow built around an external academic AI model — already draws 15+ unprompted clinician requests across URMC. Together they give the platform an ownable, validated anchor and proven demand.

Problem. Drug-resistant epilepsy is often curable by surgery, but only when the causative lesion (e.g., hippocampal sclerosis, focal cortical dysplasia) is found — and these lesions are frequently subtle or missed on standard visual MRI review. Validated quantitative and AI methods improve detection, yet they remain trapped in research code that requires Linux, containers, and high-performance-computing expertise no clinic has.

Solution and benefits. NeuroInsight runs these validated workflows on the clinician's own computer (macOS, Windows, or Linux) and returns reviewable results — no programming required. Benefits: fewer missed lesions, faster and more consistent reads, reproducibility across sites, and adoption without DevOps or cloud upload of protected health information. We are integrating the package into URMC's Patient Presurgical Conference, where surgical candidates are decided.

Differentiation. NeuroInsight's moat is the usability layer that delivers validated analysis to the point of care: one no-DevOps platform runs the whole epilepsy workup locally, covering the two most common surgically-treatable lesions — hippocampal sclerosis (AutoHS) and focal cortical dysplasia (MELD). AutoHS is also ownable IP: a histopathology-validated asymmetry method, not generic volumetry.

Competitive landscape. NeuroInsight builds on established research tools rather than competing with them — for example, it uses FreeSurfer — but those tools demand command-line expertise and do not ship as clinician-ready products. Reproducibility-focused environments such as Neurodesk make research pipelines portable and reproducible, but target researchers rather than clinical point-of-care use. A recent academic method (Belke et al., 2025) also automates HS detection; AutoHS uses a different method — a histopathology-validated hippocampal asymmetry index — and is delivered inside a turnkey, locally-run clinical platform. Commercial quantitative-imaging vendors (e.g., NeuroQuant, icometrix) focus on volumetry and atrophy and are not epilepsy-workflow or asymmetry-focused. NeuroInsight's combination of clinician-ready, local-first delivery with a histopathology-validated, HS-specific detector is, to our knowledge, unique.

Market potential. Primary customers are the ~250 NAEC-accredited Level 3/4 US epilepsy centers (256 in 2019), within NAEC's 325+ specialized-center membership, plus neuroradiology and imaging cores. Beyond the initial HS indication, the platform extends to additional epilepsy detectors and to structural, functional, and diffusion MRI across neuroscience.

---

### Proposed Research Plan (≤3500 characters)

> Briefly outline the goals and objectives for the proposed TDF project, as well as the amount of award requested ($100,000 maximum). Include a short list of budget items for which this funding will be used. Briefly outline your project timeline. Briefly describe the post-project plan. What is your strategy for post-project commercialization? Outline the estimated resources it might take to either obtain additional developmental funding or launch your product into the marketplace.

Goal. Mature NeuroInsight from a working pilot into a deployable, licensable clinical platform over 12 months — with AutoHS as the validated anchor — across four objectives:
1. Clinical validation — validate the platform's detectors (AutoHS and MELD) on independent, expert-labeled, multi-site datasets beyond our own studies, AutoHS first.
2. Platform productization — harden NeuroInsight for use outside our lab: workflow packaging, remote job monitoring, Windows signing, reliability, and an installable clinical configuration.
3. Pilot deployment — formalize the URMC anchor site by integrating the Epilepsy Workflow package into the Patient Presurgical Conference, then extend to 1–2 external epilepsy centers or imaging cores.
4. Market validation — complete NSF I-Corps and targeted market and competitive analysis, coordinated with the UR Ventures AutoHS licensing process.

Award requested: $80,000. Budget items:
- Technical/staff salary (developer/research staff for validation and hardening): $58,000
- Outsourcing/fee-for-service (I-Corps; market and competitive analysis; dataset access, de-identification, expert annotation): $16,000
- Supplies and small equipment, under $5,000 each (cloud/test compute, storage, pilot-site support): $6,000

Timeline.
- Q1: finalize validation datasets and protocol; begin platform hardening; start I-Corps.
- Q2: complete external-dataset validation analysis; package the AutoHS clinical configuration; go live with PRC integration at URMC.
- Q3: launch 1–2 external pilots; collect usage data and clinician feedback; complete market and competitive analysis.
- Q4: consolidate validation and pilot evidence; secure letter(s) of commercial interest; finalize the go-to-market and licensing package.

Post-project plan and commercialization. We will complete the AutoHS license with UR Ventures and use the validation and pilot evidence to scale through licensing to a clinical-imaging partner and/or a startup. Follow-on resources: federal non-dilutive funding (NIH/NSF SBIR/STTR, on the order of $0.3–2M across phases) to support clinical-grade validation and quality work, plus partner or seed capital for commercial deployment, sales, and support. Near-term needs include a small engineering and clinical-affairs team and multi-site validation agreements.

---

### Investigator and Other Information (≤1600 characters)

> List all principals involved and your collaborators. List all sources of current funding. List whether you require resources outside the university to achieve the proposed project goals (e.g. prototyping or service providers).

Principals and collaborators:
- Philbert Ndagijimana, Research Data Engineer (lead applicant) — architected and built the NeuroInsight platform and the AutoHS workflow.
- James Gugger, [title], [Department] (faculty sponsor / PI).
- Collaborators: URMC Department of Neurology epilepsy team and the Patient Presurgical Conference; [additional clinical/imaging collaborators — to confirm].

Current funding sources: None. There is no external or grant funding supporting this project at present; work to date has been carried out with internal/institutional effort.

Resources required outside the university: Yes — access to external/multi-site de-identified imaging datasets and expert annotation; cloud/test compute and storage; NSF I-Corps and market/competitive consulting; and code-signing/notarization services for distribution. No specialized wet-lab prototyping is required.

---

### References (1–5, ≤800 characters)

> List relevant references (up to 5) including the Invention Disclosure information.

1. Ndagijimana P, Brennan D, Shinohara RT, Gugger J. MRI-derived hippocampal asymmetry identifies hippocampal sclerosis in epilepsy surgical specimens. Brain Communications, 2026 (provisionally accepted).
2. Belke M, Zahnert F, Steinbrenner M, et al. Automatic detection of hippocampal sclerosis in patients with epilepsy. Epilepsia. 2025;66(10):3852–3864. doi:10.1111/epi.18514.
3. Fischl B. FreeSurfer. Neuroimage. 2012;62(2):774–781.
4. National Association of Epilepsy Centers. Find a Center (accredited epilepsy centers). https://naec-epilepsy.org/find-a-center (accessed 2026).
5. UR Ventures Invention Disclosure (AutoHS): [title and disclosure number — confirm with UR Ventures].
