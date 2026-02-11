/**
 * NeuroInsight Research - Main Application
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
 *  ├── Navigation (Header - Always Visible)
 *  │    └── Page Buttons: Home | Jobs | Dashboard | Viewer
 *  │
 *  └── Page Router (State-based, conditional rendering)
 *       ├── HomePage          - Landing, introduction
 *       ├── JobsPage          - Pipeline submission & quick monitoring
 *       ├── DashboardPage     - All jobs overview & results
 *       └── ViewerPage        - NIfTI visualization with segmentation
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
 *  ├── Navigation.tsx              # Header navigation bar
 *  ├── PipelineSelector.tsx        # Pipeline dropdown with metadata display
 *  ├── ResourceSelector.tsx        # CPU/Memory/GPU configuration
 *  ├── FileUpload.tsx              # Main upload wrapper (Dir/Single modes)
 *  ├── DirectorySelector.tsx       # Batch processing - select input/output dirs
 *  ├── SingleFileUpload.tsx        # Individual file upload
 *  ├── NiivueViewer.tsx            # Medical imaging viewer (PACS-like)
 *  └── icons/                      # 19 custom SVG icon components
 * 
 * services/
 *  └── api.ts                      # Backend API client (fetch wrapper)
 * 
 * types/
 *  └── index.ts                    # TypeScript interfaces (Job, Pipeline, etc.)
 * 
 * data/
 *  └── mockJobs.ts                 # Sample data for testing/demo
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
 * Backend URL: http://localhost:3003 (configured in vite.config.ts proxy)
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

import React, { useState } from 'react';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import JobsPage from './pages/JobsPage';
import DashboardPage from './pages/DashboardPage';
import ViewerPage from './pages/ViewerPage';
import DocsPage from './pages/DocsPage';

// Page type definition for type-safe navigation
type Page = 'home' | 'jobs' | 'dashboard' | 'viewer' | 'docs';

function App() {
  const [activePage, setActivePage] = useState<Page>('home');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation activePage={activePage} setActivePage={setActivePage} />

      {activePage === 'home' && <HomePage setActivePage={setActivePage} />}
      
      {activePage === 'jobs' && (
        <JobsPage 
          setActivePage={setActivePage} 
          setSelectedJobId={setSelectedJobId}
        />
      )}
      
      {activePage === 'dashboard' && (
        <DashboardPage 
          selectedJobId={selectedJobId}
          setSelectedJobId={setSelectedJobId}
          setActivePage={setActivePage}
        />
      )}

      {activePage === 'viewer' && (
        <ViewerPage 
          selectedJobId={selectedJobId}
          setSelectedJobId={setSelectedJobId}
        />
      )}

      {activePage === 'docs' && (
        <DocsPage setActivePage={setActivePage} />
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center text-sm text-gray-500">
            <p>NeuroInsight Research Platform - Version 0.1.0-alpha</p>
            <p className="mt-1">Built for the neuroimaging research community</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
