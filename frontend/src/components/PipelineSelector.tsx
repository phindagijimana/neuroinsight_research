/**
 * PipelineSelector Component
 * 
 * Allows users to select plugins (single tools) or workflows (plugin chains)
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Zap, GitBranch, Search } from 'lucide-react';
import { apiService } from '../services/api';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import type { Pipeline } from '../types';
import { Spinner } from './LoadingState';
import { inputProfileFromApi } from '../lib/inputFormat';

// Categories hidden from the catalog when the EEG feature is disabled.
const EEG_CATEGORIES: PipelineCategory[] = ['eeg', 'multimodal'];

interface PipelineSelectorProps {
  onPipelineSelect: (pipeline: Pipeline | null) => void;
  selectedPipeline: Pipeline | null;
  onExecutionSelect?: (execution: {
    type: 'plugin' | 'workflow';
    id: string;
    name: string;
    inputFormatName?: string;
    inputFormatDescription?: string;
    requiresBidsDir?: boolean;
  } | null) => void;
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
  requires_bids_dir?: boolean;
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
  requires_bids_dir?: boolean;
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
    name: 'Hippocampal Subfield Segmentation (T1)',
    version: '7.4.1',
    container: 'freesurfer/freesurfer:7.4.1',
    description: '',
    category: 'structural',
  },
  {
    id: 'segmentha_t2',
    name: 'Hippocampal Subfield Segmentation (T1 + T2)',
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
    name: 'FreeSurfer Longitudinal Statistics',
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
    name: 'MRI Volumetric Segmentation',
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
    name: 'Hippocampal Subfield Segmentation (T1)',
    version: '1.0.0',
    description: '',
    plugins: ['freesurfer_recon', 'segmentha_t1'],
    category: 'structural'
  },
  {
    id: 'hippocampal_subfields_t2',
    name: 'Hippocampal Subfield Segmentation (T1 + T2)',
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

interface CatalogRow {
  id: string;
  name: string;
  version: string;
  category: PipelineCategory;
  meta?: string;
  inputFormatName?: string;
  description?: string;
}

function filterCatalog(items: CatalogRow[], query: string): CatalogRow[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    (item) =>
      item.name.toLowerCase().includes(q) ||
      item.id.toLowerCase().includes(q) ||
      getCategoryLabel(item.category).toLowerCase().includes(q) ||
      (item.meta && item.meta.toLowerCase().includes(q)) ||
      (item.inputFormatName && item.inputFormatName.toLowerCase().includes(q))
  );
}

const PipelineCatalogList: React.FC<{
  label: string;
  items: CatalogRow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  searchPlaceholder?: string;
}> = ({ label, items, selectedId, onSelect, searchPlaceholder = 'Search by name, category, or input type…' }) => {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => filterCatalog(items, query), [items, query]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label} <span className="text-red-500">*</span>
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={searchPlaceholder}
          aria-label={`Search ${label.toLowerCase()}`}
          className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm shadow-sm focus:border-navy-600 focus:outline-none focus:ring-2 focus:ring-navy-600/20"
        />
      </div>
      <div
        className="max-h-52 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-inner"
        role="listbox"
        aria-label={label}
      >
        {filtered.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-gray-500">No matches — try a different search.</p>
        ) : (
          filtered.map((item) => {
            const selected = item.id === selectedId;
            return (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => onSelect(item.id)}
                className={`flex w-full flex-col gap-0.5 border-b border-gray-100 px-3 py-2.5 text-left transition-colors last:border-b-0 ${
                  selected
                    ? 'bg-navy-50 ring-1 ring-inset ring-navy-600/25'
                    : 'hover:bg-gray-50'
                }`}
              >
                <span className="flex items-start justify-between gap-2">
                  <span className={`text-sm font-semibold leading-snug ${selected ? 'text-navy-800' : 'text-gray-900'}`}>
                    {item.name}
                  </span>
                  <span className="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600">
                    {getCategoryLabel(item.category)}
                  </span>
                </span>
                <span className="text-[11px] text-gray-500">
                  v{item.version}
                  {item.meta ? ` · ${item.meta}` : ''}
                  {item.inputFormatName ? ` · ${item.inputFormatName}` : ''}
                </span>
              </button>
            );
          })
        )}
      </div>
      <p className="text-[11px] text-gray-400">
        {filtered.length === items.length
          ? `${items.length} available`
          : `${filtered.length} of ${items.length} shown`}
      </p>
    </div>
  );
};

const SelectedInputHint: React.FC<{ formatName?: string; description?: string }> = ({
  formatName,
  description,
}) => {
  if (!formatName) return null;
  return (
    <div className="mt-3 rounded-lg border border-navy-100 bg-navy-50/50 px-3 py-2.5">
      <p className="text-xs font-semibold text-navy-800">Expects: {formatName}</p>
      {description && (
        <p className="mt-1 text-[11px] leading-relaxed text-navy-900/75">{description}</p>
      )}
    </div>
  );
};

export const PipelineSelector: React.FC<PipelineSelectorProps> = ({
  onPipelineSelect,
  selectedPipeline,
  onExecutionSelect,
}) => {
  const { eegEnabled } = useFeatureFlags();
  const [mode, setMode] = useState<SelectionMode>('workflows');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [usingLiveData, setUsingLiveData] = useState(false);
  const [catalogEpoch, setCatalogEpoch] = useState(0);
  const [livePlugins, setLivePlugins] = useState<Plugin[]>([]);
  const [liveWorkflows, setLiveWorkflows] = useState<Workflow[]>([]);
  // Decide which data source to use. When EEG is disabled, drop EEG/multimodal
  // categories so the offline (mock) catalog matches the imaging-only backend.
  const categoryAllowed = (c: PipelineCategory) => eegEnabled || !EEG_CATEGORIES.includes(c);
  const activePlugins = (usingLiveData ? livePlugins : MOCK_PLUGINS).filter(p => categoryAllowed(p.category));
  const activeWorkflows = (usingLiveData ? liveWorkflows : MOCK_WORKFLOWS).filter(w => categoryAllowed(w.category));
  const userSelectablePlugins = activePlugins.filter(p => p.user_selectable !== false);

  const pluginCatalog: CatalogRow[] = useMemo(
    () =>
      userSelectablePlugins.map((p) => ({
        id: p.id,
        name: p.name,
        version: p.version,
        category: p.category,
        inputFormatName: p.input_format_name,
        description: p.input_format_description,
      })),
    [userSelectablePlugins]
  );

  const workflowCatalog: CatalogRow[] = useMemo(
    () =>
      activeWorkflows.map((w) => ({
        id: w.id,
        name: w.name,
        version: w.version,
        category: w.category,
        meta: `${w.plugins.length} step${w.plugins.length !== 1 ? 's' : ''}`,
        inputFormatName: w.input_format_name,
        description: w.input_format_description,
      })),
    [activeWorkflows]
  );

  const selectedPlugin = activePlugins.find((p) => p.id === selectedPluginId);
  const selectedWorkflow = activeWorkflows.find((w) => w.id === selectedWorkflowId);

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
          const apiPlugins: Plugin[] = rawPlugins.map((p: any) => {
            const profile = inputProfileFromApi(p);
            return {
              id: p.id,
              name: p.name,
              version: p.version,
              container: p.container_image,
              description: p.description || '',
              category: mapDomainToCategory(p.domain),
              user_selectable: p.user_selectable,
              input_format_name: profile.inputFormatName,
              input_format_description: profile.inputFormatDescription,
              input_format_example: p.input_format?.example_structure,
              requires_bids_dir: profile.requiresBidsDir,
            };
          });

          const rawWfs = workflowsRes.workflows ?? [];
          const apiWorkflows: Workflow[] = rawWfs.map((w: any) => {
            const profile = inputProfileFromApi(w);
            return {
              id: w.id,
              name: w.name,
              version: w.version,
              description: w.description || '',
              plugins: w.plugin_ids || [],
              category: mapDomainToCategory(w.domain),
              input_format_name: profile.inputFormatName,
              input_format_description: profile.inputFormatDescription,
              input_format_example: w.input_format?.example_structure,
              requires_bids_dir: profile.requiresBidsDir,
            };
          });

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
        onExecutionSelect?.({
          type: 'workflow',
          id: wf.id,
          name: wf.name,
          inputFormatName: wf.input_format_name,
          inputFormatDescription: wf.input_format_description,
          requiresBidsDir: wf.requires_bids_dir,
        });
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
        description: plugin.description || '',
        container_image: plugin.container,
      } as Pipeline);
      onExecutionSelect?.({
        type: 'plugin',
        id: plugin.id,
        name: plugin.name,
        inputFormatName: plugin.input_format_name,
        inputFormatDescription: plugin.input_format_description,
        requiresBidsDir: plugin.requires_bids_dir,
      });
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
        description: workflow.description || '',
        container_image: pluginContainers.join(', '),
      } as Pipeline);
      onExecutionSelect?.({
        type: 'workflow',
        id: workflow.id,
        name: workflow.name,
        inputFormatName: workflow.input_format_name,
        inputFormatDescription: workflow.input_format_description,
        requiresBidsDir: workflow.requires_bids_dir,
      });
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-100 bg-white p-5 flex items-center justify-center shadow-sm">
        <div className="flex items-center">
          <Spinner size="md" className="text-navy-600 mr-2" />
          <span className="text-sm text-gray-500">Loading pipelines…</span>
        </div>
      </div>
    );
  }

  const switchToPlugins = () => {
    setMode('plugins');
    setCatalogEpoch((e) => e + 1);
    const first = userSelectablePlugins[0];
    if (first) handlePluginSelect(first.id);
    else {
      setSelectedPluginId(null);
      setSelectedWorkflowId(null);
    }
  };

  const switchToWorkflows = () => {
    setMode('workflows');
    setCatalogEpoch((e) => e + 1);
    const first = activeWorkflows[0];
    if (first) handleWorkflowSelect(first.id);
    else {
      setSelectedPluginId(null);
      setSelectedWorkflowId(null);
    }
  };

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-5 flex flex-col shadow-sm">
      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={switchToPlugins}
          className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition border-none ${
            mode === 'plugins'
              ? 'bg-navy-600 text-white shadow-sm'
              : 'bg-slate-100/80 text-gray-700 hover:bg-slate-100'
          }`}
        >
          <Zap className="w-4 h-4 inline mr-2" />
          Plugins
        </button>
        <button
          type="button"
          onClick={switchToWorkflows}
          className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition border-none ${
            mode === 'workflows'
              ? 'bg-navy-600 text-white shadow-sm'
              : 'bg-slate-100/80 text-gray-700 hover:bg-slate-100'
          }`}
        >
          <GitBranch className="w-4 h-4 inline mr-2" />
          Workflows
        </button>
      </div>

      {error && (
        <div className="text-sm text-amber-900/90 bg-amber-50/80 border border-amber-100/80 rounded-lg px-3 py-2.5 mb-3">
          <span className="font-medium">Offline catalog.</span> {error}
        </div>
      )}

      {mode === 'plugins' && (
        <PipelineCatalogList
          key={`plugins-${catalogEpoch}`}
          label="Select plugin"
          items={pluginCatalog}
          selectedId={selectedPluginId}
          onSelect={handlePluginSelect}
        />
      )}

      {mode === 'workflows' && (
        <PipelineCatalogList
          key={`workflows-${catalogEpoch}`}
          label="Select workflow"
          items={workflowCatalog}
          selectedId={selectedWorkflowId}
          onSelect={handleWorkflowSelect}
        />
      )}

      {mode === 'plugins' && (
        <SelectedInputHint
          formatName={selectedPlugin?.input_format_name}
          description={selectedPlugin?.input_format_description}
        />
      )}
      {mode === 'workflows' && (
        <SelectedInputHint
          formatName={selectedWorkflow?.input_format_name}
          description={selectedWorkflow?.input_format_description}
        />
      )}
    </div>
  );
};
