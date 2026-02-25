/**
 * QCImageGallery Component
 *
 * Displays QC coronal slices as layered anatomical + overlay images.
 * An opacity slider lets users dynamically control overlay visibility.
 * Also surfaces HS metrics when available.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/api';
import Activity from './icons/Activity';

interface QCSlice {
  index: number;
  label: string;
  anatomicalUrl: string;
  overlayUrl: string;
}

interface HSMetrics {
  subject_id: string;
  volumes_mm3: { left: number; right: number };
  asymmetry_index: number;
  thresholds: { left_hs: number; right_hs: number };
  classification: string;
}

interface QCImageGalleryProps {
  jobId: string;
}

const QCImageGallery: React.FC<QCImageGalleryProps> = ({ jobId }) => {
  const [slices, setSlices] = useState<QCSlice[]>([]);
  const [metrics, setMetrics] = useState<HSMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [overlayOpacity, setOverlayOpacity] = useState(0.6);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const filesResp = await apiService.getJobFiles(jobId);
        if (cancelled) return;

        const baseUrl = apiService.getBaseUrl();
        const pngFiles = filesResp.files.filter(
          (f: any) => f.type === 'image' && f.name.endsWith('.png')
        );

        const anatFiles = pngFiles
          .filter((f: any) => {
            const fn = f.name.split('/').pop() || '';
            return fn.startsWith('anatomical_slice_') || fn.includes('_anat.png');
          })
          .sort((a: any, b: any) => a.name.localeCompare(b.name));

        const overlayFiles = pngFiles
          .filter((f: any) => {
            const fn = f.name.split('/').pop() || '';
            return fn.startsWith('hippocampus_overlay_') || fn.includes('_overlay.png');
          })
          .sort((a: any, b: any) => a.name.localeCompare(b.name));

        const paired: QCSlice[] = anatFiles.map((af: any, idx: number) => {
          const filename = af.name.split('/').pop() || af.name;
          const idxMatch = filename.match(/(\d{2})/);
          const sliceIdx = idxMatch ? idxMatch[1] : String(idx).padStart(2, '0');
          const label = `Slice ${idx + 1} of ${anatFiles.length}`;
          const of = overlayFiles.find((o: any) => {
            const ofn = o.name.split('/').pop() || '';
            const oIdx = ofn.match(/(\d{2})/);
            return oIdx && oIdx[1] === sliceIdx;
          });
          return {
            index: idx,
            label,
            anatomicalUrl: `${baseUrl}${af.path}`,
            overlayUrl: of ? `${baseUrl}${of.path}` : '',
          };
        });

        setSlices(paired);

        const hsMetricsFile = filesResp.files.find(
          (f: any) => f.name.endsWith('hs_metrics.json')
        );
        if (hsMetricsFile) {
          try {
            const resp = await fetch(`${baseUrl}${hsMetricsFile.path}`);
            if (resp.ok) {
              const m = await resp.json();
              if (m && m.subject_id) setMetrics(m as HSMetrics);
            }
          } catch { /* metrics are optional */ }
        }
      } catch {
        if (!cancelled) setError('Failed to load QC images.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [jobId]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (lightboxIndex === null) return;
    if (e.key === 'Escape') setLightboxIndex(null);
    if (e.key === 'ArrowRight') setLightboxIndex(i => i !== null ? Math.min(i + 1, slices.length - 1) : null);
    if (e.key === 'ArrowLeft') setLightboxIndex(i => i !== null ? Math.max(i - 1, 0) : null);
  }, [lightboxIndex, slices.length]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (loading) {
    return (
      <div className="p-8 text-center">
        <Activity className="w-6 h-6 text-[#003d7a] animate-spin mx-auto mb-2" />
        <span className="text-sm text-gray-600">Loading QC images...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  if (slices.length === 0) {
    return (
      <div className="p-6">
        <p className="text-sm text-gray-500">No QC images found for this job.</p>
      </div>
    );
  }

  const classificationColor = (cls: string) => {
    if (cls.toLowerCase().includes('left')) return 'text-navy-700 bg-navy-50 border-navy-200';
    if (cls.toLowerCase().includes('right')) return 'text-navy-700 bg-navy-50 border-navy-200';
    return 'text-green-700 bg-green-50 border-green-200';
  };

  const renderLayeredImage = (
    sl: QCSlice,
    imgClass: string,
    showLabel: boolean = true,
  ) => (
    <div className="relative bg-black">
      <img
        src={sl.anatomicalUrl}
        alt={sl.label}
        className={imgClass}
      />
      {sl.overlayUrl && (
        <img
          src={sl.overlayUrl}
          alt=""
          className={`absolute top-0 left-0 ${imgClass}`}
          style={{
            opacity: overlayOpacity,
            transition: 'opacity 0.15s ease-out',
            pointerEvents: 'none',
            width: '100%',
            height: '100%',
          }}
        />
      )}
      {showLabel && (
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1.5">
          <span className="text-[11px] font-medium text-white">{sl.label}</span>
        </div>
      )}
    </div>
  );

  return (
    <div className="p-4 space-y-5">
      {/* HS Metrics Banner */}
      {metrics && (
        <div className="bg-[#f0f4fa] border border-[#b3cce6] rounded-lg p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-[#003d7a] flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#003d7a]">Hippocampal Sclerosis Analysis</h4>
              <p className="text-xs text-[#4a6fa5]">Subject: {metrics.subject_id}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white rounded-md border border-[#d0dff0] p-3">
              <p className="text-[10px] font-medium text-[#4a6fa5] uppercase tracking-wider">Left Hippocampus</p>
              <p className="text-lg font-bold text-[#003d7a]">{metrics.volumes_mm3.left.toFixed(0)} mm³</p>
            </div>
            <div className="bg-white rounded-md border border-[#d0dff0] p-3">
              <p className="text-[10px] font-medium text-[#4a6fa5] uppercase tracking-wider">Right Hippocampus</p>
              <p className="text-lg font-bold text-[#003d7a]">{metrics.volumes_mm3.right.toFixed(0)} mm³</p>
            </div>
            <div className="bg-white rounded-md border border-[#d0dff0] p-3">
              <p className="text-[10px] font-medium text-[#4a6fa5] uppercase tracking-wider">Asymmetry Index</p>
              <p className="text-lg font-bold text-[#003d7a]">{metrics.asymmetry_index.toFixed(4)}</p>
            </div>
            <div className={`rounded-md border p-3 ${classificationColor(metrics.classification)}`}>
              <p className="text-[10px] font-medium uppercase tracking-wider opacity-75">Classification</p>
              <p className="text-lg font-bold">{metrics.classification}</p>
            </div>
          </div>
        </div>
      )}

      {/* Gallery Header + Opacity Slider */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h4 className="text-sm font-semibold text-gray-900">
          QC Overlays{' '}
          <span className="text-gray-500 font-normal">({slices.length} coronal slices)</span>
        </h4>
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-gray-600 whitespace-nowrap">
            Overlay Opacity:
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={overlayOpacity * 100}
            onChange={(e) => setOverlayOpacity(parseInt(e.target.value) / 100)}
            className="w-32 h-2 bg-[#b3cce6] rounded-lg appearance-none cursor-pointer accent-[#003d7a]"
          />
          <span className="text-sm font-semibold text-[#003d7a] w-10 text-right">
            {Math.round(overlayOpacity * 100)}%
          </span>
        </div>
      </div>

      {/* Image Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {slices.map((sl) => (
          <button
            key={sl.index}
            onClick={() => setLightboxIndex(sl.index)}
            className="group relative rounded-lg overflow-hidden border-2 border-transparent hover:border-[#003d7a] transition-all focus:outline-none focus:ring-2 focus:ring-[#003d7a] focus:ring-offset-2"
          >
            {renderLayeredImage(sl, 'w-full h-auto object-contain block')}
            <div className="absolute inset-0 bg-[#003d7a]/0 group-hover:bg-[#003d7a]/10 transition-colors flex items-center justify-center pointer-events-none">
              <svg className="w-6 h-6 text-white opacity-0 group-hover:opacity-80 transition-opacity drop-shadow" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
              </svg>
            </div>
          </button>
        ))}
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center"
          onClick={() => setLightboxIndex(null)}
        >
          {/* Close button */}
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white transition p-2 z-10"
            onClick={() => setLightboxIndex(null)}
          >
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {/* Prev button */}
          {lightboxIndex > 0 && (
            <button
              className="absolute left-4 top-1/2 -translate-y-1/2 text-white/70 hover:text-white transition p-2 z-10"
              onClick={(e) => { e.stopPropagation(); setLightboxIndex(lightboxIndex - 1); }}
            >
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}

          {/* Next button */}
          {lightboxIndex < slices.length - 1 && (
            <button
              className="absolute right-4 top-1/2 -translate-y-1/2 text-white/70 hover:text-white transition p-2 z-10"
              onClick={(e) => { e.stopPropagation(); setLightboxIndex(lightboxIndex + 1); }}
            >
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}

          {/* Lightbox opacity slider */}
          <div
            className="absolute top-5 left-1/2 -translate-x-1/2 flex items-center gap-3 bg-black/60 backdrop-blur-sm rounded-full px-5 py-2 z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <label className="text-xs font-medium text-white/80 whitespace-nowrap">Overlay Opacity:</label>
            <input
              type="range"
              min="0"
              max="100"
              value={overlayOpacity * 100}
              onChange={(e) => setOverlayOpacity(parseInt(e.target.value) / 100)}
              className="w-36 h-2 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[#4ECDC4]"
            />
            <span className="text-sm font-semibold text-white w-10 text-right">
              {Math.round(overlayOpacity * 100)}%
            </span>
          </div>

          {/* Main image */}
          <div
            className="max-w-4xl max-h-[80vh] flex flex-col items-center mt-12"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative">
              <img
                src={slices[lightboxIndex].anatomicalUrl}
                alt={slices[lightboxIndex].label}
                className="max-w-full max-h-[72vh] object-contain rounded-lg shadow-2xl block"
              />
              {slices[lightboxIndex].overlayUrl && (
                <img
                  src={slices[lightboxIndex].overlayUrl}
                  alt=""
                  className="absolute top-0 left-0 w-full h-full object-contain rounded-lg"
                  style={{
                    opacity: overlayOpacity,
                    transition: 'opacity 0.15s ease-out',
                    pointerEvents: 'none',
                  }}
                />
              )}
            </div>
            <div className="mt-3 flex items-center gap-4">
              <span className="text-white text-sm font-medium">{slices[lightboxIndex].label}</span>
              <span className="text-white/50 text-xs">{lightboxIndex + 1} / {slices.length}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QCImageGallery;
