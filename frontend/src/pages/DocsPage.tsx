/**
 * DocsPage Component
 * Browse and review all plugin and workflow YAML definitions.
 * Master-detail layout: scrollable list on the left, selected item detail on the right.
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { USER_GUIDE_URL } from '../userGuide';
import {
  FileText,
  Zap,
  GitBranch,
  Search,
  Box,
  Cpu,
  Clock,
  HardDrive,
  Shield,
  AlertTriangle,
  ChevronRight,
  FolderTree,
  CheckCircle,
} from 'lucide-react';
import { LoadingState } from '../components/LoadingState';
import WorkspacePageHeader from '../components/WorkspacePageHeader';
import Button from '../components/Button';

interface InputFormat {
  format_name?: string;
  description?: string;
  notes?: string[];
  example_structure?: string;
  file_types?: string[];
}

interface PluginDoc {
  id: string;
  name: string;
  version: string;
  domain: string;
  description: string;
  container_image: string;
  container_runtime: string;
  user_selectable: boolean;
  ui_category: string;
  inputs: { required: any[]; optional: any[] };
  input_format?: InputFormat;
  parameters: any[];
  resources: Record<string, any>;
  resource_profiles: Record<string, any>;
  parallelization: Record<string, any>;
  stages: any[];
  bundle_config: Record<string, any>;
  authors: string[];
  references: string[];
  yaml: string;
}

interface WorkflowDoc {
  id: string;
  name: string;
  version: string;
  domain: string;
  description: string;
  steps: any[];
  plugin_ids: string[];
  inputs: { required: any[]; optional: any[] };
  input_format?: InputFormat;
  validation: Record<string, any>;
  outputs: Record<string, any>;
  yaml: string;
}


const domainLabel = (domain: string) => {
  switch (domain) {
    case 'structural_mri': return 'Structural MRI';
    case 'functional_mri': return 'Functional MRI';
    case 'diffusion_mri': return 'Diffusion MRI';
    case 'epilepsy': return 'Epilepsy';
    case 'conversion': return 'Conversion';
    default: return domain;
  }
};

const domainColor = (domain: string) => {
  switch (domain) {
    case 'structural_mri': return 'bg-navy-100 text-navy-800';
    case 'functional_mri': return 'bg-navy-100 text-navy-800';
    case 'diffusion_mri': return 'bg-green-100 text-green-800';
    case 'epilepsy': return 'bg-navy-100 text-navy-800';
    case 'conversion': return 'bg-gray-100 text-gray-800';
    default: return 'bg-gray-100 text-gray-800';
  }
};

interface DocsPageProps {
  setActivePage?: (page: string) => void;
}

/* -------------------------------------------------------------------------- */
/*  Input Format Section (shared by Plugin & Workflow detail)                  */
/* -------------------------------------------------------------------------- */

