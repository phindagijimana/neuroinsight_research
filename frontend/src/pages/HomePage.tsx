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
import { Server, ArrowRight } from 'lucide-react';
import WorkspacePageHeader from '../components/WorkspacePageHeader';
import { isDesktopApp } from '../lib/desktopBridge';

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
    desc: 'MELD, FreeSurfer, dcm2niix — reproducible jobs.',
  },
  {
    icon: Server,
    title: 'Compute anywhere',
    desc: 'This computer, your HPC cluster, or the cloud.',
  },
  {
    icon: Shield,
    title: 'Your data stays in place',
    desc: 'Process data where it lives.',
  },
];

const HomePage: React.FC<HomePageProps> = ({ setActivePage }) => {
  return (
    <div className="min-h-full">
      <div className="mx-auto max-w-6xl px-6 py-8 sm:px-8">
        <WorkspacePageHeader
          title="Overview"
          subtitle="NeuroInsight runs reproducible neuroimaging pipelines locally, on HPC, or in the cloud."
        />

        <div className="flex flex-col items-center py-8 text-center">
          <div className="w-20 h-20 rounded-2xl bg-navy-600 text-white flex items-center justify-center font-extrabold text-3xl tracking-wide mb-6 shadow-sm">
            NI
          </div>
          <h1 className="text-4xl font-bold text-gray-900">NeuroInsight</h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-gray-500">
            Run reproducible neuroimaging pipelines on your data — on this computer,
            your HPC cluster, or the cloud.
          </p>
          <button
            type="button"
            onClick={() => setActivePage('jobs')}
            className="mt-8 inline-flex items-center gap-2 rounded-lg bg-navy-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-navy-800 transition-colors border-none"
          >
            {isDesktopApp() ? 'Open Jobs' : 'Get started'}
            <ArrowRight className="h-4 w-4" />
          </button>
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
      </div>
    </div>
  );
};

export default HomePage;
