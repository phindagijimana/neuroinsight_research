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
      <main className="max-w-6xl w-full mx-auto px-8 py-16 text-center">
        {/* Introduction */}
        <div className="flex flex-col items-center">
          <div className="w-20 h-20 rounded-2xl bg-navy-600 text-white flex items-center justify-center font-extrabold text-3xl tracking-wide mb-6 shadow-sm">
            NI
          </div>
          <h1 className="text-4xl font-bold text-gray-900">NeuroInsight</h1>
          <p className="text-lg text-gray-500 mt-4 max-w-2xl leading-relaxed">
            Run reproducible neuroimaging pipelines on your data — on this computer,
            your HPC cluster, or the cloud.
          </p>
        </div>

        {/* What you can do */}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mt-16 mb-6">
          What you can do
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {CAPABILITIES.map((c) => (
            <div
              key={c.title}
              className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm flex flex-col items-center text-center"
            >
              <div className="w-14 h-14 rounded-xl bg-navy-50 flex items-center justify-center mb-4">
                <c.icon className="w-7 h-7 text-navy-600" />
              </div>
              <div className="font-semibold text-lg text-gray-900">{c.title}</div>
              <p className="text-[15px] text-gray-500 mt-2 leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default HomePage;