const InputFormatSection: React.FC<{ inputFormat?: InputFormat }> = ({ inputFormat }) => {
  if (!inputFormat || (!inputFormat.format_name && !inputFormat.example_structure)) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-3 flex items-center gap-1.5">
        <FolderTree className="w-4 h-4" />
        Input Data Format
      </h3>
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
        {/* Format name & description */}
        {inputFormat.format_name && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-navy-600">{inputFormat.format_name}</span>
          </div>
        )}
        {inputFormat.description && (
          <p className="text-sm text-gray-600">{inputFormat.description}</p>
        )}

        {/* Notes */}
        {inputFormat.notes && inputFormat.notes.length > 0 && (
          <ul className="text-xs text-gray-500 space-y-1 pl-1">
            {inputFormat.notes.map((note: string, i: number) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="w-1 h-1 bg-gray-400 rounded-full mt-1.5 flex-shrink-0"></span>
                {note}
              </li>
            ))}
          </ul>
        )}

        {/* Folder structure example */}
        {inputFormat.example_structure && (
          <div>
            <span className="text-xs font-medium text-gray-500 block mb-1.5">Expected folder structure:</span>
            <pre className="bg-gray-900 text-green-300 rounded-md px-3 py-2.5 text-xs font-mono leading-relaxed overflow-x-auto whitespace-pre">
              {inputFormat.example_structure.trim()}
            </pre>
          </div>
        )}

        {/* Accepted file types */}
        {inputFormat.file_types && inputFormat.file_types.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {inputFormat.file_types.map((ft: string, i: number) => (
              <span key={i} className="text-xs bg-navy-50 text-navy-700 px-2 py-0.5 rounded font-mono">
                {ft}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*  Plugin Detail                                                             */
/* -------------------------------------------------------------------------- */

const PluginDetail: React.FC<{ plugin: PluginDoc }> = ({ plugin }) => {
  const [showYaml, setShowYaml] = useState(false);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">{plugin.name}</h2>
          <span className="text-sm text-gray-400">v{plugin.version}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs ${domainColor(plugin.domain)}`}>
            {domainLabel(plugin.domain)}
          </span>
          {plugin.user_selectable === false && (
            <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">
              Internal utility
            </span>
          )}
        </div>
        <p className="mt-1 font-mono text-xs text-gray-400">{plugin.id}</p>
        <p className="mt-3 leading-relaxed text-gray-600">{plugin.description}</p>
      </div>

      {/* Container & Resources row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Box className="w-4 h-4 text-navy-600" />
            <span className="text-xs font-semibold text-gray-500 tracking-wide">Container</span>
          </div>
          <p className="text-sm text-gray-800 font-mono break-all">{plugin.container_image}</p>
          <p className="text-xs text-gray-400 mt-1">Runtime: {plugin.container_runtime || 'docker'}</p>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="w-4 h-4 text-navy-600" />
            <span className="text-xs font-semibold text-gray-500 tracking-wide">Default Resources</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {plugin.resources?.cpus && (
              <span className="text-xs bg-navy-50 text-navy-700 px-2 py-1 rounded font-medium">{plugin.resources.cpus} CPUs</span>
            )}
            {plugin.resources?.mem_gb && (
              <span className="text-xs bg-navy-50 text-navy-700 px-2 py-1 rounded font-medium">{plugin.resources.mem_gb} GB RAM</span>
            )}
            {plugin.resources?.memory_gb && !plugin.resources?.mem_gb && (
              <span className="text-xs bg-navy-50 text-navy-700 px-2 py-1 rounded font-medium">{plugin.resources.memory_gb} GB RAM</span>
            )}
            {plugin.resources?.time_hours && (
              <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded font-medium">{plugin.resources.time_hours}h limit</span>
            )}
            {(plugin.resources?.gpus > 0 || plugin.resources?.gpu) && (
              <span className="text-xs bg-navy-50 text-navy-700 px-2 py-1 rounded font-medium">GPU required</span>
            )}
          </div>
        </div>
      </div>

      {/* Input Data Format */}
      <InputFormatSection inputFormat={plugin.input_format} />

      {/* Inputs */}
      {plugin.inputs && (plugin.inputs.required?.length > 0 || plugin.inputs.optional?.length > 0) && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-3 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4" />
            Inputs
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {plugin.inputs.required?.map((inp: any, i: number) => (
              <div key={`req-${i}`} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-800">{inp.key}</span>
                  <span className="text-navy-500 text-xs font-bold">required</span>
                  <span className="text-xs text-gray-400 ml-auto">{inp.type}</span>
                </div>
                {inp.description && <p className="text-xs text-gray-500 mt-1">{inp.description}</p>}
              </div>
            ))}
            {plugin.inputs.optional?.map((inp: any, i: number) => (
              <div key={`opt-${i}`} className="bg-white border border-gray-100 rounded-lg px-3 py-2.5 opacity-80">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-700">{inp.key}</span>
                  <span className="text-xs text-gray-400">optional</span>
                  <span className="text-xs text-gray-400 ml-auto">{inp.type}</span>
                </div>
                {inp.description && <p className="text-xs text-gray-500 mt-1">{inp.description}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Parameters */}
      {plugin.parameters && plugin.parameters.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-3 flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            Parameters
          </h3>
          <div className="space-y-2">
            {plugin.parameters.map((param: any, i: number) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5 flex items-start gap-3">
                <code className="text-sm font-mono text-navy-600 font-medium whitespace-nowrap">{param.name}</code>
                <div className="flex-1 min-w-0">
                  {param.description && <p className="text-xs text-gray-500">{param.description}</p>}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs text-gray-400">{param.type}</span>
                  {param.default !== undefined && param.default !== null && (
                    <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                      ={String(param.default)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Authors & References */}
      {plugin.authors && plugin.authors.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-2">Authors</h3>
          <p className="text-sm text-gray-600">{plugin.authors.join(', ')}</p>
        </div>
      )}

      {plugin.references && plugin.references.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-2 flex items-center gap-1.5">
            <Shield className="w-4 h-4" />
            References
          </h3>
          <ul className="space-y-1 text-sm text-navy-600">
            {plugin.references.map((ref: string, i: number) => (
              <li key={i} className="break-all">
                {/^https?:\/\//i.test(ref) ? (
                  <a href={ref} target="_blank" rel="noreferrer" className="hover:underline">
                    {ref}
                  </a>
                ) : (
                  ref
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* YAML */}
      <div>
        <button
          onClick={() => setShowYaml(!showYaml)}
          className="flex items-center gap-1.5 text-sm text-navy-600 hover:text-navy-800 font-medium transition"
        >
          <FileText className="w-4 h-4" />
          {showYaml ? 'Hide YAML Definition' : 'View Full YAML Definition'}
        </button>
        {showYaml && (
          <pre className="mt-3 bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto max-h-[500px] overflow-y-auto font-mono leading-relaxed">
            {plugin.yaml}
          </pre>
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*  Workflow Detail                                                           */
/* -------------------------------------------------------------------------- */

const WorkflowDetail: React.FC<{ workflow: WorkflowDoc }> = ({ workflow }) => {
  const [showYaml, setShowYaml] = useState(false);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl font-bold text-gray-900">{workflow.name}</h2>
          <span className="text-sm text-gray-400">v{workflow.version}</span>
          <span className={`text-xs px-2.5 py-0.5 rounded-full ${domainColor(workflow.domain)}`}>
            {domainLabel(workflow.domain)}
          </span>
          <span className="text-xs text-gray-400">
            {workflow.steps?.length || 0} step{(workflow.steps?.length || 0) !== 1 ? 's' : ''}
          </span>
        </div>
        <code className="text-xs text-gray-400 mt-1 block">{workflow.id}</code>
        <p className="text-gray-600 mt-3 leading-relaxed">{workflow.description}</p>
      </div>

      {/* Pipeline Steps */}
      {workflow.steps && workflow.steps.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-3 flex items-center gap-1.5">
            <GitBranch className="w-4 h-4" />
            Pipeline Steps
          </h3>
          <div className="space-y-2">
            {workflow.steps.map((step: any, i: number) => (
              <div key={i} className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-4 py-3">
                <div className="w-7 h-7 rounded-full bg-navy-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium text-gray-800">
                    {step.plugin_name || step.label || step.uses}
                  </span>
                  {step.plugin_description && (
                    <p className="text-xs text-gray-500 mt-0.5">{step.plugin_description}</p>
                  )}
                </div>
                <code className="text-xs text-gray-400 flex-shrink-0">{step.uses}</code>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input Data Format */}
      <InputFormatSection inputFormat={workflow.input_format} />

      {/* Inputs */}
      {workflow.inputs && (workflow.inputs.required?.length > 0 || workflow.inputs.optional?.length > 0) && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-3 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4" />
            Inputs
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {workflow.inputs.required?.map((inp: any, i: number) => (
              <div key={`req-${i}`} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-800">{inp.key}</span>
                  <span className="text-navy-500 text-xs font-bold">required</span>
                  <span className="text-xs text-gray-400 ml-auto">{inp.type}</span>
                </div>
                {inp.description && <p className="text-xs text-gray-500 mt-1">{inp.description}</p>}
              </div>
            ))}
            {workflow.inputs.optional?.map((inp: any, i: number) => (
              <div key={`opt-${i}`} className="bg-white border border-gray-100 rounded-lg px-3 py-2.5 opacity-80">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-700">{inp.key}</span>
                  <span className="text-xs text-gray-400">optional</span>
                  <span className="text-xs text-gray-400 ml-auto">{inp.type}</span>
                </div>
                {inp.description && <p className="text-xs text-gray-500 mt-1">{inp.description}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Validation */}
      {workflow.validation?.preflight_checks && workflow.validation.preflight_checks.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 tracking-wide mb-2 flex items-center gap-1.5">
            <Shield className="w-4 h-4" />
            Preflight Validation
          </h3>
          <ul className="text-sm text-gray-700 space-y-1.5">
            {workflow.validation.preflight_checks.map((check: string, i: number) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-navy-600 rounded-full flex-shrink-0"></span>
                <code className="text-xs bg-gray-100 px-2 py-0.5 rounded">{check}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* YAML */}
      <div>
        <button
          onClick={() => setShowYaml(!showYaml)}
          className="flex items-center gap-1.5 text-sm text-navy-600 hover:text-navy-800 font-medium transition"
        >
          <FileText className="w-4 h-4" />
          {showYaml ? 'Hide YAML Definition' : 'View Full YAML Definition'}
        </button>
        {showYaml && (
          <pre className="mt-3 bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto max-h-[500px] overflow-y-auto font-mono leading-relaxed">
            {workflow.yaml}
          </pre>
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*  Main Page                                                                 */
/* -------------------------------------------------------------------------- */

type LicenseStatus = {
  freesurfer: { found: boolean; path: string | null; registration_url: string };
  meld_graph: { found: boolean; path: string | null; registration_url: string };
  hint: string;
};

const DocsPage: React.FC<DocsPageProps> = () => {
  const [plugins, setPlugins] = useState<PluginDoc[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plugins' | 'workflows'>('plugins');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showUtilities, setShowUtilities] = useState(false);
  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus | null>(null);

  const selectablePlugins = plugins.filter((p) => p.user_selectable !== false);

  const pickDefaultPluginId = (items: PluginDoc[]) => {
    const firstSelectable = items.find((p) => p.user_selectable !== false);
    return firstSelectable?.id ?? items[0]?.id ?? null;
  };

  useEffect(() => {
    async function fetchDocs() {
      try {
        const [data, licenseRes] = await Promise.all([
          apiService.getDocsAll(),
          apiService.getLicenseStatus().catch(() => null),
        ]);
        setPlugins(data.plugins || []);
        setWorkflows(data.workflows || []);
        if (licenseRes) {
          setLicenseStatus(licenseRes);
        }
        if (data.plugins?.length > 0) {
          setSelectedId(pickDefaultPluginId(data.plugins));
        }
      } catch (err: any) {
        setError('Could not load documentation. Make sure the backend is running.');
        console.error('Failed to load docs:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchDocs();
  }, []);

  const handleTabSwitch = (tab: 'plugins' | 'workflows') => {
    setActiveTab(tab);
    setSearchQuery('');
    if (tab === 'plugins' && plugins.length > 0) {
      setSelectedId(pickDefaultPluginId(plugins));
    } else if (tab === 'workflows' && workflows.length > 0) {
      setSelectedId(workflows[0].id);
    } else {
      setSelectedId(null);
    }
  };

  const matchesSearch = (text: string) => text.toLowerCase().includes(searchQuery.toLowerCase());

  const filteredPlugins = plugins.filter(
    (p) =>
      matchesSearch(p.name) ||
      matchesSearch(p.id) ||
      matchesSearch(p.description) ||
      matchesSearch(p.domain) ||
      matchesSearch(domainLabel(p.domain)),
  );

  const visiblePlugins = showUtilities
    ? filteredPlugins
    : filteredPlugins.filter((p) => p.user_selectable !== false);

  const filteredWorkflows = workflows.filter(
    (w) =>
      matchesSearch(w.name) ||
      matchesSearch(w.id) ||
      matchesSearch(w.description) ||
      matchesSearch(w.domain) ||
      matchesSearch(domainLabel(w.domain)),
  );

  const selectedPlugin = plugins.find((p) => p.id === selectedId) || null;
  const selectedWorkflow = workflows.find((w) => w.id === selectedId) || null;

  useEffect(() => {
    if (activeTab !== 'plugins' || showUtilities) return;
    if (selectedPlugin && selectedPlugin.user_selectable === false) {
      setSelectedId(pickDefaultPluginId(plugins));
    }
  }, [activeTab, showUtilities, selectedPlugin, plugins]);

  if (loading) {
    return (
      <div className="min-h-full bg-gray-50 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <LoadingState message="Loading pipeline catalog…" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col bg-gray-50">
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8">
        <WorkspacePageHeader
          title="Pipeline catalog"
          subtitle="Plugins run a single tool; workflows chain several plugins. Pick one to review inputs, resources, and specs."
          actions={
            <div className="flex flex-col items-end gap-2 sm:flex-row sm:items-center">
              {!error && (
                <div className="flex flex-wrap justify-end gap-1.5">
                  <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs text-gray-600">
                    {selectablePlugins.length} plugins · {workflows.length} workflows
                  </span>
                  {licenseStatus?.freesurfer.found && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-xs text-green-700">
                      <CheckCircle className="h-3 w-3" />
                      FreeSurfer
                    </span>
                  )}
                  {licenseStatus?.meld_graph.found && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-xs text-green-700">
                      <CheckCircle className="h-3 w-3" />
                      MELD
                    </span>
                  )}
                </div>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.open(USER_GUIDE_URL, '_blank', 'noopener,noreferrer')}
              >
                User guide
              </Button>
            </div>
          }
        />

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-navy-200 bg-navy-50 p-3">
            <AlertTriangle className="h-5 w-5 shrink-0 text-navy-600" />
            <span className="text-sm text-navy-800">{error}</span>
          </div>
        )}

        {licenseStatus && !error && (!licenseStatus.freesurfer.found || !licenseStatus.meld_graph.found) && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {!licenseStatus.freesurfer.found && (
              <p className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  FreeSurfer license not found — add <code className="rounded bg-white px-1 text-xs">license.txt</code> to the project root.
                </span>
              </p>
            )}
            {!licenseStatus.meld_graph.found && (
              <p className={`flex items-start gap-2 ${!licenseStatus.freesurfer.found ? 'mt-2' : ''}`}>
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  MELD license not found — add <code className="rounded bg-white px-1 text-xs">meld_license.txt</code> to the project root.
                </span>
              </p>
            )}
          </div>
        )}

        <div className="flex min-h-[calc(100vh-14rem)] flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          {/* Catalog sidebar */}
          <div className="flex w-80 shrink-0 flex-col border-r border-gray-200 xl:w-96">
            <div className="flex shrink-0 border-b border-gray-200">
              <button
                type="button"
                onClick={() => handleTabSwitch('plugins')}
                className={`flex flex-1 items-center justify-center gap-1.5 px-4 py-3 text-sm font-medium transition ${
                  activeTab === 'plugins'
                    ? 'border-b-2 border-navy-600 bg-navy-50/40 text-navy-700'
                    : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                }`}
              >
                <Zap className="h-4 w-4" />
                Plugins ({showUtilities ? plugins.length : selectablePlugins.length})
              </button>
              <button
                type="button"
                onClick={() => handleTabSwitch('workflows')}
                className={`flex flex-1 items-center justify-center gap-1.5 px-4 py-3 text-sm font-medium transition ${
                  activeTab === 'workflows'
                    ? 'border-b-2 border-navy-600 bg-navy-50/40 text-navy-700'
                    : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                }`}
              >
                <GitBranch className="h-4 w-4" />
                Workflows ({workflows.length})
              </button>
            </div>

            <div className="shrink-0 space-y-2 border-b border-gray-100 p-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="search"
                  placeholder="Search by name or domain…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 py-2 pl-8 pr-3 text-sm outline-none focus:border-navy-600 focus:ring-2 focus:ring-navy-600"
                />
              </div>
              {activeTab === 'plugins' && plugins.length > selectablePlugins.length && (
                <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-600">
                  <input
                    type="checkbox"
                    checked={showUtilities}
                    onChange={(e) => setShowUtilities(e.target.checked)}
                    className="rounded text-navy-600 focus:ring-navy-600"
                  />
                  Show internal utilities ({plugins.length - selectablePlugins.length})
                </label>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {activeTab === 'plugins' && (
                <>
                  {visiblePlugins.length === 0 && (
                    <div className="p-4 text-center text-sm text-gray-400">No plugins match your search.</div>
                  )}
                  {visiblePlugins.map((plugin) => (
                    <button
                      key={plugin.id}
                      type="button"
                      onClick={() => setSelectedId(plugin.id)}
                      className={`w-full border-b border-gray-50 px-4 py-3 text-left transition ${
                        selectedId === plugin.id
                          ? 'border-l-[3px] border-l-navy-600 bg-navy-50'
                          : 'border-l-[3px] border-l-transparent hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`text-sm font-medium ${
                            selectedId === plugin.id ? 'text-navy-700' : 'text-gray-800'
                          }`}
                        >
                          {plugin.name}
                        </span>
                        <ChevronRight
                          className={`h-4 w-4 shrink-0 ${
                            selectedId === plugin.id ? 'text-navy-600' : 'text-gray-300'
                          }`}
                        />
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${domainColor(plugin.domain)}`}>
                          {domainLabel(plugin.domain)}
                        </span>
                        {plugin.user_selectable === false && (
                          <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                            internal
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </>
              )}

              {activeTab === 'workflows' && (
                <>
                  {filteredWorkflows.length === 0 && (
                    <div className="p-4 text-center text-sm text-gray-400">No workflows match your search.</div>
                  )}
                  {filteredWorkflows.map((workflow) => (
                    <button
                      key={workflow.id}
                      type="button"
                      onClick={() => setSelectedId(workflow.id)}
                      className={`w-full border-b border-gray-50 px-4 py-3 text-left transition ${
                        selectedId === workflow.id
                          ? 'border-l-[3px] border-l-navy-600 bg-navy-50'
                          : 'border-l-[3px] border-l-transparent hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`text-sm font-medium ${
                            selectedId === workflow.id ? 'text-navy-700' : 'text-gray-800'
                          }`}
                        >
                          {workflow.name}
                        </span>
                        <ChevronRight
                          className={`h-4 w-4 shrink-0 ${
                            selectedId === workflow.id ? 'text-navy-600' : 'text-gray-300'
                          }`}
                        />
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${domainColor(workflow.domain)}`}>
                          {domainLabel(workflow.domain)}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {workflow.steps?.length || 0} steps
                        </span>
                      </div>
                    </button>
                  ))}
                </>
              )}
            </div>
          </div>

          {/* Detail */}
          <div className="min-h-0 min-w-0 flex-1 overflow-y-auto p-6">
            {activeTab === 'plugins' && selectedPlugin && (
              <PluginDetail key={selectedPlugin.id} plugin={selectedPlugin} />
            )}
            {activeTab === 'workflows' && selectedWorkflow && (
              <WorkflowDetail key={selectedWorkflow.id} workflow={selectedWorkflow} />
            )}
            {!selectedPlugin && activeTab === 'plugins' && (
              <div className="flex h-full flex-col items-center justify-center text-gray-400">
                <Zap className="mb-3 h-12 w-12 opacity-30" />
                <p>Select a plugin to view its specification</p>
              </div>
            )}
            {!selectedWorkflow && activeTab === 'workflows' && (
              <div className="flex h-full flex-col items-center justify-center text-gray-400">
                <GitBranch className="mb-3 h-12 w-12 opacity-30" />
                <p>Select a workflow to view its specification</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocsPage;
