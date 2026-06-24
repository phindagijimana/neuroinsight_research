/**
 * Linked cortical mesh (Three.js) colored by GET .../multimodal_source_frame.
 */

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { apiService } from '../services/api';
import { Spinner } from './LoadingState';

function paintValues(
  values: number[],
  vmin: number,
  vmax: number,
  attr: THREE.BufferAttribute
): void {
  const arr = attr.array as Float32Array;
  const col = new THREE.Color();
  const mid = (vmin + vmax) / 2;
  const span = Math.max(Math.abs(vmax - mid), Math.abs(mid - vmin), 1e-12);
  for (let i = 0; i < values.length; i++) {
    const nv = Math.max(-1, Math.min(1, (values[i] - mid) / span));
    const x = (nv + 1) / 2;
    const h = (240 - x * 240) / 360;
    col.setHSL(h, 0.7, 0.42);
    arr[i * 3] = col.r;
    arr[i * 3 + 1] = col.g;
    arr[i * 3 + 2] = col.b;
  }
  attr.needsUpdate = true;
}

interface CorticalSourceViewerProps {
  jobId: string;
  timeIndex: number;
  heightPx?: number;
}

const CorticalSourceViewer: React.FC<CorticalSourceViewerProps> = ({
  jobId,
  timeIndex,
  heightPx = 300,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const colorAttrRef = useRef<THREE.BufferAttribute | null>(null);
  const frameRef = useRef(0);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const meshGeomRef = useRef<THREE.BufferGeometry | null>(null);
  const meshMatRef = useRef<THREE.MeshStandardMaterial | null>(null);

  const [meshReady, setMeshReady] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [frameLabel, setFrameLabel] = useState('');

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    setMeshReady(false);
    setLoadErr(null);
    colorAttrRef.current = null;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f4f6);

    const camera = new THREE.PerspectiveCamera(
      42,
      Math.max(mount.clientWidth, 1) / Math.max(mount.clientHeight, 1),
      0.001,
      20
    );
    camera.position.set(0.26, 0.2, 0.36);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0.02, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const key = new THREE.DirectionalLight(0xffffff, 0.95);
    key.position.set(1.2, 2.0, 0.8);
    scene.add(key);

    rendererRef.current = renderer;
    sceneRef.current = scene;
    cameraRef.current = camera;
    controlsRef.current = controls;

    let cancelled = false;

    apiService
      .getMultimodalMesh(jobId)
      .then((payload) => {
        if (cancelled) return;
        const geom = new THREE.BufferGeometry();
        const pos = new Float32Array(payload.vertices);
        geom.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geom.setIndex(payload.faces);
        geom.computeVertexNormals();

        const nVert = payload.vertex_count;
        const colors = new Float32Array(nVert * 3);
        const colorAttr = new THREE.BufferAttribute(colors, 3);
        geom.setAttribute('color', colorAttr);

        const mat = new THREE.MeshStandardMaterial({
          vertexColors: true,
          roughness: 0.62,
          metalness: 0.06,
          side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geom, mat);
        scene.add(mesh);

        meshGeomRef.current = geom;
        meshMatRef.current = mat;
        colorAttrRef.current = colorAttr;
        setMeshReady(true);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Could not load cortical mesh.';
        setLoadErr(String(msg));
      });

    const ro = new ResizeObserver(() => {
      if (!mountRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      rendererRef.current.setSize(w, h);
      cameraRef.current.aspect = w / Math.max(h, 1);
      cameraRef.current.updateProjectionMatrix();
    });
    ro.observe(mount);

    const tick = () => {
      frameRef.current = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelled = true;
      cancelAnimationFrame(frameRef.current);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      if (meshGeomRef.current) {
        meshGeomRef.current.dispose();
        meshGeomRef.current = null;
      }
      if (meshMatRef.current) {
        meshMatRef.current.dispose();
        meshMatRef.current = null;
      }
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      rendererRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      colorAttrRef.current = null;
      setMeshReady(false);
    };
  }, [jobId]);

  useEffect(() => {
    if (!meshReady || !jobId) return;
    const attr = colorAttrRef.current;
    if (!attr) return;

    let cancelled = false;
    apiService
      .getMultimodalSourceFrame(jobId, timeIndex)
      .then((frame) => {
        if (cancelled) return;
        paintValues(frame.values, frame.vmin, frame.vmax, attr);
        setFrameLabel(`t = ${frame.time_s.toFixed(4)} s · frame ${frame.time_index + 1}/${frame.n_times}`);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Could not load source frame.';
        setLoadErr(String(msg));
      });

    return () => {
      cancelled = true;
    };
  }, [jobId, timeIndex, meshReady]);

  if (loadErr) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
        {loadErr}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        ref={mountRef}
        className="w-full rounded-lg border border-gray-200 bg-gray-100 overflow-hidden relative"
        style={{ height: heightPx }}
      >
        {!meshReady && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-gray-600 text-sm bg-gray-50/90 z-10">
            <Spinner size="md" className="text-navy-600" />
            Loading cortical mesh…
          </div>
        )}
      </div>
      {meshReady && frameLabel && (
        <p className="text-xs text-gray-500">{frameLabel}</p>
      )}
    </div>
  );
};

export default CorticalSourceViewer;
