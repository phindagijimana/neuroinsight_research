/**
 * StatsViewer Component
 * Display job statistics in CSV/table format
 */

import { useState, useEffect } from 'react';
import BarChart from './icons/BarChart';
import Download from './icons/Download';
import Activity from './icons/Activity';

interface StatsViewerProps {
  jobId: string;
  pipelineName: string;
}

interface StatRow {
  [key: string]: string | number;
}

// Mock stats generator - reflects plugin/workflow outputs
const generateMockStats = (pipelineName: string): StatRow[] => {
  const lowerName = pipelineName.toLowerCase();
  
  // Structural workflows (FreeSurfer, FastSurfer, Hippocampal, Lesion Detection)
  if (lowerName.includes('freesurfer') || lowerName.includes('fastsurfer') || 
      lowerName.includes('structural') || lowerName.includes('hippocampal') || 
      lowerName.includes('lesion')) {
    return [
      { structure: 'Left Hippocampus', volume_mm3: 4049, percentage_icv: 0.34, percentile: 65 },
      { structure: 'Right Hippocampus', volume_mm3: 3841, percentage_icv: 0.32, percentile: 58 },
      { structure: 'Left Amygdala', volume_mm3: 1673, percentage_icv: 0.14, percentile: 72 },
      { structure: 'Right Amygdala', volume_mm3: 1589, percentage_icv: 0.13, percentile: 68 },
      { structure: 'Left Thalamus', volume_mm3: 7852, percentage_icv: 0.65, percentile: 55 },
      { structure: 'Right Thalamus', volume_mm3: 7934, percentage_icv: 0.66, percentile: 57 },
      { structure: 'Left Caudate', volume_mm3: 3567, percentage_icv: 0.30, percentile: 61 },
      { structure: 'Right Caudate', volume_mm3: 3498, percentage_icv: 0.29, percentile: 60 },
      { structure: 'Left Putamen', volume_mm3: 5123, percentage_icv: 0.43, percentile: 63 },
      { structure: 'Right Putamen', volume_mm3: 5056, percentage_icv: 0.42, percentile: 62 },
      { structure: 'Corpus Callosum', volume_mm3: 2145, percentage_icv: 0.18, percentile: 70 },
      { structure: 'Brain Stem', volume_mm3: 21456, percentage_icv: 1.79, percentile: 54 },
      { structure: 'Total Brain Volume', volume_mm3: 1201464, percentage_icv: 100.0, percentile: 59 },
    ];
  } 
  
  // fMRI workflows (fMRIPrep, XCP-D, connectivity)
  else if (lowerName.includes('fmri') || lowerName.includes('bold') || 
           lowerName.includes('functional') || lowerName.includes('connectivity')) {
    return [
      { metric: 'Mean Framewise Displacement', value: 0.184, unit: 'mm', threshold: '< 0.5 mm', status: 'Pass' },
      { metric: 'Max Framewise Displacement', value: 1.243, unit: 'mm', threshold: '< 5.0 mm', status: 'Pass' },
      { metric: 'Mean DVARS', value: 1.052, unit: '%', threshold: '< 1.5%', status: 'Pass' },
      { metric: 'Network Edges (50% threshold)', value: 4560, unit: 'edges', threshold: '> 1000', status: 'Pass' },
      { metric: 'Global Signal Mean', value: 452.3, unit: 'a.u.', threshold: 'N/A', status: 'Info' },
      { metric: 'Temporal SNR (mean)', value: 87.4, unit: 'ratio', threshold: '> 50', status: 'Pass' },
      { metric: 'Volumes with FD > 0.5mm', value: 12, unit: 'vols', threshold: '< 20%', status: 'Pass' },
      { metric: 'Slice-to-slice correlation', value: 0.943, unit: 'r', threshold: '> 0.85', status: 'Pass' },
    ];
  } 
  
  // Diffusion workflows (QSIPrep, QSIRecon, tractography)
  else if (lowerName.includes('qsiprep') || lowerName.includes('qsirecon') ||
           lowerName.includes('dwi') || lowerName.includes('diffusion')) {
    return [
      { tract: 'Corticospinal Tract L', fa: 0.542, md: 0.000734, ad: 0.001234, rd: 0.000434, volume_mm3: 3456 },
      { tract: 'Corticospinal Tract R', fa: 0.548, md: 0.000728, ad: 0.001228, rd: 0.000428, volume_mm3: 3521 },
      { tract: 'Corpus Callosum', fa: 0.512, md: 0.000712, ad: 0.001234, rd: 0.000468, volume_mm3: 2145 },
      { tract: 'Fornix', fa: 0.453, md: 0.000856, ad: 0.001456, rd: 0.000556, volume_mm3: 456 },
      { tract: 'Cingulum L', fa: 0.398, md: 0.000789, ad: 0.001289, rd: 0.000489, volume_mm3: 1234 },
      { tract: 'Cingulum R', fa: 0.405, md: 0.000776, ad: 0.001276, rd: 0.000476, volume_mm3: 1198 },
      { tract: 'Uncinate L', fa: 0.367, md: 0.000834, ad: 0.001334, rd: 0.000534, volume_mm3: 892 },
      { tract: 'Uncinate R', fa: 0.374, md: 0.000821, ad: 0.001321, rd: 0.000521, volume_mm3: 910 },
      { tract: 'ILF L', fa: 0.412, md: 0.000798, ad: 0.001298, rd: 0.000498, volume_mm3: 1567 },
      { tract: 'ILF R', fa: 0.419, md: 0.000785, ad: 0.001285, rd: 0.000485, volume_mm3: 1589 },
    ];
  }
  
  return [];
};

const convertToCSV = (data: StatRow[]): string => {
  if (data.length === 0) return '';
  
  const headers = Object.keys(data[0]);
  const rows = data.map(row => headers.map(header => row[header]).join(','));
  
  return [headers.join(','), ...rows].join('\n');
};

export const StatsViewer: React.FC<StatsViewerProps> = ({ jobId, pipelineName }) => {
  const [stats, setStats] = useState<StatRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate API call
    setLoading(true);
    setTimeout(() => {
      setStats(generateMockStats(pipelineName));
      setLoading(false);
    }, 300);
  }, [jobId, pipelineName]);

  const handleDownloadCSV = () => {
    const csv = convertToCSV(stats);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${jobId}_statistics.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
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

  if (stats.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-600">No statistics available for this job.</p>
      </div>
    );
  }

  const headers = Object.keys(stats[0]);

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart className="w-5 h-5 text-[#003d7a]" />
          <h3 className="text-sm font-semibold text-gray-900">Statistics & Metrics</h3>
        </div>
        <button
          onClick={handleDownloadCSV}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition"
        >
          <Download className="w-4 h-4" />
          Download CSV
        </button>
      </div>
      <div className="p-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              {headers.map((header, idx) => (
                <th
                  key={idx}
                  className="px-4 py-2 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                >
                  {header.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {stats.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                {headers.map((header, colIdx) => (
                  <td key={colIdx} className="px-4 py-2 text-gray-900">
                    {typeof row[header] === 'number' && !header.includes('volume')
                      ? Number(row[header]).toFixed(3)
                      : String(row[header]).toLocaleString()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default StatsViewer;
