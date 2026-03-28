# Viewer roadmap & deferred visualizations (`viewer_later.md`)

This note records **what belongs on the default Viewer page** versus **optional / later result types**, and what epoch, ERP, and spectral views would actually do if added later.

**UI naming in the app:** **Signal View**, **Imaging View** (brain / MRI / overlays / source maps in Niivue), **Multimodal View** (signal + imaging together). Below, “Brain” means the same role as Imaging View unless stated otherwise.

---

## Short answer

**No — you do not need all of those on the Viewer page.**

For the Viewer page described here, epoch browsers, ERP plots, and spectrogram/PSD panels are better treated as **optional result types**, not **default requirements**.

---

## What the Viewer page really needs

The Viewer should focus on:

| Mode | Role |
|------|------|
| **Imaging View** | MRI, overlays, source maps (Niivue) |
| **Signal View** | Continuous waveform browsing |
| **Multimodal View** | Signal + brain together (linked when a multimodal bundle exists) |

That is enough for the **main experience**.

---

## What to keep off the default Viewer page

### 1. Epoch / epoched visualization

**You do not need this by default.**

**Why:**

- It is useful mainly for **ERP / cognitive** workflows.
- It adds **complexity fast**.
- It is **not essential** for an **epilepsy-first MVP**.

**When you would need it:**

- If a workflow **explicitly outputs epochs**.
- If the user opened an **ERP-related** or **epoch** result (explicit intent).

**Best place:**

- Optional expansion **inside Signal View**, or  
- A **dedicated result subtype** later (not the default tab).

---

### 2. ERP waveforms

**You do not need this now.**

**Why:**

- ERP matters for **cognitive / event-related** workflows.
- It is **not essential** for an **epilepsy + source-localization** starting point.

**When you would need it:**

- N400, P300, **task EEG** workflows.
- **Averaged event-related** studies.

**Best place:**

- Later, under a separate **ERP result mode**.  
- **Not** in the main Viewer MVP.

---

### 3. Spectrogram / PSD panel

**You do not need this on the default Viewer page either.**

**Why:**

- Useful for **bandpower**, **sleep**, **resting-state**, **QA**.
- It becomes **another analytics surface**; easy to clutter the Viewer if “Analytics” is intentionally kept light here.

**When you would need it:**

- If a workflow is **specifically spectral**.
- If a user opened a **PSD / spectrogram** result from the **dashboard / job** page.

**Best place:**

- **Dashboard / job results**, or  
- An **optional advanced result drawer** later.

---

## What you actually need now (Viewer MVP)

For the **current** Viewer MVP:

| Imaging View | MRI / overlay / source map (Niivue) |
|--------------|-------------------------------------|
| **Signal View** | Waveform browser; room later for **spike / event markers** (when data supports it) |
| **Multimodal View** | Signal + brain together (sync when bundle + API support it) |

That is the **essential set**.

---

## Simple rule

Only add a visualization type to the **default** Viewer if it is:

1. **Central** to the workflow’s main output,  
2. **Needed for interpretation**, and  
3. **Likely to be used frequently**.

**By that rule:**

| Type | Default Viewer? |
|------|-----------------|
| Signal traces | Yes |
| Brain / source overlays (Imaging View) | Yes |
| Multimodal sync | Yes |
| Epochs | Later |
| ERP | Later |
| PSD / spectrogram | Later or elsewhere |

---

## Best recommendation (product)

For now, keep the Viewer page to:

- **Imaging View**  
- **Signal View**  
- **Multimodal View**  

Then allow **future workflow-specific extensions**:

- ERP mode  
- Epoch mode  
- Spectral mode  

—but **only when those workflows are actually in use** and the user has chosen a result that needs them.

**Bottom line:** You do **not** need epoch, ERP, and spectral panels on the default Viewer for it to work well. For current NIR direction, they would **mostly add clutter** unless tied to explicit outputs and user intent.

---

## Would adding epochs, ERP, or PSD be *very* helpful?

**It depends on what plugins/workflows emit and who the user is.**

- If most jobs only produce **continuous raw / preprocessed EEG** and **volumes**, then **Signal View + Imaging View + Multimodal View** already match how people **look** at those outputs. Extra panels are **nice-to-have**, not urgent.

- If you ship (or plan) **event-related**, **trial-based**, or **frequency** products (epochs, ERPs, PSD/TFR files), then **yes** — without dedicated views, users fall back to **downloading files** or **Dashboard tables**, which is slower and easier to misinterpret.

**Summary:** **Very helpful** when standardized outputs include those datatypes; **moderately helpful** for onboarding/demos; **low value** if you rarely generate those artifacts.

---

## What each optional type does (plain terms)

### 1. Epoch / epoched visualization

- **What it is:** EEG cut into **short segments locked to events** (e.g. stimulus at *t = 0*, baseline before, response after).
- **What it shows:** **Trial × channel × time** — stacked traces or heatmaps across trials.
- **Why it helps:** **Single-trial noise, artifacts, dropout** — the bridge between continuous data and averaged ERPs.
- **Minimal version:** Pick an epoch file + event type + “show trial *k*” or a butterfly of all trials for one channel.

### 2. ERP waveforms

- **What it is:** **Average** (or condition average) of epochs **time-locked** to the same event.
- **What it shows:** **Voltage vs time** (per channel or ROI), often with **confidence bands** or multiple conditions.
- **Why it helps:** Standard way cognitive/clinical EEG is **summarized** — peaks (e.g. N100, P300) and condition differences.
- **Minimal version:** One plot: time on X, µV on Y, a few channels or small multiples + legend.

### 3. Spectrogram / PSD

- **PSD (power spectral density):** **How much power** at each **frequency** (e.g. 1–40 Hz), for a **chosen window** or average.
- **Spectrogram:** **Power vs time and frequency** (heatmap).
- **Why it helps:** **Resting bands**, **sleep**, **artifact check** (line noise, muscle), **induced** oscillations.
- **Minimal version:** **PSD** for the visible Signal View window; spectrogram only if you **precompute TFR** or accept heavier client work.

---

## How this fits a minimal Viewer

| Priority | Idea |
|----------|------|
| **High leverage, small surface** | PSD for the **current preview window** (quick “is this sensible?”) — still optional, not default. |
| **Next** (event-based plugins) | **ERP** from **precomputed** files (JSON/CSV); Viewer only **plots**. |
| **Heaviest** | **Epoch browser** — defer until **trial-level QC** is a core promise. |

When you standardize concrete outputs (e.g. `epochs.fif`, `evoked`, `psd.json`, PNG-only reports), **re-rank** these three for the repo based on real file types, not generically.
