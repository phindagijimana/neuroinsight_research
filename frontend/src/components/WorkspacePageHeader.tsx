/**
 * Consistent page header for workspace views (matches Control Center tone).
 */
import React from 'react';

interface WorkspacePageHeaderProps {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}

const WorkspacePageHeader: React.FC<WorkspacePageHeaderProps> = ({
  title,
  subtitle,
  actions,
}) => (
  <div className="mb-6 flex flex-col gap-3 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">{title}</h1>
      {subtitle && (
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-gray-500">{subtitle}</p>
      )}
    </div>
    {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
  </div>
);

export default WorkspacePageHeader;
