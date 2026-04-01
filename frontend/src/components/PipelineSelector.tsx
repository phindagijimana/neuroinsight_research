/**
 * PipelineSelector Component
 * 
 * Allows users to select plugins (single tools) or workflows (plugin chains)
 */

import React, { useState, useEffect } from 'react';
import { Loader2, Zap, GitBranch, CheckCircle, AlertTriangle } from 'lucide-react';
import { apiService } from '../services/api';
import type { Pipeline } from '../types';

interface PipelineSelectorProps {
  onPipelineSelect: (pipeline: Pipeline | null) => void;
  selectedPipeline: Pipeline | null;
  onExecutionSelect?: (execution: { type: 'plugin' | 'workflow'; id: string; name: string } | null) => void;
}

type SelectionMode = 'plugins' | 'workflows';

type PipelineCategory =
  | 'structural'
  | 'functional'
  | 'diffusion'
  | 'conversion'
  | 'epilepsy'
  | 'eeg'
  | 'multimodal';

interface Plugin {
  id: string;
  name: string;
  version: string;
  container: string;
  description: string;
  category: PipelineCategory;
  user_selectable?: boolean; // If false, plugin is hidden from UI (utility plugins)
  input_format_name?: string;
  input_format_description?: string;
  input_format_example?: string;
}

interface Workflow {
  id: string;
  name: string;
  version: string;
  description: string;
  plugins: string[]; // Plugin IDs in order
  category: PipelineCategory;
  input_format_name?: string;
  input_format_description?: string;
  input_format_example?: string;
}

/** Map backend `domain` (from plugins/*.yaml) to UI category labels. */
function mapDomainToCategory(domain: string | undefined): PipelineCategory {
  const d = (domain || '').trim();
  switch (d) {
    case 'structural_mri':
      return 'structural';
    case 'functional_mri':
      return 'functional';
    case 'diffusion_mri':
      return 'diffusion';
    case 'epilepsy':
      return 'epilepsy';
    case 'conversion':
      return 'conversion';
    case 'eeg':
      return 'eeg';
    case 'eeg_imaging':
      return 'multimodal';
    default:
      return 'structural';
  }
}

// Mock plugins data
const MOCK_PLUGINS: Plugin[] = [
  {
    id: 'dcm2niix',
    name: 'DICOM to NIfTI Converter',
    version: '1.0.0',
    container: 'nipy/heudiconv:1.3.4',
    description: '',
    category: 'conversion',
  },
  {
    id: 'freesurfer_recon',
    name: 'FreeSurfer recon-all',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
  },
  {
    id: 'fastsurfer',
    name: 'FastSurfer',
    version: '2.0.0',
    container: 'deepmi/fastsurfer:v2.4.2',
    description: '',
    category: 'structural',
  },
  {
    id: 'segmentha_t1',
    name: 'FreeSurfer SegmentHA_T1',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
  },
  {
    id: 'segmentha_t2',
    name: 'FreeSurfer SegmentHA_T2',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
  },
  {
    id: 'fmriprep',
    name: 'fMRIPrep',
    version: '23.2.1',
    container: 'nipreps/fmriprep:23.2.1',
    description: '',
    category: 'functional',
  },
  {
    id: 'xcpd',
    name: 'XCP-D',
    version: '0.6.1',
    container: 'pennlinc/xcp_d:0.6.1',
    description: '',
    category: 'functional',
  },
  {
    id: 'qsiprep',
    name: 'QSIPrep',
    version: '0.20.0',
    container: 'pennbbl/qsiprep:0.20.0',
    description: '',
    category: 'diffusion',
  },
  {
    id: 'qsirecon',
    name: 'QSIRecon',
    version: '0.20.0',
    container: 'pennlinc/qsirecon:1.1.1',
    description: '',
    category: 'diffusion',
  },
  {
    id: 'meld_graph',
    name: 'MELD Graph',
    version: '1.0.0',
    container: 'phindagijimana321/meld_graph:v2.2.4-nir2',
    description: '',
    category: 'epilepsy',
  },
  {
    id: 'freesurfer_longitudinal',
    name: 'FreeSurfer Longitudinal',
    version: '1.0.0',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
    user_selectable: true,
  },
  {
    id: 'freesurfer_longitudinal_stats',
    name: 'FreeSurfer Longitudinal Stats Utility',
    version: '1.0.0',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
    user_selectable: false // Hidden from UI - only called by workflows
  },
  // EEG / multimodal (mirrors plugins/*.yaml — shown when API is offline)
  {
    id: 'eeg_preprocessing',
    name: 'EEG Preprocessing',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-preprocessing-mne:1.0.3',
    description: '',
    category: 'eeg',
  },
  {
    id: 'spike_detection',
    name: 'EEG Spike Detection',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-spike-detection-mne:1.0.1',
    description: '',
    category: 'eeg',
  },
  {
    id: 'eeg_mri_coregistration',
    name: 'EEG–MRI Coregistration',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-mri-coregistration-mne:1.0.2',
    description: '',
    category: 'multimodal',
  },
  {
    id: 'forward_model',
    name: 'EEG Forward Model',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-forward-model-mne:1.0.10',
    description: '',
    category: 'multimodal',
  },
  {
    id: 'source_localization',
    name: 'EEG Source Localization',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-source-localization-mne:1.0.3',
    description: '',
    category: 'multimodal',
  },
  {
    id: 'mri_segmentation',
    name: 'MRI Segmentation (FreeSurfer VolOnly)',
    version: '7.4.1',
    container: 'phindagijimana321/freesurfer-autorecon-volonly:7.4.1',
    description: '',
    category: 'multimodal',
  },
  {
    id: 'roi_feature_extraction',
    name: 'ROI Feature Extraction',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-roi-feature-extraction:1.0.1',
    description: '',
    category: 'multimodal',
  },
  {
    id: 'biomarker_scoring',
    name: 'Biomarker Scoring',
    version: '1.0.0',
    container: 'phindagijimana321/eeg-biomarker-scoring:1.0.0',
    description: '',
    category: 'multimodal',
  },
];

