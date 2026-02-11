/**
 * PipelineSelector Component
 * 
 * Allows users to select plugins (single tools) or workflows (plugin chains)
 */

import React, { useState, useEffect } from 'react';
import { Loader2, Info, Zap, GitBranch, CheckCircle, AlertTriangle } from 'lucide-react';
import { apiService } from '../services/api';
import type { Pipeline } from '../types';

interface PipelineSelectorProps {
  onPipelineSelect: (pipeline: Pipeline | null) => void;
  selectedPipeline: Pipeline | null;
  onExecutionSelect?: (execution: { type: 'plugin' | 'workflow'; id: string; name: string } | null) => void;
}

type SelectionMode = 'plugins' | 'workflows';

interface Plugin {
  id: string;
  name: string;
  version: string;
  container: string;
  description: string;
  category: 'structural' | 'functional' | 'diffusion' | 'conversion' | 'epilepsy';
  user_selectable?: boolean; // If false, plugin is hidden from UI (utility plugins)
}

interface Workflow {
  id: string;
  name: string;
  version: string;
  description: string;
  plugins: string[]; // Plugin IDs in order
  category: 'structural' | 'functional' | 'diffusion' | 'conversion' | 'epilepsy';
}

// Mock plugins data
const MOCK_PLUGINS: Plugin[] = [
  {
    id: 'dcm2niix',
    name: 'DICOM to NIfTI Converter',
    version: '1.0.0',
    container: 'nipy/heudiconv:latest',
    description: 'Convert DICOM images to NIfTI format with JSON sidecars',
    category: 'conversion'
  },
  {
    id: 'freesurfer_recon',
    name: 'FreeSurfer recon-all',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: 'Full cortical reconstruction and subcortical segmentation',
    category: 'structural'
  },
  {
    id: 'fastsurfer',
    name: 'FastSurfer',
    version: '2.0.0',
    container: 'deepmi/fastsurfer:latest',
    description: 'Fast deep learning-based cortical parcellation (FreeSurfer-compatible)',
    category: 'structural'
  },
  {
    id: 'segmentha_t1',
    name: 'FreeSurfer SegmentHA_T1',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: 'Segment hippocampal subfields and amygdala nuclei from T1',
    category: 'structural'
  },
  {
    id: 'segmentha_t2',
    name: 'FreeSurfer SegmentHA_T2',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: 'Enhanced hippocampal subfields using high-res T2',
    category: 'structural'
  },
  {
    id: 'fmriprep',
    name: 'fMRIPrep',
    version: '23.2.1',
    container: 'nipreps/fmriprep:23.2.1',
    description: 'Preprocessing of fMRI data (motion correction, distortion correction, coregistration)',
    category: 'functional'
  },
  {
    id: 'xcpd',
    name: 'XCP-D',
    version: '0.6.1',
    container: 'pennlinc/xcp_d:0.6.1',
    description: 'Postprocessing of fMRI: denoising, parcellation, connectivity matrices',
    category: 'functional'
  },
  {
    id: 'qsiprep',
    name: 'QSIPrep',
    version: '0.20.0',
    container: 'pennbbl/qsiprep:0.20.0',
    description: 'Preprocessing of diffusion MRI (distortion, motion, coregistration)',
    category: 'diffusion'
  },
  {
    id: 'qsirecon',
    name: 'QSIRecon',
    version: '0.20.0',
    container: 'pennbbl/qsirecon:0.20.0',
    description: 'Diffusion reconstruction, tractography, and connectomes',
    category: 'diffusion'
  },
  {
    id: 'meld_graph',
    name: 'MELD Graph',
    version: '1.0.0',
    container: 'meldproject/meld_graph:latest',
    description: 'Cortical dysplasia detection for epilepsy research',
    category: 'epilepsy'
  },
  {
    id: 'freesurfer_longitudinal',
    name: 'FreeSurfer Longitudinal',
    version: '1.0.0',
    container: 'freesurfer/freesurfer:7.4.1',
    description: 'Full FreeSurfer longitudinal stream (CROSS -> BASE -> LONG) for ≥2 timepoints',
    category: 'structural',
    user_selectable: true
  },
  {
    id: 'freesurfer_longitudinal_stats',
    name: 'FreeSurfer Longitudinal Stats Utility',
    version: '1.0.0',
    container: 'freesurfer/freesurfer:7.4.1',
    description: 'Utility plugin for post-processing FreeSurfer longitudinal outputs (QDEC tables, slopes)',
    category: 'structural',
    user_selectable: false // Hidden from UI - only called by workflows
  },
];

