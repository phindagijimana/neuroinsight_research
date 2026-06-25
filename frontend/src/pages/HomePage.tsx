/**
 * HomePage — introduction / orientation.
 *
 * A calm, professional landing that tells a new user what NeuroInsight is and
 * what it can do. It deliberately does NOT duplicate the workspace (jobs,
 * transfer, viewer, docs) — those live in their own pages, reached from the
 * navigation. Just an introduction.
 */
import Brain from '../components/icons/Brain';
import Shield from '../components/icons/Shield';
import { Server } from 'lucide-react';

interface HomePageProps {
  // Kept for call-site compatibility; the intro page navigates via the app nav.
  setActivePage: (page: string) => void;
  setSelectedJobId?: (jobId: string) => void;
  onOpenLocal?: (file: File) => void;
}

const CAPABILITIES = [
  {
    icon: Brain,
    title: 'Pipelines & workflows',
    desc: 'Curated neuroimaging tools — MELD lesion detection, FreeSurfer, dcm2niix — run as versioned, reproducible jobs.',
  },
  {
    icon: Server,
    title: 'Compute anywhere',
    desc: 'Run on this computer with Docker, on your HPC cluster via SLURM, or a cloud server — the same workflow.',
  },
  {
    icon: Shield,
    title: 'Your data stays in place',
    desc: 'Browse and process data where it lives — local disk, HPC filesystem, or a connected repository.',
  },
];

const HomePage: React.FC<HomePageProps> = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <main className="max-w-5xl w-full mx-auto px-6 py-12 text-center">
        {/* Introduction */}
        <div className="flex flex-col items-center">
          <div className="w-14 h-14 rounded-xl bg-navy-600 text-white flex items-center justify-center font-extrabold text-xl tracking-wide mb-4">
            NI
          </div>
          <h1 className="text-3xl font-bold text-gray-900">NeuroInsight</h1>
          <p className="text-base text-gray-500 mt-2 max-w-2xl">
            Run reproducible neuroimaging pipelines on your data — on this computer,
            your HPC cluster, or the cloud.
          </p>
        </div>

        {/* What you can do */}
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mt-12 mb-4">
          What you can do
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {CAPABILITIES.map((c) => (
            <div
              key={c.title}
              className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm flex flex-col items-center text-center"
            >
              <div className="w-11 h-11 rounded-lg bg-navy-50 flex items-center justify-center mb-3">
                <c.icon className="w-5 h-5 text-navy-600" />
              </div>
              <div className="font-semibold text-gray-900">{c.title}</div>
              <p className="text-sm text-gray-500 mt-1 leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default HomePage;