// Mock workflows data
const MOCK_WORKFLOWS: Workflow[] = [
  {
    id: 'dicom_ingestion',
    name: 'DICOM Ingestion',
    version: '1.0.0',
    description: '',
    plugins: ['dcm2niix'],
    category: 'conversion'
  },
  {
    id: 'structural_segmentation',
    name: 'FastSurfer Segmentation and Volumetry',
    version: '1.0.0',
    description: '',
    plugins: ['fastsurfer'],
    category: 'structural'
  },
  {
    id: 'hippocampal_subfields_t1',
    name: 'Hippocampal Subfields Segmentation T1',
    version: '1.0.0',
    description: '',
    plugins: ['freesurfer_recon', 'segmentha_t1'],
    category: 'structural'
  },
  {
    id: 'hippocampal_subfields_t2',
    name: 'Hippocampal Subfields Segmentation T1 + T2',
    version: '1.0.0',
    description: '',
    plugins: ['freesurfer_recon', 'segmentha_t2'],
    category: 'structural'
  },
  {
    id: 'fmri_preprocess',
    name: 'fMRI Preprocessing',
    version: '1.0.0',
    description: '',
    plugins: ['fmriprep'],
    category: 'functional'
  },
  {
    id: 'fmri_full',
    name: 'fMRI Full Pipeline',
    version: '1.0.0',
    description: '',
    plugins: ['fmriprep', 'xcpd'],
    category: 'functional'
  },
  {
    id: 'diffusion_preprocess',
    name: 'Diffusion Preprocessing',
    version: '1.0.0',
    description: '',
    plugins: ['qsiprep'],
    category: 'diffusion'
  },
  {
    id: 'diffusion_full',
    name: 'Diffusion Full Pipeline',
    version: '1.0.0',
    description: '',
    plugins: ['qsiprep', 'qsirecon'],
    category: 'diffusion'
  },
  {
    id: 'cortical_lesion_detection',
    name: 'Cortical Lesion Detection',
    version: '1.0.0',
    description: '',
    plugins: ['freesurfer_recon', 'meld_graph'],
    category: 'epilepsy'
  },
  {
    id: 'freesurfer_longitudinal_full',
    name: 'FreeSurfer Longitudinal Full',
    version: '1.0.0',
    description: '',
    plugins: ['freesurfer_longitudinal', 'freesurfer_longitudinal_stats'],
    category: 'structural'
  },
  {
    id: 'basic_eeg_epilepsy_detection',
    name: 'Basic EEG Epilepsy Detection',
    version: '1.0.0',
    description: '',
    plugins: ['eeg_preprocessing', 'spike_detection'],
    category: 'eeg',
  },
  {
    id: 'eeg_source_localization',
    name: 'EEG Source Localization',
    version: '1.0.0',
    description: '',
    plugins: [
      'eeg_preprocessing',
      'spike_detection',
      'eeg_mri_coregistration',
      'forward_model',
      'source_localization',
    ],
    category: 'multimodal',
  },
  {
    id: 'multimodal_epilepsy_biomarker',
    name: 'Multimodal Epilepsy Biomarker',
    version: '1.0.0',
    description:
      'Stage EEG (e.g. eeg/raw/) and T1w.nii.gz in one folder; submit paths only under that folder.',
    plugins: [
      'eeg_preprocessing',
      'spike_detection',
      'eeg_mri_coregistration',
      'bem_source_space',
      'forward_model',
      'source_localization',
      'mri_segmentation',
      'roi_feature_extraction',
      'biomarker_scoring',
    ],
    category: 'multimodal',
  },
];

