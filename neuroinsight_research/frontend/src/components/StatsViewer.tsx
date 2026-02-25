/**
 * StatsViewer Component
 *
 * Displays plugin-aware structured statistics from completed jobs.
 * Uses the /api/results/{jobId}/stats/csv endpoint for structured data
 * with fallback to /api/results/{jobId}/metrics for legacy jobs.
 */

import { useState, useEffect, useMemo } from 'react';
import BarChart from './icons/BarChart';
import Download from './icons/Download';
import Activity from './icons/Activity';
import { apiService } from '../services/api';

interface StatsViewerProps {
  jobId: string;
  pipelineName: string;
}

interface CSVData {
  name: string;
  filename: string;
  description: string;
  category: string;
  headers: string[];
  rows: any[][];
  total_rows: number;
  truncated: boolean;
}

interface LegacyMetricSection {
  name: string;
  data: Record<string, any>;
  table?: Record<string, any>[];
}

type SortDir = 'asc' | 'desc' | null;

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  volumetric: { label: 'Volumetric', color: 'bg-navy-100 text-navy-800' },
  cortical: { label: 'Cortical', color: 'bg-purple-100 text-purple-800' },
  hippocampal: { label: 'Hippocampal', color: 'bg-green-100 text-green-800' },
  longitudinal: { label: 'Longitudinal', color: 'bg-amber-100 text-amber-800' },
  clinical: { label: 'Clinical', color: 'bg-navy-100 text-navy-800' },
  connectivity: { label: 'Connectivity', color: 'bg-navy-100 text-navy-800' },
  quality: { label: 'Quality Control', color: 'bg-teal-100 text-teal-800' },
  general: { label: 'General', color: 'bg-gray-100 text-gray-700' },
};

