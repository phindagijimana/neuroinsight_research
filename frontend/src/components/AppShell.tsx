/**
 * App shell — sidebar navigation and workspace layout.
 * Replaces the web-style top nav for a desktop-grade experience.
 */
import React from 'react';
import {
  Briefcase,
  LayoutDashboard,
  Eye,
  ArrowLeftRight,
  BookOpen,
  Home,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import Brain from './icons/Brain';
import EngineStatusChip from './EngineStatusChip';
import { isDesktopApp, openControlCenter } from '../lib/desktopBridge';
import type { Page } from '../App';

interface AppShellProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
  children: React.ReactNode;
}

interface NavItem {
  id: Page;
  label: string;
  icon: LucideIcon;
}

const PRIMARY_NAV: NavItem[] = [
  { id: 'jobs', label: 'Jobs', icon: Briefcase },
  { id: 'dashboard', label: 'Results', icon: LayoutDashboard },
  { id: 'viewer', label: 'Viewer', icon: Eye },
  { id: 'transfer', label: 'Transfer', icon: ArrowLeftRight },
];

const SECONDARY_NAV: NavItem[] = [
  { id: 'docs', label: 'Docs', icon: BookOpen },
  { id: 'home', label: 'Overview', icon: Home },
];

const NavButton: React.FC<{
  item: NavItem;
  active: boolean;
  onClick: () => void;
}> = ({ item, active, onClick }) => {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors border-none ${
        active
          ? 'bg-navy-600 text-white shadow-sm'
          : 'bg-transparent text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`}
    >
      <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-white' : 'text-gray-400'}`} />
      {item.label}
    </button>
  );
};

const AppShell: React.FC<AppShellProps> = ({ activePage, onNavigate, children }) => {
  const desktop = isDesktopApp();

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <aside className="flex w-56 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div
          className="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-4 py-4"
          onClick={() => onNavigate(desktop ? 'jobs' : 'home')}
          onKeyDown={(e) => e.key === 'Enter' && onNavigate(desktop ? 'jobs' : 'home')}
          role="button"
          tabIndex={0}
        >
          <div className="rounded-lg bg-navy-600 p-2">
            <Brain className="h-6 w-6 text-white" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-bold text-gray-900">NeuroInsight</div>
            <div className="text-[11px] text-gray-500">Neuroimaging Platform</div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-400">
            Workspace
          </p>
          {PRIMARY_NAV.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              active={activePage === item.id}
              onClick={() => onNavigate(item.id)}
            />
          ))}

          <p className="mb-2 mt-5 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-400">
            More
          </p>
          {SECONDARY_NAV.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              active={activePage === item.id}
              onClick={() => onNavigate(item.id)}
            />
          ))}
        </nav>

        <div className="space-y-2 border-t border-gray-100 p-3">
          <EngineStatusChip />
          {desktop ? (
            <button
              type="button"
              onClick={() => openControlCenter()}
              className="flex w-full items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              <Settings className="h-4 w-4 text-gray-400" />
              Control Center
            </button>
          ) : (
            <NavButton
              item={{ id: 'settings', label: 'Settings', icon: Settings }}
              active={activePage === 'settings'}
              onClick={() => onNavigate('settings')}
            />
          )}
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
};

export default AppShell;
