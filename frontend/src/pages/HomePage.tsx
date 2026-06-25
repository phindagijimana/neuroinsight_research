/**
 * HomePage — workspace launchpad.
 *
 * Action-oriented entry point (not a marketing page): quick actions, recent
 * jobs, and engine status, so the app opens into the work.
 */
import { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import type { Job } from '../types';
import StatusBadge from '../components/StatusBadge';
import { Spinner } from '../components/LoadingState';
import Zap from '../components/icons/Zap';
import Eye from '../components/icons/Eye';
import Upload from '../components/icons/Upload';
import FileText from '../components/icons/FileText';
import ChevronRight from '../components/icons/ChevronRight';

interface HomePageProps {
  setActivePage: (page: string) => void;
  setSelectedJobId?: (jobId: string) => void;
  /** Open a local NIfTI/MGZ in the Viewer (no upload). Provided by the desktop shell. */
  onOpenLocal?: (file: File) => void;
}

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

const HomePage: React.FC<HomePageProps> = ({ setActivePage, setSelectedJobId, onOpenLocal }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiService
      .getJobs(undefined, 50)
      .then((data) => {
        if (cancelled) return;
        const recent = [...data]
          .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime())
          .slice(0, 5);
        setJobs(recent);
        setOnline(true);
      })
      .catch(() => !cancelled && setOnline(false))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const openJob = (job: Job) => {
    if (!setSelectedJobId) return;
    setSelectedJobId(job.id);
    setActivePage(job.status === 'completed' ? 'dashboard' : 'jobs');
  };

  const actions = [
    { icon: Zap, title: 'New job', desc: 'Pick data, pipeline & compute', onClick: () => setActivePage('jobs'), primary: true },
    { icon: FileText, title: 'Documentation', desc: 'Browse pipelines & workflows', onClick: () => setActivePage('docs') },
    { icon: Upload, title: 'Transfer data', desc: 'Move data between platforms', onClick: () => setActivePage('transfer') },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-end justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Workspace</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Run neuroimaging pipelines locally or on HPC — your data stays in place.
            </p>
          </div>
          <span className="inline-flex items-center gap-2 text-xs font-medium text-gray-500">
            <span
              className={`w-2 h-2 rounded-full ${
                online === false ? 'bg-gray-400' : 'bg-green-500'
              }`}
            />
            {online === false ? 'Engine offline' : 'Engine ready'}
          </span>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {actions.map((a) => (
            <button
              key={a.title}
              onClick={a.onClick}
              className={`group text-left rounded-xl border p-5 transition shadow-sm hover:shadow-md ${
                a.primary
                  ? 'bg-navy-600 border-navy-600 text-white hover:bg-navy-800'
                  : 'bg-white border-gray-200 text-gray-900 hover:border-navy-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    a.primary ? 'bg-white/15' : 'bg-navy-50'
                  }`}
                >
                  <a.icon className={`w-5 h-5 ${a.primary ? 'text-white' : 'text-navy-600'}`} />
                </div>
                <ChevronRight
                  className={`w-5 h-5 transition group-hover:translate-x-0.5 ${
                    a.primary ? 'text-white/70' : 'text-gray-300'
                  }`}
                />
              </div>
              <div className="mt-3 font-semibold">{a.title}</div>
              <div className={`text-sm ${a.primary ? 'text-white/80' : 'text-gray-500'}`}>{a.desc}</div>
            </button>
          ))}
        </div>

        {/* Open local file (desktop only) */}
        {onOpenLocal && (
          <label className="mt-4 flex items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-white px-5 py-4 cursor-pointer hover:border-navy-300 transition">
            <Eye className="w-5 h-5 text-navy-600 shrink-0" />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-900">Open an imaging file</div>
              <div className="text-xs text-gray-500">
                View a NIfTI or MGZ instantly — or drag &amp; drop one anywhere. No upload.
              </div>
            </div>
            <input
              type="file"
              accept=".nii,.nii.gz,.mgz,.mgh"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onOpenLocal(f);
                e.currentTarget.value = '';
              }}
            />
          </label>
        )}

        {/* Recent jobs */}
        <section className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-900">Recent jobs</h2>
            <button onClick={() => setActivePage('jobs')} className="text-sm text-navy-600 hover:underline">
              View all
            </button>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100">
            {loading ? (
              <div className="py-10 flex justify-center">
                <Spinner size="md" className="text-navy-600" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-gray-500">
                No jobs yet — start one with <span className="font-medium text-gray-700">New job</span>.
              </div>
            ) : (
              jobs.map((job) => (
                <button
                  key={job.id}
                  onClick={() => openJob(job)}
                  className="w-full text-left px-5 py-3 flex items-center gap-4 hover:bg-gray-50 transition"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {job.display_name || job.pipeline_name}
                    </div>
                    <div className="text-xs text-gray-500">{formatWhen(job.submitted_at)}</div>
                  </div>
                  <StatusBadge status={job.status} className="shrink-0" />
                  <ChevronRight className="w-4 h-4 text-gray-300 shrink-0" />
                </button>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default HomePage;
