/**
 * NeuroInsight - Main Application
 * 
 * FRONTEND ARCHITECTURE OVERVIEW
 * =============================
 * 
 * This React application provides a medical-grade UI for HPC-native
 * neuroimaging pipeline execution and visualization.
 * 
 * COMPONENT HIERARCHY
 * -------------------
 * 
 * App (Root)
 *  |-- Navigation (Header - Always Visible)
 *  |    \-- Page Buttons: Home | Jobs | Dashboard | Viewer
 *  |
 *  \-- Page Router (State-based, conditional rendering)
 *       |-- HomePage          - Landing, introduction
 *       |-- JobsPage          - Pipeline submission & quick monitoring
 *       |-- DashboardPage     - All jobs overview & results
 *       \-- ViewerPage        - NIfTI visualization with segmentation
 * 
 * STATE MANAGEMENT
 * ----------------
 * 
 * App-Level State:
 *  - activePage: Current page to display ('home' | 'jobs' | 'dashboard' | 'viewer')
 *  - selectedJobId: Job ID for Dashboard/Viewer context (null = no selection)
 * 
 * Component State:
 *  - Each page manages its own UI state (forms, filters, etc.)
 *  - Shared state passed via props (no Redux/Context needed for MVP)
 * 
 * DATA FLOW
 * ---------
 * 
 * User Actions -> Component State Update -> API Call (services/api.ts) ->
 * Backend Response -> State Update -> UI Re-render
 * 
 * Example: Job Submission Flow
 *  1. User fills form in JobsPage
 *  2. JobsPage calls apiService.submitJob()
 *  3. API POST to /api/jobs/submit
 *  4. Backend creates job, returns job_id
 *  5. JobsPage updates state, shows success
 *  6. Navigate to Dashboard to see job
 * 
 * Example: Visualization Flow
 *  1. User clicks "View Results" in Dashboard
 *  2. Dashboard sets selectedJobId and activePage='viewer'
 *  3. ViewerPage loads job metadata
 *  4. ViewerPage fetches NIfTI files from /api/results/{id}
 *  5. NiivueViewer component renders brain + segmentation
 * 
 * PAGES & RESPONSIBILITIES
 * ------------------------
 * 
 * HomePage:
 *  - Purpose: Landing page, feature highlights, onboarding
 *  - Components: Hero, feature cards, "Get Started" button
 *  - Navigation: -> Jobs (via button click)
 * 
 * JobsPage:
 *  - Purpose: Submit new processing jobs
 *  - Components: PipelineSelector, ResourceSelector, FileUpload, DirectorySelector
 *  - Features: Pipeline selection, parameter config, resource customization,
 *              directory-based batch processing, single file upload
 *  - Navigation: -> Dashboard (after submission)
 * 
 * DashboardPage:
 *  - Purpose: Monitor ALL jobs, view results overview
 *  - Components: Statistics cards, job tables (completed/active/failed)
 *  - Features: Real-time status updates, "View Results" button per job
 *  - Navigation: -> Viewer (via "View Results" button)
 * 
 * ViewerPage:
 *  - Purpose: Visualize NIfTI brain imaging with colored segmentation
 *  - Components: NiivueViewer, job info card, controls
 *  - Features: Multi-planar PACS view, segmentation overlays, opacity control,
 *              crosshair navigation, screenshot export
 *  - Data: Loads anatomy.nii.gz + segmentation.nii.gz for selected job
 * 
 * COMPONENT STRUCTURE
 * -------------------
 * 
 * components/
 *  |-- Navigation.tsx              # Header navigation bar
 *  |-- PipelineSelector.tsx        # Pipeline dropdown with metadata display
 *  |-- ResourceSelector.tsx        # CPU/Memory/GPU configuration
 *  |-- FileUpload.tsx              # Main upload wrapper (Dir/Single modes)
 *  |-- DirectorySelector.tsx       # Batch processing - select input/output dirs
 *  |-- SingleFileUpload.tsx        # Individual file upload
 *  |-- NiivueViewer.tsx            # Medical imaging viewer (PACS-like)
 *  \-- icons/                      # 19 custom SVG icon components
 * 
 * services/
 *  \-- api.ts                      # Backend API client (fetch wrapper)
 * 
 * types/
 *  \-- index.ts                    # TypeScript interfaces (Job, Pipeline, etc.)
 * 
 * data/
 *  \-- mockJobs.ts                 # Sample data for testing/demo
 * 
 * STYLING APPROACH
 * ----------------
 * 
 * Framework: Tailwind CSS (utility-first)
 * Theme: Medical professional (navy blue #003d7a, no emojis)
 * Colors:
 *  - Primary: Navy Blue #003d7a (buttons, active states)
 *  - Success: Green #10b981 (completed jobs)
 *  - Warning: Yellow #f59e0b (pending jobs)
 *  - Error: Red #ef4444 (failed jobs)
 *  - Running: Navy Blue #003d7a (active jobs)
 * 
 * Responsive: Desktop-first, functional on tablets, view-only on mobile
 * 
 * API INTEGRATION
 * ---------------
 * 
 * Backend URL: http://localhost:3000 (production), http://localhost:3001 (development proxy)
 * 
 * Key Endpoints:
 *  - GET  /api/pipelines           -> List available pipelines
 *  - POST /api/jobs/submit         -> Submit single job
 *  - POST /api/jobs/submit-batch   -> Submit batch job (directory)
 *  - GET  /api/jobs                -> List all jobs
 *  - GET  /api/jobs/{id}           -> Get job details
 *  - GET  /api/jobs/{id}/logs      -> Get job logs
 *  - GET  /api/results/{id}/files  -> List result files
 *  - GET  /api/results/{id}/volume -> Get brain MRI
 *  - GET  /api/results/{id}/segmentation -> Get segmentation overlay
 * 
 * Error Handling:
 *  - API errors displayed as toast notifications (future enhancement)
 *  - Network errors show fallback to sample data
 *  - Invalid inputs prevented by TypeScript + form validation
 * 
 * VISUALIZATION SYSTEM
 * --------------------
 * 
 * Library: Niivue (WebGL-based NIfTI viewer)
 * Format Support:
 *  - NIfTI (.nii, .nii.gz) - Neuroimaging standard
 *  - Integer label maps (ITK-SNAP compatible)
 *  - Colored segmentation overlays
 * 
 * View Modes:
 *  - Axial (horizontal slices)
 *  - Coronal (front-to-back slices)
 *  - Sagittal (left-to-right slices)
 *  - 3D render (volume rendering)
 *  - Multi-planar (4-view PACS layout) <- Default
 *  - Mosaic (grid of slices)
 * 
 * Interactions:
 *  - Left drag: Pan image
 *  - Right drag: Window/level (brightness/contrast)
 *  - Scroll: Zoom in/out
 *  - Shift+click: Move crosshair
 *  - Ctrl+click: Measure distance
 * 
 * Features:
 *  - Opacity slider (0-100%) for segmentation
 *  - Multiple colormaps (gray, jet, hot, plasma, viridis)
 *  - Crosshair toggle
 *  - Screenshot export
 *  - Sample data (MNI152 + AAL atlas)
 * 
 * PERFORMANCE CONSIDERATIONS
 * --------------------------
 * 
 * - NIfTI files streamed from backend (not fully loaded in memory)
 * - WebGL rendering for smooth 60fps visualization
 * - Lazy loading: Viewer only loads when needed
 * - Sample data preloaded in public/ directory
 * - React.StrictMode disabled for production build
 * 
 * TESTING STRATEGY
 * ----------------
 * 
 * Current: Manual testing with sample data
 * Future:
 *  - Unit tests (Jest + React Testing Library)
 *  - Integration tests (Playwright/Cypress)
 *  - E2E tests for critical flows
 * 
 * VERSION: 0.1.0-alpha (MVP)
 * BUILD: Vite 5.4+ (fast dev server, optimized production build)
 * TYPESCRIPT: 5.0+ (strict mode enabled)
 * REACT: 18.2+ (concurrent features)
 */

