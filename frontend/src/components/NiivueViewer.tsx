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
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* View Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              View Type
            </label>
            <select
              value={sliceType}
              onChange={(e) => setSliceType(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent"
            >
              <option value={3}>Multi-planar (4-up)</option>
              <option value={0}>Axial</option>
              <option value={1}>Coronal</option>
              <option value={2}>Sagittal</option>
              <option value={4}>3D Render</option>
            </select>
          </div>

          {/* Colormap */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Colormap
            </label>
            <select
              value={colormap}
              onChange={(e) => setColormap(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent"
            >
              <option value="gray">Grayscale</option>
              <option value="jet">Jet</option>
              <option value="hot">Hot</option>
              <option value="winter">Winter</option>
              <option value="plasma">Plasma</option>
              <option value="viridis">Viridis</option>
            </select>
          </div>

          {/* Mouse Mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Mouse (drag)
            </label>
            <select
              value={mouseMode}
              onChange={(e) => setMouseMode(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-navy-600 focus:border-transparent"
            >
              <option value={1}>Window / Level</option>
              <option value={2}>Measure</option>
              <option value={3}>Pan</option>
            </select>
          </div>

          {/* Crosshair Toggle */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Crosshair
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showCrosshair}
                onChange={(e) => setShowCrosshair(e.target.checked)}
                className="w-4 h-4 text-navy-600 rounded focus:ring-navy-600"
              />
              <span className="text-sm text-gray-700">Show</span>
            </label>
          </div>
        </div>

        {/* Window / Level (display range) */}
        {winRange && winMin !== null && winMax !== null && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Window Min: {winMin.toFixed(1)}
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
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Window Max: {winMax.toFixed(1)}
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

        {/* Slice position (scrubbing) — hidden in pure 3D render */}
        {sliceType !== 4 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            {(['Sagittal', 'Coronal', 'Axial'] as const).map((label, axis) => (
              <div key={label}>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {label} position: {Math.round(sliceFrac[axis] * 100)}%
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

        {/* Layers */}
        {layers.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-semibold text-gray-700 mb-2">Layers</p>
            <div className="space-y-2">
              {layers.map((l) => (
                <div key={l.index} className="flex items-center gap-3">
                  <span className="text-sm text-gray-700 w-40 truncate" title={l.name}>
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
                  <span className="text-xs text-gray-500 w-10 text-right">opacity</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 mt-4 flex-wrap">
          <button
            onClick={handleResetView}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
          >
            Reset View
          </button>
          <button
            onClick={handleScreenshot}
            className="px-4 py-2 bg-navy-600 text-white rounded-lg hover:bg-navy-800 transition"
          >
            Save Screenshot
          </button>
          <button
            onClick={() => setShowHelp((v) => !v)}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
            title="Keyboard shortcuts & mouse controls"
          >
            ? Shortcuts
          </button>
          {isHippo && segmentationUrl && (
            <>
              <button
                onClick={() => {
                  setSliceType(3);
                  setOpacity(0.7);
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
              >
                Hippocampal 3D
              </button>
              <button
                onClick={() => {
                  setSliceType(1);
                  setOpacity(0.65);
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
              >
                Coronal View
              </button>
            </>
          )}
        </div>
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

      {/* Cursor readout — voxel coords + intensity (ITK-SNAP / Slicer style) */}
      <div className="bg-gray-900 text-gray-200 rounded-lg px-4 py-2 text-xs font-mono flex flex-wrap gap-x-6 gap-y-1">
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

      {/* Instructions */}
      <div className="bg-navy-50 border border-navy-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-navy-900 mb-2">
          PACS-like Controls
        </h4>
        <div className="text-sm text-navy-800 grid grid-cols-2 gap-2">
          <div>- <strong>Left Click + Drag:</strong> Pan</div>
          <div>- <strong>Right Click + Drag:</strong> Window/Level</div>
          <div>- <strong>Mouse Wheel:</strong> Zoom</div>
          <div>- <strong>Shift + Click:</strong> Crosshair</div>
          <div>- <strong>Ctrl + Click:</strong> Measure</div>
          <div>- <strong>Multi-planar:</strong> 4-view PACS layout</div>
        </div>
      </div>
    </div>
  );
};

export default NiivueViewer;
