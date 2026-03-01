import { useState, useEffect } from 'react';
import { X, Save, Trash2, RotateCcw, GitCompare } from 'lucide-react';
import { useVersionStore, type VersionSummary } from '../../stores/versionStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';

export default function VersionPanel() {
  const panelOpen = useVersionStore((s) => s.panelOpen);
  const togglePanel = useVersionStore((s) => s.togglePanel);
  const versions = useVersionStore((s) => s.versions);
  const loading = useVersionStore((s) => s.loading);
  const loadVersions = useVersionStore((s) => s.loadVersions);
  const saveVersion = useVersionStore((s) => s.saveVersion);
  const removeVersion = useVersionStore((s) => s.removeVersion);
  const restore = useVersionStore((s) => s.restore);
  const computeDiff = useVersionStore((s) => s.computeDiff);
  const diffResult = useVersionStore((s) => s.diffResult);
  const projectId = useFlowsheetStore((s) => s.currentProjectId);
  const initProject = useFlowsheetStore((s) => s.initProject);

  const [label, setLabel] = useState('');
  const [diffV1, setDiffV1] = useState<string>('');
  const [diffV2, setDiffV2] = useState<string>('');

  useEffect(() => {
    if (panelOpen && projectId) {
      loadVersions(projectId);
    }
  }, [panelOpen, projectId]);

  if (!panelOpen) return null;

  const handleSave = async () => {
    if (!projectId) return;
    await saveVersion(projectId, label || undefined);
    setLabel('');
  };

  const handleRestore = async (v: VersionSummary) => {
    if (!projectId) return;
    await restore(projectId, v.id);
    await initProject();
  };

  const handleDiff = async () => {
    if (!projectId || !diffV1 || !diffV2) return;
    await computeDiff(projectId, diffV1, diffV2);
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString();
  };

  return (
    <div className="fixed right-0 top-12 bottom-0 w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Version History</h3>
        <button onClick={togglePanel} className="p-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
          <X size={16} />
        </button>
      </div>

      {/* Save snapshot */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 space-y-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Version label (optional)"
          className="w-full text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-gray-800 dark:text-gray-200 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={handleSave}
          disabled={loading}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-500 disabled:opacity-50 transition-colors"
        >
          <Save size={12} />
          Save Snapshot
        </button>
      </div>

      {/* Version list */}
      <div className="flex-1 overflow-y-auto">
        {versions.length === 0 && !loading && (
          <p className="text-xs text-gray-500 dark:text-gray-400 px-4 py-3">No versions saved yet.</p>
        )}
        {versions.map((v) => (
          <div
            key={v.id}
            className="px-4 py-2.5 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-900 dark:text-gray-100">
                v{v.version_number}
                {v.label && <span className="ml-1.5 text-gray-500 dark:text-gray-400">— {v.label}</span>}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleRestore(v)}
                  className="p-1 text-blue-500 hover:text-blue-400"
                  title="Restore this version"
                >
                  <RotateCcw size={12} />
                </button>
                <button
                  onClick={() => projectId && removeVersion(projectId, v.id)}
                  className="p-1 text-red-500 hover:text-red-400"
                  title="Delete this version"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
            <span className="text-xs text-gray-500 dark:text-gray-400">{formatDate(v.created_at)}</span>
          </div>
        ))}
      </div>

      {/* Diff section */}
      {versions.length >= 2 && (
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-800 space-y-2">
          <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300">Compare Versions</h4>
          <div className="flex gap-2">
            <select
              value={diffV1}
              onChange={(e) => setDiffV1(e.target.value)}
              className="flex-1 text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-1 text-gray-800 dark:text-gray-200"
            >
              <option value="">From</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>v{v.version_number}</option>
              ))}
            </select>
            <select
              value={diffV2}
              onChange={(e) => setDiffV2(e.target.value)}
              className="flex-1 text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-1 text-gray-800 dark:text-gray-200"
            >
              <option value="">To</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>v{v.version_number}</option>
              ))}
            </select>
            <button
              onClick={handleDiff}
              disabled={!diffV1 || !diffV2}
              className="px-2 py-1 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50"
            >
              <GitCompare size={12} />
            </button>
          </div>
          {diffResult && (
            <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1 max-h-32 overflow-y-auto">
              <p className="text-green-500">+{diffResult.added_nodes.length} nodes added</p>
              <p className="text-red-500">-{diffResult.removed_nodes.length} nodes removed</p>
              <p className="text-yellow-500">~{diffResult.modified_nodes.length} nodes modified</p>
              <p className="text-green-500">+{diffResult.added_edges.length} edges added</p>
              <p className="text-red-500">-{diffResult.removed_edges.length} edges removed</p>
              <p className="text-yellow-500">~{diffResult.modified_edges.length} edges modified</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
