import React from 'react';

interface WorkspaceEmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

const WorkspaceEmptyState: React.FC<WorkspaceEmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => (
  <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
    {icon && (
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-navy-600">
        {icon}
      </div>
    )}
    <p className="text-sm font-medium text-gray-700">{title}</p>
    {description && (
      <p className="mt-1 max-w-xs text-xs leading-relaxed text-gray-500">{description}</p>
    )}
    {action && <div className="mt-3">{action}</div>}
  </div>
);

export default WorkspaceEmptyState;
