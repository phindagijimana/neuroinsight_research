/**
 * StatsViewer Component
 * Display REAL job statistics from /api/results/{jobId}/metrics
 *
 * Reads actual FreeSurfer .stats files, JSON metrics, and CSV data
 * from the job output directory via the backend API.
 */

import { useState, useEffect } from 'react';
import BarChart from './icons/BarChart';
import Download from './icons/Download';
import Activity from './icons/Activity';
import { apiService } from '../services/api';

interface StatsViewerProps {
  jobId: string;
  pipelineName: string;
}

interface MetricSection {
  name: string;
  data: Record<string, any>;
  table?: Record<string, any>[];
}

const convertToCSV = (data: Record<string, any>[]): string => {
  if (data.length === 0) return '';
  const headers = Object.keys(data[0]);
  const rows = data.map(row => headers.map(h => {
    const val = row[h];
    // Escape commas and quotes in string values
    if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  }).join(','));
  return [headers.join(','), ...rows].join('\n');
};

export const StatsViewer: React.FC<StatsViewerProps> = ({ jobId }) => {
  const [sections, setSections] = useState<MetricSection[]>([]);
  const [csvFiles, setCsvFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchMetrics = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiService.getJobMetrics(jobId);
        if (cancelled) return;

        // Convert metrics object into displayable sections
        const parsed: MetricSection[] = [];
        for (const [key, value] of Object.entries(data.metrics)) {
          if (typeof value === 'object' && value !== null) {
            const table = (value as any).table;
            const measures: Record<string, any> = {};
            for (const [mk, mv] of Object.entries(value as any)) {
              if (mk !== 'table') measures[mk] = mv;
            }
            parsed.push({
              name: key.replace(/_/g, ' '),
              data: measures,
              table: Array.isArray(table) ? table : undefined,
            });
          }
        }
        setSections(parsed);
        setCsvFiles(data.csv_files || []);
      } catch (err: any) {
        if (!cancelled) {
          const status = err?.response?.status;
          if (status === 404) {
            setError('No metrics available yet. Job may still be running.');
          } else {
            setError('Failed to load metrics.');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchMetrics();
    return () => { cancelled = true; };
  }, [jobId]);

  const handleDownloadCSV = (section: MetricSection) => {
    let csv: string;
    if (section.table && section.table.length > 0) {
      csv = convertToCSV(section.table);
    } else {
      // Convert key-value measures to rows
      const rows = Object.entries(section.data).map(([key, val]) => ({
        measure: key,
        value: val,
      }));
      csv = convertToCSV(rows);
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${jobId}_${section.name.replace(/\s/g, '_')}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleDownloadRemoteCSV = (csvPath: string) => {
    const baseUrl = apiService.getBaseUrl();
    window.open(`${baseUrl}/api/results/${jobId}/download?file_path=${encodeURIComponent(csvPath)}`, '_blank');
  };

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

  if (sections.length === 0 && csvFiles.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-500">No statistics available for this job.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Parsed metrics sections */}
      {sections.map((section, idx) => (
        <div key={idx} className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart className="w-5 h-5 text-[#003d7a]" />
              <h3 className="text-sm font-semibold text-gray-900 capitalize">{section.name}</h3>
            </div>
            <button
              onClick={() => handleDownloadCSV(section)}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>

          {/* Summary measures */}
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

          {/* Table data */}
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

      {/* CSV files available for download */}
      {csvFiles.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Data Files</h3>
          </div>
          <div className="p-3 space-y-1.5">
            {csvFiles.map((csvPath, idx) => (
              <button
                key={idx}
                onClick={() => handleDownloadRemoteCSV(csvPath)}
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
