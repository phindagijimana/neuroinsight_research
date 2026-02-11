/**
 * ViewerPage Component
 * PACS-like viewer for NIfTI brain imaging with colored segmentation
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { getMockJobs } from '../data/mockJobs';
import type { Job } from '../types';
import NiivueViewer from '../components/NiivueViewer';
import JobSelector from '../components/JobSelector';
import FileBrowser from '../components/FileBrowser';
import Brain from '../components/icons/Brain';
import Eye from '../components/icons/Eye';
import Activity from '../components/icons/Activity';
import Download from '../components/icons/Download';
import RefreshCw from '../components/icons/RefreshCw';

interface ViewerPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
}

// Sample data configuration
const SAMPLE_DATA = {
  mri: '/sample_data/mni152.nii.gz',
  segmentation: '/sample_data/aal.nii.gz',
  description: 'MNI152 Template Brain with AAL Atlas Segmentation'
};

const ViewerPage: React.FC<ViewerPageProps> = ({ selectedJobId, setSelectedJobId }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [useSampleData, setUseSampleData] = useState(true);
  const [useMockData, setUseMockData] = useState(true);
  const [imageUrl, setImageUrl] = useState<string>(SAMPLE_DATA.mri);
  const [segmentationUrl, setSegmentationUrl] = useState<string>(SAMPLE_DATA.segmentation);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [showFileBrowser, setShowFileBrowser] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, [useMockData]);

  useEffect(() => {
    if (selectedJobId) {
      const selectedJob = jobs.find(j => j.id === selectedJobId);
      setJob(selectedJob || null);
      if (selectedJob && !useSampleData) {
        loadJobResults(selectedJobId);
      }
    } else {
      setJob(null);
    }
  }, [selectedJobId, jobs, useSampleData]);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      let jobsData;
      if (useMockData) {
        jobsData = await getMockJobs();
      } else {
        jobsData = await apiService.getJobs();
      }
      setJobs(jobsData);

      // Auto-select first completed job if none selected
      if (!selectedJobId) {
        const firstCompleted = jobsData.find(j => j.status === 'completed');
        if (firstCompleted) {
          setSelectedJobId(firstCompleted.id);
        }
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      if (!useMockData) {
        setUseMockData(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadJobResults = async (jobId: string) => {
    try {
      setLoading(true);
      
      // Load job metadata
      const jobData = await apiService.getJob(jobId);
      setJob(jobData);
      
      // Only load visualization if job is completed
      if (jobData.status !== 'completed') {
        setLoading(false);
        return;
      }
      
      // Try to load actual segmentation results
      try {
        const filesResponse = await fetch(`/api/results/${jobId}/files`);
        if (filesResponse.ok) {
          const files = await filesResponse.json();
          
          // Find volume and segmentation files
          const volumeFile = files.files?.find((f: any) => f.type === 'volume');
          const segFile = files.files?.find((f: any) => f.type === 'segmentation');
          
          if (volumeFile) {
            setImageUrl(volumeFile.path);
          }
          
          if (segFile) {
            setSegmentationUrl(segFile.path);
          }
        } else {
          // Fall back to sample data if results not available
          console.log('Job results not yet available, using sample data');
          handleLoadSampleData();
        }
      } catch (error) {
        console.log('Results API not available, using sample data:', error);
        handleLoadSampleData();
      }
    } catch (error) {
      console.error('Failed to load job:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSampleData = () => {
    setUseSampleData(true);
    setImageUrl(SAMPLE_DATA.mri);
    setSegmentationUrl(SAMPLE_DATA.segmentation);
    setSelectedJobId(null);
  };

  const handleFileSelect = (path: string) => {
    setSelectedFilePath(path);
    // TODO: Load the selected file in the viewer
    console.log('Loading file in viewer:', path);
    // For now, keep showing sample data
  };

  const completedJobs = jobs.filter(j => j.status === 'completed');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <Eye className="w-8 h-8 text-[#003d7a]" />
              <div>
                <h1 className="text-3xl font-bold text-gray-900">NIfTI Viewer</h1>
                <p className="text-gray-600">
                  PACS-like visualization with colored segmentation overlays
                </p>
              </div>
              {useMockData && (
                <span className="px-3 py-1 bg-navy-100 text-navy-800 text-sm font-medium rounded-full">
                  Demo Data
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={useMockData}
                  onChange={(e) => setUseMockData(e.target.checked)}
                  className="w-4 h-4 text-[#003d7a] rounded focus:ring-[#003d7a]"
                />
                Use Sample Data
              </label>
              <button
                onClick={handleLoadSampleData}
                className="px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
              >
                Load Sample Data
              </button>
              <button
                onClick={fetchJobs}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Job Selector */}
        {!loading && completedJobs.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <JobSelector
                  jobs={jobs}
                  selectedJobId={selectedJobId}
                  onJobSelect={(jobId) => {
                    setSelectedJobId(jobId);
                    setUseSampleData(false);
                    setShowFileBrowser(true);
                  }}
                  label="Select Job to View"
                />
              </div>
              {selectedJobId && (
                <button
                  onClick={() => setShowFileBrowser(!showFileBrowser)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
                >
                  {showFileBrowser ? 'Hide' : 'Show'} Files
                </button>
              )}
            </div>
          </div>
        )}

        {/* File Browser (when job selected) */}
        {!loading && selectedJobId && showFileBrowser && (
          <div className="mb-6 max-h-80 overflow-y-auto">
            <FileBrowser
              jobId={selectedJobId}
              onFileSelect={handleFileSelect}
              showDownload={true}
              showViewButton={true}
            />
          </div>
        )}

        {/* Job Info (if applicable) */}
        {job && !useSampleData && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-1">
                  Job: {job.id}
                </h2>
                <p className="text-gray-600">
                  {job.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'}: {job.pipeline_name}
                </p>
              </div>
              <div className={`px-4 py-2 rounded-full font-medium ${
                job.status === 'completed' 
                  ? 'bg-green-100 text-green-800'
                  : job.status === 'running'
                  ? 'bg-navy-100 text-navy-800'
                  : job.status === 'failed'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </div>
            </div>
            
            {/* Status-specific messages */}
            {job.status !== 'completed' && (
              <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  {job.status === 'running' && ' This job is still running. Results will be available when processing completes.'}
                  {job.status === 'pending' && ' This job is pending. Results will be available after processing.'}
                  {job.status === 'failed' && '[FAILED] This job failed. No results available.'}
                </p>
                <p className="text-sm text-yellow-700 mt-2">
                  Displaying sample data for demonstration.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div className="flex items-center justify-center gap-3">
              <Activity className="w-6 h-6 text-[#003d7a] animate-spin" />
              <span className="text-gray-600">Loading imaging data...</span>
            </div>
          </div>
        )}

        {/* Niivue Viewer */}
        {!loading && (imageUrl || useSampleData) && (
          <div className="space-y-6">
            <NiivueViewer
              imageUrl={imageUrl}
              segmentationUrl={segmentationUrl}
              onLoad={() => console.log('Volumes loaded successfully')}
            />

            {/* Segmentation Legend */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                AAL Atlas Regions (Sample)
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
                {[
                  { name: 'Precentral (L)', color: '#FF0000' },
                  { name: 'Frontal Superior (L)', color: '#FF4500' },
                  { name: 'Frontal Middle (L)', color: '#FFA500' },
                  { name: 'Frontal Inferior (L)', color: '#FFD700' },
                  { name: 'Temporal Superior (L)', color: '#00FF00' },
                  { name: 'Temporal Middle (L)', color: '#00CED1' },
                  { name: 'Parietal Superior (L)', color: '#4169E1' },
                  { name: 'Parietal Inferior (L)', color: '#9370DB' },
                  { name: 'Occipital Superior (L)', color: '#FF1493' },
                  { name: 'Hippocampus (L)', color: '#FF69B4' },
                  { name: 'Amygdala (L)', color: '#DC143C' },
                  { name: 'Caudate (L)', color: '#00BFFF' },
                ].map((region) => (
                  <div key={region.name} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
                    <div
                      className="w-4 h-4 rounded flex-shrink-0"
                      style={{ backgroundColor: region.color }}
                    />
                    <span className="text-gray-700 text-xs">{region.name}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-sm text-gray-600">
                <strong>Note:</strong> Colors are automatically assigned by the atlas.
                Use the opacity slider above to adjust segmentation visibility.
              </div>
            </div>

            {/* Download Section */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Export Options
              </h3>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => {/* Download NIfTI */}}
                  className="flex items-center gap-2 px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
                >
                  <Download className="w-4 h-4" />
                  Download Volume
                </button>
                <button
                  onClick={() => {/* Download Segmentation */}}
                  className="flex items-center gap-2 px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
                >
                  <Download className="w-4 h-4" />
                  Download Segmentation
                </button>
                <button
                  onClick={() => {/* Export to DICOM */}}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
                >
                  Export to DICOM
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Empty State - No Completed Jobs */}
        {!loading && completedJobs.length === 0 && !useSampleData && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <Brain className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No Completed Jobs Yet
            </h3>
            <p className="text-gray-600 mb-6">
              Load sample data or complete a processing job first
            </p>
            <button
              onClick={handleLoadSampleData}
              className="px-6 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
            >
              Load Sample Data
            </button>
          </div>
        )}

        {/* Orientation and color coding legend at bottom */}
        <div className="mt-8 py-4 px-4 bg-[#003d7a]/10 border border-[#003d7a]/20 rounded-lg text-center text-sm text-gray-700">
          <span className="font-medium text-[#003d7a]">L/R</span> markers indicate patient orientation (radiological view).
          <span className="mx-2">|</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#0064ff]" title="Left hippocampus" aria-hidden />
            Blue = left hippocampus
          </span>
          <span className="mx-2">|</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#ff3232]" title="Right hippocampus" aria-hidden />
            Red = right hippocampus
          </span>
        </div>
      </div>
    </div>
  );
};

export default ViewerPage;
