/**
 * Signal View: continuous traces (Recharts) + scalp topomap at selected time index.
 * Optional "Classic" theme: EEGLAB / MATLAB-style dark plot, channel labels, cursor, click-to-seek.
 * Data from GET /api/results/{job_id}/eeg_preview (MNE backend).
 */

import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Minus, Plus } from 'lucide-react';
import { apiService } from '../services/api';
import type { EegPreviewPayload } from '../types';
import { Spinner } from './LoadingState';

const WINDOW_MIN_S = 0.5;
const WINDOW_MAX_S = 120;

const EEG_VIEWER_STYLE_KEY = 'nir_eeg_viewer_style';

type EegViewerStyle = 'modern' | 'classic';

function mean(arr: number[]): number {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function divergingFill(t: number): string {
  const x = Math.max(0, Math.min(1, (t + 1) / 2));
  const h = 240 - x * 240;
  return `hsl(${h}, 70%, 42%)`;
}

/** MNE preview waveforms are in volts; MATLAB users expect µV. */
function voltsToMicrovolts(v: number): number {
  return v * 1e6;
}

function readStoredViewerStyle(): EegViewerStyle {
  try {
    const v = localStorage.getItem(EEG_VIEWER_STYLE_KEY);
    if (v === 'classic' || v === 'modern') return v;
  } catch {
    /* ignore */
  }
  return 'modern';
}

function storeViewerStyle(s: EegViewerStyle): void {
  try {
    localStorage.setItem(EEG_VIEWER_STYLE_KEY, s);
  } catch {
    /* ignore */
  }
}

interface EegViewerPanelProps {
  jobId: string | null;
  /** Job-relative path (decoded file_path), not the full download URL. */
  eegRelativePath: string | null;
  compact?: boolean;
  /** When both are set, time slider is controlled (e.g. link to cortical viewer). */
  timeIndex?: number;
  onTimeIndexChange?: (index: number) => void;
}

const EegViewerPanel: React.FC<EegViewerPanelProps> = ({
  jobId,
  eegRelativePath,
  compact = false,
  timeIndex: controlledTimeIndex,
  onTimeIndexChange,
}) => {
  const [data, setData] = useState<EegPreviewPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [internalTimeIndex, setInternalTimeIndex] = useState(0);
  const lastDataKeyRef = useRef<string>('');
  const [viewerStyle, setViewerStyle] = useState<EegViewerStyle>(readStoredViewerStyle);
  const chartFocusRef = useRef<HTMLDivElement>(null);
  /** Full Signal View only: visible window length (s) and start offset along the file (s). */
  const [windowSec, setWindowSec] = useState(8);
  const [tOffset, setTOffset] = useState(0);
  const pathKeyRef = useRef<string>('');

  const nPointsFull = useMemo(
    () => Math.min(4000, Math.max(80, Math.round(windowSec * 100))),
    [windowSec]
  );

  const isControlled =
    typeof controlledTimeIndex === 'number' && typeof onTimeIndexChange === 'function';
  const timeIndex = isControlled ? controlledTimeIndex! : internalTimeIndex;
  const setTimeIndex = isControlled ? onTimeIndexChange! : setInternalTimeIndex;

  useEffect(() => {
    if (!jobId || !eegRelativePath) {
      setData(null);
      setErr(null);
      setTimeIndex(0);
      pathKeyRef.current = '';
      return;
    }
    const pathKey = `${jobId}|${eegRelativePath}`;
    if (pathKeyRef.current !== pathKey) {
      const isFirstPath = pathKeyRef.current === '';
      pathKeyRef.current = pathKey;
      if (!isFirstPath) {
        setWindowSec(8);
        setTOffset(0);
        return;
      }
    }

    let cancelled = false;
    setLoading(true);
    setErr(null);
    const opts = compact
      ? {
          duration_s: 4,
          n_time_points: 400,
          max_channels: 24,
          time_offset_s: 0,
        }
      : {
          duration_s: windowSec,
          n_time_points: nPointsFull,
          max_channels: 32,
          time_offset_s: tOffset,
        };
    apiService
      .getEegPreview(jobId, eegRelativePath, opts)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          if (!isControlled) {
            setTimeIndex(Math.floor(payload.times.length / 2));
          }
          if (
            !compact &&
            typeof payload.time_offset_s === 'number' &&
            Math.abs(payload.time_offset_s - tOffset) > 0.02
          ) {
            setTOffset(payload.time_offset_s);
          }
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setData(null);
          const msg =
            (e as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail || 'Could not load EEG preview.';
          setErr(String(msg));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    jobId,
    eegRelativePath,
    compact,
    windowSec,
    nPointsFull,
    tOffset,
    isControlled,
    setTimeIndex,
  ]);

  useEffect(() => {
    if (!data || compact || data.total_duration_s == null) return;
    const total = data.total_duration_s;
    const shown = data.duration_s;
    const maxStart = Math.max(0, total - shown);
    if (tOffset > maxStart + 1e-4) {
      setTOffset(maxStart);
    }
  }, [data, compact, tOffset]);

  const zoomIn = useCallback(() => {
    setWindowSec((w) => Math.max(WINDOW_MIN_S, Number((w * 0.75).toFixed(3))));
  }, []);
  const zoomOut = useCallback(() => {
    setWindowSec((w) => Math.min(WINDOW_MAX_S, Number(((w * 4) / 3).toFixed(3))));
  }, []);

  useEffect(() => {
    if (!data || !isControlled || !onTimeIndexChange) return;
    const key = `${jobId}|${eegRelativePath}|${data.times.length}|${data.time_offset_s ?? 0}`;
    if (lastDataKeyRef.current === key) return;
    lastDataKeyRef.current = key;
    onTimeIndexChange(Math.floor(data.times.length / 2));
  }, [data, jobId, eegRelativePath, isControlled, onTimeIndexChange]);

  const chartPayload = useMemo(() => {
    if (!data) {
      return {
        rows: [] as Record<string, number>[],
        chNames: [] as string[],
        spacing: 1,
        yMin: 0,
        yMax: 1,
        uvpPeak: 0,
      };
    }
    const { times, ch_names, waveforms } = data;
    const nCh = ch_names.length;
    const centered = waveforms.map((row) => {
      const m = mean(row);
      return row.map((v) => v - m);
    });
    const maxAmp = centered.reduce((mx, row) => {
      const s = Math.max(...row.map((v) => Math.abs(v)), 1e-12);
      return Math.max(mx, s);
    }, 1e-12);
    const sep = compact ? 2.2 : 2.6;
    const spacing = maxAmp * sep;
    const pad = spacing * 0.65;
    const yMin = -pad;
    const yMax = (nCh - 1) * spacing + pad;

    const rows: Record<string, number>[] = [];
    for (let ti = 0; ti < times.length; ti++) {
      const o: Record<string, number> = { t: times[ti] };
      for (let ci = 0; ci < nCh; ci++) {
        o[ch_names[ci]] = centered[ci][ti] + ci * spacing;
      }
      rows.push(o);
    }
    return {
      rows,
      chNames: ch_names,
      spacing,
      yMin,
      yMax,
      uvpPeak: voltsToMicrovolts(maxAmp),
    };
  }, [data, compact]);

  const commitViewerStyle = useCallback((s: EegViewerStyle) => {
    setViewerStyle(s);
    storeViewerStyle(s);
  }, []);

  const handleChartPointer = useCallback(
    (state: {
      activeTooltipIndex?: number | string | null;
      activeLabel?: unknown;
    }) => {
      if (!data) return;
      const n = data.times.length;
      let idx: number | null = null;
      const ati = state.activeTooltipIndex;
      if (typeof ati === 'number' && ati >= 0 && ati < n) {
        idx = ati;
      } else if (typeof state.activeLabel === 'number') {
        const t = state.activeLabel;
        let best = 0;
        let bestD = Infinity;
        for (let i = 0; i < n; i++) {
          const d = Math.abs(data.times[i] - t);
          if (d < bestD) {
            bestD = d;
            best = i;
          }
        }
        idx = best;
      }
      if (idx !== null) setTimeIndex(idx);
    },
    [data, setTimeIndex]
  );

  const onChartKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!data) return;
      const maxI = data.times.length - 1;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setTimeIndex(Math.max(0, timeIndex - 1));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        setTimeIndex(Math.min(maxI, timeIndex + 1));
      } else if (e.key === 'Home') {
        e.preventDefault();
        setTimeIndex(0);
      } else if (e.key === 'End') {
        e.preventDefault();
        setTimeIndex(maxI);
      }
    },
    [data, timeIndex, setTimeIndex]
  );

  const topomapValues = useMemo(() => {
    if (!data) return { vmin: 0, vmax: 1, pts: [] as { x: number; y: number; v: number; name: string }[] };
    const { waveforms, ch_names, positions } = data;
    const ti = Math.min(timeIndex, data.times.length - 1);
    const vals = ch_names.map((_, ci) => waveforms[ci][ti]);
    const vmin = Math.min(...vals);
    const vmax = Math.max(...vals);
    const span = Math.max(Math.abs(vmin), Math.abs(vmax), 1e-12);

    const nameToV = new Map<string, number>();
    ch_names.forEach((n, i) => nameToV.set(n, vals[i]));

    const pts = positions
      .map((p) => ({
        x: p.x,
        y: p.y,
        v: nameToV.get(p.name) ?? 0,
        name: p.name,
      }))
      .filter((p) => nameToV.has(p.name));

    return { vmin: -span, vmax: span, pts };
  }, [data, timeIndex]);

  const chartHeight = compact ? 220 : 340;
  const topomapSize = compact ? 180 : 240;

  if (!jobId || !eegRelativePath) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-600 text-sm">
        {!jobId
          ? 'Select a completed job, then choose an EEG file (.edf, .fif, .vhdr, .bdf) from outputs.'
          : 'Open an EEG file from job outputs (Show Files → view) to load an MNE preview.'}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 flex items-center justify-center gap-3">
        <Spinner size="md" className="text-navy-600" />
        <span className="text-gray-600">Loading EEG preview…</span>
      </div>
    );
  }

  if (err) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
        {err}
      </div>
    );
  }

  if (!data) return null;

  const classic = viewerStyle === 'classic';
  const tiSafe = Math.min(timeIndex, Math.max(0, data.times.length - 1));
  const cursorT = data.times[tiSafe] ?? 0;

  const chartBg = classic ? '#1e1e1e' : '#ffffff';
  const gridStroke = classic ? '#3d3d3d' : '#e5e7eb';
  const axisTick = classic ? '#b0b0b0' : '#6b7280';
  const traceColors = classic
    ? chartPayload.chNames.map(() => '#d4d4d4')
    : [
        '#003d7a',
        '#0d9488',
        '#7c3aed',
        '#b45309',
        '#be123c',
        '#15803d',
        '#0369a1',
        '#a21caf',
      ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
        <span>
          <span className="font-medium text-gray-900">{data.source_file}</span>
          {' · '}
          {data.ch_names.length} ch · {data.sfreq.toFixed(0)} Hz
          {compact ? (
            <> · first {data.duration_s.toFixed(1)} s</>
          ) : (
            <>
              {' · '}
              recording {(data.total_duration_s ?? data.duration_s).toFixed(1)} s · this window{' '}
              {data.duration_s.toFixed(2)} s (~{nPointsFull} samples)
            </>
          )}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500 hidden sm:inline">View:</span>
          <div className="inline-flex rounded-md border border-gray-200 overflow-hidden text-xs">
            <button
              type="button"
              onClick={() => commitViewerStyle('classic')}
              className={`px-2.5 py-1 font-medium ${
                classic ? 'bg-gray-800 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Classic (MATLAB / EEGLAB)
            </button>
            <button
              type="button"
              onClick={() => commitViewerStyle('modern')}
              className={`px-2.5 py-1 font-medium border-l border-gray-200 ${
                !classic ? 'bg-navy-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Color
            </button>
          </div>
        </div>
      </div>

      {!compact && (() => {
        const totalDur = data.total_duration_s ?? data.duration_s;
        const t0 = data.time_offset_s ?? 0;
        const t1 = t0 + data.duration_s;
        const panMax = Math.max(0, totalDur - data.duration_s);
        const sliderVal = Math.min(tOffset, panMax);
        const step = panMax > 0 ? Math.max(0.001, panMax / 800) : 0.001;
        return (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:flex-wrap text-sm text-gray-600 bg-gray-50 rounded-lg border border-gray-200 px-3 py-2">
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs font-medium text-gray-700">Window</span>
              <button
                type="button"
                onClick={zoomIn}
                title="Shorter window — more detail (zoom in)"
                className="p-1.5 rounded border border-gray-300 bg-white hover:bg-gray-100 text-gray-800"
              >
                <Minus className="w-4 h-4" aria-hidden />
              </button>
              <button
                type="button"
                onClick={zoomOut}
                title="Longer window — more context (zoom out)"
                className="p-1.5 rounded border border-gray-300 bg-white hover:bg-gray-100 text-gray-800"
              >
                <Plus className="w-4 h-4" aria-hidden />
              </button>
              <span className="font-mono tabular-nums text-gray-900">{windowSec.toFixed(2)} s</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 min-w-[min(100%,220px)] sm:min-w-[280px]">
              <span className="text-xs text-gray-500">
                Position: {t0.toFixed(2)} s – {t1.toFixed(2)} s of {totalDur.toFixed(2)} s (drag to pan along file)
              </span>
              <input
                type="range"
                min={0}
                max={panMax}
                step={step}
                value={sliderVal}
                disabled={panMax <= 0}
                onChange={(e) => setTOffset(Number(e.target.value))}
                className="w-full accent-navy-600 disabled:opacity-40"
                aria-label="Pan along recording"
              />
            </div>
          </div>
        );
      })()}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div
          className={`lg:col-span-2 rounded-lg border p-3 ${
            classic ? 'bg-[#252526] border-gray-600' : 'bg-white border-gray-200'
          }`}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1 text-xs">
            <span className={classic ? 'text-gray-400' : 'text-gray-500'}>
              Cursor:{' '}
              <span
                className={`font-mono tabular-nums ${classic ? 'text-gray-100' : 'text-gray-900'}`}
              >
                {cursorT.toFixed(4)} s
              </span>
              {' · '}
              sample {tiSafe + 1}/{data.times.length}
            </span>
            <span className={classic ? 'text-gray-400' : 'text-gray-500'}>
              Scale ≈ ±{chartPayload.uvpPeak.toFixed(1)} µV peak (mean removed){' '}
              <span className="opacity-75">
                · click trace to seek · ← → keys
                {!compact ? ' · − / + adjust window' : ''}
              </span>
            </span>
          </div>
          <div
            ref={chartFocusRef}
            tabIndex={0}
            role="application"
            aria-label="Signal time series; use arrow keys to step time when focused"
            onMouseDown={() => chartFocusRef.current?.focus()}
            onKeyDown={onChartKeyDown}
            className="outline-none focus:ring-2 focus:ring-navy-600/40 rounded"
            style={{ width: '100%', height: chartHeight }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartPayload.rows}
                margin={{
                  top: 6,
                  right: 10,
                  left: classic ? 6 : 2,
                  bottom: 4,
                }}
                style={{ background: chartBg }}
                onClick={handleChartPointer}
              >
                <CartesianGrid
                  strokeDasharray={classic ? '2 4' : '3 3'}
                  stroke={gridStroke}
                  vertical={!classic}
                  horizontal
                />
                <XAxis
                  dataKey="t"
                  tick={{ fontSize: compact ? 9 : 10, fill: axisTick }}
                  stroke={gridStroke}
                  tickLine={{ stroke: gridStroke }}
                  label={{
                    value: 'Time (s)',
                    position: 'insideBottom',
                    offset: -2,
                    fontSize: 11,
                    fill: axisTick,
                  }}
                />
                <YAxis
                  hide={!classic}
                  domain={[chartPayload.yMin, chartPayload.yMax]}
                  ticks={chartPayload.chNames.map((_, i) => i * chartPayload.spacing)}
                  tickFormatter={(v: number) => {
                    const i = Math.round(v / chartPayload.spacing);
                    return chartPayload.chNames[i] ?? '';
                  }}
                  tick={{ fontSize: compact ? 9 : 10, fill: '#c8c8c8', fontFamily: 'ui-monospace, monospace' }}
                  stroke={gridStroke}
                  width={classic ? 44 : 0}
                  axisLine={{ stroke: gridStroke }}
                  tickLine={false}
                />
                {!classic && <YAxis hide domain={[chartPayload.yMin, chartPayload.yMax]} />}
                <Tooltip
                  contentStyle={
                    classic
                      ? { backgroundColor: '#2d2d2d', border: '1px solid #555', color: '#eee' }
                      : undefined
                  }
                  formatter={(value: any, name: any) => {
                    const rawV = typeof value === 'number' ? value : Number(value);
                    const ci = chartPayload.chNames.indexOf(String(name));
                    const baseline = ci >= 0 ? ci * chartPayload.spacing : 0;
                    const centeredV = rawV - baseline;
                    const uV = voltsToMicrovolts(centeredV);
                    return [`${uV.toFixed(2)} µV`, String(name)];
                  }}
                  labelFormatter={(t) => `t = ${Number(t).toFixed(4)} s`}
                />
                <ReferenceLine
                  x={cursorT}
                  stroke={classic ? '#fbbf24' : '#b91c1c'}
                  strokeWidth={classic ? 1.5 : 1}
                  ifOverflow="extendDomain"
                />
                {chartPayload.chNames.map((ch, i) => (
                  <Line
                    key={ch}
                    type="monotone"
                    dataKey={ch}
                    stroke={traceColors[i % traceColors.length]}
                    strokeWidth={classic ? 0.85 : 0.95}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className={`text-xs mt-2 ${classic ? 'text-gray-500' : 'text-gray-500'}`}>
            {classic
              ? 'EEGLAB-style: stacked channels (mean removed), dark background, yellow cursor. Focus the plot and use ← → to step.'
              : 'Butterfly plot: each trace mean-centered; vertical offset separates channels.'}
          </p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-3 flex flex-col items-center">
          <p className="text-xs font-medium text-gray-700 mb-2 w-full">Scalp map @ sample</p>
          {topomapValues.pts.length === 0 ? (
            <p className="text-xs text-gray-500 text-center py-8">
              No 2D positions (montage). Time slider still tracks the trace view.
            </p>
          ) : (
            <svg
              width={topomapSize}
              height={topomapSize}
              viewBox="-0.55 -0.55 1.1 1.1"
              className="text-gray-800"
            >
              <circle
                cx="0"
                cy="0"
                r="0.48"
                fill="none"
                stroke="#9ca3af"
                strokeWidth="0.012"
              />
              <line x1="-0.02" y1="0.48" x2="0.02" y2="0.48" stroke="#9ca3af" strokeWidth="0.01" />
              {topomapValues.pts.map((p) => {
                const nv = (p.v / (topomapValues.vmax || 1)) * 0.85;
                const clamped = Math.max(-1, Math.min(1, nv));
                return (
                  <circle
                    key={p.name}
                    cx={p.x}
                    cy={-p.y}
                    r="0.035"
                    fill={divergingFill(clamped)}
                    stroke="#1f2937"
                    strokeWidth="0.006"
                  >
                    <title>{`${p.name}: ${voltsToMicrovolts(p.v).toFixed(1)} µV`}</title>
                  </circle>
                );
              })}
            </svg>
          )}
          <label className="w-full mt-3 flex flex-col gap-1 text-xs text-gray-600">
            <span>Time index: {timeIndex + 1} / {data.times.length}</span>
            <input
              type="range"
              min={0}
              max={Math.max(0, data.times.length - 1)}
              value={timeIndex}
              onChange={(e) => setTimeIndex(Number(e.target.value))}
              className="w-full"
            />
          </label>
        </div>
      </div>
    </div>
  );
};

export default EegViewerPanel;
