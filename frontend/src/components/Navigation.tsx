/**
 * Navigation Component
 */

import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';
import Brain from './icons/Brain';

interface NavigationProps {
  activePage: string;
  setActivePage: (page: string) => void;
}

const NAV_ITEMS: { id: string; label: string; desktopOnly?: boolean }[] = [
  { id: 'home', label: 'Home' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'dashboard', label: 'Results' },
  { id: 'viewer', label: 'Viewer' },
  { id: 'transfer', label: 'Transfer' },
  { id: 'docs', label: 'Docs' },
  { id: 'settings', label: 'Settings', desktopOnly: true },
];

const Navigation: React.FC<NavigationProps> = ({ activePage, setActivePage }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isDesktop = typeof window !== 'undefined' && !!(window as { nir?: unknown }).nir;

  const visibleItems = NAV_ITEMS.filter((item) => !item.desktopOnly || !isDesktop);

  const navigate = (page: string) => {
    setActivePage(page);
    setMobileOpen(false);
  };

  const linkClass = (page: string) =>
    `rounded-md px-3 py-2 text-sm transition border-none bg-transparent ${
      activePage === page
        ? 'bg-navy-50 text-navy-700 font-semibold'
        : 'text-gray-600 hover:bg-slate-50 hover:text-navy-600'
    }`;

  return (
    <header className="sticky top-0 z-50 border-b border-navy-100 bg-white shadow-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-14 items-center justify-between gap-4">
          <button
            type="button"
            className="flex min-w-0 items-center gap-2.5 border-none bg-transparent p-0 text-left"
            onClick={() => navigate('home')}
          >
            <div className="rounded-lg bg-navy-600 p-1.5">
              <Brain className="h-7 w-7 text-white" />
            </div>
            <div className="min-w-0 hidden sm:block">
              <h1 className="truncate text-lg font-bold text-gray-900">NeuroInsight</h1>
              <p className="truncate text-[11px] text-gray-500">Neuroimaging Platform</p>
            </div>
          </button>

          <nav className="hidden items-center gap-0.5 md:flex">
            {visibleItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate(item.id)}
                className={linkClass(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <button
            type="button"
            className="rounded-md border border-gray-200 p-2 text-gray-600 hover:bg-slate-50 md:hidden"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <nav className="border-t border-gray-100 py-2 md:hidden">
            <div className="flex flex-col gap-0.5 pb-3">
              {visibleItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigate(item.id)}
                  className={`${linkClass(item.id)} w-full text-left`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </nav>
        )}
      </div>
    </header>
  );
};

export default Navigation;
