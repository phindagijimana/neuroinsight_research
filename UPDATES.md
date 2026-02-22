# NeuroInsight_Research.md Updates

## Document Version: 2.0 (February 7, 2026)

### Major Updates Based on Team Discussion

---

## What Changed

### 1. **Clarified Two Deployment Modes**

**Before:** Vague about "runtime modes"

**After:** Clear distinction between:
- **Mode 1: Local/Desktop** (Phases 1-3, months 1-9)
  - Fully local processing (Docker)
  - Remote HPC access (via SSH, no partnership required)
- **Mode 2: HPC-Native** (Phase 4, months 10-12)
  - Open OnDemand deployment
  - Runs directly on HPC

### 2. **Added Development Strategy Section**

New Section 5 explains phased approach:
- **Phase 1:** Local web platform (CURRENT - Months 1-3)
- **Phase 2:** HPC backend integration (Months 4-6)
- **Phase 3:** Desktop application (Months 7-9)
- **Phase 4:** HPC-Native/OOD deployment (Months 10-12)

**Key insight:** Start with local development, add HPC incrementally

### 3. **Emphasized Data Stays on HPC**

Added clear explanation:
- No bulk data upload/download in HPC mode
- Data remains on HPC filesystem throughout processing
- Only metadata and visualization slices transferred
- Respects institutional data governance

### 4. **Added Core Features Table**

New Section 4.2 shows feature parity across modes:
- Upload, Browse, Submit, Monitor, Visualize, Download
- Clear which features apply to which mode
- Clarifies when upload is needed (local) vs. not needed (HPC)

### 5. **Clarified "No Partnership Required"**

**Critical update:** Desktop app connecting to HPC does NOT require institutional partnerships
- Users bring their own HPC credentials (ssh-agent)
- App operates within user's existing permissions
- Like "Outlook for HPC" - client app, not hosted service
- Removes major adoption barrier

### 6. **Added Execution Backend Abstraction Explanation**

New Section 6.1 explains the abstraction layer:
- Same code works with Docker (local) or SLURM (HPC)
- Switch via configuration: `BACKEND_TYPE=local` or `BACKEND_TYPE=slurm`
- Enables rapid local development, seamless HPC deployment

### 7. **Reorganized Data Flow Section**

Split into three subsections:
- Local mode data flow (with upload)
- HPC mode data flow (no upload, data stays on HPC)
- NIfTI-based pipeline approach

### 8. **Updated Roadmap with Detailed Milestones**

New Section 14 shows:
- Checkboxes for completed items (✅)
- Specific deliverables for each phase
- Clear progression from local → HPC → desktop → OOD
- Current status: Phase 1 in progress

### 9. **Enhanced Security Section**

Expanded Section 11 to cover:
- Authentication for all three modes (local, desktop remote, OOD)
- Emphasis on user credentials (no app credentials)
- PHI compliance considerations
- Data security guarantees

### 10. **Updated Competitive Positioning**

Enhanced comparison table (Section 13):
- Added "Desktop App" and "Data on HPC" columns
- Clear differentiators highlighted
- Added FSL-GUI for reference
- Explains unique advantages

### 11. **Improved Summary Section**

New Section 15 includes:
- Key advantages listed with checkmarks
- Current project status (Phase 1 in progress)
- Strategic path (4-phase approach)
- Distinction from existing NeuroInsight (HS detection tool)

---

## Key Message Changes

| Aspect | Old Message | New Message |
|--------|-------------|-------------|
| **When to build** | Unclear timeline | Start local (Months 1-3), add HPC later |
| **HPC access** | Implied partnership needed | No partnership required - users bring own access |
| **Data location** | Ambiguous | Explicitly stays on HPC (no upload) |
| **Development** | Start on HPC? | Start locally with Docker, test fast |
| **Deployment** | Focused on OOD | Two modes: Desktop + OOD |

---

## Why These Changes Matter

### For Developers:
- ✅ Clear what to build first (local platform)
- ✅ Understand the abstraction layer
- ✅ Know they can develop without HPC access

### For Investors:
- ✅ Realistic timeline (12 months to full platform)
- ✅ No institutional partnerships blocking MVP
- ✅ Clear go-to-market strategy

### For Users:
- ✅ Works locally for small-scale use
- ✅ Can connect to their own HPC (no IT approval needed)
- ✅ Data never leaves their control

### For HPC Administrators:
- ✅ Understand security model (user credentials only)
- ✅ See optional OOD integration path
- ✅ Recognize it's just an SSH client (from their perspective)

---

## Document Structure

### Sections Added:
- Section 4.2: Core Features (All Modes)
- Section 4.3: Key Design Principle (Data Stays on HPC)
- Section 5: Development Strategy
- Section 6.1: Execution Backend Abstraction
- Section 8.3: Production-Ready Pipelines
- Section 10.2: Metrics & QC Visualization

### Sections Renumbered:
- Old Section 5 → New Section 6
- Old Section 6 → New Section 7
- Old Section 7 → New Section 8
- And so on...

### Sections Enhanced:
- Section 4.1: Deployment Modes (clearer distinction)
- Section 11: Security Model (all modes covered)
- Section 13: Competitive Positioning (better comparison)
- Section 14: Roadmap (specific milestones, current progress)
- Section 15: Summary (key advantages, current status)

---

## Next Steps for Documentation

### Short-term (Week 1-2):
- [ ] Add API specification (OpenAPI/Swagger)
- [ ] Create user onboarding guide
- [ ] Document pipeline YAML schema

### Medium-term (Month 1-3):
- [ ] Write developer setup guide
- [ ] Create architecture decision records (ADRs)
- [ ] Document testing strategy

### Long-term (Month 4+):
- [ ] HPC administrator guide
- [ ] Desktop app user manual
- [ ] OOD deployment guide

---

## Feedback Incorporated

Based on conversation with team:
1. ✅ Clarified two versions: Local/Desktop + HPC-Native
2. ✅ Confirmed development strategy: local first
3. ✅ Explained abstraction layer concept
4. ✅ Emphasized data stays on HPC
5. ✅ Removed partnership requirement for desktop HPC access
6. ✅ Listed core features across all modes
7. ✅ Updated roadmap to match phased approach
8. ✅ Made document more concise overall

---

**Document is now aligned with implementation strategy and realistic about timeline and dependencies.**
