/**
 * NiivueViewer Component
 * Full PACS-like NIfTI viewer with multi-plane views and segmentation overlays
 */

import { useEffect, useRef, useState } from 'react';
import { Niivue } from '@niivue/niivue';

interface NiivueViewerProps {
  imageUrl?: string;
  segmentationUrl?: string;
  pipelineName?: string;
  /** Explicit volume name — needed when imageUrl is a blob: URL (drag-and-drop). */
  imageName?: string;
  onLoad?: () => void;
  /** Canvas height in pixels (default 600; use smaller in EEG+Brain layout). */
  canvasHeightPx?: number;
}

const isHippocampalPipeline = (name?: string): boolean => {
  if (!name) return false;
  const lower = name.toLowerCase();
  return lower.includes('hs detection') || lower.includes('hippocam') || lower.includes('segmentha');
};

const NiivueViewer: React.FC<NiivueViewerProps> = ({
  imageUrl,
  segmentationUrl,
  pipelineName,
  imageName,
  onLoad,
  canvasHeightPx = 600,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<Niivue | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const isHippo = isHippocampalPipeline(pipelineName);
  // Niivue slice types: 0=Axial 1=Coronal 2=Sagittal 3=Multi-planar(4-up) 4=3D Render.
  const [sliceType, setSliceType] = useState<number>(isHippo ? 1 : 3); // 4-up by default
  const [opacity, setOpacity] = useState(isHippo ? 0.65 : 0.5);
  const [colormap, setColormap] = useState('gray');
  const [showCrosshair, setShowCrosshair] = useState(true);
  // Cursor readout (voxel coords + intensity) and window/level (display range).
  const [location, setLocation] = useState<{ vox?: number[]; mm?: number[]; values?: Array<{ value: number }> } | null>(null);
  const [winRange, setWinRange] = useState<{ min: number; max: number } | null>(null);
  const [winMin, setWinMin] = useState<number | null>(null);
  const [winMax, setWinMax] = useState<number | null>(null);
  // Tier 2/3: mouse mode, slice scrubbing, loaded layers, help overlay.
  const [mouseMode, setMouseMode] = useState<number>(1); // 1=window/level 2=measure 3=pan
  const [sliceFrac, setSliceFrac] = useState<[number, number, number]>([0.5, 0.5, 0.5]);
  const [layers, setLayers] = useState<Array<{ index: number; name: string }>>([]);
  const [showHelp, setShowHelp] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Initialize Niivue
  useEffect(() => {
    if (!canvasRef.current || nvRef.current) return;

    const nv = new Niivue({
      show3Dcrosshair: true,
      backColor: [0, 0, 0, 1],
      crosshairColor: [0, 1, 0, 1],
      selectionBoxColor: [1, 1, 1, 0.5],
      clipPlaneColor: [1, 0, 0, 0.5],
      textHeight: 0.05,
      colorbarHeight: 0.05,
      crosshairWidth: 1,
      isRadiologicalConvention: false,
      logLevel: 'error' as never, // suppress verbose console output
      dragMode: 1, // 1 = pan, 2 = measure
      isColorbar: true,
      isOrientCube: true,
      multiplanarForceRender: true,
      meshThicknessOn2D: Infinity,
      dragAndDropEnabled: true,
      isRuler: true,
      isAntiAlias: true,
      limitFrames4D: NaN,
      isHighResolutionCapable: true,
    } as ConstructorParameters<typeof Niivue>[0]);

    nv.attachToCanvas(canvasRef.current);
    nv.setSliceType(sliceType);
    // Live cursor readout (voxel coords + intensity) + keep slice sliders in sync.
    (nv as unknown as { onLocationChange: (d: unknown) => void }).onLocationChange = (d) => {
      const data = d as { vox?: number[]; mm?: number[]; values?: Array<{ value: number }>; frac?: number[] };
      setLocation(data);
      if (data.frac && data.frac.length >= 3) {
        setSliceFrac([data.frac[0], data.frac[1], data.frac[2]]);
      }
    };
    nvRef.current = nv;

    return () => {
      if (nvRef.current) {
        // Cleanup if needed
      }
    };
  }, []);

  // Load images when URLs change
  useEffect(() => {
    if (!nvRef.current || !imageUrl) return;

    const loadImages = async () => {
      setIsLoading(true);
      try {
        const extractName = (u: string): string => {
          const fp = new URLSearchParams(u.split('?')[1] || '').get('file_path');
          if (fp) return fp.split('/').pop() || 'volume.nii.gz';
          return u.split('/').pop()?.split('?')[0] || 'volume.nii.gz';
        };

        const volumeList: Array<{ url: string; name: string; colormap?: string; opacity?: number }> = [
          {
            url: imageUrl,
            name: imageName || extractName(imageUrl),
            colormap: colormap,
            opacity: 1.0,
          },
        ];

        if (segmentationUrl) {
          volumeList.push({
            url: segmentationUrl,
            name: extractName(segmentationUrl),
            colormap: 'actc',
            opacity: opacity,
          });
        }

        await (nvRef.current as Niivue).loadVolumes(volumeList as never);

        // Seed window/level from the base volume's display range.
        const vols = (nvRef.current as unknown as { volumes: Array<{ cal_min: number; cal_max: number; global_min: number; global_max: number; name?: string }> }).volumes;
        const vol = vols[0];
        if (vol) {
          setWinRange({ min: vol.global_min, max: vol.global_max });
          setWinMin(vol.cal_min);
          setWinMax(vol.cal_max);
        }
        setLayers(vols.map((v, i) => ({ index: i, name: v.name || (i === 0 ? 'Base volume' : `Overlay ${i}`) })));

        if (onLoad) onLoad();
      } catch (error) {
        console.error('Failed to load volumes:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadImages();
  }, [imageUrl, segmentationUrl, colormap, imageName, onLoad]);

  // Update slice type
  useEffect(() => {
    if (nvRef.current) {
      nvRef.current.setSliceType(sliceType);
    }
  }, [sliceType]);

  // Update segmentation opacity
  useEffect(() => {
    if (nvRef.current && nvRef.current.volumes.length > 1) {
      nvRef.current.setOpacity(1, opacity);
    }
  }, [opacity]);

  // Apply window/level (display range) to the base volume.
  useEffect(() => {
    const nv = nvRef.current as unknown as {
      volumes: Array<{ cal_min: number; cal_max: number }>;
      updateGLVolume: () => void;
    } | null;
    if (!nv || !nv.volumes[0] || winMin === null || winMax === null || winMin >= winMax) return;
    nv.volumes[0].cal_min = winMin;
    nv.volumes[0].cal_max = winMax;
    nv.updateGLVolume();
  }, [winMin, winMax]);

  // Update crosshair visibility
  useEffect(() => {
    if (nvRef.current) {
      nvRef.current.opts.show3Dcrosshair = showCrosshair;
      nvRef.current.updateGLVolume();
    }
  }, [showCrosshair]);

  // Mouse drag mode: window/level (1), measure (2), pan (3).
  useEffect(() => {
    const nv = nvRef.current as unknown as { opts: { dragMode: number }; drawScene: () => void } | null;
    if (!nv) return;
    nv.opts.dragMode = mouseMode;
    nv.drawScene();
  }, [mouseMode]);

  // Move the crosshair along one axis (slice scrubbing).
  const setSliceAxis = (axis: number, frac: number) => {
    const next: [number, number, number] = [...sliceFrac];
    next[axis] = frac;
    setSliceFrac(next);
    const nv = nvRef.current as unknown as { scene?: { crosshairPos: number[] }; drawScene: () => void } | null;
    if (nv && nv.scene) {
      nv.scene.crosshairPos = next;
      nv.drawScene();
    }
  };

  const setLayerOpacity = (index: number, value: number) => {
    if (nvRef.current && nvRef.current.volumes.length > index) {
      nvRef.current.setOpacity(index, value);
    }
  };

  // Viewer keyboard shortcuts (ignored while typing in a field).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ['INPUT', 'SELECT', 'TEXTAREA'].includes(t.tagName)) return;
      switch (e.key) {
        case '1': setSliceType(3); break; // multi-planar
        case '2': setSliceType(0); break; // axial
        case '3': setSliceType(1); break; // coronal
        case '4': setSliceType(2); break; // sagittal
        case '5': setSliceType(4); break; // 3D render
        case 'r': case 'R': handleResetView(); break;
        case 'x': case 'X': setShowCrosshair((v) => !v); break;
        case '?': setShowHelp((v) => !v); break;
        case 'Escape': setShowHelp(false); break;
        default: break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleResetView = () => {
    if (nvRef.current && nvRef.current.volumes.length > 0) {
      nvRef.current.setSliceType(sliceType);
    }
  };

  const handleScreenshot = () => {
    if (nvRef.current) {
      nvRef.current.saveScene('niivue-screenshot.png');
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Compact toolbar — primary controls only */}
      <div className="rounded-xl border border-gray-200 bg-white px-3 py-2.5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[9rem] flex-1">
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
              Layout
            </label>
            <select
              value={sliceType}
              onChange={(e) => setSliceType(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm focus:border-navy-600 focus:ring-2 focus:ring-navy-600"
            >
              <option value={3}>Multi-planar (4-up)</option>
              <option value={0}>Axial</option>
              <option value={1}>Coronal</option>
              <option value={2}>Sagittal</option>
              <option value={4}>3D render</option>
            </select>
          </div>

          <div className="min-w-[7rem] flex-1">
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
              Colormap
            </label>
            <select
              value={colormap}
              onChange={(e) => setColormap(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm focus:border-navy-600 focus:ring-2 focus:ring-navy-600"
            >
              <option value="gray">Grayscale</option>
              <option value="jet">Jet</option>
              <option value="hot">Hot</option>
              <option value="winter">Winter</option>
              <option value="plasma">Plasma</option>
              <option value="viridis">Viridis</option>
            </select>
          </div>

          <div className="min-w-[7rem] flex-1">
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
              Drag
            </label>
            <select
              value={mouseMode}
              onChange={(e) => setMouseMode(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm focus:border-navy-600 focus:ring-2 focus:ring-navy-600"
            >
              <option value={1}>Window / level</option>
              <option value={2}>Measure</option>
              <option value={3}>Pan</option>
            </select>
          </div>

          <label className="flex items-center gap-2 pb-1.5 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={showCrosshair}
              onChange={(e) => setShowCrosshair(e.target.checked)}
              className="h-4 w-4 rounded text-navy-600 focus:ring-navy-600"
            />
            Crosshair
          </label>

          <div className="flex flex-wrap gap-2 pb-0.5">
            <button
              type="button"
              onClick={handleResetView}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={handleScreenshot}
              className="rounded-lg bg-navy-600 px-3 py-1.5 text-sm text-white hover:bg-navy-800"
            >
              Screenshot
            </button>
            <button
              type="button"
              onClick={() => setShowHelp((v) => !v)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              title="Keyboard shortcuts"
            >
              ?
            </button>
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
            >
              {showAdvanced ? 'Less' : 'Adjust'}
            </button>
            {isHippo && segmentationUrl && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setSliceType(3);
                    setOpacity(0.7);
                  }}
                  className="rounded-lg bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
                >
                  Hippocampal 3D
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSliceType(1);
                    setOpacity(0.65);
                  }}
                  className="rounded-lg bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
                >
                  Coronal
                </button>
              </>
            )}
          </div>
        </div>

        {showAdvanced && (
          <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
            {winRange && winMin !== null && winMax !== null && (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-600">
                    Window min: {winMin.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min={winRange.min}
                    max={winRange.max}
                    step={(winRange.max - winRange.min) / 200 || 1}
                    value={winMin}
                    onChange={(e) => setWinMin(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-600">
                    Window max: {winMax.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min={winRange.min}
                    max={winRange.max}
                    step={(winRange.max - winRange.min) / 200 || 1}
                    value={winMax}
                    onChange={(e) => setWinMax(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>
            )}

            {sliceType !== 4 && (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {(['Sagittal', 'Coronal', 'Axial'] as const).map((label, axis) => (
                  <div key={label}>
                    <label className="mb-1 block text-xs font-medium text-gray-600">
                      {label}: {Math.round(sliceFrac[axis] * 100)}%
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.005}
                      value={sliceFrac[axis]}
                      onChange={(e) => setSliceAxis(axis, Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                ))}
              </div>
            )}

            {layers.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium text-gray-600">Layers</p>
                <div className="space-y-2">
                  {layers.map((l) => (
                    <div key={l.index} className="flex items-center gap-3">
                      <span className="w-36 truncate text-sm text-gray-700" title={l.name}>
                        {l.index === 0 ? '◾' : '▥'} {l.name}
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        defaultValue={l.index === 0 ? 1 : opacity}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setLayerOpacity(l.index, v);
                          if (l.index > 0) setOpacity(v);
                        }}
                        className="flex-1"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Canvas */}
      <div
        className="relative bg-black rounded-lg overflow-hidden"
        style={{ height: `${canvasHeightPx}px` }}
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 z-10">
            <div className="text-white text-lg">Loading volumes...</div>
          </div>
        )}
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: `${canvasHeightPx}px` }}
        />

        {/* Keyboard / mouse help overlay (toggle with ? or the Shortcuts button) */}
        {showHelp && (
          <div
            className="absolute inset-0 z-20 bg-black/70 flex items-center justify-center p-6"
            onClick={() => setShowHelp(false)}
          >
            <div
              className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-lg font-semibold text-gray-900">Viewer controls</h4>
                <button onClick={() => setShowHelp(false)} className="text-gray-400 hover:text-gray-700">✕</button>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm text-gray-700">
                <span className="font-medium">Keyboard</span><span></span>
                <span><kbd>1</kbd> Multi-planar</span><span><kbd>2</kbd>/<kbd>3</kbd>/<kbd>4</kbd> Axial/Coronal/Sagittal</span>
                <span><kbd>5</kbd> 3D render</span><span><kbd>R</kbd> Reset · <kbd>X</kbd> Crosshair</span>
                <span><kbd>?</kbd> This help</span><span><kbd>Esc</kbd> Close</span>
                <span className="font-medium mt-2">Mouse</span><span className="mt-2"></span>
                <span>Left-click: move crosshair</span><span>Left-drag: {mouseMode === 1 ? 'window/level' : mouseMode === 2 ? 'measure' : 'pan'}</span>
                <span>Scroll: zoom / slice</span><span>Right-drag: window/level</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Cursor readout */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-lg bg-gray-900 px-4 py-2 font-mono text-xs text-gray-200">
        <span>
          Voxel:{' '}
          {location?.vox ? `(${location.vox.slice(0, 3).map((v) => Math.round(v)).join(', ')})` : '—'}
        </span>
        <span>
          mm:{' '}
          {location?.mm ? `(${location.mm.slice(0, 3).map((v) => v.toFixed(1)).join(', ')})` : '—'}
        </span>
        <span>
          Intensity:{' '}
          {location?.values && location.values[0] && typeof location.values[0].value === 'number'
            ? location.values[0].value.toFixed(2)
            : '—'}
        </span>
      </div>
    </div>
  );
};

export default NiivueViewer;
