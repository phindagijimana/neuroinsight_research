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
}

const HomePage: React.FC<HomePageProps> = ({ setActivePage }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-50 via-white to-navy-50">
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid md:grid-cols-2 gap-6 items-center">
          <div className="space-y-6">
            <h2 className="text-5xl font-bold text-gray-900 leading-tight">
              HPC-Native
              <span className="text-[#003d7a]"> Neuroimaging Platform</span>
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
                    <feature.icon className="w-5 h-5 text-[#003d7a]" />
                  </div>
                  <span className="text-gray-700">{feature.text}</span>
                </div>
              ))}
            </div>

            <div className="pt-6">
              <button
                onClick={() => setActivePage('jobs')}
                className="group flex items-center gap-2 bg-[#003d7a] text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-[#002b55] transition shadow-lg hover:shadow-xl"
              >
                Get Started
                <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition" />
              </button>
            </div>
          </div>

          {/* Brain Illustration */}
          <div className="relative">
            <div className="absolute top-10 right-10 w-72 h-72 rounded-full filter blur-3xl opacity-60 animate-pulse" style={{ backgroundColor: '#003d7a' }}></div>
            <div className="absolute bottom-10 left-10 w-72 h-72 rounded-full filter blur-3xl opacity-60 animate-pulse" style={{ backgroundColor: '#003d7a', animationDelay: '1s' }}></div>

            <div className="relative bg-white rounded-2xl shadow-2xl p-8 border border-navy-100">
              <div className="flex items-center justify-center">
                <Brain className="w-64 h-64 text-[#003d7a]" />
              </div>

              <div className="mt-4 text-center">
                <p className="text-sm text-gray-500">Pipeline-Agnostic Processing</p>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Cards */}
        <div className="mt-16 grid md:grid-cols-3 gap-6">
          {[
            {
              icon: Brain,
              title: 'Pipeline Plugins and Workflows',
              description: 'YAML-based pipeline definitions. Contains pipelines like FreeSurfer, FastSurfer, QSIprep, fMRIprep, ... and common workflows.'
            },
            {
              icon: Zap,
              title: 'Works Anywhere',
              description: 'Runs locally with Docker, HPC with SLURM and Remote servers on AWS, Google Cloud, Azure.'
            },
            {
              icon: Shield,
              title: 'Research-Ready',
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