const getCategoryLabel = (category: string) => {
  switch (category) {
    case 'structural': return 'Structural';
    case 'functional': return 'Functional';
    case 'diffusion': return 'Diffusion';
    case 'conversion': return 'Conversion';
    case 'epilepsy': return 'Epilepsy';
    case 'eeg': return 'EEG';
    case 'multimodal': return 'EEG + Imaging';
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
  const [licenseStatus, setLicenseStatus] = useState<{
    freesurfer: { found: boolean; path: string | null; registration_url: string };
    meld_graph: { found: boolean; path: string | null; registration_url: string };
    hint: string;
  } | null>(null);

  // Decide which data source to use
  const activePlugins = usingLiveData ? livePlugins : MOCK_PLUGINS;
  const activeWorkflows = usingLiveData ? liveWorkflows : MOCK_WORKFLOWS;
  const userSelectablePlugins = activePlugins.filter(p => p.user_selectable !== false);

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch ALL plugins (including utilities for workflow step lookups) and workflows
        const [pluginsRes, workflowsRes] = await Promise.all([
          apiService.getPlugins(false),
          apiService.getWorkflows(),
        ]);

        const rawPlugins = pluginsRes.plugins ?? [];
        if (rawPlugins.length > 0) {
          setError(null);
          // Map API response to our Plugin interface
          const apiPlugins: Plugin[] = rawPlugins.map((p: any) => ({
            id: p.id,
            name: p.name,
            version: p.version,
            container: p.container_image,
            description: '',
            category: mapDomainToCategory(p.domain),
            user_selectable: p.user_selectable,
          }));

          const rawWfs = workflowsRes.workflows ?? [];
          // Map API response to our Workflow interface
          const apiWorkflows: Workflow[] = rawWfs.map((w: any) => ({
            id: w.id,
            name: w.name,
            version: w.version,
            description: '',
            plugins: w.plugin_ids || [],
            category: mapDomainToCategory(w.domain),
          }));

          setLivePlugins(apiPlugins);
          setLiveWorkflows(apiWorkflows);
          setUsingLiveData(true);
        } else {
          setUsingLiveData(false);
          setError('API returned no plugins — using demo catalog. Start the backend so plugins/ YAML is loaded.');
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
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
          description: '',
        } as Pipeline);
        onExecutionSelect?.({ type: 'workflow', id: wf.id, name: wf.name });
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
        description: '',
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
        description: '',
        container_image: pluginContainers.join(', '),
      } as Pipeline);
      onExecutionSelect?.({ type: 'workflow', id: workflow.id, name: workflow.name });
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-100 bg-white p-5 flex items-center justify-center shadow-sm">
        <div className="flex items-center">
          <Loader2 className="h-6 w-6 animate-spin text-[#003d7a] mr-2" />
          <span className="text-sm text-gray-500">Loading pipelines…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-gray-100 bg-white p-5 flex flex-col shadow-sm">
        {/* Mode Toggle */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('plugins')}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition ${
              mode === 'plugins'
                ? 'bg-[#003d7a] text-white shadow-sm'
                : 'bg-slate-100/80 text-gray-700 hover:bg-slate-100'
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
        <div className="text-sm text-gray-600 bg-amber-50/80 border border-amber-100/80 rounded-lg px-3 py-2.5">
          <span className="font-medium text-amber-900/90">Offline catalog.</span> Connect the backend for live plugins.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-5 flex flex-col shadow-sm">
      {/* Mode Toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => {
            setMode('plugins');
            const firstSelectablePlugin = userSelectablePlugins[0];
            setSelectedPluginId(firstSelectablePlugin?.id || null);
            setSelectedWorkflowId(null);
          }}
          className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition ${
            mode === 'plugins'
              ? 'bg-[#003d7a] text-white shadow-sm'
              : 'bg-slate-100/80 text-gray-700 hover:bg-slate-100'
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
          className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition ${
            mode === 'workflows'
              ? 'bg-[#003d7a] text-white shadow-sm'
              : 'bg-slate-100/80 text-gray-700 hover:bg-slate-100'
          }`}
        >
          <GitBranch className="w-4 h-4 inline mr-2" />
          Workflows
        </button>
      </div>

      {error && (
        <div className="text-sm text-amber-900/90 bg-amber-50/80 border border-amber-100/80 rounded-lg px-3 py-2.5 mb-3">
          {error}
        </div>
      )}

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

    </div>
  );
};