const convertToCSV = (headers: string[], rows: any[][]): string => {
  const escape = (val: any): string => {
    const s = String(val ?? '');
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  return [
    headers.map(escape).join(','),
    ...rows.map(row => row.map(escape).join(',')),
  ].join('\n');
};

export const StatsViewer: React.FC<StatsViewerProps> = ({ jobId, pipelineName }) => {
  const [csvData, setCsvData] = useState<CSVData[]>([]);
  const [legacySections, setLegacySections] = useState<LegacyMetricSection[]>([]);
  const [legacyCsvFiles, setLegacyCsvFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pipelineLabel, setPipelineLabel] = useState(pipelineName);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [sortStates, setSortStates] = useState<Record<string, { col: number; dir: SortDir }>>({});
  const [searchTerms, setSearchTerms] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      // Try the new structured endpoint first
      try {
        const data = await apiService.getStatsCSVs(jobId);
        if (cancelled) return;
        if (data.csvs && data.csvs.length > 0) {
          setCsvData(data.csvs);
          setPipelineLabel(data.pipeline_name || pipelineName);
          // Auto-expand first two sections
          const initial = new Set<string>();
          data.csvs.slice(0, 2).forEach(c => initial.add(c.filename));
          setExpandedSections(initial);
          setLoading(false);
          return;
        }
      } catch {
        // Structured endpoint not available, fall through to legacy
      }

      // Fallback to legacy metrics endpoint
      try {
        const data = await apiService.getJobMetrics(jobId);
        if (cancelled) return;
        const parsed: LegacyMetricSection[] = [];
        for (const [key, value] of Object.entries(data.metrics)) {
          if (typeof value === 'object' && value !== null) {
            const table = (value as any).table;
            const measures: Record<string, any> = {};
            for (const [mk, mv] of Object.entries(value as any)) {
              if (mk !== 'table') measures[mk] = mv;
            }
            parsed.push({ name: key.replace(/_/g, ' '), data: measures, table: Array.isArray(table) ? table : undefined });
          }
        }
        setLegacySections(parsed);
        setLegacyCsvFiles(data.csv_files || []);
      } catch (err: any) {
        if (!cancelled) {
          const status = err?.response?.status;
          if (status === 404) {
            setError('No statistics available yet. Job may still be running.');
          } else {
            setError('Failed to load statistics.');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [jobId, pipelineName]);

  const toggleSection = (filename: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const handleSort = (filename: string, colIdx: number) => {
    setSortStates(prev => {
      const current = prev[filename];
      let dir: SortDir = 'asc';
      if (current?.col === colIdx) {
        dir = current.dir === 'asc' ? 'desc' : current.dir === 'desc' ? null : 'asc';
      }
      return { ...prev, [filename]: { col: colIdx, dir } };
    });
  };

  const getSortedRows = (csv: CSVData): any[][] => {
    const sort = sortStates[csv.filename];
    const search = (searchTerms[csv.filename] || '').toLowerCase();
    let rows = csv.rows;

    if (search) {
      rows = rows.filter(row =>
        row.some(val => String(val ?? '').toLowerCase().includes(search))
      );
    }

    if (!sort || sort.dir === null) return rows;

    return [...rows].sort((a, b) => {
      const va = a[sort.col];
      const vb = b[sort.col];
      const na = typeof va === 'number' ? va : parseFloat(va);
      const nb = typeof vb === 'number' ? vb : parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) {
        return sort.dir === 'asc' ? na - nb : nb - na;
      }
      const sa = String(va ?? '');
      const sb = String(vb ?? '');
      return sort.dir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  };

  const handleDownloadCSV = (csv: CSVData) => {
    apiService.downloadStatsCSV(jobId, csv.filename);
  };

  const handleDownloadAllCSVs = () => {
    csvData.forEach(csv => {
      apiService.downloadStatsCSV(jobId, csv.filename);
    });
  };

  const handleClientCSVDownload = (section: LegacyMetricSection) => {
    let csvStr: string;
    if (section.table && section.table.length > 0) {
      const headers = Object.keys(section.table[0]);
      const rows = section.table.map(row => headers.map(h => row[h]));
      csvStr = convertToCSV(headers, rows);
    } else {
      const rows = Object.entries(section.data).map(([key, val]) => [key, val]);
      csvStr = convertToCSV(['measure', 'value'], rows);
    }
    const blob = new Blob([csvStr], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${jobId.slice(0, 8)}_${section.name.replace(/\s/g, '_')}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Group CSVs by category
  const groupedCsvs = useMemo(() => {
    const groups: Record<string, CSVData[]> = {};
    csvData.forEach(csv => {
      const cat = csv.category || 'general';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(csv);
    });
    return groups;
  }, [csvData]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-center gap-3">
          <Activity className="w-5 h-5 text-[#003d7a] animate-spin" />
          <span className="text-gray-600">Loading statistics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  // No data at all
  if (csvData.length === 0 && legacySections.length === 0 && legacyCsvFiles.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-500">No statistics available for this job.</p>
      </div>
    );
  }

  // ======================== New structured CSV display ========================
  if (csvData.length > 0) {
    return (
      <div className="space-y-4">
        {/* Header with summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart className="w-5 h-5 text-[#003d7a]" />
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                {pipelineLabel} Statistics
              </h3>
              <p className="text-xs text-gray-500">
                {csvData.length} dataset{csvData.length !== 1 ? 's' : ''} available
              </p>
            </div>
          </div>
          {csvData.length > 1 && (
            <button
              onClick={handleDownloadAllCSVs}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] transition"
            >
              <Download className="w-3.5 h-3.5" />
              Download All CSVs
            </button>
          )}
        </div>

        {/* Category groups */}
        {Object.entries(groupedCsvs).map(([category, csvs]) => (
          <div key={category} className="space-y-3">
            {/* Category header */}
            {Object.keys(groupedCsvs).length > 1 && (
              <div className="flex items-center gap-2 pt-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  CATEGORY_LABELS[category]?.color || CATEGORY_LABELS.general.color
                }`}>
                  {CATEGORY_LABELS[category]?.label || category}
                </span>
                <div className="flex-1 border-b border-gray-200" />
              </div>
            )}

            {/* CSV sections */}
            {csvs.map(csv => {
              const isExpanded = expandedSections.has(csv.filename);
              const sortedRows = isExpanded ? getSortedRows(csv) : [];
              const sort = sortStates[csv.filename];
              const search = searchTerms[csv.filename] || '';

              return (
                <div key={csv.filename} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                  {/* Section header - always visible */}
                  <button
                    onClick={() => toggleSection(csv.filename)}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition"
                  >
                    <div className="flex items-center gap-3 text-left">
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900">{csv.name}</h4>
                        <p className="text-xs text-gray-500">{csv.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">
                        {csv.total_rows} row{csv.total_rows !== 1 ? 's' : ''}
                      </span>
                      <div
                        onClick={(e) => { e.stopPropagation(); handleDownloadCSV(csv); }}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition cursor-pointer"
                      >
                        <Download className="w-3 h-3" />
                        CSV
                      </div>
                    </div>
                  </button>

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="border-t border-gray-200">
                      {/* Search bar for tables with many rows */}
                      {csv.total_rows > 10 && (
                        <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
                          <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearchTerms(prev => ({ ...prev, [csv.filename]: e.target.value }))}
                            placeholder="Filter rows..."
                            className="w-full max-w-xs px-3 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a] focus:border-[#003d7a]"
                          />
                        </div>
                      )}

                      {/* Summary cards for key-value datasets */}
                      {csv.headers.length <= 3 && csv.headers[0]?.toLowerCase().includes('measure') && (
                        <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 border-b border-gray-100">
                          {csv.rows.slice(0, 12).map((row, idx) => (
                            <div key={idx} className="bg-gray-50 rounded-lg p-2.5">
                              <div className="text-xs text-gray-500 truncate" title={String(row[0])}>
                                {String(row[0]).replace(/_/g, ' ')}
                              </div>
                              <div className="text-sm font-semibold text-gray-900">
                                {typeof row[1] === 'number'
                                  ? row[1].toLocaleString(undefined, { maximumFractionDigits: 2 })
                                  : String(row[1] ?? '')}
                              </div>
                              {row[2] && (
                                <div className="text-xs text-gray-400">{String(row[2])}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Data table */}
                      <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="sticky top-0 bg-gray-50 z-10">
                            <tr>
                              {csv.headers.map((header, ci) => (
                                <th
                                  key={ci}
                                  onClick={() => handleSort(csv.filename, ci)}
                                  className="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                                >
                                  <span className="inline-flex items-center gap-1">
                                    {header.replace(/_/g, ' ')}
                                    {sort?.col === ci && sort.dir === 'asc' && <span className="text-[#003d7a]">&#9650;</span>}
                                    {sort?.col === ci && sort.dir === 'desc' && <span className="text-[#003d7a]">&#9660;</span>}
                                    {(sort?.col !== ci || sort?.dir === null) && (
                                      <span className="text-gray-300">&#9650;&#9660;</span>
                                    )}
                                  </span>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {sortedRows.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-navy-50/30">
                                {row.map((val, cIdx) => (
                                  <td key={cIdx} className="px-3 py-1.5 text-gray-900 whitespace-nowrap">
                                    {typeof val === 'number'
                                      ? val.toLocaleString(undefined, { maximumFractionDigits: 4 })
                                      : String(val ?? '')}
                                  </td>
                                ))}
                              </tr>
                            ))}
                            {sortedRows.length === 0 && (
                              <tr>
                                <td colSpan={csv.headers.length} className="px-3 py-4 text-center text-gray-400 text-xs">
                                  {search ? 'No matching rows' : 'No data'}
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>

                      {/* Truncation notice */}
                      {csv.truncated && (
                        <div className="px-4 py-2 bg-navy-50 border-t border-navy-100 text-xs text-navy-700">
                          Showing {csv.rows.length} of {csv.total_rows} rows. Download CSV for the full dataset.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    );
  }

  // ======================== Legacy metrics display ========================
  return (
    <div className="space-y-4">
      {legacySections.map((section, idx) => (
        <div key={idx} className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart className="w-5 h-5 text-[#003d7a]" />
              <h3 className="text-sm font-semibold text-gray-900 capitalize">{section.name}</h3>
            </div>
            <button
              onClick={() => handleClientCSVDownload(section)}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>

          {Object.keys(section.data).length > 0 && (
            <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-3 gap-3 border-b border-gray-100">
              {Object.entries(section.data).slice(0, 12).map(([key, val]) => (
                <div key={key}>
                  <div className="text-xs text-gray-500 truncate">{key.replace(/_/g, ' ')}</div>
                  <div className="text-sm font-medium text-gray-900">
                    {typeof val === 'number' ? val.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(val)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {section.table && section.table.length > 0 && (
            <div className="p-4 overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-gray-200">
                    {Object.keys(section.table[0]).map((header, i) => (
                      <th key={i} className="px-3 py-2 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                        {header.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {section.table.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-gray-50">
                      {Object.values(row).map((val, cIdx) => (
                        <td key={cIdx} className="px-3 py-1.5 text-gray-900">
                          {typeof val === 'number'
                            ? val.toLocaleString(undefined, { maximumFractionDigits: 4 })
                            : String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}

      {legacyCsvFiles.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Data Files</h3>
          </div>
          <div className="p-3 space-y-1.5">
            {legacyCsvFiles.map((csvPath, idx) => (
              <button
                key={idx}
                onClick={() => {
                  const baseUrl = apiService.getBaseUrl();
                  window.open(`${baseUrl}/api/results/${jobId}/download?file_path=${encodeURIComponent(csvPath)}`, '_blank');
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-gray-50 rounded-md transition"
              >
                <Download className="w-4 h-4 text-[#003d7a] flex-shrink-0" />
                <span className="text-gray-700 truncate">{csvPath}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StatsViewer;
