/**
 * Collapsible left file drawer for the Viewer (Horos / OsiriX style).
 */
import React from 'react';
import { ChevronLeft, ChevronRight, FolderTree } from 'lucide-react';
import FileBrowser, { type ViewerFileMode } from './FileBrowser';

interface ViewerFileDrawerProps {
  open: boolean;
  onToggle: () => void;
  jobId: string;
  onFileSelect: (downloadPath: string) => void;
  viewerFileMode: ViewerFileMode;
}

const ViewerFileDrawer: React.FC<ViewerFileDrawerProps> = ({
  open,
  onToggle,
  jobId,
  onFileSelect,
  viewerFileMode,
}) => {
  if (!open) {
    return (
      <div className="flex w-10 shrink-0 flex-col border-r border-gray-200 bg-gray-50">
        <button
          type="button"
          onClick={onToggle}
          className="flex flex-1 flex-col items-center justify-center gap-1 px-1 py-4 text-gray-500 hover:bg-gray-100 hover:text-navy-700"
          title="Show output files"
          aria-label="Show output files"
        >
          <ChevronRight className="h-4 w-4" />
          <FolderTree className="h-4 w-4" />
          <span className="text-[10px] font-semibold uppercase tracking-widest [writing-mode:vertical-rl] rotate-180">
            Files
          </span>
        </button>
      </div>
    );
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-gray-200 bg-white xl:w-80">
      <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2.5">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900">Output files</p>
          <p className="truncate text-[11px] text-gray-500">Click a volume to load</p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800"
          title="Hide file list"
          aria-label="Hide file list"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <FileBrowser
          key={`${jobId}-${viewerFileMode}`}
          jobId={jobId}
          onFileSelect={onFileSelect}
          showDownload={true}
          showViewButton={true}
          viewerFileMode={viewerFileMode}
          variant="embedded"
        />
      </div>
    </aside>
  );
};

export default ViewerFileDrawer;