import { useState, useEffect, lazy, Suspense, type DragEvent } from 'react';
import Navigation from './components/Navigation';
import {
  clearViewerQueryParam,
  setViewerQueryParam,
  shouldOpenViewerFromUrl,
  type ViewerTab,
} from './utils/viewerQuery';

// Page type definition for type-safe navigation -- exported for child components
export type Page = 'home' | 'jobs' | 'dashboard' | 'viewer' | 'transfer' | 'docs';

// Code-split pages with React.lazy for smaller initial bundle
const HomePage = lazy(() => import('./pages/HomePage'));
const JobsPage = lazy(() => import('./pages/JobsPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ViewerPage = lazy(() => import('./pages/ViewerPage'));
const TransferPage = lazy(() => import('./pages/TransferPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));

type NavigateOptions = { viewerTab?: ViewerTab };

function App() {
  const [activePage, setActivePage] = useState<Page>(() => {
    if (typeof window === 'undefined') return 'home';
    return shouldOpenViewerFromUrl(window.location.search) ? 'viewer' : 'home';
  });
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  /** Bumps when navigating to Viewer so the page re-reads `?viewer=` (e.g. header while already on Viewer). */
  const [viewerNavEpoch, setViewerNavEpoch] = useState(0);
  /** A locally-opened imaging volume (drag-and-drop / file picker), viewed without upload. */
  const [localVolume, setLocalVolume] = useState<{ url: string; name: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  /** Updates URL `?viewer=` when entering/leaving the Viewer page (deep links). */
  const navigateTo = (page: string, opts?: NavigateOptions) => {
    const p = page as Page;
    if (p !== 'viewer') {
      clearViewerQueryParam();
    } else {
      setViewerQueryParam(opts?.viewerTab ?? 'imaging');
      setViewerNavEpoch((e) => e + 1);
    }
    setActivePage(p);
  };

  /** Open a local NIfTI/MGZ volume in the Viewer (no upload — data stays in place). */
  const isVolumeFile = (name: string) => /\.(nii(\.gz)?|mgz|mgh)$/i.test(name);
  const openLocalVolume = (file: File) => {
    if (!file) return;
    if (localVolume?.url) URL.revokeObjectURL(localVolume.url);
    const url = URL.createObjectURL(file);
    setLocalVolume({ url, name: file.name });
    navigateTo('viewer', { viewerTab: 'imaging' });
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = Array.from(e.dataTransfer?.files || []).find((f) => isVolumeFile(f.name));
    if (file) openLocalVolume(file);
  };
  const handleDragOver = (e: DragEvent) => {
    if (e.dataTransfer?.types?.includes('Files')) {
      e.preventDefault();
      setIsDragging(true);
    }
  };
  const handleDragLeave = (e: DragEvent) => {
    if (!e.relatedTarget) setIsDragging(false); // left the window
  };

  // Desktop shell: native "Open Data" (File > Open Data… / Cmd+O) pushes volume
  // bytes here; rebuild a File and open it in the Viewer.
  useEffect(() => {
    const desktop = (window as unknown as { nir?: { onOpenVolume?: (cb: (p: { name: string; data: ArrayBuffer | Uint8Array }) => void) => () => void } }).nir;
    if (!desktop?.onOpenVolume) return;
    const off = desktop.onOpenVolume(({ name, data }) => {
      try {
        const buf: ArrayBuffer =
          data instanceof Uint8Array
            ? (data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) as ArrayBuffer)
            : data;
        openLocalVolume(new File([buf], name));
      } catch {
        /* ignore malformed payloads */
      }
    });
    return off;
    // openLocalVolume only uses setState (stable); subscribe once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="min-h-screen bg-gray-50"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="fixed inset-0 z-50 bg-navy-600/70 flex items-center justify-center pointer-events-none">
          <div className="bg-white rounded-2xl px-10 py-8 text-center shadow-2xl border-2 border-dashed border-navy-600">
            <p className="text-2xl font-bold text-navy-600 mb-1">Drop to view</p>
            <p className="text-gray-600">Release a NIfTI (.nii/.nii.gz) or MGZ file to open it in the Viewer</p>
          </div>
        </div>
      )}
      <Navigation activePage={activePage} setActivePage={navigateTo} />

      <Suspense fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-gray-500 text-lg">Loading...</div>
        </div>
      }>
        {activePage === 'home' && <HomePage setActivePage={navigateTo} setSelectedJobId={setSelectedJobId} onOpenLocal={openLocalVolume} />}
        
        {activePage === 'jobs' && (
          <JobsPage 
            setActivePage={navigateTo} 
            setSelectedJobId={setSelectedJobId}
          />
        )}
        
        {activePage === 'dashboard' && (
          <DashboardPage 
            selectedJobId={selectedJobId}
            setSelectedJobId={setSelectedJobId}
            setActivePage={navigateTo}
          />
        )}

        {activePage === 'viewer' && (
          <ViewerPage
            selectedJobId={selectedJobId}
            setSelectedJobId={setSelectedJobId}
            viewerNavEpoch={viewerNavEpoch}
            localVolume={localVolume}
          />
        )}

        {activePage === 'transfer' && (
          <TransferPage />
        )}

        {activePage === 'docs' && (
          <DocsPage setActivePage={navigateTo} />
        )}
      </Suspense>
    </div>
  );
}

export default App;
