/**
 * Navigation Component
 * Adapted from NeuroInsight for NeuroInsight Research
 */

import React from 'react';
import Brain from './icons/Brain';

interface NavigationProps {
  activePage: string;
  setActivePage: (page: string) => void;
}

const Navigation: React.FC<NavigationProps> = ({ activePage, setActivePage }) => {

  return (
    <header className="bg-white border-b border-navy-100 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActivePage('home')}>
            <div className="bg-[#003d7a] p-2 rounded-lg">
              <Brain className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">NeuroInsight Research</h1>
              <p className="text-xs text-gray-500">Neuroimaging Platform</p>
            </div>
          </div>
          <nav className="flex gap-6">
            <button
              onClick={() => setActivePage('home')}
              className={`transition border-none bg-transparent ${
                activePage === 'home' ? 'text-[#003d7a] font-semibold' : 'text-gray-600 hover:text-[#003d7a]'
              }`}
            >
              Home
            </button>
            <button
              onClick={() => setActivePage('jobs')}
              className={`transition border-none bg-transparent ${
                activePage === 'jobs' ? 'text-[#003d7a] font-semibold' : 'text-gray-600 hover:text-[#003d7a]'
              }`}
            >
              Jobs
            </button>
            <button
              onClick={() => setActivePage('dashboard')}
              className={`transition border-none bg-transparent ${
                activePage === 'dashboard' ? 'text-[#003d7a] font-semibold' : 'text-gray-600 hover:text-[#003d7a]'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setActivePage('viewer')}
              className={`transition border-none bg-transparent ${
                activePage === 'viewer' ? 'text-[#003d7a] font-semibold' : 'text-gray-600 hover:text-[#003d7a]'
              }`}
            >
              Viewer
            </button>
            <button
              onClick={() => setActivePage('docs')}
              className={`transition border-none bg-transparent ${
                activePage === 'docs' ? 'text-[#003d7a] font-semibold' : 'text-gray-600 hover:text-[#003d7a]'
              }`}
            >
              Docs
            </button>
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Navigation;
