/**
 * Explains how EEG signal, cortical source map, and MRI connect in Multimodal View.
 */

import { Activity, ArrowDown, ArrowRight, Brain, Layers } from 'lucide-react';
import type { MultimodalManifest } from '../types';

function baseName(p: string): string {
  const s = p.replace(/\\/g, '/');
  const i = s.lastIndexOf('/');
  return i >= 0 ? s.slice(i + 1) : s;
}

interface MultimodalLinkageCardProps {
  manifest: MultimodalManifest;
  /** Currently opened EEG path in the viewer (may match manifest.eeg_file). */
  eegOpenPath?: string | null;
}

const MultimodalLinkageCard: React.FC<MultimodalLinkageCardProps> = ({
  manifest,
  eegOpenPath,
}) => {
  const L = manifest.linkage;
  const eegLabel = baseName(L?.eeg_file ?? manifest.eeg_file ?? eegOpenPath ?? '—');
  const mriLabel = baseName(L?.mri_ref ?? manifest.mri_ref ?? '—');
  const method = manifest.inverse_method ?? '—';
  const space = manifest.space ?? '—';

  return (
    <div className="rounded-lg border border-navy-600/25 bg-gradient-to-b from-navy-600/[0.06] to-gray-50/80 p-3 space-y-3">
      <div>
        <h3 className="text-xs font-semibold text-navy-600 tracking-wide">
          EEG ↔ MRI (source localization)
        </h3>
        <p className="text-xs text-gray-600 mt-1">
          How signal, cortical map, and anatomy are tied together in this job.
        </p>
      </div>

      {/* Desktop: horizontal flow; mobile: vertical */}
      <div className="flex flex-col sm:flex-row sm:items-stretch sm:justify-between gap-2 sm:gap-1">
        <div className="flex-1 min-w-0 rounded-md border border-gray-200 bg-white p-2.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-800">
            <Activity className="w-4 h-4 text-navy-600 shrink-0" aria-hidden />
            EEG (signal)
          </div>
          <p className="text-xs font-mono text-gray-700 truncate mt-1.5" title={eegLabel}>
            {eegLabel}
          </p>
        </div>

        <div className="hidden sm:flex flex-col items-center justify-center text-navy-600 px-0.5 shrink-0">
          <ArrowRight className="w-5 h-5" aria-hidden />
          <span className="text-[10px] text-center text-gray-500 max-w-[4.5rem] leading-tight mt-0.5">
            time → source
          </span>
        </div>
        <div className="flex sm:hidden flex-row items-center justify-center text-navy-600 py-0.5">
          <ArrowDown className="w-5 h-5" aria-hidden />
          <span className="text-[10px] text-gray-500 ml-2">time → source</span>
        </div>

        <div className="flex-1 min-w-0 rounded-md border border-gray-200 bg-white p-2.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-800">
            <Brain className="w-4 h-4 text-navy-600 shrink-0" aria-hidden />
            Cortical source
          </div>
          <p className="text-xs text-gray-600 mt-1.5">
            <span className="text-gray-500">Method:</span> {method}
          </p>
          <p className="text-xs text-gray-600">
            <span className="text-gray-500">Space:</span> {space}
          </p>
        </div>

        <div className="hidden sm:flex flex-col items-center justify-center text-navy-600 px-0.5 shrink-0">
          <ArrowRight className="w-5 h-5" aria-hidden />
          <span className="text-[10px] text-center text-gray-500 max-w-[4.5rem] leading-tight mt-0.5">
            anatomy
          </span>
        </div>
        <div className="flex sm:hidden flex-row items-center justify-center text-navy-600 py-0.5">
          <ArrowDown className="w-5 h-5" aria-hidden />
          <span className="text-[10px] text-gray-500 ml-2">anatomy</span>
        </div>

        <div className="flex-1 min-w-0 rounded-md border border-gray-200 bg-white p-2.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-800">
            <Layers className="w-4 h-4 text-navy-600 shrink-0" aria-hidden />
            MRI (Imaging View)
          </div>
          <p className="text-xs font-mono text-gray-700 truncate mt-1.5" title={mriLabel}>
            {mriLabel}
          </p>
        </div>
      </div>

      {(L?.registration || L?.signal_to_source || L?.source_to_anatomy) && (
        <dl className="text-xs text-gray-700 space-y-2 border-t border-gray-200/80 pt-2">
          {L.registration && (
            <div>
              <dt className="font-medium text-gray-800">Registration / coregistration</dt>
              <dd className="text-gray-600 mt-0.5 leading-relaxed">{L.registration}</dd>
            </div>
          )}
          {L.signal_to_source && (
            <div>
              <dt className="font-medium text-gray-800">Signal → source map</dt>
              <dd className="text-gray-600 mt-0.5 leading-relaxed">{L.signal_to_source}</dd>
            </div>
          )}
          {L.source_to_anatomy && (
            <div>
              <dt className="font-medium text-gray-800">Source map ↔ MRI</dt>
              <dd className="text-gray-600 mt-0.5 leading-relaxed">{L.source_to_anatomy}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
};

export default MultimodalLinkageCard;
