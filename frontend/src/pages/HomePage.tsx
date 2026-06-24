/**
 * HomePage Component
 * Adapted from NeuroInsight for NeuroInsight Research
 */

import Zap from '../components/icons/Zap';
import Activity from '../components/icons/Activity';
import CheckCircle from '../components/icons/CheckCircle';
import ChevronRight from '../components/icons/ChevronRight';
import Shield from '../components/icons/Shield';
import Brain from '../components/icons/Brain';

interface HomePageProps {
  setActivePage: (page: string) => void;
  /** Open a local NIfTI/MGZ in the Viewer (no upload). Provided by the desktop/app shell. */
  onOpenLocal?: (file: File) => void;
}

const HomePage: React.FC<HomePageProps> = ({ setActivePage, onOpenLocal }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-50 via-white to-navy-50">
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="max-w-3xl">
          <div className="space-y-6">
            <h2 className="text-5xl font-bold text-gray-900 leading-tight">
              <span className="text-navy-600">Run neuroimaging pipelines, anywhere</span>
            </h2>

            <p className="text-lg text-gray-600 leading-relaxed">
              Process neuroimaging data with production-ready pipelines. Works both locally 
              or on a remote computer. Data stays in place—no upload needed.
            </p>

            <div className="grid grid-cols-1 gap-3 pt-4">
              {[
                { icon: Zap, text: 'Batch process hundreds of scans at once' },
                { icon: Activity, text: 'Multiple pipelines: FreeSurfer, FastSurfer, and more' },
                { icon: CheckCircle, text: 'Directory-based workflow—no file uploads' },
                { icon: Shield, text: 'Secure: data never leaves your machine or HPC' }
              ].map((feature, idx) => (
                <div key={idx} className="flex items-center gap-3">
                  <div className="bg-navy-100 p-2 rounded-lg">
                    <feature.icon className="w-5 h-5 text-navy-600" />
                  </div>
                  <span className="text-gray-700">{feature.text}</span>
                </div>
              ))}
            </div>

            <div className="pt-6 flex flex-wrap items-center gap-3">
              <button
                onClick={() => setActivePage('jobs')}
                className="group flex items-center gap-2 bg-navy-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-navy-800 transition shadow-lg hover:shadow-xl"
              >
                New Job
                <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition" />
              </button>
              {onOpenLocal && (
                <label className="flex items-center gap-2 bg-white text-navy-600 px-6 py-4 rounded-xl font-semibold text-lg border border-navy-100 hover:bg-navy-50 transition cursor-pointer shadow-sm">
                  <Brain className="w-5 h-5" />
                  Open Imaging File
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
            </div>
            {onOpenLocal && (
              <p className="text-sm text-gray-500">
                Tip: drag &amp; drop a NIfTI or MGZ file anywhere to view it instantly — no upload.
              </p>
            )}
          </div>
        </div>

        {/* Feature Cards */}
        <div className="mt-16 grid md:grid-cols-3 gap-6">
          {[
            {
              icon: Brain,
              title: 'Pipelines & workflows',
              description: 'YAML-based pipeline definitions. Contains pipelines like FreeSurfer, FastSurfer, QSIprep, fMRIprep, ... and common workflows.'
            },
            {
              icon: Zap,
              title: 'Local, HPC, or cloud',
              description: 'Runs locally with Docker, HPC with SLURM and Remote servers on AWS, Google Cloud, Azure.'
            },
            {
              icon: Shield,
              title: 'Data stays in place',
              description: 'Data governance compliant. No cloud uploads. Runs where your data already lives.'
            }
          ].map((feature, idx) => (
            <div key={idx} className="bg-white rounded-xl p-6 shadow-lg border border-navy-100 hover:shadow-xl transition">
              <div className="bg-navy-100 w-12 h-12 rounded-lg flex items-center justify-center mb-4">
                <feature.icon className="w-6 h-6 text-navy-800" />
              </div>
              <h4 className="text-xl font-bold text-gray-900 mb-2">{feature.title}</h4>
              <p className="text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default HomePage;