// Mock workflows data
const MOCK_WORKFLOWS: Workflow[] = [
  {
    id: 'dicom_ingestion',
    name: 'DICOM Ingestion',
    version: '1.0.0',
    description: 'Convert DICOM images to NIfTI format',
    plugins: ['dcm2niix'],
    category: 'conversion'
  },
  {
    id: 'structural_segmentation',
    name: 'FastSurfer Segmentation and Volumetry',
    version: '1.0.0',
    description: 'Full cortical and subcortical segmentation with volumetry',
    plugins: ['fastsurfer'],
    category: 'structural'
  },
  {
    id: 'hippocampal_subfields_t1',
    name: 'Hippocampal Subfields Segmentation T1',
    version: '1.0.0',
    description: 'Segment hippocampal subfields and amygdala nuclei from T1',
    plugins: ['freesurfer_recon', 'segmentha_t1'],
    category: 'structural'
  },
  {
    id: 'hippocampal_subfields_t2',
    name: 'Hippocampal Subfields Segmentation T1 + T2',
    version: '1.0.0',
    description: 'Enhanced hippocampal subfield segmentation with high-res T2',
    plugins: ['freesurfer_recon', 'segmentha_t2'],
    category: 'structural'
  },
  {
    id: 'fmri_preprocess',
    name: 'fMRI Preprocessing',
    version: '1.0.0',
    description: 'Preprocess functional MRI data',
    plugins: ['fmriprep'],
    category: 'functional'
  },
  {
    id: 'fmri_full',
    name: 'fMRI Full Pipeline',
    version: '1.0.0',
    description: 'Complete fMRI pipeline: preprocessing + connectivity analysis',
    plugins: ['fmriprep', 'xcpd'],
    category: 'functional'
  },
  {
    id: 'diffusion_preprocess',
    name: 'Diffusion Preprocessing',
    version: '1.0.0',
    description: 'Preprocess diffusion MRI data',
    plugins: ['qsiprep'],
    category: 'diffusion'
  },
  {
    id: 'diffusion_full',
    name: 'Diffusion Full Pipeline',
    version: '1.0.0',
    description: 'Complete diffusion pipeline: preprocessing + tractography',
    plugins: ['qsiprep', 'qsirecon'],
    category: 'diffusion'
  },
  {
    id: 'cortical_lesion_detection',
    name: 'Cortical Lesion Detection',
    version: '1.0.0',
    description: 'Detect cortical dysplasia for epilepsy research',
    plugins: ['freesurfer_recon', 'meld_graph'],
    category: 'epilepsy'
  },
  {
    id: 'freesurfer_longitudinal_v1',
    name: 'FreeSurfer Longitudinal Processing',
    version: '1.0.0',
    description: 'FreeSurfer longitudinal processing (CROSS -> BASE -> LONG) for ≥2 timepoints',
    plugins: ['freesurfer_longitudinal'],
    category: 'structural'
  },
  {
    id: 'freesurfer_longitudinal_postprocess_v1',
    name: 'FreeSurfer Longitudinal Post-processing',
    version: '1.0.0',
    description: 'Generate QDEC tables and slopes from existing FreeSurfer longitudinal outputs',
    plugins: ['freesurfer_longitudinal_stats'],
    category: 'structural'
  },
];

