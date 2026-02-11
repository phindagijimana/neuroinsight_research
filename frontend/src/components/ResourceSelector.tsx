/**
 * ResourceSelector Component
 *
 * Full resource configuration panel: CPU, RAM, GPU, parallelization.
 * Detects host machine limits, shows plugin resource profiles, and
 * allows users to customize with sliders and inputs.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Cpu, HardDrive, Clock, Zap, Layers, Settings2, AlertTriangle, ChevronDown } from 'lucide-react';
import type { SystemResources, ResourceProfile, ParallelizationInfo } from '../types';
import { apiService } from '../services/api';

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface ResourceConfig {
  memory_gb: number;
  cpus: number;
  time_hours: number;
  gpu: boolean;
  threads: number;
  omp_nthreads: number;
  parallel: boolean;
  // HPC / SLURM
  partition?: string;
  qos?: string;
  account?: string;
  nodes?: number;
}

interface PluginResources {
  /** Default flat resources from the plugin */
  resources?: Record<string, any>;
  /** All named profiles (default, cpu_only, …) */
  resource_profiles?: Record<string, ResourceProfile>;
  /** Parallelization capabilities */
  parallelization?: ParallelizationInfo;
}

interface ResourceSelectorProps {
  plugin: PluginResources | null;
  backendType: 'local' | 'hpc';
  onResourcesChange: (resources: ResourceConfig) => void;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const profileLabel = (name: string) =>
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/* ─── Component ──────────────────────────────────────────────────────────── */

export const ResourceSelector: React.FC<ResourceSelectorProps> = ({
  plugin,
  backendType,
  onResourcesChange,
}) => {
  /* ── State ─────────────────────────────────────────────────────────────── */
  const [systemRes, setSystemRes] = useState<SystemResources | null>(null);
  const [activeProfile, setActiveProfile] = useState<string>('default');
  const [useCustom, setUseCustom] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [resources, setResources] = useState<ResourceConfig>({
    memory_gb: 16, cpus: 4, time_hours: 6, gpu: false,
    threads: 4, omp_nthreads: 4, parallel: true,
  });

  /* ── Fetch system resources once ───────────────────────────────────────── */
  useEffect(() => {
    apiService.getSystemResources()
      .then(setSystemRes)
      .catch(() => setSystemRes(null));
  }, []);

  /* ── Derived limits ────────────────────────────────────────────────────── */
  const limits = useMemo(() => ({
    maxCpus:   systemRes?.limits.max_cpus      ?? 32,
    maxMemGb:  systemRes?.limits.max_memory_gb ?? 128,
    gpuAvail:  systemRes?.limits.gpu_available ?? false,
    gpuCount:  systemRes?.limits.gpu_count     ?? 0,
  }), [systemRes]);

  /* ── Profiles ──────────────────────────────────────────────────────────── */
  const profiles = plugin?.resource_profiles ?? {};
  const profileNames = Object.keys(profiles);
  const para = plugin?.parallelization;

  /* ── Build ResourceConfig from a profile ───────────────────────────────── */
  const configFromProfile = (prof: ResourceProfile): ResourceConfig => {
    const cpus = clamp(prof.cpus, 1, limits.maxCpus);
    return {
      memory_gb: clamp(prof.mem_gb, 1, limits.maxMemGb),
      cpus,
      time_hours: prof.time_hours,
      gpu: (prof.gpus ?? 0) > 0 && limits.gpuAvail,
      threads: cpus,
      omp_nthreads: Math.min(4, cpus),
      parallel: true,
    };
  };

  /* ── Initialise from plugin defaults ───────────────────────────────────── */
  useEffect(() => {
    if (!plugin) return;
    const prof = profiles[activeProfile] ?? profiles['default'];
    if (prof) {
      const cfg = configFromProfile(prof);
      setResources(cfg);
      onResourcesChange(cfg);
    } else if (plugin.resources) {
      // Fallback: flat resources object
      const r = plugin.resources;
      const cpus = clamp(r.cpus ?? 4, 1, limits.maxCpus);
      const cfg: ResourceConfig = {
        memory_gb: clamp(r.memory_gb ?? r.mem_gb ?? 16, 1, limits.maxMemGb),
        cpus,
        time_hours: r.time_hours ?? 6,
        gpu: !!(r.gpu ?? ((r.gpus ?? 0) > 0)) && limits.gpuAvail,
        threads: cpus,
        omp_nthreads: Math.min(4, cpus),
        parallel: true,
      };
      setResources(cfg);
      onResourcesChange(cfg);
    }
  }, [plugin, activeProfile, limits.maxCpus, limits.maxMemGb, limits.gpuAvail]);

  /* ── Updater ───────────────────────────────────────────────────────────── */
  const update = (key: keyof ResourceConfig, value: any) => {
    setResources((prev) => {
      const next = { ...prev, [key]: value };
      // Auto-sync threads when cpus change (unless user overrode)
      if (key === 'cpus' && !showAdvanced) {
        next.threads = value;
        next.omp_nthreads = Math.min(4, value);
      }
      onResourcesChange(next);
      return next;
    });
  };

  const resetToProfile = (profName: string) => {
    const prof = profiles[profName];
    if (prof) {
      const cfg = configFromProfile(prof);
      setResources(cfg);
      onResourcesChange(cfg);
      setActiveProfile(profName);
      setUseCustom(false);
      setShowAdvanced(false);
    }
  };

  if (!plugin) return null;

  /* ── Warning flags ─────────────────────────────────────────────────────── */
  const overCpu = resources.cpus > limits.maxCpus;
  const overMem = resources.memory_gb > limits.maxMemGb;
  const gpuNeededButMissing = resources.gpu && !limits.gpuAvail;

  /* ─────────────────────────────────────────────────────────────────────── */
  /*  RENDER                                                                 */
  /* ─────────────────────────────────────────────────────────────────────── */
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full flex flex-col gap-4">
      {/* Header + customize toggle */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
          <Settings2 className="h-4 w-4 text-[#003d7a]" />
          Resource Configuration
        </h3>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={useCustom}
            onChange={(e) => {
              setUseCustom(e.target.checked);
              if (!e.target.checked) resetToProfile(activeProfile);
            }}
            className="rounded border-gray-300 text-[#003d7a] focus:ring-[#003d7a]"
          />
          <span className="text-gray-600">Customize</span>
        </label>
      </div>

      {/* System capacity bar */}
      {systemRes && (
        <div className="flex gap-3 text-[10px] text-gray-400 border-b border-gray-100 pb-2">
          <span>Host: {systemRes.cpu.total_logical} CPUs</span>
          <span>{systemRes.memory.total_gb} GB RAM</span>
          {systemRes.gpu.available ? (
            <span className="text-emerald-500">
              GPU {systemRes.gpu.devices?.[0]?.name ?? 'available'}
            </span>
          ) : (
            <span>No GPU</span>
          )}
        </div>
      )}

      {/* ── Profile selector (only if multiple profiles) ──────────────── */}
      {profileNames.length > 1 && (
        <div>
          <label className="text-[11px] font-medium text-gray-500 mb-1 block">
            Resource Profile
          </label>
          <div className="flex gap-1.5 flex-wrap">
            {profileNames.map((name) => (
              <button
                key={name}
                onClick={() => resetToProfile(name)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-all ${
                  activeProfile === name
                    ? 'bg-[#003d7a] text-white border-[#003d7a]'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                }`}
              >
                {profileLabel(name)}
                {profiles[name]?.gpus > 0 && (
                  <Zap className="inline h-3 w-3 ml-1 -mt-0.5" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Read-only mode ────────────────────────────────────────────── */}
      {!useCustom ? (
        <div className="space-y-2">
          <Row icon={<HardDrive />} label="Memory"    value={`${resources.memory_gb} GB`} />
          <Row icon={<Cpu />}       label="CPUs"       value={`${resources.cpus} cores`} />
          <Row icon={<Clock />}     label="Time limit" value={`${resources.time_hours} h`} />
          {resources.gpu && <Row icon={<Zap />} label="GPU" value="Enabled" accent />}
          {para?.supports_threading && (
            <Row icon={<Layers />} label="Threads" value={`${resources.threads}`} />
          )}
          <p className="text-[10px] text-gray-400 pt-1">
            Using {profileLabel(activeProfile)} profile. Check "Customize" to adjust.
          </p>
        </div>
      ) : (
        /* ── Editable mode ──────────────────────────────────────────── */
        <div className="space-y-3">
          {/* Memory */}
          <SliderField
            icon={<HardDrive className="h-4 w-4 text-[#003d7a]" />}
            label="Memory (GB)"
            value={resources.memory_gb}
            min={1} max={limits.maxMemGb} step={1}
            onChange={(v) => update('memory_gb', v)}
            warn={overMem}
            hint={`Host max: ${limits.maxMemGb} GB`}
          />

          {/* CPUs */}
          <SliderField
            icon={<Cpu className="h-4 w-4 text-[#003d7a]" />}
            label="CPU Cores"
            value={resources.cpus}
            min={1} max={limits.maxCpus} step={1}
            onChange={(v) => update('cpus', v)}
            warn={overCpu}
            hint={`Host max: ${limits.maxCpus}`}
          />

          {/* Time */}
          <SliderField
            icon={<Clock className="h-4 w-4 text-[#003d7a]" />}
            label="Time Limit (hours)"
            value={resources.time_hours}
            min={1} max={168} step={1}
            onChange={(v) => update('time_hours', v)}
            hint="Max walltime for the job"
          />

          {/* GPU — always visible, disabled if not available */}
          <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-md">
            <div className="flex items-center gap-2">
              <Zap className={`h-4 w-4 ${limits.gpuAvail ? 'text-[#003d7a]' : 'text-gray-300'}`} />
              <span className="text-sm text-gray-700">GPU Acceleration</span>
            </div>
            <div className="flex items-center gap-2">
              {!limits.gpuAvail && (
                <span className="text-[10px] text-gray-400">Not available</span>
              )}
              <input
                type="checkbox"
                checked={resources.gpu}
                disabled={!limits.gpuAvail}
                onChange={(e) => update('gpu', e.target.checked)}
                className="rounded border-gray-300 text-[#003d7a] focus:ring-[#003d7a] disabled:opacity-40"
              />
            </div>
          </div>
          {gpuNeededButMissing && (
            <p className="text-[10px] text-amber-600 flex items-center gap-1 -mt-1 ml-1">
              <AlertTriangle className="h-3 w-3" />
              GPU requested but no GPU detected on this host.
            </p>
          )}
          {para?.gpu_optional && limits.gpuAvail && !resources.gpu && (
            <p className="text-[10px] text-navy-500 -mt-1 ml-1">
              This plugin supports GPU acceleration for faster processing.
            </p>
          )}

          {/* ── Advanced: Parallelization ───────────────────────────── */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 pt-1"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            Parallelization Settings
          </button>

          {showAdvanced && (
            <div className="space-y-3 pl-2 border-l-2 border-navy-100">
              {/* Parallel toggle */}
              <div className="flex items-center justify-between py-1.5 px-3 bg-navy-50/50 rounded-md">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-[#003d7a]" />
                  <span className="text-sm text-gray-700">Enable Parallelization</span>
                </div>
                <input
                  type="checkbox"
                  checked={resources.parallel}
                  onChange={(e) => update('parallel', e.target.checked)}
                  className="rounded border-gray-300 text-[#003d7a] focus:ring-[#003d7a]"
                />
              </div>

              {resources.parallel && (
                <>
                  {/* Threads */}
                  <SliderField
                    icon={<Layers className="h-4 w-4 text-navy-500" />}
                    label="Processing Threads"
                    value={resources.threads}
                    min={1}
                    max={para?.max_useful_cpus ?? resources.cpus}
                    step={1}
                    onChange={(v) => update('threads', v)}
                    hint={
                      para?.supports_threading
                        ? `Controls --nthreads / -openmp (max useful: ${para.max_useful_cpus ?? resources.cpus})`
                        : 'Thread count for parallel stages'
                    }
                  />

                  {/* OMP threads */}
                  {para?.supports_openmp && (
                    <SliderField
                      icon={<Layers className="h-4 w-4 text-[#003d7a]" />}
                      label="OpenMP Threads"
                      value={resources.omp_nthreads}
                      min={1}
                      max={Math.min(8, resources.cpus)}
                      step={1}
                      onChange={(v) => update('omp_nthreads', v)}
                      hint="Per-process thread pool (--omp-nthreads). Keep low for multi-process pipelines."
                    />
                  )}
                </>
              )}

              {!resources.parallel && (
                <p className="text-[10px] text-gray-400 ml-1">
                  Pipeline will run single-threaded. Enable to use multiple CPU cores.
                </p>
              )}
            </div>
          )}

          {/* HPC options */}
          {backendType === 'hpc' && (
            <div className="pt-3 border-t border-gray-200 space-y-2">
              <h4 className="text-xs font-semibold text-gray-700">HPC / SLURM Options</h4>
              <TextInput label="Partition" value={resources.partition ?? ''}
                placeholder="e.g., general, gpu, bigmem"
                onChange={(v) => update('partition', v || undefined)} />
              <TextInput label="QoS" value={resources.qos ?? ''}
                placeholder="e.g., normal, high"
                onChange={(v) => update('qos', v || undefined)} />
              <TextInput label="Account" value={resources.account ?? ''}
                placeholder="e.g., lab_account"
                onChange={(v) => update('account', v || undefined)} />
            </div>
          )}

          {/* Reset */}
          <button
            onClick={() => resetToProfile(activeProfile)}
            className="w-full py-1.5 text-xs border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50"
          >
            Reset to {profileLabel(activeProfile)} Defaults
          </button>
        </div>
      )}

      {/* Warnings */}
      {useCustom && (overCpu || overMem) && (
        <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-md flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-[11px] text-amber-800">
            {overCpu && overMem
              ? 'CPU and memory exceed host capacity. Job may fail or be very slow.'
              : overCpu
              ? 'CPU count exceeds host capacity. Job performance may degrade.'
              : 'Memory exceeds host capacity. Job may be killed by the OS.'}
          </p>
        </div>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════════════════════ */

/** Read-only resource row */
const Row: React.FC<{
  icon: React.ReactElement;
  label: string;
  value: string;
  accent?: boolean;
}> = ({ icon, label, value, accent }) => (
  <div className="flex items-center justify-between py-1.5 px-3 bg-navy-50/60 rounded-md">
    <div className="flex items-center gap-2">
      {React.cloneElement(icon, { className: `h-4 w-4 ${accent ? 'text-amber-500' : 'text-[#003d7a]'}` })}
      <span className="text-sm text-gray-700">{label}</span>
    </div>
    <span className={`text-sm font-medium ${accent ? 'text-amber-600' : 'text-gray-900'}`}>{value}</span>
  </div>
);

/** Slider + number input field */
const SliderField: React.FC<{
  icon: React.ReactElement;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  hint?: string;
  warn?: boolean;
}> = ({ icon, label, value, min, max, step, onChange, hint, warn }) => (
  <div>
    <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
      {icon}
      {label}
    </label>
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min} max={max} step={step}
        value={Math.min(value, max)}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 h-1.5 accent-[#003d7a] cursor-pointer"
      />
      <input
        type="number"
        min={min} max={999} step={step}
        value={value}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (!isNaN(v) && v >= min) onChange(v);
        }}
        className={`w-16 px-2 py-1 text-sm text-center border rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a] ${
          warn ? 'border-amber-400 bg-amber-50' : 'border-gray-300'
        }`}
      />
    </div>
    {hint && <p className="text-[10px] text-gray-400 mt-0.5">{hint}</p>}
  </div>
);

/** Text input for HPC options */
const TextInput: React.FC<{
  label: string;
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
}> = ({ label, value, placeholder, onChange }) => (
  <div>
    <label className="block text-xs text-gray-600 mb-0.5">{label}</label>
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a]"
    />
  </div>
);
