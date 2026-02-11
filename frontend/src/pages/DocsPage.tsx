/**
 * DocsPage Component
 * Browse and review all plugin and workflow YAML definitions.
 * Master-detail layout: scrollable list on the left, selected item detail on the right.
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import {
  FileText,
  Zap,
  GitBranch,
  Loader2,
  Search,
  Box,
  Cpu,
  Clock,
  HardDrive,
  Shield,
  AlertTriangle,
  ChevronRight,
  FolderTree,
} from 'lucide-react';

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
    case 'functional_mri': return 'bg-purple-100 text-purple-800';
    case 'diffusion_mri': return 'bg-green-100 text-green-800';
    case 'epilepsy': return 'bg-red-100 text-red-800';
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
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <FolderTree className="w-4 h-4" />
        Input Data Format
      </h3>
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
        {/* Format name & description */}
        {inputFormat.format_name && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-[#003d7a]">{inputFormat.format_name}</span>
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
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl font-bold text-gray-900">{plugin.name}</h2>
          <span className="text-sm text-gray-400">v{plugin.version}</span>
          <span className={`text-xs px-2.5 py-0.5 rounded-full ${domainColor(plugin.domain)}`}>
            {domainLabel(plugin.domain)}
          </span>
          {!plugin.user_selectable && (
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-orange-100 text-orange-700">
              Utility (hidden)
            </span>
          )}
        </div>
        <code className="text-xs text-gray-400 mt-1 block">{plugin.id}</code>
        <p className="text-gray-600 mt-3 leading-relaxed">{plugin.description}</p>
      </div>

      {/* Container & Resources row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Box className="w-4 h-4 text-[#003d7a]" />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Container</span>
          </div>
          <p className="text-sm text-gray-800 font-mono break-all">{plugin.container_image}</p>
          <p className="text-xs text-gray-400 mt-1">Runtime: {plugin.container_runtime || 'docker'}</p>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="w-4 h-4 text-[#003d7a]" />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Default Resources</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {plugin.resources?.cpus && (
              <span className="text-xs bg-navy-50 text-navy-700 px-2 py-1 rounded font-medium">{plugin.resources.cpus} CPUs</span>
            )}
            {plugin.resources?.mem_gb && (
              <span className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded font-medium">{plugin.resources.mem_gb} GB RAM</span>
            )}
            {plugin.resources?.memory_gb && !plugin.resources?.mem_gb && (
              <span className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded font-medium">{plugin.resources.memory_gb} GB RAM</span>
            )}
            {plugin.resources?.time_hours && (
              <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded font-medium">{plugin.resources.time_hours}h limit</span>
            )}
            {(plugin.resources?.gpus > 0 || plugin.resources?.gpu) && (
              <span className="text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded font-medium">GPU required</span>
            )}
          </div>
        </div>
      </div>

      {/* Input Data Format */}
      <InputFormatSection inputFormat={plugin.input_format} />

      {/* Inputs */}
      {plugin.inputs && (plugin.inputs.required?.length > 0 || plugin.inputs.optional?.length > 0) && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4" />
            Inputs
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {plugin.inputs.required?.map((inp: any, i: number) => (
              <div key={`req-${i}`} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-800">{inp.key}</span>
                  <span className="text-red-500 text-xs font-bold">required</span>
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            Parameters
          </h3>
          <div className="space-y-2">
            {plugin.parameters.map((param: any, i: number) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5 flex items-start gap-3">
                <code className="text-sm font-mono text-[#003d7a] font-medium whitespace-nowrap">{param.name}</code>
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Authors</h3>
          <p className="text-sm text-gray-600">{plugin.authors.join(', ')}</p>
        </div>
      )}

      {plugin.references && plugin.references.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Shield className="w-4 h-4" />
            References
          </h3>
          <ul className="text-sm text-navy-600 space-y-1">
            {plugin.references.map((ref: string, i: number) => (
              <li key={i} className="break-all">{ref}</li>
            ))}
          </ul>
        </div>
      )}

      {/* YAML */}
      <div>
        <button
          onClick={() => setShowYaml(!showYaml)}
          className="flex items-center gap-1.5 text-sm text-[#003d7a] hover:text-[#002b55] font-medium transition"
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <GitBranch className="w-4 h-4" />
            Pipeline Steps
          </h3>
          <div className="space-y-2">
            {workflow.steps.map((step: any, i: number) => (
              <div key={i} className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-4 py-3">
                <div className="w-7 h-7 rounded-full bg-[#003d7a] text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <HardDrive className="w-4 h-4" />
            Inputs
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {workflow.inputs.required?.map((inp: any, i: number) => (
              <div key={`req-${i}`} className="bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-800">{inp.key}</span>
                  <span className="text-red-500 text-xs font-bold">required</span>
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Shield className="w-4 h-4" />
            Preflight Validation
          </h3>
          <ul className="text-sm text-gray-700 space-y-1.5">
            {workflow.validation.preflight_checks.map((check: string, i: number) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-[#003d7a] rounded-full flex-shrink-0"></span>
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
          className="flex items-center gap-1.5 text-sm text-[#003d7a] hover:text-[#002b55] font-medium transition"
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

const DocsPage: React.FC<DocsPageProps> = () => {
  const [plugins, setPlugins] = useState<PluginDoc[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plugins' | 'workflows'>('plugins');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    async function fetchDocs() {
      try {
        const data = await apiService.getDocsAll();
        setPlugins(data.plugins || []);
        setWorkflows(data.workflows || []);
        // Auto-select first plugin
        if (data.plugins?.length > 0) {
          setSelectedId(data.plugins[0].id);
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

  // When switching tabs, auto-select first item in new tab
  const handleTabSwitch = (tab: 'plugins' | 'workflows') => {
    setActiveTab(tab);
    setSearchQuery('');
    if (tab === 'plugins' && plugins.length > 0) {
      setSelectedId(plugins[0].id);
    } else if (tab === 'workflows' && workflows.length > 0) {
      setSelectedId(workflows[0].id);
    } else {
      setSelectedId(null);
    }
  };

  const filteredPlugins = plugins.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.domain.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredWorkflows = workflows.filter(
    (w) =>
      w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.domain.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedPlugin = plugins.find((p) => p.id === selectedId) || null;
  const selectedWorkflow = workflows.find((w) => w.id === selectedId) || null;

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-[#003d7a] mr-3" />
          <span className="text-gray-600 text-lg">Loading documentation...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 h-full flex flex-col">
      {/* Header */}
      <div className="mb-6 flex-shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <FileText className="w-7 h-7 text-[#003d7a]" />
          <h1 className="text-2xl font-bold text-gray-900">Documentation</h1>
        </div>
        <p className="text-gray-500 text-sm ml-10">
          Browse plugins and workflows. Select one to view its full specification.
        </p>
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-center gap-2 flex-shrink-0">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <span className="text-amber-800 text-sm">{error}</span>
        </div>
      )}

      {/* Main layout: sidebar + detail */}
      <div className="flex gap-6 flex-1 min-h-0">
        {/* Sidebar */}
        <div className="w-80 flex-shrink-0 flex flex-col bg-white border border-gray-200 rounded-lg overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-gray-200 flex-shrink-0">
            <button
              onClick={() => handleTabSwitch('plugins')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition flex items-center justify-center gap-1.5 ${
                activeTab === 'plugins'
                  ? 'text-[#003d7a] border-b-2 border-[#003d7a] bg-navy-50/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Zap className="w-4 h-4" />
              Plugins ({plugins.length})
            </button>
            <button
              onClick={() => handleTabSwitch('workflows')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition flex items-center justify-center gap-1.5 ${
                activeTab === 'workflows'
                  ? 'text-[#003d7a] border-b-2 border-[#003d7a] bg-navy-50/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <GitBranch className="w-4 h-4" />
              Workflows ({workflows.length})
            </button>
          </div>

          {/* Search */}
          <div className="p-3 border-b border-gray-100 flex-shrink-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder={`Search ${activeTab}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#003d7a] focus:border-[#003d7a] outline-none"
              />
            </div>
          </div>

          {/* Scrollable list */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'plugins' && (
              <>
                {filteredPlugins.length === 0 && (
                  <div className="p-4 text-sm text-gray-400 text-center">No plugins match your search.</div>
                )}
                {filteredPlugins.map((plugin) => (
                  <button
                    key={plugin.id}
                    onClick={() => setSelectedId(plugin.id)}
                    className={`w-full text-left px-4 py-3 border-b border-gray-50 transition ${
                      selectedId === plugin.id
                        ? 'bg-navy-50 border-l-[3px] border-l-[#003d7a]'
                        : 'hover:bg-gray-50 border-l-[3px] border-l-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-medium ${selectedId === plugin.id ? 'text-[#003d7a]' : 'text-gray-800'}`}>
                        {plugin.name}
                      </span>
                      <ChevronRight className={`w-4 h-4 flex-shrink-0 ${selectedId === plugin.id ? 'text-[#003d7a]' : 'text-gray-300'}`} />
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${domainColor(plugin.domain)}`}>
                        {domainLabel(plugin.domain)}
                      </span>
                      {!plugin.user_selectable && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-600">utility</span>
                      )}
                    </div>
                  </button>
                ))}
              </>
            )}

            {activeTab === 'workflows' && (
              <>
                {filteredWorkflows.length === 0 && (
                  <div className="p-4 text-sm text-gray-400 text-center">No workflows match your search.</div>
                )}
                {filteredWorkflows.map((workflow) => (
                  <button
                    key={workflow.id}
                    onClick={() => setSelectedId(workflow.id)}
                    className={`w-full text-left px-4 py-3 border-b border-gray-50 transition ${
                      selectedId === workflow.id
                        ? 'bg-navy-50 border-l-[3px] border-l-[#003d7a]'
                        : 'hover:bg-gray-50 border-l-[3px] border-l-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-medium ${selectedId === workflow.id ? 'text-[#003d7a]' : 'text-gray-800'}`}>
                        {workflow.name}
                      </span>
                      <ChevronRight className={`w-4 h-4 flex-shrink-0 ${selectedId === workflow.id ? 'text-[#003d7a]' : 'text-gray-300'}`} />
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${domainColor(workflow.domain)}`}>
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

        {/* Detail panel */}
        <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-y-auto p-6 min-h-0">
          {activeTab === 'plugins' && selectedPlugin && (
            <PluginDetail key={selectedPlugin.id} plugin={selectedPlugin} />
          )}
          {activeTab === 'workflows' && selectedWorkflow && (
            <WorkflowDetail key={selectedWorkflow.id} workflow={selectedWorkflow} />
          )}
          {!selectedPlugin && activeTab === 'plugins' && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <Zap className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-lg">Select a plugin to view its details</p>
            </div>
          )}
          {!selectedWorkflow && activeTab === 'workflows' && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <GitBranch className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-lg">Select a workflow to view its details</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Reference footer */}
      <div className="mt-4 flex-shrink-0 bg-gray-50 border border-gray-200 rounded-lg px-5 py-3">
        <div className="flex gap-8 text-sm text-gray-500">
          <div>
            <span className="font-medium text-[#003d7a]">Plugin</span> — Wraps one neuroimaging tool in a Docker container. Encodes <em>execution</em>.
          </div>
          <div>
            <span className="font-medium text-[#003d7a]">Workflow</span> — Chains plugins into a reproducible sequence. Encodes <em>scientific intent</em>.
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocsPage;
