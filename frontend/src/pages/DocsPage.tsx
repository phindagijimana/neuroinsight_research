/**
 * DocsPage Component
 * Browse and review all plugin and workflow YAML definitions.
 * Accessible at /docs in the navigation.
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import {
  FileText,
  Zap,
  GitBranch,
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
  Box,
  Cpu,
  Clock,
  HardDrive,
  Shield,
  AlertTriangle,
} from 'lucide-react';

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
  parameters: any[];
  resources: Record<string, any>;
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

const DocsPage: React.FC<DocsPageProps> = () => {
  const [plugins, setPlugins] = useState<PluginDoc[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plugins' | 'workflows'>('plugins');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showYaml, setShowYaml] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    async function fetchDocs() {
      try {
        const data = await apiService.getDocsAll();
        setPlugins(data.plugins || []);
        setWorkflows(data.workflows || []);
      } catch (err: any) {
        setError('Could not load documentation. Make sure the backend is running.');
        console.error('Failed to load docs:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchDocs();
  }, []);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
    setShowYaml(null);
  };

  const toggleYaml = (id: string) => {
    setShowYaml(showYaml === id ? null : id);
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <FileText className="w-8 h-8 text-[#003d7a]" />
          <h1 className="text-3xl font-bold text-gray-900">Plugin & Workflow Documentation</h1>
        </div>
        <p className="text-gray-600 ml-11">
          Browse all available plugins and workflows. Review their inputs, outputs, resource requirements, and full YAML definitions.
        </p>
        <div className="flex items-center gap-4 mt-3 ml-11 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <Zap className="w-4 h-4" />
            {plugins.length} plugins
          </span>
          <span className="flex items-center gap-1">
            <GitBranch className="w-4 h-4" />
            {workflows.length} workflows
          </span>
        </div>
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
          <span className="text-amber-800">{error}</span>
        </div>
      )}

      {/* Search + Tabs */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search plugins and workflows..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003d7a] focus:border-[#003d7a] outline-none"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('plugins')}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === 'plugins'
                ? 'bg-[#003d7a] text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <Zap className="w-4 h-4" />
            Plugins ({filteredPlugins.length})
          </button>
          <button
            onClick={() => setActiveTab('workflows')}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === 'workflows'
                ? 'bg-[#003d7a] text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <GitBranch className="w-4 h-4" />
            Workflows ({filteredWorkflows.length})
          </button>
        </div>
      </div>

      {/* Plugin List */}
      {activeTab === 'plugins' && (
        <div className="space-y-3">
          {filteredPlugins.map((plugin) => (
            <div key={plugin.id} className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              {/* Plugin Header */}
              <button
                onClick={() => toggleExpand(plugin.id)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition text-left"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {expandedId === plugin.id ? (
                    <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900">{plugin.name}</span>
                      <span className="text-xs text-gray-400">v{plugin.version}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${domainColor(plugin.domain)}`}>
                        {domainLabel(plugin.domain)}
                      </span>
                      {!plugin.user_selectable && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">
                          Utility (hidden)
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5 truncate">{plugin.description}</p>
                  </div>
                </div>
                <code className="text-xs text-gray-400 ml-4 flex-shrink-0 hidden sm:block">{plugin.id}</code>
              </button>

              {/* Plugin Details (expanded) */}
              {expandedId === plugin.id && (
                <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {/* Container */}
                    <div className="flex items-start gap-2">
                      <Box className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Container</span>
                        <p className="text-sm text-gray-800 font-mono">{plugin.container_image}</p>
                        <p className="text-xs text-gray-400">Runtime: {plugin.container_runtime}</p>
                      </div>
                    </div>

                    {/* Resources */}
                    <div className="flex items-start gap-2">
                      <Cpu className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Default Resources</span>
                        <div className="flex flex-wrap gap-2 mt-1">
                          {plugin.resources.cpus && (
                            <span className="text-xs bg-navy-50 text-navy-700 px-2 py-0.5 rounded">{plugin.resources.cpus} CPUs</span>
                          )}
                          {plugin.resources.mem_gb && (
                            <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded">{plugin.resources.mem_gb} GB RAM</span>
                          )}
                          {plugin.resources.time_hours && (
                            <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">{plugin.resources.time_hours}h time</span>
                          )}
                          {plugin.resources.gpus > 0 && (
                            <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">GPU required</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Inputs */}
                  <div className="mb-4">
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-2 flex items-center gap-1">
                      <HardDrive className="w-3.5 h-3.5" />
                      Inputs
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {plugin.inputs.required.map((inp: any, i: number) => (
                        <div key={i} className="text-sm bg-white border border-gray-200 rounded px-3 py-2">
                          <span className="font-medium text-gray-800">{inp.key}</span>
                          <span className="text-red-500 ml-1">*</span>
                          <span className="text-xs text-gray-400 ml-2">{inp.type}</span>
                          {inp.description && (
                            <p className="text-xs text-gray-500 mt-0.5">{inp.description}</p>
                          )}
                        </div>
                      ))}
                      {plugin.inputs.optional.map((inp: any, i: number) => (
                        <div key={i} className="text-sm bg-white border border-gray-100 rounded px-3 py-2 opacity-75">
                          <span className="text-gray-700">{inp.key}</span>
                          <span className="text-xs text-gray-400 ml-2">{inp.type}</span>
                          <span className="text-xs text-gray-400 ml-1">(optional)</span>
                          {inp.description && (
                            <p className="text-xs text-gray-500 mt-0.5">{inp.description}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* References */}
                  {plugin.references && plugin.references.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-xs font-medium text-gray-500 uppercase mb-1 flex items-center gap-1">
                        <Shield className="w-3.5 h-3.5" />
                        References
                      </h4>
                      <ul className="text-sm text-navy-600 space-y-0.5">
                        {plugin.references.map((ref: string, i: number) => (
                          <li key={i}>
                            <a href={ref} target="_blank" rel="noopener noreferrer" className="hover:underline break-all">
                              {ref}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* YAML Toggle */}
                  <button
                    onClick={() => toggleYaml(plugin.id)}
                    className="flex items-center gap-1 text-sm text-[#003d7a] hover:text-[#002b55] font-medium"
                  >
                    <FileText className="w-4 h-4" />
                    {showYaml === plugin.id ? 'Hide YAML Definition' : 'View Full YAML Definition'}
                  </button>

                  {showYaml === plugin.id && (
                    <div className="mt-3 relative">
                      <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto max-h-[500px] overflow-y-auto font-mono leading-relaxed">
                        {plugin.yaml}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Workflow List */}
      {activeTab === 'workflows' && (
        <div className="space-y-3">
          {filteredWorkflows.map((workflow) => (
            <div key={workflow.id} className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              {/* Workflow Header */}
              <button
                onClick={() => toggleExpand(workflow.id)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition text-left"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {expandedId === workflow.id ? (
                    <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900">{workflow.name}</span>
                      <span className="text-xs text-gray-400">v{workflow.version}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${domainColor(workflow.domain)}`}>
                        {domainLabel(workflow.domain)}
                      </span>
                      <span className="text-xs text-gray-400">
                        {workflow.steps.length} step{workflow.steps.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5 truncate">{workflow.description}</p>
                  </div>
                </div>
                <code className="text-xs text-gray-400 ml-4 flex-shrink-0 hidden sm:block">{workflow.id}</code>
              </button>

              {/* Workflow Details (expanded) */}
              {expandedId === workflow.id && (
                <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                  {/* Pipeline Steps */}
                  <div className="mb-4">
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-2 flex items-center gap-1">
                      <GitBranch className="w-3.5 h-3.5" />
                      Pipeline Steps
                    </h4>
                    <div className="space-y-2">
                      {workflow.steps.map((step: any, i: number) => (
                        <div key={i} className="flex items-center gap-3 bg-white border border-gray-200 rounded px-3 py-2">
                          <div className="w-6 h-6 rounded-full bg-[#003d7a] text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">
                            {i + 1}
                          </div>
                          <div className="min-w-0 flex-1">
                            <span className="text-sm font-medium text-gray-800">
                              {step.plugin_name || step.plugin_id}
                            </span>
                            {step.plugin_description && (
                              <p className="text-xs text-gray-500 truncate">{step.plugin_description}</p>
                            )}
                          </div>
                          <code className="text-xs text-gray-400 flex-shrink-0">{step.plugin_id}</code>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Inputs */}
                  <div className="mb-4">
                    <h4 className="text-xs font-medium text-gray-500 uppercase mb-2 flex items-center gap-1">
                      <HardDrive className="w-3.5 h-3.5" />
                      Inputs
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {workflow.inputs.required.map((inp: any, i: number) => (
                        <div key={i} className="text-sm bg-white border border-gray-200 rounded px-3 py-2">
                          <span className="font-medium text-gray-800">{inp.key}</span>
                          <span className="text-red-500 ml-1">*</span>
                          <span className="text-xs text-gray-400 ml-2">{inp.type}</span>
                          {inp.description && (
                            <p className="text-xs text-gray-500 mt-0.5">{inp.description}</p>
                          )}
                        </div>
                      ))}
                      {workflow.inputs.optional.map((inp: any, i: number) => (
                        <div key={i} className="text-sm bg-white border border-gray-100 rounded px-3 py-2 opacity-75">
                          <span className="text-gray-700">{inp.key}</span>
                          <span className="text-xs text-gray-400 ml-2">{inp.type}</span>
                          <span className="text-xs text-gray-400 ml-1">(optional)</span>
                          {inp.description && (
                            <p className="text-xs text-gray-500 mt-0.5">{inp.description}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Validation */}
                  {workflow.validation?.preflight_checks && workflow.validation.preflight_checks.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-xs font-medium text-gray-500 uppercase mb-2 flex items-center gap-1">
                        <Shield className="w-3.5 h-3.5" />
                        Preflight Validation Checks
                      </h4>
                      <ul className="text-sm text-gray-700 space-y-1">
                        {workflow.validation.preflight_checks.map((check: string, i: number) => (
                          <li key={i} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 bg-[#003d7a] rounded-full flex-shrink-0"></span>
                            <code className="text-xs bg-gray-100 px-2 py-0.5 rounded">{check}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* YAML Toggle */}
                  <button
                    onClick={() => toggleYaml(workflow.id)}
                    className="flex items-center gap-1 text-sm text-[#003d7a] hover:text-[#002b55] font-medium"
                  >
                    <FileText className="w-4 h-4" />
                    {showYaml === workflow.id ? 'Hide YAML Definition' : 'View Full YAML Definition'}
                  </button>

                  {showYaml === workflow.id && (
                    <div className="mt-3 relative">
                      <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto max-h-[500px] overflow-y-auto font-mono leading-relaxed">
                        {workflow.yaml}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Quick Reference */}
      <div className="mt-8 bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">Quick Reference</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600">
          <div>
            <span className="font-medium text-[#003d7a]">Plugin</span> — A wrapper around one neuroimaging tool
            (e.g., FreeSurfer, fMRIPrep). Runs a single pipeline step using an official Docker container.
            Plugins encode <em>execution</em>.
          </div>
          <div>
            <span className="font-medium text-[#003d7a]">Workflow</span> — A reproducible sequence of plugins
            that encodes best practice (e.g., fMRIPrep then XCP-D). Workflows enforce execution order,
            pass outputs between steps, and encode <em>scientific intent</em>.
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocsPage;