const getCategoryLabel = (category: string) => {
  switch (category) {
    case 'structural': return 'Structural';
    case 'functional': return 'Functional';
    case 'diffusion': return 'Diffusion';
    case 'conversion': return 'Conversion';
    case 'epilepsy': return 'Epilepsy';
    default: return category;
  }
};

export const PipelineSelector: React.FC<PipelineSelectorProps> = ({
  onPipelineSelect,
  selectedPipeline,
  onExecutionSelect,
}) => {
  const [mode, setMode] = useState<SelectionMode>('workflows');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [usingLiveData, setUsingLiveData] = useState(false);
  
  // Live data from API (or fallback to mock)
  const [livePlugins, setLivePlugins] = useState<Plugin[]>([]);
  const [liveWorkflows, setLiveWorkflows] = useState<Workflow[]>([]);
  const [licenseStatus, setLicenseStatus] = useState<{ found: boolean; path: string | null; hint: string } | null>(null);

  // Decide which data source to use
  const activePlugins = usingLiveData ? livePlugins : MOCK_PLUGINS;
  const activeWorkflows = usingLiveData ? liveWorkflows : MOCK_WORKFLOWS;
  const userSelectablePlugins = activePlugins.filter(p => p.user_selectable !== false);

  useEffect(() => {
    async function fetchData() {
      try {
        // Try fetching real plugins, workflows, and license status from API
        const [pluginsRes, workflowsRes, licenseRes] = await Promise.all([
          apiService.getPlugins(true),
          apiService.getWorkflows(),
          apiService.getLicenseStatus().catch(() => null),
        ]);
        
        if (licenseRes) {
          setLicenseStatus(licenseRes);
        }

        if (pluginsRes.plugins.length > 0) {
          // Map API response to our Plugin interface
          const apiPlugins: Plugin[] = pluginsRes.plugins.map((p: any) => ({
            id: p.id,
            name: p.name,
            version: p.version,
            container: p.container_image,
            description: p.description,
            category: (p.domain === 'structural_mri' ? 'structural' :
                       p.domain === 'functional_mri' ? 'functional' :
                       p.domain === 'diffusion_mri' ? 'diffusion' :
                       p.domain === 'epilepsy' ? 'epilepsy' :
                       p.domain === 'conversion' ? 'conversion' : 'structural') as Plugin['category'],
            user_selectable: p.user_selectable,
          }));

          // Map API response to our Workflow interface
          const apiWorkflows: Workflow[] = workflowsRes.workflows.map((w: any) => ({
            id: w.id,
            name: w.name,
            version: w.version,
            description: w.description,
            plugins: w.plugin_ids || [],
            category: (w.domain === 'structural_mri' ? 'structural' :
                       w.domain === 'functional_mri' ? 'functional' :
                       w.domain === 'diffusion_mri' ? 'diffusion' :
                       w.domain === 'epilepsy' ? 'epilepsy' :
                       w.domain === 'conversion' ? 'conversion' : 'structural') as Workflow['category'],
          }));

          setLivePlugins(apiPlugins);
          setLiveWorkflows(apiWorkflows);
          setUsingLiveData(true);
          console.log(`Loaded ${apiPlugins.length} plugins and ${apiWorkflows.length} workflows from API`);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        console.warn('API unavailable, using mock data:', msg);
        setError(`Live data unavailable (${msg}). Using sample data.`);
        setUsingLiveData(false);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  // Auto-select first item once data is loaded
  useEffect(() => {
    if (!loading) {
      const wfs = usingLiveData ? liveWorkflows : MOCK_WORKFLOWS;
      if (wfs.length > 0 && !selectedWorkflowId && mode === 'workflows') {
        setSelectedWorkflowId(wfs[0].id);
      }
      // Create a Pipeline-compatible object for parent component
      if (wfs.length > 0 && !selectedPipeline) {
        const wf = wfs[0];
        onPipelineSelect({
          name: wf.name,
          version: wf.version,
          description: wf.description,
        } as Pipeline);
      }
    }
  }, [loading, usingLiveData]);

  const handlePluginSelect = (pluginId: string) => {
    setSelectedPluginId(pluginId);
    setSelectedWorkflowId(null);
    
    const plugin = activePlugins.find(p => p.id === pluginId);
    if (plugin) {
      onPipelineSelect({
        name: plugin.name,
        version: plugin.version,
        description: plugin.description,
        container_image: plugin.container,
      } as Pipeline);
      onExecutionSelect?.({ type: 'plugin', id: plugin.id, name: plugin.name });
    }
  };

  const handleWorkflowSelect = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setSelectedPluginId(null);
    
    const workflow = activeWorkflows.find(w => w.id === workflowId);
    if (workflow) {
      const pluginContainers = workflow.plugins
        .map(pid => activePlugins.find(p => p.id === pid)?.container || '')
        .filter(Boolean);
      onPipelineSelect({
        name: workflow.name,
        version: workflow.version,
        description: workflow.description,
        container_image: pluginContainers.join(', '),
      } as Pipeline);
      onExecutionSelect?.({ type: 'workflow', id: workflow.id, name: workflow.name });
    }
  };

  const selectedPlugin = activePlugins.find(p => p.id === selectedPluginId);
  const selectedWorkflow = activeWorkflows.find(w => w.id === selectedWorkflowId);
  const workflowPlugins = selectedWorkflow ? activePlugins.filter(p => selectedWorkflow.plugins.includes(p.id)) : [];

  if (loading) {
    return (
      <div className="bg-white shadow sm:rounded-lg p-6 h-full flex items-center justify-center">
        <div className="flex items-center">
          <Loader2 className="h-6 w-6 animate-spin text-[#003d7a] mr-2" />
          <span className="text-gray-600">Loading pipelines...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white shadow sm:rounded-lg p-6 h-full flex flex-col">
        {/* Mode Toggle */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('plugins')}
            className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition ${
              mode === 'plugins'
                ? 'bg-[#003d7a] text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <Zap className="w-4 h-4 inline mr-2" />
            Plugins
          </button>
          <button
            onClick={() => setMode('workflows')}
            className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition ${
              mode === 'workflows'
                ? 'bg-[#003d7a] text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <GitBranch className="w-4 h-4 inline mr-2" />
            Workflows
          </button>
        </div>

        {/* Using mock data since API failed */}
        <div className="text-sm text-gray-700 bg-navy-50 border border-navy-200 rounded p-3">
          <strong className="text-[#003d7a]">Note:</strong> API unavailable. Showing mock data for demonstration.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white shadow sm:rounded-lg p-6 h-full flex flex-col">
      {/* Mode Toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => {
            setMode('plugins');
            const firstSelectablePlugin = userSelectablePlugins[0];
            setSelectedPluginId(firstSelectablePlugin?.id || null);
            setSelectedWorkflowId(null);
          }}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition ${
            mode === 'plugins'
              ? 'bg-[#003d7a] text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <Zap className="w-4 h-4 inline mr-2" />
          Plugins
        </button>
        <button
          onClick={() => {
            setMode('workflows');
            setSelectedWorkflowId(activeWorkflows[0]?.id || null);
            setSelectedPluginId(null);
          }}
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition ${
            mode === 'workflows'
              ? 'bg-[#003d7a] text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <GitBranch className="w-4 h-4 inline mr-2" />
          Workflows
        </button>
      </div>

      {/* Data source & license indicators */}
      <div className="mb-3 space-y-1">
        <div className="text-xs text-gray-500 flex items-center gap-1">
          <span className={`inline-block w-2 h-2 rounded-full ${usingLiveData ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
          {usingLiveData
            ? `Live: ${userSelectablePlugins.length} plugins, ${activeWorkflows.length} workflows`
            : `Demo: ${userSelectablePlugins.length} plugins, ${activeWorkflows.length} workflows`
          }
        </div>
        {licenseStatus && (
          <div className={`text-xs flex items-center gap-1 ${licenseStatus.found ? 'text-green-600' : 'text-amber-600'}`}>
            {licenseStatus.found ? (
              <>
                <CheckCircle className="w-3 h-3" />
                FreeSurfer license detected
              </>
            ) : (
              <>
                <AlertTriangle className="w-3 h-3" />
                <span>No FreeSurfer license — place <code className="bg-gray-100 px-1 rounded text-[10px]">license.txt</code> in app directory</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Plugin Selector */}
      {mode === 'plugins' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Select Plugin <span className="text-red-500">*</span>
          </label>
          <select
            value={selectedPluginId || ''}
            onChange={(e) => handlePluginSelect(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#003d7a] focus:border-[#003d7a] text-base"
          >
            {userSelectablePlugins.map((plugin) => (
              <option key={plugin.id} value={plugin.id}>
                {plugin.name} (v{plugin.version}) - {getCategoryLabel(plugin.category)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Workflow Selector */}
      {mode === 'workflows' && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Select Workflow <span className="text-red-500">*</span>
          </label>
          <select
            value={selectedWorkflowId || ''}
            onChange={(e) => handleWorkflowSelect(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#003d7a] focus:border-[#003d7a] text-base"
          >
            {activeWorkflows.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.name} ({workflow.plugins.length} plugin{workflow.plugins.length > 1 ? 's' : ''}) - {getCategoryLabel(workflow.category)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Selected Plugin Details */}
      {selectedPlugin && mode === 'plugins' && (
        <div className="mt-6">
          {/* Description */}
          <div className="p-4 bg-gray-50 rounded-md">
            <div className="flex items-start">
              <Info className="h-5 w-5 text-[#003d7a] mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-medium text-gray-900">Description</h4>
                <p className="text-sm text-gray-600 mt-1">{selectedPlugin.description}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Selected Workflow Details */}
      {selectedWorkflow && mode === 'workflows' && (
        <div className="mt-6">
          {/* Pipeline Steps */}
          <div className="p-4 bg-navy-50 border border-navy-200 rounded-md">
            <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-[#003d7a]" />
              Pipeline Steps
            </h4>
            <div className="space-y-3">
              {workflowPlugins.map((plugin, idx) => (
                <div key={plugin.id} className="flex items-start gap-3 bg-white p-3 rounded-md border border-gray-300">
                  <div className="flex flex-col items-center">
                    <div className="w-8 h-8 rounded-full bg-[#003d7a] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">
                      {idx + 1}
                    </div>
                    {idx < workflowPlugins.length - 1 && (
                      <div className="w-0.5 h-8 bg-[#003d7a] opacity-30 my-1"></div>
                    )}
                  </div>
                  <div className="flex-1">
                    <h5 className="text-sm font-semibold text-gray-900">{plugin.name}</h5>
                    <p className="text-xs text-gray-600 mt-1">{plugin.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Reference Guide */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Quick Reference</h4>
        <div className="space-y-2 text-xs text-gray-600">
          <div className="flex gap-2">
            <span className="font-semibold text-[#003d7a] min-w-[60px]">Plugin:</span>
            <span>Single neuroimaging tool running one container. Use for individual processing steps or full control.</span>
          </div>
          <div className="flex gap-2">
            <span className="font-semibold text-[#003d7a] min-w-[60px]">Workflow:</span>
            <span>Sequence of plugins working together. Manages dependencies automatically. Recommended for complete analysis pipelines.</span>
          </div>
          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <span className="font-semibold text-gray-500 min-w-[60px]">Note:</span>
            <span className="text-gray-500 italic">Some utility plugins are hidden but work within workflows for specialized tasks.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
