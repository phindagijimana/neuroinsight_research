/**
 * NiivueViewer Component
 * Full PACS-like NIfTI viewer with multi-plane views and segmentation overlays
 */

import { useEffect, useRef, useState } from 'react';
import { Niivue } from '@niivue/niivue';

interface NiivueViewerProps {
  imageUrl?: string;
  segmentationUrl?: string;
  onLoad?: () => void;
}

const NiivueViewer: React.FC<NiivueViewerProps> = ({
  imageUrl,
  segmentationUrl,
  onLoad
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<Niivue | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [sliceType, setSliceType] = useState<number>(4); // 4 = multi-planar view
  const [opacity, setOpacity] = useState(0.5);
  const [colormap, setColormap] = useState('gray');
  const [showCrosshair, setShowCrosshair] = useState(true);

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
        // Build volume descriptors for Niivue.loadVolumes()
        const volumeList: Array<{ url: string; colormap?: string; opacity?: number }> = [
          {
            url: imageUrl,
            colormap: colormap,
            opacity: 1.0,
          },
        ];

        // Load segmentation if provided
        if (segmentationUrl) {
          volumeList.push({
            url: segmentationUrl,
            colormap: 'actc', // Colored anatomical labels
            opacity: opacity,
          });
        }

        await (nvRef.current as Niivue).loadVolumes(volumeList as never);
        
        if (onLoad) onLoad();
      } catch (error) {
        console.error('Failed to load volumes:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadImages();
  }, [imageUrl, segmentationUrl, colormap, onLoad]);

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

  // Update crosshair visibility
  useEffect(() => {
    if (nvRef.current) {
      nvRef.current.opts.show3Dcrosshair = showCrosshair;
      nvRef.current.updateGLVolume();
    }
  }, [showCrosshair]);

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
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003d7a] focus:border-transparent"
            >
              <option value={0}>Axial</option>
              <option value={1}>Coronal</option>
              <option value={2}>Sagittal</option>
              <option value={3}>3D Render</option>
              <option value={4}>Multi-planar (PACS)</option>
              <option value={5}>Mosaic</option>
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
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003d7a] focus:border-transparent"
            >
              <option value="gray">Grayscale</option>
              <option value="jet">Jet</option>
              <option value="hot">Hot</option>
              <option value="winter">Winter</option>
              <option value="plasma">Plasma</option>
              <option value="viridis">Viridis</option>
            </select>
          </div>

          {/* Segmentation Opacity */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Overlay Opacity: {opacity.toFixed(2)}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="w-full"
            />
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
                className="w-4 h-4 text-[#003d7a] rounded focus:ring-[#003d7a]"
              />
              <span className="text-sm text-gray-700">Show</span>
            </label>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 mt-4">
          <button
            onClick={handleResetView}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
          >
            Reset View
          </button>
          <button
            onClick={handleScreenshot}
            className="px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
          >
            Save Screenshot
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: '600px' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 z-10">
            <div className="text-white text-lg">Loading volumes...</div>
          </div>
        )}
        <canvas ref={canvasRef} style={{ width: '100%', height: '600px' }} />
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
