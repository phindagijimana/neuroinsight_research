/**
 * Multimodal View: compact signal preview, optional linked cortical mesh, Niivue imaging below.
 */

import { useCallback, useEffect, useState } from 'react';
import NiivueViewer from './NiivueViewer';
import EegViewerPanel from './EegViewerPanel';
import CorticalSourceViewer from './CorticalSourceViewer';
import MultimodalLinkageCard from './MultimodalLinkageCard';
import { apiService } from '../services/api';
import type { MultimodalManifest } from '../types';

interface EegBrainFusionPanelProps {
  jobId: string | null;
  eegRelativePath: string | null;
  imageUrl: string;
  segmentationUrl?: string;
  pipelineName?: string;
  onNiivueLoad?: () => void;
}

const EegBrainFusionPanel: React.FC<EegBrainFusionPanelProps> = ({
  jobId,
  eegRelativePath,
  imageUrl,
  segmentationUrl,
  pipelineName,
  onNiivueLoad,
}) => {
  const [linkTimeIndex, setLinkTimeIndex] = useState(0);
  const [manifest, setManifest] = useState<MultimodalManifest | null>(null);

  const linkCortex = Boolean(jobId && manifest?.cortex_npz);

  useEffect(() => {
    setLinkTimeIndex(0);
    setManifest(null);
    if (!jobId) return;
    let cancelled = false;
    apiService
      .getMultimodalManifest(jobId)
      .then((m) => {
        if (!cancelled) setManifest(m);
      })
      .catch(() => {
        if (!cancelled) setManifest(null);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const onEEGTimeChange = useCallback((i: number) => {
    setLinkTimeIndex(i);
  }, []);

  return (
    <div className="space-y-4">
      {manifest && (
        <MultimodalLinkageCard manifest={manifest} eegOpenPath={eegRelativePath} />
      )}

      <div className="bg-gray-50 rounded-lg border border-gray-200 p-3">
        <h3 className="text-xs font-semibold text-gray-700 tracking-wide mb-2">
          Signal View
        </h3>
        <EegViewerPanel
          jobId={jobId}
          eegRelativePath={eegRelativePath}
          compact
          timeIndex={linkCortex ? linkTimeIndex : undefined}
          onTimeIndexChange={linkCortex ? onEEGTimeChange : undefined}
        />
      </div>

      {linkCortex && jobId && (
        <div>
          <h3 className="text-xs font-semibold text-gray-700 tracking-wide mb-2">
            Cortical source (linked time)
          </h3>
          <CorticalSourceViewer jobId={jobId} timeIndex={linkTimeIndex} heightPx={300} />
          {manifest?.qc?.message && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1.5 mt-2">
              {manifest.qc.message}
            </p>
          )}
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold text-gray-700 tracking-wide mb-2">
          Imaging View
        </h3>
        <NiivueViewer
          imageUrl={imageUrl}
          segmentationUrl={segmentationUrl}
          pipelineName={pipelineName}
          onLoad={onNiivueLoad}
          canvasHeightPx={420}
        />
      </div>
    </div>
  );
};

export default EegBrainFusionPanel;
